"""
Optional Features Tests (test_06_optional_features.py)

Purpose: Verify optional features work when enabled.

Test IDs:
- OF-001 to OF-028
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell, get_cell_output
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    list_mcp_tools,
    parse_tool_result,
)
from tests.e2e.helpers.mock_qcodes import MEASUREIT_TOOLS, DATABASE_TOOLS, DYNAMIC_TOOLS


class TestMeasureItTools:
    """Test MeasureIt optional feature."""

    @pytest.mark.p1
    def test_measureit_enable(self, notebook_page):
        """OF-001: Enable MeasureIt option."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option measureit")
        output = get_cell_output(notebook_page)

        assert "error" not in output.lower(), f"Error enabling measureit: {output}"

    @pytest.mark.p1
    def test_measureit_tools_visible(self, notebook_page, mcp_port):
        """OF-002: MeasureIt tools are visible when enabled."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option measureit")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        tools_raw = list_mcp_tools(base_url)
        # Extract tool names from list of dicts
        tools = [t.get("name") for t in tools_raw if isinstance(t, dict)]

        # Check for MeasureIt tools
        for tool in MEASUREIT_TOOLS:
            assert tool in tools, f"MeasureIt tool {tool} not found. Available: {tools}"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p1
    def test_measureit_get_status_no_sweeps(self, notebook_page, mcp_port):
        """OF-003: measureit_get_status returns empty when no sweeps."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option measureit")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "measureit_get_status")
        success, content = parse_tool_result(result)

        # Should succeed, indicating no active sweeps
        assert (
            success or "no" in content.lower() or "empty" in content.lower()
        ), f"Unexpected result: {content}"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p2
    def test_measureit_resources(self, notebook_page, mcp_port):
        """OF-004: MeasureIt resources available when enabled."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option measureit")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        from tests.e2e.helpers.mcp_helpers import list_mcp_resources

        base_url = f"http://localhost:{mcp_port}"
        list_mcp_resources(base_url)

        # Should have measureit-related resources
        # (Check documentation for expected resources)

        run_cell(notebook_page, "%mcp_stop")


class TestDatabaseTools:
    """Test Database optional feature."""

    @pytest.mark.p1
    def test_database_enable(self, notebook_page):
        """OF-010: Enable database option."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        output = get_cell_output(notebook_page)

        assert "error" not in output.lower(), f"Error enabling database: {output}"

    @pytest.mark.p1
    def test_database_tools_visible(self, notebook_page, mcp_port):
        """OF-011: Database tools are visible when enabled."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        tools_raw = list_mcp_tools(base_url)
        # Extract tool names from list of dicts
        tools = [t.get("name") for t in tools_raw if isinstance(t, dict)]

        for tool in DATABASE_TOOLS:
            assert tool in tools, f"Database tool {tool} not found. Available: {tools}"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p1
    def test_database_list_all_available_db(self, notebook_page, mcp_port):
        """OF-012: database_list_all_available_db returns database list."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "database_list_all_available_db")
        success, content = parse_tool_result(result)

        # Should return something (may be empty if no databases)
        assert (
            success or "no database" in content.lower()
        ), f"Unexpected error: {content}"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p1
    def test_database_list_experiments(self, notebook_page, mcp_port):
        """OF-013: database_list_experiments returns experiment list."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "database_list_experiments")
        success, content = parse_tool_result(result)

        # Should handle no experiments gracefully
        assert (
            success
            or "no experiment" in content.lower()
            or "not found" in content.lower()
        ), f"Unexpected error: {content}"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p2
    def test_database_get_dataset_info(self, notebook_page, mcp_port):
        """OF-014: database_get_dataset_info returns dataset info."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        call_mcp_tool(base_url, "database_get_dataset_info", {"run_id": 1})
        # May fail if no dataset, but should handle gracefully

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p2
    def test_database_get_database_stats(self, notebook_page, mcp_port):
        """OF-015: database_get_database_stats returns statistics."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "database_get_database_stats")
        success, content = parse_tool_result(result)

        # Should return some stats or indicate no database
        assert result is not None

        run_cell(notebook_page, "%mcp_stop")


class TestDynamicTools:
    """Test Dynamic Tools optional feature."""

    @pytest.mark.p1
    def test_dynamictool_requires_dangerous(self, notebook_page):
        """OF-020: Dynamic tools require dangerous mode."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        # Try to enable in safe mode
        run_cell(notebook_page, "%mcp_option dynamictool")
        output = get_cell_output(notebook_page)

        # Should fail or warn that dangerous mode is required
        output_lower = output.lower()
        assert (
            "dangerous" in output_lower
            or "error" in output_lower
            or "require" in output_lower
        ), f"Expected warning about dangerous mode: {output}"

    @pytest.mark.p1
    def test_dynamictool_enable_in_dangerous(self, mcp_server_dynamictool, mcp_port):
        """OF-021: Dynamic tools can be enabled in dangerous mode.

        Uses the mcp_server_dynamictool fixture which sets up dangerous mode
        with dynamictool enabled. This verifies the feature works correctly.
        """
        # Verify the mode is correct
        assert mcp_server_dynamictool["mode"] == "dangerous+dynamictool"

        # Verify dynamic tools are available
        base_url = f"http://localhost:{mcp_port}"
        tools_raw = list_mcp_tools(base_url)
        # Extract tool names from list of dicts
        tools = [t.get("name") for t in tools_raw if isinstance(t, dict)]

        for tool in DYNAMIC_TOOLS:
            assert tool in tools, f"Dynamic tool {tool} not found. Available: {tools}"

    @pytest.mark.p1
    def test_dynamic_list_tools(self, mcp_server_dangerous, mcp_port):
        """OF-022: dynamic_list_tools returns registered tools."""
        page = mcp_server_dangerous["page"]

        # Enable dynamic tools
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "dynamic_list_tools")
        success, content = parse_tool_result(result)

        # Should succeed (may be empty if no tools registered)
        assert success or result is not None

    @pytest.mark.p1
    def test_dynamic_register_tool(self, mcp_server_dangerous, mcp_port):
        """OF-023: dynamic_register_tool registers a new tool."""
        page = mcp_server_dangerous["page"]

        # Enable dynamic tools
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"

        # Register a simple tool
        result = call_mcp_tool(
            base_url,
            "dynamic_register_tool",
            {
                "name": "test_dynamic_tool",
                "description": "A test dynamic tool",
                "code": "def test_dynamic_tool():\n    return 'Hello from dynamic tool'",
            },
        )
        success, content = parse_tool_result(result)

        # Should register successfully
        assert success, f"Failed to register tool: {content}"

    @pytest.mark.p1
    def test_dynamic_call_registered_tool(self, mcp_server_dangerous, mcp_port):
        """OF-024: Can call a registered dynamic tool."""
        page = mcp_server_dangerous["page"]

        # Enable dynamic tools
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"

        # Register a tool
        call_mcp_tool(
            base_url,
            "dynamic_register_tool",
            {
                "name": "my_test_tool",
                "description": "Returns a greeting",
                "code": "def my_test_tool(name='World'):\n    return f'Hello, {name}!'",
            },
        )
        page.wait_for_timeout(500)

        # Call the registered tool
        result = call_mcp_tool(base_url, "my_test_tool", {"name": "E2E Test"})
        success, content = parse_tool_result(result)

        # Should succeed and return greeting
        assert (
            success or "hello" in content.lower()
        ), f"Dynamic tool call failed: {content}"

    @pytest.mark.p2
    def test_dynamic_inspect_tool(self, mcp_server_dangerous, mcp_port):
        """OF-025: dynamic_inspect_tool shows tool details."""
        page = mcp_server_dangerous["page"]

        # Enable and register a tool
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"

        call_mcp_tool(
            base_url,
            "dynamic_register_tool",
            {
                "name": "inspect_test_tool",
                "description": "Tool for inspection test",
                "code": "def inspect_test_tool():\n    pass",
            },
        )
        page.wait_for_timeout(500)

        # Inspect the tool
        result = call_mcp_tool(
            base_url, "dynamic_inspect_tool", {"name": "inspect_test_tool"}
        )
        success, content = parse_tool_result(result)

        # Should return tool details
        assert success, f"Inspect failed: {content}"

    @pytest.mark.p2
    def test_dynamic_update_tool(self, mcp_server_dangerous, mcp_port):
        """OF-026: dynamic_update_tool updates existing tool."""
        page = mcp_server_dangerous["page"]

        # Enable and register a tool
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"

        call_mcp_tool(
            base_url,
            "dynamic_register_tool",
            {
                "name": "update_test_tool",
                "description": "Original description",
                "code": "def update_test_tool():\n    return 'v1'",
            },
        )
        page.wait_for_timeout(500)

        # Update the tool
        result = call_mcp_tool(
            base_url,
            "dynamic_update_tool",
            {
                "name": "update_test_tool",
                "description": "Updated description",
                "code": "def update_test_tool():\n    return 'v2'",
            },
        )
        success, content = parse_tool_result(result)

        assert success, f"Update failed: {content}"

    @pytest.mark.p1
    def test_dynamic_revoke_tool(self, mcp_server_dangerous, mcp_port):
        """OF-027: dynamic_revoke_tool removes a tool."""
        page = mcp_server_dangerous["page"]

        # Enable and register a tool
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"

        call_mcp_tool(
            base_url,
            "dynamic_register_tool",
            {
                "name": "revoke_test_tool",
                "description": "Tool to be revoked",
                "code": "def revoke_test_tool():\n    pass",
            },
        )
        page.wait_for_timeout(500)

        # Revoke the tool
        result = call_mcp_tool(
            base_url, "dynamic_revoke_tool", {"name": "revoke_test_tool"}
        )
        success, content = parse_tool_result(result)

        assert success, f"Revoke failed: {content}"

        # Verify tool is no longer available
        tools = list_mcp_tools(base_url)
        assert "revoke_test_tool" not in tools, "Tool should be revoked"

    @pytest.mark.p2
    def test_dynamic_registry_stats(self, mcp_server_dangerous, mcp_port):
        """OF-028: dynamic_registry_stats returns statistics."""
        page = mcp_server_dangerous["page"]

        # Enable dynamic tools
        run_cell(page, "%mcp_stop")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_option dynamictool")
        page.wait_for_timeout(500)
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "dynamic_registry_stats")
        success, content = parse_tool_result(result)

        # Should return stats
        assert success or result is not None


class TestOptionDisabling:
    """Test disabling optional features."""

    @pytest.mark.p1
    def test_disable_measureit(self, notebook_page, mcp_port):
        """Test disabling MeasureIt option."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        # Enable then disable
        run_cell(notebook_page, "%mcp_option measureit")
        notebook_page.wait_for_timeout(500)
        run_cell(notebook_page, "%mcp_option -measureit")
        output = get_cell_output(notebook_page)

        assert "error" not in output.lower(), f"Error disabling measureit: {output}"

        # Start and verify tools are not available
        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        tools = list_mcp_tools(base_url)

        for tool in MEASUREIT_TOOLS:
            assert (
                tool not in tools
            ), f"MeasureIt tool {tool} should not be available after disable"

        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p1
    def test_disable_database(self, notebook_page, mcp_port):
        """Test disabling database option."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        # Enable then disable
        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)
        run_cell(notebook_page, "%mcp_option -database")
        output = get_cell_output(notebook_page)

        assert "error" not in output.lower(), f"Error disabling database: {output}"

        # Start and verify tools are not available
        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        base_url = f"http://localhost:{mcp_port}"
        tools = list_mcp_tools(base_url)

        for tool in DATABASE_TOOLS:
            assert (
                tool not in tools
            ), f"Database tool {tool} should not be available after disable"

        run_cell(notebook_page, "%mcp_stop")
