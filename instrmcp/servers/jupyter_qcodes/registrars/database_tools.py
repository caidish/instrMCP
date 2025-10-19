"""
Database integration tool registrar.

Registers tools for querying QCodes databases (optional feature).
"""

import json
import logging
from typing import List, Optional

from mcp.types import TextContent

logger = logging.getLogger(__name__)


class DatabaseToolRegistrar:
    """Registers database integration tools with the MCP server."""

    def __init__(self, mcp_server, db_integration):
        """
        Initialize the database tool registrar.

        Args:
            mcp_server: FastMCP server instance
            db_integration: Database integration module
        """
        self.mcp = mcp_server
        self.db = db_integration

    def register_all(self):
        """Register all database tools."""
        self._register_list_experiments()
        self._register_get_dataset_info()
        self._register_get_database_stats()
        self._register_list_available_databases()

    def _register_list_experiments(self):
        """Register the database/list_experiments tool."""

        @self.mcp.tool(name="database_list_experiments")
        async def list_experiments(
            database_path: Optional[str] = None,
        ) -> List[TextContent]:
            """List all experiments in the specified QCodes database.

            Args:
                database_path: Path to database file. If None, uses MeasureIt
                    default or QCodes config.

            Returns JSON containing experiment information including ID, name,
            sample name, and format string for each experiment.
            """
            try:
                result = self.db.list_experiments(database_path=database_path)
                return [TextContent(type="text", text=result)]
            except Exception as e:
                logger.error(f"Error in list_experiments: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_dataset_info(self):
        """Register the database/get_dataset_info tool."""

        @self.mcp.tool(name="database_get_dataset_info")
        async def get_dataset_info(
            id: int, database_path: Optional[str] = None
        ) -> List[TextContent]:
            """Get detailed information about a specific dataset.

            Args:
                id: Dataset run ID to load (e.g., load_by_id(2))
                database_path: Path to database file. If None, uses MeasureIt
                    default or QCodes config.
            """
            try:
                result = self.db.get_dataset_info(id=id, database_path=database_path)
                return [TextContent(type="text", text=result)]
            except Exception as e:
                logger.error(f"Error in database/get_dataset_info: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_database_stats(self):
        """Register the database/get_database_stats tool."""

        @self.mcp.tool(name="database_get_database_stats")
        async def get_database_stats(
            database_path: Optional[str] = None,
        ) -> List[TextContent]:
            """Get database statistics and health information.

            Args:
                database_path: Path to database file. If None, uses MeasureIt
                    default or QCodes config.

            Returns JSON containing database statistics including path, size,
            experiment count, dataset count, and last modified time.
            """
            try:
                result = self.db.get_database_stats(database_path=database_path)
                return [TextContent(type="text", text=result)]
            except Exception as e:
                logger.error(f"Error in database/get_database_stats: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_list_available_databases(self):
        """Register the database_list_available tool."""

        @self.mcp.tool(name="database_list_available")
        async def list_available_databases() -> List[TextContent]:
            """List all available QCodes databases.

            Searches common locations including MeasureIt databases directory
            and QCodes configuration paths.

            Returns JSON containing available databases with metadata including
            name, path, size, source, and experiment count.
            """
            try:
                result = self.db.list_available_databases()
                return [TextContent(type="text", text=result)]
            except Exception as e:
                logger.error(f"Error in database_list_available: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
