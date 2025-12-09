"""
QCodes instrument tool registrar.

Registers tools for interacting with QCodes instruments.
"""

import json
import logging
from typing import List

from mcp.types import TextContent

from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call
import time

logger = get_logger("tools.qcodes")


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

        @self.mcp.tool(
            name="qcodes_instrument_info",
            annotations={
                "title": "Get Instrument Info",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def instrument_info(
            name: str, with_values: bool = False
        ) -> List[TextContent]:
            """Get detailed information about a QCodes instrument.

            Args:
                name: Instrument name, or "*" to list all instruments
                with_values: Include cached parameter values (only for specific instruments, not with "*")

            Note:
                To get live parameter values, use qcodes_get_parameter_values with:
                - "{instrument}.{parameter}" for direct parameters
                - "{instrument}.{channel}.{parameter}" for multi-channel instruments
                Example: "lockin.X" or "dac.ch01.voltage"
            """
            start = time.perf_counter()
            try:
                info = await self.tools.instrument_info(name, with_values)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_instrument_info",
                    {"name": name, "with_values": with_values},
                    duration,
                    "success",
                )
                return [
                    TextContent(
                        type="text", text=json.dumps(info, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_instrument_info",
                    {"name": name, "with_values": with_values},
                    duration,
                    "error",
                    str(e),
                )
                logger.error(f"Error in qcodes_instrument_info: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_parameter_values(self):
        """Register the qcodes_get_parameter_values tool."""

        @self.mcp.tool(
            name="qcodes_get_parameter_values",
            annotations={
                "title": "Get Parameter Values",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_parameter_values(queries: str) -> List[TextContent]:
            """Get QCodes parameter values - supports both single parameter and batch queries.

            Args:
                queries: JSON string containing single query or list of queries
                         Single: {"instrument": "name", "parameter": "param", "fresh": false}
                         Batch: [{"instrument": "name1", "parameter": "param1"}, ...]
            """
            start = time.perf_counter()
            try:
                queries_data = json.loads(queries)
                results = await self.tools.get_parameter_values(queries_data)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_get_parameter_values",
                    {"queries": queries},
                    duration,
                    "success",
                )
                return [
                    TextContent(
                        type="text", text=json.dumps(results, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_get_parameter_values",
                    {"queries": queries},
                    duration,
                    "error",
                    str(e),
                )
                logger.error(f"Error in qcodes_get_parameter_values: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
