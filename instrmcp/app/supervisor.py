"""The supervisor: observer + process orchestrator.

Owns the JupyterLab subprocess and exposes runtime health over a local HTTP/WS API
(served by :mod:`instrmcp.app.api`). It *observes* the kernel-hosted MCP server via
``check_http_mcp_server`` but never starts/stops it — the MCP server starts when a
notebook opens on the ``instrmcp`` kernel and dies with that kernel.

Everything runs in a single asyncio event loop: the JupyterLab stdout reader, the
health-check loop, and the uvicorn-served API + webapp.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional
from urllib.parse import parse_qs, urlsplit

from instrmcp.app import runfile
from instrmcp.app.components import Component, ComponentState, aggregate_state
from instrmcp.app.launcher import _URL_RE, build_jupyter_argv, build_jupyter_env
from instrmcp.app.logs import LogStore
from instrmcp.app.profiles import Profile
from instrmcp.utils.logging_config import get_logger
from instrmcp.utils.stdio_proxy import check_http_mcp_server

logger = get_logger("app.supervisor")

HEALTH_INTERVAL_S = 2.0
DEGRADE_AFTER = 3  # consecutive MCP failures before READY -> DEGRADED


class Supervisor:
    """Launches JupyterLab and serves the status API / webapp."""

    def __init__(self, profile: Profile, no_browser: bool = False) -> None:
        self.profile = profile
        self.no_browser = no_browser
        self.logs = LogStore()
        self.started_at = time.time()
        self.jupyter_url: Optional[str] = None

        self.components: dict[str, Component] = {
            "jupyter": Component("jupyter"),
            "mcp": Component("mcp", observed=True),
        }

        #: Latest cached MeasureIt status (populated in Milestone 4).
        self.measureit_status: Optional[dict] = None

        self._jupyter_proc: Optional[asyncio.subprocess.Process] = None
        self._tasks: list[asyncio.Task] = []
        self._uvicorn = None
        self._stop = asyncio.Event()
        self._shutting_down = False

    # -- lifecycle --------------------------------------------------------

    async def run(self) -> int:
        """Start everything and block until stopped."""
        import uvicorn

        from instrmcp.app.api import create_app

        await self._start_jupyter()
        self._write_run_file()

        self._tasks = [
            asyncio.create_task(self._read_jupyter_output(), name="jupyter-reader"),
            asyncio.create_task(self._health_loop(), name="health-loop"),
        ]
        if self.profile.measureit.enabled:
            self._tasks.append(
                asyncio.create_task(self._measureit_loop(), name="measureit-loop")
            )

        config = uvicorn.Config(
            create_app(self),
            host="127.0.0.1",
            port=self.profile.supervisor_port,
            log_level="warning",
            access_log=False,
            loop="asyncio",
        )
        self._uvicorn = uvicorn.Server(config)
        server_task = asyncio.create_task(self._uvicorn.serve(), name="api-server")

        print(f"  Dashboard:  http://127.0.0.1:{self.profile.supervisor_port}/\n")

        await self._stop.wait()
        await self.shutdown()
        server_task.cancel()
        return 0

    def request_stop(self) -> None:
        """Signal the run loop to shut down (called by SIGINT/SIGTERM or POST /stop)."""
        self._stop.set()

    async def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("Supervisor shutting down")

        for c in self.components.values():
            if not c.observed:
                c.set(ComponentState.STOPPED, "stopped")

        # Stop JupyterLab.
        if self._jupyter_proc and self._jupyter_proc.returncode is None:
            self._jupyter_proc.terminate()
            try:
                await asyncio.wait_for(self._jupyter_proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._jupyter_proc.kill()

        for task in self._tasks:
            task.cancel()

        if self._uvicorn is not None:
            self._uvicorn.should_exit = True

        runfile.remove_run_file(self.profile.name)
        self._stop.set()

    # -- JupyterLab -------------------------------------------------------

    async def _start_jupyter(self) -> None:
        argv = build_jupyter_argv(self.profile, no_browser=self.no_browser)
        cwd = self.profile.environment.working_dir or None
        logger.info("Launching JupyterLab: %s", " ".join(argv))
        self.components["jupyter"].set(ComponentState.STARTING, "launching")
        self.components["mcp"].set(
            ComponentState.STARTING, "waiting for a notebook on the instrmcp kernel"
        )
        self._jupyter_proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=build_jupyter_env(self.profile),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

    async def _read_jupyter_output(self) -> None:
        assert self._jupyter_proc is not None and self._jupyter_proc.stdout is not None
        async for raw in self._jupyter_proc.stdout:
            line = raw.decode(errors="replace").rstrip("\n")
            self.logs.append("jupyter", line)
            if self.jupyter_url is None:
                m = _URL_RE.search(line)
                if m:
                    self.jupyter_url = m.group(0)
                    self._write_run_file()
                    self.logs.append(
                        "supervisor", f"JupyterLab ready: {self.jupyter_url}"
                    )

    # -- health -----------------------------------------------------------

    async def _health_loop(self) -> None:
        while not self._stop.is_set():
            changed = self._poll_jupyter()
            changed |= await self._poll_mcp()
            if changed:
                self._broadcast_status()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=HEALTH_INTERVAL_S)
            except asyncio.TimeoutError:
                pass

    def _poll_jupyter(self) -> bool:
        comp = self.components["jupyter"]
        proc = self._jupyter_proc
        if proc is None:
            return False
        if proc.returncode is not None:
            return comp.set(
                ComponentState.ERROR,
                f"JupyterLab exited (rc={proc.returncode})",
                error=f"rc={proc.returncode}",
            )
        if self.jupyter_url:
            return comp.set(
                ComponentState.READY, f"running at {self.jupyter_url}", pid=proc.pid
            )
        return comp.set(ComponentState.STARTING, "starting", pid=proc.pid)

    async def _poll_mcp(self) -> bool:
        comp = self.components["mcp"]
        host, port = self.profile.mcp.host, self.profile.mcp.port
        up = await check_http_mcp_server(host, port)
        if up:
            comp.fail_count = 0
            return comp.set(ComponentState.READY, f"responding on {host}:{port}")
        comp.fail_count += 1
        if comp.state in (ComponentState.READY, ComponentState.DEGRADED):
            return comp.set(ComponentState.DEGRADED, "stopped responding")
        return comp.set(
            ComponentState.STARTING,
            "waiting for a notebook on the instrmcp kernel",
        )

    async def _measureit_loop(self) -> None:
        """Poll the measureit_get_status MCP tool over HTTP and broadcast changes.

        Reads sweep status out-of-process (no kernel comm). Silently no-ops while the
        MCP server / measureit option isn't available (the tool call returns None).
        """
        from instrmcp.app import mcp_client

        interval = max(0.25, self.profile.measureit.stream_interval_s)
        host, port = self.profile.mcp.host, self.profile.mcp.port
        while not self._stop.is_set():
            status = await mcp_client.get_measureit_status(host, port)
            if status != self.measureit_status:
                self.measureit_status = status
                self.logs.broadcast({"type": "measureit", "status": status})
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # -- introspection ----------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "profile": self.profile.name,
            "aggregate": aggregate_state(self.components).value,
            "components": {k: c.to_dict() for k, c in self.components.items()},
            "jupyter_url": self.jupyter_url,
            "mcp": {
                "host": self.profile.mcp.host,
                "port": self.profile.mcp.port,
                "mode": self.profile.mcp.mode,
                "options": sorted(self.profile.mcp.options),
            },
            "harness": {"expected": self.profile.harness.expected},
            "measureit": {
                "enabled": self.profile.measureit.enabled,
                "status": self.measureit_status,
            },
            "supervisor_port": self.profile.supervisor_port,
            "started_at": self.started_at,
            "uptime_s": time.time() - self.started_at,
        }

    def _broadcast_status(self) -> None:
        self.logs.broadcast({"type": "status", "status": self.snapshot()})

    def _write_run_file(self) -> None:
        runfile.write_run_file(
            self.profile.name,
            {
                "pid": os.getpid(),
                "jupyter_pid": self._jupyter_proc.pid if self._jupyter_proc else None,
                "supervisor_port": self.profile.supervisor_port,
                "mcp_host": self.profile.mcp.host,
                "mcp_port": self.profile.mcp.port,
                "jupyter_url": self.jupyter_url,
                "started_at": self.started_at,
            },
        )

    # -- control ----------------------------------------------------------

    async def restart_kernel(self) -> dict:
        """Restart all running kernels via the JupyterLab REST API (best effort)."""
        if not self.jupyter_url:
            return {"ok": False, "message": "JupyterLab URL not yet known"}
        try:
            import httpx

            split = urlsplit(self.jupyter_url)
            base = f"{split.scheme}://{split.netloc}"
            token = parse_qs(split.query).get("token", [None])[0]
            params = {"token": token} if token else {}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{base}/api/kernels", params=params)
                resp.raise_for_status()
                kernels = resp.json()
                restarted = []
                for k in kernels:
                    kid = k.get("id")
                    r = await client.post(
                        f"{base}/api/kernels/{kid}/restart", params=params
                    )
                    if r.status_code in (200, 204):
                        restarted.append(kid)
            return {"ok": True, "restarted": restarted}
        except Exception as e:  # pragma: no cover - network dependent
            return {"ok": False, "message": f"kernel restart failed: {e}"}
