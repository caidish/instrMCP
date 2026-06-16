"""Minimal MCP-over-HTTP client for the supervisor.

The supervisor reads MeasureIt sweep status by calling the existing
``measureit_get_status`` MCP tool over HTTP — no kernel comm, no new MCP tool. This
keeps the supervisor out-of-process and reuses whatever the kernel already exposes.

The JSON-RPC handshake mirrors :func:`instrmcp.utils.stdio_proxy.check_http_mcp_server`
(initialize → notifications/initialized → tools/call). Responses may be SSE-framed, so
we reuse ``_parse_sse_text`` from that module.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from instrmcp.utils.stdio_proxy import _parse_sse_text

_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


async def call_tool(
    name: str,
    arguments: Optional[dict] = None,
    host: str = "127.0.0.1",
    port: int = 8123,
    timeout: float = 10.0,
) -> Optional[dict]:
    """Call an MCP tool over HTTP and return its JSON-RPC ``result``, or None.

    Returns None on any transport error, missing session, or tool error (e.g. the
    tool isn't registered because its option isn't enabled in the kernel).
    """
    endpoint = f"http://{host}:{port}/mcp"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            init = await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": "init",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "instrmcp-supervisor", "version": "1"},
                    },
                },
                headers=_JSON_HEADERS,
            )
            if init.status_code != 200:
                return None
            session_id = init.headers.get("mcp-session-id")
            if not session_id:
                return None

            headers = {**_JSON_HEADERS, "mcp-session-id": session_id}
            await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                headers=headers,
            )

            resp = await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": "call",
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments or {}},
                },
                headers=headers,
            )
            if resp.status_code != 200:
                return None
            payload = _parse_sse_text(resp.text)
            if "error" in payload:
                return None
            return payload.get("result")
    except Exception:
        return None


def _extract_text(result: dict) -> Optional[str]:
    """Pull the first text block out of a tools/call result."""
    content = result.get("content") if isinstance(result, dict) else None
    if not content:
        return None
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text")
    return None


async def get_measureit_status(
    host: str = "127.0.0.1", port: int = 8123, timeout: float = 10.0
) -> Optional[dict[str, Any]]:
    """Return parsed ``measureit_get_status`` output, or None if unavailable.

    Requests ``detailed=True`` so the result includes the per-sweep ``sweeps`` dict
    (state/progress/...) that the dashboard renders. The tool's default (concise) mode
    only returns ``sweep_names``/``count`` with no per-sweep details.
    """
    result = await call_tool(
        "measureit_get_status",
        arguments={"detailed": True},
        host=host,
        port=port,
        timeout=timeout,
    )
    if not result:
        return None
    text = _extract_text(result)
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
