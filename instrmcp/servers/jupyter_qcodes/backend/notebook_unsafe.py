"""
Notebook unsafe backend for cell modification and execution.

Handles all unsafe notebook operations including:
- Cell content modification
- Cell execution
- Cell creation and deletion
- Patch application
"""

import asyncio
import re
import time
import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from .base import BaseBackend, SharedState

if TYPE_CHECKING:
    from .notebook import NotebookBackend

logger = logging.getLogger(__name__)


class NotebookUnsafeBackend(BaseBackend):
    """Backend for unsafe notebook operations (modification and execution)."""

    def __init__(self, state: SharedState, notebook_backend: "NotebookBackend"):
        """Initialize notebook unsafe backend.

        Args:
            state: SharedState instance containing shared resources
            notebook_backend: NotebookBackend for accessing get_editing_cell
        """
        super().__init__(state)
        self.notebook = notebook_backend
        # Import active_cell_bridge lazily to avoid circular imports
        self._bridge = None

    @property
    def bridge(self):
        """Lazy import of active_cell_bridge."""
        if self._bridge is None:
            try:
                from .. import active_cell_bridge

                self._bridge = active_cell_bridge
            except ImportError:
                import active_cell_bridge

                self._bridge = active_cell_bridge
        return self._bridge

    async def update_editing_cell(self, content: str) -> Dict[str, Any]:
        """Update the content of the currently editing cell in JupyterLab frontend.

        This sends a request to the frontend to update the currently active cell
        with the provided content.

        Args:
            content: New Python code content to set in the active cell

        Returns:
            Dictionary with update status and response details
        """
        try:
            # Validate input
            if not isinstance(content, str):
                return {
                    "success": False,
                    "error": f"Content must be a string, got {type(content).__name__}",
                    "content": None,
                }

            # Send update request to frontend
            result = self.bridge.update_active_cell(content)

            # Add metadata
            result.update(
                {
                    "source": "update_editing_cell",
                    "content_preview": (
                        content[:100] + "..." if len(content) > 100 else content
                    ),
                    "bridge_status": self.bridge.get_bridge_status(),
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in update_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": content[:100] + "..." if len(content) > 100 else content,
                "source": "error",
            }

    async def _get_cell_output(
        self, cell_number: int, timeout_s: float = 0.5, bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Request and retrieve cell output from JupyterLab frontend.

        Args:
            cell_number: Execution count of the cell
            timeout_s: Timeout for waiting for response
            bypass_cache: If True, skip cache and always request fresh from frontend.
                         Use this for final fetch to ensure late outputs are captured.

        Returns:
            Dictionary with output data or None if not available
        """
        # First check cache (unless bypassing)
        # Note: get_cached_cell_output now returns a wrapper dict with "data" key
        if not bypass_cache:
            cached = self.bridge.get_cached_cell_output(cell_number)
            if cached and cached.get("data"):
                return cached.get("data")

        # Request from frontend
        result = self.bridge.get_cell_outputs([cell_number], timeout_s=timeout_s)
        if not result.get("success"):
            return None

        # Wait a bit for response to arrive and be cached (non-blocking)
        await asyncio.sleep(0.1)

        # Check cache again and extract data from wrapper
        cached = self.bridge.get_cached_cell_output(cell_number)
        if cached and cached.get("data"):
            return cached.get("data")
        return None

    def _process_frontend_output(
        self,
        frontend_output: Optional[Dict[str, Any]],
        target_count: int,
        cell_input: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Process frontend output and return result dict if error or output found.

        Args:
            frontend_output: Output from frontend (may be None)
            target_count: Cell execution count
            cell_input: Cell source code

        Returns:
            Result dict if error or output found, None otherwise
        """
        if not frontend_output:
            return None

        outputs = frontend_output.get("outputs", [])

        # Check if outputs contain an error (Jupyter output type, not sweep state)
        for output in outputs:
            if output.get("type") == "error":
                return {
                    "status": "error",
                    "has_error": True,
                    "has_output": True,
                    "cell_number": target_count,
                    "input": cell_input,
                    "error_type": output.get("ename", "Unknown"),
                    "error_message": output.get("evalue", ""),
                    "traceback": "\n".join(output.get("traceback", [])),
                    "outputs": outputs,
                }

        # Check if outputs contain data
        if frontend_output.get("has_output"):
            return {
                "status": "completed",
                "has_error": False,
                "has_output": True,
                "cell_number": target_count,
                "input": cell_input,
                "outputs": outputs,
            }

        return None

    async def _wait_for_execution(
        self, initial_count: int, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Wait for cell execution to complete (simplified - no output retrieval).

        Two-phase approach:
        1. Wait for execution_count to increase (execution started)
        2. Wait for last_execution_result to change (execution completed)

        The primary completion signal is `last_execution_result` identity change,
        which is set at the END of IPython's run_cell. This handles all cells
        including long-running silent ones (e.g., `time.sleep(10); x = 1`).

        IMPORTANT: This method only waits for completion and detects errors.
        Output retrieval is done separately by the caller using
        active_cell_bridge.get_active_cell_output() for consistency with
        notebook_get_editing_cell_output.

        Args:
            initial_count: The execution_count before triggering execution
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            Dictionary with execution status (no output fields - caller fetches output)
        """
        import sys
        import traceback as tb_module

        start_time = time.time()
        poll_interval = 0.1  # 100ms

        # Capture initial state for identity comparison
        initial_last_traceback = getattr(sys, "last_traceback", None)
        initial_last_result = getattr(self.ipython, "last_execution_result", None)

        target_count = None

        while (time.time() - start_time) < timeout:
            current_count = getattr(self.ipython, "execution_count", 0)

            # Phase 1: Wait for execution to START
            if target_count is None:
                if current_count > initial_count:
                    target_count = current_count
                    # Execution started - continue to phase 2
                else:
                    await asyncio.sleep(poll_interval)
                    continue

            # Phase 2: Wait for execution to COMPLETE
            In = self.ipython.user_ns.get("In", [])
            cell_input = In[target_count] if target_count < len(In) else ""

            # Check 1: Error detected (compare traceback object identity, not type)
            current_last_traceback = getattr(sys, "last_traceback", None)
            if (
                current_last_traceback is not None
                and current_last_traceback is not initial_last_traceback
            ):
                # New error occurred - return immediately with error info
                error_type = getattr(sys, "last_type", None)
                return {
                    "status": "error",
                    "has_error": True,
                    "cell_number": target_count,
                    "input": cell_input,
                    "error_type": error_type.__name__ if error_type else "Unknown",
                    "error_message": str(getattr(sys, "last_value", "")),
                    "traceback": "".join(tb_module.format_tb(current_last_traceback)),
                }

            # Check 2: last_execution_result changed (primary completion signal)
            current_last_result = getattr(self.ipython, "last_execution_result", None)
            execution_completed = (
                current_last_result is not None
                and current_last_result is not initial_last_result
            )

            if execution_completed:
                # Execution completed successfully - return without output
                # (caller will fetch output using get_active_cell_output)
                return {
                    "status": "completed",
                    "has_error": False,
                    "cell_number": target_count,
                    "input": cell_input,
                }

            # Check 3: Execution count advanced beyond target (another cell ran)
            fresh_count = getattr(self.ipython, "execution_count", 0)
            if fresh_count > target_count:
                return {
                    "status": "completed",
                    "has_error": False,
                    "cell_number": target_count,
                    "input": cell_input,
                }

            await asyncio.sleep(poll_interval)

        # Timeout
        return {
            "status": "timeout",
            "has_error": False,
            "has_output": False,
            "cell_number": target_count or 0,
            "message": f"Timeout after {timeout}s waiting for execution to complete",
        }

    async def execute_editing_cell(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Execute the currently editing cell and wait for output.

        UNSAFE: This tool executes code in the active notebook cell. The code will run
        in the frontend with output appearing in the notebook.

        Output retrieval uses the same robust logic as notebook_get_editing_cell_output
        via active_cell_bridge.get_active_cell_output().

        Args:
            timeout: Maximum seconds to wait for execution to complete (default: 30)

        Returns:
            Dictionary with execution status AND output/error details
        """
        try:
            # 1. Capture current execution count and cell text from bridge
            initial_count = getattr(self.ipython, "execution_count", 0)
            # Get cell text from bridge snapshot BEFORE execution (most reliable)
            bridge_snapshot = self.bridge.get_active_cell()
            cell_text_from_bridge = (
                bridge_snapshot.get("text", "") if bridge_snapshot else ""
            )

            # 2. Send execution request to frontend
            exec_result = self.bridge.execute_active_cell()

            if not exec_result.get("success"):
                exec_result.update(
                    {
                        "source": "execute_editing_cell",
                        "warning": "UNSAFE: Attempted to execute code but request failed",
                    }
                )
                return exec_result

            # 3. Wait for execution to complete (simplified - no output polling)
            wait_result = await self._wait_for_execution(initial_count, timeout)

            # 4. Handle timeout
            if wait_result.get("status") == "timeout":
                return {
                    "success": True,
                    "executed": True,
                    "execution_count": 0,
                    **wait_result,
                    "source": "execute_editing_cell",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: Code was executed in the active cell",
                }

            # 5. Handle errors detected during wait
            if wait_result.get("has_error"):
                return {
                    "success": True,
                    "executed": True,
                    "execution_count": wait_result.get("cell_number", 0),
                    **wait_result,
                    "has_output": False,
                    "source": "execute_editing_cell",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: Code was executed in the active cell",
                }

            # 6. Fetch output using shared logic from get_active_cell_output
            # This is the same path used by notebook_get_editing_cell_output
            output_result = self.bridge.get_active_cell_output(timeout_s=2.0)

            # 7. Build combined result
            combined_result = {
                "success": True,
                "executed": True,
                "execution_count": wait_result.get("cell_number", 0),
                "status": wait_result.get("status", "completed"),
                "cell_number": wait_result.get("cell_number", 0),
                "input": wait_result.get("input", ""),
                "has_error": False,
                "source": "execute_editing_cell",
                "bridge_status": self.bridge.get_bridge_status(),
                "warning": "UNSAFE: Code was executed in the active cell",
            }

            # 8. Merge output data from get_active_cell_output
            if output_result.get("success"):
                outputs = output_result.get("outputs", [])
                has_output = output_result.get("has_output", False)
                has_error = output_result.get("has_error", False)

                combined_result["has_output"] = has_output
                combined_result["outputs"] = outputs

                # Check for errors in frontend output (may have been missed by sys.last_*)
                if has_error:
                    combined_result["has_error"] = True
                    combined_result["status"] = "error"
                    # Extract error details from outputs (Jupyter output type)
                    for out in outputs:
                        if out.get("type") == "error":
                            combined_result["error_type"] = out.get(
                                "ename", "UnknownError"
                            )
                            combined_result["error_message"] = out.get("evalue", "")
                            combined_result["traceback"] = "\n".join(
                                out.get("traceback", [])
                            )
                            break
            else:
                # Frontend fetch failed - check IPython Out cache as fallback
                Out = self.ipython.user_ns.get("Out", {})
                cell_num = wait_result.get("cell_number", 0)
                if cell_num in Out:
                    combined_result["has_output"] = True
                    combined_result["output"] = str(Out[cell_num])
                else:
                    combined_result["has_output"] = False
                    combined_result["message"] = "Cell executed (output fetch failed)"

            # 9. Detect if a MeasureIt sweep was started and extract sweep names
            # Use bridge text (captured before execution) as fallback if IPython In[] is empty
            cell_input = wait_result.get("input", "") or cell_text_from_bridge
            sweep_pattern = r"(\w+)\.start\s*\("
            sweep_matches = re.findall(sweep_pattern, cell_input)

            if sweep_matches:
                combined_result["sweep_detected"] = True
                combined_result["sweep_names"] = sweep_matches
                if len(sweep_matches) == 1:
                    combined_result["suggestion"] = (
                        f"A sweep appears to have been started. "
                        f"Use measureit_wait_for_sweep with sweep name "
                        f"'{sweep_matches[0]}' to wait for completion."
                    )
                else:
                    names = ", ".join(f"'{n}'" for n in sweep_matches)
                    combined_result["suggestion"] = (
                        f"Multiple sweeps appear to have been started ({names}). "
                        f"Use measureit_wait_for_sweep(timeout=..., variable_name=name) or "
                        f"measureit_wait_for_sweep(timeout=..., all=True) to wait for completion."
                    )

            return combined_result

        except Exception as e:
            logger.error(f"Error in execute_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to execute code but failed",
            }

    async def add_new_cell(
        self,
        cell_type: str = "code",
        position: str = "below",
        content: str = "",
        timeout_s: float = 2.0,
    ) -> Dict[str, Any]:
        """Add a new cell in the notebook.

        UNSAFE: This tool adds new cells to the notebook. The cell will be created
        relative to the currently active cell.

        Args:
            cell_type: Type of cell to create ("code", "markdown", "raw")
            position: Position relative to active cell ("above", "below", "end")
            content: Initial content for the new cell
            timeout_s: How long to wait for frontend response (default 2.0s)

        Returns:
            Dictionary with creation status and response details
        """
        try:
            # Send add cell request to frontend
            result = self.bridge.add_new_cell(
                cell_type, position, content, timeout_s=timeout_s
            )

            # Add metadata
            result.update(
                {
                    "source": "add_new_cell",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: New cell was added to the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in add_new_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to add cell but failed",
            }

    async def delete_editing_cell(self) -> Dict[str, Any]:
        """Delete the currently editing cell.

        UNSAFE: This tool deletes the currently active cell from the notebook.
        Use with caution as this action cannot be undone easily.

        Returns:
            Dictionary with deletion status and response details
        """
        try:
            # Send delete cell request to frontend
            result = self.bridge.delete_editing_cell()

            # Add metadata
            result.update(
                {
                    "source": "delete_editing_cell",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cell was deleted from the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in delete_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to delete cell but failed",
            }

    async def apply_patch(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """Apply a patch to the current cell content.

        UNSAFE: This tool modifies the content of the currently active cell by
        replacing the first occurrence of old_text with new_text.

        Args:
            old_text: Text to find and replace
            new_text: Text to replace with

        Returns:
            Dictionary with patch status and response details
        """
        try:
            # Send patch request to frontend
            result = self.bridge.apply_patch(old_text, new_text)

            # Add metadata
            result.update(
                {
                    "source": "apply_patch",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cell content was modified via patch",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in apply_patch: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to apply patch but failed",
            }

    async def delete_cells_by_number(self, cell_numbers: List[int]) -> Dict[str, Any]:
        """Delete multiple cells by their execution count numbers.

        UNSAFE: This tool deletes cells from the notebook by their execution count.
        Use with caution as this action cannot be undone easily.

        Args:
            cell_numbers: List of execution count numbers (e.g., [1, 2, 5])

        Returns:
            Dictionary with deletion status and detailed results for each cell
        """
        try:
            # Send delete cells by number request to frontend
            result = self.bridge.delete_cells_by_number(cell_numbers)

            # Add metadata
            result.update(
                {
                    "source": "delete_cells_by_number",
                    "bridge_status": self.bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cells were deleted from the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in delete_cells_by_number: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "cell_numbers_requested": cell_numbers,
                "warning": "UNSAFE: Attempted to delete cells but failed",
            }
