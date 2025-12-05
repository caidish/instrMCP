"""
Unified QCodes meta-tool registrar.

Consolidates 2 QCodes tools into a single meta-tool to reduce
context window overhead while preserving all functionality.
"""

import json
import time
from typing import List, Optional, Dict, Set

from mcp.types import TextContent

from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call

logger = get_logger("tools.qcodes")


class QCodesMetaToolRegistrar:
    """Registers unified QCodes meta-tool with the MCP server."""

    # All actions are read-only (no safe/unsafe distinction needed)
    ALL_ACTIONS: Set[str] = {"instrument_info", "get_values"}

    # Action -> (required_params, optional_params_with_defaults)
    ACTION_PARAMS: Dict[str, tuple] = {
        "instrument_info": (["name"], {"with_values": False}),
        "get_values": (["queries"], {}),
    }

    # Action -> usage example for error messages
    ACTION_USAGE: Dict[str, str] = {
        "instrument_info": 'qcodes(action="instrument_info", name="lockin") or qcodes(action="instrument_info", name="*") to list all',
        "get_values": 'qcodes(action="get_values", queries=\'{"instrument": "lockin", "parameter": "X"}\')',
    }

    def __init__(self, mcp_server, tools):
        """
        Initialize the QCodes meta-tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
        """
        self.mcp = mcp_server
        self.tools = tools

    def register_all(self):
        """Register the unified QCodes meta-tool."""
        self._register_qcodes_tool()

    def _register_qcodes_tool(self):
        @self.mcp.tool(name="qcodes")
        async def qcodes(
            action: str,
            name: Optional[str] = None,
            with_values: bool = False,
            queries: Optional[str] = None,
        ) -> List[TextContent]:
            """Unified QCodes tool for instrument and parameter operations.

            STRICT PARAMETER REQUIREMENTS BY ACTION:

            ═══ INSTRUMENT OPERATIONS ═══

            action="instrument_info"
                → REQUIRES: name
                → Optional: with_values (include cached parameter values)
                → Use name="*" to list all available instruments
                Examples:
                  qcodes(action="instrument_info", name="*")
                  qcodes(action="instrument_info", name="lockin")
                  qcodes(action="instrument_info", name="dac", with_values=True)

            action="get_values"
                → REQUIRES: queries (JSON string)
                → Single query: {"instrument": "name", "parameter": "param", "fresh": false}
                → Batch query: [{"instrument": "name1", "parameter": "param1"}, ...]
                → Hierarchical params: "ch01.voltage", "X", "dac.ch01.voltage"
                Examples:
                  qcodes(action="get_values", queries='{"instrument": "lockin", "parameter": "X"}')
                  qcodes(action="get_values", queries='{"instrument": "dac", "parameter": "ch01.voltage", "fresh": true}')
                  qcodes(action="get_values", queries='[{"instrument": "lockin", "parameter": "X"}, {"instrument": "lockin", "parameter": "Y"}]')

            Returns:
                JSON with instrument info, parameter values, or error details.
            """
            return await self._handle_action(
                action=action,
                name=name,
                with_values=with_values,
                queries=queries,
            )

    async def _handle_action(self, action: str, **kwargs) -> List[TextContent]:
        """Route and execute the requested action."""
        start = time.perf_counter()

        # Sanitize action: strip quotes that LLMs sometimes add
        # e.g., '"instrument_info"' → 'instrument_info'
        if action:
            action = action.strip("\"'")

        # 1. Validate action exists
        if action not in self.ALL_ACTIONS:
            return self._error_response(
                error=f"Unknown action: '{action}'",
                action=action,
                hint="Use one of the valid actions listed below",
                valid_actions=sorted(self.ALL_ACTIONS),
            )

        # 2. Validate required parameters
        required_params, _ = self.ACTION_PARAMS[action]
        missing = [p for p in required_params if kwargs.get(p) is None]
        if missing:
            return self._error_response(
                error=f"Missing required parameter(s): {missing}",
                action=action,
                missing=missing,
                usage=self.ACTION_USAGE.get(action, ""),
            )

        # 3. Execute action
        try:
            if action == "instrument_info":
                result = await self._action_instrument_info(
                    name=kwargs["name"],
                    with_values=kwargs.get("with_values", False),
                )
            elif action == "get_values":
                result = await self._action_get_values(
                    queries=kwargs["queries"],
                )
            else:
                return self._error_response(
                    error=f"Action '{action}' not implemented",
                    action=action,
                )

            duration = (time.perf_counter() - start) * 1000
            log_tool_call("qcodes", {"action": action, **kwargs}, duration, "success")
            return [
                TextContent(type="text", text=json.dumps(result, indent=2, default=str))
            ]

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            log_tool_call(
                "qcodes", {"action": action, **kwargs}, duration, "error", str(e)
            )
            logger.error(f"Error in qcodes action '{action}': {e}")
            return self._error_response(
                error=str(e),
                action=action,
            )

    async def _action_instrument_info(self, name: str, with_values: bool) -> dict:
        """Get instrument information."""
        return await self.tools.instrument_info(name, with_values)

    async def _action_get_values(self, queries: str) -> list:
        """Get parameter values from JSON query."""
        try:
            queries_data = json.loads(queries)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in queries: {e}. "
                f"Expected format: "
                f'{{"instrument": "name", "parameter": "param"}} or '
                f'[{{"instrument": "name1", "parameter": "param1"}}, ...]'
            )
        return await self.tools.get_parameter_values(queries_data)

    def _error_response(
        self,
        error: str,
        action: str = None,
        hint: str = None,
        valid_actions: list = None,
        missing: list = None,
        usage: str = None,
    ) -> List[TextContent]:
        """Build a structured error response."""
        response = {"error": error}
        if action:
            response["action"] = action
        if hint:
            response["hint"] = hint
        if valid_actions:
            response["valid_actions"] = valid_actions
        if missing:
            response["missing"] = missing
        if usage:
            response["usage"] = usage
        return [TextContent(type="text", text=json.dumps(response, indent=2))]
