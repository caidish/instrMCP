"""
Unit tests for QCodes tool registrar.

Tests QCodesToolRegistrar for registering QCodes instrument tools with FastMCP.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from mcp.types import TextContent

from instrmcp.servers.jupyter_qcodes.registrars.qcodes_tools import QCodesToolRegistrar


class TestQCodesToolRegistrar:
    """Test QCodesToolRegistrar class for registering QCodes tools."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server."""
        mcp = MagicMock()
        mcp._tools = {}

        # Mock the @mcp.tool decorator
        def tool_decorator(name=None):
            def wrapper(func):
                tool_name = name or func.__name__
                mcp._tools[tool_name] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance."""
        tools = MagicMock()
        tools.instrument_info = AsyncMock()
        tools.get_parameter_values = AsyncMock()
        return tools

    @pytest.fixture
    def registrar(self, mock_mcp_server, mock_tools):
        """Create a QCodesToolRegistrar instance."""
        return QCodesToolRegistrar(mock_mcp_server, mock_tools)

    def test_initialization(self, mock_mcp_server, mock_tools):
        """Test registrar initialization."""
        registrar = QCodesToolRegistrar(mock_mcp_server, mock_tools)
        assert registrar.mcp == mock_mcp_server
        assert registrar.tools == mock_tools

    def test_register_all(self, registrar, mock_mcp_server):
        """Test registering all QCodes tools."""
        registrar.register_all()

        # Check that both tools were registered
        assert "qcodes_instrument_info" in mock_mcp_server._tools
        assert "qcodes_get_parameter_values" in mock_mcp_server._tools

    @pytest.mark.asyncio
    async def test_instrument_info_success(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test successful instrument info retrieval."""
        # Setup mock response
        mock_info = {
            "name": "mock_dac",
            "parameters": {"ch01.voltage": {"value": 3.14, "unit": "V"}},
        }
        mock_tools.instrument_info.return_value = mock_info

        # Register tools
        registrar.register_all()

        # Call the registered tool
        instrument_info_func = mock_mcp_server._tools["qcodes_instrument_info"]
        result = await instrument_info_func(name="mock_dac", with_values=True)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        response_data = json.loads(result[0].text)
        assert response_data == mock_info
        mock_tools.instrument_info.assert_called_once_with("mock_dac", True)

    @pytest.mark.asyncio
    async def test_instrument_info_without_values(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test instrument info without cached values."""
        mock_info = {"name": "mock_dac", "parameters": {}}
        mock_tools.instrument_info.return_value = mock_info

        registrar.register_all()
        instrument_info_func = mock_mcp_server._tools["qcodes_instrument_info"]
        result = await instrument_info_func(name="mock_dac", with_values=False)

        response_data = json.loads(result[0].text)
        assert response_data == mock_info
        mock_tools.instrument_info.assert_called_once_with("mock_dac", False)

    @pytest.mark.asyncio
    async def test_instrument_info_error(self, registrar, mock_tools, mock_mcp_server):
        """Test instrument info with error."""
        # Setup mock to raise exception
        mock_tools.instrument_info.side_effect = ValueError("Instrument not found")

        registrar.register_all()
        instrument_info_func = mock_mcp_server._tools["qcodes_instrument_info"]
        result = await instrument_info_func(name="nonexistent", with_values=False)

        # Verify error response
        assert isinstance(result, list)
        assert len(result) == 1
        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Instrument not found" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_parameter_values_single_query(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting parameter values with single query."""
        query = {"instrument": "mock_dac", "parameter": "ch01.voltage", "fresh": False}
        mock_result = {"value": 3.14, "unit": "V", "timestamp": 1234567890}
        mock_tools.get_parameter_values.return_value = mock_result

        registrar.register_all()
        get_values_func = mock_mcp_server._tools["qcodes_get_parameter_values"]
        result = await get_values_func(queries=json.dumps(query))

        response_data = json.loads(result[0].text)
        assert response_data == mock_result
        mock_tools.get_parameter_values.assert_called_once_with(query)

    @pytest.mark.asyncio
    async def test_get_parameter_values_batch_query(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting parameter values with batch query."""
        queries = [
            {"instrument": "mock_dac", "parameter": "ch01.voltage"},
            {"instrument": "mock_dac", "parameter": "ch02.voltage"},
        ]
        mock_result = [{"value": 3.14, "unit": "V"}, {"value": 2.71, "unit": "V"}]
        mock_tools.get_parameter_values.return_value = mock_result

        registrar.register_all()
        get_values_func = mock_mcp_server._tools["qcodes_get_parameter_values"]
        result = await get_values_func(queries=json.dumps(queries))

        response_data = json.loads(result[0].text)
        assert response_data == mock_result
        mock_tools.get_parameter_values.assert_called_once_with(queries)

    @pytest.mark.asyncio
    async def test_get_parameter_values_invalid_json(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting parameter values with invalid JSON."""
        registrar.register_all()
        get_values_func = mock_mcp_server._tools["qcodes_get_parameter_values"]
        result = await get_values_func(queries="not valid json")

        response_data = json.loads(result[0].text)
        assert "error" in response_data

    @pytest.mark.asyncio
    async def test_get_parameter_values_error(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting parameter values with error."""
        query = {"instrument": "mock_dac", "parameter": "nonexistent"}
        mock_tools.get_parameter_values.side_effect = ValueError("Parameter not found")

        registrar.register_all()
        get_values_func = mock_mcp_server._tools["qcodes_get_parameter_values"]
        result = await get_values_func(queries=json.dumps(query))

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Parameter not found" in response_data["error"]

    @pytest.mark.asyncio
    async def test_instrument_info_with_complex_data(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test instrument info with complex nested data structures."""
        mock_info = {
            "name": "mock_dac",
            "type": "DAC",
            "parameters": {
                "ch01": {
                    "voltage": {"value": 3.14, "unit": "V", "limits": [-10, 10]},
                    "current": {"value": 0.001, "unit": "A"},
                },
                "ch02": {"voltage": {"value": 2.71, "unit": "V", "limits": [-10, 10]}},
            },
            "submodules": ["ch01", "ch02"],
            "metadata": {"serial": "12345", "firmware": "1.2.3"},
        }
        mock_tools.instrument_info.return_value = mock_info

        registrar.register_all()
        instrument_info_func = mock_mcp_server._tools["qcodes_instrument_info"]
        result = await instrument_info_func(name="mock_dac", with_values=True)

        response_data = json.loads(result[0].text)
        assert response_data == mock_info
        assert "submodules" in response_data
        assert len(response_data["submodules"]) == 2

    def test_registrar_tool_names(self, registrar, mock_mcp_server):
        """Test that tools are registered with correct names."""
        registrar.register_all()

        expected_tools = ["qcodes_instrument_info", "qcodes_get_parameter_values"]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_server._tools
            assert callable(mock_mcp_server._tools[tool_name])
