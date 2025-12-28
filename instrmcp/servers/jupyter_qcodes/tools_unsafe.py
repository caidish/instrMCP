"""
Unsafe mode tools for Jupyter MCP server.

These tools allow cell manipulation and code execution in Jupyter notebooks.
They are only available when the server is running in unsafe mode.
"""

import json
import time
from typing import List

from mcp.types import TextContent

from instrmcp.logging_config import get_logger
from .tool_logger import log_tool_call

logger = get_logger("tools.unsafe")


class UnsafeToolRegistrar:
    """Registers unsafe mode tools with the MCP server."""

    def __init__(self, mcp_server, tools, consent_manager=None):
        """
        Initialize the unsafe tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            consent_manager: Optional ConsentManager for execute_cell consent
        """
        self.mcp = mcp_server
        self.tools = tools
        self.consent_manager = consent_manager

    # ===== Concise mode helpers =====

    def _to_concise_update_cell(self, result: dict) -> dict:
        """Convert full update cell result to concise format.

        Concise: success, message.
        """
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
        }

    def _to_concise_execute_cell(self, result: dict) -> dict:
        """Convert full execute cell result to concise format.

        Concise: signal_success, status, execution_count, outputs, error info if error.
        Also renames 'success' to 'signal_success' to clarify it indicates the signal was sent,
        not that the cell code executed without error.

        Bug fixes applied:
        - Bug #4: Always include has_output and outputs (not just output_summary)
        - Bug #5: Handle all three error patterns (direct fields, nested dict, string)
        """
        concise = {
            "signal_success": result.get("success", False),
            "status": result.get("status"),
            "execution_count": result.get("execution_count"),
        }

        # Bug #5 Fix: Include error info if present - handle all three patterns
        # Also handle edge case where has_error is not set but error exists (e.g., bridge failure)
        has_error = result.get("has_error")
        has_error_info = (
            result.get("error_type")
            or result.get("error")
            or (result.get("success") is False and result.get("status") == "error")
        )

        if has_error or has_error_info:
            concise["has_error"] = True

            # Pattern 1 & 2: Direct fields from _process_frontend_output / _wait_for_execution
            if result.get("error_type"):
                concise["error_type"] = result.get("error_type")
                concise["error_message"] = result.get("error_message")
                if result.get("traceback"):
                    concise["traceback"] = result.get("traceback")
            # Pattern 3: Nested dict (future-proofing) or simple string from exception handler
            elif result.get("error"):
                error_info = result.get("error")
                if isinstance(error_info, dict):
                    concise["error_type"] = error_info.get("type")
                    concise["error_message"] = error_info.get("message")
                else:
                    concise["error_message"] = str(error_info)

        # Bug #4 Fix: Always include has_output and outputs, not just summary
        concise["has_output"] = result.get("has_output", False)
        if "outputs" in result:
            concise["outputs"] = result.get("outputs", [])
        if "output" in result:
            concise["output"] = result.get("output")

        # Also include summary for convenience (truncated to 200 chars)
        outputs = result.get("outputs", [])
        if outputs:
            first_output = outputs[0] if isinstance(outputs, list) else outputs
            if isinstance(first_output, dict):
                text = first_output.get("text", "")
                if len(text) > 200:
                    text = text[:200] + "..."
                concise["output_summary"] = text
            else:
                concise["output_summary"] = str(first_output)[:200]
        elif result.get("output"):
            output = str(result.get("output"))
            if len(output) > 200:
                output = output[:200] + "..."
            concise["output_summary"] = output

        # Preserve sweep detection fields
        if result.get("sweep_detected"):
            concise["sweep_detected"] = True
            concise["sweep_names"] = result.get("sweep_names", [])
            concise["suggestion"] = result.get("suggestion")

        return concise

    def _to_concise_success_only(self, result: dict) -> dict:
        """Convert to concise format with just success.

        Used by: add_cell, delete_cell, delete_cells, apply_patch.
        """
        return {"success": result.get("success", False)}

    # ===== End concise mode helpers =====

    def register_all(self):
        """Register all unsafe mode tools."""
        self._register_update_editing_cell()
        self._register_execute_cell()
        self._register_add_cell()
        self._register_delete_cell()
        self._register_delete_cells()
        self._register_apply_patch()

    def _register_update_editing_cell(self):
        """Register the notebook/update_editing_cell tool."""

        @self.mcp.tool(
            name="notebook_update_editing_cell",
            annotations={
                "title": "Update Active Cell",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def update_editing_cell(
            content: str, detailed: bool = False
        ) -> List[TextContent]:
            """Update the content of the currently editing cell in JupyterLab frontend.

            UNSAFE: This tool modifies the content of the currently active cell.
            Only available in unsafe mode. The content will replace the entire
            current cell content.

            Args:
                content: New Python code content to set in the active cell
                detailed: If False (default), return concise summary; if True, return full info
            """
            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content to show what will be replaced
                    cell_info = await self.tools.get_editing_cell()
                    old_content = cell_info.get("text", "")

                    consent_result = await self.consent_manager.request_consent(
                        operation="update_cell",
                        tool_name="notebook_update_editing_cell",
                        author="MCP Server",
                        details={
                            "old_content": old_content,
                            "new_content": content,
                            "description": f"Replace cell content ({len(old_content)} chars → {len(content)} chars)",
                            "cell_type": cell_info.get("cell_type", "code"),
                            "cell_index": cell_info.get("index", "unknown"),
                        },
                    )

                    if not consent_result["approved"]:
                        reason = consent_result.get("reason", "User declined")
                        logger.warning(f"Cell update declined - {reason}")
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "success": False,
                                        "error": f"Update declined: {reason}",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    else:
                        logger.debug("✅ Cell update approved")
                        if consent_result.get("reason") != "bypass_mode":
                            print("✅ Consent granted for cell update")

                except TimeoutError:
                    logger.error("Consent request timed out for cell update")
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": "Consent request timed out",
                                },
                                indent=2,
                            ),
                        )
                    ]

            try:
                result = await self.tools.update_editing_cell(content)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_update_cell(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/update_editing_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_execute_cell(self):
        """Register the notebook/execute_cell tool."""

        @self.mcp.tool(
            name="notebook_execute_cell",
            annotations={
                "title": "Execute Cell",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            },
        )
        async def execute_editing_cell(
            timeout: float = 30.0, detailed: bool = False
        ) -> List[TextContent]:
            """Execute the currently editing cell and return the output.

            UNSAFE: This tool executes code in the active notebook cell. Only available in unsafe mode.
            The code will run in the frontend and this tool will wait for execution to complete,
            returning the cell output in the response.

            Args:
                timeout: Maximum seconds to wait for execution to complete (default: 30.0)
                detailed: If False (default), return concise summary; if True, return full info

            Returns:
                JSON response with execution result including:
                - signal_success: Whether the execution request was sent successfully (was 'success')
                - status: Execution status ("completed", "error", or "timeout")
                - execution_count: The IPython execution count for this cell
                - input: The code that was executed (detailed mode only)
                - outputs: List of cell outputs (both modes)
                - output: Expression return value if any (both modes)
                - output_summary: Truncated first output for quick preview (concise mode)
                - has_output: Whether the cell produced output
                - has_error: Whether an error occurred
                - error_type: Error type name if execution failed
                - error_message: Error message if execution failed
                - traceback: Full traceback if execution failed (when available)
                - sweep_detected: True if .start() was detected in the code
                - suggestion: Hint to use wait tools if sweep was detected

            Note:
                - If sweep_detected is True, use measureit_wait_for_sweep(variable_name) or
                  measureit_wait_for_all_sweeps() to wait for completion before proceeding.
            """
            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content for consent dialog
                    cell_info = await self.tools.get_editing_cell()
                    cell_content = cell_info.get("text", "")

                    consent_result = await self.consent_manager.request_consent(
                        operation="execute_cell",
                        tool_name="notebook_execute_cell",
                        author="MCP Server",
                        details={
                            "source_code": cell_content,
                            "description": "Execute code in the currently active Jupyter notebook cell",
                            "cell_type": cell_info.get("cell_type", "code"),
                        },
                    )

                    if not consent_result["approved"]:
                        reason = consent_result.get("reason", "User declined")
                        logger.warning(f"Cell execution declined - {reason}")
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "success": False,
                                        "error": f"Execution declined: {reason}",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    else:
                        logger.debug("✅ Cell execution approved")
                        if consent_result.get("reason") != "bypass_mode":
                            print("✅ Consent granted for cell execution")

                except TimeoutError:
                    logger.error("Consent request timed out for cell execution")
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": "Consent request timed out",
                                },
                                indent=2,
                            ),
                        )
                    ]

            start = time.perf_counter()
            try:
                result = await self.tools.execute_editing_cell(timeout=timeout)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "notebook_execute_cell",
                    {"detailed": detailed},
                    duration,
                    "success",
                )

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_execute_cell(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call("notebook_execute_cell", {}, duration, "error", str(e))
                logger.error(f"Error in notebook/execute_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_add_cell(self):
        """Register the notebook/add_cell tool."""

        @self.mcp.tool(
            name="notebook_add_cell",
            annotations={
                "title": "Add Cell",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        )
        async def add_new_cell(
            cell_type: str = "code",
            position: str = "below",
            content: str = "",
            detailed: bool = False,
        ) -> List[TextContent]:
            """Add a new cell in the notebook.

            UNSAFE: This tool adds new cells to the notebook. Only available in unsafe mode.
            The cell will be created relative to the currently active cell.

            Args:
                cell_type: Type of cell to create ("code", "markdown", "raw") - default: "code"
                position: Position relative to active cell ("above", "below") - default: "below"
                content: Initial content for the new cell - default: empty string
                detailed: If False (default), return just success; if True, return full info
            """
            try:
                result = await self.tools.add_new_cell(cell_type, position, content)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_success_only(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/add_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_delete_cell(self):
        """Register the notebook/delete_cell tool."""

        @self.mcp.tool(
            name="notebook_delete_cell",
            annotations={
                "title": "Delete Cell",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def delete_editing_cell(detailed: bool = False) -> List[TextContent]:
            """Delete the currently editing cell.

            UNSAFE: This tool deletes the currently active cell from the notebook. Only available in unsafe mode.
            Use with caution as this action cannot be undone easily. If this is the last cell in the notebook,
            a new empty code cell will be created automatically.

            Args:
                detailed: If False (default), return just success; if True, return full info
            """
            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content for consent dialog
                    cell_info = await self.tools.get_editing_cell()
                    cell_content = cell_info.get("text", "")

                    consent_result = await self.consent_manager.request_consent(
                        operation="delete_cell",
                        tool_name="notebook_delete_cell",
                        author="MCP Server",
                        details={
                            "source_code": cell_content,
                            "description": "Delete the currently active Jupyter notebook cell",
                            "cell_type": cell_info.get("cell_type", "code"),
                            "cell_index": cell_info.get("index", "unknown"),
                        },
                    )

                    if not consent_result["approved"]:
                        reason = consent_result.get("reason", "User declined")
                        logger.warning(f"Cell deletion declined - {reason}")
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "success": False,
                                        "error": f"Deletion declined: {reason}",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    else:
                        logger.debug("✅ Cell deletion approved")
                        if consent_result.get("reason") != "bypass_mode":
                            print("✅ Consent granted for cell deletion")

                except TimeoutError:
                    logger.error("Consent request timed out for cell deletion")
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": "Consent request timed out",
                                },
                                indent=2,
                            ),
                        )
                    ]

            try:
                result = await self.tools.delete_editing_cell()

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_success_only(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/delete_cell: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_delete_cells(self):
        """Register the notebook/delete_cells tool."""

        @self.mcp.tool(
            name="notebook_delete_cells",
            annotations={
                "title": "Delete Multiple Cells",
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def delete_cells_by_number(
            cell_numbers: str, detailed: bool = False
        ) -> List[TextContent]:
            """Delete multiple cells by their execution count numbers.

            UNSAFE: This tool deletes cells from the notebook by their execution counts.
            Only available in unsafe mode. Use with caution as this action cannot be undone easily.

            Args:
                cell_numbers: JSON string containing a list of execution count numbers to delete.
                             Example: "[1, 2, 5]" to delete cells 1, 2, and 5
                             Can also be a single number: "3"
                detailed: If False (default), return just success; if True, return full info

            Returns:
                JSON with deletion status and detailed results for each cell, including:
                - success: Overall operation success
                - deleted_count: Number of cells actually deleted
                - total_requested: Number of cells requested to delete
                - results: List with status for each cell number
            """
            # Parse cell_numbers first for validation
            import json as json_module

            try:
                parsed = json_module.loads(cell_numbers)
                if isinstance(parsed, int):
                    cell_list = [parsed]
                elif isinstance(parsed, list):
                    cell_list = parsed
                else:
                    return [
                        TextContent(
                            type="text",
                            text=json_module.dumps(
                                {
                                    "success": False,
                                    "error": "cell_numbers must be an integer or list of integers",
                                },
                                indent=2,
                            ),
                        )
                    ]
            except json_module.JSONDecodeError:
                return [
                    TextContent(
                        type="text",
                        text=json_module.dumps(
                            {
                                "success": False,
                                "error": f"Invalid JSON format: {cell_numbers}",
                            },
                            indent=2,
                        ),
                    )
                ]

            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    consent_result = await self.consent_manager.request_consent(
                        operation="delete_cells",
                        tool_name="notebook_delete_cells",
                        author="MCP Server",
                        details={
                            "description": f"Delete {len(cell_list)} cell(s) from notebook",
                            "cell_numbers": cell_list,
                            "count": len(cell_list),
                        },
                    )

                    if not consent_result["approved"]:
                        reason = consent_result.get("reason", "User declined")
                        logger.warning(f"Cells deletion declined - {reason}")
                        return [
                            TextContent(
                                type="text",
                                text=json_module.dumps(
                                    {
                                        "success": False,
                                        "error": f"Deletion declined: {reason}",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    else:
                        logger.debug(
                            f"✅ Cells deletion approved ({len(cell_list)} cells)"
                        )
                        if consent_result.get("reason") != "bypass_mode":
                            print(
                                f"✅ Consent granted for deletion of {len(cell_list)} cell(s)"
                            )

                except TimeoutError:
                    logger.error("Consent request timed out for cells deletion")
                    return [
                        TextContent(
                            type="text",
                            text=json_module.dumps(
                                {
                                    "success": False,
                                    "error": "Consent request timed out",
                                },
                                indent=2,
                            ),
                        )
                    ]

            # Now execute the deletion
            try:
                result = await self.tools.delete_cells_by_number(cell_list)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_success_only(result)

                return [
                    TextContent(
                        type="text",
                        text=json_module.dumps(result, indent=2, default=str),
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/delete_cells: {e}")
                return [
                    TextContent(
                        type="text", text=json_module.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_apply_patch(self):
        """Register the notebook/apply_patch tool."""

        @self.mcp.tool(
            name="notebook_apply_patch",
            annotations={
                "title": "Apply Patch",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def apply_patch(
            old_text: str, new_text: str, detailed: bool = False
        ) -> List[TextContent]:
            """Apply a patch to the current cell content.

            UNSAFE: This tool modifies the content of the currently active cell. Only available in unsafe mode.
            It replaces the first occurrence of old_text with new_text in the cell content.

            Args:
                old_text: Text to find and replace (cannot be empty)
                new_text: Text to replace with (can be empty to delete text)
                detailed: If False (default), return just success; if True, return full info
            """
            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content to show diff
                    cell_info = await self.tools.get_editing_cell()
                    cell_content = cell_info.get("cell_content", "")

                    consent_result = await self.consent_manager.request_consent(
                        operation="apply_patch",
                        tool_name="notebook_apply_patch",
                        author="MCP Server",
                        details={
                            "old_text": old_text,
                            "new_text": new_text,
                            "cell_content": cell_content,
                            "description": f"Apply patch: replace {len(old_text)} chars with {len(new_text)} chars",
                            "cell_type": cell_info.get("cell_type", "code"),
                            "cell_index": cell_info.get("index", "unknown"),
                        },
                    )

                    if not consent_result["approved"]:
                        reason = consent_result.get("reason", "User declined")
                        logger.warning(f"Patch application declined - {reason}")
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "success": False,
                                        "error": f"Patch declined: {reason}",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    else:
                        logger.debug("✅ Patch application approved")
                        if consent_result.get("reason") != "bypass_mode":
                            print("✅ Consent granted for patch application")

                except TimeoutError:
                    logger.error("Consent request timed out for patch application")
                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": "Consent request timed out",
                                },
                                indent=2,
                            ),
                        )
                    ]

            try:
                result = await self.tools.apply_patch(old_text, new_text)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_success_only(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in notebook/apply_patch: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
