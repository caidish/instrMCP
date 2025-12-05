"""
Unified database meta-tool registrar.

Consolidates 4 database tools into a single meta-tool to reduce
context window overhead while preserving all functionality.
"""

import json
import time
from typing import List, Optional, Dict, Set

from mcp.types import TextContent

from instrmcp.logging_config import get_logger
from ..tool_logger import log_tool_call

logger = get_logger("tools.database")


class DatabaseMetaToolRegistrar:
    """Registers unified database meta-tool with the MCP server."""

    # All actions are read-only
    ALL_ACTIONS: Set[str] = {
        "list_experiments",
        "get_dataset",
        "stats",
        "list_available",
    }

    # Action -> (required_params, optional_params_with_defaults)
    ACTION_PARAMS: Dict[str, tuple] = {
        "list_experiments": ([], {"database_path": None}),
        "get_dataset": (["id"], {"database_path": None}),
        "stats": ([], {"database_path": None}),
        "list_available": ([], {}),
    }

    # Action -> usage example for error messages
    ACTION_USAGE: Dict[str, str] = {
        "list_experiments": 'database(action="list_experiments") or database(action="list_experiments", database_path="/path/to/db.db")',
        "get_dataset": 'database(action="get_dataset", id=1) or database(action="get_dataset", id=5, database_path="/path/to/db.db")',
        "stats": 'database(action="stats") or database(action="stats", database_path="/path/to/db.db")',
        "list_available": 'database(action="list_available")',
    }

    def __init__(self, mcp_server, db_integration):
        """
        Initialize the database meta-tool registrar.

        Args:
            mcp_server: FastMCP server instance
            db_integration: Database integration module (instrmcp.extensions.database)
        """
        self.mcp = mcp_server
        self.db = db_integration

    def register_all(self):
        """Register the unified database meta-tool."""
        self._register_database_tool()

    def _register_database_tool(self):
        @self.mcp.tool(name="database")
        async def database(
            action: str,
            id: Optional[int] = None,
            database_path: Optional[str] = None,
        ) -> List[TextContent]:
            """Unified database tool for QCodes database operations.

            STRICT PARAMETER REQUIREMENTS BY ACTION:

            ═══ DATABASE OPERATIONS ═══

            action="list_experiments"
                → No required params.
                → Optional: database_path (uses MeasureIt/QCodes default if not specified)
                Examples:
                  database(action="list_experiments")
                  database(action="list_experiments", database_path="/path/to/experiments.db")

            action="get_dataset"
                → REQUIRES: id (dataset run ID, e.g., 1, 2, 5)
                → Optional: database_path
                Examples:
                  database(action="get_dataset", id=1)
                  database(action="get_dataset", id=5, database_path="/path/to/experiments.db")

            action="stats"
                → No required params. Returns database statistics.
                → Optional: database_path
                Examples:
                  database(action="stats")
                  database(action="stats", database_path="/path/to/experiments.db")

            action="list_available"
                → No required params.
                → Searches MeasureIt databases directory and QCodes config paths.
                Example:
                  database(action="list_available")

            Database Path Resolution (when database_path=None):
                1. MeasureIt default: $MeasureItHome/Databases/Example_database.db
                2. QCodes config: qc.config.core.db_location
                3. Error with suggestions if neither exists

            Returns:
                JSON with database/experiment/dataset info or error details.
            """
            return await self._handle_action(
                action=action,
                id=id,
                database_path=database_path,
            )

    async def _handle_action(self, action: str, **kwargs) -> List[TextContent]:
        """Route and execute the requested action."""
        start = time.perf_counter()

        # Sanitize action: strip quotes that LLMs sometimes add
        # e.g., '"list_experiments"' → 'list_experiments'
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
            if action == "list_experiments":
                result = self._action_list_experiments(
                    database_path=kwargs.get("database_path"),
                )
            elif action == "get_dataset":
                result = self._action_get_dataset(
                    id=kwargs["id"],
                    database_path=kwargs.get("database_path"),
                )
            elif action == "stats":
                result = self._action_stats(
                    database_path=kwargs.get("database_path"),
                )
            elif action == "list_available":
                result = self._action_list_available()
            else:
                return self._error_response(
                    error=f"Action '{action}' not implemented",
                    action=action,
                )

            duration = (time.perf_counter() - start) * 1000
            log_tool_call("database", {"action": action, **kwargs}, duration, "success")

            # db functions already return JSON strings
            return [TextContent(type="text", text=result)]

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            log_tool_call(
                "database", {"action": action, **kwargs}, duration, "error", str(e)
            )
            logger.error(f"Error in database action '{action}': {e}")
            return self._error_response(
                error=str(e),
                action=action,
            )

    def _action_list_experiments(self, database_path: Optional[str]) -> str:
        """List all experiments in the database."""
        return self.db.list_experiments(database_path=database_path)

    def _action_get_dataset(self, id: int, database_path: Optional[str]) -> str:
        """Get dataset information."""
        return self.db.get_dataset_info(id=id, database_path=database_path)

    def _action_stats(self, database_path: Optional[str]) -> str:
        """Get database statistics."""
        return self.db.get_database_stats(database_path=database_path)

    def _action_list_available(self) -> str:
        """List available databases."""
        return self.db.list_available_databases()

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
