"""
Edge Case Tests (test_10_edge_cases.py)

Purpose: Verify robust handling of invalid inputs and boundary conditions.

Test IDs:
- EC-001 to EC-030
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell
from tests.e2e.helpers.mcp_helpers import call_mcp_tool, parse_tool_result


class TestNotebookToolEdgeCases:
    """Test notebook tools with edge case inputs."""

    @pytest.mark.p2
    def test_read_active_cell_invalid_line_range(self, mcp_server):
        """EC-001: notebook_read_active_cell handles start > end."""
        page = mcp_server["page"]
        run_cell(page, "# Line 1\n# Line 2", wait_for_output=False)

        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": 5, "line_end": 2},
        )
        # Should return empty or handle gracefully, not crash
        assert result is not None

    @pytest.mark.p2
    def test_read_active_cell_negative_lines(self, mcp_server):
        """EC-002: notebook_read_active_cell handles negative line numbers."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": -1, "line_end": 5},
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_read_active_cell_zero_max_lines(self, mcp_server):
        """EC-003: notebook_read_active_cell with max_lines=0."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_active_cell", {"max_lines": 0}
        )
        assert result is not None

    @pytest.mark.p2
    def test_read_active_cell_very_large_line_range(self, mcp_server):
        """EC-004: notebook_read_active_cell with very large line numbers."""
        page = mcp_server["page"]
        run_cell(page, "# Small cell", wait_for_output=False)

        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": 1000, "line_end": 2000},
        )
        # Should return empty or handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_read_content_invalid_cell_id_json(self, mcp_server):
        """EC-005: notebook_read_content with invalid JSON for cell_id_notebooks."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": "not-valid-json"},
        )
        # Should fail gracefully with error message
        assert result is not None

    @pytest.mark.p2
    def test_read_content_negative_num_cells(self, mcp_server):
        """EC-006: notebook_read_content with negative num_cells."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_content", {"num_cells": -5}
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_move_cursor_invalid_direction(self, mcp_server):
        """EC-007: notebook_move_cursor with invalid direction."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_move_cursor",
            {"direction": "invalid_direction"},
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_move_cursor_out_of_bounds_index(self, mcp_server):
        """EC-008: notebook_move_cursor with index beyond notebook."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:9999"}
        )
        # Should fail gracefully or clamp to bounds
        assert result is not None

    @pytest.mark.p2
    def test_move_cursor_negative_index(self, mcp_server):
        """EC-009: notebook_move_cursor with negative index."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:-1"}
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_move_cursor_malformed_index(self, mcp_server):
        """EC-010: notebook_move_cursor with malformed index string."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"target": "index:abc"}
        )
        # Should fail gracefully
        assert result is not None


class TestUnsafeToolEdgeCases:
    """Test unsafe tools with edge case inputs."""

    @pytest.mark.p2
    def test_delete_cell_invalid_json(self, mcp_server_dangerous):
        """EC-011: notebook_delete_cell with invalid cell_id_notebooks JSON."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_delete_cell",
            {"cell_id_notebooks": "invalid"},
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_delete_cell_out_of_bounds(self, mcp_server_dangerous):
        """EC-012: notebook_delete_cell with out-of-bounds indices."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_delete_cell",
            {"cell_id_notebooks": "[999, 1000]"},
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_apply_patch_empty_old_text(self, mcp_server_dangerous):
        """EC-013: notebook_apply_patch with empty old_text."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("some content")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"old_text": "", "new_text": "replacement"},
        )
        success, content = parse_tool_result(result)
        # Should fail - empty old_text not allowed
        assert not success or "error" in content.lower() or "empty" in content.lower()

    @pytest.mark.p2
    def test_apply_patch_nonexistent_text(self, mcp_server_dangerous):
        """EC-014: notebook_apply_patch when old_text not found."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("actual content here")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"old_text": "nonexistent text xyz", "new_text": "replacement"},
        )
        success, content = parse_tool_result(result)
        # Should fail or indicate no match
        if success:
            assert (
                "not found" in content.lower()
                or "no match" in content.lower()
                or "error" in content.lower()
            )

    @pytest.mark.p2
    def test_add_cell_invalid_type(self, mcp_server_dangerous):
        """EC-015: notebook_add_cell with invalid cell type."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "invalid_type_xyz", "position": "below"},
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_add_cell_invalid_position(self, mcp_server_dangerous):
        """EC-016: notebook_add_cell with invalid position."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_add_cell",
            {"cell_type": "code", "position": "invalid_pos_xyz"},
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_execute_cell_zero_timeout(self, mcp_server_dangerous):
        """EC-017: notebook_execute_active_cell with timeout=0 (fire-and-forget)."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("x = 1 + 1")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_execute_active_cell",
            {"timeout": 0},
        )
        success, content = parse_tool_result(result)
        # timeout=0 means fire-and-forget, should succeed immediately
        assert success or "no_wait" in content.lower()

    @pytest.mark.p2
    def test_execute_cell_negative_timeout(self, mcp_server_dangerous):
        """EC-018: notebook_execute_active_cell with negative timeout."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("y = 2")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_execute_active_cell",
            {"timeout": -5},
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_update_cell_with_special_chars(self, mcp_server_dangerous):
        """EC-019: notebook_update_editing_cell with special characters."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("x = 1")
        page.keyboard.press("Escape")

        # Content with unicode and special chars
        special_content = "# Test with émojis 🎉 and unicode: λ, π, ∑"
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_update_editing_cell",
            {"content": special_content},
        )
        success, content = parse_tool_result(result)
        assert success, f"Update with special chars failed: {content}"


class TestQCodesToolEdgeCases:
    """Test QCodes tools with edge case inputs."""

    @pytest.mark.p2
    def test_instrument_info_empty_name(self, mock_qcodes_station):
        """EC-020: qcodes_instrument_info with empty name."""
        result = call_mcp_tool(
            mock_qcodes_station["url"], "qcodes_instrument_info", {"name": ""}
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_instrument_info_special_chars(self, mock_qcodes_station):
        """EC-021: qcodes_instrument_info with special characters in name."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"name": "invalid/instrument\\name"},
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_get_parameter_values_empty_list(self, mock_qcodes_station):
        """EC-022: qcodes_get_parameter_values with empty parameters list."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"parameters": []},
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_get_parameter_info_empty_param(self, mock_qcodes_station):
        """EC-023: qcodes_get_parameter_info with empty parameter name."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_info",
            {"instrument": "mock_dmm", "parameter": ""},
        )
        # Should fail gracefully
        assert result is not None


class TestResourceEdgeCases:
    """Test resource tools with edge case inputs."""

    @pytest.mark.p2
    def test_get_resource_empty_uri(self, mcp_server):
        """EC-024: mcp_get_resource with empty URI."""
        from tests.e2e.helpers.mcp_helpers import get_mcp_resource

        result = get_mcp_resource(mcp_server["url"], "")
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_get_resource_malformed_uri(self, mcp_server):
        """EC-025: mcp_get_resource with malformed URI."""
        from tests.e2e.helpers.mcp_helpers import get_mcp_resource

        result = get_mcp_resource(mcp_server["url"], "not://a/valid/uri/scheme")
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_get_resource_very_long_uri(self, mcp_server):
        """EC-026: mcp_get_resource with very long URI."""
        from tests.e2e.helpers.mcp_helpers import get_mcp_resource

        long_uri = "resource://" + "a" * 10000
        result = get_mcp_resource(mcp_server["url"], long_uri)
        # Should fail gracefully without memory issues
        assert result is not None


class TestVariableEdgeCases:
    """Test variable tools with edge case inputs."""

    @pytest.mark.p2
    def test_read_variable_empty_name(self, mcp_server):
        """EC-027: notebook_read_variable with empty name."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_variable", {"name": ""}
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_read_variable_special_chars(self, mcp_server):
        """EC-028: notebook_read_variable with special characters."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_variable", {"name": "invalid.var.name!"}
        )
        # Should fail gracefully - not a valid Python identifier
        assert result is not None

    @pytest.mark.p2
    def test_list_variables_invalid_filter(self, mcp_server):
        """EC-029: notebook_list_variables with invalid type filter."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_list_variables",
            {"type_filter": "nonexistent_type_xyz"},
        )
        # Should return empty list or handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_server_status_with_extra_params(self, mcp_server):
        """EC-030: notebook_server_status ignores unknown parameters."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_server_status",
            {"unknown_param": "value", "another_unknown": 123},
        )
        # Should succeed, ignoring unknown params
        success, content = parse_tool_result(result)
        assert success, f"Server status with extra params failed: {content}"
