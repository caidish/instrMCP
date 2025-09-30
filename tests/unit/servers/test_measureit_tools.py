"""
Unit tests for MeasureIt integration tool registrar.

Tests MeasureItToolRegistrar for registering MeasureIt sweep monitoring tools with FastMCP.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from mcp.types import TextContent

from instrmcp.servers.jupyter_qcodes.registrars.measureit_tools import MeasureItToolRegistrar


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

        # Check that the get_status tool was registered
        assert "measureit_get_status" in mock_mcp_server._tools
        assert callable(mock_mcp_server._tools["measureit_get_status"])

    @pytest.mark.asyncio
    async def test_get_status_no_sweeps_running(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status when no sweeps are running."""
        mock_status = {
            "running": False,
            "sweeps": [],
            "checked_variables": ["sweep1d_obj", "sweep2d_obj"]
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
    async def test_get_status_with_running_sweep(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with a running sweep."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "my_sweep1d",
                    "sweep_type": "Sweep1D",
                    "status": "running",
                    "config": {
                        "parameter": "gate_voltage",
                        "start": 0.0,
                        "stop": 1.0,
                        "num_points": 100
                    }
                }
            ],
            "checked_variables": ["my_sweep1d", "other_sweep"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is True
        assert len(response_data["sweeps"]) == 1
        assert response_data["sweeps"][0]["sweep_type"] == "Sweep1D"
        assert response_data["sweeps"][0]["status"] == "running"

    @pytest.mark.asyncio
    async def test_get_status_with_multiple_sweeps(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with multiple sweeps."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "sweep1d",
                    "sweep_type": "Sweep1D",
                    "status": "running"
                },
                {
                    "variable_name": "sweep2d",
                    "sweep_type": "Sweep2D",
                    "status": "paused"
                },
                {
                    "variable_name": "sweep0d",
                    "sweep_type": "Sweep0D",
                    "status": "completed"
                }
            ],
            "checked_variables": ["sweep1d", "sweep2d", "sweep0d"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is True
        assert len(response_data["sweeps"]) == 3
        assert response_data["sweeps"][0]["sweep_type"] == "Sweep1D"
        assert response_data["sweeps"][1]["status"] == "paused"
        assert response_data["sweeps"][2]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_status_error(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with error."""
        mock_tools.get_measureit_status.side_effect = Exception("MeasureIt not available")

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "MeasureIt not available" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_status_with_sweep_config(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with detailed sweep configuration."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "complex_sweep",
                    "sweep_type": "Sweep2D",
                    "status": "running",
                    "config": {
                        "outer_parameter": "gate_voltage",
                        "outer_start": -1.0,
                        "outer_stop": 1.0,
                        "outer_points": 50,
                        "inner_parameter": "bias_voltage",
                        "inner_start": -0.5,
                        "inner_stop": 0.5,
                        "inner_points": 100,
                        "delay": 0.001,
                        "measured_parameters": ["current", "conductance"]
                    },
                    "progress": {
                        "current_point": 1234,
                        "total_points": 5000,
                        "percentage": 24.68
                    }
                }
            ],
            "checked_variables": ["complex_sweep"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert "config" in sweep
        assert "progress" in sweep
        assert sweep["config"]["outer_parameter"] == "gate_voltage"
        assert sweep["progress"]["percentage"] == 24.68

    @pytest.mark.asyncio
    async def test_get_status_with_sweep_queue(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with SweepQueue."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "my_queue",
                    "sweep_type": "SweepQueue",
                    "status": "running",
                    "config": {
                        "queue_length": 5,
                        "current_sweep_index": 2,
                        "sweeps": [
                            {"type": "Sweep1D", "parameter": "gate"},
                            {"type": "Sweep2D", "parameter": "bias"},
                            {"type": "Sweep1D", "parameter": "field"}
                        ]
                    }
                }
            ],
            "checked_variables": ["my_queue"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert sweep["sweep_type"] == "SweepQueue"
        assert sweep["config"]["queue_length"] == 5
        assert sweep["config"]["current_sweep_index"] == 2

    @pytest.mark.asyncio
    async def test_get_status_with_empty_checked_variables(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status when no variables were checked."""
        mock_status = {
            "running": False,
            "sweeps": [],
            "checked_variables": []
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is False
        assert len(response_data["checked_variables"]) == 0

    @pytest.mark.asyncio
    async def test_get_status_with_idle_sweep(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with idle/completed sweeps."""
        mock_status = {
            "running": False,
            "sweeps": [
                {
                    "variable_name": "completed_sweep",
                    "sweep_type": "Sweep1D",
                    "status": "idle",
                    "config": {
                        "parameter": "voltage",
                        "completed": True,
                        "data_saved": True
                    }
                }
            ],
            "checked_variables": ["completed_sweep"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        assert response_data["running"] is False
        assert response_data["sweeps"][0]["status"] == "idle"

    @pytest.mark.asyncio
    async def test_get_status_returns_text_content(self, registrar, mock_tools, mock_mcp_server):
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
    async def test_get_status_json_serialization(self, registrar, mock_tools, mock_mcp_server):
        """Test that get_status properly serializes complex objects."""
        from datetime import datetime

        # Include objects that need default=str serialization
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "sweep",
                    "sweep_type": "Sweep1D",
                    "status": "running",
                    "timestamp": datetime(2024, 1, 1, 12, 0, 0)
                }
            ],
            "checked_variables": ["sweep"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        # Should not raise JSON serialization error
        response_data = json.loads(result[0].text)
        assert response_data["running"] is True

    def test_only_one_tool_registered(self, registrar, mock_mcp_server):
        """Test that only the get_status tool is registered."""
        registrar.register_all()

        # Should only have one MeasureIt tool
        measureit_tools = [name for name in mock_mcp_server._tools.keys()
                          if name.startswith("measureit_")]
        assert len(measureit_tools) == 1
        assert "measureit_get_status" in measureit_tools

    @pytest.mark.asyncio
    async def test_get_status_with_simul_sweep(self, registrar, mock_tools, mock_mcp_server):
        """Test getting MeasureIt status with SimulSweep."""
        mock_status = {
            "running": True,
            "sweeps": [
                {
                    "variable_name": "simul_sweep",
                    "sweep_type": "SimulSweep",
                    "status": "running",
                    "config": {
                        "parameters": ["gate1", "gate2", "gate3"],
                        "simultaneous": True,
                        "sweep_range": [0, 1],
                        "num_points": 100
                    }
                }
            ],
            "checked_variables": ["simul_sweep"]
        }
        mock_tools.get_measureit_status.return_value = mock_status

        registrar.register_all()
        get_status_func = mock_mcp_server._tools["measureit_get_status"]
        result = await get_status_func()

        response_data = json.loads(result[0].text)
        sweep = response_data["sweeps"][0]
        assert sweep["sweep_type"] == "SimulSweep"
        assert len(sweep["config"]["parameters"]) == 3
        assert sweep["config"]["simultaneous"] is True
