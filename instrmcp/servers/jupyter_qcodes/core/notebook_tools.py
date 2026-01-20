"""
Jupyter notebook tool registrar.

Registers tools for interacting with Jupyter notebook variables and cells.
"""

import json
import time
from typing import List, Optional

from mcp.types import TextContent
from ..active_cell_bridge import (  # noqa: F401 - invalidate_cell_output_cache exposed for unsafe tools
    get_cell_outputs,
    get_cached_cell_output,
    get_active_cell_output,
    get_notebook_structure,
    get_cells_by_index,
    invalidate_cell_output_cache,
)
from instrmcp.utils.logging_config import get_logger
from instrmcp.utils.mcptool_logger import log_tool_call

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

    def _to_detailed_editing_cell(self, result: dict) -> dict:
        """Filter editing cell info for detailed mode.

        Removes internal/debug fields: cell_id, notebook_path, client_id,
        captured, age_seconds, timestamp_ms, source, fresh_requested, fresh_threshold_ms.
        """
        exclude_keys = {
            "cell_id",
            "notebook_path",
            "client_id",
            "captured",
            "age_seconds",
            "timestamp_ms",
            "source",
            "fresh_requested",
            "fresh_threshold_ms",
        }
        return {k: v for k, v in result.items() if k not in exclude_keys}

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
            "cell_id_notebook": info.get("cell_id_notebook") or info.get("cell_index"),
            "executed": info.get("executed", False),
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

    def _to_concise_notebook_cells(
        self, result: dict, include_output: bool = True
    ) -> dict:
        """Convert full notebook cells to concise format.

        Concise: recent cells with cell_id_notebook, cell_type, executed, source (truncated).
        If include_output=True, also includes has_output, has_error, status.
        """
        concise_cells = []
        for cell in result.get("cells", []):
            # Support both old field name (input) and new field name (source)
            source_text = cell.get("source") or cell.get("input", "")
            truncated_source = (
                source_text[:100] + "..." if len(source_text) > 100 else source_text
            )
            concise_cell = {
                "cell_id_notebook": cell.get("cell_id_notebook"),
                "cell_type": cell.get("cell_type"),
                "executed": cell.get("cell_execution_number") is not None,
                "source": truncated_source,
            }
            if include_output:
                concise_cell["has_output"] = cell.get("has_output", False)
                concise_cell["has_error"] = cell.get("has_error", False)
                concise_cell["status"] = cell.get("status")
            concise_cells.append(concise_cell)
        return {
            "total_cells": result.get("total_cells"),
            "cells": concise_cells,
            "count": len(concise_cells),
        }

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

        Uses timestamp-based cache validation to avoid returning stale
        error states that no longer reflect the current cell state.

        Args:
            cell_number: Execution count of the cell
            timeout_s: Timeout for waiting for response

        Returns:
            Dictionary with output data or None if not available/expired
        """
        # First check cache with TTL validation (default 60 seconds)
        # This prevents stale error states from persisting
        cached = get_cached_cell_output(cell_number)
        if cached and cached.get("data"):
            # Extract just the data portion, not the metadata wrapper
            return cached.get("data")

        # Request fresh data from frontend
        result = get_cell_outputs([cell_number], timeout_s=timeout_s)
        if not result.get("success"):
            return None

        # Wait a bit for response to arrive and be cached
        time.sleep(0.1)

        # Check cache again and extract data
        cached = get_cached_cell_output(cell_number)
        if cached and cached.get("data"):
            return cached.get("data")
        return None

    def register_all(self):
        """Register all notebook tools."""
        self._register_list_variables()
        self._register_read_variable()
        self._register_read_active_cell()
        self._register_read_active_cell_output()
        self._register_read_content()
        self._register_move_cursor()
        self._register_server_status()

    def _register_list_variables(self):
        """Register the notebook/list_variables tool."""

        @self.mcp.tool(
            name="notebook_list_variables",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_variables(
            type_filter: Optional[str] = None,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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

    def _register_read_variable(self):
        """Register the notebook/read_variable tool."""

        @self.mcp.tool(
            name="notebook_read_variable",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_variable_info(
            name: str, detailed: bool = False
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            start = time.perf_counter()
            try:
                info = await self.tools.get_variable_info(name)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_read_variable",
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
                    "notebook_read_variable",
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

    def _register_read_active_cell(self):
        """Register the notebook/read_active_cell tool."""

        @self.mcp.tool(
            name="notebook_read_active_cell",
            annotations={
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
            # Description loaded from metadata_baseline.yaml
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
                log_tool_call("notebook_read_active_cell", args, duration, "success")

                # Apply mode filtering
                if detailed:
                    result = self._to_detailed_editing_cell(result)
                else:
                    result = self._to_concise_editing_cell(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_read_active_cell", args, duration, "error", str(e)
                )
                logger.error(f"Error in notebook/get_editing_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_read_active_cell_output(self):
        """Register the notebook/read_active_cell_output tool."""

        @self.mcp.tool(
            name="notebook_read_active_cell_output",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_editing_cell_output(detailed: bool = False) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml

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
                            "executed": False,
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
                            "executed": False,
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
                        "cell_id_notebook": cell_index,
                        "executed": True,
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
        # Description loaded from metadata_baseline.yaml
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

    def _register_read_content(self):
        """Register the notebook/read_content tool."""

        @self.mcp.tool(
            name="notebook_read_content",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_notebook_cells(
            num_cells: int = 2,
            include_output: bool = True,
            cell_id_notebooks: Optional[str] = None,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # NEW TWO-PHASE APPROACH: Uses frontend to access ALL cells including unexecuted ones
            try:
                import sys
                import traceback

                # Parse cell_id_notebooks if provided (JSON array of indices)
                specific_indices = None
                if cell_id_notebooks:
                    try:
                        parsed = json.loads(cell_id_notebooks)
                        if isinstance(parsed, list):
                            specific_indices = [int(i) for i in parsed]
                        elif isinstance(parsed, int):
                            specific_indices = [parsed]
                        else:
                            return [
                                TextContent(
                                    type="text",
                                    text=json.dumps(
                                        {
                                            "error": "cell_id_notebooks must be an integer or list of integers"
                                        },
                                        indent=2,
                                    ),
                                )
                            ]
                    except (json.JSONDecodeError, ValueError) as e:
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {"error": f"Invalid cell_id_notebooks format: {e}"},
                                    indent=2,
                                ),
                            )
                        ]

                # PHASE 1: Get notebook structure (lightweight - no source code)
                structure = get_notebook_structure(timeout_s=2.0)

                if not structure.get("success"):
                    # Frontend unavailable - check if position-based access was requested
                    if specific_indices is not None:
                        # Position-based access requires frontend - return explicit error
                        logger.warning(
                            f"Frontend unavailable: {structure.get('error')}. "
                            "Cannot use cell_id_notebooks without frontend."
                        )
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "error": "cell_id_notebooks requires JupyterLab frontend connection",
                                        "detail": "Position-based cell access is only available when the frontend bridge is connected. "
                                        "Use num_cells parameter instead, or ensure the JupyterLab extension is loaded.",
                                        "frontend_error": structure.get("error"),
                                    },
                                    indent=2,
                                ),
                            )
                        ]

                    # Fallback to IPython-based approach only for num_cells mode
                    logger.warning(
                        f"Frontend unavailable: {structure.get('error')}. "
                        "Falling back to IPython history."
                    )
                    return await self._get_cells_from_ipython(
                        num_cells, include_output, detailed
                    )

                total_cells = structure.get("total_cells", 0)
                structure_cells = structure.get("cells", [])

                if total_cells == 0:
                    result = {
                        "total_cells": 0,
                        "cells": [],
                        "count": 0,
                        "error_count": 0,
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2))]

                # PHASE 2: Determine which cells to fetch
                if specific_indices is not None:
                    # Fetch specific cells by index
                    indices_to_fetch = [
                        i for i in specific_indices if 0 <= i < total_cells
                    ]
                else:
                    # Fetch cells around the active cell (cursor position)
                    active_index = structure.get("active_cell_index", total_cells - 1)
                    half = num_cells // 2
                    start = max(0, active_index - half)
                    end = min(total_cells, start + num_cells)
                    # Adjust start if we hit the end boundary
                    if end == total_cells:
                        start = max(0, total_cells - num_cells)
                    indices_to_fetch = list(range(start, end))

                # Get cells with source code
                cells_result = get_cells_by_index(indices_to_fetch, timeout_s=2.0)

                if not cells_result.get("success"):
                    logger.warning(
                        f"Failed to get cells by index: {cells_result.get('error')}"
                    )
                    return await self._get_cells_from_ipython(
                        num_cells, include_output, detailed
                    )

                fetched_cells = cells_result.get("cells", [])

                # PHASE 3: Process cells and add outputs for executed cells
                cells = []
                for cell_data in fetched_cells:
                    # Use execution number internally to fetch outputs (not exposed in return)
                    exec_num = cell_data.get("cell_execution_number")

                    cell_info = {
                        "cell_id_notebook": cell_data.get("cell_id_notebook"),
                        "cell_type": cell_data.get("cell_type"),
                        "executed": exec_num is not None,
                        "source": cell_data.get("source", ""),
                        "has_output": False,
                        "has_error": False,
                    }

                    if include_output and exec_num is not None:
                        # Only fetch output for executed cells
                        try:
                            frontend_output = self._get_frontend_output(exec_num)
                            if frontend_output and self._is_valid_frontend_output(
                                frontend_output
                            ):
                                outputs = frontend_output.get("outputs", [])
                                has_output = frontend_output.get("has_output", False)

                                # Check for errors in outputs
                                has_error_output = any(
                                    out.get("type") == "error"
                                    or out.get("output_type") == "error"
                                    for out in outputs
                                )

                                cell_info["has_output"] = has_output
                                cell_info["has_error"] = has_error_output
                                cell_info["outputs"] = outputs

                                if has_error_output:
                                    cell_info["status"] = "error"
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
                                                "message": out.get("evalue", ""),
                                                "traceback": "\n".join(
                                                    out.get("traceback", [])
                                                ),
                                            }
                                            break
                                elif has_output:
                                    cell_info["status"] = "completed"
                                else:
                                    cell_info["status"] = "completed_no_output"
                            else:
                                # Fallback to IPython Out cache
                                Out = self.ipython.user_ns.get("Out", {})
                                if exec_num in Out:
                                    cell_info["output"] = str(Out[exec_num])
                                    cell_info["has_output"] = True
                                    cell_info["status"] = "completed"
                                else:
                                    cell_info["status"] = "completed_no_output"
                        except Exception as e:
                            logger.warning(
                                f"Error getting output for cell {exec_num}: {e}"
                            )
                            cell_info["status"] = "output_fetch_failed"
                    elif exec_num is None:
                        # Unexecuted cell (markdown or code that hasn't been run)
                        cell_info["status"] = "not_executed"
                    else:
                        cell_info["status"] = "completed_no_output"

                    cells.append(cell_info)

                # Count cells with errors
                error_count = sum(1 for cell in cells if cell.get("has_error", False))

                result = {
                    "total_cells": total_cells,
                    "cells": cells,
                    "count": len(cells),
                    "requested": len(indices_to_fetch),
                    "error_count": error_count,
                }

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_notebook_cells(result, include_output)

                return [TextContent(type="text", text=json.dumps(result, indent=2))]

            except Exception as e:
                logger.error(f"Error in get_notebook_cells: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    async def _get_cells_from_ipython(
        self, num_cells: int, include_output: bool, detailed: bool
    ) -> List[TextContent]:
        """Fallback method to get cells from IPython history when frontend unavailable."""
        import sys
        import traceback

        cells = []
        current_execution_count = getattr(self.ipython, "execution_count", 0)

        if hasattr(self.ipython, "user_ns"):
            In = self.ipython.user_ns.get("In", [])
            Out = self.ipython.user_ns.get("Out", {})

            if len(In) > 1:  # In[0] is empty
                start_idx = max(1, len(In) - num_cells)
                latest_executed = len(In) - 1

                for i in range(start_idx, len(In)):
                    if i < len(In) and In[i]:
                        cell_info = {
                            "cell_id_notebook": None,  # Unknown for IPython fallback
                            "cell_type": "code",  # IPython only tracks code cells
                            "executed": True,  # IPython In[] only contains executed cells
                            "source": In[i],
                            "has_error": False,
                        }

                        if include_output:
                            if i in Out:
                                cell_info["output"] = str(Out[i])
                                cell_info["has_output"] = True
                                cell_info["status"] = "completed"
                            elif i < current_execution_count:
                                cell_info["has_output"] = False
                                # Check sys.last_* for latest cell errors
                                if i == latest_executed:
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
                                        cell_info["status"] = "completed_no_output"
                                else:
                                    cell_info["status"] = "completed_no_output"
                            else:
                                cell_info["has_output"] = False
                                cell_info["status"] = "not_executed"
                        else:
                            cell_info["has_output"] = False

                        cells.append(cell_info)

        error_count = sum(1 for cell in cells if cell.get("has_error", False))

        result = {
            "total_cells": None,  # Unknown for IPython fallback
            "cells": cells,
            "count": len(cells),
            "requested": num_cells,
            "error_count": error_count,
            "note": "Using IPython fallback - only executed code cells shown",
        }

        if not detailed:
            result = self._to_concise_notebook_cells(result, include_output)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    def _register_move_cursor(self):
        """Register the notebook/move_cursor tool."""

        @self.mcp.tool(
            name="notebook_move_cursor",
            annotations={
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def move_cursor(target: str, detailed: bool = False) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def server_status(detailed: bool = False) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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
