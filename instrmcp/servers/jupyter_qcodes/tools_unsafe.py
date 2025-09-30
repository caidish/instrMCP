"""
Unsafe mode tools for Jupyter MCP server.

These tools allow cell manipulation and code execution in Jupyter notebooks.
They are only available when the server is running in unsafe mode.
"""

import json
import logging
from typing import List

from mcp.types import TextContent

logger = logging.getLogger(__name__)


class UnsafeToolRegistrar:
    """Registers unsafe mode tools with the MCP server."""

    def __init__(self, mcp_server, tools):
        """
        Initialize the unsafe tool registrar.

        Args:
            mcp_server: FastMCP server instance
            tools: QCodesReadOnlyTools instance
        """
        self.mcp = mcp_server
        self.tools = tools

    def register_all(self):
        """Register all unsafe mode tools."""
        self._register_execute_cell()
        self._register_add_cell()
        self._register_delete_cell()
        self._register_delete_cells()
        self._register_apply_patch()

    def _register_execute_cell(self):
        """Register the notebook/execute_cell tool."""

        @self.mcp.tool(name="notebook_execute_cell")
        async def execute_editing_cell() -> List[TextContent]:
            """Execute the currently editing cell in the JupyterLab frontend.

            UNSAFE: This tool executes code in the active notebook cell. Only available in unsafe mode.
            The code will run in the frontend with output appearing in the notebook.

            After execution, use notebook/get_editing_cell_output to retrieve the execution result,
            including any output or errors from the cell.
            """
            try:
                result = await self.tools.execute_editing_cell()
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/execute_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_add_cell(self):
        """Register the notebook/add_cell tool."""

        @self.mcp.tool(name="notebook_add_cell")
        async def add_new_cell(
            cell_type: str = "code",
            position: str = "below",
            content: str = ""
        ) -> List[TextContent]:
            """Add a new cell in the notebook.

            UNSAFE: This tool adds new cells to the notebook. Only available in unsafe mode.
            The cell will be created relative to the currently active cell.

            Args:
                cell_type: Type of cell to create ("code", "markdown", "raw") - default: "code"
                position: Position relative to active cell ("above", "below") - default: "below"
                content: Initial content for the new cell - default: empty string
            """
            try:
                result = await self.tools.add_new_cell(cell_type, position, content)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/add_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_delete_cell(self):
        """Register the notebook/delete_cell tool."""

        @self.mcp.tool(name="notebook_delete_cell")
        async def delete_editing_cell() -> List[TextContent]:
            """Delete the currently editing cell.

            UNSAFE: This tool deletes the currently active cell from the notebook. Only available in unsafe mode.
            Use with caution as this action cannot be undone easily. If this is the last cell in the notebook,
            a new empty code cell will be created automatically.
            """
            try:
                result = await self.tools.delete_editing_cell()
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/delete_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_delete_cells(self):
        """Register the notebook/delete_cells tool."""

        @self.mcp.tool(name="notebook_delete_cells")
        async def delete_cells_by_number(cell_numbers: str) -> List[TextContent]:
            """Delete multiple cells by their execution count numbers.

            UNSAFE: This tool deletes cells from the notebook by their execution counts.
            Only available in unsafe mode. Use with caution as this action cannot be undone easily.

            Args:
                cell_numbers: JSON string containing a list of execution count numbers to delete.
                             Example: "[1, 2, 5]" to delete cells 1, 2, and 5
                             Can also be a single number: "3"

            Returns:
                JSON with deletion status and detailed results for each cell, including:
                - success: Overall operation success
                - deleted_count: Number of cells actually deleted
                - total_requested: Number of cells requested to delete
                - results: List with status for each cell number
            """
            try:
                # Parse cell_numbers - can be either single int or list
                import json as json_module
                try:
                    parsed = json_module.loads(cell_numbers)
                    if isinstance(parsed, int):
                        cell_list = [parsed]
                    elif isinstance(parsed, list):
                        cell_list = parsed
                    else:
                        return [TextContent(type="text", text=json_module.dumps({
                            "success": False,
                            "error": "cell_numbers must be an integer or list of integers"
                        }, indent=2))]
                except json_module.JSONDecodeError:
                    return [TextContent(type="text", text=json_module.dumps({
                        "success": False,
                        "error": f"Invalid JSON format: {cell_numbers}"
                    }, indent=2))]

                result = await self.tools.delete_cells_by_number(cell_list)
                return [TextContent(type="text", text=json_module.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/delete_cells: {e}")
                return [TextContent(type="text", text=json_module.dumps({"error": str(e)}, indent=2))]

    def _register_apply_patch(self):
        """Register the notebook/apply_patch tool."""

        @self.mcp.tool(name="notebook_apply_patch")
        async def apply_patch(old_text: str, new_text: str) -> List[TextContent]:
            """Apply a patch to the current cell content.

            UNSAFE: This tool modifies the content of the currently active cell. Only available in unsafe mode.
            It replaces the first occurrence of old_text with new_text in the cell content.

            Args:
                old_text: Text to find and replace (cannot be empty)
                new_text: Text to replace with (can be empty to delete text)
            """
            try:
                result = await self.tools.apply_patch(old_text, new_text)
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/apply_patch: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]