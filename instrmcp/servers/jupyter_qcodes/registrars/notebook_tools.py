"""
Jupyter notebook tool registrar.

Registers tools for interacting with Jupyter notebook variables and cells.
"""

import json
import time
from typing import List, Optional

from mcp.types import TextContent
from ..active_cell_bridge import (
    get_cell_outputs,
    get_cached_cell_output,
    get_active_cell_output,
)
from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call

logger = get_logger("tools.notebook")


class NotebookToolRegistrar:
    """Registers Jupyter notebook tools with the MCP server."""

    def __init__(
        self,
        mcp_server,
        tools,
        ipython,
        safe_mode=True,
        dangerous_mode=False,
        enabled_options=None,
    ):
        """
        Initialize the notebook tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            ipython: IPython instance for direct notebook access
            safe_mode: Whether server is in safe mode (read-only)
            dangerous_mode: Whether server is in dangerous mode (auto-approve consents)
            enabled_options: Set of enabled optional features (measureit, database, etc.)
        """
        self.mcp = mcp_server
        self.tools = tools
        self.ipython = ipython
        self.safe_mode = safe_mode
        self.dangerous_mode = dangerous_mode
        self.enabled_options = enabled_options or set()

    # ===== Concise mode helpers =====

    def _to_concise_variable_info(self, info: dict) -> dict:
        """Convert full variable info to concise format.

        Concise: name, type, qcodes_instrument flag, brief repr (first 10 chars).
        """
        repr_full = info.get("repr", "")
        brief_repr = repr_full[:10] + "..." if len(repr_full) > 10 else repr_full
        return {
            "name": info.get("name"),
            "type": info.get("type"),
            "qcodes_instrument": info.get("qcodes_instrument", False),
            "repr": brief_repr,
        }

    def _to_concise_editing_cell(self, result: dict) -> dict:
        """Convert full editing cell info to concise format.

        Concise: cell_type, cell_index, cell_content.
        """
        return {
            "cell_type": result.get("cell_type"),
            "cell_index": result.get("cell_index"),
            "cell_content": result.get("cell_content"),
        }

    def _to_concise_editing_cell_output(self, info: dict) -> dict:
        """Convert full editing cell output to concise format.

        Concise: status, message, has_output, has_error, output_summary (truncated),
        plus error_type/error_message if has_error is true.
        Removes verbose outputs array and provides brief summary instead.
        """
        # Extract a brief summary of output (first 100 chars)
        output_summary = None
        outputs = info.get("outputs") or info.get("output")
        if outputs:
            if isinstance(outputs, str):
                output_summary = (
                    outputs[:100] + "..." if len(outputs) > 100 else outputs
                )
            elif isinstance(outputs, list) and len(outputs) > 0:
                # Get first text output from outputs array
                for out in outputs:
                    if isinstance(out, dict):
                        text = out.get("text") or out.get("data", {}).get(
                            "text/plain", ""
                        )
                        if text:
                            if isinstance(text, list):
                                text = "".join(text)
                            output_summary = (
                                text[:100] + "..." if len(text) > 100 else text
                            )
                            break

        result = {
            "status": info.get("status"),
            "message": info.get("message"),
            "has_output": info.get("has_output", False),
            "has_error": info.get("has_error", False),
            "output_summary": output_summary,
        }

        if info.get("has_error") and info.get("error"):
            result["error_type"] = info["error"].get("type")
            result["error_message"] = info["error"].get("message")

        return result

    def _to_concise_notebook_cells(self, result: dict) -> dict:
        """Convert full notebook cells to concise format.

        Concise: recent cells with cell_number, input (truncated), has_output, has_error, status.
        """
        concise_cells = []
        for cell in result.get("cells", []):
            input_text = cell.get("input", "")
            truncated_input = (
                input_text[:100] + "..." if len(input_text) > 100 else input_text
            )
            concise_cells.append(
                {
                    "cell_number": cell.get("cell_number"),
                    "input": truncated_input,
                    "has_output": cell.get("has_output", False),
                    "has_error": cell.get("has_error", False),
                    "status": cell.get("status"),
                }
            )
        return {"cells": concise_cells, "count": len(concise_cells)}

    def _to_concise_move_cursor(self, result: dict) -> dict:
        """Convert full move cursor result to concise format.

        Concise: success only.
        """
        return {"success": result.get("success", False)}

    # ===== End concise mode helpers =====

    def _is_valid_frontend_output(self, frontend_output: dict) -> bool:
        """Check if frontend response is valid cell output data (not a failure response).

        Valid responses have 'has_output' field or 'outputs' array.
        Failure responses like {success: false, message: "..."} are not valid.
        """
        if not frontend_output or not isinstance(frontend_output, dict):
            return False
        # Valid cell output has 'has_output' field or 'outputs' array
        return "has_output" in frontend_output or "outputs" in frontend_output

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

        @self.mcp.tool(
            name="notebook_list_variables",
            annotations={
                "title": "List Notebook Variables",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_variables(
            type_filter: Optional[str] = None,
        ) -> List[TextContent]:
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

        @self.mcp.tool(
            name="notebook_get_variable_info",
            annotations={
                "title": "Get Variable Info",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_variable_info(
            name: str, detailed: bool = False
        ) -> List[TextContent]:
            """Get detailed information about a notebook variable.

            Args:
                name: Variable name
                detailed: If False (default), return concise summary; if True, return full info
            """
            start = time.perf_counter()
            try:
                info = await self.tools.get_variable_info(name)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_get_variable_info",
                    {"name": name, "detailed": detailed},
                    duration,
                    "success",
                )

                # Apply concise mode filtering
                if not detailed:
                    info = self._to_concise_variable_info(info)

                return [TextContent(type="text", text=json.dumps(info, indent=2))]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_get_variable_info",
                    {"name": name, "detailed": detailed},
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

        @self.mcp.tool(
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
        ) -> List[TextContent]:
            """Get the currently editing cell content from JupyterLab frontend.

            This captures the cell that is currently being edited in the frontend.

            Args:
                fresh_ms: Maximum age in milliseconds. If provided and cached data is older,
                         will request fresh data from frontend (default: 1000)
                line_start: Optional starting line number (1-indexed).
                line_end: Optional ending line number (1-indexed, inclusive).
                max_lines: Maximum number of lines to return (default: 200).
                detailed: If False (default), return concise summary; if True, return full info

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
                "detailed": detailed,
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

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_editing_cell(result)

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

        @self.mcp.tool(
            name="notebook_get_editing_cell_output",
            annotations={
                "title": "Get Cell Output",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_editing_cell_output(detailed: bool = False) -> List[TextContent]:
            """Get the output of the currently active cell in JupyterLab.

            This tool retrieves the output from the cell that is currently selected
            in JupyterLab, including any errors. If the cell hasn't been executed,
            it will indicate that status.

            Args:
                detailed: If False (default), return concise summary; if True, return full info
            """

            def format_response(info: dict) -> List[TextContent]:
                """Helper to format response with optional concise filtering."""
                if not detailed:
                    info = self._to_concise_editing_cell_output(info)
                return [TextContent(type="text", text=json.dumps(info, indent=2))]

            try:
                # FIX for Bug #10: Use direct frontend query instead of IPython history
                # This gets output from the currently selected cell in JupyterLab,
                # avoiding stale state issues with sys.last_* and Out history.
                frontend_result = get_active_cell_output(timeout_s=2.0)

                if frontend_result.get("success"):
                    # Frontend returned the active cell's output directly
                    outputs = frontend_result.get("outputs", [])
                    has_output = frontend_result.get("has_output", False)
                    has_error = frontend_result.get("has_error", False)
                    execution_count = frontend_result.get("execution_count")
                    cell_type = frontend_result.get("cell_type", "code")
                    cell_index = frontend_result.get("cell_index")

                    # Handle non-code cells
                    if cell_type != "code":
                        cell_info = {
                            "status": "not_code_cell",
                            "message": f"Active cell is a {cell_type} cell (no outputs)",
                            "cell_type": cell_type,
                            "cell_index": cell_index,
                            "has_output": False,
                            "has_error": False,
                        }
                        return format_response(cell_info)

                    # Handle unexecuted code cells
                    if execution_count is None:
                        cell_info = {
                            "status": "not_executed",
                            "message": "Active cell has not been executed yet",
                            "cell_index": cell_index,
                            "has_output": False,
                            "has_error": False,
                        }
                        return format_response(cell_info)

                    # Extract error details if present
                    error_info = None
                    if has_error:
                        for out in outputs:
                            if out.get("type") == "error":
                                error_info = {
                                    "type": out.get("ename", "UnknownError"),
                                    "message": out.get("evalue", ""),
                                    "traceback": "\n".join(out.get("traceback", [])),
                                }
                                break

                    # Build response
                    if has_error:
                        status = "error"
                        message = "Cell raised an exception"
                    elif has_output:
                        status = "completed"
                        message = None
                    else:
                        status = "completed_no_output"
                        message = "Cell executed successfully but produced no output"

                    cell_info = {
                        "cell_number": execution_count,
                        "execution_count": execution_count,
                        "cell_index": cell_index,
                        "status": status,
                        # Include outputs if there's output OR if there's an error
                        # (error details are in the outputs array)
                        "outputs": outputs if (has_output or has_error) else None,
                        "has_output": has_output,
                        "has_error": has_error,
                    }
                    if message:
                        cell_info["message"] = message
                    if error_info:
                        cell_info["error"] = error_info

                    return format_response(cell_info)

                else:
                    # Frontend request failed - fall back to IPython history
                    # Note: _send_and_wait uses 'message' for errors, not 'error'
                    error_msg = frontend_result.get("error") or frontend_result.get(
                        "message"
                    )
                    logger.debug(
                        f"Frontend request failed: {error_msg}, "
                        "falling back to IPython history"
                    )
                    return await self._get_output_from_ipython_history(format_response)

            except Exception as e:
                logger.error(f"Error in get_editing_cell_output: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"status": "error", "error": str(e)}, indent=2),
                    )
                ]

    async def _get_output_from_ipython_history(self, format_response):
        """Fallback: Get output from IPython In/Out history when frontend is unavailable."""
        import sys
        import traceback

        if hasattr(self.ipython, "user_ns"):
            In = self.ipython.user_ns.get("In", [])
            Out = self.ipython.user_ns.get("Out", {})
            current_execution_count = getattr(self.ipython, "execution_count", 0)

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
                    return format_response(cell_info)

                # Find the most recent completed cell
                for i in range(len(In) - 1, 0, -1):
                    if In[i]:  # Skip empty entries
                        # Check Out dictionary
                        if i in Out:
                            cell_info = {
                                "cell_number": i,
                                "execution_count": i,
                                "input": In[i],
                                "status": "completed",
                                "output": str(Out[i]),
                                "has_output": True,
                                "has_error": False,
                            }
                            return format_response(cell_info)
                        elif i < current_execution_count:
                            # Cell was executed but produced no output
                            has_error = False
                            error_info = None

                            # Check sys.last_* for error info
                            if (
                                hasattr(sys, "last_type")
                                and hasattr(sys, "last_value")
                                and hasattr(sys, "last_traceback")
                                and sys.last_type is not None
                                and i == latest_cell_num
                            ):
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
                            return format_response(cell_info)

        # Fallback: no recent executed cells
        result = {
            "status": "no_cells",
            "error": "No recently executed cells found",
            "message": "Execute a cell first to see its output",
            "has_output": False,
            "has_error": False,
        }
        return format_response(result)

    def _register_get_notebook_cells(self):
        """Register the notebook/get_notebook_cells tool."""

        @self.mcp.tool(
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
        ) -> List[TextContent]:
            """Get recent notebook cells with input, output, and error information.

            Args:
                num_cells: Number of recent cells to retrieve (default: 2 for performance)
                include_output: Include cell outputs and errors (default: True)
                detailed: If False (default), return concise summary; if True, return full info
            """
            try:
                import sys
                import traceback

                cells = []
                current_execution_count = getattr(self.ipython, "execution_count", 0)

                # FRONTEND-FIRST FIX: Removed pre-computation of latest_cell_with_error
                # based on sys.last_* as it causes stale error state bugs.
                # Error detection now happens per-cell using frontend data.

                # Method 1: Use IPython's In/Out cache (fastest for recent cells)
                if hasattr(self.ipython, "user_ns"):
                    In = self.ipython.user_ns.get("In", [])
                    Out = self.ipython.user_ns.get("Out", {})

                    # Get the last num_cells entries
                    if len(In) > 1:  # In[0] is empty
                        start_idx = max(1, len(In) - num_cells)
                        latest_executed = len(In) - 1

                        for i in range(start_idx, len(In)):
                            if i < len(In) and In[i]:  # Skip empty entries
                                cell_info = {
                                    "cell_number": i,
                                    "execution_count": i,
                                    "input": In[i],
                                    "has_error": False,
                                }

                                if include_output:
                                    # FRONTEND-FIRST FIX: Track whether frontend has valid data
                                    frontend_output = None
                                    frontend_has_data = False
                                    try:
                                        frontend_output = self._get_frontend_output(i)
                                        # Check if frontend returned valid cell output data
                                        # (not a failure response like {success: false})
                                        frontend_has_data = (
                                            self._is_valid_frontend_output(
                                                frontend_output
                                            )
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"Error getting frontend output for cell {i}: {e}"
                                        )

                                    if frontend_output and frontend_output.get(
                                        "has_output"
                                    ):
                                        # Frontend has output - check for errors
                                        outputs = frontend_output.get("outputs", [])
                                        has_error_output = any(
                                            out.get("type") == "error"
                                            or out.get("output_type") == "error"
                                            for out in outputs
                                        )
                                        cell_info["outputs"] = outputs
                                        cell_info["has_output"] = True
                                        cell_info["has_error"] = has_error_output
                                        # Always set explicit status
                                        cell_info["status"] = (
                                            "error" if has_error_output else "completed"
                                        )
                                        if has_error_output:
                                            # Extract error details
                                            for out in outputs:
                                                if (
                                                    out.get("type") == "error"
                                                    or out.get("output_type") == "error"
                                                ):
                                                    cell_info["error"] = {
                                                        "type": out.get(
                                                            "ename", "UnknownError"
                                                        ),
                                                        "message": out.get(
                                                            "evalue", ""
                                                        ),
                                                        "traceback": "\n".join(
                                                            out.get("traceback", [])
                                                        ),
                                                    }
                                                    break
                                        cells.append(cell_info)
                                        continue  # Skip other checks for this cell

                                    elif frontend_has_data and not frontend_output.get(
                                        "has_output"
                                    ):
                                        # FRONTEND-FIRST FIX: Frontend has data but no output
                                        # Check if there's an error in outputs array
                                        outputs = frontend_output.get("outputs", [])
                                        has_error_output = any(
                                            out.get("type") == "error"
                                            or out.get("output_type") == "error"
                                            for out in outputs
                                        )
                                        cell_info["has_output"] = False
                                        cell_info["has_error"] = has_error_output
                                        if has_error_output:
                                            cell_info["status"] = "error"
                                            for out in outputs:
                                                if (
                                                    out.get("type") == "error"
                                                    or out.get("output_type") == "error"
                                                ):
                                                    cell_info["error"] = {
                                                        "type": out.get(
                                                            "ename", "UnknownError"
                                                        ),
                                                        "message": out.get(
                                                            "evalue", ""
                                                        ),
                                                        "traceback": "\n".join(
                                                            out.get("traceback", [])
                                                        ),
                                                    }
                                                    break
                                        else:
                                            cell_info["status"] = "completed_no_output"
                                        cells.append(cell_info)
                                        continue

                                    # Check Out dictionary (expression return values)
                                    if i in Out:
                                        # Cell has output
                                        cell_info["output"] = str(Out[i])
                                        cell_info["has_output"] = True
                                        cell_info["status"] = "completed"
                                    elif i < current_execution_count:
                                        # Cell executed but has no output
                                        # FRONTEND-FIRST FIX: Only use sys.last_* as last resort
                                        cell_info["has_output"] = False
                                        if (
                                            not frontend_has_data
                                            and i == latest_executed
                                        ):
                                            # Only check sys.last_* for latest cell when
                                            # frontend has no data
                                            if (
                                                hasattr(sys, "last_type")
                                                and hasattr(sys, "last_value")
                                                and hasattr(sys, "last_traceback")
                                                and sys.last_type is not None
                                            ):
                                                cell_info["has_error"] = True
                                                cell_info["error"] = {
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
                                                cell_info["status"] = "error"
                                            else:
                                                cell_info["status"] = (
                                                    "completed_no_output"
                                                )
                                        else:
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

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_notebook_cells(result)

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

        @self.mcp.tool(
            name="notebook_move_cursor",
            annotations={
                "title": "Move Cursor",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def move_cursor(target: str, detailed: bool = False) -> List[TextContent]:
            """Move cursor to a different cell in the notebook.

            Changes which cell is currently active (selected) in JupyterLab.
            This is a SAFE operation as it only changes selection without modifying content.

            Args:
                target: Where to move the cursor:
                       - "above": Move to cell above current
                       - "below": Move to cell below current
                       - "bottom": Move to the last cell in the notebook (by file order)
                       - "<number>": Move to cell with that execution count (e.g., "5" for [5])
                detailed: If False (default), return just success; if True, return full info

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

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_move_cursor(result)

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

        @self.mcp.tool(
            name="notebook_server_status",
            annotations={
                "title": "Server Status",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def server_status() -> List[TextContent]:
            """Get server status and configuration."""
            try:
                # Get list of registered tools from FastMCP
                registered_tools = []
                if hasattr(self.mcp, "_tools"):
                    registered_tools = list(self.mcp._tools.keys())

                # Determine mode: dangerous > unsafe > safe
                if self.dangerous_mode:
                    mode = "dangerous"
                elif self.safe_mode:
                    mode = "safe"
                else:
                    mode = "unsafe"

                status = {
                    "status": "running",
                    "mode": mode,
                    "enabled_options": sorted(list(self.enabled_options)),
                    "dynamic_tools_count": len(registered_tools),
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
