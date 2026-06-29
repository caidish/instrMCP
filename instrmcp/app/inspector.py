"""Synchronous facade over :mod:`instrmcp.app.mcp_client` for the GUI Inspector.

The embedded Inspector tab in the Streamlit control panel lets a user browse the
kernel-hosted MCP server's tools / resources / prompts and call them — a native,
Node-free alternative to the official (npx) MCP Inspector. Streamlit runs
synchronously, so this module wraps the async ``mcp_client`` coroutines with
``asyncio.run`` and returns plain ``{ok, ..., error}`` dicts the UI can render.

Everything here is pure Python over HTTP to ``127.0.0.1:8123/mcp`` — no kernel
comm, no new MCP tool, no Node runtime. It reuses the same JSON-RPC handshake as
the MeasureIt status poll.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from instrmcp.app import mcp_client


def _run(coro: Any) -> Any:
    """Run an async coroutine to completion from synchronous Streamlit code."""
    return asyncio.run(coro)


def parse_json_args(text: str):
    """Parse a JSON-object argument string from the GUI.

    Returns ``(args_dict, None)`` on success or ``(None, error_message)``. Empty
    input is treated as ``{}`` (no arguments).
    """
    text = (text or "").strip()
    if not text:
        return {}, None
    try:
        value = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    if not isinstance(value, dict):
        return None, 'Arguments must be a JSON object, e.g. {"name": "value"}.'
    return value, None


def inspect(host: str = "127.0.0.1", port: int = 8123, timeout: float = 10.0) -> dict:
    """Snapshot the server's tools / resources / prompts.

    Returns ``{ok, tools, resources, prompts, error}``. ``ok`` is False only when
    the server can't be reached (``tools/list`` fails the handshake); a server
    that simply has no resources/prompts capability yields empty lists, not an
    error.
    """

    async def _gather() -> dict:
        tools = await mcp_client.list_tools(host=host, port=port, timeout=timeout)
        if tools is None:
            return {
                "ok": False,
                "error": (
                    f"Could not reach the MCP server at {host}:{port}. "
                    "Start it from the JupyterLab toolbar (Start), then retry."
                ),
                "tools": [],
                "resources": [],
                "prompts": [],
            }
        resources = await mcp_client.list_resources(
            host=host, port=port, timeout=timeout
        )
        prompts = await mcp_client.list_prompts(host=host, port=port, timeout=timeout)
        return {
            "ok": True,
            "error": None,
            "tools": tools,
            "resources": resources or [],
            "prompts": prompts or [],
        }

    return _run(_gather())


def call_tool_sync(
    name: str,
    arguments: Optional[dict] = None,
    host: str = "127.0.0.1",
    port: int = 8123,
    timeout: float = 30.0,
) -> dict:
    """Call a tool and return ``{ok, result, text, error}``."""
    result = _run(
        mcp_client.call_tool(name, arguments, host=host, port=port, timeout=timeout)
    )
    if result is None:
        return {
            "ok": False,
            "result": None,
            "text": None,
            "error": f"Tool '{name}' failed or is not available.",
        }
    return {
        "ok": True,
        "result": result,
        "text": mcp_client._extract_text(result),
        "error": None,
    }


def read_resource_sync(
    uri: str,
    host: str = "127.0.0.1",
    port: int = 8123,
    timeout: float = 30.0,
) -> dict:
    """Read a resource by URI and return ``{ok, result, error}``."""
    result = _run(mcp_client.read_resource(uri, host=host, port=port, timeout=timeout))
    if result is None:
        return {
            "ok": False,
            "result": None,
            "error": f"Resource '{uri}' could not be read.",
        }
    return {"ok": True, "result": result, "error": None}


def get_prompt_sync(
    name: str,
    arguments: Optional[dict] = None,
    host: str = "127.0.0.1",
    port: int = 8123,
    timeout: float = 30.0,
) -> dict:
    """Render a prompt and return ``{ok, result, error}``."""
    result = _run(
        mcp_client.get_prompt(name, arguments, host=host, port=port, timeout=timeout)
    )
    if result is None:
        return {
            "ok": False,
            "result": None,
            "error": f"Prompt '{name}' could not be rendered.",
        }
    return {"ok": True, "result": result, "error": None}
