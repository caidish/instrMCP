"""
MeasureIt integration tool registrar.

Registers tools for interacting with MeasureIt sweep objects (optional feature).
"""

import json
import logging
from typing import List, Optional

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
        Preserves top-level error, sweep_error, killed, timed_out fields if present.
        Adds kill_reason to explain why the sweep was killed.
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
        if "timed_out" in data:
            result["timed_out"] = data["timed_out"]
        if "kill_suggestion" in data:
            result["kill_suggestion"] = data["kill_suggestion"]
        # Always preserve killed status; only add kill_reason when killed=True
        if "killed" in data:
            result["killed"] = data["killed"]
            if data["killed"] is True:
                # Add explanation for why the sweep was killed
                if data.get("sweep_error"):
                    result["kill_reason"] = "Sweep entered error state"
                elif sweep and sweep.get("state") not in ("ramping", "running"):
                    result["kill_reason"] = (
                        "Sweep completed; killed to release hardware resources"
                    )
                else:
                    # Fallback when sweep data unavailable
                    result["kill_reason"] = "Killed to release hardware resources"
        return result

    def _to_concise_sweeps(self, data: dict) -> dict:
        """Convert full sweeps info to concise format.

        Concise: only sweep states and error_message (if error state).
        Preserves top-level error, sweep_error, errored_sweeps, killed, timed_out fields.
        Adds kill_reason to explain why sweeps were killed.
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
        if "timed_out" in data:
            result["timed_out"] = data["timed_out"]
        if "kill_suggestion" in data:
            result["kill_suggestion"] = data["kill_suggestion"]
        # Always preserve killed status; only add kill_reason when killed=True
        if "killed" in data:
            result["killed"] = data["killed"]
            if data["killed"] is True:
                # Add explanation for why sweeps were killed
                if data.get("sweep_error"):
                    result["kill_reason"] = "One or more sweeps entered error state"
                else:
                    result["kill_reason"] = (
                        "Sweeps completed; killed to release hardware resources"
                    )
        return result

    # ===== End concise mode helpers =====

    def register_all(self):
        """Register all MeasureIt tools."""
        self._register_get_status()
        self._register_wait_for_sweep()
        self._register_kill_sweep()

    def _register_get_status(self):
        """Register the measureit/get_status tool."""

        @self.mcp.tool(
            name="measureit_get_status",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_measureit_status(detailed: bool = False) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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

    def _register_wait_for_sweep(self):
        """Register the measureit/wait_for_sweep tool."""

        @self.mcp.tool(
            name="measureit_wait_for_sweep",
            annotations={
                "readOnlyHint": False,  # Kills sweeps to release hardware resources
                "idempotentHint": False,
                "openWorldHint": False,
            },
        )
        async def wait_for_sweep(
            timeout: float,
            variable_name: Optional[str] = None,
            all: bool = False,
            kill: bool = True,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            try:
                # If all=True, wait for all sweeps
                if all:
                    result = await self.tools.wait_for_all_sweeps(
                        timeout=timeout, kill=kill
                    )
                    # Apply concise mode filtering
                    if not detailed:
                        result = self._to_concise_sweeps(result)
                else:
                    # Require variable_name when all=False
                    if not variable_name:
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "error": "variable_name is required when all=False",
                                        "hint": "Provide variable_name to wait for a specific sweep, "
                                        "or set all=True to wait for all sweeps",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
                    result = await self.tools.wait_for_sweep(
                        variable_name, timeout=timeout, kill=kill
                    )
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
                "readOnlyHint": False,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def kill_sweep(
            variable_name: Optional[str] = None,
            all: bool = False,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            try:
                # If all=True, kill all sweeps
                if all:
                    result = await self.tools.kill_all_sweeps()
                else:
                    # Require variable_name when all=False
                    if not variable_name:
                        return [
                            TextContent(
                                type="text",
                                text=json.dumps(
                                    {
                                        "error": "variable_name is required when all=False",
                                        "hint": "Provide variable_name to kill a specific sweep, "
                                        "or set all=True to kill all sweeps",
                                    },
                                    indent=2,
                                ),
                            )
                        ]
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
