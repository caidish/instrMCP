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

        # No core resources should be registered
        assert not mock_mcp_server._resources

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

        assert not mock_mcp_server._resources

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
            # Without metadata_config, uses uri_suffix as fallback name
            assert resource.name == "measureit_sweep0d_template"
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

            # MeasureIt: 12 total
            assert resource_count == 12

    @pytest.mark.asyncio
    async def test_resources_have_correct_structure(
        self, registrar, mock_tools, mock_mcp_server
    ):
        """Test that all resources have correct structure."""
        mock_tools.list_instruments.return_value = []
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

        assert not mock_mcp_server._resources


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

        # Mock get_resources() to return FunctionResource-like objects from _resources
        async def mock_get_resources():
            # Return dict mapping uri to mock resource objects
            result = {}
            for uri, func in mcp._resources.items():
                mock_res = MagicMock()
                mock_res.uri = uri
                # Extract name from uri (e.g., "resource://foo" -> "foo")
                mock_res.name = uri.replace("resource://", "")
                mock_res.description = f"Description for {mock_res.name}"
                result[uri] = mock_res
            return result

        mcp.get_resources = mock_get_resources
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

        # Should have 0 core resources
        assert guide["total_resources"] == 0

        # Check resource URIs match registered resources
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

        # Verify no core resources are listed
        assert listed_uris == set()

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

        # Should have 12 MeasureIt (7 templates + 5 database access) = 12 resources
        assert guide["total_resources"] == 12

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

        # Should have 0 resources
        assert guide["total_resources"] == 0

        # Check all URIs match
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

        assert listed_uris == set()

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

        # Should have 12 MeasureIt resources
        assert guide["total_resources"] == 12

        # All listed URIs must match registered resources
        listed_uris = {r["uri"] for r in guide["resources"]}
        registered_uris = set(mock_mcp_server._resources.keys())
        assert listed_uris == registered_uris

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
        # Note: use_when and example are now composed into description, not separate fields
        for resource in guide["resources"]:
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource

            # URI should be valid format
            assert resource["uri"].startswith("resource://")

            # Fields should have meaningful content
            assert len(resource["name"]) > 0
            assert len(resource["description"]) > 0
