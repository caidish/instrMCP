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
from mcp.types import TextContent, Resource, TextResourceContents

from .tools import QCodesReadOnlyTools

# MeasureIt integration (optional)
try:
    from ...extensions.MeasureIt import (
        get_sweep0d_template,
        get_sweep1d_template,
        get_sweep2d_template,
        get_simulsweep_template,
        get_sweepqueue_template,
        get_common_patterns_template,
        get_measureit_code_examples
    )
    MEASUREIT_AVAILABLE = True
except ImportError:
    MEASUREIT_AVAILABLE = False

# Database integration (optional)
try:
    from ...extensions import database as db_integration
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class JupyterMCPServer:
    """MCP server for Jupyter QCoDeS integration."""
    
    def __init__(self, ipython, host: str = "127.0.0.1", port: int = 8123, safe_mode: bool = True, enabled_options: set = None):
        self.ipython = ipython
        self.host = host
        self.port = port
        self.safe_mode = safe_mode
        self.enabled_options = enabled_options or set()
        self.running = False
        self.server_task: Optional[asyncio.Task] = None
        
        # Generate a random token for basic security
        self.token = secrets.token_urlsafe(32)
        
        # Initialize tools
        self.tools = QCodesReadOnlyTools(ipython)
        
        # Create FastMCP server
        server_name = f"Jupyter QCoDeS MCP Server ({'Safe' if safe_mode else 'Unsafe'} Mode)"
        self.mcp = FastMCP(server_name)
        self._register_resources()
        self._register_tools()
        
        mode_status = "safe" if safe_mode else "unsafe"
        logger.info(f"Jupyter MCP Server initialized on {host}:{port} in {mode_status} mode")

    def _register_resources(self):
        """Register MCP resources."""

        @self.mcp.resource("resource://available_instruments")
        async def available_instruments() -> Resource:
            """Resource providing list of available QCodes instruments."""
            try:
                # Get list of instruments
                instruments = await self.tools.list_instruments()

                # Convert to JSON string
                content = json.dumps(instruments, indent=2, default=str)

                return Resource(
                    uri="resource://available_instruments",
                    name="Available Instruments",
                    description="List of QCodes instruments available in the namespace with hierarchical parameter structure",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://available_instruments",
                        mimeType="application/json",
                        text=content
                    )]
                )

            except Exception as e:
                logger.error(f"Error generating available_instruments resource: {e}")
                error_content = json.dumps({
                    "error": str(e),
                    "status": "error"
                }, indent=2)

                return Resource(
                    uri="resource://available_instruments",
                    name="Available Instruments (Error)",
                    description="Error retrieving available instruments",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://available_instruments",
                        mimeType="application/json",
                        text=error_content
                    )]
                )

        @self.mcp.resource("resource://station_state")
        async def station_state() -> Resource:
            """Resource providing current QCodes station snapshot."""
            try:
                # Get station snapshot
                snapshot = await self.tools.station_snapshot()

                # Convert to JSON string
                content = json.dumps(snapshot, indent=2, default=str)

                return Resource(
                    uri="resource://station_state",
                    name="Station State",
                    description="Current QCodes station snapshot without parameter values",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://station_state",
                        mimeType="application/json",
                        text=content
                    )]
                )

            except Exception as e:
                logger.error(f"Error generating station_state resource: {e}")
                error_content = json.dumps({
                    "error": str(e),
                    "status": "error"
                }, indent=2)

                return Resource(
                    uri="resource://station_state",
                    name="Station State (Error)",
                    description="Error retrieving station state",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://station_state",
                        mimeType="application/json",
                        text=error_content
                    )]
                )

        # MeasureIt template resources (optional - only if measureit option enabled)
        if MEASUREIT_AVAILABLE and 'measureit' in self.enabled_options:

            @self.mcp.resource("resource://measureit_sweep0d_template")
            async def measureit_sweep0d_template() -> Resource:
                """Resource providing Sweep0D code templates and examples."""
                content = get_sweep0d_template()
                return Resource(
                    uri="resource://measureit_sweep0d_template",
                    name="MeasureIt Sweep0D Template",
                    description="Sweep0D code examples and patterns for time-based monitoring",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_sweep0d_template",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_sweep1d_template")
            async def measureit_sweep1d_template() -> Resource:
                """Resource providing Sweep1D code templates and examples."""
                content = get_sweep1d_template()
                return Resource(
                    uri="resource://measureit_sweep1d_template",
                    name="MeasureIt Sweep1D Template",
                    description="Sweep1D code examples and patterns for single parameter sweeps",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_sweep1d_template",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_sweep2d_template")
            async def measureit_sweep2d_template() -> Resource:
                """Resource providing Sweep2D code templates and examples."""
                content = get_sweep2d_template()
                return Resource(
                    uri="resource://measureit_sweep2d_template",
                    name="MeasureIt Sweep2D Template",
                    description="Sweep2D code examples and patterns for 2D parameter mapping",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_sweep2d_template",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_simulsweep_template")
            async def measureit_simulsweep_template() -> Resource:
                """Resource providing SimulSweep code templates and examples."""
                content = get_simulsweep_template()
                return Resource(
                    uri="resource://measureit_simulsweep_template",
                    name="MeasureIt SimulSweep Template",
                    description="SimulSweep code examples and patterns for simultaneous parameter sweeping",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_simulsweep_template",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_sweepqueue_template")
            async def measureit_sweepqueue_template() -> Resource:
                """Resource providing SweepQueue code templates and examples."""
                content = get_sweepqueue_template()
                return Resource(
                    uri="resource://measureit_sweepqueue_template",
                    name="MeasureIt SweepQueue Template",
                    description="SweepQueue code examples and patterns for sequential measurement workflows",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_sweepqueue_template",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_common_patterns")
            async def measureit_common_patterns() -> Resource:
                """Resource providing common MeasureIt patterns and best practices."""
                content = get_common_patterns_template()
                return Resource(
                    uri="resource://measureit_common_patterns",
                    name="MeasureIt Common Patterns",
                    description="Common MeasureIt patterns and best practices for measurement workflows",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_common_patterns",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://measureit_code_examples")
            async def measureit_code_examples() -> Resource:
                """Resource providing all MeasureIt patterns in a structured format."""
                content = get_measureit_code_examples()
                return Resource(
                    uri="resource://measureit_code_examples",
                    name="MeasureIt Code Examples",
                    description="Complete collection of all MeasureIt patterns and templates in structured format",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://measureit_code_examples",
                        mimeType="application/json",
                        text=content
                    )]
                )

        # Database integration resources (optional - only if database option enabled)
        if DATABASE_AVAILABLE and 'database' in self.enabled_options:

            @self.mcp.resource("resource://database_config")
            async def database_config() -> Resource:
                """Resource providing current database configuration and connection status."""
                content = db_integration.get_current_database_config(database_path=None)
                return Resource(
                    uri="resource://database_config",
                    name="Database Configuration",
                    description="Current QCodes database configuration, path, and connection status",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://database_config",
                        mimeType="application/json",
                        text=content
                    )]
                )

            @self.mcp.resource("resource://recent_measurements")
            async def recent_measurements() -> Resource:
                """Resource providing recent measurement metadata."""
                content = db_integration.get_recent_measurements(limit=20, database_path=None)
                return Resource(
                    uri="resource://recent_measurements",
                    name="Recent Measurements",
                    description="Metadata for recent measurements across all experiments",
                    mimeType="application/json",
                    contents=[TextResourceContents(
                        uri="resource://recent_measurements",
                        mimeType="application/json",
                        text=content
                    )]
                )


    def _register_tools(self):
        """Register all MCP tools."""
        
        # QCoDeS instrument tools
        
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
        async def get_parameter_values(queries: str) -> List[TextContent]:
            """Get parameter values - supports both single parameter and batch queries.

            Args:
                queries: JSON string containing single query or list of queries
                         Single: {"instrument": "name", "parameter": "param", "fresh": false}
                         Batch: [{"instrument": "name1", "parameter": "param1"}, ...]
            """
            try:
                queries_data = json.loads(queries)
                results = await self.tools.get_parameter_values(queries_data)
                return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in get_parameter_values: {e}")
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
        async def get_editing_cell_output() -> List[TextContent]:
            """Get the output of the most recently executed cell.
            
            This tool retrieves the output from the last executed cell in the notebook.
            If a cell is currently running, it will indicate that status instead.
            """
            try:
                # Use IPython's In/Out cache to get the last executed cell
                if hasattr(self.ipython, 'user_ns'):
                    In = self.ipython.user_ns.get('In', [])
                    Out = self.ipython.user_ns.get('Out', {})
                    current_execution_count = getattr(self.ipython, 'execution_count', 0)
                    
                    if len(In) > 1:  # In[0] is empty
                        latest_cell_num = len(In) - 1
                        
                        # Check if the latest cell is currently running
                        # Cell is running if: it exists in In but not in Out, and matches current execution count
                        if (latest_cell_num not in Out and 
                            latest_cell_num == current_execution_count and
                            In[latest_cell_num]):
                            
                            cell_info = {
                                "cell_number": latest_cell_num,
                                "execution_count": latest_cell_num,
                                "input": In[latest_cell_num],
                                "status": "running",
                                "message": "Cell is currently executing - no output available yet",
                                "has_output": False,
                                "output": None
                            }
                            return [TextContent(type="text", text=json.dumps(cell_info, indent=2))]
                        
                        # Find the most recent completed cell (has both input and output)
                        for i in range(len(In) - 1, 0, -1):  # Start from most recent
                            if In[i]:  # Skip empty entries
                                if i in Out:
                                    # Cell completed with output
                                    cell_info = {
                                        "cell_number": i,
                                        "execution_count": i,
                                        "input": In[i],
                                        "status": "completed",
                                        "output": str(Out[i]),
                                        "has_output": True
                                    }
                                    return [TextContent(type="text", text=json.dumps(cell_info, indent=2))]
                                elif i < current_execution_count:
                                    # Cell was executed but produced no output
                                    cell_info = {
                                        "cell_number": i,
                                        "execution_count": i,
                                        "input": In[i],
                                        "status": "completed_no_output",
                                        "message": "Cell executed successfully but produced no output",
                                        "output": None,
                                        "has_output": False
                                    }
                                    return [TextContent(type="text", text=json.dumps(cell_info, indent=2))]
                
                # Fallback: no recent executed cells
                result = {
                    "status": "no_cells",
                    "error": "No recently executed cells found",
                    "message": "Execute a cell first to see its output",
                    "has_output": False
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
            except Exception as e:
                logger.error(f"Error in get_editing_cell_output: {e}")
                return [TextContent(type="text", text=json.dumps({"status": "error", "error": str(e)}, indent=2))]
        
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

        # Database integration tools (optional - only if database option enabled)
        if DATABASE_AVAILABLE and 'database' in self.enabled_options:

            @self.mcp.tool()
            async def list_experiments(database_path: Optional[str] = None) -> List[TextContent]:
                """List all experiments in the specified QCodes database.

                Args:
                    database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

                Returns JSON containing experiment information including ID, name,
                sample_name, start_time, end_time, and number of datasets.
                """
                try:
                    result = db_integration.list_experiments(database_path=database_path)
                    return [TextContent(type="text", text=result)]
                except Exception as e:
                    logger.error(f"Error in list_experiments: {e}")
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]


            @self.mcp.tool()
            async def get_dataset_info(
                id: int,
                database_path: Optional[str] = None
            ) -> List[TextContent]:
                """Get detailed information about a specific dataset.

                Args:
                    id: Dataset run ID to load (e.g., load_by_id(2))
                    database_path: Path to database file. If None, uses MeasureIt default or QCodes config.
                """
                try:
                    result = db_integration.get_dataset_info(
                        id=id,
                        database_path=database_path
                    )
                    return [TextContent(type="text", text=result)]
                except Exception as e:
                    logger.error(f"Error in get_dataset_info: {e}")
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

            @self.mcp.tool()
            async def get_database_stats(database_path: Optional[str] = None) -> List[TextContent]:
                """Get database statistics and health information.

                Args:
                    database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

                Returns JSON containing database statistics including path, size,
                experiment count, dataset count, and last modified time.
                """
                try:
                    result = db_integration.get_database_stats(database_path=database_path)
                    return [TextContent(type="text", text=result)]
                except Exception as e:
                    logger.error(f"Error in get_database_stats: {e}")
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]



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

    def set_enabled_options(self, enabled_options: set) -> Dict[str, Any]:
        """Change the server's enabled options.

        Note: This requires server restart to take effect for resource registration.

        Args:
            enabled_options: Set of enabled option names

        Returns:
            Dictionary with status information
        """
        old_options = self.enabled_options.copy()
        self.enabled_options = enabled_options.copy()

        added = enabled_options - old_options
        removed = old_options - enabled_options

        logger.info(f"MCP server options changed: added={added}, removed={removed}")

        return {
            "old_options": sorted(old_options),
            "new_options": sorted(enabled_options),
            "added_options": sorted(added),
            "removed_options": sorted(removed),
            "server_running": self.running,
            "restart_required": True,
            "message": f"Server options updated. Restart required for resource changes to take effect."
        }