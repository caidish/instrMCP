"""
QCodes instrument tool registrar.

Registers tools for interacting with QCodes instruments.
"""

import json
import logging
from typing import List

from mcp.types import TextContent

logger = logging.getLogger(__name__)


class QCodesToolRegistrar:
    """Registers QCodes instrument tools with the MCP server."""

    def __init__(self, mcp_server, tools):
        """
        Initialize the QCodes tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
        """
        self.mcp = mcp_server
        self.tools = tools

    def register_all(self):
        """Register all QCodes instrument tools."""
        self._register_instrument_info()
        self._register_get_parameter_values()

    def _register_instrument_info(self):
        """Register the qcodes_instrument_info tool."""

        @self.mcp.tool(name="qcodes_instrument_info")
        async def instrument_info(name: str, with_values: bool = False) -> List[TextContent]:
            """Get detailed information about a QCodes instrument.

            Args:
                name: Instrument name
                with_values: Include cached parameter values
            """
            try:
                info = await self.tools.instrument_info(name, with_values)
                return [TextContent(type="text", text=json.dumps(info, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in qcodes_instrument_info: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_get_parameter_values(self):
        """Register the qcodes_get_parameter_values tool."""

        @self.mcp.tool(name="qcodes_get_parameter_values")
        async def get_parameter_values(queries: str) -> List[TextContent]:
            """Get QCodes parameter values - supports both single parameter and batch queries.

            Args:
                queries: JSON string containing single query or list of queries
                         Single: {"instrument": "name", "parameter": "param", "fresh": false}
                         Batch: [{"instrument": "name1", "parameter": "param1"}, ...]
            """
            try:
                queries_data = json.loads(queries)
                results = await self.tools.get_parameter_values(queries_data)
                return [TextContent(type="text", text=json.dumps(results, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in qcodes_get_parameter_values: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]