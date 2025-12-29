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

    def _to_concise_instrument_info(self, info: dict, name: str) -> dict:
        """Convert full instrument info to concise format.

        Concise format: status, name (or list), brief parameter summary (counts per level),
        omit full parameter dict/values and timing.
        """
        # For wildcard query, return just names and count
        if name == "*":
            return {
                "status": "success",
                "instruments": info.get("instruments", []),
                "count": info.get("count", 0),
            }

        # For specific instrument, return concise summary
        hierarchy_info = info.get("hierarchy_info", {})
        return {
            "status": "success",
            "name": info.get("name", name),
            "parameter_summary": {
                "direct_count": len(hierarchy_info.get("direct_parameters", [])),
                "channel_count": len(hierarchy_info.get("channel_info", {})),
                "total_count": hierarchy_info.get("parameter_count", 0),
            },
            "has_channels": hierarchy_info.get("has_channels", False),
        }

    def _to_concise_parameter_values(self, result) -> dict:
        """Convert full parameter value result to concise format.

        Concise format: per query {instrument, parameter, value, error?}; only include value.
        """
        # Handle single result
        if isinstance(result, dict):
            return self._concise_single_param(result)

        # Handle batch results
        return [self._concise_single_param(r) for r in result]

    def _concise_single_param(self, result: dict) -> dict:
        """Convert a single parameter result to concise format."""
        query = result.get("query", {})
        concise = {
            "instrument": query.get("instrument", ""),
            "parameter": query.get("parameter", ""),
        }

        if "error" in result:
            concise["error"] = result["error"]
        else:
            concise["value"] = result.get("value")

        return concise

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
            name: str, with_values: bool = False, detailed: bool = False
        ) -> List[TextContent]:
            """Get detailed information about a QCodes instrument.

            Args:
                name: Instrument name, or "*" to list all instruments
                with_values: Include cached parameter values (only for specific instruments, not with "*")
                detailed: If False (default), return concise summary; if True, return full response

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
                    {"name": name, "with_values": with_values, "detailed": detailed},
                    duration,
                    "success",
                )

                # Apply concise mode filtering
                if not detailed:
                    info = self._to_concise_instrument_info(info, name)

                return [
                    TextContent(
                        type="text", text=json.dumps(info, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_instrument_info",
                    {"name": name, "with_values": with_values, "detailed": detailed},
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
        async def get_parameter_values(
            queries: str, detailed: bool = False
        ) -> List[TextContent]:
            """Get QCodes parameter values - supports both single parameter and batch queries.

            Args:
                queries: JSON string containing single query or list of queries
                         Single: {"instrument": "name", "parameter": "param", "fresh": false}
                         Batch: [{"instrument": "name1", "parameter": "param1"}, ...]
                detailed: If False (default), return concise {instrument, parameter, value};
                         if True, return full response with timestamps and source info
            """
            start = time.perf_counter()
            try:
                queries_data = json.loads(queries)
                results = await self.tools.get_parameter_values(queries_data)
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_get_parameter_values",
                    {"queries": queries, "detailed": detailed},
                    duration,
                    "success",
                )

                # Apply concise mode filtering
                if not detailed:
                    results = self._to_concise_parameter_values(results)

                return [
                    TextContent(
                        type="text", text=json.dumps(results, indent=2, default=str)
                    )
                ]
            except Exception as e:
                duration = (time.perf_counter() - start) * 1000
                log_tool_call(
                    "qcodes_get_parameter_values",
                    {"queries": queries, "detailed": detailed},
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
