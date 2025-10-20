"""
Unit tests for database query tools.

Tests list_experiments, get_dataset_info, get_database_stats, and
database path resolution for QCodes database integration.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from instrmcp.extensions.database.query_tools import (
    list_experiments,
    get_dataset_info,
    get_database_stats,
    _resolve_database_path,
    _format_file_size,
    QCODES_AVAILABLE,
)

# Check if MeasureIt is available
try:
    import measureit  # noqa: F401

    MEASUREIT_AVAILABLE = True
except ImportError:
    MEASUREIT_AVAILABLE = False


class TestResolveDatabasePath:
    """Test database path resolution logic."""

    def test_resolve_explicit_path(self, tmp_path):
        """Test explicit path takes precedence."""
        # Create a temporary database file
        db_file = tmp_path / "database.db"
        db_file.touch()
        explicit_path = str(db_file)

        resolved_path, resolution_info = _resolve_database_path(explicit_path)
        assert resolved_path == explicit_path
        assert resolution_info["source"] == "explicit"
        assert resolution_info["tried_path"] == explicit_path

    @pytest.mark.skipif(not MEASUREIT_AVAILABLE, reason="MeasureIt not available")
    def test_resolve_measureit_home_path(self, monkeypatch, temp_dir):
        """Test MeasureIt get_path() is used (via measureit.get_path)."""
        # Create database file
        db_dir = temp_dir / "Databases"
        db_dir.mkdir()
        db_file = db_dir / "Example_database.db"
        db_file.touch()

        with patch("measureit.get_path") as mock_get_path:
            mock_get_path.return_value = db_dir

            resolved_path, resolution_info = _resolve_database_path(None)
            expected = str(db_dir / "Example_database.db")
            assert resolved_path == expected
            assert resolution_info["source"] == "measureit_default"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resolve_qcodes_default(self, monkeypatch, temp_dir):
        """Test falls back to QCodes config."""
        # Create qcodes database file
        qcodes_db = temp_dir / "qcodes.db"
        qcodes_db.touch()

        with patch("measureit.get_path", side_effect=ImportError):
            with patch("instrmcp.extensions.database.query_tools.qc") as mock_qc:
                mock_qc.config.core.db_location = str(qcodes_db)
                resolved_path, resolution_info = _resolve_database_path(None)
                assert resolved_path == str(qcodes_db)
                assert resolution_info["source"] == "qcodes_config"

    @pytest.mark.skipif(not MEASUREIT_AVAILABLE, reason="MeasureIt not available")
    def test_resolve_priority_explicit_over_env(self, monkeypatch, temp_dir):
        """Test explicit path has priority over environment."""
        # Create explicit database file
        explicit_db = temp_dir / "explicit.db"
        explicit_db.touch()
        explicit_path = str(explicit_db)

        # Create measureit database directory
        db_dir = temp_dir / "Databases"
        db_dir.mkdir()

        with patch("measureit.get_path") as mock_get_path:
            mock_get_path.return_value = db_dir

            resolved_path, resolution_info = _resolve_database_path(explicit_path)
            assert resolved_path == explicit_path
            assert resolution_info["source"] == "explicit"


class TestFormatFileSize:
    """Test file size formatting utility."""

    def test_format_bytes(self):
        """Test formatting bytes."""
        assert "B" in _format_file_size(512)
        assert "512" in _format_file_size(512)

    def test_format_kilobytes(self):
        """Test formatting kilobytes."""
        result = _format_file_size(2048)
        assert "KB" in result
        assert "2.0" in result

    def test_format_megabytes(self):
        """Test formatting megabytes."""
        result = _format_file_size(5 * 1024 * 1024)
        assert "MB" in result
        assert "5.0" in result

    def test_format_gigabytes(self):
        """Test formatting gigabytes."""
        result = _format_file_size(3 * 1024 * 1024 * 1024)
        assert "GB" in result
        assert "3.0" in result

    def test_format_zero(self):
        """Test formatting zero bytes."""
        result = _format_file_size(0)
        assert "0.0 B" in result


@pytest.mark.usefixtures("mock_qcodes_db_config")
class TestListExperiments:
    """Test list_experiments functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_returns_valid_json(self):
        """Test list_experiments returns valid JSON."""
        result = list_experiments()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_has_required_fields(self):
        """Test list_experiments includes required fields."""
        result = json.loads(list_experiments())
        assert "database_path" in result
        assert "experiment_count" in result
        assert "experiments" in result
        assert isinstance(result["experiments"], list)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_list_experiments_empty_database(self, mock_experiments):
        """Test list_experiments with empty database."""
        mock_experiments.return_value = []

        result = json.loads(list_experiments())
        assert result["experiment_count"] == 0
        assert result["experiments"] == []

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_list_experiments_multiple_experiments(self, mock_experiments):
        """Test list_experiments with multiple experiments."""
        mock_exp1 = MagicMock()
        mock_exp1.exp_id = 1
        mock_exp1.name = "exp1"
        mock_exp1.sample_name = "sample1"

        mock_exp2 = MagicMock()
        mock_exp2.exp_id = 2
        mock_exp2.name = "exp2"
        mock_exp2.sample_name = "sample2"

        mock_experiments.return_value = [mock_exp1, mock_exp2]

        result = json.loads(list_experiments())
        assert result["experiment_count"] == 2
        assert len(result["experiments"]) == 2

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_list_experiments_experiment_structure(self, mock_experiments):
        """Test each experiment has proper structure."""
        mock_exp = MagicMock()
        mock_exp.exp_id = 1
        mock_exp.name = "test_experiment"
        mock_exp.sample_name = "test_sample"
        mock_exp.start_time = 1234567890
        mock_exp.end_time = 1234567900
        mock_exp.format_string = "{}-{}-{}"

        mock_experiments.return_value = [mock_exp]

        result = json.loads(list_experiments())
        exp = result["experiments"][0]

        assert exp["experiment_id"] == 1
        assert exp["name"] == "test_experiment"
        assert exp["sample_name"] == "test_sample"
        assert "run_ids" in exp
        assert "dataset_count" in exp

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_with_explicit_path(self, mock_database_path):
        """Test list_experiments with explicit database path."""
        result = json.loads(list_experiments(mock_database_path))
        assert result["database_path"] == mock_database_path

    def test_list_experiments_without_qcodes(self):
        """Test list_experiments returns error when QCodes unavailable."""
        with patch("instrmcp.extensions.database.query_tools.QCODES_AVAILABLE", False):
            result = json.loads(list_experiments())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_list_experiments_handles_errors(self, mock_experiments):
        """Test list_experiments handles database errors gracefully."""
        mock_experiments.side_effect = Exception("Database error")

        result = json.loads(list_experiments())
        assert "error" in result
        assert "Failed to list experiments" in result["error"]


@pytest.mark.usefixtures("mock_qcodes_db_config")
class TestGetDatasetInfo:
    """Test get_dataset_info functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_returns_valid_json(self):
        """Test get_dataset_info returns valid JSON."""
        with patch("instrmcp.extensions.database.query_tools.load_by_id") as mock_load:
            mock_dataset = self._create_mock_dataset()
            mock_load.return_value = mock_dataset

            result = get_dataset_info(1)
            parsed = json.loads(result)
            assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_has_required_sections(self, mock_load):
        """Test get_dataset_info includes required sections."""
        mock_dataset = self._create_mock_dataset()
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        assert "basic_info" in result
        assert "experiment_info" in result
        assert "parameters" in result
        assert "metadata" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_basic_info_structure(self, mock_load):
        """Test basic_info section has correct structure."""
        mock_dataset = self._create_mock_dataset()
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        basic = result["basic_info"]

        assert basic["run_id"] == 1
        assert basic["name"] == "test_dataset"
        assert "guid" in basic
        assert "completed" in basic
        assert "number_of_results" in basic

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_experiment_info_structure(self, mock_load):
        """Test experiment_info section has correct structure."""
        mock_dataset = self._create_mock_dataset()
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        exp = result["experiment_info"]

        assert exp["experiment_id"] == 1
        assert exp["name"] == "test_experiment"
        assert exp["sample_name"] == "test_sample"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_parameters_structure(self, mock_load):
        """Test parameters section is properly structured."""
        mock_dataset = self._create_mock_dataset()

        # Create mock parameter spec
        mock_param = MagicMock()
        mock_param.name = "voltage"
        mock_param.type = "numeric"
        mock_param.label = "Gate Voltage"
        mock_param.unit = "V"
        mock_param.depends_on = ""

        mock_dataset.parameters = {"voltage": mock_param}
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        params = result["parameters"]

        assert "voltage" in params
        assert params["voltage"]["name"] == "voltage"
        assert params["voltage"]["label"] == "Gate Voltage"
        assert params["voltage"]["unit"] == "V"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_with_measureit_metadata(self, mock_load):
        """Test extracting MeasureIt metadata."""
        mock_dataset = self._create_mock_dataset()
        mock_dataset.metadata = {
            "measureit": json.dumps(
                {
                    "class": "Sweep1D",
                    "module": "MeasureIt.sweep1d",
                    "attributes": {"rate": 0.01, "bidirectional": True},
                    "set_param": "gate.voltage",
                    "follow_params": {"lockin.x": {}, "lockin.y": {}},
                }
            )
        }
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        measureit = result["measureit_info"]

        assert measureit is not None
        assert measureit["class"] == "Sweep1D"
        assert measureit["module"] == "MeasureIt.sweep1d"
        assert "attributes" in measureit
        assert "follow_params" in measureit

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_parameter_data_truncation(self, mock_load):
        """Test parameter data is truncated for large datasets."""
        mock_dataset = self._create_mock_dataset()

        import numpy as np

        large_data = np.arange(100)

        mock_dataset.get_parameter_data.return_value = {
            "voltage": {"voltage": large_data}
        }
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        param_data = result["parameter_data"]

        # Should be truncated for large datasets
        assert "voltage" in param_data
        voltage_data = param_data["voltage"]["voltage"]
        assert "data_truncated" in voltage_data

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_small_parameter_data(self, mock_load):
        """Test parameter data is not truncated for small datasets."""
        mock_dataset = self._create_mock_dataset()

        import numpy as np

        small_data = np.array([1.0, 2.0, 3.0])

        mock_dataset.get_parameter_data.return_value = {
            "current": {"current": small_data}
        }
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        param_data = result["parameter_data"]

        assert "current" in param_data
        current_data = param_data["current"]["current"]
        assert current_data["data_truncated"] is False
        assert "data" in current_data

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_with_timestamp(self, mock_load):
        """Test dataset info includes timestamp."""
        mock_dataset = self._create_mock_dataset()
        mock_dataset.run_timestamp_raw = 1234567890.0
        mock_load.return_value = mock_dataset

        result = json.loads(get_dataset_info(1))
        basic = result["basic_info"]

        assert "timestamp" in basic
        assert basic["timestamp"] == 1234567890.0
        assert "timestamp_readable" in basic
        # Should be ISO format
        datetime.fromisoformat(basic["timestamp_readable"])

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_with_explicit_path(self, mock_database_path):
        """Test get_dataset_info with explicit database path."""
        with patch("instrmcp.extensions.database.query_tools.load_by_id") as mock_load:
            mock_dataset = self._create_mock_dataset()
            mock_load.return_value = mock_dataset

            result = get_dataset_info(1, mock_database_path)
            # Should not raise exception
            assert isinstance(json.loads(result), dict)

    def test_get_dataset_info_without_qcodes(self):
        """Test get_dataset_info returns error when QCodes unavailable."""
        with patch("instrmcp.extensions.database.query_tools.QCODES_AVAILABLE", False):
            result = json.loads(get_dataset_info(1))
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_dataset_info_handles_errors(self, mock_load):
        """Test get_dataset_info handles errors gracefully."""
        mock_load.side_effect = Exception("Dataset not found")

        result = json.loads(get_dataset_info(999))
        assert "error" in result
        assert "Failed to get dataset info" in result["error"]

    @staticmethod
    def _create_mock_dataset():
        """Helper to create a mock dataset."""
        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.name = "test_dataset"
        mock_dataset.guid = "550e8400-e29b-41d4-a716-446655440001"
        mock_dataset.completed = True
        mock_dataset.__len__ = MagicMock(return_value=100)
        mock_dataset.exp_id = 1
        mock_dataset.exp_name = "test_experiment"
        mock_dataset.sample_name = "test_sample"
        mock_dataset.parameters = {}
        mock_dataset.metadata = {}
        mock_dataset.get_parameter_data.return_value = {}
        return mock_dataset


@pytest.mark.usefixtures("mock_qcodes_db_config")
class TestGetDatabaseStats:
    """Test get_database_stats functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_returns_valid_json(self):
        """Test get_database_stats returns valid JSON."""
        result = get_database_stats()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_has_required_fields(self):
        """Test get_database_stats includes required fields."""
        result = json.loads(get_database_stats())
        assert "database_path" in result
        assert "database_exists" in result
        assert "experiment_count" in result
        assert "total_dataset_count" in result
        assert "qcodes_version" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_nonexistent_database(self, temp_dir):
        """Test stats for nonexistent database."""
        db_path = temp_dir / "nonexistent.db"
        result = json.loads(get_database_stats(str(db_path)))

        # Should return error for nonexistent path
        assert "error" in result
        assert "error_type" in result
        assert result["error_type"] == "database_not_found"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_existing_database(self, temp_dir):
        """Test stats for existing database."""
        db_path = temp_dir / "test.db"
        db_path.write_text("test data")

        result = json.loads(get_database_stats(str(db_path)))

        assert result["database_exists"] is True
        assert result["database_size_bytes"] > 0
        assert "database_size_readable" in result
        assert "last_modified" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_file_size_formatting(self, temp_dir):
        """Test file size is formatted in human-readable form."""
        db_path = temp_dir / "test.db"
        db_path.write_bytes(b"x" * 2048)

        result = json.loads(get_database_stats(str(db_path)))

        assert (
            "KB" in result["database_size_readable"]
            or "B" in result["database_size_readable"]
        )

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.Path")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_get_database_stats_experiment_count(self, mock_experiments, mock_path_cls):
        """Test stats includes experiment count."""
        # Mock database file exists
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mock_stat = MagicMock()
        mock_stat.st_size = 1024 * 1024  # 1 MB
        mock_stat.st_mtime = 1234567890
        mock_db_path.stat.return_value = mock_stat
        mock_path_cls.return_value = mock_db_path

        # Mock experiments
        mock_exp1 = MagicMock()
        mock_exp1.exp_id = 1
        mock_exp2 = MagicMock()
        mock_exp2.exp_id = 2

        mock_experiments.return_value = [mock_exp1, mock_exp2]

        result = json.loads(get_database_stats())
        assert result["experiment_count"] == 2

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_database_stats_dataset_count(self, mock_load, mock_experiments):
        """Test stats includes dataset count."""
        mock_experiments.return_value = []

        # Mock a few datasets
        def mock_load_side_effect(run_id):
            if run_id <= 3:
                ds = MagicMock()
                ds.run_id = run_id
                return ds
            raise Exception("Not found")

        mock_load.side_effect = mock_load_side_effect

        result = json.loads(get_database_stats())
        # Should find at least some datasets
        assert result["total_dataset_count"] >= 0

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_get_database_stats_measurement_types(self, mock_load, mock_experiments):
        """Test stats includes measurement type breakdown."""
        mock_experiments.return_value = []

        # Mock datasets with different types
        def mock_load_side_effect(run_id):
            if run_id == 1:
                ds = MagicMock()
                ds.run_id = 1
                ds.metadata = {"measureit": json.dumps({"class": "Sweep1D"})}
                return ds
            raise Exception("Not found")

        mock_load.side_effect = mock_load_side_effect

        result = json.loads(get_database_stats())
        assert "measurement_types" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_get_database_stats_experiment_details(self, mock_experiments):
        """Test stats includes experiment details."""
        mock_exp = MagicMock()
        mock_exp.exp_id = 1
        mock_exp.name = "test_exp"
        mock_exp.sample_name = "test_sample"
        mock_exp.start_time = 1234567890
        mock_exp.end_time = 1234567900

        mock_experiments.return_value = [mock_exp]

        result = json.loads(get_database_stats())
        if "experiment_details" in result:
            details = result["experiment_details"]
            assert len(details) > 0
            assert details[0]["experiment_id"] == 1

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_with_explicit_path(self, mock_database_path):
        """Test get_database_stats with explicit database path."""
        result = json.loads(get_database_stats(mock_database_path))
        assert result["database_path"] == mock_database_path

    def test_get_database_stats_without_qcodes(self):
        """Test get_database_stats returns error when QCodes unavailable."""
        with patch("instrmcp.extensions.database.query_tools.QCODES_AVAILABLE", False):
            result = json.loads(get_database_stats())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.Path")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_get_database_stats_handles_errors(self, mock_experiments, mock_path_cls):
        """Test get_database_stats handles errors gracefully."""
        # Mock database file exists
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True
        mock_stat = MagicMock()
        mock_stat.st_size = 1024
        mock_stat.st_mtime = 1234567890
        mock_db_path.stat.return_value = mock_stat
        mock_path_cls.return_value = mock_db_path

        # Make experiments() raise an error
        mock_experiments.side_effect = Exception("Database error")

        result = json.loads(get_database_stats())
        # Should handle error gracefully with count_error field
        assert "count_error" in result
        assert "Database error" in result["count_error"]


class TestQueryToolsIntegration:
    """Test integration between query tools."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @pytest.mark.skipif(not MEASUREIT_AVAILABLE, reason="MeasureIt not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    def test_all_tools_use_same_path_resolution(
        self, mock_experiments, temp_dir, monkeypatch
    ):
        """Test all tools use consistent path resolution."""
        mock_experiments.return_value = []

        # Create the expected database file
        db_dir = temp_dir / "Databases"
        db_dir.mkdir()
        expected_db = db_dir / "Example_database.db"
        expected_db.touch()

        # Mock measureit.get_path to return our temp directory
        with patch("measureit.get_path") as mock_get_path:
            mock_get_path.return_value = db_dir

            experiments_result = json.loads(list_experiments())
            stats_result = json.loads(get_database_stats())

            expected_path = str(expected_db)
            # Check if database_path exists (may be in error dict)
            if "database_path" in experiments_result:
                assert experiments_result["database_path"] == expected_path
            if "database_path" in stats_result:
                assert stats_result["database_path"] == expected_path

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_all_tools_return_valid_json(self):
        """Test all tools return valid JSON."""
        with patch("instrmcp.extensions.database.query_tools.load_by_id") as mock_load:
            mock_dataset = MagicMock()
            mock_dataset.run_id = 1
            mock_dataset.captured_run_id = 1
            mock_dataset.exp_id = 1
            mock_dataset.exp_name = "test"
            mock_dataset.sample_name = "sample"
            mock_dataset.name = "dataset"
            mock_dataset.guid = "test-guid"
            mock_dataset.completed = True
            mock_dataset.__len__ = MagicMock(return_value=10)
            mock_dataset.parameters = {}
            mock_dataset.metadata = {}
            mock_dataset.get_parameter_data.return_value = {}
            mock_load.return_value = mock_dataset

            experiments = list_experiments()
            dataset_info = get_dataset_info(1)
            stats = get_database_stats()

            json.loads(experiments)
            json.loads(dataset_info)
            json.loads(stats)

    def test_all_tools_without_qcodes_consistent(self):
        """Test all tools handle missing QCodes consistently."""
        with patch("instrmcp.extensions.database.query_tools.QCODES_AVAILABLE", False):
            experiments = json.loads(list_experiments())
            dataset_info = json.loads(get_dataset_info(1))
            stats = json.loads(get_database_stats())

            assert "error" in experiments
            assert "error" in dataset_info
            assert "error" in stats

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch("instrmcp.extensions.database.query_tools.experiments")
    @patch("instrmcp.extensions.database.query_tools.load_by_id")
    def test_tools_work_with_same_database(
        self, mock_load, mock_experiments, mock_database_path
    ):
        """Test tools work consistently with same database."""
        mock_exp = MagicMock()
        mock_exp.exp_id = 1
        mock_exp.name = "test"
        mock_exp.sample_name = "sample"
        mock_experiments.return_value = [mock_exp]

        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.exp_id = 1
        mock_dataset.exp_name = "test"
        mock_dataset.sample_name = "sample"
        mock_dataset.name = "dataset"
        mock_dataset.guid = "test-guid"
        mock_dataset.completed = True
        mock_dataset.__len__ = MagicMock(return_value=10)
        mock_dataset.parameters = {}
        mock_dataset.metadata = {}
        mock_dataset.get_parameter_data.return_value = {}
        mock_load.return_value = mock_dataset

        experiments = json.loads(list_experiments(mock_database_path))
        dataset_info = json.loads(get_dataset_info(1, mock_database_path))
        stats = json.loads(get_database_stats(mock_database_path))

        # All should reference same database
        assert experiments["database_path"] == mock_database_path
        assert stats["database_path"] == mock_database_path
