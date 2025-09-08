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
    
    def __init__(self, ipython, host: str = "127.0.0.1", port: int = 8123, safe_mode: bool = True):
        self.ipython = ipython
        self.host = host
        self.port = port
        self.safe_mode = safe_mode
        self.running = False
        self.server_task: Optional[asyncio.Task] = None
        
        # Generate a random token for basic security
        self.token = secrets.token_urlsafe(32)
        
        # Initialize tools
        self.tools = QCodesReadOnlyTools(ipython)
        
        # Create FastMCP server
        server_name = f"Jupyter QCoDeS MCP Server ({'Safe' if safe_mode else 'Unsafe'} Mode)"
        self.mcp = FastMCP(server_name)
        self._register_tools()
        
        mode_status = "safe" if safe_mode else "unsafe"
        logger.info(f"Jupyter MCP Server initialized on {host}:{port} in {mode_status} mode")
    
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
        
        @self.mcp.tool()
        async def get_editing_cell(fresh_ms: int = 1000) -> List[TextContent]:
            """Get the currently editing cell content from JupyterLab frontend.
            
            This captures the cell that is currently being edited in the frontend.
            
            Args:
                fresh_ms: Maximum age in milliseconds. If provided and cached data is older,
                         will request fresh data from frontend (default: 1000, accept any age)
            """
            try:
                result = await self.tools.get_editing_cell(fresh_ms)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in get_editing_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def update_editing_cell(content: str) -> List[TextContent]:
            """Update the content of the currently editing cell in JupyterLab frontend.
            
            This tool allows you to programmatically set new Python code in the cell
            that is currently being edited in JupyterLab. The content will replace
            the entire current cell content.
            
            Args:
                content: New Python code content to set in the active cell
            """
            try:
                result = await self.tools.update_editing_cell(content)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in update_editing_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # Cell editing tools
        
        @self.mcp.tool()
        async def get_notebook_cells(num_cells: int = 2, include_output: bool = True) -> List[TextContent]:
            """Get recent notebook cells with input and output.
            
            Args:
                num_cells: Number of recent cells to retrieve (default: 2 for performance)
                include_output: Include cell outputs (default: True)
            """
            try:
                cells = []
                
                # Method 1: Use IPython's In/Out cache (fastest for recent cells)
                if hasattr(self.ipython, 'user_ns'):
                    In = self.ipython.user_ns.get('In', [])
                    Out = self.ipython.user_ns.get('Out', {})
                    
                    # Get the last num_cells entries
                    if len(In) > 1:  # In[0] is empty
                        start_idx = max(1, len(In) - num_cells)
                        for i in range(start_idx, len(In)):
                            if i < len(In) and In[i]:  # Skip empty entries
                                cell_info = {
                                    "cell_number": i,
                                    "execution_count": i,
                                    "input": In[i]
                                }
                                if include_output and i in Out:
                                    cell_info["output"] = str(Out[i])
                                    cell_info["has_output"] = True
                                else:
                                    cell_info["has_output"] = False
                                cells.append(cell_info)
                
                # Method 2: Fallback to history_manager if In/Out not available
                if not cells and hasattr(self.ipython, 'history_manager'):
                    try:
                        # Get range with output
                        current_count = getattr(self.ipython, 'execution_count', 1)
                        start_line = max(1, current_count - num_cells)
                        
                        history = list(self.ipython.history_manager.get_range(
                            session=0,  # Current session
                            start=start_line,
                            stop=current_count + 1,
                            raw=True,
                            output=include_output
                        ))
                        
                        for session, line_num, content in history:
                            if include_output and isinstance(content, tuple):
                                input_text, output_text = content
                                cells.append({
                                    "cell_number": line_num,
                                    "execution_count": line_num,
                                    "input": input_text,
                                    "output": str(output_text) if output_text else None,
                                    "has_output": output_text is not None
                                })
                            else:
                                cells.append({
                                    "cell_number": line_num,
                                    "execution_count": line_num,
                                    "input": content,
                                    "has_output": False
                                })
                    except Exception as he:
                        logger.debug(f"Could not get history: {he}")
                
                # Add metadata
                result = {
                    "cells": cells,
                    "total_cells": len(cells),
                    "requested_cells": num_cells,
                    "include_output": include_output,
                    "current_execution_count": getattr(self.ipython, 'execution_count', 0),
                    "kernel_info": {
                        "implementation": getattr(self.ipython.kernel, 'implementation', 'unknown') if hasattr(self.ipython, 'kernel') else 'unknown',
                        "language_info": getattr(self.ipython.kernel, 'language_info', {}) if hasattr(self.ipython, 'kernel') else {}
                    }
                }
                
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                
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
        
        # Unsafe mode tools
        if not self.safe_mode:
            @self.mcp.tool()
            async def execute_editing_cell() -> List[TextContent]:
                """Execute the currently editing cell in the JupyterLab frontend.
                
                UNSAFE: This tool executes code in the active notebook cell. Only available in unsafe mode.
                The code will run in the frontend with output appearing in the notebook.
                """
                try:
                    result = await self.tools.execute_editing_cell()
                    return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
                except Exception as e:
                    logger.error(f"Error in execute_editing_cell: {e}")
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # Parameter subscription tools
        
        # @self.mcp.tool()
        # async def subscribe_parameter(instrument: str, parameter: str, interval_s: float = 1.0) -> List[TextContent]:
        #     """Subscribe to periodic parameter updates.
        #     
        #     Args:
        #         instrument: Instrument name
        #         parameter: Parameter name
        #         interval_s: Polling interval in seconds
        #     """
        #     try:
        #         result = await self.tools.subscribe_parameter(instrument, parameter, interval_s)
        #         return [TextContent(type="text", text=json.dumps(result, indent=2))]
        #     except Exception as e:
        #         logger.error(f"Error in subscribe_parameter: {e}")
        #         return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # @self.mcp.tool()
        # async def unsubscribe_parameter(instrument: str, parameter: str) -> List[TextContent]:
        #     """Unsubscribe from parameter updates.
        #     
        #     Args:
        #         instrument: Instrument name
        #         parameter: Parameter name
        #     """
        #     try:
        #         result = await self.tools.unsubscribe_parameter(instrument, parameter)
        #         return [TextContent(type="text", text=json.dumps(result, indent=2))]
        #     except Exception as e:
        #         logger.error(f"Error in unsubscribe_parameter: {e}")
        #         return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # @self.mcp.tool()
        # async def list_subscriptions() -> List[TextContent]:
        #     """List current parameter subscriptions."""
        #     try:
        #         result = await self.tools.list_subscriptions()
        #         return [TextContent(type="text", text=json.dumps(result, indent=2))]
        #     except Exception as e:
        #         logger.error(f"Error in list_subscriptions: {e}")
        #         return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # System tools
        
        # @self.mcp.tool()
        # async def get_cache_stats() -> List[TextContent]:
        #     """Get parameter cache statistics."""
        #     try:
        #         stats = await self.tools.get_cache_stats()
        #         return [TextContent(type="text", text=json.dumps(stats, indent=2))]
        #     except Exception as e:
        #         logger.error(f"Error in get_cache_stats: {e}")
        #         return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        # @self.mcp.tool()
        # async def clear_cache() -> List[TextContent]:
        #     """Clear the parameter cache."""
        #     try:
        #         result = await self.tools.clear_cache()
        #         return [TextContent(type="text", text=json.dumps(result, indent=2))]
        #     except Exception as e:
        #         logger.error(f"Error in clear_cache: {e}")
        #         return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]
        
        @self.mcp.tool()
        async def server_status() -> List[TextContent]:
            """Get server status and configuration."""
            try:
                # Get list of registered tools from FastMCP
                registered_tools = []
                if hasattr(self.mcp, '_tools'):
                    registered_tools = list(self.mcp._tools.keys())
                elif hasattr(self.mcp, 'tools'):
                    registered_tools = list(self.mcp.tools.keys())
                
                status = {
                    "server_running": self.running,
                    "safe_mode": self.safe_mode,
                    "mode": "safe" if self.safe_mode else "unsafe",
                    "host": self.host,
                    "port": self.port,
                    "tools_count": len(registered_tools),
                    "registered_tools": registered_tools,
                    "ipython_info": {
                        "class": self.ipython.__class__.__name__,
                        "execution_count": getattr(self.ipython, 'execution_count', 0)
                    },
                    "rate_limit_interval": self.tools.min_interval_s,
                    "unsafe_tools_expected": ["execute_editing_cell"] if not self.safe_mode else [],
                    "unsafe_tools_registered": [tool for tool in registered_tools if "execute" in tool.lower()]
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
                port=self.port,
                show_banner=False
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
    
    def set_safe_mode(self, safe_mode: bool) -> Dict[str, Any]:
        """Change the server's safe mode setting.
        
        Note: This requires server restart to take effect for tool registration.
        
        Args:
            safe_mode: True for safe mode, False for unsafe mode
            
        Returns:
            Dictionary with status information
        """
        old_mode = self.safe_mode
        self.safe_mode = safe_mode
        
        mode_status = "safe" if safe_mode else "unsafe"
        old_mode_status = "safe" if old_mode else "unsafe"
        
        logger.info(f"MCP server mode changed from {old_mode_status} to {mode_status}")
        
        return {
            "old_mode": old_mode_status,
            "new_mode": mode_status,
            "server_running": self.running,
            "restart_required": True,
            "message": f"Server mode changed to {mode_status}. Restart required for tool changes to take effect."
        }