"""
Claude Desktop launcher for Jupyter QCoDeS MCP server.

This script provides STDIO transport compatibility for Claude Desktop while
still supporting the HTTP-based Jupyter integration. It can work in two modes:

1. Proxy Mode: If a Jupyter HTTP server is detected running on port 8123,
   this script acts as a proxy forwarding MCP requests via STDIO to HTTP.

2. Standalone Mode: If no Jupyter server is found, runs a standalone
   QCoDeS MCP server using STDIO transport directly.
"""

import asyncio
import sys
import os
import logging
import httpx
import json
from typing import Optional

# Configure logging for clean STDIO communication
# Only suppress INFO and DEBUG levels, keep WARNING, ERROR, CRITICAL for debugging
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.ERROR)  # Suppress FastMCP INFO messages
logging.getLogger("mcp").setLevel(logging.ERROR)     # Suppress MCP INFO messages  
logging.getLogger("httpx").setLevel(logging.WARNING) # Suppress HTTP request logs
logging.getLogger("asyncio").setLevel(logging.WARNING) # Suppress asyncio logs

# Add the parent directory to sys.path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastmcp import FastMCP
from mcp.types import TextContent
from tools import QCodesReadOnlyTools

logger = logging.getLogger(__name__)


class JupyterProxyTools:
    """Tools that proxy requests to the Jupyter HTTP MCP server."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8123"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.initialized = False
        self.working_endpoint = None
        self.session_id = None
    
    async def _find_working_endpoint(self):
        """Find which endpoint works for this MCP server."""
        if self.working_endpoint:
            return self.working_endpoint
            
        endpoints_to_try = [
            f"{self.base_url}/mcp",  # Streamable HTTP - prioritized
        ]
        
        test_request = {
            "jsonrpc": "2.0",
            "id": 0, 
            "method": "tools/list",
            "params": {}
        }
        
        for endpoint in endpoints_to_try:
            try:
                response = await self.client.post(
                    endpoint,
                    json=test_request,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                )
                
                if response.status_code == 200:
                    # Handle both SSE and JSON responses
                    response_text = response.text
                    if "data: " in response_text:
                        # SSE format
                        json_line = response_text.split("data: ")[1].strip()
                        json_response = json.loads(json_line)
                    else:
                        # Regular JSON
                        json_response = response.json()
                    
                    if "jsonrpc" in json_response and ("result" in json_response or "error" in json_response):
                        self.working_endpoint = endpoint
                        return endpoint
            except Exception:
                continue
                
        # Default to /mcp endpoint since we know that's what the server uses
        self.working_endpoint = f"{self.base_url}/mcp"
        return self.working_endpoint

    async def _ensure_session(self):
        """Ensure we have a valid session for Streamable HTTP."""
        if not self.session_id:
            endpoint = await self._find_working_endpoint()
            
            # Step 1: Initialize session with proper MCP initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Claude Desktop Proxy",
                        "version": "1.0.0"
                    }
                }
            }
            
            try:
                response = await self.client.post(
                    endpoint,
                    json=init_request,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"
                    }
                )
                
                if response.status_code == 200:
                    # Extract session ID from response headers (Streamable HTTP standard)
                    self.session_id = response.headers.get("mcp-session-id")
                    if not self.session_id:
                        # Fallback to default if no session ID provided
                        self.session_id = "default-session"
                    
                    # Step 2: Send initialized notification (required by MCP spec)
                    initialized_notification = {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                        "params": {}
                    }
                    
                    await self.client.post(
                        endpoint,
                        json=initialized_notification,
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream",
                            "mcp-session-id": self.session_id
                        }
                    )
                    
                else:
                    self.session_id = "default-session"
                    
            except Exception:
                self.session_id = "default-session"

    async def _proxy_request(self, tool_name: str, **kwargs) -> dict:
        """Proxy a tool request to the Jupyter HTTP MCP server using JSON-RPC."""
        try:
            # Ensure we have a session
            await self._ensure_session()
            endpoint = await self._find_working_endpoint()
            
            # Create proper MCP JSON-RPC request (session ID goes in headers, not body)
            json_rpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs if kwargs else {}
                }
            }
            
            # Prepare headers with session ID
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            
            # Add session ID to headers if we have one
            if self.session_id:
                headers["mcp-session-id"] = self.session_id
            
            response = await self.client.post(
                endpoint,
                json=json_rpc_request,
                headers=headers
            )
            response.raise_for_status()
            
            # Parse JSON-RPC response (might be SSE format)
            response_text = response.text
            if "data: " in response_text:
                # Handle SSE response format
                json_line = response_text.split("data: ")[1].strip()
                json_response = json.loads(json_line)
            else:
                # Handle regular JSON response
                json_response = response.json()
            
            if "error" in json_response:
                return {"error": f"MCP error: {json_response['error']}"}
            elif "result" in json_response:
                # Extract the actual tool result from MCP response
                result = json_response["result"]
                if isinstance(result, dict) and "content" in result:
                    # Return the content of the first text content item
                    content = result.get("content", [])
                    if content and len(content) > 0:
                        return content[0].get("text", "")
                return result
            else:
                return {"error": "Invalid JSON-RPC response"}
                
        except Exception as e:
            return {"error": f"Proxy request failed: {str(e)}"}


class StandaloneMCPServer:
    """Standalone MCP server using mock QCoDeS setup."""
    
    def __init__(self):
        # Try to initialize QCoDeS tools - will use mock data if no real instruments
        try:
            # Try to get IPython instance if available
            from IPython import get_ipython
            ipython = get_ipython()
            if ipython is not None:
                self.tools = QCodesReadOnlyTools(ipython)
            else:
                # Create a mock IPython-like object for standalone mode
                self.tools = self._create_standalone_tools()
        except (ImportError, Exception) as e:
            logger.warning(f"Could not access IPython, using standalone mode: {e}")
            self.tools = self._create_standalone_tools()
    
    def _create_standalone_tools(self):
        """Create standalone tools with mock data when no Jupyter is available."""
        class MockIPython:
            def __init__(self):
                self.user_ns = {
                    'mock_standalone': True,
                    'message': 'QCoDeS MCP Server running in standalone mode - connect to Jupyter for full functionality'
                }
                self.execution_count = 0
        
        return QCodesReadOnlyTools(MockIPython())


async def check_jupyter_server(host: str = "127.0.0.1", port: int = 8123) -> bool:
    """Check if Jupyter MCP server is running using proper Streamable HTTP session management."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            endpoint = f"http://{host}:{port}/mcp"  # Use known working endpoint
            
            # Step 1: Initialize to get session ID
            init_request = {
                "jsonrpc": "2.0",
                "id": "test-init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "Proxy Test",
                        "version": "1.0.0"
                    }
                }
            }
            
            init_response = await client.post(
                endpoint,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            if init_response.status_code != 200:
                return False
            
            # Step 2: Extract session ID from headers
            session_id = init_response.headers.get("mcp-session-id")
            if not session_id:
                return False
            
            # Step 2.5: Send initialized notification (required by MCP spec)
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            await client.post(
                endpoint,
                json=initialized_notification,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id
                }
            )
            
            # Step 3: Test with a simple tools/list request using the session
            test_request = {
                "jsonrpc": "2.0",
                "id": "test-tools",
                "method": "tools/list",
                "params": {}
            }
            
            test_response = await client.post(
                endpoint,
                json=test_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id
                }
            )
            
            if test_response.status_code == 200:
                # Parse response (might be SSE format)
                response_text = test_response.text
                if "data: " in response_text:
                    json_line = response_text.split("data: ")[1].strip()
                    json_response = json.loads(json_line)
                else:
                    json_response = test_response.json()
                
                # Check if it's a valid JSON-RPC response
                return "jsonrpc" in json_response and ("result" in json_response or "error" in json_response)
                
            return False
            
    except Exception:
        return False


def create_proxy_server(jupyter_url: str) -> FastMCP:
    """Create a proxy MCP server that forwards to Jupyter HTTP server."""
    mcp = FastMCP("Jupyter QCoDeS Proxy")
    proxy_tools = JupyterProxyTools(jupyter_url)
    
    @mcp.tool()
    async def list_instruments() -> list[TextContent]:
        """List all QCoDeS instruments in the Jupyter namespace."""
        result = await proxy_tools._proxy_request("list_instruments")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def instrument_info(name: str, with_values: bool = False) -> list[TextContent]:
        """Get detailed information about an instrument."""
        result = await proxy_tools._proxy_request("instrument_info", name=name, with_values=with_values)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def get_parameter_value(instrument: str, parameter: str, fresh: bool = False) -> list[TextContent]:
        """Get a parameter value with caching and rate limiting."""
        result = await proxy_tools._proxy_request("get_parameter_value", 
                                                 instrument=instrument, parameter=parameter, fresh=fresh)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def station_snapshot() -> list[TextContent]:
        """Get full QCoDeS station snapshot without parameter values."""
        result = await proxy_tools._proxy_request("station_snapshot")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def list_variables(type_filter: Optional[str] = None) -> list[TextContent]:
        """List variables in the Jupyter namespace."""
        result = await proxy_tools._proxy_request("list_variables", type_filter=type_filter)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def get_parameter_values(queries: str) -> list[TextContent]:
        """Get multiple parameter values in batch."""
        result = await proxy_tools._proxy_request("get_parameter_values", queries=queries)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def get_variable_info(name: str) -> list[TextContent]:
        """Get detailed information about a variable."""
        result = await proxy_tools._proxy_request("get_variable_info", name=name)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def get_notebook_cells() -> list[TextContent]:
        """Get information about notebook cells."""
        result = await proxy_tools._proxy_request("get_notebook_cells")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def suggest_code(description: str, context: str = "") -> list[TextContent]:
        """Suggest code based on available instruments and context."""
        result = await proxy_tools._proxy_request("suggest_code", description=description, context=context)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def subscribe_parameter(instrument: str, parameter: str, interval_s: float = 1.0) -> list[TextContent]:
        """Subscribe to periodic parameter updates."""
        result = await proxy_tools._proxy_request("subscribe_parameter", instrument=instrument, parameter=parameter, interval_s=interval_s)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def unsubscribe_parameter(instrument: str, parameter: str) -> list[TextContent]:
        """Unsubscribe from parameter updates."""
        result = await proxy_tools._proxy_request("unsubscribe_parameter", instrument=instrument, parameter=parameter)
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def list_subscriptions() -> list[TextContent]:
        """List current parameter subscriptions."""
        result = await proxy_tools._proxy_request("list_subscriptions")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def get_cache_stats() -> list[TextContent]:
        """Get parameter cache statistics."""
        result = await proxy_tools._proxy_request("get_cache_stats")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def clear_cache() -> list[TextContent]:
        """Clear the parameter cache."""
        result = await proxy_tools._proxy_request("clear_cache")
        return [TextContent(type="text", text=str(result))]
    
    @mcp.tool()
    async def server_status() -> list[TextContent]:
        """Get server status - shows this is proxy mode."""
        result = await proxy_tools._proxy_request("server_status")
        proxy_info = {
            "mode": "proxy",
            "proxy_target": jupyter_url,
            "jupyter_server_status": result
        }
        return [TextContent(type="text", text=str(proxy_info))]
    
    return mcp


def create_standalone_server() -> FastMCP:
    """Create a standalone MCP server for when Jupyter is not available."""
    mcp = FastMCP("QCoDeS Standalone MCP Server")
    server = StandaloneMCPServer()
    
    @mcp.tool()
    async def list_instruments() -> list[TextContent]:
        """List all QCoDeS instruments in standalone mode."""
        try:
            result = await server.tools.list_instruments()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def instrument_info(name: str, with_values: bool = False) -> list[TextContent]:
        """Get detailed information about an instrument."""
        try:
            result = await server.tools.instrument_info(name, with_values)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def get_parameter_value(instrument: str, parameter: str, fresh: bool = False) -> list[TextContent]:
        """Get a parameter value with caching and rate limiting."""
        try:
            result = await server.tools.get_parameter_value(instrument, parameter, fresh)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def get_parameter_values(queries: str) -> list[TextContent]:
        """Get multiple parameter values in batch."""
        try:
            import json
            queries_list = json.loads(queries)
            result = await server.tools.get_parameter_values(queries_list)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def station_snapshot() -> list[TextContent]:
        """Get full QCoDeS station snapshot."""
        try:
            result = await server.tools.station_snapshot()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def list_variables(type_filter: Optional[str] = None) -> list[TextContent]:
        """List variables in the namespace."""
        try:
            result = await server.tools.list_variables(type_filter)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def get_variable_info(name: str) -> list[TextContent]:
        """Get detailed information about a variable."""
        try:
            result = await server.tools.get_variable_info(name)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def get_notebook_cells() -> list[TextContent]:
        """Get information about notebook cells - limited in standalone."""
        return [TextContent(type="text", text=str({
            "mode": "standalone",
            "message": "Notebook cells not available in standalone mode",
            "suggestion": "Use Jupyter mode for full notebook integration"
        }))]
    
    @mcp.tool()
    async def suggest_code(description: str, context: str = "") -> list[TextContent]:
        """Suggest code based on available instruments and context."""
        try:
            # Get current instruments and variables for context
            instruments = await server.tools.list_instruments()
            variables = await server.tools.list_variables()
            
            suggestion = {
                "description": description,
                "context": context,
                "available_instruments": instruments,
                "available_variables": variables[:5],  # Limit for brevity
                "suggested_code": f"# Code suggestion for: {description}\n# Available instruments: {[i.get('name', 'unknown') for i in instruments]}\n# Add your implementation here",
                "mode": "standalone",
                "note": "Basic code suggestion. Use Jupyter mode for enhanced AI suggestions."
            }
            return [TextContent(type="text", text=str(suggestion))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def subscribe_parameter(instrument: str, parameter: str, interval_s: float = 1.0) -> list[TextContent]:
        """Subscribe to periodic parameter updates."""
        try:
            result = await server.tools.subscribe_parameter(instrument, parameter, interval_s)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def unsubscribe_parameter(instrument: str, parameter: str) -> list[TextContent]:
        """Unsubscribe from parameter updates."""
        try:
            result = await server.tools.unsubscribe_parameter(instrument, parameter)
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def list_subscriptions() -> list[TextContent]:
        """List current parameter subscriptions."""
        try:
            result = await server.tools.list_subscriptions()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def get_cache_stats() -> list[TextContent]:
        """Get parameter cache statistics."""
        try:
            result = await server.tools.get_cache_stats()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def clear_cache() -> list[TextContent]:
        """Clear the parameter cache."""
        try:
            result = await server.tools.clear_cache()
            return [TextContent(type="text", text=str(result))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    
    @mcp.tool()
    async def server_status() -> list[TextContent]:
        """Get server status - shows this is standalone mode."""
        return [TextContent(type="text", text=str({
            "mode": "standalone",
            "message": "Running without Jupyter - full tool functionality with mock data",
            "tools_available": 15,
            "suggestion": "Start Jupyter with %load_ext servers.jupyter_qcodes.jupyter_mcp_extension for live instrument data"
        }))]
    
    return mcp


def main():
    """Main launcher that chooses between proxy and standalone mode."""
    
    async def check_and_setup():
        # Check if Jupyter server is running
        jupyter_running = await check_jupyter_server()
        
        if jupyter_running:
            return create_proxy_server("http://127.0.0.1:8123")
        else:
            return create_standalone_server()
    
    # Check if we're in an event loop already
    try:
        loop = asyncio.get_running_loop()
        # We're in a loop, use run_until_complete
        mcp = loop.run_until_complete(check_and_setup())
    except RuntimeError:
        # No loop running, create new one
        mcp = asyncio.run(check_and_setup())
    
    # Run with STDIO transport for Claude Desktop compatibility
    # Suppress banner for clean STDIO communication
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Silently exit on Ctrl+C for clean STDIO
        sys.exit(0)
    except Exception as e:
        # Only log errors to stderr in debug mode
        if os.getenv("DEBUG"):
            print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)