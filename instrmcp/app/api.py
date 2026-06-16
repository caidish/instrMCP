"""Local status API + static webapp, served by the supervisor.

Starlette app (uvicorn-served from the supervisor's event loop). Same-origin: the
dashboard at ``GET /`` is served by this same app, so no CORS is required. Real MCP
control (mode/options/restart) lives in the JupyterLab notebook toolbar, not here —
``POST /restart-mcp`` is intentionally advisory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:  # avoid a circular import at runtime
    from instrmcp.app.supervisor import Supervisor

WEBAPP_DIR = Path(__file__).parent / "webapp"


def create_app(supervisor: "Supervisor") -> Starlette:
    """Build the Starlette app bound to a live supervisor."""

    async def status(request):
        return JSONResponse(supervisor.snapshot())

    async def profiles(request):
        from instrmcp.app.profiles import list_profiles

        return JSONResponse([p.model_dump() for p in list_profiles()])

    async def doctor(request):
        from instrmcp.app.doctor import run_doctor

        report = await run_doctor(supervisor.profile)
        return JSONResponse(report.model_dump())

    async def logs(request):
        component = request.query_params.get("component")
        try:
            lines = int(request.query_params.get("lines", "200"))
        except ValueError:
            lines = 200
        return JSONResponse(
            {
                "components": supervisor.logs.components(),
                "logs": supervisor.logs.tail(component, lines),
            }
        )

    async def measureit(request):
        return JSONResponse(
            {
                "enabled": supervisor.profile.measureit.enabled,
                "status": supervisor.measureit_status,
            }
        )

    async def start(request):
        # Idempotent: the supervisor is already running if this endpoint is reachable.
        return JSONResponse({"ok": True, "message": "supervisor already running"})

    async def stop(request):
        supervisor.request_stop()
        return JSONResponse({"ok": True, "message": "stopping"}, status_code=202)

    async def restart_kernel(request):
        result = await supervisor.restart_kernel()
        return JSONResponse(result, status_code=200 if result.get("ok") else 502)

    async def restart_mcp(request):
        return JSONResponse(
            {
                "ok": False,
                "advisory": True,
                "message": (
                    "Restart the MCP server from the JupyterLab notebook toolbar "
                    "(or run %mcp_restart in the kernel). The supervisor cannot "
                    "restart the kernel-hosted MCP server directly."
                ),
            },
            status_code=202,
        )

    async def events_ws(websocket):
        await websocket.accept()
        queue = supervisor.logs.subscribe()
        # Send an initial status snapshot so a fresh client renders immediately.
        try:
            await websocket.send_json(
                {"type": "status", "status": supervisor.snapshot()}
            )
            while True:
                event = await queue.get()
                await websocket.send_json(event)
        except Exception:
            pass
        finally:
            supervisor.logs.unsubscribe(queue)

    routes = [
        Route("/status", status),
        Route("/profiles", profiles),
        Route("/doctor", doctor),
        Route("/logs", logs),
        Route("/measureit", measureit),
        Route("/start", start, methods=["POST"]),
        Route("/stop", stop, methods=["POST"]),
        Route("/restart-kernel", restart_kernel, methods=["POST"]),
        Route("/restart-mcp", restart_mcp, methods=["POST"]),
        WebSocketRoute("/events", events_ws),
    ]

    # Mount the static dashboard at "/" if it exists (added in Milestone 3).
    if WEBAPP_DIR.is_dir():
        routes.append(Mount("/", app=StaticFiles(directory=str(WEBAPP_DIR), html=True)))

    return Starlette(routes=routes)
