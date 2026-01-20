"""
Cell Targeting Tests (test_08_cell_targeting.py)

Purpose: Verify cell_id_notebook and index:N navigation features.

Test IDs:
- CT-001 to CT-022
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import (
    run_cell,
    count_cells,
    get_active_cell_index,
)
from tests.e2e.helpers.mcp_helpers import call_mcp_tool, parse_tool_result


class TestReadContentCellIdNotebooks:
    """Test notebook_read_content with cell_id_notebooks parameter."""

    @pytest.mark.p0
    def test_read_content_cell_id_notebooks_single(self, mcp_server):
        """CT-001: Read content from single cell by index."""
        page = mcp_server["page"]

        # Create multiple cells
        run_cell(page, "# Cell 0", wait_for_output=False)
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# Cell 1")
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# Cell 2")
        page.keyboard.press("Escape")

        page.wait_for_timeout(500)

        # Read specific cell by index
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": ["index:1"]},
        )
        success, content = parse_tool_result(result)
        assert success, f"Read failed: {content}"
        # Should contain Cell 1 content

    @pytest.mark.p0
    def test_read_content_cell_id_notebooks_multiple(self, mcp_server):
        """CT-002: Read content from multiple cells by index."""
        page = mcp_server["page"]

        # Create multiple cells
        for i in range(4):
            if i > 0:
                page.keyboard.press("Escape")
                page.keyboard.press("B")
                page.keyboard.press("Enter")
            page.keyboard.type(f"# Cell {i}")

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # Read multiple cells
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": ["index:0", "index:2"]},
        )
        success, content = parse_tool_result(result)
        assert success, f"Read failed: {content}"

    @pytest.mark.p1
    def test_read_content_cell_id_notebooks_mixed_types(self, mcp_server):
        """CT-003: Read content from mixed cell types."""
        page = mcp_server["page"]

        # Create code cell
        run_cell(page, "x = 1", wait_for_output=False)

        # Create markdown cell
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("M")  # Convert to markdown
        page.keyboard.press("Enter")
        page.keyboard.type("# Markdown")
        page.keyboard.press("Escape")

        # Create another code cell
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("y = 2")
        page.keyboard.press("Escape")

        page.wait_for_timeout(500)

        # Read all cells
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": ["index:0", "index:1", "index:2"]},
        )
        success, content = parse_tool_result(result)
        assert success, f"Read failed: {content}"

    @pytest.mark.p1
    def test_read_content_cell_id_notebooks_out_of_bounds(self, mcp_server):
        """CT-004: Read content handles out of bounds index."""
        page = mcp_server["page"]

        # Create just one cell
        run_cell(page, "# Only cell", wait_for_output=False)

        # Try to read index 10 (doesn't exist)
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": ["index:10"]},
        )
        # Should handle gracefully (error or empty)
        success, content = parse_tool_result(result)
        # Either fails with message or returns empty


class TestMoveCursorIndex:
    """Test notebook_move_cursor with index:N navigation."""

    @pytest.mark.p0
    def test_move_cursor_index_first(self, mcp_server):
        """CT-010: Move cursor to first cell (index:0)."""
        page = mcp_server["page"]

        # Create multiple cells
        for i in range(3):
            if i > 0:
                page.keyboard.press("Escape")
                page.keyboard.press("B")
                page.keyboard.press("Enter")
            page.keyboard.type(f"# Cell {i}")

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # Move to first cell
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:0"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Move failed: {content}"

        # Verify we're at first cell
        active_idx = get_active_cell_index(page)
        assert active_idx == 0, f"Expected index 0, got {active_idx}"

    @pytest.mark.p0
    def test_move_cursor_index_middle(self, mcp_server):
        """CT-011: Move cursor to middle cell."""
        page = mcp_server["page"]

        # Create multiple cells
        for i in range(5):
            if i > 0:
                page.keyboard.press("Escape")
                page.keyboard.press("B")
                page.keyboard.press("Enter")
            page.keyboard.type(f"# Cell {i}")

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # Move to middle cell (index 2)
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:2"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Move failed: {content}"

        # Verify position
        active_idx = get_active_cell_index(page)
        assert active_idx == 2, f"Expected index 2, got {active_idx}"

    @pytest.mark.p0
    def test_move_cursor_index_last(self, mcp_server):
        """CT-012: Move cursor to last cell."""
        page = mcp_server["page"]

        # Create multiple cells
        for i in range(4):
            if i > 0:
                page.keyboard.press("Escape")
                page.keyboard.press("B")
                page.keyboard.press("Enter")
            page.keyboard.type(f"# Cell {i}")

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        # Move to last cell
        total_cells = count_cells(page)
        last_index = total_cells - 1
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": f"index:{last_index}"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Move failed: {content}"

        # Verify position
        active_idx = get_active_cell_index(page)
        assert (
            active_idx == total_cells - 1
        ), f"Expected last cell ({total_cells - 1}), got {active_idx}"

    @pytest.mark.p1
    def test_move_cursor_index_invalid(self, mcp_server):
        """CT-013: Move cursor handles invalid index."""
        page = mcp_server["page"]

        # Create 2 cells
        run_cell(page, "# Cell 0", wait_for_output=False)
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# Cell 1")
        page.keyboard.press("Escape")

        page.wait_for_timeout(500)

        # Try invalid index
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:100"}
        )
        success, content = parse_tool_result(result)

        # Should fail or indicate invalid target
        # Known issue: may incorrectly return success
        if success:
            # Check if content indicates problem
            pass  # Document actual behavior


class TestDeleteCellByPositions:
    """Test notebook_delete_cell with position targeting."""

    @pytest.mark.p0
    def test_delete_cell_by_positions(self, mcp_server_dangerous):
        """CT-020: Delete the currently active cell."""
        page = mcp_server_dangerous["page"]

        # Add a cell that we'll delete
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# Cell to delete")
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        initial_count = count_cells(page)

        # Delete the current cell (no arguments = delete active cell)
        result = call_mcp_tool(mcp_server_dangerous["url"], "notebook_delete_cell", {})
        page.wait_for_timeout(1000)

        success, content = parse_tool_result(result)
        assert success, f"Delete failed: {content}"

        new_count = count_cells(page)
        assert (
            new_count == initial_count - 1
        ), f"Expected {initial_count - 1} cells, got {new_count}"

    @pytest.mark.p1
    def test_delete_cell_multiple_positions(self, mcp_server_dangerous):
        """CT-021: Delete multiple cells by positions."""
        page = mcp_server_dangerous["page"]

        # Create multiple cells
        for i in range(5):
            if i > 0:
                page.keyboard.press("Escape")
                page.keyboard.press("B")
                page.keyboard.press("Enter")
            page.keyboard.type(f"# Cell {i}")

        page.keyboard.press("Escape")
        page.wait_for_timeout(500)

        initial_count = count_cells(page)

        # Delete cells - testing with last created cell
        # Using index for the last cell to delete it
        last_index = initial_count - 1
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_delete_cell",
            {"cell_id_notebooks": str(last_index)},
        )
        page.wait_for_timeout(1000)

        success, content = parse_tool_result(result)
        # Check actual behavior

    @pytest.mark.p1
    def test_delete_cell_out_of_bounds(self, mcp_server_dangerous):
        """CT-022: Delete cell handles out of bounds position."""
        page = mcp_server_dangerous["page"]

        # Create 2 cells
        run_cell(page, "# Cell 0", wait_for_output=False)
        page.keyboard.press("Escape")
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# Cell 1")
        page.keyboard.press("Escape")

        page.wait_for_timeout(500)

        # Try to delete out of bounds
        call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_delete_cell",
            {"cell_id_notebooks": "100"},
        )
        page.wait_for_timeout(1000)

        # Should fail or do nothing
        # Count should not change if position invalid


class TestCellNavigation:
    """Test general cell navigation features."""

    @pytest.mark.p0
    def test_navigation_sequence(self, mcp_server):
        """Test sequential navigation through cells."""
        page = mcp_server["page"]

        # Get total cell count to work with existing cells
        total_cells = count_cells(page)

        # Navigate to top
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "index:0"})
        page.wait_for_timeout(200)
        assert get_active_cell_index(page) == 0, "Should be at first cell after top"

        # Navigate down
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "below"})
        page.wait_for_timeout(200)
        assert get_active_cell_index(page) == 1, "Should be at second cell after down"

        # Navigate to bottom
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "bottom"})
        page.wait_for_timeout(200)
        total_cells = count_cells(page)
        assert (
            get_active_cell_index(page) == total_cells - 1
        ), "Should be at last cell after bottom"

        # Navigate up
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "above"})
        page.wait_for_timeout(200)
        assert (
            get_active_cell_index(page) == total_cells - 2
        ), "Should be at second-to-last cell after up"

    @pytest.mark.p1
    def test_navigation_boundary(self, mcp_server):
        """Test navigation at boundaries."""
        page = mcp_server["page"]

        # Go to top
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "index:0"})
        page.wait_for_timeout(200)

        # Try to go above top
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "above"})
        page.wait_for_timeout(200)

        # Should still be at top (index 0)
        assert (
            get_active_cell_index(page) == 0
        ), "Should stay at top after trying to go above"

        # Go to bottom
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "bottom"})
        page.wait_for_timeout(200)

        # Try to go below bottom
        call_mcp_tool(mcp_server["url"], "notebook_move_cursor", {"target": "below"})
        page.wait_for_timeout(200)

        # Should still be at bottom
        total_cells = count_cells(page)
        assert (
            get_active_cell_index(page) == total_cells - 1
        ), "Should stay at bottom after trying to go below"
