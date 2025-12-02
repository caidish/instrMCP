"""
Jupyter notebook tool registrar.

Registers tools for interacting with Jupyter notebook variables and cells.
"""

import json
import time
from typing import List, Optional

from mcp.types import TextContent
from ..active_cell_bridge import get_cell_outputs, get_cached_cell_output
from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call

logger = get_logger("tools.notebook")


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

    def _get_frontend_output(
        self, cell_number: int, timeout_s: float = 0.5
    ) -> Optional[dict]:
        """
        Request and retrieve cell output from JupyterLab frontend.

        Args:
            cell_number: Execution count of the cell
            timeout_s: Timeout for waiting for response

        Returns:
            Dictionary with output data or None if not available
        """
        # First check cache
        cached = get_cached_cell_output(cell_number)
        if cached:
            return cached

        # Request from frontend
        result = get_cell_outputs([cell_number], timeout_s=timeout_s)
        if not result.get("success"):
            return None

        # Wait a bit for response to arrive and be cached
        time.sleep(0.1)

        # Check cache again
        return get_cached_cell_output(cell_number)

    def register_all(self):
        """Register all notebook tools."""
        self._register_list_variables()
        self._register_get_variable_info()
        self._register_get_editing_cell()
        self._register_get_editing_cell_output()
        self._register_get_notebook_cells()
        self._register_move_cursor()
        self._register_server_status()

    def _register_list_variables(self):
        """Register the notebook/list_variables tool."""

        @self.mcp.tool(name="notebook_list_variables")
        async def list_variables(type_filter: str = None) -> List[TextContent]:
            """List variables in the Jupyter namespace.

            Args:
                type_filter: Optional type filter (e.g., "array", "dict", "instrument")
            """
            start = time.perf_counter()
            try:
                variables = await self.tools.list_variables(type_filter)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_list_variables",
                    {"type_filter": type_filter},
                    duration,
                    "success",
                )
                return [TextContent(type="text", text=json.dumps(variables, indent=2))]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_list_variables",
                    {"type_filter": type_filter},
                    duration,
                    "error",
                    str(e),
                )
                logger.error(f"Error in notebook/list_variables: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_variable_info(self):
        """Register the notebook/get_variable_info tool."""

        @self.mcp.tool(name="notebook_get_variable_info")
        async def get_variable_info(name: str) -> List[TextContent]:
            """Get detailed information about a notebook variable.

            Args:
                name: Variable name
            """
            start = time.perf_counter()
            try:
                info = await self.tools.get_variable_info(name)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_get_variable_info", {"name": name}, duration, "success"
                )
                return [TextContent(type="text", text=json.dumps(info, indent=2))]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_get_variable_info",
                    {"name": name},
                    duration,
                    "error",
                    str(e),
                )
                logger.error(f"Error in notebook/get_variable_info: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_editing_cell(self):
        """Register the notebook/get_editing_cell tool."""

        @self.mcp.tool(name="notebook_get_editing_cell")
        async def get_editing_cell(
            fresh_ms: int = 1000,
            line_start: Optional[int] = None,
            line_end: Optional[int] = None,
            max_lines: int = 200,
        ) -> List[TextContent]:
            """Get the currently editing cell content from JupyterLab frontend.

            This captures the cell that is currently being edited in the frontend.

            Args:
                fresh_ms: Maximum age in milliseconds. If provided and cached data is older,
                         will request fresh data from frontend (default: 1000)
                line_start: Optional starting line number (1-indexed).
                line_end: Optional ending line number (1-indexed, inclusive).
                max_lines: Maximum number of lines to return (default: 200).

            Line selection logic:
                - If both line_start and line_end are provided: return those lines exactly
                - Else if total_lines <= max_lines: return all lines
                - Else if line_start is provided: return max_lines starting from line_start
                - Else if line_end is provided: return max_lines ending at line_end
                - Else: return first max_lines lines
            """
            start = time.perf_counter()
            args = {
                "fresh_ms": fresh_ms,
                "line_start": line_start,
                "line_end": line_end,
                "max_lines": max_lines,
            }
            try:
                result = await self.tools.get_editing_cell(
                    fresh_ms=fresh_ms,
                    line_start=line_start,
                    line_end=line_end,
                    max_lines=max_lines,
                )
                duration = (time.perf_counter() - start) * 1000
                log_tool_call("notebook_get_editing_cell", args, duration, "success")
                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_get_editing_cell", args, duration, "error", str(e)
                )
                logger.error(f"Error in notebook/get_editing_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_editing_cell_output(self):
        """Register the notebook/get_editing_cell_output tool."""

        @self.mcp.tool(name="notebook_get_editing_cell_output")
        async def get_editing_cell_output() -> List[TextContent]:
            """Get the output of the most recently executed cell, including errors.

            This tool retrieves the output from the last executed cell in the notebook.
            If a cell is currently running, it will indicate that status instead.
            If a cell raised an error, the error information will be included.
            """
            try:
                import sys
                import traceback

                # Use IPython's In/Out cache to get the last executed cell
                if hasattr(self.ipython, "user_ns"):
                    In = self.ipython.user_ns.get("In", [])
                    Out = self.ipython.user_ns.get("Out", {})
                    current_execution_count = getattr(
                        self.ipython, "execution_count", 0
                    )

                    if len(In) > 1:  # In[0] is empty
                        latest_cell_num = len(In) - 1

                        # Check if the latest cell is currently running
                        if (
                            latest_cell_num not in Out
                            and latest_cell_num == current_execution_count
                            and In[latest_cell_num]
                        ):
                            cell_info = {
                                "cell_number": latest_cell_num,
                                "execution_count": latest_cell_num,
                                "input": In[latest_cell_num],
                                "status": "running",
                                "message": "Cell is currently executing - no output available yet",
                                "has_output": False,
                                "has_error": False,
                                "output": None,
                            }
                            return [
                                TextContent(
                                    type="text", text=json.dumps(cell_info, indent=2)
                                )
                            ]

                        # Find the most recent completed cell (has both input and output)
                        for i in range(len(In) - 1, 0, -1):  # Start from most recent
                            if In[i]:  # Skip empty entries
                                # Try to get output from JupyterLab frontend
                                try:
                                    frontend_output = self._get_frontend_output(i)
                                    if frontend_output and frontend_output.get(
                                        "has_output"
                                    ):
                                        # Return the complete output structure
                                        cell_info = {
                                            "cell_number": i,
                                            "execution_count": i,
                                            "input": In[i],
                                            "status": "completed",
                                            "outputs": frontend_output.get(
                                                "outputs", []
                                            ),
                                            "has_output": True,
                                            "has_error": False,
                                        }
                                        return [
                                            TextContent(
                                                type="text",
                                                text=json.dumps(cell_info, indent=2),
                                            )
                                        ]
                                except Exception as e:
                                    logger.warning(
                                        f"Error extracting frontend output for cell {i}: {e}"
                                    )

                                # Check Out dictionary (for expression return values)
                                if i in Out:
                                    # Cell completed with output
                                    cell_info = {
                                        "cell_number": i,
                                        "execution_count": i,
                                        "input": In[i],
                                        "status": "completed",
                                        "output": str(Out[i]),
                                        "has_output": True,
                                        "has_error": False,
                                    }
                                    return [
                                        TextContent(
                                            type="text",
                                            text=json.dumps(cell_info, indent=2),
                                        )
                                    ]
                                elif i < current_execution_count:
                                    # Cell was executed but produced no output
                                    # Check if this was due to an error
                                    has_error = False
                                    error_info = None

                                    # Check sys.last_* for most recent exception
                                    if (
                                        hasattr(sys, "last_type")
                                        and hasattr(sys, "last_value")
                                        and hasattr(sys, "last_traceback")
                                        and sys.last_type is not None
                                    ):
                                        # We can only know if this cell raised the last exception
                                        # by checking if it's the most recent executed cell
                                        if i == latest_cell_num:
                                            has_error = True
                                            error_info = {
                                                "type": sys.last_type.__name__,
                                                "message": str(sys.last_value),
                                                "traceback": "".join(
                                                    traceback.format_exception(
                                                        sys.last_type,
                                                        sys.last_value,
                                                        sys.last_traceback,
                                                    )
                                                ),
                                            }

                                    if has_error:
                                        cell_info = {
                                            "cell_number": i,
                                            "execution_count": i,
                                            "input": In[i],
                                            "status": "error",
                                            "message": "Cell raised an exception",
                                            "output": None,
                                            "has_output": False,
                                            "has_error": True,
                                            "error": error_info,
                                        }
                                    else:
                                        cell_info = {
                                            "cell_number": i,
                                            "execution_count": i,
                                            "input": In[i],
                                            "status": "completed_no_output",
                                            "message": "Cell executed successfully but produced no output",
                                            "output": None,
                                            "has_output": False,
                                            "has_error": False,
                                        }
                                    return [
                                        TextContent(
                                            type="text",
                                            text=json.dumps(cell_info, indent=2),
                                        )
                                    ]

                # Fallback: no recent executed cells
                result = {
                    "status": "no_cells",
                    "error": "No recently executed cells found",
                    "message": "Execute a cell first to see its output",
                    "has_output": False,
                    "has_error": False,
                }
                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error in get_editing_cell_output: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"status": "error", "error": str(e)}, indent=2),
                    )
                ]

    def _register_get_notebook_cells(self):
        """Register the notebook/get_notebook_cells tool."""

        @self.mcp.tool(name="notebook_get_notebook_cells")
        async def get_notebook_cells(
            num_cells: int = 2, include_output: bool = True
        ) -> List[TextContent]:
            """Get recent notebook cells with input, output, and error information.

            Args:
                num_cells: Number of recent cells to retrieve (default: 2 for performance)
                include_output: Include cell outputs and errors (default: True)
            """
            try:
                import sys
                import traceback

                cells = []
                current_execution_count = getattr(self.ipython, "execution_count", 0)

                # Track last error info (only most recent is available)
                last_error_info = None
                latest_cell_with_error = None
                if (
                    hasattr(sys, "last_type")
                    and hasattr(sys, "last_value")
                    and hasattr(sys, "last_traceback")
                    and sys.last_type is not None
                ):
                    last_error_info = {
                        "type": sys.last_type.__name__,
                        "message": str(sys.last_value),
                        "traceback": "".join(
                            traceback.format_exception(
                                sys.last_type, sys.last_value, sys.last_traceback
                            )
                        ),
                    }

                # Method 1: Use IPython's In/Out cache (fastest for recent cells)
                if hasattr(self.ipython, "user_ns"):
                    In = self.ipython.user_ns.get("In", [])
                    Out = self.ipython.user_ns.get("Out", {})

                    # Get the last num_cells entries
                    if len(In) > 1:  # In[0] is empty
                        start_idx = max(1, len(In) - num_cells)
                        latest_executed = len(In) - 1

                        # The most recent error corresponds to the latest executed cell
                        # that doesn't have output
                        if (
                            last_error_info
                            and latest_executed not in Out
                            and latest_executed < current_execution_count
                        ):
                            latest_cell_with_error = latest_executed

                        for i in range(start_idx, len(In)):
                            if i < len(In) and In[i]:  # Skip empty entries
                                cell_info = {
                                    "cell_number": i,
                                    "execution_count": i,
                                    "input": In[i],
                                    "has_error": False,
                                }

                                if include_output:
                                    # Try to get output from JupyterLab frontend
                                    try:
                                        frontend_output = self._get_frontend_output(i)
                                        if frontend_output and frontend_output.get(
                                            "has_output"
                                        ):
                                            # Return complete output structure
                                            cell_info["outputs"] = frontend_output.get(
                                                "outputs", []
                                            )
                                            cell_info["has_output"] = True
                                            cells.append(cell_info)
                                            continue  # Skip other checks for this cell
                                    except Exception as e:
                                        logger.warning(
                                            f"Error getting frontend output for cell {i}: {e}"
                                        )

                                    # Check Out dictionary (expression return values)
                                    if i in Out:
                                        # Cell has output
                                        cell_info["output"] = str(Out[i])
                                        cell_info["has_output"] = True
                                    elif (
                                        i == latest_cell_with_error and last_error_info
                                    ):
                                        # Cell raised the most recent error
                                        cell_info["has_output"] = False
                                        cell_info["has_error"] = True
                                        cell_info["error"] = last_error_info
                                        cell_info["status"] = "error"
                                    elif i < current_execution_count:
                                        # Cell executed but has no output (and no known error)
                                        cell_info["has_output"] = False
                                        cell_info["status"] = "completed_no_output"
                                    else:
                                        # Cell not yet executed
                                        cell_info["has_output"] = False
                                        cell_info["status"] = "not_executed"
                                else:
                                    cell_info["has_output"] = False

                                cells.append(cell_info)

                # Method 2: Fallback to history_manager if In/Out not available
                if not cells and hasattr(self.ipython, "history_manager"):
                    try:
                        # Get range with output
                        current_count = getattr(self.ipython, "execution_count", 1)
                        start_line = max(1, current_count - num_cells)

                        history = list(
                            self.ipython.history_manager.get_range(
                                session=0,  # Current session
                                start=start_line,
                                stop=current_count + 1,
                                raw=True,
                                output=include_output,
                            )
                        )

                        for _, line_num, content in history:
                            if include_output and isinstance(content, tuple):
                                input_text, output_text = content
                                cells.append(
                                    {
                                        "cell_number": line_num,
                                        "execution_count": line_num,
                                        "input": input_text,
                                        "output": (
                                            str(output_text) if output_text else None
                                        ),
                                        "has_output": output_text is not None,
                                        "has_error": False,  # Can't determine from history_manager
                                    }
                                )
                            else:
                                cells.append(
                                    {
                                        "cell_number": line_num,
                                        "execution_count": line_num,
                                        "input": content,
                                        "has_output": False,
                                        "has_error": False,  # Can't determine from history_manager
                                    }
                                )
                    except Exception as hist_error:
                        logger.warning(f"History manager fallback failed: {hist_error}")

                # Count cells with errors
                error_count = sum(1 for cell in cells if cell.get("has_error", False))

                result = {
                    "cells": cells,
                    "count": len(cells),
                    "requested": num_cells,
                    "error_count": error_count,
                    "note": "Only the most recent error can be captured. Older errors are not available.",
                }

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error in get_notebook_cells: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_move_cursor(self):
        """Register the notebook/move_cursor tool."""

        @self.mcp.tool(name="notebook_move_cursor")
        async def move_cursor(target: str) -> List[TextContent]:
            """Move cursor to a different cell in the notebook.

            Changes which cell is currently active (selected) in JupyterLab.
            This is a SAFE operation as it only changes selection without modifying content.

            Args:
                target: Where to move the cursor:
                       - "above": Move to cell above current
                       - "below": Move to cell below current
                       - "bottom": Move to the last cell in the notebook (by file order)
                       - "<number>": Move to cell with that execution count (e.g., "5" for [5])

            Returns:
                JSON with operation status, old index, and new index

            Example usage:
                move_cursor("below")   # Move to next cell
                move_cursor("above")   # Move to previous cell
                move_cursor("bottom")  # Move to last cell in notebook
                move_cursor("5")       # Move to cell [5]
            """
            try:
                result = await self.tools.move_cursor(target)
                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/move_cursor: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_server_status(self):
        """Register the notebook/server_status tool."""

        @self.mcp.tool(name="notebook_server_status")
        async def server_status() -> List[TextContent]:
            """Get server status and configuration."""
            try:
                # Get list of registered tools from FastMCP
                registered_tools = []
                if hasattr(self.mcp, "_tools"):
                    registered_tools = list(self.mcp._tools.keys())

                status = {
                    "status": "running",
                    "mode": (
                        "safe"
                        if hasattr(self, "safe_mode") and self.safe_mode
                        else "unsafe"
                    ),
                    "tools_count": len(registered_tools),
                    "tools": registered_tools[:20],  # Limit to first 20 for readability
                }

                return [TextContent(type="text", text=json.dumps(status, indent=2))]
            except Exception as e:
                logger.error(f"Error in server_status: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
