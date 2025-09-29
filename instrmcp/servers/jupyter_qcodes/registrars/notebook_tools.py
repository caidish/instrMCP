"""
Jupyter notebook tool registrar.

Registers tools for interacting with Jupyter notebook variables and cells.
"""

import json
import logging
from typing import List

from mcp.types import TextContent

logger = logging.getLogger(__name__)


class NotebookToolRegistrar:
    """Registers Jupyter notebook tools with the MCP server."""

    def __init__(self, mcp_server, tools, ipython):
        """
        Initialize the notebook tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            ipython: IPython instance for direct notebook access
        """
        self.mcp = mcp_server
        self.tools = tools
        self.ipython = ipython

    def register_all(self):
        """Register all notebook tools."""
        self._register_list_variables()
        self._register_get_variable_info()
        self._register_get_editing_cell()
        self._register_update_editing_cell()
        self._register_get_editing_cell_output()
        self._register_get_notebook_cells()
        self._register_server_status()

    def _register_list_variables(self):
        """Register the notebook/list_variables tool."""

        @self.mcp.tool(name="notebook/list_variables")
        async def list_variables(type_filter: str = None) -> List[TextContent]:
            """List variables in the Jupyter namespace.

            Args:
                type_filter: Optional type filter (e.g., "array", "dict", "instrument")
            """
            try:
                variables = await self.tools.list_variables(type_filter)
                return [TextContent(type="text", text=json.dumps(variables, indent=2))]
            except Exception as e:
                logger.error(f"Error in notebook/list_variables: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_get_variable_info(self):
        """Register the notebook/get_variable_info tool."""

        @self.mcp.tool(name="notebook/get_variable_info")
        async def get_variable_info(name: str) -> List[TextContent]:
            """Get detailed information about a notebook variable.

            Args:
                name: Variable name
            """
            try:
                info = await self.tools.get_variable_info(name)
                return [TextContent(type="text", text=json.dumps(info, indent=2))]
            except Exception as e:
                logger.error(f"Error in notebook/get_variable_info: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_get_editing_cell(self):
        """Register the notebook/get_editing_cell tool."""

        @self.mcp.tool(name="notebook/get_editing_cell")
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
                logger.error(f"Error in notebook/get_editing_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_update_editing_cell(self):
        """Register the notebook/update_editing_cell tool."""

        @self.mcp.tool(name="notebook/update_editing_cell")
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
                logger.error(f"Error in notebook/update_editing_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_get_editing_cell_output(self):
        """Register the notebook/get_editing_cell_output tool."""

        @self.mcp.tool(name="notebook/get_editing_cell_output")
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

    def _register_get_notebook_cells(self):
        """Register the notebook/get_notebook_cells tool."""

        @self.mcp.tool(name="notebook/get_notebook_cells")
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

                        for _, line_num, content in history:
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
                    except Exception as hist_error:
                        logger.warning(f"History manager fallback failed: {hist_error}")

                result = {
                    "cells": cells,
                    "count": len(cells),
                    "requested": num_cells
                }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error in get_notebook_cells: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_server_status(self):
        """Register the notebook/server_status tool."""

        @self.mcp.tool(name="notebook/server_status")
        async def server_status() -> List[TextContent]:
            """Get server status and configuration."""
            try:
                # Get list of registered tools from FastMCP
                registered_tools = []
                if hasattr(self.mcp, '_tools'):
                    registered_tools = list(self.mcp._tools.keys())

                status = {
                    "status": "running",
                    "mode": "safe" if hasattr(self, 'safe_mode') and self.safe_mode else "unsafe",
                    "tools_count": len(registered_tools),
                    "tools": registered_tools[:20],  # Limit to first 20 for readability
                }

                return [TextContent(type="text", text=json.dumps(status, indent=2))]
            except Exception as e:
                logger.error(f"Error in server_status: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]