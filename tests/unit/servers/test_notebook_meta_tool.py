"""Tests for the unified notebook meta-tool."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from instrmcp.servers.jupyter_qcodes.registrars.notebook_meta_tool import (
    NotebookMetaToolRegistrar,
)


@pytest.fixture
def mock_mcp():
    """Create a mock FastMCP server."""
    mcp = MagicMock()
    mcp.tool = MagicMock(return_value=lambda f: f)
    mcp._tools = {}
    return mcp


@pytest.fixture
def mock_tools():
    """Create mock QCodesReadOnlyTools."""
    tools = MagicMock()
    tools.list_variables = AsyncMock(return_value=[{"name": "x", "type": "int"}])
    tools.get_variable_info = AsyncMock(
        return_value={"name": "x", "type": "int", "value": 42}
    )
    tools.get_editing_cell = AsyncMock(
        return_value={"text": "print('hello')", "cell_type": "code", "index": 0}
    )
    tools.move_cursor = AsyncMock(return_value={"success": True, "new_index": 1})
    tools.update_editing_cell = AsyncMock(return_value={"success": True})
    tools.execute_editing_cell = AsyncMock(return_value={"success": True})
    tools.add_new_cell = AsyncMock(return_value={"success": True, "index": 1})
    tools.delete_editing_cell = AsyncMock(return_value={"success": True})
    tools.delete_cells_by_number = AsyncMock(
        return_value={"success": True, "deleted": 2}
    )
    tools.apply_patch = AsyncMock(return_value={"success": True})
    return tools


@pytest.fixture
def mock_ipython():
    """Create a mock IPython instance."""
    ipython = MagicMock()
    ipython.user_ns = {"In": ["", "x = 1", "print(x)"], "Out": {1: 1, 2: None}}
    ipython.execution_count = 3
    return ipython


@pytest.fixture
def mock_consent_manager():
    """Create a mock consent manager."""
    consent = MagicMock()
    consent.request_consent = AsyncMock(
        return_value={"approved": True, "reason": "user_approved"}
    )
    return consent


@pytest.fixture
def registrar_safe(mock_mcp, mock_tools, mock_ipython):
    """Create a registrar in safe mode."""
    registrar = NotebookMetaToolRegistrar(
        mock_mcp,
        mock_tools,
        mock_ipython,
        safe_mode=True,
        dangerous_mode=False,
        consent_manager=None,
    )
    return registrar


@pytest.fixture
def registrar_unsafe(mock_mcp, mock_tools, mock_ipython, mock_consent_manager):
    """Create a registrar in unsafe mode with consent."""
    registrar = NotebookMetaToolRegistrar(
        mock_mcp,
        mock_tools,
        mock_ipython,
        safe_mode=False,
        dangerous_mode=False,
        consent_manager=mock_consent_manager,
    )
    return registrar


@pytest.fixture
def registrar_dangerous(mock_mcp, mock_tools, mock_ipython, mock_consent_manager):
    """Create a registrar in dangerous mode (consent bypassed)."""
    mock_consent_manager.request_consent = AsyncMock(
        return_value={"approved": True, "reason": "bypass_mode"}
    )
    registrar = NotebookMetaToolRegistrar(
        mock_mcp,
        mock_tools,
        mock_ipython,
        safe_mode=False,
        dangerous_mode=True,
        consent_manager=mock_consent_manager,
    )
    return registrar


class TestActionRouting:
    """Test that actions are routed to correct backend methods."""

    @pytest.mark.asyncio
    async def test_list_variables_routes_correctly(self, registrar_safe, mock_tools):
        """Test list_variables action routes to tools.list_variables."""
        result = await registrar_safe._handle_action(
            action="list_variables", type_filter="int"
        )
        mock_tools.list_variables.assert_called_once_with("int")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_variable_info_routes_correctly(self, registrar_safe, mock_tools):
        """Test get_variable_info action routes to tools.get_variable_info."""
        result = await registrar_safe._handle_action(
            action="get_variable_info", name="x"
        )
        mock_tools.get_variable_info.assert_called_once_with("x")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_editing_cell_routes_correctly(self, registrar_safe, mock_tools):
        """Test get_editing_cell action routes with all parameters."""
        result = await registrar_safe._handle_action(
            action="get_editing_cell",
            fresh_ms=500,
            line_start=1,
            line_end=10,
            max_lines=100,
        )
        mock_tools.get_editing_cell.assert_called_once_with(
            fresh_ms=500, line_start=1, line_end=10, max_lines=100
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_move_cursor_routes_correctly(self, registrar_safe, mock_tools):
        """Test move_cursor action routes to tools.move_cursor."""
        result = await registrar_safe._handle_action(
            action="move_cursor", target="below"
        )
        mock_tools.move_cursor.assert_called_once_with("below")
        assert len(result) == 1


class TestSafeModeBlocking:
    """Test that unsafe actions are blocked in safe mode."""

    @pytest.mark.asyncio
    async def test_update_editing_cell_blocked_in_safe_mode(self, registrar_safe):
        """Test update_editing_cell is blocked in safe mode."""
        result = await registrar_safe._handle_action(
            action="update_editing_cell", content="new content"
        )
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()
        assert response["safe_mode"] is True

    @pytest.mark.asyncio
    async def test_execute_cell_blocked_in_safe_mode(self, registrar_safe):
        """Test execute_cell is blocked in safe mode."""
        result = await registrar_safe._handle_action(action="execute_cell")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_add_cell_blocked_in_safe_mode(self, registrar_safe):
        """Test add_cell is blocked in safe mode."""
        result = await registrar_safe._handle_action(action="add_cell")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_delete_cell_blocked_in_safe_mode(self, registrar_safe):
        """Test delete_cell is blocked in safe mode."""
        result = await registrar_safe._handle_action(action="delete_cell")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_delete_cells_blocked_in_safe_mode(self, registrar_safe):
        """Test delete_cells is blocked in safe mode."""
        result = await registrar_safe._handle_action(
            action="delete_cells", cell_numbers="[1, 2]"
        )
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_apply_patch_blocked_in_safe_mode(self, registrar_safe):
        """Test apply_patch is blocked in safe mode."""
        result = await registrar_safe._handle_action(
            action="apply_patch", old_text="old", new_text="new"
        )
        response = json.loads(result[0].text)
        assert "error" in response
        assert "unsafe mode" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_safe_actions_allowed_in_safe_mode(self, registrar_safe):
        """Test that safe actions work in safe mode."""
        for action in NotebookMetaToolRegistrar.SAFE_ACTIONS:
            # Provide required params for actions that need them
            kwargs = {}
            if action == "get_variable_info":
                kwargs["name"] = "test"
            elif action == "move_cursor":
                kwargs["target"] = "below"

            result = await registrar_safe._handle_action(action=action, **kwargs)
            response = json.loads(result[0].text)
            # Should not have safe_mode blocking error (may have other errors)
            # safe_mode=True in error response means action was blocked due to safe mode
            if "error" in response:
                assert (
                    response.get("safe_mode") is not True
                ), f"Action {action} should not be blocked in safe mode"


class TestParameterValidation:
    """Test parameter validation for actions."""

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, registrar_safe):
        """Test unknown action returns error with valid actions list."""
        result = await registrar_safe._handle_action(action="invalid_action")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "Unknown action" in response["error"]
        assert "valid_actions" in response
        assert len(response["valid_actions"]) == 13

    @pytest.mark.asyncio
    async def test_action_with_extra_quotes_is_sanitized(
        self, registrar_safe, mock_tools
    ):
        """Test that extra quotes around action are stripped."""
        # LLM sometimes sends '"list_variables"' instead of 'list_variables'
        result = await registrar_safe._handle_action(action='"list_variables"')
        response = json.loads(result[0].text)
        # Should succeed and call the backend method
        # If it failed, response would be a dict with "error" key
        if isinstance(response, dict) and "error" in response:
            assert "Unknown action" not in response["error"]
        # If successful, the mock should have been called
        mock_tools.list_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_required_param_returns_error(self, registrar_safe):
        """Test missing required parameter returns error with usage."""
        # get_variable_info requires 'name'
        result = await registrar_safe._handle_action(action="get_variable_info")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "missing" in response
        assert "name" in response["missing"]
        # Should include usage example
        assert "usage" in response
        assert "get_variable_info" in response["usage"]
        assert "name=" in response["usage"]

    @pytest.mark.asyncio
    async def test_move_cursor_requires_target(self, registrar_safe):
        """Test move_cursor requires target parameter with usage."""
        result = await registrar_safe._handle_action(action="move_cursor")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "target" in response["missing"]
        # Should include usage example
        assert "usage" in response
        assert "move_cursor" in response["usage"]
        assert "target=" in response["usage"]

    @pytest.mark.asyncio
    async def test_invalid_cell_numbers_json(self, registrar_unsafe):
        """Test invalid JSON for cell_numbers returns error with usage."""
        result = await registrar_unsafe._handle_action(
            action="delete_cells", cell_numbers="not json"
        )
        response = json.loads(result[0].text)
        assert "error" in response
        assert "Invalid JSON" in response["error"]
        # Should include usage example
        assert "usage" in response
        assert "delete_cells" in response["usage"]

    @pytest.mark.asyncio
    async def test_cell_numbers_must_be_int_or_list(self, registrar_unsafe):
        """Test cell_numbers must be int or list with usage."""
        result = await registrar_unsafe._handle_action(
            action="delete_cells", cell_numbers='"string"'
        )
        response = json.loads(result[0].text)
        assert "error" in response
        assert "integer or list" in response["error"]
        # Should include usage example
        assert "usage" in response
        assert "cell_numbers=" in response["usage"]


class TestConsentFlow:
    """Test consent handling for unsafe operations."""

    @pytest.mark.asyncio
    async def test_consent_requested_for_execute_cell(
        self, registrar_unsafe, mock_consent_manager, mock_tools
    ):
        """Test consent is requested for execute_cell."""
        await registrar_unsafe._handle_action(action="execute_cell")
        mock_consent_manager.request_consent.assert_called_once()
        call_args = mock_consent_manager.request_consent.call_args
        assert call_args[1]["operation"] == "execute_cell"

    @pytest.mark.asyncio
    async def test_consent_requested_for_update_cell(
        self, registrar_unsafe, mock_consent_manager, mock_tools
    ):
        """Test consent is requested for update_editing_cell."""
        await registrar_unsafe._handle_action(
            action="update_editing_cell", content="new"
        )
        mock_consent_manager.request_consent.assert_called_once()
        call_args = mock_consent_manager.request_consent.call_args
        assert call_args[1]["operation"] == "update_cell"

    @pytest.mark.asyncio
    async def test_consent_declined_returns_error(
        self, registrar_unsafe, mock_consent_manager
    ):
        """Test declined consent returns error without executing."""
        mock_consent_manager.request_consent = AsyncMock(
            return_value={"approved": False, "reason": "User declined"}
        )
        result = await registrar_unsafe._handle_action(action="execute_cell")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "declined" in response["error"].lower()

    @pytest.mark.asyncio
    async def test_add_cell_no_consent_required(
        self, registrar_unsafe, mock_consent_manager, mock_tools
    ):
        """Test add_cell does not require consent."""
        await registrar_unsafe._handle_action(action="add_cell")
        mock_consent_manager.request_consent.assert_not_called()
        mock_tools.add_new_cell.assert_called_once()

    @pytest.mark.asyncio
    async def test_consent_timeout_returns_error(
        self, registrar_unsafe, mock_consent_manager
    ):
        """Test consent timeout returns error."""
        mock_consent_manager.request_consent = AsyncMock(side_effect=TimeoutError())
        result = await registrar_unsafe._handle_action(action="execute_cell")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "timed out" in response["error"].lower()


class TestDangerousMode:
    """Test dangerous mode behavior."""

    @pytest.mark.asyncio
    async def test_dangerous_mode_bypasses_consent(
        self, registrar_dangerous, mock_consent_manager, mock_tools
    ):
        """Test dangerous mode auto-approves consent."""
        await registrar_dangerous._handle_action(action="execute_cell")
        # Consent should be called but return bypass_mode
        mock_consent_manager.request_consent.assert_called_once()
        mock_tools.execute_editing_cell.assert_called_once()


class TestServerStatus:
    """Test server_status action."""

    @pytest.mark.asyncio
    async def test_server_status_safe_mode(self, registrar_safe):
        """Test server_status returns safe mode."""
        result = await registrar_safe._handle_action(action="server_status")
        response = json.loads(result[0].text)
        assert response["mode"] == "safe"
        assert response["status"] == "running"

    @pytest.mark.asyncio
    async def test_server_status_unsafe_mode(self, registrar_unsafe):
        """Test server_status returns unsafe mode."""
        result = await registrar_unsafe._handle_action(action="server_status")
        response = json.loads(result[0].text)
        assert response["mode"] == "unsafe"

    @pytest.mark.asyncio
    async def test_server_status_dangerous_mode(self, registrar_dangerous):
        """Test server_status returns dangerous mode."""
        result = await registrar_dangerous._handle_action(action="server_status")
        response = json.loads(result[0].text)
        assert response["mode"] == "dangerous"


class TestErrorHandling:
    """Test error handling and response format."""

    @pytest.mark.asyncio
    async def test_backend_error_returns_json_error(self, registrar_safe, mock_tools):
        """Test backend errors are returned as JSON."""
        mock_tools.list_variables = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        result = await registrar_safe._handle_action(action="list_variables")
        response = json.loads(result[0].text)
        assert "error" in response
        assert "Database connection failed" in response["error"]

    @pytest.mark.asyncio
    async def test_error_response_includes_action(self, registrar_safe, mock_tools):
        """Test error response includes action name."""
        mock_tools.list_variables = AsyncMock(side_effect=Exception("Error"))
        result = await registrar_safe._handle_action(action="list_variables")
        response = json.loads(result[0].text)
        assert response.get("action") == "list_variables"


class TestToolRegistration:
    """Test tool registration with FastMCP."""

    def test_register_all_creates_notebook_tool(
        self, mock_mcp, mock_tools, mock_ipython
    ):
        """Test register_all creates the notebook tool."""
        registrar = NotebookMetaToolRegistrar(
            mock_mcp, mock_tools, mock_ipython, safe_mode=True
        )
        registrar.register_all()
        mock_mcp.tool.assert_called_once()
        call_kwargs = mock_mcp.tool.call_args[1]
        assert call_kwargs["name"] == "notebook"

    def test_all_actions_documented(self, mock_mcp, mock_tools, mock_ipython):
        """Test all actions are in the class constants."""
        all_actions = (
            NotebookMetaToolRegistrar.SAFE_ACTIONS
            | NotebookMetaToolRegistrar.UNSAFE_ACTIONS
        )
        action_params = NotebookMetaToolRegistrar.ACTION_PARAMS
        # Every action should have params defined
        for action in all_actions:
            assert (
                action in action_params
            ), f"Action {action} missing from ACTION_PARAMS"


class TestSecurityValidation:
    """Test security constraints are enforced."""

    def test_unsafe_mode_requires_consent_manager(
        self, mock_mcp, mock_tools, mock_ipython
    ):
        """Test that unsafe mode without consent_manager raises error."""
        with pytest.raises(ValueError, match="consent_manager is required"):
            NotebookMetaToolRegistrar(
                mock_mcp,
                mock_tools,
                mock_ipython,
                safe_mode=False,  # Unsafe mode
                consent_manager=None,  # Missing consent manager = vulnerability
            )

    def test_safe_mode_allows_no_consent_manager(
        self, mock_mcp, mock_tools, mock_ipython
    ):
        """Test that safe mode works without consent_manager."""
        # Should NOT raise - safe mode doesn't need consent since unsafe actions are blocked
        registrar = NotebookMetaToolRegistrar(
            mock_mcp,
            mock_tools,
            mock_ipython,
            safe_mode=True,
            consent_manager=None,
        )
        assert registrar.safe_mode is True
        assert registrar.consent_manager is None

    def test_unsafe_mode_with_consent_manager_works(
        self, mock_mcp, mock_tools, mock_ipython, mock_consent_manager
    ):
        """Test that unsafe mode with consent_manager initializes correctly."""
        registrar = NotebookMetaToolRegistrar(
            mock_mcp,
            mock_tools,
            mock_ipython,
            safe_mode=False,
            consent_manager=mock_consent_manager,
        )
        assert registrar.safe_mode is False
        assert registrar.consent_manager is mock_consent_manager


class TestFastMCPIntegration:
    """Integration tests with real FastMCP to verify Pydantic validation."""

    @pytest.fixture
    def real_mcp(self):
        """Create a real FastMCP instance for integration testing."""
        from fastmcp import FastMCP

        return FastMCP("test-notebook")

    @pytest.fixture
    def integration_registrar(self, real_mcp, mock_tools, mock_ipython):
        """Create registrar with real FastMCP."""
        registrar = NotebookMetaToolRegistrar(
            real_mcp,
            mock_tools,
            mock_ipython,
            safe_mode=True,
            consent_manager=None,
        )
        registrar.register_all()
        return registrar

    def _get_tool_fn(self, mcp, tool_name):
        """Get the tool function from FastMCP's tool manager."""
        tool_info = mcp._tool_manager._tools.get(tool_name)
        assert tool_info is not None, f"Tool '{tool_name}' should be registered"
        return tool_info.fn

    @pytest.mark.asyncio
    async def test_tool_accepts_null_optional_params(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test that tool accepts None for Optional params (Pydantic validation)."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        # Call with explicit None values - this is what MCP Inspector sends
        result = await notebook_tool(
            action="list_variables",
            name=None,
            type_filter=None,
            fresh_ms=1000,
            line_start=None,
            line_end=None,
            max_lines=200,
            num_cells=2,
            include_output=True,
            target=None,
            content=None,
            cell_type="code",
            position="below",
            cell_numbers=None,
            old_text=None,
            new_text=None,
        )
        # Should succeed without Pydantic validation error
        assert len(result) == 1
        mock_tools.list_variables.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_accepts_minimal_params(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test that tool works with only required params."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        # Call with only action (minimal call)
        result = await notebook_tool(action="list_variables")
        assert len(result) == 1
        mock_tools.list_variables.assert_called()

    @pytest.mark.asyncio
    async def test_get_editing_cell_with_null_line_params(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test get_editing_cell accepts null line_start/line_end."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        result = await notebook_tool(
            action="get_editing_cell",
            line_start=None,
            line_end=None,
        )
        assert len(result) == 1
        mock_tools.get_editing_cell.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_variable_info_with_required_name(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test get_variable_info with required name param."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        result = await notebook_tool(
            action="get_variable_info",
            name="my_var",
        )
        assert len(result) == 1
        mock_tools.get_variable_info.assert_called_once_with("my_var")

    @pytest.mark.asyncio
    async def test_move_cursor_with_required_target(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test move_cursor with required target param."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        result = await notebook_tool(
            action="move_cursor",
            target="below",
        )
        assert len(result) == 1
        mock_tools.move_cursor.assert_called_once_with("below")

    @pytest.mark.asyncio
    async def test_action_sanitization_through_fastmcp(
        self, real_mcp, integration_registrar, mock_tools
    ):
        """Test that quoted action is sanitized even through FastMCP."""
        notebook_tool = self._get_tool_fn(real_mcp, "notebook")

        # LLM sometimes sends '"list_variables"' with extra quotes
        result = await notebook_tool(action='"list_variables"')
        assert len(result) == 1
        # Should succeed after stripping quotes - check no error in response
        response = json.loads(result[0].text)
        # Response could be a list (success) or dict (error)
        if isinstance(response, dict):
            assert "Unknown action" not in response.get("error", "")
        # If it's a list, the action succeeded (list_variables returns a list)
        mock_tools.list_variables.assert_called_once()

    def test_tool_schema_has_optional_types(self, real_mcp, integration_registrar):
        """Verify that FastMCP generates correct schema with anyOf for Optional types."""
        tool_info = real_mcp._tool_manager._tools.get("notebook")
        assert tool_info is not None

        params = tool_info.parameters
        properties = params.get("properties", {})

        # Check that Optional[str] params have 'anyOf' with null type
        for optional_param in [
            "name",
            "type_filter",
            "target",
            "content",
            "old_text",
            "new_text",
            "cell_numbers",
        ]:
            prop = properties.get(optional_param, {})
            # FastMCP should generate: {"anyOf": [{"type": "string"}, {"type": "null"}]}
            assert (
                "anyOf" in prop or prop.get("type") == "string"
            ), f"Param '{optional_param}' should have anyOf or be optional"

        # Check that Optional[int] params have 'anyOf' with null type
        for optional_int_param in ["line_start", "line_end"]:
            prop = properties.get(optional_int_param, {})
            assert (
                "anyOf" in prop or prop.get("type") == "integer"
            ), f"Param '{optional_int_param}' should have anyOf or be optional"
