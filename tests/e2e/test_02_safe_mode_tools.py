"""
Safe Mode Tools Tests (test_02_safe_mode_tools.py)

Purpose: Verify all read-only tools work correctly in safe mode.

Test IDs:
- SM-001 to SM-083
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import (
    run_cell,
    select_cell,
)
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    list_mcp_tools,
    list_mcp_resources,
    get_mcp_resource,
    parse_tool_result,
)
from tests.e2e.helpers.mock_qcodes import SAFE_MODE_TOOLS


class TestResourceTools:
    """Test MCP resource tools."""

    @pytest.mark.p0
    def test_mcp_list_resources(self, mcp_server):
        """SM-001: mcp_list_resources returns available resources."""
        resources = list_mcp_resources(mcp_server["url"])
        assert isinstance(resources, list), "Expected list of resources"
        # Should have at least some resources
        assert len(resources) > 0, "Expected at least one resource"

    @pytest.mark.p0
    def test_mcp_get_resource_valid(self, mcp_server):
        """SM-002: mcp_get_resource returns valid resource content."""
        # First list resources
        resources = list_mcp_resources(mcp_server["url"])
        assert len(resources) > 0, "No resources available"

        # Get the first resource - resources is a list of dicts with "uri" key
        first_resource = resources[0]
        resource_uri = (
            first_resource.get("uri")
            if isinstance(first_resource, dict)
            else first_resource
        )
        resource = get_mcp_resource(mcp_server["url"], resource_uri)
        assert "error" not in resource, f"Error getting resource: {resource}"

    @pytest.mark.p1
    def test_mcp_get_resource_invalid(self, mcp_server):
        """SM-003: mcp_get_resource handles invalid URI gracefully."""
        resource = get_mcp_resource(mcp_server["url"], "invalid://nonexistent/resource")
        # Should return an error, not crash
        # Either an error in response or empty result
        assert resource is not None, "Expected a response for invalid resource"


class TestNotebookTools:
    """Test notebook-related MCP tools."""

    @pytest.mark.p0
    def test_notebook_server_status(self, mcp_server):
        """SM-010: notebook_server_status returns server information."""
        result = call_mcp_tool(mcp_server["url"], "notebook_server_status")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        # Should contain some status information
        assert len(content) > 0, "Expected status content"

    @pytest.mark.p0
    def test_notebook_list_variables_no_filter(self, test_variables):
        """SM-011: notebook_list_variables returns all variables."""
        result = call_mcp_tool(test_variables["url"], "notebook_list_variables")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        # Should contain some of our test variables (defined in safe_mode notebook)
        assert (
            "test_int" in content or "test_str" in content or "station" in content
        ), f"Expected test variables in: {content}"

    @pytest.mark.p1
    def test_notebook_list_variables_type_filter(self, test_variables):
        """SM-012: notebook_list_variables filters by type."""
        result = call_mcp_tool(
            test_variables["url"], "notebook_list_variables", {"type_filter": "int"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p0
    def test_notebook_read_variable_simple(self, test_variables):
        """SM-013: notebook_read_variable reads simple variable."""
        result = call_mcp_tool(
            test_variables["url"], "notebook_read_variable", {"name": "test_int"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        assert "42" in content, f"Expected test_int=42 in: {content}"

    @pytest.mark.p1
    def test_notebook_read_variable_detailed(self, test_variables):
        """SM-014: notebook_read_variable with detailed output."""
        result = call_mcp_tool(
            test_variables["url"],
            "notebook_read_variable",
            {"name": "my_dict", "detailed": True},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_variable_numpy_array(self, test_variables):
        """SM-015: notebook_read_variable reads numpy array."""
        result = call_mcp_tool(
            test_variables["url"], "notebook_read_variable", {"name": "arr"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_variable_dataframe(self, test_variables):
        """SM-016: notebook_read_variable reads pandas DataFrame."""
        result = call_mcp_tool(
            test_variables["url"], "notebook_read_variable", {"name": "df"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_variable_large_array(self, test_variables):
        """SM-017: notebook_read_variable handles large arrays."""
        result = call_mcp_tool(
            test_variables["url"], "notebook_read_variable", {"name": "large_arr"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_variable_nonexistent(self, test_variables):
        """SM-018: notebook_read_variable handles nonexistent variable."""
        result = call_mcp_tool(
            test_variables["url"],
            "notebook_read_variable",
            {"name": "nonexistent_variable_xyz"},
        )
        # Should fail or return error message
        success, content = parse_tool_result(result)
        # Either success=False or content indicates error
        if success:
            assert (
                "not found" in content.lower()
                or "error" in content.lower()
                or "undefined" in content.lower()
            ), f"Expected error for nonexistent variable: {content}"

    @pytest.mark.p0
    def test_notebook_read_active_cell_basic(self, mcp_server):
        """SM-020: notebook_read_active_cell returns cell content."""
        page = mcp_server["page"]

        # Write some code to the active cell
        run_cell(page, "# Test cell content\nx = 42", wait_for_output=True)

        result = call_mcp_tool(mcp_server["url"], "notebook_read_active_cell")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_active_cell_detailed(self, mcp_server):
        """SM-021: notebook_read_active_cell with detailed mode."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_active_cell", {"detailed": True}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p2
    def test_notebook_read_active_cell_line_range(self, mcp_server):
        """SM-022: notebook_read_active_cell with line range."""
        page = mcp_server["page"]

        # Create a multi-line cell
        code = "# Line 1\n# Line 2\n# Line 3\n# Line 4\n# Line 5"
        run_cell(page, code, wait_for_output=False)

        # FIXED: Use correct parameter names (line_start/line_end not start_line/end_line)
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": 2, "line_end": 4},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_active_cell_markdown(self, mcp_server):
        """SM-023: notebook_read_active_cell reads markdown cell."""
        page = mcp_server["page"]

        # Create a markdown cell
        page.keyboard.press("Escape")
        page.keyboard.press("M")  # Convert to markdown
        page.keyboard.press("Enter")
        page.keyboard.type("# Markdown Header")
        page.keyboard.press("Escape")

        result = call_mcp_tool(mcp_server["url"], "notebook_read_active_cell")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p0
    def test_notebook_read_active_cell_output_success(self, mcp_server):
        """SM-030: notebook_read_active_cell_output returns output."""
        page = mcp_server["page"]

        # Execute a cell with output
        run_cell(page, 'print("test output")', wait_for_output=True)

        result = call_mcp_tool(mcp_server["url"], "notebook_read_active_cell_output")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_read_active_cell_output_error(self, mcp_server):
        """SM-031: notebook_read_active_cell_output captures errors."""
        page = mcp_server["page"]

        # Execute a cell with error
        run_cell(page, "1/0", wait_for_output=True)

        result = call_mcp_tool(mcp_server["url"], "notebook_read_active_cell_output")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        # Should contain error indication
        assert (
            "error" in content.lower() or "zero" in content.lower()
        ), f"Expected error in output: {content}"

    @pytest.mark.p1
    def test_notebook_read_active_cell_output_no_output(self, mcp_server):
        """SM-032: notebook_read_active_cell_output handles no output."""
        page = mcp_server["page"]

        # Execute a cell without output
        run_cell(page, "x = 1", wait_for_output=True)

        result = call_mcp_tool(mcp_server["url"], "notebook_read_active_cell_output")
        success, content = parse_tool_result(result)
        # Should succeed but indicate no output
        assert (
            success or "no output" in content.lower()
        ), f"Unexpected result: {content}"

    @pytest.mark.p1
    def test_notebook_read_active_cell_output_markdown(self, mcp_server):
        """SM-033: notebook_read_active_cell_output for markdown."""
        page = mcp_server["page"]

        # Create and render markdown
        page.keyboard.press("Escape")
        page.keyboard.press("M")
        page.keyboard.press("Enter")
        page.keyboard.type("# Header")
        page.keyboard.press("Shift+Enter")
        page.wait_for_timeout(1000)

        call_mcp_tool(mcp_server["url"], "notebook_read_active_cell_output")
        # Markdown cells may not have "output" in the traditional sense
        # Tool should handle this gracefully

    @pytest.mark.p0
    def test_notebook_read_content_basic(self, mcp_server):
        """SM-040: notebook_read_content returns notebook content."""
        result = call_mcp_tool(mcp_server["url"], "notebook_read_content")
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        assert len(content) > 0, "Expected notebook content"

    @pytest.mark.p1
    def test_notebook_read_content_with_output(self, mcp_server):
        """SM-041: notebook_read_content includes cell outputs."""
        page = mcp_server["page"]

        # Execute a cell with output
        run_cell(page, 'print("hello")', wait_for_output=True)

        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_content", {"include_outputs": True}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p2
    def test_notebook_read_content_detailed(self, mcp_server):
        """SM-042: notebook_read_content with detailed mode."""
        result = call_mcp_tool(
            mcp_server["url"], "notebook_read_content", {"detailed": True}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p0
    def test_notebook_move_cursor_above(self, mcp_server):
        """SM-050: notebook_move_cursor moves cursor above."""
        page = mcp_server["page"]

        # Create multiple cells
        run_cell(page, "# cell 1", wait_for_output=False)
        page.keyboard.press("B")  # Add cell below
        page.keyboard.press("Enter")
        page.keyboard.type("# cell 2")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"direction": "above"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p0
    def test_notebook_move_cursor_below(self, mcp_server):
        """SM-051: notebook_move_cursor moves cursor below."""
        page = mcp_server["page"]

        # Create multiple cells
        run_cell(page, "# cell 1", wait_for_output=False)
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.type("# cell 2")
        page.keyboard.press("Escape")

        # Move to first cell
        select_cell(page, 0)

        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"direction": "below"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_notebook_move_cursor_top_bottom(self, mcp_server):
        """SM-052: notebook_move_cursor moves to top/bottom."""
        page = mcp_server["page"]

        # Create multiple cells
        for i in range(3):
            run_cell(page, f"# cell {i}", wait_for_output=False)
            page.keyboard.press("B")

        # Move to top
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"direction": "top"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Move to top failed: {content}"

        # Move to bottom
        result = call_mcp_tool(
            mcp_server["url"], "notebook_move_cursor", {"direction": "bottom"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Move to bottom failed: {content}"


class TestQCodesTools:
    """Test QCodes-related MCP tools."""

    @pytest.mark.p0
    def test_qcodes_instrument_info_all(self, mock_qcodes_station):
        """SM-060: qcodes_instrument_info returns all instruments."""
        result = call_mcp_tool(
            mock_qcodes_station["url"], "qcodes_instrument_info", {"name": "*"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"
        # The safe mode notebook creates dac1 and dac2, mock_qcodes_station adds mock_dmm
        assert (
            "mock_dmm" in content or "dac1" in content or "dac2" in content
        ), f"Expected some instrument in: {content}"

    @pytest.mark.p0
    def test_qcodes_instrument_info_specific(self, mock_qcodes_station):
        """SM-061: qcodes_instrument_info for specific instrument."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"instrument_name": "mock_dmm"},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_instrument_info_detailed(self, mock_qcodes_station):
        """SM-062: qcodes_instrument_info with detailed mode."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"instrument_name": "mock_dmm", "detailed": True},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_instrument_info_with_values(self, mock_qcodes_station):
        """SM-063: qcodes_instrument_info includes parameter values."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"instrument_name": "mock_dmm", "include_values": True},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_instrument_info_invalid(self, mock_qcodes_station):
        """SM-064: qcodes_instrument_info handles invalid instrument."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"instrument_name": "nonexistent_instrument"},
        )
        success, content = parse_tool_result(result)
        # Should handle gracefully - either error or empty result
        # Not crash

    @pytest.mark.p0
    def test_qcodes_get_parameter_info_basic(self, mock_qcodes_station):
        """SM-070: qcodes_get_parameter_info returns parameter info."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_info",
            {"instrument_name": "mock_dmm", "parameter_name": "voltage"},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_get_parameter_info_detailed(self, mock_qcodes_station):
        """SM-071: qcodes_get_parameter_info with detailed mode."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_info",
            {
                "instrument_name": "mock_dmm",
                "parameter_name": "voltage",
                "detailed": True,
            },
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_get_parameter_info_invalid(self, mock_qcodes_station):
        """SM-072: qcodes_get_parameter_info handles invalid parameter."""
        call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_info",
            {"instrument_name": "mock_dmm", "parameter_name": "nonexistent_param"},
        )
        # Should handle gracefully

    @pytest.mark.p0
    def test_qcodes_get_parameter_values_single(self, mock_qcodes_station):
        """SM-080: qcodes_get_parameter_values reads single parameter."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"parameters": ["mock_dmm.voltage"]},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_get_parameter_values_batch(self, mock_qcodes_station):
        """SM-081: qcodes_get_parameter_values reads multiple parameters."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {
                "parameters": [
                    "mock_dmm.voltage",
                    "mock_dmm.current",
                    "mock_dmm.frequency",
                ]
            },
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_get_parameter_values_detailed(self, mock_qcodes_station):
        """SM-082: qcodes_get_parameter_values with detailed mode."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"parameters": ["mock_dmm.voltage"], "detailed": True},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call failed: {content}"

    @pytest.mark.p1
    def test_qcodes_get_parameter_values_invalid(self, mock_qcodes_station):
        """SM-083: qcodes_get_parameter_values handles invalid parameter."""
        call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"parameters": ["nonexistent.param"]},
        )
        # Should handle gracefully


class TestToolAvailability:
    """Test that correct tools are available in safe mode."""

    @pytest.mark.p0
    def test_safe_mode_tools_available(self, mcp_server):
        """Verify safe mode tools are available."""
        tools = list_mcp_tools(mcp_server["url"])
        assert len(tools) > 0, "No tools available"

        # Get tool names from the list of tool dictionaries
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]

        # Check for expected safe mode tools
        for tool in SAFE_MODE_TOOLS:
            assert (
                tool in tool_names
            ), f"Expected safe mode tool {tool} not found. Available: {tool_names}"

    @pytest.mark.p0
    def test_unsafe_tools_not_available(self, mcp_server):
        """Verify unsafe tools are NOT available in safe mode."""
        tools = list_mcp_tools(mcp_server["url"])

        # Get tool names from the list of tool dictionaries
        tool_names = [t.get("name") for t in tools if isinstance(t, dict)]

        # These tools should NOT be in safe mode
        unsafe_only = [
            "notebook_execute_active_cell",
            "notebook_delete_cell",
            "notebook_apply_patch",
        ]

        for tool in unsafe_only:
            assert (
                tool not in tool_names
            ), f"Unsafe tool {tool} should not be in safe mode"


class TestResourceTemplates:
    """Test MCP resource template retrieval."""

    @pytest.mark.p1
    def test_list_resources_returns_list(self, mcp_server):
        """SM-100: mcp_list_resources returns a list of resources."""
        resources = list_mcp_resources(mcp_server["url"])
        assert isinstance(resources, list), "Expected list of resources"

    @pytest.mark.p1
    def test_resources_have_uri(self, mcp_server):
        """SM-101: Resources have URI field."""
        resources = list_mcp_resources(mcp_server["url"])
        # Check all resources that are dicts have URI
        for i, resource in enumerate(resources):
            if isinstance(resource, dict):
                assert (
                    "uri" in resource
                ), f"Resource {i} missing 'uri' field: {resource}"

    @pytest.mark.p1
    def test_get_available_instruments_resource(self, mcp_server):
        """SM-102: Get available_instruments resource."""
        resource = get_mcp_resource(
            mcp_server["url"], "resource://available_instruments"
        )
        # Should return something (may be empty if no instruments)
        assert resource is not None

    @pytest.mark.p2
    def test_resources_not_empty(self, mcp_server):
        """SM-103: Resources list has at least one resource in safe mode."""
        resources = list_mcp_resources(mcp_server["url"])
        # Should have at least some core resources
        assert isinstance(resources, list), "Expected list"
        assert len(resources) > 0, "Expected at least one resource in the list"

    @pytest.mark.p2
    def test_get_nonexistent_resource_error(self, mcp_server):
        """SM-104: Getting non-existent resource returns error or empty content."""
        resource = get_mcp_resource(
            mcp_server["url"], "resource://definitely_nonexistent_resource_xyz"
        )
        # Should return a response (error or empty), verify it's returned
        assert resource is not None
        # If it's a dict with error info or empty content, that's valid
        if isinstance(resource, dict):
            # Either has content key or error key
            assert "contents" in resource or "error" in resource or len(resource) == 0
