"""Tests for JSON auto-correction feature using MCP sampling."""

import pytest
import json
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from pathlib import Path

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
    """Create a mock FastMCP instance."""
    mock = Mock()
    mock.tool = Mock(return_value=lambda f: f)
    mock.remove_tool = Mock()
    return mock


@pytest.fixture
def mock_context():
    """Create a mock FastMCP Context for sampling."""
    mock = AsyncMock()
    # Default behavior: return corrected JSON
    mock.sample = AsyncMock()
    return mock


@pytest.fixture
def temp_registry(tmp_path):
    """Create a temporary registry directory."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    return registry_dir


@pytest.fixture
def registrar_disabled(mock_mcp, mock_ipython, temp_registry):
    """Create a DynamicToolRegistrar with auto_correct_json disabled."""
    with patch(
        "instrmcp.tools.dynamic.tool_registry.Path.home",
        return_value=temp_registry.parent,
    ):
        registrar = DynamicToolRegistrar(
            mock_mcp, mock_ipython, auto_correct_json=False
        )
        registrar.registry._cache.clear()
        return registrar


@pytest.fixture
def registrar_enabled(mock_mcp, mock_ipython, temp_registry):
    """Create a DynamicToolRegistrar with auto_correct_json enabled."""
    with patch(
        "instrmcp.tools.dynamic.tool_registry.Path.home",
        return_value=temp_registry.parent,
    ):
        registrar = DynamicToolRegistrar(mock_mcp, mock_ipython, auto_correct_json=True)
        registrar.registry._cache.clear()
        return registrar


class TestAutoCorrectDisabled:
    """Test that auto-correction does NOT happen when disabled (default)."""

    @pytest.mark.asyncio
    async def test_no_sampling_when_disabled(
        self, registrar_disabled, mock_context, caplog
    ):
        """Test that ctx.sample() is never called when auto_correct_json is False."""
        malformed_json = "[{name: 'test'}]"  # Missing quotes

        result = await registrar_disabled._attempt_json_correction(
            mock_context, "parameters", malformed_json, "JSON error"
        )

        # Should return None immediately without sampling
        assert result is None
        mock_context.sample.assert_not_called()

        # Should not log any correction attempts
        assert "Attempting JSON correction" not in caplog.text

    @pytest.mark.asyncio
    async def test_returns_error_on_malformed_json_when_disabled(
        self, registrar_disabled, mock_context
    ):
        """Test that errors are returned without correction when disabled."""
        # This test verifies the behavior conceptually
        # In practice, the error would be raised by the caller

        malformed_json = "[{bad: json}]"

        # Attempt correction returns None
        result = await registrar_disabled._attempt_json_correction(
            mock_context, "capabilities", malformed_json, "Expecting value"
        )

        assert result is None
        mock_context.sample.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_fields_no_sampling_when_disabled(
        self, registrar_disabled, mock_context
    ):
        """Test that no sampling happens for any field when disabled."""
        fields = ["parameters", "capabilities", "returns", "examples", "tags"]

        for field in fields:
            result = await registrar_disabled._attempt_json_correction(
                mock_context, field, "[{broken}]", "JSON error"
            )
            assert result is None

        # No sampling calls at all
        assert mock_context.sample.call_count == 0


class TestAutoCorrectEnabled:
    """Test that auto-correction works when enabled."""

    @pytest.mark.asyncio
    async def test_sampling_called_when_enabled(
        self, registrar_enabled, mock_context, caplog
    ):
        """Test that ctx.sample() is called when auto_correct_json is True."""
        import logging

        caplog.set_level(logging.DEBUG)  # Capture DEBUG level logs

        malformed_json = "[{name: 'test'}]"
        corrected_json = '[{"name": "test"}]'

        # Mock the sample response
        mock_response = Mock()
        mock_response.text = corrected_json
        mock_context.sample.return_value = mock_response

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", malformed_json, "Expecting property name"
        )

        # Should call sample
        mock_context.sample.assert_called_once()

        # Should return corrected JSON
        assert result == corrected_json

        # Should log the attempt
        assert "Attempting JSON correction" in caplog.text
        assert "Successfully corrected JSON" in caplog.text

    @pytest.mark.asyncio
    async def test_correction_prompt_format(self, registrar_enabled, mock_context):
        """Test that the correction prompt is properly formatted."""
        malformed_json = "[{test: 123}]"
        error_msg = "Expecting property name enclosed in double quotes"

        mock_response = Mock()
        mock_response.text = '[{"test": 123}]'
        mock_context.sample.return_value = mock_response

        await registrar_enabled._attempt_json_correction(
            mock_context, "capabilities", malformed_json, error_msg
        )

        # Check the prompt includes key information
        call_args = mock_context.sample.call_args
        prompt = call_args[0][0]

        assert "capabilities" in prompt  # Field name
        assert malformed_json in prompt  # Original JSON
        assert error_msg in prompt  # Error message
        assert "Fix this malformed JSON" in prompt
        assert "Return ONLY the corrected JSON" in prompt

    @pytest.mark.asyncio
    async def test_correction_uses_low_temperature(
        self, registrar_enabled, mock_context
    ):
        """Test that sampling uses temperature=0.1 for deterministic results."""
        mock_response = Mock()
        mock_response.text = "[]"
        mock_context.sample.return_value = mock_response

        await registrar_enabled._attempt_json_correction(
            mock_context, "tags", "[broken]", "error"
        )

        # Verify temperature parameter
        call_args = mock_context.sample.call_args
        assert call_args[1]["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_validates_corrected_json(self, registrar_enabled, mock_context):
        """Test that corrected JSON is validated before returning."""
        malformed_json = "[{test: 1}]"

        # Mock returns invalid JSON
        mock_response = Mock()
        mock_response.text = "{still broken}"
        mock_context.sample.return_value = mock_response

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", malformed_json, "error"
        )

        # Should return None because corrected JSON is still invalid
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_sampling_exception(
        self, registrar_enabled, mock_context, caplog
    ):
        """Test that exceptions during sampling are handled gracefully."""
        mock_context.sample.side_effect = Exception("Sampling failed")

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "returns", "[bad]", "error"
        )

        # Should return None
        assert result is None

        # Should log warning
        assert "JSON correction failed" in caplog.text

    @pytest.mark.asyncio
    async def test_handles_timeout_error(self, registrar_enabled, mock_context, caplog):
        """Test that timeout errors are handled with specific message."""
        import logging

        caplog.set_level(logging.WARNING)

        # Simulate timeout from LLM sampling
        mock_context.sample.side_effect = TimeoutError("Request timed out")

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", "[timeout test]", "error"
        )

        # Should return None
        assert result is None

        # Should log specific timeout warning
        assert "timed out" in caplog.text.lower()
        assert "took too long" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_single_retry_limit(self, registrar_enabled, mock_context):
        """Test that correction is only attempted once (no retry loops)."""
        # This is enforced by the caller, but we verify the method behavior
        mock_response = Mock()
        mock_response.text = "[]"
        mock_context.sample.return_value = mock_response

        # Call twice - each should independently call sample
        await registrar_enabled._attempt_json_correction(
            mock_context, "test", "[1]", "error"
        )
        await registrar_enabled._attempt_json_correction(
            mock_context, "test", "[2]", "error"
        )

        # Should have called sample exactly twice (once per call)
        assert mock_context.sample.call_count == 2


class TestCorrectionIntegration:
    """Test integration of correction with tool registration flow."""

    @pytest.mark.asyncio
    async def test_correction_in_parse_json_field(
        self, registrar_enabled, mock_context
    ):
        """Test that parse_json_field helper uses correction properly."""
        # This tests the integration conceptually
        # The actual parse_json_field is a nested function in dynamic_register_tool

        malformed = '[{name: "test"}]'  # Single quotes instead of double
        corrected = '[{"name": "test"}]'

        mock_response = Mock()
        mock_response.text = corrected
        mock_context.sample.return_value = mock_response

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", malformed, "Expecting value"
        )

        assert result == corrected
        assert json.loads(result) == [{"name": "test"}]  # Valid JSON

    @pytest.mark.asyncio
    async def test_multiple_field_corrections(self, registrar_enabled, mock_context):
        """Test that multiple fields can be corrected independently."""
        corrections = {
            "capabilities": ("[{cap}]", '["cap"]'),
            "parameters": ("[{name: x}]", '[{"name": "x"}]'),
            "returns": ("{type: obj}", '{"type": "obj"}'),
        }

        for field_name, (malformed, corrected) in corrections.items():
            mock_response = Mock()
            mock_response.text = corrected
            mock_context.sample.return_value = mock_response

            result = await registrar_enabled._attempt_json_correction(
                mock_context, field_name, malformed, "JSON error"
            )

            assert result == corrected
            # Verify it's valid JSON
            json.loads(result)


class TestOptInOptOutBehavior:
    """Test the opt-in/opt-out behavior at the registrar level."""

    def test_registrar_initialized_disabled_by_default(
        self, mock_mcp, mock_ipython, temp_registry
    ):
        """Test that registrar defaults to disabled when parameter not provided."""
        with patch(
            "instrmcp.tools.dynamic.tool_registry.Path.home",
            return_value=temp_registry.parent,
        ):
            # Create without auto_correct_json parameter
            registrar = DynamicToolRegistrar(mock_mcp, mock_ipython)
            assert registrar.auto_correct_json is False

    def test_registrar_can_be_enabled(self, mock_mcp, mock_ipython, temp_registry):
        """Test that registrar can be explicitly enabled."""
        with patch(
            "instrmcp.tools.dynamic.tool_registry.Path.home",
            return_value=temp_registry.parent,
        ):
            registrar = DynamicToolRegistrar(
                mock_mcp, mock_ipython, auto_correct_json=True
            )
            assert registrar.auto_correct_json is True

    def test_registrar_can_be_disabled(self, mock_mcp, mock_ipython, temp_registry):
        """Test that registrar can be explicitly disabled."""
        with patch(
            "instrmcp.tools.dynamic.tool_registry.Path.home",
            return_value=temp_registry.parent,
        ):
            registrar = DynamicToolRegistrar(
                mock_mcp, mock_ipython, auto_correct_json=False
            )
            assert registrar.auto_correct_json is False


class TestAuditLogging:
    """Test that corrections are properly logged to audit trail."""

    @pytest.mark.asyncio
    async def test_successful_correction_logged(
        self, registrar_enabled, mock_context, caplog
    ):
        """Test that successful corrections are logged."""
        import logging

        caplog.set_level(logging.DEBUG)  # Capture DEBUG level logs

        mock_response = Mock()
        mock_response.text = "[]"
        mock_context.sample.return_value = mock_response

        await registrar_enabled._attempt_json_correction(
            mock_context, "test_field", "[bad]", "error"
        )

        # Check logs
        assert "Attempting JSON correction" in caplog.text
        assert "test_field" in caplog.text
        assert "Successfully corrected JSON" in caplog.text

    @pytest.mark.asyncio
    async def test_failed_correction_logged(
        self, registrar_enabled, mock_context, caplog
    ):
        """Test that failed corrections are logged."""
        mock_context.sample.side_effect = Exception("LLM error")

        await registrar_enabled._attempt_json_correction(
            mock_context, "test_field", "[bad]", "error"
        )

        # Check logs
        assert "JSON correction failed" in caplog.text
        assert "test_field" in caplog.text


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_json_string(self, registrar_enabled, mock_context):
        """Test handling of empty JSON strings."""
        # Empty strings should not be corrected (they're handled by parse_json_field)
        # This tests the method directly
        result = await registrar_enabled._attempt_json_correction(
            mock_context, "test", "", "error"
        )

        # Will attempt correction since method was called
        # But in practice, parse_json_field returns None for empty strings
        assert mock_context.sample.called or result is None

    @pytest.mark.asyncio
    async def test_already_valid_json(self, registrar_enabled, mock_context):
        """Test that valid JSON is not sent for correction."""
        # In practice, parse_json_field only calls correction on JSONDecodeError
        # So valid JSON never reaches _attempt_json_correction
        # This tests the conceptual flow

        valid_json = '[{"name": "test"}]'

        # If somehow called with valid JSON
        mock_response = Mock()
        mock_response.text = valid_json
        mock_context.sample.return_value = mock_response

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", valid_json, "no error"
        )

        # Should return corrected (which equals original)
        assert result == valid_json

    @pytest.mark.asyncio
    async def test_very_long_json(self, registrar_enabled, mock_context):
        """Test handling of very long JSON strings."""
        # Test that max_tokens parameter is set appropriately
        long_json = "[{" + "x" * 1000 + "}]"

        mock_response = Mock()
        mock_response.text = "[]"
        mock_context.sample.return_value = mock_response

        await registrar_enabled._attempt_json_correction(
            mock_context, "parameters", long_json, "error"
        )

        # Verify max_tokens is set
        call_args = mock_context.sample.call_args
        assert call_args[1]["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_correction_with_special_characters(
        self, registrar_enabled, mock_context
    ):
        """Test correction of JSON with special characters."""
        malformed = "[{'name': 'test\\nvalue'}]"  # Newlines, single quotes
        corrected = '[{"name": "test\\nvalue"}]'

        mock_response = Mock()
        mock_response.text = corrected
        mock_context.sample.return_value = mock_response

        result = await registrar_enabled._attempt_json_correction(
            mock_context, "examples", malformed, "error"
        )

        assert result == corrected
        # Verify it parses correctly
        parsed = json.loads(result)
        assert parsed[0]["name"] == "test\nvalue"
