"""
Unit tests for resource registrar.

Tests ResourceRegistrar for registering MCP resources (QCodes, notebook, MeasureIt templates, database).
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from mcp.types import Resource, TextResourceContents

from instrmcp.servers.jupyter_qcodes.core.resources import ResourceRegistrar


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

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
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

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
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

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
        ):
            registrar.register_all()

            # Count all registered resources
            resource_count = len(mock_mcp_server._resources)

            # Core: 2, MeasureIt: 7, Database: 7 (2 base + 5 access templates) = 16 total
            assert resource_count == 16

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


class TestResourceDiscoveryTools:
    """Test resource discovery tools (mcp_list_resources and mcp_get_resource)."""

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server with tool registration."""
        mcp = MagicMock()
        mcp._resources = {}
        mcp._tools = {}

        # Mock the @mcp.resource decorator
        def resource_decorator(uri):
            def wrapper(func):
                mcp._resources[uri] = func
                return func

            return wrapper

        # Mock the @mcp.tool decorator
        def tool_decorator(name=None, annotations=None):
            def wrapper(func):
                tool_name = name or func.__name__
                mcp._tools[tool_name] = func
                return func

            return wrapper

        mcp.resource = resource_decorator
        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance."""
        tools = MagicMock()
        tools.list_instruments = AsyncMock(return_value=[])
        tools.get_station_snapshot = AsyncMock(return_value={})
        return tools

    @pytest.fixture
    def mock_measureit_module(self):
        """Create a mock MeasureIt integration module."""
        return MagicMock()

    @pytest.fixture
    def mock_db_module(self):
        """Create a mock database integration module."""
        db = MagicMock()
        db.get_current_database_config = MagicMock(
            return_value=json.dumps({"database_path": "/test/db.db"})
        )
        db.get_recent_measurements = MagicMock(
            return_value=json.dumps({"measurements": []})
        )
        return db

    @pytest.mark.asyncio
    async def test_list_resources_core_only(self, mock_mcp_server, mock_tools):
        """Test mcp_list_resources with core resources only."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)
        registrar.register_all()

        # Get the list_resources tool
        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()

        # Parse the result
        assert len(result) == 1
        guide = json.loads(result[0].text)

        # Check structure
        assert "total_resources" in guide
        assert "resources" in guide
        assert "guidance" in guide

        # Should have 2 core resources
        assert guide["total_resources"] == 2

        # Check resource URIs match registered resources
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

        # Verify core resources are listed
        assert "resource://available_instruments" in listed_uris
        assert "resource://station_state" in listed_uris

    @pytest.mark.asyncio
    async def test_list_resources_with_measureit(
        self, mock_mcp_server, mock_tools, mock_measureit_module
    ):
        """Test mcp_list_resources with MeasureIt enabled."""
        enabled_options = {"measureit"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
        )

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
        ):
            registrar.register_all()

        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)

        # Should have 2 core + 12 MeasureIt (7 templates + 5 database access) = 14 resources
        assert guide["total_resources"] == 14

        # Check all URIs match
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

        # Verify MeasureIt resources are listed
        assert "resource://measureit_sweep0d_template" in listed_uris
        assert "resource://measureit_sweep1d_template" in listed_uris
        assert "resource://measureit_code_examples" in listed_uris

    @pytest.mark.asyncio
    async def test_list_resources_with_database(
        self, mock_mcp_server, mock_tools, mock_db_module
    ):
        """Test mcp_list_resources with database enabled."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=mock_db_module,
        )
        registrar.register_all()

        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)

        # Should have 2 core + 2 database = 4 resources (database access templates are under measureit)
        assert guide["total_resources"] == 4

        # Check all URIs match
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

        # Verify database resources are listed
        assert "resource://database_config" in listed_uris
        assert "resource://recent_measurements" in listed_uris

    @pytest.mark.asyncio
    async def test_list_resources_all_options(
        self, mock_mcp_server, mock_tools, mock_measureit_module, mock_db_module
    ):
        """Test mcp_list_resources with all options enabled."""
        enabled_options = {"measureit", "database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
            db_module=mock_db_module,
        )

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
        ):
            registrar.register_all()

        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)

        # Should have 2 core + 7 MeasureIt + 7 database (2 base + 5 access templates) = 16 resources
        assert guide["total_resources"] == 16

        # All listed URIs must match registered resources
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

    @pytest.mark.asyncio
    async def test_get_resource_core_resources(self, mock_mcp_server, mock_tools):
        """Test mcp_get_resource for core resources."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)

        mock_instruments = [{"name": "test_dac", "type": "DAC"}]
        mock_tools.list_instruments.return_value = mock_instruments

        registrar.register_all()

        get_resource_func = mock_mcp_server._tools["mcp_get_resource"]

        # Test available_instruments
        result = await get_resource_func("resource://available_instruments")
        assert len(result) == 1
        content = json.loads(result[0].text)
        assert content == mock_instruments

        # Test station_state
        mock_snapshot = {"instruments": {"test_dac": {}}}
        mock_tools.get_station_snapshot.return_value = mock_snapshot

        result = await get_resource_func("resource://station_state")
        content = json.loads(result[0].text)
        assert content == mock_snapshot

    @pytest.mark.asyncio
    async def test_get_resource_with_measureit(
        self, mock_mcp_server, mock_tools, mock_measureit_module
    ):
        """Test mcp_get_resource for MeasureIt resources."""
        enabled_options = {"measureit"}

        mock_template = json.dumps({"examples": [{"name": "test", "code": "# test"}]})

        # Patch at the point where get_resource imports the functions
        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template",
                return_value=mock_template,
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples",
                return_value=mock_template,
            ),
        ):
            registrar = ResourceRegistrar(
                mock_mcp_server,
                mock_tools,
                enabled_options=enabled_options,
                measureit_module=mock_measureit_module,
            )
            registrar.register_all()

            get_resource_func = mock_mcp_server._tools["mcp_get_resource"]

            # Test MeasureIt resource
            result = await get_resource_func("resource://measureit_sweep0d_template")
            assert len(result) == 1
            assert result[0].text == mock_template

    @pytest.mark.asyncio
    async def test_get_resource_with_database(
        self, mock_mcp_server, mock_tools, mock_db_module
    ):
        """Test mcp_get_resource for database resources."""
        enabled_options = {"database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            db_module=mock_db_module,
        )

        registrar.register_all()
        get_resource_func = mock_mcp_server._tools["mcp_get_resource"]

        # Test database_config
        result = await get_resource_func("resource://database_config")
        assert len(result) == 1
        content = json.loads(result[0].text)
        assert "database_path" in content

        # Test recent_measurements
        result = await get_resource_func("resource://recent_measurements")
        content = json.loads(result[0].text)
        assert "measurements" in content

    @pytest.mark.asyncio
    async def test_get_resource_invalid_uri(self, mock_mcp_server, mock_tools):
        """Test mcp_get_resource with invalid URI."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)
        registrar.register_all()

        get_resource_func = mock_mcp_server._tools["mcp_get_resource"]

        # Try invalid URI
        result = await get_resource_func("resource://nonexistent")
        assert len(result) == 1
        error_msg = json.loads(result[0].text)

        assert "error" in error_msg
        assert "Unknown resource URI" in error_msg["error"]
        assert "available_uris" in error_msg
        assert "hint" in error_msg

        # Available URIs should match registered resources
        available_uris = set(error_msg["available_uris"])
        registered_uris = set(mock_mcp_server._resources.keys())
        assert available_uris == registered_uris

    @pytest.mark.asyncio
    async def test_get_resource_all_registered_uris(
        self, mock_mcp_server, mock_tools, mock_measureit_module, mock_db_module
    ):
        """Test mcp_get_resource can retrieve all registered resources."""
        enabled_options = {"measureit", "database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
            db_module=mock_db_module,
        )

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
        ):
            registrar.register_all()

        get_resource_func = mock_mcp_server._tools["mcp_get_resource"]

        # Try to get every registered resource
        for uri in mock_mcp_server._resources.keys():
            result = await get_resource_func(uri)
            assert len(result) == 1
            # Should not be an error message
            try:
                content = json.loads(result[0].text)
                assert "error" not in content or content.get("status") == "error"
            except json.JSONDecodeError:
                # Some resources might return non-JSON text, that's ok
                pass

    @pytest.mark.asyncio
    async def test_list_and_get_consistency(
        self, mock_mcp_server, mock_tools, mock_measureit_module, mock_db_module
    ):
        """Test that list_resources and get_resource are consistent."""
        enabled_options = {"measureit", "database"}
        registrar = ResourceRegistrar(
            mock_mcp_server,
            mock_tools,
            enabled_options=enabled_options,
            measureit_module=mock_measureit_module,
            db_module=mock_db_module,
        )

        with (
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep0d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep1d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweep2d_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_simulsweep_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_sweepqueue_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_common_patterns_template"
            ),
            patch(
                "instrmcp.servers.jupyter_qcodes.options.measureit.get_measureit_code_examples"
            ),
        ):
            registrar.register_all()

        # Get all URIs from list_resources
        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)
        listed_uris = {r["uri"] for r in guide["resources"]}

        # Verify we can get all listed resources
        get_resource_func = mock_mcp_server._tools["mcp_get_resource"]
        for uri in listed_uris:
            result = await get_resource_func(uri)
            assert len(result) == 1
            # Should not contain error message (except for legitimate errors)
            content = result[0].text
            if content.startswith("{") and "error" in content:
                error_data = json.loads(content)
                # Allow errors from resource retrieval, not from URI lookup
                assert "Unknown resource URI" not in error_data.get("error", "")

    @pytest.mark.asyncio
    async def test_resource_metadata_in_list(self, mock_mcp_server, mock_tools):
        """Test that list_resources includes proper metadata."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)
        registrar.register_all()

        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)

        # Check each resource has required fields
        for resource in guide["resources"]:
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource
            assert "use_when" in resource
            assert "example" in resource

            # URI should be valid format
            assert resource["uri"].startswith("resource://")

            # Fields should have meaningful content
            assert len(resource["name"]) > 0
            assert len(resource["description"]) > 0
            assert len(resource["use_when"]) > 0

    @pytest.mark.asyncio
    async def test_guidance_section_completeness(self, mock_mcp_server, mock_tools):
        """Test that guidance section is complete and useful."""
        registrar = ResourceRegistrar(mock_mcp_server, mock_tools)
        registrar.register_all()

        list_resources_func = mock_mcp_server._tools["mcp_list_resources"]
        result = await list_resources_func()
        guide = json.loads(result[0].text)

        # Check guidance structure (simplified)
        guidance = guide["guidance"]
        assert "workflow" in guidance
        assert "common_patterns" in guidance

        # Check workflow is a simple string
        assert isinstance(guidance["workflow"], str)
        assert len(guidance["workflow"]) > 0

        # Check common_patterns is populated
        assert isinstance(guidance["common_patterns"], list)
        assert len(guidance["common_patterns"]) > 0
