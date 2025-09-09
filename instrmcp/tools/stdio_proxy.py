"""
Shared STDIO↔HTTP MCP proxy utilities.

Provides a small MCP server over STDIO that forwards initialize/initialized and
tools/* JSON-RPC calls to an HTTP MCP server (e.g., http://127.0.0.1:8123/mcp).

Used by both Claude Desktop and Codex launchers to avoid code duplication.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import httpx
from fastmcp import FastMCP
from mcp.types import TextContent

logger = logging.getLogger(__name__)


class HttpMCPProxy:
    """Proxy helper that talks to a Streamable HTTP MCP server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8123"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.working_endpoint: Optional[str] = None
        self.session_id: Optional[str] = None

    async def _find_working_endpoint(self) -> str:
        if self.working_endpoint:
            return self.working_endpoint

        endpoint = f"{self.base_url}/mcp"

        test_request = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": "tools/list",
            "params": {},
        }

        try:
            resp = await self.client.post(
                endpoint,
                json=test_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            if resp.status_code == 200:
                # SSE or JSON
                text = resp.text
                if "data: " in text:
                    payload = json.loads(text.split("data: ")[1].strip())
                else:
                    payload = resp.json()
                if "jsonrpc" in payload and ("result" in payload or "error" in payload):
                    self.working_endpoint = endpoint
                    return endpoint
        except Exception:
            pass

        # Default to /mcp
        self.working_endpoint = endpoint
        return endpoint

    async def _ensure_session(self) -> None:
        if self.session_id:
            return

        endpoint = await self._find_working_endpoint()
        init_request = {
            "jsonrpc": "2.0",
            "id": "init",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "InstrMCP Proxy", "version": "1.0.0"},
            },
        }

        try:
            resp = await self.client.post(
                endpoint,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            if resp.status_code == 200:
                self.session_id = resp.headers.get("mcp-session-id") or "default-session"
                # Send initialized notification
                await self.client.post(
                    endpoint,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": self.session_id,
                    },
                )
            else:
                self.session_id = "default-session"
        except Exception:
            self.session_id = "default-session"

    async def call(self, tool_name: str, **kwargs) -> dict:
        try:
            await self._ensure_session()
            endpoint = await self._find_working_endpoint()

            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": kwargs or {}},
            }

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if self.session_id:
                headers["mcp-session-id"] = self.session_id

            resp = await self.client.post(endpoint, json=req, headers=headers)
            resp.raise_for_status()

            text = resp.text
            if "data: " in text:
                payload = json.loads(text.split("data: ")[1].strip())
            else:
                payload = resp.json()

            if "error" in payload:
                return {"error": f"MCP error: {payload['error']}"}
            if "result" in payload:
                result = payload["result"]
                if isinstance(result, dict) and "content" in result:
                    content = result.get("content", [])
                    if content:
                        return content[0].get("text", "")
                return result
            return {"error": "Invalid JSON-RPC response"}
        except Exception as e:
            return {"error": f"Proxy request failed: {e}"}


async def check_http_mcp_server(host: str = "127.0.0.1", port: int = 8123) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            endpoint = f"http://{host}:{port}/mcp"
            init_request = {
                "jsonrpc": "2.0",
                "id": "test-init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "Proxy Test", "version": "1.0.0"},
                },
            }

            init_resp = await client.post(
                endpoint,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            if init_resp.status_code != 200:
                return False

            session_id = init_resp.headers.get("mcp-session-id")
            if not session_id:
                return False

            await client.post(
                endpoint,
                json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )

            test_resp = await client.post(
                endpoint,
                json={"jsonrpc": "2.0", "id": "test-tools", "method": "tools/list", "params": {}},
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )
            if test_resp.status_code != 200:
                return False

            text = test_resp.text
            payload = json.loads(text.split("data: ")[1].strip()) if "data: " in text else test_resp.json()
            return "jsonrpc" in payload and ("result" in payload or "error" in payload)
    except Exception:
        return False


def create_stdio_proxy_server(base_url: str, server_name: str = "InstrMCP Proxy") -> FastMCP:
    mcp = FastMCP(server_name)
    proxy = HttpMCPProxy(base_url)

    @mcp.tool()
    async def list_instruments() -> list[TextContent]:
        result = await proxy.call("list_instruments")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def instrument_info(name: str, with_values: bool = False) -> list[TextContent]:
        result = await proxy.call("instrument_info", name=name, with_values=with_values)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def get_parameter_value(instrument: str, parameter: str, fresh: bool = False) -> list[TextContent]:
        result = await proxy.call("get_parameter_value", instrument=instrument, parameter=parameter, fresh=fresh)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def station_snapshot() -> list[TextContent]:
        result = await proxy.call("station_snapshot")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def list_variables(type_filter: Optional[str] = None) -> list[TextContent]:
        result = await proxy.call("list_variables", type_filter=type_filter)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def get_parameter_values(queries: str) -> list[TextContent]:
        result = await proxy.call("get_parameter_values", queries=queries)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def get_variable_info(name: str) -> list[TextContent]:
        result = await proxy.call("get_variable_info", name=name)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def get_notebook_cells(num_cells: int = 2, include_output: bool = True) -> list[TextContent]:
        result = await proxy.call("get_notebook_cells", num_cells=num_cells, include_output=include_output)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def get_editing_cell(fresh_ms: int = 1000) -> list[TextContent]:
        result = await proxy.call("get_editing_cell", fresh_ms=fresh_ms)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def update_editing_cell(content: str) -> list[TextContent]:
        result = await proxy.call("update_editing_cell", content=content)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def suggest_code(description: str, context: str = "") -> list[TextContent]:
        result = await proxy.call("suggest_code", description=description, context=context)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def execute_editing_cell() -> list[TextContent]:
        result = await proxy.call("execute_editing_cell")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool()
    async def server_status() -> list[TextContent]:
        result = await proxy.call("server_status")
        info = {"mode": "proxy", "proxy_target": base_url, "jupyter_server_status": result}
        return [TextContent(type="text", text=str(info))]

    return mcp

