"""
Database integration tool registrar.

Registers tools for querying QCodes databases (optional feature).
"""

import json
import logging
from typing import List, Optional

from mcp.types import TextContent

from .database_internal import generate_code_suggestion, analyze_sweep_groups

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

    # ===== Concise mode helpers =====

    def _to_concise_list_experiments(self, data: dict) -> dict:
        """Convert full experiments list to concise format.

        Concise: database_path and only experiment names.
        Preserves error field if present.
        """
        experiments = data.get("experiments", [])
        result = {
            "database_path": data.get("database_path"),
            "experiments": [exp.get("name", "") for exp in experiments],
            "count": len(experiments),
        }
        if "error" in data:
            result["error"] = data["error"]
        return result

    def _to_concise_dataset_info(self, data: dict) -> dict:
        """Convert full dataset info to concise format.

        Concise: id, name, sample, metadata.
        Preserves error field if present.
        """
        basic_info = data.get("basic_info", {})
        exp_info = data.get("experiment_info", {})
        result = {
            "id": basic_info.get("run_id"),
            "name": basic_info.get("name"),
            "sample": exp_info.get("sample_name"),
            "metadata": data.get("metadata", {}),
        }
        if "error" in data:
            result["error"] = data["error"]
        return result

    def _to_concise_list_available(self, data: dict) -> dict:
        """Convert full database list to concise format.

        Concise: only database names and paths.
        Preserves error field if present.
        """
        databases = data.get("databases", [])
        result = {
            "databases": [
                {"name": db.get("name"), "path": db.get("path")} for db in databases
            ],
            "count": len(databases),
        }
        if "error" in data:
            result["error"] = data["error"]
        return result

    def _generate_code_suggestion(self, data: dict) -> str:
        """Generate comprehensive code example for retrieving the dataset.

        Uses the database_internal module which provides sweep-type-aware
        code generation with automatic grouping of related sweeps.
        """
        database_path = data.get("database_path", "")
        basic_info = data.get("basic_info", {})
        run_id = basic_info.get("run_id", 1)

        try:
            # Use the new comprehensive code generation
            result = generate_code_suggestion(
                database_path=database_path,
                run_id=run_id,
                include_groups=True,
            )
            return result.get("code_by_run_id", {}).get(
                run_id, self._generate_fallback_code(data)
            )
        except Exception as e:
            logger.warning(f"Comprehensive code generation failed: {e}")
            return self._generate_fallback_code(data)

    def _generate_fallback_code(self, data: dict) -> str:
        """Generate basic fallback code when sweep type cannot be determined."""
        database_path = data.get("database_path", "")
        basic_info = data.get("basic_info", {})
        run_id = basic_info.get("run_id", 1)
        parameter_data = data.get("parameter_data", {})

        # Build parameter extraction code from nested structure
        param_code_lines = []
        for outer_key, inner_dict in parameter_data.items():
            if isinstance(inner_dict, dict):
                for inner_key in inner_dict.keys():
                    var_name = inner_key.replace(".", "_")
                    param_code_lines.append(
                        f'{var_name} = d["{outer_key}"]["{inner_key}"]'
                    )

        param_code = (
            "\n".join(param_code_lines) if param_code_lines else "# No parameters"
        )

        return f"""from qcodes.dataset import load_by_id
from qcodes.dataset.sqlite.database import initialise_or_create_database_at

db = "{database_path}"
initialise_or_create_database_at(db)

ds = load_by_id({run_id})
d = ds.get_parameter_data()

# Extract parameter arrays:
{param_code}
"""

    # ===== End concise mode helpers =====

    def register_all(self):
        """Register all database tools."""
        self._register_list_experiments()
        self._register_get_dataset_info()
        self._register_get_database_stats()
        self._register_list_available_databases()

    def _register_list_experiments(self):
        """Register the database/list_experiments tool."""

        @self.mcp.tool(
            name="database_list_experiments",
            annotations={
                "title": "List Experiments",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_experiments(
            database_path: Optional[str] = None,
            detailed: bool = False,
        ) -> List[TextContent]:
            """List all experiments in the specified QCodes database.

            Args:
                database_path: Path to database file. If None, uses MeasureIt
                    default or QCodes config.
                detailed: If False (default), return concise summary; if True, return full info

            Returns JSON containing experiment information including ID, name,
            sample name, and format string for each experiment.
            """
            try:
                result_str = self.db.list_experiments(database_path=database_path)
                result = json.loads(result_str)

                # Detect sweep groups (Sweep2D parent, SweepQueue batches)
                db_path = result.get("database_path")
                if db_path:
                    try:
                        groups = analyze_sweep_groups(db_path)
                        # Filter to only show multi-run groups
                        grouped = [
                            {
                                "type": g.group_type,
                                "sweep_type": g.sweep_type.value,
                                "run_ids": g.run_ids,
                                "description": g.description,
                            }
                            for g in groups
                            if len(g.run_ids) > 1
                        ]
                        if grouped:
                            result["sweep_groups"] = grouped
                    except Exception as e:
                        logger.debug(f"Could not analyze sweep groups: {e}")

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_list_experiments(result)

                # Add hint for data loading templates
                result["hint"] = (
                    "For dataset loading code, use database_get_dataset_info with "
                    "code_suggestion=True, or fetch resource://database_access{0d,1d,2d}_template"
                )

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in list_experiments: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_dataset_info(self):
        """Register the database/get_dataset_info tool."""

        @self.mcp.tool(
            name="database_get_dataset_info",
            annotations={
                "title": "Get Dataset Info",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_dataset_info(
            id: int,
            database_path: Optional[str] = None,
            detailed: bool = False,
            code_suggestion: bool = False,
        ) -> List[TextContent]:
            """Get detailed information about a specific dataset.

            Args:
                id: Dataset run ID to load (e.g., load_by_id(2))
                database_path: Path to database file. If None, uses MeasureIt
                    default or QCodes config.
                detailed: If False (default), return concise summary; if True, return full info
                code_suggestion: If True, include Python code example for loading the dataset
            """
            try:
                result_str = self.db.get_dataset_info(
                    id=id, database_path=database_path
                )
                result = json.loads(result_str)

                # Add code suggestion if requested
                if code_suggestion:
                    result["code_suggestion"] = self._generate_code_suggestion(result)

                # Apply concise mode filtering
                if not detailed:
                    concise = self._to_concise_dataset_info(result)
                    # Preserve code_suggestion in concise mode if it was requested
                    if code_suggestion:
                        concise["code_suggestion"] = result["code_suggestion"]
                    result = concise

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in database/get_dataset_info: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    def _register_get_database_stats(self):
        """Register the database/get_database_stats tool."""

        @self.mcp.tool(
            name="database_get_database_stats",
            annotations={
                "title": "Database Statistics",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
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

        @self.mcp.tool(
            name="database_list_available",
            annotations={
                "title": "List Databases",
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_available_databases(
            detailed: bool = False,
        ) -> List[TextContent]:
            """List all available QCodes databases.

            Searches common locations including MeasureIt databases directory
            and QCodes configuration paths.

            Args:
                detailed: If False (default), return only database names and paths;
                    if True, return full info including size, source, experiment count.

            Returns JSON containing available databases.
            """
            try:
                result_str = self.db.list_available_databases()
                result = json.loads(result_str)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_list_available(result)

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in database_list_available: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
