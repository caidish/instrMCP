"""
FastMCP server implementation for Jupyter QCoDeS integration.

This server provides read-only access to QCoDeS instruments and
Jupyter notebook functionality through MCP tools.
"""

import asyncio
import json
import logging
import secrets
from typing import List, Dict, Any, Optional

from fastmcp import FastMCP
from mcp.types import TextContent

from .tools import QCodesReadOnlyTools

logger = logging.getLogger(__name__)


class JupyterMCPServer:
    """MCP server for Jupyter QCoDeS integration."""
    
    def __init__(self, ipython, host: str = "127.0.0.1", port: int = 8123):
        self.ipython = ipython
        self.host = host
        self.port = port
        self.running = False
        self.server_task: Optional[asyncio.Task] = None
        
        # Generate a random token for basic security
        self.token = secrets.token_urlsafe(32)
        
        # Initialize tools
        self.tools = QCodesReadOnlyTools(ipython)
        
        # Create FastMCP server
        self.mcp = FastMCP("Jupyter QCoDeS MCP Server")
        self._register_tools()
        
        logger.info(f"Jupyter MCP Server initialized on {host}:{port}")
    
    def _register_tools(self):
        """Register all MCP tools."""
        
        # QCoDeS instrument tools
        
        @self.mcp.tool()
        async def list_instruments() -> List[TextContent]:
            """List all QCoDeS instruments in the Jupyter namespace."""
            try:
                instruments = await self.tools.list_instruments()
                return [TextContent(type="text", text=json.dumps(instruments, indent=2))]
            except Exception as e:
                logger.error(f"Error in list_instruments: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def instrument_info(name: str, with_values: bool = False) -> List[TextContent]:
            """Get detailed information about an instrument.
            
            Args:
                name: Instrument name
                with_values: Include cached parameter values
            """
            try:
                info = await self.tools.instrument_info(name, with_values)
                return [TextContent(type="text", text=json.dumps(info, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in instrument_info: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def get_parameter_value(instrument: str, parameter: str, fresh: bool = False) -> List[TextContent]:
            """Get a parameter value with caching and rate limiting.
            
            Args:
                instrument: Instrument name
                parameter: Parameter name or hierarchical path (e.g., "voltage", "ch01.voltage", "submodule.param")
                fresh: Force fresh read from hardware (rate limited)
            """
            try:
                result = await self.tools.get_parameter_value(instrument, parameter, fresh)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in get_parameter_value: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def get_parameter_values(queries: str) -> List[TextContent]:
            """Get multiple parameter values in batch.
            
            Args:
                queries: JSON string containing list of queries
                         Format: [{"instrument": "name", "parameter": "param", "fresh": false}, ...]
            """
            try:
                queries_list = json.loads(queries)
                results = await self.tools.get_parameter_values(queries_list)
                return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in get_parameter_values: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def station_snapshot() -> List[TextContent]:
            """Get full QCoDeS station snapshot without parameter values."""
            try:
                snapshot = await self.tools.station_snapshot()
                return [TextContent(type="text", text=json.dumps(snapshot, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in station_snapshot: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # Namespace and variable tools
        
        @self.mcp.tool()
        async def list_variables(type_filter: str = None) -> List[TextContent]:
            """List variables in the Jupyter namespace.
            
            Args:
                type_filter: Optional type filter (e.g., "array", "dict", "instrument")
            """
            try:
                variables = await self.tools.list_variables(type_filter)
                return [TextContent(type="text", text=json.dumps(variables, indent=2))]
            except Exception as e:
                logger.error(f"Error in list_variables: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def get_variable_info(name: str) -> List[TextContent]:
            """Get detailed information about a variable.
            
            Args:
                name: Variable name
            """
            try:
                info = await self.tools.get_variable_info(name)
                return [TextContent(type="text", text=json.dumps(info, indent=2))]
            except Exception as e:
                logger.error(f"Error in get_variable_info: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # Cell editing tools
        
        @self.mcp.tool()
        async def get_notebook_cells() -> List[TextContent]:
            """Get information about notebook cells."""
            try:
                # Try to get cell information from IPython
                cells_info = []
                
                # Get execution count and history
                if hasattr(self.ipython, 'execution_count'):
                    cells_info.append({
                        "type": "execution_info",
                        "execution_count": self.ipython.execution_count,
                        "kernel_info": {
                            "implementation": getattr(self.ipython, 'kernel', {}).get('implementation', 'unknown'),
                            "language_info": getattr(self.ipython, 'kernel', {}).get('language_info', {})
                        }
                    })
                
                # Try to get history
                try:
                    history = list(self.ipython.history_manager.get_range(output=False))[-10:]  # Last 10 commands
                    cells_info.append({
                        "type": "recent_history",
                        "history": [{"session": s, "line": l, "code": c} for s, l, c in history]
                    })
                except Exception as he:
                    logger.debug(f"Could not get history: {he}")
                
                return [TextContent(type="text", text=json.dumps({
                    "cells_info": cells_info,
                    "note": "Direct cell access requires additional Jupyter integration"
                }, indent=2))]
                
            except Exception as e:
                logger.error(f"Error in get_notebook_cells: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def suggest_code(description: str, context: str = "") -> List[TextContent]:
            """Suggest code based on available instruments and context.
            
            Args:
                description: Description of what you want to do
                context: Additional context (e.g., current variables, measurement type)
            """
            try:
                # Get current instruments for context
                instruments = await self.tools.list_instruments()
                variables = await self.tools.list_variables()
                
                suggestion = {
                    "description": description,
                    "context": context,
                    "available_instruments": instruments,
                    "available_variables": variables[:10],  # Limit for brevity
                    "suggested_code": f"# Code suggestion for: {description}\\n# Available instruments: {[i['name'] for i in instruments]}\\n# Add your implementation here",
                    "note": "This is a basic code suggestion. Implement your logic based on available instruments and variables."
                }
                
                return [TextContent(type="text", text=json.dumps(suggestion, indent=2))]
                
            except Exception as e:
                logger.error(f"Error in suggest_code: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # Parameter subscription tools
        
        @self.mcp.tool()
        async def subscribe_parameter(instrument: str, parameter: str, interval_s: float = 1.0) -> List[TextContent]:
            """Subscribe to periodic parameter updates.
            
            Args:
                instrument: Instrument name
                parameter: Parameter name
                interval_s: Polling interval in seconds
            """
            try:
                result = await self.tools.subscribe_parameter(instrument, parameter, interval_s)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in subscribe_parameter: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def unsubscribe_parameter(instrument: str, parameter: str) -> List[TextContent]:
            """Unsubscribe from parameter updates.
            
            Args:
                instrument: Instrument name
                parameter: Parameter name
            """
            try:
                result = await self.tools.unsubscribe_parameter(instrument, parameter)
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in unsubscribe_parameter: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def list_subscriptions() -> List[TextContent]:
            """List current parameter subscriptions."""
            try:
                result = await self.tools.list_subscriptions()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in list_subscriptions: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # System tools
        
        @self.mcp.tool()
        async def get_cache_stats() -> List[TextContent]:
            """Get parameter cache statistics."""
            try:
                stats = await self.tools.get_cache_stats()
                return [TextContent(type="text", text=json.dumps(stats, indent=2))]
            except Exception as e:
                logger.error(f"Error in get_cache_stats: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def clear_cache() -> List[TextContent]:
            """Clear the parameter cache."""
            try:
                result = await self.tools.clear_cache()
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in clear_cache: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def server_status() -> List[TextContent]:
            """Get server status and configuration."""
            try:
                status = {
                    "server_running": self.running,
                    "host": self.host,
                    "port": self.port,
                    "tools_count": len([name for name in dir(self.mcp) if not name.startswith('_')]),
                    "ipython_info": {
                        "class": self.ipython.__class__.__name__,
                        "execution_count": getattr(self.ipython, 'execution_count', 0)
                    },
                    "rate_limit_interval": self.tools.min_interval_s
                }
                return [TextContent(type="text", text=json.dumps(status, indent=2))]
            except Exception as e:
                logger.error(f"Error in server_status: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
    
    async def start(self):
        """Start the MCP server."""
        if self.running:
            return
        
        try:
            logger.info(f"Starting Jupyter MCP server on {self.host}:{self.port}")
            
            # Start the server in a separate task
            self.server_task = asyncio.create_task(self._run_server())
            self.running = True
            
            print(f"🚀 QCoDeS MCP Server running on http://{self.host}:{self.port}")
            print(f"🔑 Access token: {self.token}")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def _run_server(self):
        """Run the FastMCP server."""
        try:
            # Use FastMCP's run method - it handles the asyncio loop
            await asyncio.to_thread(
                self.mcp.run,
                transport="http",
                host=self.host,
                port=self.port
            )
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server."""
        if not self.running:
            return
        
        try:
            self.running = False
            
            # Clean up tools
            await self.tools.cleanup()
            
            # Cancel server task
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Jupyter MCP server stopped")
            print("🛑 QCoDeS MCP Server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")