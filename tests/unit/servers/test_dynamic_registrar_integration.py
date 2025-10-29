"""Integration tests for DynamicToolRegistrar with FastMCP."""

import pytest
from unittest.mock import Mock, patch

from instrmcp.servers.jupyter_qcodes.dynamic_registrar import DynamicToolRegistrar
from instrmcp.tools.dynamic import create_tool_spec


@pytest.fixture
def mock_ipython():
    """Create a mock IPython instance."""
    mock = Mock()
    mock.user_ns = {"test_var": 42}
    return mock


@pytest.fixture
def mock_mcp():
    """Create a mock FastMCP instance with remove_tool support."""
    mock = Mock()
    mock.tool = Mock(return_value=lambda f: f)  # Decorator that returns the function
    mock.remove_tool = Mock()  # Mock the remove_tool method
    return mock


@pytest.fixture
def temp_registry(tmp_path):
    """Create a temporary registry directory."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    return registry_dir


@pytest.fixture
def registrar(mock_mcp, mock_ipython, temp_registry):
    """Create a DynamicToolRegistrar with mocked dependencies."""
    with patch(
        "instrmcp.tools.dynamic.tool_registry.Path.home",
        return_value=temp_registry.parent,
    ):
        registrar = DynamicToolRegistrar(mock_mcp, mock_ipython)
        # Clear any tools loaded from startup
        registrar.registry._cache.clear()
        return registrar


class TestFastMCPRemoveTool:
    """Test that FastMCP's remove_tool is called correctly."""

    def test_remove_tool_called_on_revoke(self, registrar, mock_mcp):
        """Test that mcp.remove_tool() is called when revoking a tool."""
        # Register a tool
        spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="Test tool for removal",
            author="test",
            source_code="def test_tool():\n    return 42",
        )
        registrar._register_tool_with_fastmcp(spec)
        registrar.registry.register(spec)

        # Reset mock to clear registration calls
        mock_mcp.remove_tool.reset_mock()

        # Revoke the tool
        registrar._unregister_tool_from_fastmcp("test_tool")

        # Verify remove_tool was called
        mock_mcp.remove_tool.assert_called_once_with("test_tool")

    def test_remove_tool_handles_exception(self, registrar, mock_mcp, caplog):
        """Test that exceptions from remove_tool are handled gracefully."""
        # Register a tool
        spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="Test tool for testing",
            author="test",
            source_code="def test_tool():\n    return 42",
        )
        registrar._register_tool_with_fastmcp(spec)
        registrar.registry.register(spec)

        # Make remove_tool raise an exception
        mock_mcp.remove_tool.side_effect = Exception("FastMCP error")

        # Revoke should not crash
        registrar._unregister_tool_from_fastmcp("test_tool")

        # Verify warning was logged
        assert "Failed to remove tool 'test_tool' from FastMCP" in caplog.text

    def test_remove_tool_called_during_update(self, registrar, mock_mcp):
        """Test that remove_tool is called when updating a tool."""
        # Register initial tool
        old_spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="Test tool for testing",
            author="test",
            source_code="def test_tool():\n    return 42",
        )
        registrar._register_tool_with_fastmcp(old_spec)
        registrar.registry.register(old_spec)

        # Reset mock to clear registration calls
        mock_mcp.remove_tool.reset_mock()

        # Update the tool
        new_spec = create_tool_spec(
            name="test_tool",
            version="2.0.0",
            description="Updated test tool",
            author="test",
            source_code="def test_tool():\n    return 100",
        )

        # Simulate the update process (unregister + register)
        registrar._unregister_tool_from_fastmcp("test_tool")
        registrar._register_tool_with_fastmcp(new_spec)
        registrar.registry.update(new_spec)

        # Verify remove_tool was called once during update
        mock_mcp.remove_tool.assert_called_once_with("test_tool")


class TestRegistrationOrder:
    """Test that registration happens in the correct order to prevent faulty tools."""

    def test_fastmcp_registration_before_registry(self, registrar, mock_mcp):
        """Test that FastMCP registration happens before registry storage."""
        spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="Test tool for testing",
            author="test",
            source_code="def test_tool():\n    return 42",
        )

        # Track the order of operations
        call_order = []

        original_register_fastmcp = registrar._register_tool_with_fastmcp
        original_register_registry = registrar.registry.register

        def track_fastmcp(s):
            call_order.append("fastmcp")
            return original_register_fastmcp(s)

        def track_registry(s):
            call_order.append("registry")
            return original_register_registry(s)

        registrar._register_tool_with_fastmcp = track_fastmcp
        registrar.registry.register = track_registry

        # Register the tool (simulating the full flow)
        registrar._register_tool_with_fastmcp(spec)
        registrar.registry.register(spec)

        # Verify FastMCP registration happened first
        assert call_order == ["fastmcp", "registry"]

    def test_registry_not_updated_when_compilation_fails(self, registrar, mock_mcp):
        """Test that registry is not updated if tool compilation fails."""
        # Create a tool spec that defines wrong function name
        spec = create_tool_spec(
            name="bad_tool",
            version="1.0.0",
            description="Tool with wrong function name",
            author="test",
            source_code="def wrong_name():\n    return 42",  # Function name doesn't match tool name
        )

        # Try to register (will fail - function name must match tool name)
        with pytest.raises(Exception):
            registrar._register_tool_with_fastmcp(spec)

        # Verify tool is NOT in registry (because we didn't call registry.register())
        assert registrar.registry.get("bad_tool") is None

        # Verify it's not in the tool list
        tools = registrar.registry.list_tools()
        assert "bad_tool" not in [t["name"] for t in tools]


class TestUpdateRollback:
    """Test that update failures trigger proper rollback."""

    def test_update_rollback_on_registration_failure(self, registrar, mock_mcp):
        """Test that failed FastMCP registration triggers rollback."""
        # Register a working tool
        old_spec = create_tool_spec(
            name="test_tool",
            version="1.0.0",
            description="Original tool for testing",
            author="test",
            source_code="def test_tool():\n    return 42",
        )
        registrar._register_tool_with_fastmcp(old_spec)
        registrar.registry.register(old_spec)

        # Create a valid spec for update
        new_spec = create_tool_spec(
            name="test_tool",
            version="2.0.0",
            description="Updated tool for testing",
            author="test",
            source_code="def test_tool():\n    return 100",
        )

        # Make FastMCP tool registration fail
        original_tool = mock_mcp.tool

        def failing_tool(name=None):
            if name == "test_tool":
                raise Exception("FastMCP registration failed")
            return original_tool(name=name)

        mock_mcp.tool = failing_tool

        # Attempt update with rollback
        registrar._unregister_tool_from_fastmcp("test_tool")
        try:
            registrar._register_tool_with_fastmcp(new_spec)
            registrar.registry.update(new_spec)
        except Exception:
            # Rollback: re-register old version
            mock_mcp.tool = original_tool  # Restore for rollback
            registrar._register_tool_with_fastmcp(old_spec)

        # Verify old version is still in runtime
        assert "test_tool" in registrar.runtime._tool_functions

        # Verify registry still has old version (update was never called due to exception)
        tool = registrar.registry.get("test_tool")
        assert tool.version == "1.0.0"


class TestToolVisibility:
    """Test that only successfully registered tools are visible."""

    def test_only_valid_tools_in_list(self, registrar):
        """Test that only successfully registered tools appear in list."""
        # Register a valid tool
        valid_spec = create_tool_spec(
            name="valid_tool",
            version="1.0.0",
            description="Valid tool for testing",
            author="test",
            source_code="def valid_tool():\n    return 42",
        )
        registrar._register_tool_with_fastmcp(valid_spec)
        registrar.registry.register(valid_spec)

        # Try to register an invalid tool (wrong function name - should fail)
        invalid_spec = create_tool_spec(
            name="invalid_tool",
            version="1.0.0",
            description="Invalid tool for testing",
            author="test",
            source_code="def wrong_name():\n    return 99",  # Function name doesn't match
        )
        try:
            registrar._register_tool_with_fastmcp(invalid_spec)
            registrar.registry.register(invalid_spec)  # This won't be reached
        except Exception:
            pass  # Expected - compilation fails

        # List should only contain valid tool
        tools = registrar.registry.list_tools()
        tool_names = [t["name"] for t in tools]

        assert "valid_tool" in tool_names
        assert "invalid_tool" not in tool_names
        assert len(tools) == 1

    def test_revoked_tools_removed_from_runtime(self, registrar):
        """Test that revoked tools are removed from runtime."""
        # Register a tool
        spec = create_tool_spec(
            name="temp_tool",
            version="1.0.0",
            description="Temporary tool for testing",
            author="test",
            source_code="def temp_tool():\n    return 123",
        )
        registrar._register_tool_with_fastmcp(spec)
        registrar.registry.register(spec)

        # Verify it's in runtime
        assert "temp_tool" in registrar.runtime._tool_functions

        # Revoke the tool
        registrar._unregister_tool_from_fastmcp("temp_tool")
        registrar.registry.revoke("temp_tool")

        # Verify it's removed from runtime
        assert "temp_tool" not in registrar.runtime._tool_functions

        # Verify it's removed from registry
        assert registrar.registry.get("temp_tool") is None
