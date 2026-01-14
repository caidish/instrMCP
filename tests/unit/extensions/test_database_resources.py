"""
Unit tests for database resource providers.

Tests database configuration, recent measurements, and resource
generation for QCodes database integration.

These tests use a real SQLite database with the QCoDeS schema since
the implementation now uses direct SQLite queries instead of the
QCoDeS API functions.
"""

import pytest
import json
import sqlite3
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

from instrmcp.extensions.database.db_resources import (
    get_current_database_config,
    get_recent_measurements,
    _resolve_database_path,
    QCODES_AVAILABLE,
)


@pytest.fixture
def qcodes_test_database(tmp_path):
    """Create a SQLite database with QCoDeS schema for testing."""
    db_path = tmp_path / "test_qcodes.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create experiments table (QCoDeS schema)
    cursor.execute(
        """
        CREATE TABLE experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT,
            sample_name TEXT,
            format_string TEXT,
            start_time REAL,
            end_time REAL
        )
    """
    )

    # Create runs table (QCoDeS schema)
    cursor.execute(
        """
        CREATE TABLE runs (
            run_id INTEGER PRIMARY KEY,
            exp_id INTEGER,
            name TEXT,
            result_table_name TEXT,
            guid TEXT,
            run_timestamp REAL,
            completed_timestamp REAL,
            is_completed INTEGER,
            captured_run_id INTEGER,
            run_description TEXT,
            measureit TEXT,
            FOREIGN KEY (exp_id) REFERENCES experiments(exp_id)
        )
    """
    )

    # Insert test experiment
    cursor.execute(
        """
        INSERT INTO experiments (exp_id, name, sample_name, format_string, start_time)
        VALUES (1, 'test_experiment', 'test_sample', '{name}', 1234567890.0)
    """
    )

    # Insert test runs
    test_runs = [
        (
            1,
            1,
            "run_1",
            "results_1",
            "guid-1",
            1234567890.0,
            1234567900.0,
            1,
            1,
            '{"interdependencies": {"paramspecs": [{"name": "voltage"}, {"name": "current", "depends_on": ["voltage"]}]}}',
            '{"class": "Sweep1D", "module": "MeasureIt"}',
        ),
        (
            2,
            1,
            "run_2",
            "results_2",
            "guid-2",
            1234567950.0,
            1234567960.0,
            1,
            2,
            '{"interdependencies": {"paramspecs": [{"name": "time"}, {"name": "signal"}]}}',
            '{"class": "Sweep0D", "module": "MeasureIt"}',
        ),
        (
            3,
            1,
            "run_3",
            "results_3",
            "guid-3",
            1234568000.0,
            None,
            0,
            3,
            '{"interdependencies": {"paramspecs": []}}',
            None,
        ),  # No measureit metadata (raw QCoDeS)
    ]

    cursor.executemany(
        """
        INSERT INTO runs (run_id, exp_id, name, result_table_name, guid, run_timestamp,
                         completed_timestamp, is_completed, captured_run_id, run_description, measureit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        test_runs,
    )

    # Create result tables for each run
    for run_id in [1, 2, 3]:
        table_name = f"results_{run_id}"
        cursor.execute(
            f"""
            CREATE TABLE "{table_name}" (
                id INTEGER PRIMARY KEY,
                voltage REAL,
                current REAL
            )
        """
        )
        # Insert some test data
        for i in range(10):
            cursor.execute(
                f'INSERT INTO "{table_name}" (voltage, current) VALUES (?, ?)',
                (i * 0.1, i * 0.01),
            )

    conn.commit()
    conn.close()

    return str(db_path)


@pytest.fixture
def empty_qcodes_database(tmp_path):
    """Create an empty SQLite database with QCoDeS schema."""
    db_path = tmp_path / "empty_qcodes.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT,
            sample_name TEXT,
            format_string TEXT,
            start_time REAL,
            end_time REAL
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE runs (
            run_id INTEGER PRIMARY KEY,
            exp_id INTEGER,
            name TEXT,
            result_table_name TEXT,
            guid TEXT,
            run_timestamp REAL,
            completed_timestamp REAL,
            is_completed INTEGER,
            captured_run_id INTEGER,
            run_description TEXT,
            measureit TEXT,
            FOREIGN KEY (exp_id) REFERENCES experiments(exp_id)
        )
    """
    )

    conn.commit()
    conn.close()

    return str(db_path)


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
        monkeypatch.setenv("MeasureItHome", measureit_home)

        result = _resolve_database_path(None)
        expected = str(temp_dir / "Databases" / "Example_database.db")
        assert result == expected

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resolve_qcodes_default(self, monkeypatch):
        """Test falls back to QCodes config."""
        # Clear MeasureItHome
        monkeypatch.delenv("MeasureItHome", raising=False)

        with patch("instrmcp.extensions.database.db_resources.qc") as mock_qc:
            mock_qc.config.core.db_location = "/qcodes/default.db"
            result = _resolve_database_path(None)
            assert result == "/qcodes/default.db"

    def test_resolve_priority_explicit_over_env(self, monkeypatch, temp_dir):
        """Test explicit path has priority over environment."""
        monkeypatch.setenv("MeasureItHome", str(temp_dir))
        explicit_path = "/explicit/database.db"

        result = _resolve_database_path(explicit_path)
        assert result == explicit_path


class TestDatabaseConfig:
    """Test database configuration resource."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_returns_valid_json(self, qcodes_test_database):
        """Test config returns valid JSON."""
        config = get_current_database_config(qcodes_test_database)
        parsed = json.loads(config)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_has_required_fields(self, qcodes_test_database):
        """Test config includes required fields."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert "database_path" in config
        assert "database_exists" in config
        assert "connection_status" in config
        assert "qcodes_version" in config
        assert "last_checked" in config

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_with_explicit_path(self, qcodes_test_database):
        """Test config with explicit database path."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert config["database_path"] == qcodes_test_database

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_checks_file_existence(self, qcodes_test_database):
        """Test config checks if database file exists."""
        config = json.loads(get_current_database_config(qcodes_test_database))
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
    def test_config_connection_status_connected(self, qcodes_test_database):
        """Test config reports connected status for valid database."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert config["connection_status"] == "connected"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_experiment_count(self, qcodes_test_database):
        """Test config includes experiment count from database."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert config["connection_status"] == "connected"
        assert config["experiment_count"] == 1  # We inserted 1 experiment

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_includes_qcodes_version(self, qcodes_test_database):
        """Test config includes QCodes version."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert "qcodes_version" in config
        assert isinstance(config["qcodes_version"], str)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_includes_configuration_dict(self, qcodes_test_database):
        """Test config includes QCodes configuration."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        assert "configuration" in config
        assert isinstance(config["configuration"], dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_handles_connection_error(self, temp_dir):
        """Test config handles connection errors gracefully."""
        # Create an invalid database file (not a SQLite database)
        invalid_db = temp_dir / "invalid.db"
        invalid_db.write_text("This is not a SQLite database")

        config = json.loads(get_current_database_config(str(invalid_db)))
        assert config["connection_status"] == "error"
        assert "connection_error" in config

    def test_config_without_qcodes(self):
        """Test config returns error when QCodes unavailable."""
        with patch("instrmcp.extensions.database.db_resources.QCODES_AVAILABLE", False):
            config = json.loads(get_current_database_config())
            assert "error" in config
            assert "QCodes not available" in config["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_config_timestamp_format(self, qcodes_test_database):
        """Test config timestamp is in ISO format."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        timestamp = config["last_checked"]
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp)


class TestRecentMeasurements:
    """Test recent measurements resource."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_returns_valid_json(self, qcodes_test_database):
        """Test recent measurements returns valid JSON."""
        result = get_recent_measurements(limit=5, database_path=qcodes_test_database)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_has_required_fields(self, qcodes_test_database):
        """Test recent measurements includes required fields."""
        result = json.loads(get_recent_measurements(database_path=qcodes_test_database))
        assert "database_path" in result
        assert "limit" in result
        assert "recent_measurements" in result
        assert "retrieved_at" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_respects_limit(self, qcodes_test_database):
        """Test recent measurements respects limit parameter."""
        limit = 2
        result = json.loads(
            get_recent_measurements(limit=limit, database_path=qcodes_test_database)
        )
        assert result["limit"] == limit
        assert len(result["recent_measurements"]) <= limit

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_dataset_structure(self, qcodes_test_database):
        """Test each measurement has proper structure."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        assert len(measurements) == 3  # We inserted 3 runs
        measurement = measurements[0]

        assert "run_id" in measurement
        assert "experiment_name" in measurement
        assert "sample_name" in measurement
        assert "name" in measurement
        assert "completed" in measurement
        assert "number_of_results" in measurement
        assert "parameters" in measurement

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_includes_timestamp(self, qcodes_test_database):
        """Test measurements include timestamp information."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        assert len(measurements) > 0
        measurement = measurements[0]

        assert "timestamp" in measurement
        assert isinstance(measurement["timestamp"], (int, float))
        if measurement.get("timestamp_readable"):
            datetime.fromisoformat(measurement["timestamp_readable"])

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_sorted_by_time(self, qcodes_test_database):
        """Test measurements are sorted by timestamp descending."""
        result = json.loads(
            get_recent_measurements(limit=10, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        # Should be sorted by timestamp descending (most recent first)
        for i in range(len(measurements) - 1):
            ts1 = measurements[i]["timestamp"] or 0
            ts2 = measurements[i + 1]["timestamp"] or 0
            assert ts1 >= ts2, f"Measurements not sorted: {ts1} < {ts2}"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_with_explicit_path(self, qcodes_test_database):
        """Test recent measurements with explicit database path."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        assert result["database_path"] == qcodes_test_database

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_includes_measureit_type(self, qcodes_test_database):
        """Test measurements include MeasureIt type if available."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        # Find the Sweep1D measurement
        sweep1d_measurements = [
            m for m in measurements if m["measurement_type"] == "Sweep1D"
        ]
        assert len(sweep1d_measurements) >= 1

        # Also check for qcodes type (run 3 has no measureit metadata)
        qcodes_measurements = [
            m for m in measurements if m["measurement_type"] == "qcodes"
        ]
        assert len(qcodes_measurements) >= 1

    def test_recent_measurements_without_qcodes(self):
        """Test recent measurements returns error when QCodes unavailable."""
        with patch("instrmcp.extensions.database.db_resources.QCODES_AVAILABLE", False):
            result = json.loads(get_recent_measurements())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_handles_incomplete_data(self, empty_qcodes_database):
        """Test recent measurements handles empty database gracefully."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=empty_qcodes_database)
        )
        assert "recent_measurements" in result
        assert len(result["recent_measurements"]) == 0

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_includes_total_available(self, qcodes_test_database):
        """Test result includes total available count."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        assert "total_available" in result
        assert result["total_available"] == 3  # We inserted 3 runs

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_handles_errors_gracefully(self, temp_dir):
        """Test recent measurements handles database errors."""
        # Create an invalid database file
        invalid_db = temp_dir / "invalid.db"
        invalid_db.write_text("Not a database")

        result = json.loads(get_recent_measurements(database_path=str(invalid_db)))
        # Should return error but still be valid JSON
        assert "error" in result or "recent_measurements" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_result_count(self, qcodes_test_database):
        """Test that number_of_results is correctly extracted from result tables."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        # Each result table has 10 rows
        for m in measurements:
            assert m["number_of_results"] == 10

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_recent_measurements_parameters_parsed(self, qcodes_test_database):
        """Test that parameters are parsed from run_description."""
        result = json.loads(
            get_recent_measurements(limit=5, database_path=qcodes_test_database)
        )
        measurements = result["recent_measurements"]

        # Find run_1 which has voltage and current parameters
        run1 = next((m for m in measurements if m["run_id"] == 1), None)
        assert run1 is not None
        assert "voltage" in run1["parameters"]
        assert "current" in run1["parameters"]


class TestResourceIntegration:
    """Test integration between resource providers."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_both_resources_use_same_path_resolution(self, qcodes_test_database):
        """Test config and measurements use consistent path."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        measurements = json.loads(
            get_recent_measurements(database_path=qcodes_test_database)
        )

        assert config["database_path"] == qcodes_test_database
        assert measurements["database_path"] == qcodes_test_database

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resources_handle_same_database(self, qcodes_test_database):
        """Test both resources work with same database path."""
        config = json.loads(get_current_database_config(qcodes_test_database))
        measurements = json.loads(
            get_recent_measurements(database_path=qcodes_test_database)
        )

        assert config["database_path"] == qcodes_test_database
        assert measurements["database_path"] == qcodes_test_database

        # Config should show the experiment
        assert config["experiment_count"] == 1

        # Measurements should show the runs
        assert len(measurements["recent_measurements"]) == 3

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resources_return_valid_json_structure(self, qcodes_test_database):
        """Test both resources return valid, parseable JSON."""
        config = get_current_database_config(qcodes_test_database)
        measurements = get_recent_measurements(
            limit=5, database_path=qcodes_test_database
        )

        config_parsed = json.loads(config)
        measurements_parsed = json.loads(measurements)

        assert isinstance(config_parsed, dict)
        assert isinstance(measurements_parsed, dict)

    def test_resources_without_qcodes_consistent(self):
        """Test both resources handle missing QCodes consistently."""
        with patch("instrmcp.extensions.database.db_resources.QCODES_AVAILABLE", False):
            config = json.loads(get_current_database_config())
            measurements = json.loads(get_recent_measurements())

            assert "error" in config
            assert "error" in measurements
            assert "QCodes" in config["error"]
            assert "QCodes" in measurements["error"]
