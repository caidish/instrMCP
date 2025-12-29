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

        Concise: only sweep's state.
        Preserves error field if present.
        """
        sweep = data.get("sweep")
        if sweep is None:
            result = {"sweep": None}
        else:
            result = {
                "sweep": {
                    "variable_name": sweep.get("variable_name"),
                    "state": sweep.get("state"),
                }
            }
        if "error" in data:
            result["error"] = data["error"]
        return result

    def _to_concise_sweeps(self, data: dict) -> dict:
        """Convert full sweeps info to concise format.

        Concise: only sweep states.
        Preserves error field if present.
        """
        sweeps = data.get("sweeps")
        if sweeps is None:
            result = {"sweeps": None}
        else:
            result = {
                "sweeps": {
                    name: {"state": info.get("state")} for name, info in sweeps.items()
                }
            }
        if "error" in data:
            result["error"] = data["error"]
        return result

    # ===== End concise mode helpers =====

    def register_all(self):
        """Register all MeasureIt tools."""
        self._register_get_status()
        self._register_wait_for_all_sweeps()
        self._register_wait_for_sweep()

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
        async def wait_for_all_sweeps(detailed: bool = False) -> List[TextContent]:
            """Wait until all currently running MeasureIt sweeps finish.

            Args:
                detailed: If False (default), return only sweep states;
                    if True, return full sweep information.
            """
            try:
                result = await self.tools.wait_for_all_sweeps()

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
            variable_name: str, detailed: bool = False
        ) -> List[TextContent]:
            """Wait until the specified MeasureIt sweep finishes.

            Args:
                variable_name: Name of the sweep variable to wait for.
                detailed: If False (default), return only sweep state;
                    if True, return full sweep information.
            """
            try:
                result = await self.tools.wait_for_sweep(variable_name)

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
