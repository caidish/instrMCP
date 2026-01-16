"""
Database integration tool registrar.

Registers tools for querying QCodes databases (optional feature).
"""

import json
import logging
from typing import List, Optional

from mcp.types import TextContent

from .internal import generate_code_suggestion, analyze_sweep_groups

logger = logging.getLogger(__name__)


class DatabaseToolRegistrar:
    """Registers database integration tools with the MCP server."""

    def __init__(
        self,
        mcp_server,
        db_integration,
        tools=None,
        safe_mode=True,
    ):
        """
        Initialize the database tool registrar.

        Args:
            mcp_server: FastMCP server instance
            db_integration: Database integration module
            tools: QCodesReadOnlyTools instance (for cell operations in unsafe mode)
            safe_mode: Whether server is in safe mode (read-only)
        """
        self.mcp = mcp_server
        self.db = db_integration
        self.tools = tools
        self.safe_mode = safe_mode

    # ===== Concise mode helpers =====

    def _format_run_ids_concise(self, run_ids: list | str) -> str:
        """Format run_ids list concisely.

        For small lists (<=5): show all, e.g., "1, 2, 3"
        For larger lists: show range, e.g., "1-1000 (1000 runs)"
        """
        if not run_ids:
            return ""
        if isinstance(run_ids, str):
            return run_ids
        if len(run_ids) <= 5:
            return ",".join(str(r) for r in run_ids)
        return f"{min(run_ids)}-{max(run_ids)}({len(run_ids)})"

    def _to_concise_list_experiments(self, data: dict) -> dict:
        """Convert full experiments list to concise format.

        Concise: database_path, experiments with run_ids summary, and sweep groups.
        If experiments exceed 10, return only sweep groups with a warning.
        Preserves error field if present.
        """
        experiments = data.get("experiments", [])
        if len(experiments) > 10:
            result = {}
            sweep_groups = data.get("sweep_groups", [])
            if sweep_groups:
                result["sweep_groups"] = [
                    f"{g['type']}: {self._format_run_ids_concise(g['run_ids'])}"
                    for g in sweep_groups
                ]
            result["warning"] = (
                "large number of experiment, truncated. "
                "See code template and write code to query."
            )
            if "error" in data:
                result["error"] = data["error"]
            return result
        result = {
            "database_path": data.get("database_path"),
            "experiments": [
                {
                    "name": exp.get("name", ""),
                    "run_ids": self._format_run_ids_concise(exp.get("run_ids", [])),
                }
                for exp in experiments
            ],
            "count": len(experiments),
        }
        # Include concise sweep groups: "type: run_ids_summary"
        sweep_groups = data.get("sweep_groups", [])
        if sweep_groups:
            result["sweep_groups"] = [
                f"{g['type']}: {self._format_run_ids_concise(g['run_ids'])}"
                for g in sweep_groups
            ]
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
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_experiments(
            database_path: Optional[str] = None,
            detailed: bool = False,
            scan_nested: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            try:
                result_str = self.db.list_experiments(
                    database_path=database_path,
                    scan_nested=scan_nested,
                )
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

                if "warning" not in result:
                    # Add hint for data loading code
                    result["hint"] = (
                        "For dataset loading code, use database_get_dataset_info "
                        "with code_suggestion=True. For groups, only one run_id is needed."
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
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_dataset_info(
            id: int,
            database_path: Optional[str] = None,
            detailed: bool = False,
            code_suggestion: bool = True,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            try:
                result_str = self.db.get_dataset_info(
                    id=id, database_path=database_path
                )
                result = json.loads(result_str)

                # Generate code suggestion if requested
                if code_suggestion:
                    code = self._generate_code_suggestion(result)

                    # In unsafe mode with tools available: auto-execute
                    if not self.safe_mode and self.tools is not None:
                        exec_result = await self._auto_execute_code(code)
                        # Apply concise mode filtering first
                        if not detailed:
                            result = self._to_concise_dataset_info(result)
                        # Replace code_suggestion with execution result
                        result["code_executed"] = exec_result
                    else:
                        # Safe mode: just return code suggestion
                        result["code_suggestion"] = code
                        if not detailed:
                            concise = self._to_concise_dataset_info(result)
                            concise["code_suggestion"] = code
                            result = concise
                else:
                    # No code suggestion requested
                    if not detailed:
                        result = self._to_concise_dataset_info(result)

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in database/get_dataset_info: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]

    async def _auto_execute_code(self, code: str) -> dict:
        # Description loaded from metadata_baseline.yaml
        try:
            # 1. Add new cell with the code
            add_result = await self.tools.add_new_cell(
                cell_type="code", position="below", content=code
            )

            if not add_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to add cell",
                    "details": add_result,
                }

            # 2. Execute the cell
            exec_result = await self.tools.execute_editing_cell(timeout=30.0)

            # 3. Extract output from various possible fields
            cell_output = self._extract_cell_output(exec_result)

            if exec_result.get("status") == "completed":
                return {
                    "success": True,
                    "message": "Code added to notebook cell and executed successfully",
                    "cell_content": code,
                    "cell_output": cell_output,
                    "has_error": exec_result.get("has_error", False),
                }
            elif exec_result.get("status") == "error":
                return {
                    "success": False,
                    "message": "Code added but execution encountered an error",
                    "cell_content": code,
                    "cell_output": cell_output,
                    "error_type": exec_result.get("error_type", ""),
                    "error_message": exec_result.get("error_message", ""),
                    "suggestion": "Please check the cell and fix the error",
                }
            else:
                return {
                    "success": False,
                    "message": "Code added but execution failed or timed out",
                    "cell_content": code,
                    "error": exec_result.get("error", exec_result.get("message", "")),
                    "suggestion": "Please check the cell and revise the code if needed",
                }

        except Exception as e:
            logger.error(f"Error in _auto_execute_code: {e}")
            return {
                "success": False,
                "error": str(e),
                "cell_content": code,
                "suggestion": "Auto-execution failed. Please add the code manually.",
            }

    def _extract_cell_output(self, exec_result: dict) -> str:
        """Extract text output from execution result.

        Args:
            exec_result: Result from execute_editing_cell

        Returns:
            String representation of output
        """
        # Check for direct output string (from Out cache)
        if exec_result.get("output"):
            return str(exec_result["output"])

        # Check for outputs array (from frontend)
        outputs = exec_result.get("outputs", [])
        if not outputs:
            return ""

        # Extract text from outputs
        text_parts = []
        for output in outputs:
            output_type = output.get("type", "")

            if output_type == "stream":
                # stdout/stderr
                text_parts.append(output.get("text", ""))
            elif output_type == "execute_result":
                # Expression result
                data = output.get("data", {})
                if "text/plain" in data:
                    text_parts.append(data["text/plain"])
            elif output_type == "display_data":
                # Display output
                data = output.get("data", {})
                if "text/plain" in data:
                    text_parts.append(data["text/plain"])
            elif output_type == "error":
                # Error output
                text_parts.append(
                    f"{output.get('ename', 'Error')}: {output.get('evalue', '')}"
                )

        return "\n".join(text_parts)

    def _register_get_database_stats(self):
        """Register the database/get_database_stats tool."""

        @self.mcp.tool(
            name="database_get_database_stats",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def get_database_stats(
            database_path: Optional[str] = None,
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
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
        """Register the database_list_all_available_db tool."""

        @self.mcp.tool(
            name="database_list_all_available_db",
            annotations={
                "readOnlyHint": True,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )
        async def list_available_databases(
            detailed: bool = False,
        ) -> List[TextContent]:
            # Description loaded from metadata_baseline.yaml
            try:
                result_str = self.db.list_available_databases()
                result = json.loads(result_str)

                # Apply concise mode filtering
                if not detailed:
                    result = self._to_concise_list_available(result)

                return [TextContent(type="text", text=json.dumps(result, indent=2))]
            except Exception as e:
                logger.error(f"Error in database_list_all_available_db: {e}")
                return [
                    TextContent(
                        type="text", text=json.dumps({"error": str(e)}, indent=2)
                    )
                ]
