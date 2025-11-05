"""
Unit tests for database integration tool registrar.

Tests DatabaseToolRegistrar for registering database query tools with FastMCP.
"""

import pytest
import json
from unittest.mock import MagicMock
from mcp.types import TextContent

from instrmcp.servers.jupyter_qcodes.registrars.database_tools import (
    DatabaseToolRegistrar,
)


class TestDatabaseToolRegistrar:
    """Test DatabaseToolRegistrar class for registering database tools."""

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
    def mock_db_integration(self):
        """Create a mock database integration module."""
        db = MagicMock()
        db.list_experiments = MagicMock()
        db.get_dataset_info = MagicMock()
        db.get_database_stats = MagicMock()
        return db

    @pytest.fixture
    def registrar(self, mock_mcp_server, mock_db_integration):
        """Create a DatabaseToolRegistrar instance."""
        return DatabaseToolRegistrar(mock_mcp_server, mock_db_integration)

    def test_initialization(self, mock_mcp_server, mock_db_integration):
        """Test registrar initialization."""
        registrar = DatabaseToolRegistrar(mock_mcp_server, mock_db_integration)
        assert registrar.mcp == mock_mcp_server
        assert registrar.db == mock_db_integration

    def test_register_all(self, registrar, mock_mcp_server):
        """Test registering all database tools."""
        registrar.register_all()

        expected_tools = [
            "database_list_experiments",
            "database_get_dataset_info",
            "database_get_database_stats",
        ]

        for tool_name in expected_tools:
            assert tool_name in mock_mcp_server._tools
            assert callable(mock_mcp_server._tools[tool_name])

    @pytest.mark.asyncio
    async def test_list_experiments_default_path(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test listing experiments with default database path."""
        mock_experiments = json.dumps(
            {
                "experiments": [
                    {
                        "exp_id": 1,
                        "name": "test_exp",
                        "sample_name": "sample1",
                        "format_string": "exp_{}-{}",
                    }
                ],
                "count": 1,
            },
            indent=2,
        )
        mock_db_integration.list_experiments.return_value = mock_experiments

        registrar.register_all()
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        result = await list_exp_func(database_path=None)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], TextContent)
        assert result[0].text == mock_experiments
        mock_db_integration.list_experiments.assert_called_once_with(database_path=None)

    @pytest.mark.asyncio
    async def test_list_experiments_custom_path(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test listing experiments with custom database path."""
        custom_path = "/path/to/custom.db"
        mock_experiments = json.dumps({"experiments": [], "count": 0}, indent=2)
        mock_db_integration.list_experiments.return_value = mock_experiments

        registrar.register_all()
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        result = await list_exp_func(database_path=custom_path)

        mock_db_integration.list_experiments.assert_called_once_with(
            database_path=custom_path
        )

    @pytest.mark.asyncio
    async def test_list_experiments_error(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test listing experiments with error."""
        mock_db_integration.list_experiments.side_effect = Exception(
            "Database not found"
        )

        registrar.register_all()
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        result = await list_exp_func(database_path=None)

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Database not found" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_dataset_info_success(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting dataset info successfully."""
        mock_dataset = json.dumps(
            {
                "run_id": 1,
                "name": "measurement_1",
                "exp_id": 1,
                "run_timestamp": "2024-01-01 12:00:00",
                "completed_timestamp": "2024-01-01 12:05:00",
                "parameters": {
                    "setpoints": ["gate_voltage"],
                    "measured": ["current", "voltage"],
                },
                "metadata": {"temperature": 300, "field": 0.5},
            },
            indent=2,
        )
        mock_db_integration.get_dataset_info.return_value = mock_dataset

        registrar.register_all()
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        result = await get_dataset_func(id=1, database_path=None)

        assert result[0].text == mock_dataset
        mock_db_integration.get_dataset_info.assert_called_once_with(
            id=1, database_path=None
        )

    @pytest.mark.asyncio
    async def test_get_dataset_info_with_path(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting dataset info with custom database path."""
        custom_path = "/path/to/db.db"
        mock_dataset = json.dumps({"run_id": 5, "name": "test"}, indent=2)
        mock_db_integration.get_dataset_info.return_value = mock_dataset

        registrar.register_all()
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        result = await get_dataset_func(id=5, database_path=custom_path)

        mock_db_integration.get_dataset_info.assert_called_once_with(
            id=5, database_path=custom_path
        )

    @pytest.mark.asyncio
    async def test_get_dataset_info_not_found(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting dataset info for non-existent dataset."""
        mock_db_integration.get_dataset_info.side_effect = ValueError(
            "Dataset 999 not found"
        )

        registrar.register_all()
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        result = await get_dataset_func(id=999, database_path=None)

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Dataset 999 not found" in response_data["error"]

    @pytest.mark.asyncio
    async def test_get_database_stats_success(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting database stats successfully."""
        mock_stats = json.dumps(
            {
                "database_path": "/path/to/database.db",
                "size_bytes": 1024000,
                "size_human": "1.0 MB",
                "experiment_count": 5,
                "dataset_count": 123,
                "last_modified": "2024-01-01 15:30:00",
                "status": "healthy",
            },
            indent=2,
        )
        mock_db_integration.get_database_stats.return_value = mock_stats

        registrar.register_all()
        get_stats_func = mock_mcp_server._tools["database_get_database_stats"]
        result = await get_stats_func(database_path=None)

        assert result[0].text == mock_stats
        mock_db_integration.get_database_stats.assert_called_once_with(
            database_path=None
        )

    @pytest.mark.asyncio
    async def test_get_database_stats_with_path(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting database stats with custom path."""
        custom_path = "/custom/path/database.db"
        mock_stats = json.dumps({"dataset_count": 0}, indent=2)
        mock_db_integration.get_database_stats.return_value = mock_stats

        registrar.register_all()
        get_stats_func = mock_mcp_server._tools["database_get_database_stats"]
        result = await get_stats_func(database_path=custom_path)

        mock_db_integration.get_database_stats.assert_called_once_with(
            database_path=custom_path
        )

    @pytest.mark.asyncio
    async def test_get_database_stats_error(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting database stats with error."""
        mock_db_integration.get_database_stats.side_effect = Exception(
            "Cannot access database"
        )

        registrar.register_all()
        get_stats_func = mock_mcp_server._tools["database_get_database_stats"]
        result = await get_stats_func(database_path=None)

        response_data = json.loads(result[0].text)
        assert "error" in response_data
        assert "Cannot access database" in response_data["error"]

    @pytest.mark.asyncio
    async def test_list_experiments_with_multiple_experiments(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test listing multiple experiments."""
        mock_experiments = json.dumps(
            {
                "experiments": [
                    {"exp_id": 1, "name": "exp1", "sample_name": "sample1"},
                    {"exp_id": 2, "name": "exp2", "sample_name": "sample2"},
                    {"exp_id": 3, "name": "exp3", "sample_name": "sample3"},
                ],
                "count": 3,
                "database_path": "/path/to/db.db",
            },
            indent=2,
        )
        mock_db_integration.list_experiments.return_value = mock_experiments

        registrar.register_all()
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        result = await list_exp_func(database_path=None)

        experiments = json.loads(result[0].text)
        assert experiments["count"] == 3
        assert len(experiments["experiments"]) == 3

    @pytest.mark.asyncio
    async def test_get_dataset_info_with_complex_metadata(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test getting dataset info with complex metadata."""
        mock_dataset = json.dumps(
            {
                "run_id": 42,
                "name": "complex_measurement",
                "metadata": {
                    "temperature": 4.2,
                    "magnetic_field": 1.5,
                    "sample_properties": {
                        "width": 100,
                        "length": 200,
                        "material": "GaAs",
                    },
                    "measurement_settings": {
                        "averaging": 10,
                        "delay": 0.001,
                        "channels": [1, 2, 3, 4],
                    },
                },
                "parameters": {
                    "setpoints": ["gate_voltage", "bias_voltage"],
                    "measured": ["current", "conductance", "noise"],
                },
            },
            indent=2,
        )
        mock_db_integration.get_dataset_info.return_value = mock_dataset

        registrar.register_all()
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        result = await get_dataset_func(id=42, database_path=None)

        dataset = json.loads(result[0].text)
        assert dataset["run_id"] == 42
        assert "sample_properties" in dataset["metadata"]
        assert len(dataset["parameters"]["measured"]) == 3

    @pytest.mark.asyncio
    async def test_database_tools_parameter_validation(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test that database tools handle parameter types correctly."""
        registrar.register_all()

        # Test list_experiments accepts None
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        mock_db_integration.list_experiments.return_value = json.dumps({}, indent=2)
        await list_exp_func(database_path=None)

        # Test get_dataset_info requires int id
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        mock_db_integration.get_dataset_info.return_value = json.dumps({}, indent=2)
        await get_dataset_func(id=1, database_path=None)

    @pytest.mark.asyncio
    async def test_all_tools_return_text_content(
        self, registrar, mock_db_integration, mock_mcp_server
    ):
        """Test that all database tools return TextContent."""
        mock_db_integration.list_experiments.return_value = json.dumps({}, indent=2)
        mock_db_integration.get_dataset_info.return_value = json.dumps({}, indent=2)
        mock_db_integration.get_database_stats.return_value = json.dumps({}, indent=2)

        registrar.register_all()

        # Test list_experiments
        list_exp_func = mock_mcp_server._tools["database_list_experiments"]
        result1 = await list_exp_func(database_path=None)
        assert isinstance(result1, list)
        assert isinstance(result1[0], TextContent)

        # Test get_dataset_info
        get_dataset_func = mock_mcp_server._tools["database_get_dataset_info"]
        result2 = await get_dataset_func(id=1, database_path=None)
        assert isinstance(result2, list)
        assert isinstance(result2[0], TextContent)

        # Test get_database_stats
        get_stats_func = mock_mcp_server._tools["database_get_database_stats"]
        result3 = await get_stats_func(database_path=None)
        assert isinstance(result3, list)
        assert isinstance(result3[0], TextContent)

    def test_registrar_stores_correct_references(
        self, mock_mcp_server, mock_db_integration
    ):
        """Test that registrar stores correct references to mcp and db."""
        registrar = DatabaseToolRegistrar(mock_mcp_server, mock_db_integration)
        assert registrar.mcp is mock_mcp_server
        assert registrar.db is mock_db_integration
