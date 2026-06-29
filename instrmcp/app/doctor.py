"""Doctor / health checks for the InstrMCP App.

Produces a user-readable diagnostic report covering the Python environment, JupyterLab,
the auto-loading kernelspec, profile validity, and MCP reachability. Checks are pure —
they never mutate state, install anything, or launch processes.

``run_doctor`` is the async canonical entry point (used by the supervisor API);
``run_doctor_sync`` wraps it for the CLI.
"""

from __future__ import annotations

import asyncio
import importlib.util
import socket
import sys
from typing import Literal, Optional

from pydantic import BaseModel, Field

from instrmcp.app.install_kernel import installed_kernel_metadata, kernel_installed
from instrmcp.app.profiles import Profile, validate_profile
from instrmcp.utils.stdio_proxy import check_http_mcp_server

Status = Literal["ok", "warn", "fail"]


class DoctorCheck(BaseModel):
    name: str
    status: Status
    detail: str
    fix: Optional[str] = None


class DoctorReport(BaseModel):
    profile: str
    checks: list[DoctorCheck] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True if no check failed (warnings are tolerated)."""
        return all(c.status != "fail" for c in self.checks)

    def render(self) -> str:
        """Render a human-readable report."""
        symbol = {"ok": "OK  ", "warn": "WARN", "fail": "FAIL"}
        lines = [f"Doctor Check (profile: {self.profile})", ""]
        for c in self.checks:
            lines.append(f"  [{symbol[c.status]}] {c.name}: {c.detail}")
            if c.fix and c.status != "ok":
                lines.append(f"           fix: {c.fix}")
        lines.append("")
        lines.append("Result: " + ("healthy" if self.ok else "problems found"))
        return "\n".join(lines)


def _port_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """Return True if a TCP connection to ``host:port`` succeeds (something listening)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def run_doctor(profile: Profile) -> DoctorReport:
    """Run all diagnostic checks for ``profile`` and return a report."""
    checks: list[DoctorCheck] = []

    # 1. Python version.
    py = sys.version_info
    if py >= (3, 10):
        checks.append(
            DoctorCheck(
                name="Python",
                status="ok",
                detail=f"{py.major}.{py.minor}.{py.micro}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="Python",
                status="fail",
                detail=f"{py.major}.{py.minor} (need >= 3.10)",
                fix="Use a Python 3.10+ environment (e.g. conda env instrMCPdev).",
            )
        )

    # 2. instrmcp package.
    try:
        from instrmcp import __version__

        checks.append(
            DoctorCheck(name="instrmcp package", status="ok", detail=__version__)
        )
    except Exception as e:  # pragma: no cover - defensive
        checks.append(
            DoctorCheck(
                name="instrmcp package", status="fail", detail=f"import failed: {e}"
            )
        )

    # 3. JupyterLab.
    if importlib.util.find_spec("jupyterlab") is not None:
        checks.append(DoctorCheck(name="JupyterLab", status="ok", detail="installed"))
    else:
        checks.append(
            DoctorCheck(
                name="JupyterLab",
                status="fail",
                detail="not installed",
                fix="pip install jupyterlab",
            )
        )

    # 4. jupyter_client (needed for kernelspec install).
    if importlib.util.find_spec("jupyter_client") is not None:
        checks.append(
            DoctorCheck(name="jupyter_client", status="ok", detail="installed")
        )
    else:
        checks.append(
            DoctorCheck(
                name="jupyter_client",
                status="fail",
                detail="not installed",
                fix="pip install jupyter_client",
            )
        )

    # 5. instrmcp kernelspec.
    kernel_name = profile.jupyter.kernel_name
    if kernel_installed(kernel_name):
        checks.append(
            DoctorCheck(
                name=f"kernelspec '{kernel_name}'", status="ok", detail="installed"
            )
        )
        # 6. Kernelspec drift vs active profile.
        meta = installed_kernel_metadata(kernel_name) or {}
        want = {
            "mode": profile.mcp.mode,
            "options": sorted(profile.mcp.options),
            "autostart": profile.mcp.autostart,
        }
        have = {
            "mode": meta.get("mode"),
            "options": sorted(meta.get("options", [])),
            "autostart": meta.get("autostart"),
        }
        if meta and have != want:
            checks.append(
                DoctorCheck(
                    name="kernelspec drift",
                    status="warn",
                    detail=f"installed {have} != profile {want}",
                    fix=f"instrmcp install-kernel --profile {profile.name}",
                )
            )
    else:
        # The kernelspec is OPTIONAL: it only powers the advanced auto-start-on-kernel
        # path. The normal flow (open a notebook, click Start in the InstrMCP toolbar)
        # works with any kernel, so a missing kernelspec is not a failure.
        checks.append(
            DoctorCheck(
                name=f"kernelspec '{kernel_name}'",
                status="warn",
                detail="not installed (optional; the notebook toolbar works without it)",
                fix=f"Optional auto-start kernel: instrmcp install-kernel --profile {profile.name}",
            )
        )

    # 7. Profile validity.
    errors = validate_profile(profile)
    if errors:
        checks.append(
            DoctorCheck(
                name="profile validation",
                status="fail",
                detail="; ".join(errors),
                fix="Edit the profile to resolve the listed issues.",
            )
        )
    else:
        checks.append(
            DoctorCheck(name="profile validation", status="ok", detail="valid")
        )

    # 8. MCP port / reachability.
    host, port = profile.mcp.host, profile.mcp.port
    if _port_listening(host, port):
        if await check_http_mcp_server(host, port):
            checks.append(
                DoctorCheck(
                    name="MCP server",
                    status="ok",
                    detail=f"responding on {host}:{port}",
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name="MCP server",
                    status="warn",
                    detail=f"a non-MCP process is listening on {host}:{port}",
                    fix="Free the port or change mcp.port; two instrmcp kernels collide.",
                )
            )
    else:
        checks.append(
            DoctorCheck(
                name="MCP server",
                status="ok",
                detail=f"port {host}:{port} free (MCP starts with the kernel)",
            )
        )

    # 9. measureit option vs package availability.
    if "measureit" in profile.mcp.options:
        if importlib.util.find_spec("measureit") is not None:
            checks.append(
                DoctorCheck(name="measureit", status="ok", detail="installed")
            )
        else:
            checks.append(
                DoctorCheck(
                    name="measureit",
                    status="warn",
                    detail="option enabled but package not importable",
                    fix="Install MeasureIt or remove 'measureit' from mcp.options.",
                )
            )

    # 10. conda environment hint.
    want_env = profile.environment.conda_env
    if want_env:
        import os

        have_env = os.environ.get("CONDA_DEFAULT_ENV")
        if have_env == want_env:
            checks.append(DoctorCheck(name="conda env", status="ok", detail=have_env))
        else:
            checks.append(
                DoctorCheck(
                    name="conda env",
                    status="warn",
                    detail=f"active '{have_env}' != profile '{want_env}'",
                    fix=f"conda activate {want_env}",
                )
            )

    return DoctorReport(profile=profile.name, checks=checks)


def run_doctor_sync(profile: Profile) -> DoctorReport:
    """Synchronous wrapper around :func:`run_doctor` for CLI use."""
    return asyncio.run(run_doctor(profile))
