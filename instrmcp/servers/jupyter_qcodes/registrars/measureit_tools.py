"""
MeasureIt integration tool registrar.

Registers tools for interacting with MeasureIt sweep objects (optional feature).
"""

import json
import logging
from typing import List

from mcp.types import TextContent

logger = logging.getLogger(__name__)


class MeasureItToolRegistrar:
    """Registers MeasureIt integration tools with the MCP server."""

    def __init__(self, mcp_server, tools):
        """
        Initialize the MeasureIt tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
        """
        self.mcp = mcp_server
        self.tools = tools

    # ===== Concise mode helpers =====

    def _to_concise_status(self, data: dict) -> dict:
        """Convert full status to concise format.

        Concise: active status and sweep names only.
        Preserves error field if present.
        """
        sweeps = data.get("sweeps", {})
        result = {
            "active": data.get("active", False),
            "sweep_names": list(sweeps.keys()),
            "count": len(sweeps),
        }
        if "error" in data:
            result["error"] = data["error"]
        return result

    def _to_concise_sweep(self, data: dict) -> dict:
        """Convert full sweep info to concise format.

        Concise: only sweep's state and error_message (if error state).
        Preserves top-level error, sweep_error fields if present.
        """
        sweep = data.get("sweep")
        if sweep is None:
            result = {"sweep": None}
        else:
            concise_sweep = {
                "variable_name": sweep.get("variable_name"),
                "state": sweep.get("state"),
            }
            # Include error_message in concise output when state is error
            if sweep.get("state") == "error" and sweep.get("error_message"):
                concise_sweep["error_message"] = sweep.get("error_message")
            result = {"sweep": concise_sweep}
        if "error" in data:
            result["error"] = data["error"]
        if "sweep_error" in data:
            result["sweep_error"] = data["sweep_error"]
        return result

    def _to_concise_sweeps(self, data: dict) -> dict:
        """Convert full sweeps info to concise format.

        Concise: only sweep states and error_message (if error state).
        Preserves top-level error, sweep_error, errored_sweeps fields if present.
        """
        sweeps = data.get("sweeps")
        if sweeps is None:
            result = {"sweeps": None}
        else:
            concise_sweeps = {}
            for name, info in sweeps.items():
                concise_info = {"state": info.get("state")}
                # Include error_message in concise output when state is error
                if info.get("state") == "error" and info.get("error_message"):
                    concise_info["error_message"] = info.get("error_message")
                concise_sweeps[name] = concise_info
            result = {"sweeps": concise_sweeps}
        if "error" in data:
            result["error"] = data["error"]
        if "sweep_error" in data:
            result["sweep_error"] = data["sweep_error"]
        if "errored_sweeps" in data:
            result["errored_sweeps"] = data["errored_sweeps"]
        return result

    # ===== End concise mode helpers =====

    def register_all(self):
        """Register all MeasureIt tools."""
        self._register_get_status()
        self._register_wait_for_all_sweeps()
        self._register_wait_for_sweep()
        self._register_kill_sweep()

    def _register_get_status(self):
        """Register the measureit/get_status tool."""

        @self.mcp.tool(
            name="measureit_get_status",
            annotations={
                "title": "MeasureIt Status",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_measureit_status(detailed: bool = False) -> List[TextContent]:
            """Check if any MeasureIt sweep is currently running.

            Returns information about active MeasureIt sweeps in the notebook namespace,
            including sweep type, status, and basic configuration if available.

            Args:
                detailed: If False (default), return only active status and sweep names;
                    if True, return full sweep information.

            Returns JSON containing:
            - Concise mode: active (bool), sweep_names (list), count (int)
            - Detailed mode: active (bool), sweeps (dict with full sweep info)
            """
            try:
                result = await self.tools.get_measureit_status()

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_status(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in measureit/get_status: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_wait_for_all_sweeps(self):
        """Register the measureit/wait_for_all_sweeps tool."""

        @self.mcp.tool(
            name="measureit_wait_for_all_sweeps",
            annotations={
                "title": "Wait for All Sweeps",
                "readOnlyHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        )
        async def wait_for_all_sweeps(
            timeout: float | None = None, detailed: bool = False
        ) -> List[TextContent]:
            """Wait until all currently running MeasureIt sweeps finish.

            IMPORTANT: Calculate timeout based on sweep parameters before calling.
            Formula: timeout = (num_points * delay_per_point) + ramp_time + safety_margin
            Example: 100 points × 0.1s delay + 10s ramp + 30s margin = 50s timeout.
            If sweep duration is unknown, use a reasonable default (e.g., 300s) or
            call measureit_get_status first to check time_remaining.

            Args:
                timeout: Maximum time to wait in seconds. If None, wait indefinitely.
                    STRONGLY RECOMMENDED to set this to avoid hanging on stuck sweeps.
                detailed: If False (default), return only sweep states;
                    if True, return full sweep information.

            Returns JSON containing:
                - sweeps: Dict of sweep info (or None if no sweeps were running)
                - error: Error message if timeout or other error occurred
                - timed_out: True if the timeout was reached
            """
            try:
                result = await self.tools.wait_for_all_sweeps(timeout=timeout)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_sweeps(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in measureit/wait_for_all_sweeps: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_wait_for_sweep(self):
        """Register the measureit/wait_for_sweep tool."""

        @self.mcp.tool(
            name="measureit_wait_for_sweep",
            annotations={
                "title": "Wait for Sweep",
                "readOnlyHint": True,
                "idempotentHint": False,
                "openWorldHint": False,
            },
        )
        async def wait_for_sweep(
            variable_name: str,
            timeout: float | None = None,
            detailed: bool = False,
        ) -> List[TextContent]:
            """Wait until the specified MeasureIt sweep finishes.

            IMPORTANT: Calculate timeout based on sweep parameters before calling.
            Formula: timeout = (num_points * delay_per_point) + ramp_time + safety_margin
            Example: 100 points × 0.1s delay + 10s ramp + 30s margin = 50s timeout.
            If sweep duration is unknown, use a reasonable default (e.g., 300s) or
            call measureit_get_status(detailed=True) first to check time_remaining.

            Args:
                variable_name: Name of the sweep variable to wait for.
                timeout: Maximum time to wait in seconds. If None, wait indefinitely.
                    STRONGLY RECOMMENDED to set this to avoid hanging on stuck sweeps.
                detailed: If False (default), return only sweep state;
                    if True, return full sweep information.

            Returns JSON containing:
                - sweep: Dict of sweep info (or None if no matching sweep was running)
                - error: Error message if timeout or other error occurred
                - timed_out: True if the timeout was reached
            """
            try:
                result = await self.tools.wait_for_sweep(variable_name, timeout=timeout)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_sweep(result)

                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in measureit/wait_for_sweep: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_kill_sweep(self):
        """Register the measureit/kill_sweep tool."""

        @self.mcp.tool(
            name="measureit_kill_sweep",
            annotations={
                "title": "Kill Sweep",
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def kill_sweep(variable_name: str) -> List[TextContent]:
            """Kill a running MeasureIt sweep to release resources.

            UNSAFE: This tool stops a running sweep, which may leave instruments
            in an intermediate state. Use when a sweep needs to be terminated
            due to timeout, error, or user request.

            After killing a sweep, you may need to:
            - Re-initialize instruments to a known state
            - Check instrument parameters before starting a new sweep

            Args:
                variable_name: Name of the sweep variable in the notebook namespace
                    (e.g., "sweep1d", "my_sweep")

            Returns JSON containing:
                - success: bool - whether the kill was successful
                - sweep_name: str - name of the sweep
                - previous_state: str - state before kill
                - new_state: str - state after kill
                - error: str (if any error occurred)
            """
            try:
                result = await self.tools.kill_sweep(variable_name)
                return [
                    TextContent(
                        type="text", text=json.dumps(result, indent=2, default=str)
                    )
                ]
            except Exception as e:
                logger.error(f"Error in measureit/kill_sweep: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
