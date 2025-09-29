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
        self._register_apply_patch()

    def _register_execute_cell(self):
        """Register the notebook/execute_cell tool."""

        @self.mcp.tool(name="notebook/execute_cell")
        async def execute_editing_cell() -> List[TextContent]:
            """Execute the currently editing cell in the JupyterLab frontend.

            UNSAFE: This tool executes code in the active notebook cell. Only available in unsafe mode.
            The code will run in the frontend with output appearing in the notebook.
            """
            try:
                result = await self.tools.execute_editing_cell()
                return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            except Exception as e:
                logger.error(f"Error in notebook/execute_cell: {e}")
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    def _register_add_cell(self):
        """Register the notebook/add_cell tool."""

        @self.mcp.tool(name="notebook/add_cell")
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

        @self.mcp.tool(name="notebook/delete_cell")
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

    def _register_apply_patch(self):
        """Register the notebook/apply_patch tool."""

        @self.mcp.tool(name="notebook/apply_patch")
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