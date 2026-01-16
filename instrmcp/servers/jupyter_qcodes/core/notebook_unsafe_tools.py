"""
Unsafe mode tools for Jupyter MCP server.

These tools allow cell manipulation and code execution in Jupyter notebooks.
They are only available when the server is running in unsafe mode.

Security: Code is scanned for dangerous patterns BEFORE execution. Dangerous
patterns (like os.environ modification, subprocess calls, etc.) will cause
immediate rejection of the tool call with a clear warning to the client.
"""

import json
import time
from typing import List, Optional

from mcp.types import TextContent

from instrmcp.utils.logging_config import get_logger
from instrmcp.utils.mcptool_logger import log_tool_call
from ..security import CodeScanner, get_default_scanner

logger = get_logger("tools.unsafe")


class UnsafeToolRegistrar:
    """Registers unsafe mode tools with the MCP server."""

    def __init__(
        self,
        mcp_server,
        tools,
        consent_manager=None,
        code_scanner: Optional[CodeScanner] = None,
    ):
        """
        Initialize the unsafe tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
            consent_manager: Optional ConsentManager for execute_cell consent
            code_scanner: Optional CodeScanner for dangerous pattern detection.
                         If None, uses the default scanner.
        """
        self.mcp = mcp_server
        self.tools = tools
        self.consent_manager = consent_manager
        self.code_scanner = code_scanner or get_default_scanner()

    def _scan_and_reject(
        self, code: str, tool_name: str
    ) -> Optional[List[TextContent]]:
        """Scan code for dangerous patterns and return rejection if blocked.

        This runs BEFORE consent dialogs - it's a hard security boundary.

        Args:
            code: Python code to scan
            tool_name: Name of the tool for logging

        Returns:
            List[TextContent] with rejection message if blocked, None if safe
        """
        if not code or not code.strip():
            return None

        # Log that scanning is happening (visible confirmation)
        logger.info(f"🔍 Security scan starting for {tool_name} ({len(code)} chars)")

        scan_result = self.code_scanner.scan(code)

        if scan_result.blocked:
            rejection_msg = self.code_scanner.get_rejection_message(scan_result)
            logger.error(
                f"🚫 {tool_name} blocked by code scanner: {scan_result.block_reason}"
            )
            # Print to ensure visibility even if logging isn't configured
            print(f"🚫 BLOCKED: {scan_result.block_reason}")

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "blocked": True,
                            "error": f"Security policy violation: {scan_result.block_reason}",
                            "security_scan": scan_result.to_dict(),
                            "message": rejection_msg,
                        },
                        indent=2,
                    ),
                )
            ]

        # Log warnings for non-blocking issues (HIGH/MEDIUM that weren't blocked)
        if scan_result.issues:
            logger.warning(
                f"⚠️  {tool_name}: {len(scan_result.issues)} potential risk(s) detected "
                f"but not blocked"
            )

        return None

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
        Preserves error field if present (Bug #12 fix).
        """
        concise = {"success": result.get("success", False)}
        # Always preserve error messages regardless of detailed mode
        if "error" in result:
            concise["error"] = result["error"]
        return concise

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
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def update_editing_cell(
            content: str, detailed: bool = False
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # SECURITY: Scan the new content for dangerous patterns BEFORE consent
            rejection = self._scan_and_reject(content, "notebook_update_editing_cell")
            if rejection:
                return rejection

            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content to show what will be replaced
                    cell_info = await self.tools.get_editing_cell()
                    old_content = cell_info.get("cell_content", "")

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
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": False,
                "openWorldHint": True,
            },
        )
        async def execute_editing_cell(
            timeout: float = 30.0, detailed: bool = False
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # SECURITY: First get cell content and scan for dangerous patterns
            # This runs BEFORE consent - it's a hard security boundary
            try:
                cell_info = await self.tools.get_editing_cell()
                cell_content = cell_info.get("cell_content", "")
            except Exception as e:
                # CRITICAL: Cannot proceed without cell content for security scan
                # This is a hard security boundary - never execute without scanning
                logger.error(f"SECURITY: Cannot retrieve cell for security scan: {e}")
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "blocked": True,
                                "error": "Security scan failed: unable to retrieve cell content. Execution blocked.",
                            },
                            indent=2,
                        ),
                    )
                ]

            # Scan for dangerous patterns and reject if found
            rejection = self._scan_and_reject(cell_content, "notebook_execute_cell")
            if rejection:
                return rejection

            # Request consent if consent manager is available
            if self.consent_manager:
                try:
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
            timeout_s: float = 2.0,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # SECURITY: Scan content for dangerous patterns (only for code cells)
            if cell_type == "code" and content:
                rejection = self._scan_and_reject(content, "notebook_add_cell")
                if rejection:
                    return rejection

            try:
                result = await self.tools.add_new_cell(
                    cell_type, position, content, timeout_s
                )

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
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def delete_editing_cell(detailed: bool = False) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    # Get current cell content for consent dialog
                    cell_info = await self.tools.get_editing_cell()
                    cell_content = cell_info.get("cell_content", "")

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
                "readOnlyHint": False,
                "destructiveHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def delete_cells_by_number(
            cell_numbers: str, detailed: bool = False
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def apply_patch(
            old_text: str, new_text: str, detailed: bool = False
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            # SECURITY: Get current cell content and compute the patched result
            # We must scan the FULL resulting code, not just the new_text fragment
            try:
                cell_info = await self.tools.get_editing_cell()
                current_content = cell_info.get("cell_content", "")
            except Exception as e:
                # CRITICAL: Cannot proceed without cell content for security scan
                logger.error(
                    f"SECURITY: Cannot retrieve cell for patch security scan: {e}"
                )
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "blocked": True,
                                "error": "Security scan failed: unable to retrieve cell content for patch.",
                            },
                            indent=2,
                        ),
                    )
                ]

            # Verify the old_text exists in the cell
            if old_text not in current_content:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "error": "Patch failed: old_text not found in cell content.",
                            },
                            indent=2,
                        ),
                    )
                ]

            # Compute the resulting code after patch application
            patched_content = current_content.replace(old_text, new_text, 1)

            # SECURITY: Scan the FULL resulting code for dangerous patterns
            rejection = self._scan_and_reject(patched_content, "notebook_apply_patch")
            if rejection:
                return rejection

            # Request consent if consent manager is available
            if self.consent_manager:
                try:
                    cell_content = current_content  # For consent dialog

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
