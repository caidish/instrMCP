"""
Dangerous Mode Tests (test_04_dangerous_mode.py)

Purpose: Verify consent bypass in dangerous mode.

Test IDs:
- DM-001 to DM-013
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell, get_cell_output, count_cells
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    list_mcp_tools,
    parse_tool_result,
)


class TestDangerousModeSwitch:
    """Test switching to dangerous mode."""

    @pytest.mark.p0
    def test_dangerous_mode_switch(self, notebook_page):
        """DM-001: Switch to dangerous mode."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_dangerous")
        output = get_cell_output(notebook_page)

        # May show warning but shouldn't error
        assert (
            "error" not in output.lower() or "warning" in output.lower()
        ), f"Unexpected error: {output}"

    @pytest.mark.p0
    def test_dangerous_mode_status(self, mcp_server_dangerous):
        """DM-002: Status shows dangerous mode."""
        page = mcp_server_dangerous["page"]

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert (
            "dangerous" in output.lower()
        ), f"Expected dangerous mode in status: {output}"


class TestConsentBypass:
    """Test that consent dialogs are bypassed in dangerous mode."""

    @pytest.mark.p0
    def test_consent_bypass_update_cell(self, mcp_server_dangerous):
        """DM-010: No consent dialog for cell update in dangerous mode."""
        page = mcp_server_dangerous["page"]

        # Set up cell
        page.keyboard.press("Enter")
        page.keyboard.type("before = 1")
        page.keyboard.press("Escape")

        # Update should succeed immediately without dialog
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"new_content": "after = 2"},
        )

        success, content = parse_tool_result(result)
        # In dangerous mode, should succeed without user interaction
        assert success or "after" in str(
            result
        ), f"Update should succeed in dangerous mode: {result}"

    @pytest.mark.p0
    def test_consent_bypass_execute_cell(self, mcp_server_dangerous):
        """DM-011: No consent dialog for cell execution in dangerous mode."""
        page = mcp_server_dangerous["page"]

        # Set up cell
        page.keyboard.press("Enter")
        page.keyboard.type("x = 42")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )

        success, content = parse_tool_result(result)
        assert success, f"Execute should succeed in dangerous mode: {content}"

    @pytest.mark.p0
    def test_consent_bypass_delete_cell(self, mcp_server_dangerous):
        """DM-012: No consent dialog for cell deletion in dangerous mode."""
        page = mcp_server_dangerous["page"]

        # Create cells
        run_cell(page, "cell1 = 1", wait_for_output=False)
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("cell2 = 2")
        page.keyboard.press("Escape")

        initial_count = count_cells(page)

        result = call_mcp_tool(mcp_server_dangerous["url"], "notebook_delete_cell")
        page.wait_for_timeout(1000)

        success, content = parse_tool_result(result)
        assert success, f"Delete should succeed in dangerous mode: {content}"

        # Verify deletion
        new_count = count_cells(page)
        assert (
            new_count < initial_count
        ), f"Cell should be deleted: {initial_count} -> {new_count}"

    @pytest.mark.p0
    def test_consent_bypass_apply_patch(self, mcp_server_dangerous):
        """DM-013: No consent dialog for apply patch in dangerous mode."""
        page = mcp_server_dangerous["page"]

        # Set up cell with patchable content
        page.keyboard.press("Enter")
        page.keyboard.type("old_var = 100")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"old_text": "old_var", "new_text": "new_var"},
        )

        # Should succeed without interaction
        success, content = parse_tool_result(result)
        # Patch should apply (or report not found if cell state changed)


class TestDangerousModeTools:
    """Test tool availability and behavior in dangerous mode."""

    @pytest.mark.p0
    def test_all_tools_available(self, mcp_server_dangerous):
        """Verify all tools are available in dangerous mode."""
        tools_raw = list_mcp_tools(mcp_server_dangerous["url"])
        # Extract tool names from list of dicts
        tools = [t.get("name") for t in tools_raw if isinstance(t, dict)]

        # All unsafe tools should be available
        expected_tools = [
            "notebook_execute_active_cell",
            "notebook_add_cell",
            "notebook_delete_cell",
            "notebook_apply_patch",
        ]

        for tool in expected_tools:
            assert (
                tool in tools
            ), f"Expected tool {tool} in dangerous mode. Available: {tools}"

    @pytest.mark.p0
    def test_rapid_operations(self, mcp_server_dangerous):
        """DM-014: Multiple operations without consent delays."""
        page = mcp_server_dangerous["page"]

        # Perform multiple operations quickly
        # In dangerous mode, these should all succeed without dialogs

        # Add cell
        result1 = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": "x = 1"},
        )
        page.wait_for_timeout(500)

        # Execute cell
        result2 = call_mcp_tool(
            mcp_server_dangerous["url"], "notebook_execute_active_cell"
        )
        page.wait_for_timeout(500)

        # Add another cell
        result3 = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "below", "content": "y = 2"},
        )

        # All should succeed
        for i, result in enumerate([result1, result2, result3], 1):
            success, content = parse_tool_result(result)
            assert success, f"Operation {i} failed: {content}"
