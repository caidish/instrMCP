"""
Unified notebook meta-tool registrar.

Consolidates 13 notebook tools into a single meta-tool to reduce
context window overhead while preserving all functionality.
"""

import json
import sys
import time
import traceback
from typing import List, Optional, Dict, Any, Set

from mcp.types import TextContent
from ..active_cell_bridge import get_cell_outputs, get_cached_cell_output
from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call

logger = get_logger("tools.notebook")


class NotebookMetaToolRegistrar:
    """Registers unified notebook meta-tool with the MCP server."""

    # Safe actions (available in all modes)
    SAFE_ACTIONS: Set[str] = {
        "list_variables",
        "get_variable_info",
        "get_editing_cell",
        "get_editing_cell_output",
        "get_notebook_cells",
        "move_cursor",
        "server_status",
    }

    # Unsafe actions (require unsafe mode)
    UNSAFE_ACTIONS: Set[str] = {
        "update_editing_cell",
        "execute_cell",
        "add_cell",
        "delete_cell",
        "delete_cells",
        "apply_patch",
    }

    # Actions requiring user consent (subset of unsafe)
    CONSENT_REQUIRED: Set[str] = {
        "update_editing_cell",
        "execute_cell",
        "delete_cell",
        "delete_cells",
        "apply_patch",
    }

    # Action -> (required_params, optional_params_with_defaults)
    ACTION_PARAMS: Dict[str, tuple] = {
        "list_variables": ([], {"type_filter": None}),
        "get_variable_info": (["name"], {}),
        "get_editing_cell": (
            [],
            {"fresh_ms": 1000, "line_start": None, "line_end": None, "max_lines": 200},
        ),
        "get_editing_cell_output": ([], {}),
        "get_notebook_cells": ([], {"num_cells": 2, "include_output": True}),
        "move_cursor": (["target"], {}),
        "server_status": ([], {}),
        "update_editing_cell": (["content"], {}),
        "execute_cell": ([], {}),
        "add_cell": ([], {"cell_type": "code", "position": "below", "content": ""}),
        "delete_cell": ([], {}),
        "delete_cells": (["cell_numbers"], {}),
        "apply_patch": (["old_text", "new_text"], {}),
    }

    # Action -> usage example for error messages
    ACTION_USAGE: Dict[str, str] = {
        "list_variables": 'notebook(action="list_variables") or notebook(action="list_variables", type_filter="array")',
        "get_variable_info": 'notebook(action="get_variable_info", name="my_var")',
        "get_editing_cell": 'notebook(action="get_editing_cell") or notebook(action="get_editing_cell", line_start=1, line_end=50)',
        "get_editing_cell_output": 'notebook(action="get_editing_cell_output")',
        "get_notebook_cells": 'notebook(action="get_notebook_cells") or notebook(action="get_notebook_cells", num_cells=5)',
        "move_cursor": 'notebook(action="move_cursor", target="below") where target is "above", "below", "bottom", or cell number',
        "server_status": 'notebook(action="server_status")',
        "update_editing_cell": 'notebook(action="update_editing_cell", content="x = 42\\nprint(x)")',
        "execute_cell": 'notebook(action="execute_cell")',
        "add_cell": 'notebook(action="add_cell") or notebook(action="add_cell", cell_type="markdown", position="above", content="# Header")',
        "delete_cell": 'notebook(action="delete_cell")',
        "delete_cells": 'notebook(action="delete_cells", cell_numbers="[1, 2, 5]") - JSON array of cell indices',
        "apply_patch": 'notebook(action="apply_patch", old_text="x = 10", new_text="x = 20")',
    }

    def __init__(
        self,
        mcp_server,
        tools,
        ipython,
        safe_mode: bool = True,
        dangerous_mode: bool = False,
        consent_manager=None,
    ):
        """
        Initialize the notebook meta-tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            ipython: IPython instance for direct notebook access
            safe_mode: Whether server is in safe mode (read-only)
            dangerous_mode: Whether server is in dangerous mode (auto-approve consents)
            consent_manager: Required ConsentManager when safe_mode=False

        Raises:
            ValueError: If safe_mode=False and consent_manager is None (security violation)
        """
        # Defense-in-depth: Prevent consent bypass via misconfiguration
        # When not in safe mode, consent_manager MUST be provided to ensure
        # unsafe actions (execute_cell, delete_cell, etc.) require user approval
        if not safe_mode and consent_manager is None:
            raise ValueError(
                "consent_manager is required when safe_mode=False. "
                "Unsafe mode without consent would bypass all safety checks."
            )

        self.mcp = mcp_server
        self.tools = tools
        self.ipython = ipython
        self.safe_mode = safe_mode
        self.dangerous_mode = dangerous_mode
        self.consent_manager = consent_manager

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
        cached = get_cached_cell_output(cell_number)
        if cached:
            return cached

        result = get_cell_outputs([cell_number], timeout_s=timeout_s)
        if not result.get("success"):
            return None

        time.sleep(0.1)
        return get_cached_cell_output(cell_number)

    def register_all(self):
        """Register the unified notebook meta-tool."""
        self._register_notebook_tool()

    def _register_notebook_tool(self):
        @self.mcp.tool(name="notebook")
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
        ) -> List[TextContent]:
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
            return await self._handle_action(
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

    async def _handle_action(self, action: str, **kwargs) -> List[TextContent]:
        """Route and execute the requested action."""
        start = time.perf_counter()

        # Sanitize action: strip quotes that LLMs sometimes add
        # e.g., '"get_notebook_cells"' → 'get_notebook_cells'
        if action:
            action = action.strip("\"'")

        # 1. Validate action exists
        all_actions = self.SAFE_ACTIONS | self.UNSAFE_ACTIONS
        if action not in all_actions:
            return self._error_response(
                f"Unknown action: '{action}'",
                valid_actions=sorted(all_actions),
                hint="Use one of the valid actions listed above",
            )

        # 2. Check safe mode restrictions
        if self.safe_mode and action in self.UNSAFE_ACTIONS:
            return self._error_response(
                f"Action '{action}' requires unsafe mode",
                action=action,
                safe_mode=True,
                hint="Use %mcp_unsafe to enable unsafe mode, then restart server",
            )

        # 3. Validate required parameters
        required, defaults = self.ACTION_PARAMS[action]
        missing = [p for p in required if kwargs.get(p) is None]
        if missing:
            return self._error_response(
                f"Missing required parameter(s) for action '{action}'",
                action=action,
                missing=missing,
                required=required,
                usage=self.ACTION_USAGE.get(action, ""),
            )

        # 4. Special validation for cell_numbers (must be valid JSON)
        if action == "delete_cells":
            validation_result = self._validate_cell_numbers(kwargs.get("cell_numbers"))
            if validation_result is not None:
                return validation_result

        # 5. Handle consent if required
        if action in self.CONSENT_REQUIRED and self.consent_manager:
            consent_result = await self._request_consent(action, kwargs)
            if consent_result is not None:
                return consent_result  # Returns error response if declined

        # 6. Execute the action
        try:
            result = await self._execute_action(action, kwargs)
            duration = (time.perf_counter() - start) * 1000
            log_tool_call(f"notebook.{action}", kwargs, duration, "success")
            return [
                TextContent(type="text", text=json.dumps(result, indent=2, default=str))
            ]
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            log_tool_call(f"notebook.{action}", kwargs, duration, "error", str(e))
            logger.error(f"Error in notebook/{action}: {e}")
            return self._error_response(str(e), action=action)

    def _validate_cell_numbers(self, cell_numbers: str) -> Optional[List[TextContent]]:
        """Validate cell_numbers JSON format. Returns error response or None if valid."""
        usage = self.ACTION_USAGE.get("delete_cells", "")
        try:
            parsed = json.loads(cell_numbers)
            if isinstance(parsed, int):
                return None  # Valid single number
            elif isinstance(parsed, list):
                if all(isinstance(x, int) for x in parsed):
                    return None  # Valid list of numbers
                return self._error_response(
                    "cell_numbers list must contain only integers",
                    action="delete_cells",
                    provided=cell_numbers,
                    usage=usage,
                )
            else:
                return self._error_response(
                    "cell_numbers must be an integer or list of integers",
                    action="delete_cells",
                    provided=cell_numbers,
                    usage=usage,
                )
        except json.JSONDecodeError as e:
            return self._error_response(
                f"Invalid JSON format for cell_numbers: {e}",
                action="delete_cells",
                provided=cell_numbers,
                usage=usage,
            )

    async def _request_consent(
        self, action: str, kwargs: dict
    ) -> Optional[List[TextContent]]:
        """Request consent for unsafe actions. Returns error response if declined, None if approved."""
        try:
            # Get current cell content for context
            cell_info = await self.tools.get_editing_cell()
            cell_content = cell_info.get("text", "")
            cell_type = cell_info.get("cell_type", "code")
            cell_index = cell_info.get("index", "unknown")

            # Build consent details based on action
            if action == "update_editing_cell":
                details = {
                    "old_content": cell_content,
                    "new_content": kwargs.get("content", ""),
                    "description": f"Replace cell content ({len(cell_content)} chars -> {len(kwargs.get('content', ''))} chars)",
                    "cell_type": cell_type,
                    "cell_index": cell_index,
                }
                operation = "update_cell"
            elif action == "execute_cell":
                details = {
                    "source_code": cell_content,
                    "description": "Execute code in the currently active Jupyter notebook cell",
                    "cell_type": cell_type,
                }
                operation = "execute_cell"
            elif action == "delete_cell":
                details = {
                    "source_code": cell_content,
                    "description": "Delete the currently active Jupyter notebook cell",
                    "cell_type": cell_type,
                    "cell_index": cell_index,
                }
                operation = "delete_cell"
            elif action == "delete_cells":
                parsed = json.loads(kwargs.get("cell_numbers", "[]"))
                cell_list = [parsed] if isinstance(parsed, int) else parsed
                details = {
                    "description": f"Delete {len(cell_list)} cell(s) from notebook",
                    "cell_numbers": cell_list,
                    "count": len(cell_list),
                }
                operation = "delete_cells"
            elif action == "apply_patch":
                details = {
                    "old_text": kwargs.get("old_text"),
                    "new_text": kwargs.get("new_text"),
                    "cell_content": cell_content,
                    "description": f"Apply patch: replace {len(kwargs.get('old_text', ''))} chars with {len(kwargs.get('new_text', ''))} chars",
                    "cell_type": cell_type,
                    "cell_index": cell_index,
                }
                operation = "apply_patch"
            else:
                return None  # No consent needed

            consent_result = await self.consent_manager.request_consent(
                operation=operation,
                tool_name=f"notebook.{action}",
                author="MCP Server",
                details=details,
            )

            if not consent_result["approved"]:
                reason = consent_result.get("reason", "User declined")
                logger.warning(f"Action '{action}' declined - {reason}")
                return self._error_response(
                    f"{action.replace('_', ' ').title()} declined: {reason}",
                    action=action,
                    consent_declined=True,
                )
            else:
                logger.debug(f"Action '{action}' approved")
                if consent_result.get("reason") != "bypass_mode":
                    action_display = action.replace("_", " ")
                    print(f"Consent granted for {action_display}")
                return None  # Approved, continue

        except TimeoutError:
            logger.error(f"Consent request timed out for {action}")
            return self._error_response(
                "Consent request timed out",
                action=action,
            )

    async def _execute_action(self, action: str, kwargs: dict) -> dict:
        """Execute the backend method for an action."""
        if action == "list_variables":
            return await self.tools.list_variables(kwargs.get("type_filter"))

        elif action == "get_variable_info":
            return await self.tools.get_variable_info(kwargs["name"])

        elif action == "get_editing_cell":
            return await self.tools.get_editing_cell(
                fresh_ms=kwargs.get("fresh_ms", 1000),
                line_start=kwargs.get("line_start"),
                line_end=kwargs.get("line_end"),
                max_lines=kwargs.get("max_lines", 200),
            )

        elif action == "get_editing_cell_output":
            return await self._handle_get_editing_cell_output()

        elif action == "get_notebook_cells":
            return await self._handle_get_notebook_cells(
                kwargs.get("num_cells", 2),
                kwargs.get("include_output", True),
            )

        elif action == "move_cursor":
            return await self.tools.move_cursor(kwargs["target"])

        elif action == "server_status":
            return self._handle_server_status()

        elif action == "update_editing_cell":
            return await self.tools.update_editing_cell(kwargs["content"])

        elif action == "execute_cell":
            return await self.tools.execute_editing_cell()

        elif action == "add_cell":
            return await self.tools.add_new_cell(
                kwargs.get("cell_type", "code"),
                kwargs.get("position", "below"),
                kwargs.get("content", ""),
            )

        elif action == "delete_cell":
            return await self.tools.delete_editing_cell()

        elif action == "delete_cells":
            parsed = json.loads(kwargs["cell_numbers"])
            cell_list = [parsed] if isinstance(parsed, int) else parsed
            return await self.tools.delete_cells_by_number(cell_list)

        elif action == "apply_patch":
            return await self.tools.apply_patch(kwargs["old_text"], kwargs["new_text"])

        else:
            raise ValueError(f"Unknown action: {action}")

    async def _handle_get_editing_cell_output(self) -> dict:
        """Handle get_editing_cell_output action with full IPython integration."""
        if hasattr(self.ipython, "user_ns"):
            In = self.ipython.user_ns.get("In", [])
            Out = self.ipython.user_ns.get("Out", {})
            current_execution_count = getattr(self.ipython, "execution_count", 0)

            if len(In) > 1:
                latest_cell_num = len(In) - 1

                # Check if the latest cell is currently running
                if (
                    latest_cell_num not in Out
                    and latest_cell_num == current_execution_count
                    and In[latest_cell_num]
                ):
                    return {
                        "cell_number": latest_cell_num,
                        "execution_count": latest_cell_num,
                        "input": In[latest_cell_num],
                        "status": "running",
                        "message": "Cell is currently executing - no output available yet",
                        "has_output": False,
                        "has_error": False,
                        "output": None,
                    }

                # Find the most recent completed cell
                for i in range(len(In) - 1, 0, -1):
                    if In[i]:
                        # Try frontend output first
                        try:
                            frontend_output = self._get_frontend_output(i)
                            if frontend_output and frontend_output.get("has_output"):
                                return {
                                    "cell_number": i,
                                    "execution_count": i,
                                    "input": In[i],
                                    "status": "completed",
                                    "outputs": frontend_output.get("outputs", []),
                                    "has_output": True,
                                    "has_error": False,
                                }
                        except Exception as e:
                            logger.warning(
                                f"Error extracting frontend output for cell {i}: {e}"
                            )

                        # Check Out dictionary
                        if i in Out:
                            return {
                                "cell_number": i,
                                "execution_count": i,
                                "input": In[i],
                                "status": "completed",
                                "output": str(Out[i]),
                                "has_output": True,
                                "has_error": False,
                            }
                        elif i < current_execution_count:
                            # Check for error
                            has_error = False
                            error_info = None

                            if (
                                hasattr(sys, "last_type")
                                and hasattr(sys, "last_value")
                                and hasattr(sys, "last_traceback")
                                and sys.last_type is not None
                            ):
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
                                return {
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
                                return {
                                    "cell_number": i,
                                    "execution_count": i,
                                    "input": In[i],
                                    "status": "completed_no_output",
                                    "message": "Cell executed successfully but produced no output",
                                    "output": None,
                                    "has_output": False,
                                    "has_error": False,
                                }

        return {
            "status": "no_cells",
            "error": "No recently executed cells found",
            "message": "Execute a cell first to see its output",
            "has_output": False,
            "has_error": False,
        }

    async def _handle_get_notebook_cells(
        self, num_cells: int, include_output: bool
    ) -> dict:
        """Handle get_notebook_cells action with full IPython integration."""
        cells = []
        current_execution_count = getattr(self.ipython, "execution_count", 0)

        # Track last error info
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

        if hasattr(self.ipython, "user_ns"):
            In = self.ipython.user_ns.get("In", [])
            Out = self.ipython.user_ns.get("Out", {})

            if len(In) > 1:
                start_idx = max(1, len(In) - num_cells)
                latest_executed = len(In) - 1

                if (
                    last_error_info
                    and latest_executed not in Out
                    and latest_executed < current_execution_count
                ):
                    latest_cell_with_error = latest_executed

                for i in range(start_idx, len(In)):
                    if i < len(In) and In[i]:
                        cell_info = {
                            "cell_number": i,
                            "execution_count": i,
                            "input": In[i],
                            "has_error": False,
                        }

                        if include_output:
                            # Try frontend output
                            try:
                                frontend_output = self._get_frontend_output(i)
                                if frontend_output and frontend_output.get(
                                    "has_output"
                                ):
                                    cell_info["outputs"] = frontend_output.get(
                                        "outputs", []
                                    )
                                    cell_info["has_output"] = True
                                    cells.append(cell_info)
                                    continue
                            except Exception as e:
                                logger.warning(
                                    f"Error getting frontend output for cell {i}: {e}"
                                )

                            if i in Out:
                                cell_info["output"] = str(Out[i])
                                cell_info["has_output"] = True
                            elif i == latest_cell_with_error and last_error_info:
                                cell_info["has_output"] = False
                                cell_info["has_error"] = True
                                cell_info["error"] = last_error_info
                                cell_info["status"] = "error"
                            elif i < current_execution_count:
                                cell_info["has_output"] = False
                                cell_info["status"] = "completed_no_output"
                            else:
                                cell_info["has_output"] = False
                                cell_info["status"] = "not_executed"
                        else:
                            cell_info["has_output"] = False

                        cells.append(cell_info)

        # Fallback to history_manager
        if not cells and hasattr(self.ipython, "history_manager"):
            try:
                current_count = getattr(self.ipython, "execution_count", 1)
                start_line = max(1, current_count - num_cells)

                history = list(
                    self.ipython.history_manager.get_range(
                        session=0,
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
                                "output": str(output_text) if output_text else None,
                                "has_output": output_text is not None,
                                "has_error": False,
                            }
                        )
                    else:
                        cells.append(
                            {
                                "cell_number": line_num,
                                "execution_count": line_num,
                                "input": content,
                                "has_output": False,
                                "has_error": False,
                            }
                        )
            except Exception as hist_error:
                logger.warning(f"History manager fallback failed: {hist_error}")

        error_count = sum(1 for cell in cells if cell.get("has_error", False))

        return {
            "cells": cells,
            "count": len(cells),
            "requested": num_cells,
            "error_count": error_count,
            "note": "Only the most recent error can be captured. Older errors are not available.",
        }

    def _handle_server_status(self) -> dict:
        """Handle server_status action."""
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

        return {
            "status": "running",
            "mode": mode,
            "tools_count": len(registered_tools),
            "tools": registered_tools[:20],
        }

    def _error_response(self, message: str, **extra) -> List[TextContent]:
        """Generate consistent error response."""
        error = {"error": message, "success": False}
        error.update(extra)
        return [TextContent(type="text", text=json.dumps(error, indent=2))]
