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

    # QCodes meta-tool (consolidates 2 tools into 1)
    @mcp.tool(name="qcodes")
    async def qcodes(
        action: str,
        name: Optional[str] = None,
        with_values: bool = False,
        queries: Optional[str] = None,
    ) -> list[TextContent]:
        """Unified QCodes tool for instrument and parameter operations.

        STRICT PARAMETER REQUIREMENTS BY ACTION:

        ═══ INSTRUMENT OPERATIONS ═══

        action="instrument_info"
            → REQUIRES: name
            → Optional: with_values (include cached parameter values)
            → Use name="*" to list all available instruments
            Examples:
              qcodes(action="instrument_info", name="*")
              qcodes(action="instrument_info", name="lockin")
              qcodes(action="instrument_info", name="dac", with_values=True)

        action="get_values"
            → REQUIRES: queries (JSON string)
            → Single query: {"instrument": "name", "parameter": "param", "fresh": false}
            → Batch query: [{"instrument": "name1", "parameter": "param1"}, ...]
            → Hierarchical params: "ch01.voltage", "X", "dac.ch01.voltage"
            Examples:
              qcodes(action="get_values", queries='{"instrument": "lockin", "parameter": "X"}')
              qcodes(action="get_values", queries='{"instrument": "dac", "parameter": "ch01.voltage", "fresh": true}')
              qcodes(action="get_values", queries='[{"instrument": "lockin", "parameter": "X"}, {"instrument": "lockin", "parameter": "Y"}]')

        Returns:
            JSON with instrument info, parameter values, or error details.
        """
        result = await proxy.call(
            "qcodes",
            action=action,
            name=name,
            with_values=with_values,
            queries=queries,
        )
        return [TextContent(type="text", text=str(result))]

    # Notebook meta-tool (consolidates 13 tools into 1)
    @mcp.tool(name="notebook")
    async def notebook(
        action: str,
        name: Optional[str] = None,
        type_filter: Optional[str] = None,
        fresh_ms: int = 1000,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        max_lines: int = 200,
        num_cells: int = 2,
        include_output: bool = True,
        target: Optional[str] = None,
        content: Optional[str] = None,
        cell_type: str = "code",
        position: str = "below",
        cell_numbers: Optional[str] = None,
        old_text: Optional[str] = None,
        new_text: Optional[str] = None,
    ) -> list[TextContent]:
        """Unified notebook tool for all Jupyter notebook operations.

        STRICT PARAMETER REQUIREMENTS BY ACTION:

        ═══ READ OPERATIONS (always available) ═══

        action="list_variables"
            → No required params.
            → Optional: type_filter (e.g., "array", "DataFrame", "int", "float", "str", "dict", "list")
            Examples:
              notebook(action="list_variables")
              notebook(action="list_variables", type_filter="array")
              notebook(action="list_variables", type_filter="DataFrame")

        action="get_variable_info"
            → REQUIRES: name
            Example: notebook(action="get_variable_info", name="my_var")

        action="get_editing_cell"
            → No required params.
            → Optional: fresh_ms (cache timeout), line_start, line_end, max_lines
            Examples:
              notebook(action="get_editing_cell")
              notebook(action="get_editing_cell", line_start=1, line_end=50)

        action="get_editing_cell_output"
            → No required params. Returns output of last executed cell.

        action="get_notebook_cells"
            → No required params.
            → Optional: num_cells (default 2), include_output (default True)
            Example: notebook(action="get_notebook_cells", num_cells=5)

        action="move_cursor"
            → REQUIRES: target (one of: "above", "below", "bottom", or cell number as string)
            Examples:
              notebook(action="move_cursor", target="below")
              notebook(action="move_cursor", target="3")

        action="server_status"
            → No required params. Returns server mode (safe/unsafe/dangerous).

        ═══ WRITE OPERATIONS (unsafe mode only) ═══
        Note: These actions require user consent via dialog (except add_cell).

        action="update_editing_cell" [consent required]
            → REQUIRES: content
            Example: notebook(action="update_editing_cell", content="x = 42\\nprint(x)")

        action="execute_cell" [consent required]
            → No required params. Executes the currently active cell.

        action="add_cell" [NO consent required]
            → No required params.
            → Optional: cell_type ("code"/"markdown"), position ("above"/"below"), content
            Example: notebook(action="add_cell", cell_type="markdown", position="above", content="# Header")

        action="delete_cell" [consent required]
            → No required params. Deletes the currently active cell.

        action="delete_cells" [consent required]
            → REQUIRES: cell_numbers (JSON array string)
            Example: notebook(action="delete_cells", cell_numbers="[1, 2, 5]")

        action="apply_patch" [consent required]
            → REQUIRES: old_text AND new_text
            Example: notebook(action="apply_patch", old_text="x = 10", new_text="x = 20")

        Returns:
            JSON with operation result or error details.
        """
        result = await proxy.call(
            "notebook",
            action=action,
            name=name,
            type_filter=type_filter,
            fresh_ms=fresh_ms,
            line_start=line_start,
            line_end=line_end,
            max_lines=max_lines,
            num_cells=num_cells,
            include_output=include_output,
            target=target,
            content=content,
            cell_type=cell_type,
            position=position,
            cell_numbers=cell_numbers,
            old_text=old_text,
            new_text=new_text,
        )
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(name="mcp_list_resources")
    async def list_resources() -> list[TextContent]:
        """
        List all available MCP resources and guide on when to use them.

        MCP Resources provide READ-ONLY reference data and templates,
        while Tools perform active operations. Use this tool to discover
        what context and documentation is available.
        """
        result = await proxy.call("mcp_list_resources")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(name="mcp_get_resource")
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

    # MeasureIt integration tools (optional - only if measureit option enabled)
    @mcp.tool(name="measureit_get_status")
    async def get_measureit_status() -> list[TextContent]:
        """Check if any MeasureIt sweep is currently running."""
        result = await proxy.call("measureit_get_status")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(name="measureit_wait_for_all_sweeps")
    async def wait_for_all_sweeps() -> list[TextContent]:
        """Wait until all currently running MeasureIt sweeps finish."""
        result = await proxy.call("measureit_wait_for_all_sweeps")
        return [TextContent(type="text", text=str(result))]

    @mcp.tool(name="measureit_wait_for_sweep")
    async def wait_for_sweep(variable_name: str) -> list[TextContent]:
        """Wait until the specified MeasureIt sweep finishes."""
        result = await proxy.call(
            "measureit_wait_for_sweep", variable_name=variable_name
        )
        return [TextContent(type="text", text=str(result))]

    # Database meta-tool (consolidates 4 tools into 1)
    @mcp.tool(name="database")
    async def database(
        action: str,
        id: Optional[int] = None,
        database_path: Optional[str] = None,
    ) -> list[TextContent]:
        """Unified database tool for QCodes database operations.

        STRICT PARAMETER REQUIREMENTS BY ACTION:

        ═══ DATABASE OPERATIONS ═══

        action="list_experiments"
            → No required params.
            → Optional: database_path (uses MeasureIt/QCodes default if not specified)
            Examples:
              database(action="list_experiments")
              database(action="list_experiments", database_path="/path/to/experiments.db")

        action="get_dataset"
            → REQUIRES: id (dataset run ID, e.g., 1, 2, 5)
            → Optional: database_path
            Examples:
              database(action="get_dataset", id=1)
              database(action="get_dataset", id=5, database_path="/path/to/experiments.db")

        action="stats"
            → No required params. Returns database statistics.
            → Optional: database_path
            Examples:
              database(action="stats")
              database(action="stats", database_path="/path/to/experiments.db")

        action="list_available"
            → No required params.
            → Searches MeasureIt databases directory and QCodes config paths.
            Example:
              database(action="list_available")

        Database Path Resolution (when database_path=None):
            1. MeasureIt default: $MeasureItHome/Databases/Example_database.db
            2. QCodes config: qc.config.core.db_location
            3. Error with suggestions if neither exists

        Returns:
            JSON with database/experiment/dataset info or error details.
        """
        result = await proxy.call(
            "database",
            action=action,
            id=id,
            database_path=database_path,
        )
        return [TextContent(type="text", text=str(result))]

    # Dynamic meta-tool (consolidates 6 tools into 1, only in unsafe mode)
    @mcp.tool(name="dynamic")
    async def dynamic(
        action: str,
        # Register/update params
        name: Optional[str] = None,
        source_code: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        author: Optional[str] = None,
        capabilities: Optional[str] = None,
        parameters: Optional[str] = None,
        returns: Optional[str] = None,
        examples: Optional[str] = None,
        tags: Optional[str] = None,
        # List filter params
        tag: Optional[str] = None,
        capability: Optional[str] = None,
        # Revoke param
        reason: Optional[str] = None,
    ) -> list[TextContent]:
        """Unified dynamic tool for runtime tool management.

        Create, update, inspect, and manage dynamically registered tools at runtime.
        Tools persist across server restarts in ~/.instrmcp/registry/.

        STRICT PARAMETER REQUIREMENTS BY ACTION:

        ═══ READ OPERATIONS ═══

        action="list"
            → No required params.
            → Optional: tag, capability, author (filter results)
            Examples:
              dynamic(action="list")
              dynamic(action="list", author="me")
              dynamic(action="list", capability="cap:numpy")
              dynamic(action="list", tag="analysis")

        action="inspect"
            → REQUIRES: name
            → Returns full tool specification including source code
            Example:
              dynamic(action="inspect", name="my_tool")

        action="stats"
            → No required params.
            → Returns registry statistics (total tools, by author, by capability)
            Example:
              dynamic(action="stats")

        ═══ WRITE OPERATIONS (unsafe mode only) ═══

        action="register" [consent required]
            → REQUIRES: name, source_code
            → Optional: version (default "1.0.0"), description, author (default "unknown"),
              capabilities (JSON array), parameters (JSON array), returns (JSON object),
              examples (JSON array), tags (JSON array)
            → User sees consent dialog with full source code before approval
            Examples:
              dynamic(action="register", name="add_nums", source_code="def add_nums(a, b): return a + b")
              dynamic(action="register", name="analyze", source_code="def analyze(data): return sum(data)",
                      capabilities='["cap:python.builtin"]',
                      parameters='[{"name": "data", "type": "array", "required": true}]')

        action="update" [consent required]
            → REQUIRES: name, version (new version, must differ from current)
            → Optional: source_code, description, capabilities, parameters, returns, examples, tags
            → Only provided fields are updated; others keep existing values
            → User sees consent dialog before approval
            Example:
              dynamic(action="update", name="add_nums", version="1.1.0",
                      source_code="def add_nums(a, b, c=0): return a + b + c")

        action="revoke"
            → REQUIRES: name
            → Optional: reason (for audit trail)
            → Permanently removes tool from registry (cannot be undone)
            → NO consent required (destructive but explicit)
            Examples:
              dynamic(action="revoke", name="my_tool")
              dynamic(action="revoke", name="old_tool", reason="Replaced by new_tool")

        JSON Parameter Formats:
            capabilities: '["cap:numpy", "cap:custom.analysis"]'
            parameters: '[{"name": "x", "type": "number", "description": "Input", "required": true}]'
            returns: '{"type": "number", "description": "Result"}'
            examples: '["example usage 1", "example usage 2"]'
            tags: '["analysis", "math"]'

        Returns:
            JSON with operation result or error details including valid_actions hint.
        """
        result = await proxy.call(
            "dynamic",
            action=action,
            name=name,
            source_code=source_code,
            version=version,
            description=description,
            author=author,
            capabilities=capabilities,
            parameters=parameters,
            returns=returns,
            examples=examples,
            tags=tags,
            tag=tag,
            capability=capability,
            reason=reason,
        )
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
