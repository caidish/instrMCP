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

    def register_all(self):
        """Register all MeasureIt tools."""
        self._register_get_status()
        self._register_wait_for_all_sweeps()
        self._register_wait_for_sweep()

    def _register_get_status(self):
        """Register the measureit/get_status tool."""

        @self.mcp.tool(name="measureit_get_status")
        async def get_measureit_status() -> List[TextContent]:
            """Check if any MeasureIt sweep is currently running.

            Returns information about active MeasureIt sweeps in the notebook namespace,
            including sweep type, status, and basic configuration if available.

            Returns JSON containing:
            - running: bool - whether any sweep is currently active
            - sweeps: List of active sweep objects with their status
            - checked_variables: List of variable names checked
            """
            try:
                result = await self.tools.get_measureit_status()
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

        @self.mcp.tool(name="measureit_wait_for_all_sweeps")
        async def wait_for_all_sweeps() -> List[TextContent]:
            """Wait until all currently running MeasureIt sweeps finish."""
            try:
                result = await self.tools.wait_for_all_sweeps()
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

        @self.mcp.tool(name="measureit_wait_for_sweep")
        async def wait_for_sweep(variable_name: str) -> List[TextContent]:
            """Wait until the specified MeasureIt sweep finishes."""
            try:
                result = await self.tools.wait_for_sweep(variable_name)
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
