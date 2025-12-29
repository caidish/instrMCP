"""
Shared STDIO↔HTTP MCP proxy utilities.

Provides a small MCP server over STDIO that forwards initialize/initialized and
tools/* JSON-RPC calls to an HTTP MCP server (e.g., http://127.0.0.1:8123/mcp).

Used by both Claude Desktop and Codex launchers to avoid code duplication.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx
from fastmcp import FastMCP
from mcp.types import TextContent, Resource, TextResourceContents

logger = logging.getLogger(__name__)


class HttpMCPProxy:
    """Proxy helper that talks to a Streamable HTTP MCP server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8123"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.working_endpoint: Optional[str] = None
        self.session_id: Optional[str] = None
        self._resource_cache: dict = {}  # Cache for resource list

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
                self.session_id = (
                    resp.headers.get("mcp-session-id") or "default-session"
                )
                # Send initialized notification
                await self.client.post(
                    endpoint,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {},
                    },
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

    async def list_resources(self) -> list:
        """List available resources from the HTTP MCP server."""
        try:
            await self._ensure_session()
            endpoint = await self._find_working_endpoint()

            req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "resources/list",
                "params": {},
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
                logger.error(f"Error listing resources: {payload['error']}")
                return []
            if "result" in payload:
                result = payload["result"]
                if isinstance(result, dict) and "resources" in result:
                    return result["resources"]
                return []
            return []
        except Exception as e:
            logger.error(f"Failed to list resources: {e}")
            return []

    async def read_resource(self, uri: str) -> dict:
        """Read a specific resource from the HTTP MCP server."""
        try:
            await self._ensure_session()
            endpoint = await self._find_working_endpoint()

            req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": uri},
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
                return payload["result"]
            return {"error": "Invalid JSON-RPC response"}
        except Exception as e:
            return {"error": f"Failed to read resource: {e}"}


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
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )

            test_resp = await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": "test-tools",
                    "method": "tools/list",
                    "params": {},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )
            if test_resp.status_code != 200:
                return False

            text = test_resp.text
            payload = (
                json.loads(text.split("data: ")[1].strip())
                if "data: " in text
                else test_resp.json()
            )
            return "jsonrpc" in payload and ("result" in payload or "error" in payload)
    except Exception:
        return False


def create_stdio_proxy_server(
    base_url: str, server_name: str = "InstrMCP Proxy"
) -> FastMCP:
    mcp = FastMCP(server_name)
    proxy = HttpMCPProxy(base_url)

    # QCodes instrument tools
    @mcp.tool(
        name="qcodes_instrument_info",
        annotations={
            "title": "Get Instrument Info",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def instrument_info(
        name: str, with_values: bool = False, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "qcodes_instrument_info",
            name=name,
            with_values=with_values,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="qcodes_get_parameter_values",
        annotations={
            "title": "Get Parameter Values",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_parameter_values(
        queries: str, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "qcodes_get_parameter_values", queries=queries, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    # Jupyter notebook variable tools
    @mcp.tool(
        name="notebook_list_variables",
        annotations={
            "title": "List Notebook Variables",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_variables(type_filter: Optional[str] = None) -> list[TextContent]:
        result = await proxy.call("notebook_list_variables", type_filter=type_filter)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_get_variable_info",
        annotations={
            "title": "Get Variable Info",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_variable_info(name: str, detailed: bool = False) -> list[TextContent]:
        result = await proxy.call(
            "notebook_get_variable_info", name=name, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_get_editing_cell",
        annotations={
            "title": "Get Active Cell",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_editing_cell(
        fresh_ms: int = 1000,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        max_lines: int = 200,
        detailed: bool = False,
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_get_editing_cell",
            fresh_ms=fresh_ms,
            line_start=line_start,
            line_end=line_end,
            max_lines=max_lines,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_update_editing_cell",
        annotations={
            "title": "Update Active Cell",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def update_editing_cell(
        content: str, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_update_editing_cell", content=content, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_get_editing_cell_output",
        annotations={
            "title": "Get Cell Output",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_editing_cell_output(detailed: bool = False) -> list[TextContent]:
        result = await proxy.call("notebook_get_editing_cell_output", detailed=detailed)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_get_notebook_cells",
        annotations={
            "title": "Get Recent Cells",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_notebook_cells(
        num_cells: int = 2, include_output: bool = True, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_get_notebook_cells",
            num_cells=num_cells,
            include_output=include_output,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_server_status",
        annotations={
            "title": "Server Status",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def server_status() -> list[TextContent]:
        result = await proxy.call("notebook_server_status")
        info = {
            "mode": "proxy",
            "proxy_target": base_url,
            "jupyter_server_status": result,
        }
        return [TextContent(type="text", text=str(info))]

    @mcp.tool(
        name="mcp_list_resources",
        annotations={
            "title": "List MCP Resources",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_resources() -> list[TextContent]:
        """
        List all available MCP resources and guide on when to use them.

        MCP Resources provide READ-ONLY reference data and templates,
        while Tools perform active operations. Use this tool to discover
        what context and documentation is available.
        """
        result = await proxy.call("mcp_list_resources")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="mcp_get_resource",
        annotations={
            "title": "Get MCP Resource",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_resource(uri: str) -> list[TextContent]:
        """
        Retrieve the content of a specific MCP resource by its URI.

        Use this tool to access resource content when you need the actual data
        (e.g., instrument list, templates, configuration). This is a fallback
        when direct resource access is not available.

        Args:
            uri: Resource URI (e.g., "resource://available_instruments")

        Returns:
            Resource content as JSON or text.

        Examples:
            - mcp_get_resource("resource://available_instruments")
            - mcp_get_resource("resource://measureit_sweep1d_template")
            - mcp_get_resource("resource://database_config")
        """
        result = await proxy.call("mcp_get_resource", uri=uri)
        return [TextContent(type="text", text=str(result))]

    # Unsafe notebook tools
    @mcp.tool(
        name="notebook_execute_cell",
        annotations={
            "title": "Execute Cell",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def execute_editing_cell(
        timeout: float = 30.0, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_execute_cell", timeout=timeout, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_add_cell",
        annotations={
            "title": "Add Cell",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def add_new_cell(
        cell_type: str = "code",
        position: str = "below",
        content: str = "",
        detailed: bool = False,
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_add_cell",
            cell_type=cell_type,
            position=position,
            content=content,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_delete_cell",
        annotations={
            "title": "Delete Cell",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def delete_editing_cell(detailed: bool = False) -> list[TextContent]:
        result = await proxy.call("notebook_delete_cell", detailed=detailed)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_delete_cells",
        annotations={
            "title": "Delete Multiple Cells",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def delete_cells_by_number(
        cell_numbers: str, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_delete_cells", cell_numbers=cell_numbers, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_apply_patch",
        annotations={
            "title": "Apply Patch",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def apply_patch(
        old_text: str, new_text: str, detailed: bool = False
    ) -> list[TextContent]:
        result = await proxy.call(
            "notebook_apply_patch",
            old_text=old_text,
            new_text=new_text,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="notebook_move_cursor",
        annotations={
            "title": "Move Cursor",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def move_cursor(target: str, detailed: bool = False) -> list[TextContent]:
        result = await proxy.call(
            "notebook_move_cursor", target=target, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    # MeasureIt integration tools (optional - only if measureit option enabled)
    @mcp.tool(
        name="measureit_get_status",
        annotations={
            "title": "MeasureIt Status",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_measureit_status(detailed: bool = False) -> list[TextContent]:
        """Check if any MeasureIt sweep is currently running."""
        result = await proxy.call("measureit_get_status", detailed=detailed)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="measureit_wait_for_all_sweeps",
        annotations={
            "title": "Wait for All Sweeps",
            "readOnlyHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def wait_for_all_sweeps(detailed: bool = False) -> list[TextContent]:
        """Wait until all currently running MeasureIt sweeps finish."""
        result = await proxy.call("measureit_wait_for_all_sweeps", detailed=detailed)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="measureit_wait_for_sweep",
        annotations={
            "title": "Wait for Sweep",
            "readOnlyHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def wait_for_sweep(
        variable_name: str, detailed: bool = False
    ) -> list[TextContent]:
        """Wait until the specified MeasureIt sweep finishes."""
        result = await proxy.call(
            "measureit_wait_for_sweep", variable_name=variable_name, detailed=detailed
        )
        return [TextContent(type="text", text=str(result))]

    # Database integration tools (optional - only if database option enabled)
    @mcp.tool(
        name="database_list_experiments",
        annotations={
            "title": "List Experiments",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_experiments(
        database_path: Optional[str] = None,
        detailed: bool = False,
    ) -> list[TextContent]:
        result = await proxy.call(
            "database_list_experiments",
            database_path=database_path,
            detailed=detailed,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="database_get_dataset_info",
        annotations={
            "title": "Get Dataset Info",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_dataset_info(
        id: int,
        database_path: Optional[str] = None,
        detailed: bool = False,
        code_suggestion: bool = False,
    ) -> list[TextContent]:
        result = await proxy.call(
            "database_get_dataset_info",
            id=id,
            database_path=database_path,
            detailed=detailed,
            code_suggestion=code_suggestion,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="database_get_database_stats",
        annotations={
            "title": "Database Statistics",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_database_stats(
        database_path: Optional[str] = None,
    ) -> list[TextContent]:
        result = await proxy.call(
            "database_get_database_stats", database_path=database_path
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="database_list_available",
        annotations={
            "title": "List Databases",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_available_databases(detailed: bool = False) -> list[TextContent]:
        result = await proxy.call("database_list_available", detailed=detailed)
        return [TextContent(type="text", text=str(result))]

    # Dynamic tool meta-tools (only available in unsafe mode)
    @mcp.tool(
        name="dynamic_register_tool",
        annotations={
            "title": "Register Dynamic Tool",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def register_dynamic_tool(
        name: str,
        version: str,
        description: str,
        author: str,
        capabilities: str,
        parameters: str,
        returns: str,
        source_code: str,
        examples: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> list[TextContent]:
        """Register a new dynamic tool."""
        result = await proxy.call(
            "dynamic_register_tool",
            name=name,
            version=version,
            description=description,
            author=author,
            capabilities=capabilities,
            parameters=parameters,
            returns=returns,
            source_code=source_code,
            examples=examples,
            tags=tags,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="dynamic_update_tool",
        annotations={
            "title": "Update Dynamic Tool",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def update_dynamic_tool(
        name: str,
        version: str,
        description: Optional[str] = None,
        capabilities: Optional[str] = None,
        parameters: Optional[str] = None,
        returns: Optional[str] = None,
        source_code: Optional[str] = None,
        examples: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> list[TextContent]:
        """Update an existing dynamic tool."""
        result = await proxy.call(
            "dynamic_update_tool",
            name=name,
            version=version,
            description=description,
            capabilities=capabilities,
            parameters=parameters,
            returns=returns,
            source_code=source_code,
            examples=examples,
            tags=tags,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="dynamic_revoke_tool",
        annotations={
            "title": "Revoke Dynamic Tool",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def revoke_dynamic_tool(
        name: str, reason: Optional[str] = None
    ) -> list[TextContent]:
        """Revoke (delete) a dynamic tool."""
        result = await proxy.call("dynamic_revoke_tool", name=name, reason=reason)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="dynamic_list_tools",
        annotations={
            "title": "List Dynamic Tools",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def list_dynamic_tools(
        tag: Optional[str] = None,
        capability: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[TextContent]:
        """List all registered dynamic tools with optional filtering."""
        result = await proxy.call(
            "dynamic_list_tools", tag=tag, capability=capability, author=author
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="dynamic_inspect_tool",
        annotations={
            "title": "Inspect Dynamic Tool",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def inspect_dynamic_tool(name: str) -> list[TextContent]:
        """Inspect a dynamic tool's complete specification."""
        result = await proxy.call("dynamic_inspect_tool", name=name)
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(
        name="dynamic_registry_stats",
        annotations={
            "title": "Registry Statistics",
            "readOnlyHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_dynamic_registry_stats() -> list[TextContent]:
        """Get statistics about the dynamic tool registry."""
        result = await proxy.call("dynamic_registry_stats")
        return [TextContent(type="text", text=str(result))]

    # Register resources
    # Core QCodes resources
    @mcp.resource("resource://available_instruments")
    async def available_instruments() -> Resource:
        """Resource providing list of available QCodes instruments."""
        result = await proxy.read_resource("resource://available_instruments")
        if "error" in result:
            error_content = json.dumps({"error": result["error"]}, indent=2)
            return Resource(
                uri="resource://available_instruments",
                name="Available Instruments (Error)",
                description="Error retrieving available instruments",
                mimeType="application/json",
                contents=[
                    TextResourceContents(
                        uri="resource://available_instruments",
                        mimeType="application/json",
                        text=error_content,
                    )
                ],
            )

        # Extract content from result
        contents_data = result.get("contents", [])
        if contents_data and isinstance(contents_data, list):
            text_content = contents_data[0].get("text", "{}")
        else:
            text_content = "{}"

        return Resource(
            uri="resource://available_instruments",
            name="Available Instruments",
            description=(
                "List of QCodes instruments available in the namespace "
                "with hierarchical parameter structure"
            ),
            mimeType="application/json",
            contents=[
                TextResourceContents(
                    uri="resource://available_instruments",
                    mimeType="application/json",
                    text=text_content,
                )
            ],
        )

    @mcp.resource("resource://station_state")
    async def station_state() -> Resource:
        """Resource providing current QCodes station snapshot."""
        result = await proxy.read_resource("resource://station_state")
        if "error" in result:
            error_content = json.dumps({"error": result["error"]}, indent=2)
            return Resource(
                uri="resource://station_state",
                name="Station State (Error)",
                description="Error retrieving station state",
                mimeType="application/json",
                contents=[
                    TextResourceContents(
                        uri="resource://station_state",
                        mimeType="application/json",
                        text=error_content,
                    )
                ],
            )

        # Extract content from result
        contents_data = result.get("contents", [])
        if contents_data and isinstance(contents_data, list):
            text_content = contents_data[0].get("text", "{}")
        else:
            text_content = "{}"

        return Resource(
            uri="resource://station_state",
            name="QCodes Station State",
            description="Current QCodes station snapshot without parameter values",
            mimeType="application/json",
            contents=[
                TextResourceContents(
                    uri="resource://station_state",
                    mimeType="application/json",
                    text=text_content,
                )
            ],
        )

    # MeasureIt resources (optional - only available if measureit option is enabled on server)
    measureit_resources = [
        (
            "measureit_sweep0d_template",
            "MeasureIt Sweep0D Template",
            "Sweep0D code examples and patterns for time-based monitoring",
        ),
        (
            "measureit_sweep1d_template",
            "MeasureIt Sweep1D Template",
            "Sweep1D code examples and patterns for single parameter sweeps",
        ),
        (
            "measureit_sweep2d_template",
            "MeasureIt Sweep2D Template",
            "Sweep2D code examples and patterns for 2D parameter mapping",
        ),
        (
            "measureit_simulsweep_template",
            "MeasureIt SimulSweep Template",
            "SimulSweep code examples for simultaneous parameter sweeping",
        ),
        (
            "measureit_sweepqueue_template",
            "MeasureIt SweepQueue Template",
            "SweepQueue code examples for sequential measurement workflows",
        ),
        (
            "measureit_common_patterns",
            "MeasureIt Common Patterns",
            "Common MeasureIt patterns and best practices",
        ),
        (
            "measureit_code_examples",
            "MeasureIt Code Examples",
            "Complete collection of ALL MeasureIt patterns in structured format",
        ),
    ]

    for uri_suffix, name, description in measureit_resources:
        # Create a closure to capture the current values
        def make_measureit_resource(
            uri_suffix=uri_suffix, name=name, description=description
        ):
            uri = f"resource://{uri_suffix}"

            @mcp.resource(uri)
            async def measureit_resource() -> Resource:
                result = await proxy.read_resource(uri)
                if "error" in result:
                    error_content = json.dumps({"error": result["error"]}, indent=2)
                    return Resource(
                        uri=uri,
                        name=f"{name} (Error)",
                        description=f"Error retrieving {name}",
                        mimeType="application/json",
                        contents=[
                            TextResourceContents(
                                uri=uri,
                                mimeType="application/json",
                                text=error_content,
                            )
                        ],
                    )

                # Extract content from result
                contents_data = result.get("contents", [])
                if contents_data and isinstance(contents_data, list):
                    text_content = contents_data[0].get("text", "{}")
                else:
                    text_content = "{}"

                return Resource(
                    uri=uri,
                    name=name,
                    description=description,
                    mimeType="application/json",
                    contents=[
                        TextResourceContents(
                            uri=uri,
                            mimeType="application/json",
                            text=text_content,
                        )
                    ],
                )

            return measureit_resource

        make_measureit_resource()

    # Database resources (optional - only available if database option is enabled on server)
    @mcp.resource("resource://database_config")
    async def database_config() -> Resource:
        """Resource providing current QCodes database configuration."""
        result = await proxy.read_resource("resource://database_config")
        if "error" in result:
            error_content = json.dumps({"error": result["error"]}, indent=2)
            return Resource(
                uri="resource://database_config",
                name="Database Configuration (Error)",
                description="Error retrieving database configuration",
                mimeType="application/json",
                contents=[
                    TextResourceContents(
                        uri="resource://database_config",
                        mimeType="application/json",
                        text=error_content,
                    )
                ],
            )

        # Extract content from result
        contents_data = result.get("contents", [])
        if contents_data and isinstance(contents_data, list):
            text_content = contents_data[0].get("text", "{}")
        else:
            text_content = "{}"

        return Resource(
            uri="resource://database_config",
            name="Database Configuration",
            description="Current QCodes database configuration, path, and connection status",
            mimeType="application/json",
            contents=[
                TextResourceContents(
                    uri="resource://database_config",
                    mimeType="application/json",
                    text=text_content,
                )
            ],
        )

    @mcp.resource("resource://recent_measurements")
    async def recent_measurements() -> Resource:
        """Resource providing metadata for recent measurements."""
        result = await proxy.read_resource("resource://recent_measurements")
        if "error" in result:
            error_content = json.dumps({"error": result["error"]}, indent=2)
            return Resource(
                uri="resource://recent_measurements",
                name="Recent Measurements (Error)",
                description="Error retrieving recent measurements",
                mimeType="application/json",
                contents=[
                    TextResourceContents(
                        uri="resource://recent_measurements",
                        mimeType="application/json",
                        text=error_content,
                    )
                ],
            )

        # Extract content from result
        contents_data = result.get("contents", [])
        if contents_data and isinstance(contents_data, list):
            text_content = contents_data[0].get("text", "[]")
        else:
            text_content = "[]"

        return Resource(
            uri="resource://recent_measurements",
            name="Recent Measurements",
            description="Metadata for recent measurements across all experiments",
            mimeType="application/json",
            contents=[
                TextResourceContents(
                    uri="resource://recent_measurements",
                    mimeType="application/json",
                    text=text_content,
                )
            ],
        )

    return mcp
