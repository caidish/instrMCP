"""
Unit tests for MeasureIt integration tool registrar.

Tests MeasureItToolRegistrar for registering MeasureIt sweep monitoring tools with FastMCP.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from mcp.types import TextContent

from instrmcp.servers.jupyter_qcodes.registrars.measureit_tools import (
    MeasureItToolRegistrar,
)


class TestMeasureItToolRegistrar:
    """Test MeasureItToolRegistrar class for registering MeasureIt tools."""

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
        tools.get_measureit_status = AsyncMock()
        tools.wait_for_all_sweeps = AsyncMock()
        tools.wait_for_sweep = AsyncMock()
        return tools

    @pytest.fixture
    def registrar(self, mock_mcp_server, mock_tools):
        """Create a MeasureItToolRegistrar instance."""
        return MeasureItToolRegistrar(mock_mcp_server, mock_tools)

    def test_initialization(self, mock_mcp_server, mock_tools):
        """Test registrar initialization."""
        registrar = MeasureItToolRegistrar(mock_mcp_server, mock_tools)
        assert registrar.mcp == mock_mcp_server
        assert registrar.tools == mock_tools

    def test_register_all(self, registrar, mock_mcp_server):
        """Test registering all MeasureIt tools."""
        registrar.register_all()

        # Check that all MeasureIt tools were registered
        for tool_name in [
            "measureit_get_status",
            "measureit_wait_for_all_sweeps",
            "measureit_wait_for_sweep",
        ]:
            assert tool_name in mock_mcp_server._tools
            assert callable(mock_mcp_server._tools[tool_name])

    @pytest.mark.asyncio
    async def test_get_status_no_sweeps_running(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status when no sweeps are running."""
        mock_status = {
            "running": False,
            "sweeps": [],
            "checked_variables": ["sweep1d_obj", "sweep2d_obj"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)

        response_data = json.loads(result[0].text)
        assert response_data["running"] is False
        assert len(response_data["sweeps"]) == 0
        mock_tools.get_measureit_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_with_running_sweep(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with a running sweep."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "my_sweep1d",
                    "type": "Sweep1D",
                    "module": "measureit.sweep.sweep1d",
                    "is_running": True,
                    "progress": 0.45,
                    "elapsed_time": 12.0,
                    "time_remaining": 15.0,
                }
            ],
            "checked_variables": ["my_sweep1d", "other_sweep"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is True
        assert len(response_data["sweeps"]) == 1
        sweep = response_data["sweeps"][0]
        assert sweep["type"] == "Sweep1D"
        assert sweep["module"] == "measureit.sweep.sweep1d"
        assert sweep["is_running"] is True
        assert sweep["progress"] == 0.45

    @pytest.mark.asyncio
    async def test_wait_for_all_sweeps_tool(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test wait_for_all_sweeps tool registration and execution."""
        mock_tools.wait_for_all_sweeps.return_value = {"sweeps": []}

        registrar.register_all()
        wait_tool = mock_mcp_server._tools["measureit_wait_for_all_sweeps"]
        result = await wait_tool()

        assert isinstance(result, list)
        assert isinstance(result[0], TextContent)
        payload = json.loads(result[0].text)
        assert payload["sweeps"] == []
        mock_tools.wait_for_all_sweeps.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_sweep_tool(self, registrar, mock_tools, mock_mcp_server):
        """Test wait_for_sweep tool registration and execution."""
        mock_tools.wait_for_sweep.return_value = {"sweep": {"variable_name": "s1"}}

        registrar.register_all()
        wait_tool = mock_mcp_server._tools["measureit_wait_for_sweep"]
        result = await wait_tool("s1")

        assert isinstance(result, list)
        assert isinstance(result[0], TextContent)
        payload = json.loads(result[0].text)
        assert payload["sweep"]["variable_name"] == "s1"
        mock_tools.wait_for_sweep.assert_called_once_with("s1")

    @pytest.mark.asyncio
    async def test_get_status_with_multiple_sweeps(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with multiple sweeps."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "sweep1d",
                    "type": "Sweep1D",
                    "module": "measureit.sweep.sweep1d",
                    "is_running": True,
                    "progress": 0.2,
                },
                {
                    "variable_name": "sweep2d",
                    "type": "Sweep2D",
                    "module": "measureit.sweep.sweep2d",
                    "is_running": False,
                    "progress": 0.75,
                },
                {
                    "variable_name": "sweep0d",
                    "type": "Sweep0D",
                    "module": "measureit.sweep.sweep0d",
                    "is_running": False,
                    "progress": 1.0,
                },
            ],
            "checked_variables": ["sweep1d", "sweep2d", "sweep0d"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is True
        assert len(response_data["sweeps"]) == 3
        assert response_data["sweeps"][0]["type"] == "Sweep1D"
        assert response_data["sweeps"][1]["is_running"] is False
        assert response_data["sweeps"][2]["progress"] == 1.0

    @pytest.mark.asyncio
    async def test_get_status_error(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with error."""
        mock_tools.get_measureit_status.side_effect = Exception(
            "MeasureIt not available"
        )

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "MeasureIt not available" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_status_with_sweep_config(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with detailed sweep configuration."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "complex_sweep",
                    "type": "Sweep2D",
                    "module": "measureit.sweep.sweep2d",
                    "is_running": True,
                    "progress": 0.2468,
                    "elapsed_time": 120.0,
                    "time_remaining": 360.0,
                }
            ],
            "checked_variables": ["complex_sweep"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert sweep["type"] == "Sweep2D"
        assert sweep["is_running"] is True
        assert sweep["progress"] == 0.2468
        assert sweep["elapsed_time"] == 120.0
        assert sweep["time_remaining"] == 360.0

    @pytest.mark.asyncio
    async def test_get_status_with_sweep_queue(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with SweepQueue."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "my_queue",
                    "type": "SweepQueue",
                    "module": "measureit.sweep.queue",
                    "is_running": True,
                    "progress": 0.5,
                    "elapsed_time": 90.0,
                    "time_remaining": 30.0,
                    "queue_length": 5,
                    "current_sweep_index": 2,
                }
            ],
            "checked_variables": ["my_queue"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert sweep["type"] == "SweepQueue"
        assert sweep["queue_length"] == 5
        assert sweep["current_sweep_index"] == 2

    @pytest.mark.asyncio
    async def test_get_status_with_empty_checked_variables(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status when no variables were checked."""
        mock_status = {"running": False, "sweeps": [], "checked_variables": []}
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is False
        assert len(response_data["checked_variables"]) == 0

    @pytest.mark.asyncio
    async def test_get_status_with_idle_sweep(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with idle/completed sweeps."""
        mock_status = {
            "running": False,
            "sweeps": [
                {
                    "variable_name": "completed_sweep",
                    "type": "Sweep1D",
                    "module": "measureit.sweep.sweep1d",
                    "is_running": False,
                    "progress": 1.0,
                    "elapsed_time": 240.0,
                    "time_remaining": 0.0,
                    "completed": True,
                }
            ],
            "checked_variables": ["completed_sweep"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is False
        assert response_data["sweeps"][0]["is_running"] is False

    @pytest.mark.asyncio
    async def test_get_status_returns_text_content(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test that get_status returns TextContent."""
        mock_status = {"running": False, "sweeps": [], "checked_variables": []}
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].type == "text"

    @pytest.mark.asyncio
    async def test_get_status_json_serialization(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test that get_status properly serializes complex objects."""
        from datetime import datetime

        # Include objects that need default=str serialization
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "sweep",
                    "type": "Sweep1D",
                    "module": "measureit.sweep.sweep1d",
                    "is_running": True,
                    "timestamp": datetime(2024, 1, 1, 12, 0, 0),
                }
            ],
            "checked_variables": ["sweep"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        # Should not raise JSON serialization error
        response_data = json.loads(result[0].text)
        assert response_data["running"] is True

    def test_three_tools_registered(self, registrar, mock_mcp_server):
        """Test that the get_status, wait_for_sweep, and wait_for_all_sweeps tools are registered."""
        registrar.register_all()

        # Should only have one MeasureIt tool
        measureit_tools = [
            name
            for name in mock_mcp_server._tools.keys()
            if name.startswith("measureit_")
        ]
        assert len(measureit_tools) == 3
        assert "measureit_get_status" in measureit_tools
        assert "measureit_wait_for_sweep" in measureit_tools
        assert "measureit_wait_for_all_sweeps" in measureit_tools

    @pytest.mark.asyncio
    async def test_get_status_with_simul_sweep(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test getting MeasureIt status with SimulSweep."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "simul_sweep",
                    "type": "SimulSweep",
                    "module": "measureit.sweep.simulsweep",
                    "is_running": True,
                    "progress": 0.33,
                    "elapsed_time": 45.0,
                    "time_remaining": 90.0,
                    "parameters": ["gate1", "gate2", "gate3"],
                    "simultaneous": True,
                }
            ],
            "checked_variables": ["simul_sweep"],
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert sweep["type"] == "SimulSweep"
        assert len(sweep["parameters"]) == 3
        assert sweep["simultaneous"] is True
