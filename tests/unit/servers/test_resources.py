"""
Unit tests for resource registrar.

Tests ResourceRegistrar for registering MCP resources (QCodes, notebook, MeasureIt templates, database).
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from mcp.types import Resource, TextResourceContents

from instrmcp.servers.jupyter_qcodes.registrars.resources import ResourceRegistrar


class TestResourceRegistrar:
    """Test ResourceRegistrar class for registering MCP resources."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server."""
        mcp = MagicMock()
        mcp._resources = {}

        # Mock the @mcp.resource decorator
        def resource_decorator(uri):
            def wrapper(func):
                mcp._resources[uri] = func
                return func

            return wrapper

        mcp.resource = resource_decorator
        return mcp

    @pytest.fixture
    def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance."""
        tools = MagicMock()
        tools.list_instruments = AsyncMock()
        tools.get_station_snapshot = AsyncMock()
        return tools

    @pytest.fixture
    def mock_measureit_module(self):
        """Create a mock MeasureIt integration module."""
        return MagicMock()

    @pytest.fixture
    def mock_db_module(self):
        """Create a mock database integration module."""
        db = MagicMock()
        db.get_current_database_config = MagicMock()
        db.get_recent_measurements = MagicMock()
        return db

    @pytest.fixture
    def registrar(self, mock_mcp_server, mock_tools):
        """Create a ResourceRegistrar instance."""
        return ResourceRegistrar(mock_mcp_server, mock_tools)

    def test_initialization(self, mock_mcp_server, mock_tools):
        """Test registrar initialization."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)
        assert registrar.mcp == mock_mcp_server
        assert registrar.tools == mock_tools
        assert registrar.enabled_options == set()
        assert registrar.measureit is None
        assert registrar.db is None

    def test_initialization_with_options(
        self, mock_mcp_server, mock_tools, mock_measureit_module, mock_db_module
    ):
        """Test registrar initialization with optional features."""
        enabled_options = {"measureit", "database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
            db_module=mock_db_module,
        )
        assert registrar.enabled_options == enabled_options
        assert registrar.measureit == mock_measureit_module
        assert registrar.db == mock_db_module

    def test_register_all_core_only(self, registrar, mock_mcp_server):
        """Test registering only core resources."""
        registrar.register_all()

        # Core resources should be registered
        assert "resource://available_instruments" in mock_mcp_server._resources
        assert "resource://station_state" in mock_mcp_server._resources

        # Optional resources should not be registered
        assert "resource://measureit_sweep0d_template" not in mock_mcp_server._resources
        assert "resource://database_config" not in mock_mcp_server._resources

    def test_register_all_with_measureit(
        self, mock_mcp_server, mock_tools, mock_measureit_module
    ):
        """Test registering resources with MeasureIt enabled."""
        enabled_options = {"measureit"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
        )

        with patch("instrmcp.extensions.MeasureIt.get_sweep0d_template"), patch(
            "instrmcp.extensions.MeasureIt.get_sweep1d_template"
        ), patch("instrmcp.extensions.MeasureIt.get_sweep2d_template"), patch(
            "instrmcp.extensions.MeasureIt.get_simulsweep_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_sweepqueue_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_common_patterns_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_measureit_code_examples"
        ):

            registrar.register_all()

            # Core resources
            assert "resource://available_instruments" in mock_mcp_server._resources
            assert "resource://station_state" in mock_mcp_server._resources

            # MeasureIt resources
            assert "resource://measureit_sweep0d_template" in mock_mcp_server._resources
            assert "resource://measureit_sweep1d_template" in mock_mcp_server._resources
            assert "resource://measureit_sweep2d_template" in mock_mcp_server._resources
            assert (
                "resource://measureit_simulsweep_template" in mock_mcp_server._resources
            )
            assert (
                "resource://measureit_sweepqueue_template" in mock_mcp_server._resources
            )
            assert "resource://measureit_common_patterns" in mock_mcp_server._resources
            assert "resource://measureit_code_examples" in mock_mcp_server._resources

    def test_register_all_with_database(
        self, mock_mcp_server, mock_tools, mock_db_module
    ):
        """Test registering resources with database enabled."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=mock_db_module,
        )

        registrar.register_all()

        # Core resources
        assert "resource://available_instruments" in mock_mcp_server._resources
        assert "resource://station_state" in mock_mcp_server._resources

        # Database resources
        assert "resource://database_config" in mock_mcp_server._resources
        assert "resource://recent_measurements" in mock_mcp_server._resources

    @pytest.mark.asyncio
    async def test_available_instruments_resource(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test available_instruments resource."""
        mock_instruments = [
            {
                "name": "mock_dac",
                "type": "DAC",
                "parameters": {"ch01.voltage": {"unit": "V", "limits": [-10, 10]}},
            }
        ]
        mock_tools.list_instruments.return_value = mock_instruments

        registrar.register_all()
        available_instruments_func = mock_mcp_server._resources[
            "resource://available_instruments"
        ]
        resource = await available_instruments_func()

        assert isinstance(resource, Resource)
        assert str(resource.uri) == "resource://available_instruments"
        assert resource.name == "Available Instruments"
        assert resource.mimeType == "application/json"
        assert len(resource.contents) == 1
        assert isinstance(resource.contents[0], TextResourceContents)

        content = json.loads(resource.contents[0].text)
        assert content == mock_instruments

    @pytest.mark.asyncio
    async def test_available_instruments_error(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test available_instruments resource with error."""
        mock_tools.list_instruments.side_effect = Exception("QCodes error")

        registrar.register_all()
        available_instruments_func = mock_mcp_server._resources[
            "resource://available_instruments"
        ]
        resource = await available_instruments_func()

        assert isinstance(resource, Resource)
        assert "Error" in resource.name
        content = json.loads(resource.contents[0].text)
        assert "error" in content
        assert "QCodes error" in content["error"]

    @pytest.mark.asyncio
    async def test_station_state_resource(self, registrar, mock_tools, mock_mcp_server):
        """Test station_state resource."""
        mock_snapshot = {"instruments": {"mock_dac": {"type": "DAC", "parameters": {}}}}
        mock_tools.get_station_snapshot.return_value = mock_snapshot

        registrar.register_all()
        station_state_func = mock_mcp_server._resources["resource://station_state"]
        resource = await station_state_func()

        assert isinstance(resource, Resource)
        assert str(resource.uri) == "resource://station_state"
        assert resource.name == "QCodes Station State"
        assert resource.mimeType == "application/json"

        content = json.loads(resource.contents[0].text)
        assert content == mock_snapshot

    @pytest.mark.asyncio
    async def test_station_state_error(self, registrar, mock_tools, mock_mcp_server):
        """Test station_state resource with error."""
        mock_tools.get_station_snapshot.side_effect = Exception("Station error")

        registrar.register_all()
        station_state_func = mock_mcp_server._resources["resource://station_state"]
        resource = await station_state_func()

        assert "Error" in resource.name
        content = json.loads(resource.contents[0].text)
        assert "error" in content
        assert "Station error" in content["error"]

    @pytest.mark.asyncio
    async def test_database_config_resource(
        self, mock_mcp_server, mock_tools, mock_db_module
    ):
        """Test database_config resource."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=mock_db_module,
        )

        mock_config = json.dumps(
            {"database_path": "/path/to/db.db", "connected": True, "version": "0.20.0"},
            indent=2,
        )
        mock_db_module.get_current_database_config.return_value = mock_config

        registrar.register_all()
        db_config_func = mock_mcp_server._resources["resource://database_config"]
        resource = await db_config_func()

        assert isinstance(resource, Resource)
        assert str(resource.uri) == "resource://database_config"
        assert resource.name == "Database Configuration"
        assert resource.mimeType == "application/json"

        content = json.loads(resource.contents[0].text)
        assert content["database_path"] == "/path/to/db.db"
        assert content["connected"] is True

    @pytest.mark.asyncio
    async def test_recent_measurements_resource(
        self, mock_mcp_server, mock_tools, mock_db_module
    ):
        """Test recent_measurements resource."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=mock_db_module,
        )

        mock_measurements = json.dumps(
            {
                "measurements": [
                    {
                        "run_id": 1,
                        "name": "measurement1",
                        "timestamp": "2024-01-01 12:00:00",
                    },
                    {
                        "run_id": 2,
                        "name": "measurement2",
                        "timestamp": "2024-01-01 13:00:00",
                    },
                ],
                "count": 2,
            },
            indent=2,
        )
        mock_db_module.get_recent_measurements.return_value = mock_measurements

        registrar.register_all()
        recent_meas_func = mock_mcp_server._resources["resource://recent_measurements"]
        resource = await recent_meas_func()

        assert isinstance(resource, Resource)
        assert str(resource.uri) == "resource://recent_measurements"
        assert resource.name == "Recent Measurements"
        assert resource.mimeType == "application/json"

        content = json.loads(resource.contents[0].text)
        assert content["count"] == 2
        assert len(content["measurements"]) == 2

    @pytest.mark.asyncio
    async def test_measureit_template_resource(
        self, mock_mcp_server, mock_tools, mock_measureit_module
    ):
        """Test MeasureIt template resource registration."""
        enabled_options = {"measureit"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
        )

        mock_template = json.dumps(
            {"examples": [{"name": "basic_sweep0d", "code": "# Sweep0D example"}]},
            indent=2,
        )

        with patch(
            "instrmcp.extensions.MeasureIt.get_sweep0d_template",
            return_value=mock_template,
        ), patch("instrmcp.extensions.MeasureIt.get_sweep1d_template"), patch(
            "instrmcp.extensions.MeasureIt.get_sweep2d_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_simulsweep_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_sweepqueue_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_common_patterns_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_measureit_code_examples"
        ):

            registrar.register_all()
            sweep0d_func = mock_mcp_server._resources[
                "resource://measureit_sweep0d_template"
            ]
            resource = await sweep0d_func()

            assert isinstance(resource, Resource)
            assert str(resource.uri) == "resource://measureit_sweep0d_template"
            assert resource.name == "MeasureIt Sweep0D Template"
            assert resource.mimeType == "application/json"

            content = json.loads(resource.contents[0].text)
            assert "examples" in content

    def test_register_all_with_all_options(
        self, mock_mcp_server, mock_tools, mock_measureit_module, mock_db_module
    ):
        """Test registering all resources with all options enabled."""
        enabled_options = {"measureit", "database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
            db_module=mock_db_module,
        )

        with patch("instrmcp.extensions.MeasureIt.get_sweep0d_template"), patch(
            "instrmcp.extensions.MeasureIt.get_sweep1d_template"
        ), patch("instrmcp.extensions.MeasureIt.get_sweep2d_template"), patch(
            "instrmcp.extensions.MeasureIt.get_simulsweep_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_sweepqueue_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_common_patterns_template"
        ), patch(
            "instrmcp.extensions.MeasureIt.get_measureit_code_examples"
        ):

            registrar.register_all()

            # Count all registered resources
            resource_count = len(mock_mcp_server._resources)

            # Core: 2, MeasureIt: 7, Database: 2 = 11 total
            assert resource_count == 11

    @pytest.mark.asyncio
    async def test_resources_have_correct_structure(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test that all resources have correct structure."""
        mock_tools.list_instruments.return_value = []
        mock_tools.get_station_snapshot.return_value = {}

        registrar.register_all()

        for uri, func in mock_mcp_server._resources.items():
            resource = await func()
            assert isinstance(resource, Resource)
            assert str(resource.uri) == uri
            assert resource.name is not None
            assert resource.description is not None
            assert resource.mimeType == "application/json"
            assert len(resource.contents) == 1
            assert isinstance(resource.contents[0], TextResourceContents)
            assert str(resource.contents[0].uri) == uri
            assert resource.contents[0].mimeType == "application/json"

    def test_no_measureit_resources_without_module(self, mock_mcp_server, mock_tools):
        """Test that MeasureIt resources are not registered without module."""
        enabled_options = {"measureit"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=None,  # No module provided
        )

        registrar.register_all()

        # MeasureIt resources should not be registered
        assert "resource://measureit_sweep0d_template" not in mock_mcp_server._resources

    def test_no_database_resources_without_module(self, mock_mcp_server, mock_tools):
        """Test that database resources are not registered without module."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=None,  # No module provided
        )

        registrar.register_all()

        # Database resources should not be registered
        assert "resource://database_config" not in mock_mcp_server._resources
        assert "resource://recent_measurements" not in mock_mcp_server._resources

    @pytest.mark.asyncio
    async def test_available_instruments_with_complex_data(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test available_instruments with complex hierarchical instruments."""
        mock_instruments = [
            {
                "name": "complex_dac",
                "type": "DAC",
                "submodules": {
                    "ch01": {
                        "parameters": {
                            "voltage": {"unit": "V", "value": 0.0},
                            "current": {"unit": "A", "value": 0.001},
                        }
                    },
                    "ch02": {"parameters": {"voltage": {"unit": "V", "value": 0.5}}},
                },
                "metadata": {
                    "serial": "12345",
                    "firmware": "v1.2.3",
                    "calibration_date": "2024-01-01",
                },
            }
        ]
        mock_tools.list_instruments.return_value = mock_instruments

        registrar.register_all()
        available_instruments_func = mock_mcp_server._resources[
            "resource://available_instruments"
        ]
        resource = await available_instruments_func()

        content = json.loads(resource.contents[0].text)
        assert len(content) == 1
        assert "submodules" in content[0]
        assert "metadata" in content[0]
        assert content[0]["metadata"]["serial"] == "12345"
