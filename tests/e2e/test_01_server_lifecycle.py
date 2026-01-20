"""
Server Lifecycle Tests (test_01_server_lifecycle.py)

Purpose: Verify MCP server start/stop/restart and mode switching.

Test IDs:
- SL-001 to SL-010
"""

import pytest
from tests.e2e.helpers import (
    call_mcp_tool,
    list_mcp_tools,
    parse_tool_result,
)


class TestServerLifecycle:
    """Test MCP server lifecycle operations."""

    @pytest.mark.p0
    def test_server_starts_successfully(self, mcp_server):
        """SL-001: Server starts and becomes available."""
        # The fixture already ensures the server is running
        assert mcp_server["port"] > 0
        assert mcp_server["url"].startswith("http://")

        # Verify we can list tools (server is responsive)
        tools = list_mcp_tools(mcp_server["url"])
        assert len(tools) > 0, "Server should have tools available"

    @pytest.mark.p0
    def test_server_start_default_safe_mode(self, mcp_server):
        """SL-002: Server starts in safe mode by default."""
        assert mcp_server["mode"] == "safe"

        # In safe mode, certain unsafe tools should not be available
        tools = list_mcp_tools(mcp_server["url"])
        tool_names = [t.get("name") for t in tools]

        # Safe mode should have basic tools
        assert "notebook_read_active_cell" in tool_names
        assert "qcodes_instrument_info" in tool_names

    @pytest.mark.p0
    def test_server_unsafe_mode(self, mcp_server_unsafe):
        """SL-003: Server can start in unsafe mode."""
        assert mcp_server_unsafe["mode"] == "unsafe"

        tools = list_mcp_tools(mcp_server_unsafe["url"])
        tool_names = [t.get("name") for t in tools]

        # Unsafe mode should have execute tools
        assert "notebook_execute_active_cell" in tool_names

    @pytest.mark.p0
    def test_server_dangerous_mode(self, mcp_server_dangerous):
        """SL-004: Server can start in dangerous mode."""
        assert mcp_server_dangerous["mode"] == "dangerous"

        tools = list_mcp_tools(mcp_server_dangerous["url"])
        tool_names = [t.get("name") for t in tools]

        # Dangerous mode should have all unsafe tools
        assert "notebook_execute_active_cell" in tool_names
        assert "notebook_delete_cell" in tool_names


class TestServerTools:
    """Tests for server tool availability."""

    @pytest.mark.p0
    def test_tools_list_not_empty(self, mcp_server):
        """SL-005: tools/list returns non-empty list."""
        tools = list_mcp_tools(mcp_server["url"])
        assert len(tools) > 0, "Should have at least one tool"

    @pytest.mark.p0
    def test_qcodes_tools_available(self, mcp_server):
        """SL-006: QCodes tools are available."""
        tools = list_mcp_tools(mcp_server["url"])
        tool_names = [t.get("name") for t in tools]

        assert "qcodes_instrument_info" in tool_names
        assert "qcodes_get_parameter_values" in tool_names

    @pytest.mark.p0
    def test_notebook_tools_available(self, mcp_server):
        """SL-007: Notebook tools are available."""
        tools = list_mcp_tools(mcp_server["url"])
        tool_names = [t.get("name") for t in tools]

        assert "notebook_read_active_cell" in tool_names
        assert "notebook_read_content" in tool_names
        assert "notebook_list_variables" in tool_names

    @pytest.mark.p1
    def test_safe_mode_excludes_execute(self, mcp_server):
        """SL-008: Safe mode excludes execution tools."""
        tools = list_mcp_tools(mcp_server["url"])
        tool_names = [t.get("name") for t in tools]

        # These should NOT be available in safe mode
        assert "notebook_execute_active_cell" not in tool_names

    @pytest.mark.p1
    def test_unsafe_mode_includes_execute(self, mcp_server_unsafe):
        """SL-009: Unsafe mode includes execution tools."""
        tools = list_mcp_tools(mcp_server_unsafe["url"])
        tool_names = [t.get("name") for t in tools]

        # These SHOULD be available in unsafe mode
        assert "notebook_execute_active_cell" in tool_names
        assert "notebook_add_cell" in tool_names


class TestServerResponsiveness:
    """Tests for server responsiveness and health."""

    @pytest.mark.p0
    def test_server_responds_to_tool_call(self, mcp_server):
        """SL-010: Server responds to tool calls."""
        # Call a simple tool
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_server_status",
            {},
        )
        success, content = parse_tool_result(result)
        assert success, f"Tool call should succeed: {content}"
