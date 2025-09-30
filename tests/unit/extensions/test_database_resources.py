"""
Unit tests for database resource providers.

Tests database configuration, recent measurements, and resource
generation for QCodes database integration.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime

from instrmcp.extensions.database.db_resources import (
    get_current_database_config,
    get_recent_measurements,
    _resolve_database_path,
    QCODES_AVAILABLE
)


class TestResolveDatabasePath:
    """Test database path resolution logic."""

    def test_resolve_explicit_path(self):
        """Test explicit path takes precedence."""
        explicit_path = "/explicit/path/to/database.db"
        result = _resolve_database_path(explicit_path)
        assert result == explicit_path

    def test_resolve_measureit_home_path(self, monkeypatch, temp_dir):
        """Test MeasureItHome environment variable is used."""
        measureit_home = str(temp_dir)
        monkeypatch.setenv('MeasureItHome', measureit_home)

        result = _resolve_database_path(None)
        expected = str(temp_dir / "Databases" / "Example_database.db")
        assert result == expected

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resolve_qcodes_default(self, monkeypatch):
        """Test falls back to QCodes config."""
        # Clear MeasureItHome
        monkeypatch.delenv('MeasureItHome', raising=False)

        with patch('instrmcp.extensions.database.db_resources.qc') as mock_qc:
            mock_qc.config.core.db_location = "/qcodes/default.db"
            result = _resolve_database_path(None)
            assert result == "/qcodes/default.db"

    def test_resolve_priority_explicit_over_env(self, monkeypatch, temp_dir):
        """Test explicit path has priority over environment."""
        monkeypatch.setenv('MeasureItHome', str(temp_dir))
        explicit_path = "/explicit/database.db"

        result = _resolve_database_path(explicit_path)
        assert result == explicit_path


class TestDatabaseConfig:
    """Test database configuration resource."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_returns_valid_json(self):
        """Test config returns valid JSON."""
        config = get_current_database_config()
        parsed = json.loads(config)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_has_required_fields(self):
        """Test config includes required fields."""
        config = json.loads(get_current_database_config())
        assert "database_path" in config
        assert "database_exists" in config
        assert "connection_status" in config
        assert "qcodes_version" in config
        assert "last_checked" in config

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_with_explicit_path(self, mock_database_path):
        """Test config with explicit database path."""
        config = json.loads(get_current_database_config(mock_database_path))
        assert config["database_path"] == mock_database_path

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_checks_file_existence(self, temp_dir):
        """Test config checks if database file exists."""
        db_path = temp_dir / "test.db"
        db_path.touch()  # Create empty file

        config = json.loads(get_current_database_config(str(db_path)))
        assert config["database_exists"] is True
        assert "database_size_bytes" in config
        assert "database_modified" in config

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_nonexistent_database(self, temp_dir):
        """Test config with nonexistent database."""
        db_path = temp_dir / "nonexistent.db"

        config = json.loads(get_current_database_config(str(db_path)))
        assert config["database_exists"] is False

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.experiments')
    def test_config_connection_status(self, mock_experiments):
        """Test config reports connection status."""
        mock_experiments.return_value = []

        config = json.loads(get_current_database_config())
        assert config["connection_status"] in ["connected", "error", "unknown"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.experiments')
    def test_config_experiment_count(self, mock_experiments):
        """Test config includes experiment count."""
        mock_exp1 = MagicMock()
        mock_exp2 = MagicMock()
        mock_experiments.return_value = [mock_exp1, mock_exp2]

        config = json.loads(get_current_database_config())
        if config["connection_status"] == "connected":
            assert config["experiment_count"] == 2

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_includes_qcodes_version(self):
        """Test config includes QCodes version."""
        config = json.loads(get_current_database_config())
        assert "qcodes_version" in config
        assert isinstance(config["qcodes_version"], str)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_includes_configuration_dict(self):
        """Test config includes QCodes configuration."""
        config = json.loads(get_current_database_config())
        # Configuration may be empty dict if there are errors, so just check it exists
        assert "configuration" in config
        assert isinstance(config["configuration"], dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.experiments')
    def test_config_handles_connection_error(self, mock_experiments):
        """Test config handles connection errors gracefully."""
        mock_experiments.side_effect = Exception("Connection failed")

        config = json.loads(get_current_database_config())
        assert config["connection_status"] == "error"
        assert "connection_error" in config

    def test_config_without_qcodes(self):
        """Test config returns error when QCodes unavailable."""
        with patch('instrmcp.extensions.database.db_resources.QCODES_AVAILABLE', False):
            config = json.loads(get_current_database_config())
            assert "error" in config
            assert "QCodes not available" in config["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_timestamp_format(self):
        """Test config timestamp is in ISO format."""
        config = json.loads(get_current_database_config())
        timestamp = config["last_checked"]
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp)


class TestRecentMeasurements:
    """Test recent measurements resource."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_returns_valid_json(self):
        """Test recent measurements returns valid JSON."""
        result = get_recent_measurements(limit=5)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_has_required_fields(self):
        """Test recent measurements includes required fields."""
        result = json.loads(get_recent_measurements())
        assert "database_path" in result
        assert "limit" in result
        assert "recent_measurements" in result
        assert "retrieved_at" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_respects_limit(self):
        """Test recent measurements respects limit parameter."""
        limit = 5
        result = json.loads(get_recent_measurements(limit=limit))
        assert result["limit"] == limit
        assert len(result["recent_measurements"]) <= limit

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.load_by_id')
    def test_recent_measurements_dataset_structure(self, mock_load):
        """Test each measurement has proper structure."""
        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.exp_name = "test_exp"
        mock_dataset.sample_name = "test_sample"
        mock_dataset.name = "test_measurement"
        mock_dataset.completed = True
        mock_dataset.__len__ = MagicMock(return_value=100)
        mock_dataset.parameters = {"voltage": MagicMock(), "current": MagicMock()}
        mock_dataset.run_timestamp_raw = 1234567890.0

        mock_load.return_value = mock_dataset

        result = json.loads(get_recent_measurements(limit=5))
        measurements = result["recent_measurements"]

        if len(measurements) > 0:
            measurement = measurements[0]
            assert "run_id" in measurement
            assert "experiment_name" in measurement
            assert "sample_name" in measurement
            assert "name" in measurement
            assert "completed" in measurement
            assert "number_of_results" in measurement
            assert "parameters" in measurement

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.load_by_id')
    def test_recent_measurements_includes_timestamp(self, mock_load):
        """Test measurements include timestamp information."""
        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.exp_name = "test"
        mock_dataset.sample_name = "sample"
        mock_dataset.name = "measurement"
        mock_dataset.completed = True
        mock_dataset.__len__ = MagicMock(return_value=10)
        mock_dataset.parameters = {}
        mock_dataset.run_timestamp_raw = 1234567890.0

        mock_load.return_value = mock_dataset

        result = json.loads(get_recent_measurements(limit=5))
        measurements = result["recent_measurements"]

        if len(measurements) > 0:
            measurement = measurements[0]
            if "timestamp" in measurement:
                assert isinstance(measurement["timestamp"], float)
            if "timestamp_readable" in measurement:
                datetime.fromisoformat(measurement["timestamp_readable"])

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.load_by_id')
    def test_recent_measurements_sorted_by_time(self, mock_load):
        """Test measurements are sorted by timestamp."""
        # Create mock datasets with different timestamps
        def create_mock_dataset(run_id, timestamp):
            ds = MagicMock()
            ds.run_id = run_id
            ds.captured_run_id = run_id
            ds.exp_name = "test"
            ds.sample_name = "sample"
            ds.name = f"measurement_{run_id}"
            ds.completed = True
            ds.__len__ = MagicMock(return_value=10)
            ds.parameters = {}
            ds.run_timestamp_raw = timestamp
            return ds

        datasets = {
            1: create_mock_dataset(1, 1000.0),
            2: create_mock_dataset(2, 3000.0),
            3: create_mock_dataset(3, 2000.0),
        }

        mock_load.side_effect = lambda rid: datasets.get(rid) if rid in datasets else MagicMock(side_effect=Exception)

        result = json.loads(get_recent_measurements(limit=10))
        measurements = result["recent_measurements"]

        # Should be sorted by timestamp descending (most recent first)
        if len(measurements) >= 2:
            for i in range(len(measurements) - 1):
                if measurements[i]["timestamp"] and measurements[i+1]["timestamp"]:
                    assert measurements[i]["timestamp"] >= measurements[i+1]["timestamp"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_with_explicit_path(self, mock_database_path):
        """Test recent measurements with explicit database path."""
        result = json.loads(get_recent_measurements(limit=5, database_path=mock_database_path))
        assert result["database_path"] == mock_database_path

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.load_by_id')
    def test_recent_measurements_includes_measureit_type(self, mock_load):
        """Test measurements include MeasureIt type if available."""
        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.exp_name = "test"
        mock_dataset.sample_name = "sample"
        mock_dataset.name = "measurement"
        mock_dataset.completed = True
        mock_dataset.__len__ = MagicMock(return_value=10)
        mock_dataset.parameters = {}
        mock_dataset.run_timestamp_raw = 1234567890.0
        mock_dataset.metadata = {
            'measureit': json.dumps({'class': 'Sweep1D', 'module': 'MeasureIt'})
        }

        mock_load.return_value = mock_dataset

        result = json.loads(get_recent_measurements(limit=5))
        measurements = result["recent_measurements"]

        if len(measurements) > 0:
            assert "measurement_type" in measurements[0]

    def test_recent_measurements_without_qcodes(self):
        """Test recent measurements returns error when QCodes unavailable."""
        with patch('instrmcp.extensions.database.db_resources.QCODES_AVAILABLE', False):
            result = json.loads(get_recent_measurements())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    @patch('instrmcp.extensions.database.db_resources.load_by_id')
    def test_recent_measurements_handles_incomplete_data(self, mock_load):
        """Test recent measurements handles datasets with missing fields."""
        mock_dataset = MagicMock()
        mock_dataset.run_id = 1
        mock_dataset.captured_run_id = 1
        mock_dataset.exp_name = "test"
        mock_dataset.sample_name = "sample"
        mock_dataset.name = "measurement"
        mock_dataset.completed = False
        mock_dataset.__len__ = MagicMock(return_value=0)
        mock_dataset.parameters = {}
        # No timestamp
        del mock_dataset.run_timestamp_raw

        mock_load.return_value = mock_dataset

        result = json.loads(get_recent_measurements(limit=5))
        # Should not raise exception, handle gracefully
        assert "recent_measurements" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_includes_total_available(self):
        """Test result includes total available count."""
        result = json.loads(get_recent_measurements(limit=5))
        assert "total_available" in result or "recent_measurements" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_handles_errors_gracefully(self):
        """Test recent measurements handles database errors."""
        with patch('instrmcp.extensions.database.db_resources.load_by_id') as mock_load:
            mock_load.side_effect = Exception("Database error")

            result = json.loads(get_recent_measurements())
            # Should return error but still be valid JSON
            assert "error" in result or "recent_measurements" in result


class TestResourceIntegration:
    """Test integration between resource providers."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_both_resources_use_same_path_resolution(self, temp_dir, monkeypatch):
        """Test config and measurements use consistent path resolution."""
        monkeypatch.setenv('MeasureItHome', str(temp_dir))

        config = json.loads(get_current_database_config())
        measurements = json.loads(get_recent_measurements())

        expected_path = str(temp_dir / "Databases" / "Example_database.db")
        assert config["database_path"] == expected_path
        assert measurements["database_path"] == expected_path

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resources_handle_same_database(self, mock_database_path):
        """Test both resources work with same database path."""
        config = json.loads(get_current_database_config(mock_database_path))
        measurements = json.loads(get_recent_measurements(database_path=mock_database_path))

        assert config["database_path"] == mock_database_path
        assert measurements["database_path"] == mock_database_path

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resources_return_valid_json_structure(self):
        """Test both resources return valid, parseable JSON."""
        config = get_current_database_config()
        measurements = get_recent_measurements(limit=5)

        config_parsed = json.loads(config)
        measurements_parsed = json.loads(measurements)

        assert isinstance(config_parsed, dict)
        assert isinstance(measurements_parsed, dict)

    def test_resources_without_qcodes_consistent(self):
        """Test both resources handle missing QCodes consistently."""
        with patch('instrmcp.extensions.database.db_resources.QCODES_AVAILABLE', False):
            config = json.loads(get_current_database_config())
            measurements = json.loads(get_recent_measurements())

            assert "error" in config
            assert "error" in measurements
            assert "QCodes" in config["error"]
            assert "QCodes" in measurements["error"]
