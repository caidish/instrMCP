"""``instrmcp launch`` orchestration.

Loads a profile, runs a fail-fast doctor check, then hands off to the asyncio
``Supervisor`` (which spawns JupyterLab, runs the health loop, and serves the status
API + webapp). The argv/env builders here are shared with the supervisor.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import sys
from typing import Optional

from instrmcp.app import runfile
from instrmcp.app.doctor import run_doctor_sync
from instrmcp.app.profiles import Profile, load_profile
from instrmcp.utils.logging_config import get_logger

logger = get_logger("app.launcher")

# Matches the tokened lab URL JupyterLab prints on startup.
_URL_RE = re.compile(r"https?://[^\s]+/lab\S*")


def build_jupyter_argv(profile: Profile, no_browser: bool = False) -> list[str]:
    """Build the ``python -m jupyterlab`` argv from a profile."""
    j = profile.jupyter
    argv = [
        sys.executable,
        "-m",
        "jupyterlab",
        "--port",
        str(j.port),
        "--ServerApp.ip",
        j.host,
        "--MultiKernelManager.default_kernel_name",
        j.kernel_name,
    ]
    if j.notebook_dir:
        argv += ["--ServerApp.root_dir", j.notebook_dir]
    if no_browser or not j.open_browser:
        argv.append("--no-browser")
    return argv


def build_jupyter_env(profile: Profile) -> dict:
    """Build the environment for the JupyterLab subprocess."""
    env = dict(os.environ)
    env.update(profile.environment.env_vars or {})
    return env


def run_launch(
    profile_name: Optional[str] = None,
    no_browser: bool = False,
    force: bool = False,
) -> int:
    """Launch instrmcp for the given profile."""
    profile = load_profile(profile_name)

    # Fail-fast doctor: refuse to launch on hard failures unless --force.
    report = run_doctor_sync(profile)
    print(report.render())
    print()
    if not report.ok and not force:
        print("Refusing to launch: doctor reported failures. Use --force to override.")
        return 1

    existing = runfile.read_run_file(profile.name)
    if existing and runfile.process_alive(existing.get("pid", -1)):
        print(
            f"A supervisor for profile '{profile.name}' is already running "
            f"(pid {existing['pid']}). Use `instrmcp stop` first."
        )
        return 1

    print(f"Starting instrmcp (profile: {profile.name})...")
    print(
        f"  JupyterLab launching on "
        f"http://{profile.jupyter.host}:{profile.jupyter.port}"
    )
    print("  Open a notebook on the 'instrmcp' kernel to auto-start the MCP server.")
    print("  Press Ctrl+C to stop.")

    return asyncio.run(_serve(profile, no_browser))


async def _serve(profile: Profile, no_browser: bool) -> int:
    from instrmcp.app.supervisor import Supervisor

    supervisor = Supervisor(profile, no_browser=no_browser)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, supervisor.request_stop)
        except (NotImplementedError, ValueError):  # pragma: no cover - Windows
            pass

    return await supervisor.run()
