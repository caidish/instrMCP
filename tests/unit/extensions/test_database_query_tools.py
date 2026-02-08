"""
Unit tests for database query tools.

Tests list_experiments, get_dataset_info, get_database_stats, and
database path resolution for QCodes database integration.

These tests use a real SQLite database with the QCoDeS schema since
the implementation now uses direct SQLite queries instead of the
QCoDeS API functions.
"""

import pytest
import json
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime

from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
    list_experiments,
    get_dataset_info,
    get_database_stats,
    resolve_database_path,
    _list_available_databases,
    _format_file_size,
    QCODES_AVAILABLE,
)

# Check if MeasureIt is available
try:
    import measureit  # noqa: F401

    MEASUREIT_AVAILABLE = True
except ImportError:
    MEASUREIT_AVAILABLE = False


def _count_run_ids(run_ids: str) -> int:
    """Count runs from a concise run_ids string (e.g., 1,2 or 6-16(11))."""
    if not run_ids:
        return 0
    if "(" in run_ids and run_ids.endswith(")"):
        try:
            return int(run_ids.split("(")[-1].rstrip(")"))
        except ValueError:
            pass
    return len([r for r in run_ids.split(",") if r])


@pytest.fixture
def qcodes_test_database(tmp_path):
    """Create a SQLite database with QCoDeS schema for testing."""
    db_path = tmp_path / "test_qcodes.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create experiments table (QCoDeS schema)
    cursor.execute("""
        CREATE TABLE experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT,
            sample_name TEXT,
            format_string TEXT,
            start_time REAL,
            end_time REAL
        )
    """)

    # Create runs table (QCoDeS schema)
    cursor.execute("""
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
            snapshot TEXT,
            FOREIGN KEY (exp_id) REFERENCES experiments(exp_id)
        )
    """)

    # Create layouts table (for parameter info)
    cursor.execute("""
        CREATE TABLE layouts (
            layout_id INTEGER PRIMARY KEY,
            run_id INTEGER,
            parameter TEXT,
            label TEXT,
            unit TEXT,
            inferred_from TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        )
    """)

    # Create dependencies table
    cursor.execute("""
        CREATE TABLE dependencies (
            id INTEGER PRIMARY KEY,
            dependent INTEGER,
            independent INTEGER,
            axis_num INTEGER,
            FOREIGN KEY (dependent) REFERENCES layouts(layout_id),
            FOREIGN KEY (independent) REFERENCES layouts(layout_id)
        )
    """)

    # Insert test experiments
    cursor.execute("""
        INSERT INTO experiments (exp_id, name, sample_name, format_string, start_time)
        VALUES (1, 'test_experiment', 'test_sample', '{name}', 1234567890.0)
    """)
    cursor.execute("""
        INSERT INTO experiments (exp_id, name, sample_name, format_string, start_time)
        VALUES (2, 'second_experiment', 'sample2', '{name}', 1234567900.0)
    """)

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
            2,
            "run_3",
            "results_3",
            "guid-3",
            1234568000.0,
            None,
            0,
            3,
            '{"interdependencies": {"paramspecs": []}}',
            None,
        ),  # No measureit metadata
    ]

    cursor.executemany(
        """
        INSERT INTO runs (run_id, exp_id, name, result_table_name, guid, run_timestamp,
                         completed_timestamp, is_completed, captured_run_id, run_description, measureit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        test_runs,
    )

    # Insert layouts (parameters) for run 1
    cursor.execute("""
        INSERT INTO layouts (layout_id, run_id, parameter, label, unit, inferred_from)
        VALUES (1, 1, 'voltage', 'Gate Voltage', 'V', NULL)
    """)
    cursor.execute("""
        INSERT INTO layouts (layout_id, run_id, parameter, label, unit, inferred_from)
        VALUES (2, 1, 'current', 'Drain Current', 'A', NULL)
    """)

    # Insert dependency (current depends on voltage)
    cursor.execute("""
        INSERT INTO dependencies (dependent, independent, axis_num)
        VALUES (2, 1, 0)
    """)

    # Create result tables for each run
    for run_id in [1, 2, 3]:
        table_name = f"results_{run_id}"
        cursor.execute(f"""
            CREATE TABLE "{table_name}" (
                id INTEGER PRIMARY KEY,
                voltage REAL,
                current REAL
            )
        """)
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

    cursor.execute("""
        CREATE TABLE experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT,
            sample_name TEXT,
            format_string TEXT,
            start_time REAL,
            end_time REAL
        )
    """)

    cursor.execute("""
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
    """)

    conn.commit()
    conn.close()

    return str(db_path)


class TestResolveDatabasePath:
    """Test database path resolution logic."""

    def test_resolve_explicit_path(self, tmp_path):
        """Test explicit path takes precedence."""
        db_file = tmp_path / "database.db"
        db_file.touch()
        explicit_path = str(db_file)

        resolved_path, resolution_info = resolve_database_path(explicit_path)
        assert resolved_path == explicit_path
        assert resolution_info["source"] == "explicit"
        assert resolution_info["tried_path"] == explicit_path

    def test_resolve_nested_databases_in_data_dir(self, tmp_path):
        """Test nested Databases directories are used when scan_nested is enabled."""
        nested_dir = tmp_path / "projectA" / "Databases"
        nested_dir.mkdir(parents=True)
        db_file = nested_dir / "nested.db"
        db_file.touch()

        resolved_path, resolution_info = resolve_database_path(
            None,
            data_dir=tmp_path,
            scan_nested=True,
        )

        assert resolved_path == str(db_file)
        assert resolution_info["source"] == "data_dir_nested"
        assert resolution_info["tried_path"] == str(db_file)

    @pytest.mark.skipif(not MEASUREIT_AVAILABLE, reason="MeasureIt not available")
    def test_resolve_measureit_home_path(self, monkeypatch, temp_dir):
        """Test MeasureIt get_path() is used."""
        db_dir = temp_dir / "Databases"
        db_dir.mkdir()
        db_file = db_dir / "Example_database.db"
        db_file.touch()

        with patch("measureit.get_path") as mock_get_path:
            mock_get_path.return_value = db_dir

            resolved_path, resolution_info = resolve_database_path(None)
            expected = str(db_dir / "Example_database.db")
            assert resolved_path == expected
            assert resolution_info["source"] == "measureit_default"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_resolve_qcodes_default(self, monkeypatch, temp_dir):
        """Test falls back to QCodes config."""
        qcodes_db = temp_dir / "qcodes.db"
        qcodes_db.touch()

        with patch("measureit.get_path", side_effect=ImportError):
            with patch(
                "instrmcp.servers.jupyter_qcodes.options.database.query_tools.qc"
            ) as mock_qc:
                mock_qc.config.core.db_location = str(qcodes_db)
                resolved_path, resolution_info = resolve_database_path(None)
                assert resolved_path == str(qcodes_db)
                assert resolution_info["source"] == "qcodes_config"

    def test_resolve_cwd_database(self, tmp_path, monkeypatch):
        """Test CWD databases are discovered when MeasureIt is unavailable."""
        db_file = tmp_path / "workspace_data.db"
        db_file.touch()

        monkeypatch.chdir(tmp_path)

        with patch("measureit.get_path", side_effect=ImportError):
            with patch(
                "instrmcp.servers.jupyter_qcodes.options.database.query_tools.qc"
            ) as mock_qc:
                mock_qc.config.core.db_location = "/nonexistent/qcodes.db"
                resolved_path, resolution_info = resolve_database_path(None)
                assert resolved_path == str(db_file)
                assert resolution_info["source"] == "jupyter_cwd"

    def test_resolve_cwd_prefers_example_database(self, tmp_path, monkeypatch):
        """Test CWD prefers Example_database.db over other .db files."""
        other_db = tmp_path / "other.db"
        other_db.touch()
        example_db = tmp_path / "Example_database.db"
        example_db.touch()

        monkeypatch.chdir(tmp_path)

        with patch("measureit.get_path", side_effect=ImportError):
            with patch(
                "instrmcp.servers.jupyter_qcodes.options.database.query_tools.qc"
            ) as mock_qc:
                mock_qc.config.core.db_location = "/nonexistent/qcodes.db"
                resolved_path, resolution_info = resolve_database_path(None)
                assert resolved_path == str(example_db)
                assert resolution_info["source"] == "jupyter_cwd"

    def test_resolve_measureit_has_priority_over_cwd(self, tmp_path, monkeypatch):
        """Test MeasureIt default takes priority over CWD."""
        # CWD has a database
        cwd_db = tmp_path / "cwd_data.db"
        cwd_db.touch()
        monkeypatch.chdir(tmp_path)

        # MeasureIt also has a database
        measureit_dir = tmp_path / "MeasureItHome" / "Databases"
        measureit_dir.mkdir(parents=True)
        measureit_db = measureit_dir / "Example_database.db"
        measureit_db.touch()

        with patch("measureit.get_path", return_value=measureit_dir):
            resolved_path, resolution_info = resolve_database_path(None)
            assert resolved_path == str(measureit_db)
            assert resolution_info["source"] == "measureit_default"

    @pytest.mark.skipif(not MEASUREIT_AVAILABLE, reason="MeasureIt not available")
    def test_resolve_priority_explicit_over_env(self, monkeypatch, temp_dir):
        """Test explicit path has priority over environment."""
        explicit_db = temp_dir / "explicit.db"
        explicit_db.touch()
        explicit_path = str(explicit_db)

        db_dir = temp_dir / "Databases"
        db_dir.mkdir()

        with patch("measureit.get_path") as mock_get_path:
            mock_get_path.return_value = db_dir

            resolved_path, resolution_info = resolve_database_path(explicit_path)
            assert resolved_path == explicit_path
            assert resolution_info["source"] == "explicit"


class TestListAvailableDatabases:
    """Test _list_available_databases discovers CWD databases."""

    def test_list_finds_cwd_databases(self, tmp_path, monkeypatch):
        """Test that _list_available_databases finds databases in CWD."""
        db_file = tmp_path / "my_data.db"
        db_file.touch()
        monkeypatch.chdir(tmp_path)

        with patch("measureit.get_path", side_effect=ImportError):
            with patch(
                "instrmcp.servers.jupyter_qcodes.options.database.query_tools.qc"
            ) as mock_qc:
                mock_qc.config.core.db_location = "/nonexistent/qcodes.db"
                databases = _list_available_databases()
                cwd_dbs = [db for db in databases if db["source"] == "jupyter_cwd"]
                assert len(cwd_dbs) == 1
                assert cwd_dbs[0]["name"] == "my_data.db"

    def test_list_no_duplicates_with_cwd(self, tmp_path, monkeypatch):
        """Test that same database isn't listed twice from different sources."""
        db_file = tmp_path / "Example_database.db"
        db_file.touch()
        monkeypatch.chdir(tmp_path)

        # MeasureIt points to the same directory as CWD
        with patch("measureit.get_path", return_value=tmp_path):
            databases = _list_available_databases()
            paths = [db["path"] for db in databases]
            # Should appear only once (seen_paths deduplication)
            assert paths.count(str(db_file)) == 1


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


class TestListExperiments:
    """Test list_experiments functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_returns_valid_json(self, qcodes_test_database):
        """Test list_experiments returns valid JSON."""
        result = list_experiments(qcodes_test_database)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_has_required_fields(self, qcodes_test_database):
        """Test list_experiments includes required fields."""
        result = json.loads(list_experiments(qcodes_test_database))
        assert "database_path" in result
        assert "experiment_count" in result
        assert "experiments" in result
        assert isinstance(result["experiments"], list)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_empty_database(self, empty_qcodes_database):
        """Test list_experiments with empty database."""
        result = json.loads(list_experiments(empty_qcodes_database))
        assert result["experiment_count"] == 0
        assert result["experiments"] == []

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_multiple_experiments(self, qcodes_test_database):
        """Test list_experiments with multiple experiments."""
        result = json.loads(list_experiments(qcodes_test_database))
        assert result["experiment_count"] == 2
        assert len(result["experiments"]) == 2

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_experiment_structure(self, qcodes_test_database):
        """Test each experiment has proper structure."""
        result = json.loads(list_experiments(qcodes_test_database))
        exp = result["experiments"][0]

        assert exp["experiment_id"] == 1
        assert exp["name"] == "test_experiment"
        assert exp["sample_name"] == "test_sample"
        assert "run_ids" in exp
        assert isinstance(exp["run_ids"], str)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_with_explicit_path(self, qcodes_test_database):
        """Test list_experiments with explicit database path."""
        result = json.loads(list_experiments(qcodes_test_database))
        assert result["database_path"] == qcodes_test_database

    def test_list_experiments_without_qcodes(self):
        """Test list_experiments returns error when QCodes unavailable."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.database.query_tools.QCODES_AVAILABLE",
            False,
        ):
            result = json.loads(list_experiments())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_handles_errors(self, temp_dir):
        """Test list_experiments handles database errors gracefully."""
        # Create an invalid database file
        invalid_db = temp_dir / "invalid.db"
        invalid_db.write_text("Not a database")

        result = json.loads(list_experiments(str(invalid_db)))
        assert "error" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_list_experiments_run_ids(self, qcodes_test_database):
        """Test that run_ids are correctly extracted."""
        result = json.loads(list_experiments(qcodes_test_database))

        # First experiment should have runs 1 and 2
        exp1 = next(e for e in result["experiments"] if e["experiment_id"] == 1)
        assert exp1["run_ids"] == "1,2"

        # Second experiment should have run 3
        exp2 = next(e for e in result["experiments"] if e["experiment_id"] == 2)
        assert exp2["run_ids"] == "3"


class TestGetDatasetInfo:
    """Test get_dataset_info functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_returns_valid_json(self, qcodes_test_database):
        """Test get_dataset_info returns valid JSON."""
        result = get_dataset_info(1, qcodes_test_database)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_has_required_sections(self, qcodes_test_database):
        """Test get_dataset_info includes required sections."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        assert "basic_info" in result
        assert "experiment_info" in result
        assert "parameters" in result
        assert "metadata" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_basic_info_structure(self, qcodes_test_database):
        """Test basic_info section has correct structure."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        basic = result["basic_info"]

        assert basic["run_id"] == 1
        assert basic["name"] == "run_1"
        assert basic["guid"] == "guid-1"
        assert "completed" in basic
        assert "number_of_results" in basic
        assert basic["number_of_results"] == 10  # We inserted 10 rows

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_experiment_info_structure(self, qcodes_test_database):
        """Test experiment_info section has correct structure."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        exp = result["experiment_info"]

        assert exp["experiment_id"] == 1
        assert exp["name"] == "test_experiment"
        assert exp["sample_name"] == "test_sample"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_parameters_structure(self, qcodes_test_database):
        """Test parameters section is properly structured."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        params = result["parameters"]

        assert "voltage" in params
        assert params["voltage"]["name"] == "voltage"
        assert params["voltage"]["label"] == "Gate Voltage"
        assert params["voltage"]["unit"] == "V"

        assert "current" in params
        assert params["current"]["name"] == "current"
        assert "voltage" in params["current"]["depends_on"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_with_measureit_metadata(self, qcodes_test_database):
        """Test extracting MeasureIt metadata."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        measureit = result["measureit_info"]

        assert measureit is not None
        assert measureit["class"] == "Sweep1D"
        assert measureit["module"] == "MeasureIt"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_with_timestamp(self, qcodes_test_database):
        """Test dataset info includes timestamp."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        basic = result["basic_info"]

        assert "timestamp" in basic
        assert basic["timestamp"] == 1234567890.0
        assert "timestamp_readable" in basic
        datetime.fromisoformat(basic["timestamp_readable"])

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_nonexistent_dataset(self, qcodes_test_database):
        """Test get_dataset_info with nonexistent run_id."""
        result = json.loads(get_dataset_info(999, qcodes_test_database))
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_with_explicit_path(self, qcodes_test_database):
        """Test get_dataset_info with explicit database path."""
        result = json.loads(get_dataset_info(1, qcodes_test_database))
        assert result["database_path"] == qcodes_test_database

    def test_get_dataset_info_without_qcodes(self):
        """Test get_dataset_info returns error when QCodes unavailable."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.database.query_tools.QCODES_AVAILABLE",
            False,
        ):
            result = json.loads(get_dataset_info(1))
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_dataset_info_handles_errors(self, temp_dir):
        """Test get_dataset_info handles errors gracefully."""
        invalid_db = temp_dir / "invalid.db"
        invalid_db.write_text("Not a database")

        result = json.loads(get_dataset_info(1, str(invalid_db)))
        assert "error" in result


class TestGetDatabaseStats:
    """Test get_database_stats functionality."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_returns_valid_json(self, qcodes_test_database):
        """Test get_database_stats returns valid JSON."""
        result = get_database_stats(qcodes_test_database)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_has_required_fields(self, qcodes_test_database):
        """Test get_database_stats includes required fields."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert "database_path" in result
        assert "path_resolved_via" in result
        assert "database_size_readable" in result
        assert "last_modified" in result
        assert "experiment_count" in result
        assert "total_dataset_count" in result
        assert "latest_run_id" in result
        assert "measurement_types" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_nonexistent_database(self, temp_dir):
        """Test stats for nonexistent database."""
        db_path = temp_dir / "nonexistent.db"
        result = json.loads(get_database_stats(str(db_path)))

        assert "error" in result
        assert "error_type" in result
        assert result["error_type"] == "database_not_found"

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_existing_database(self, qcodes_test_database):
        """Test stats for existing database."""
        result = json.loads(get_database_stats(qcodes_test_database))

        assert result["database_size_readable"] is not None
        assert result["last_modified"] is not None

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_experiment_count(self, qcodes_test_database):
        """Test stats includes experiment count."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert result["experiment_count"] == 2

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_dataset_count(self, qcodes_test_database):
        """Test stats includes dataset count."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert result["total_dataset_count"] == 3  # We inserted 3 runs

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_measurement_types(self, qcodes_test_database):
        """Test stats includes measurement type breakdown."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert "measurement_types" in result

        types = result["measurement_types"]
        assert types.get("Sweep1D", 0) >= 1
        assert types.get("Sweep0D", 0) >= 1

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_latest_run_id(self, qcodes_test_database):
        """Test stats includes latest run ID."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert result["latest_run_id"] == 3

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_with_explicit_path(self, qcodes_test_database):
        """Test get_database_stats with explicit database path."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert result["database_path"] == qcodes_test_database

    def test_get_database_stats_without_qcodes(self):
        """Test get_database_stats returns error when QCodes unavailable."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.database.query_tools.QCODES_AVAILABLE",
            False,
        ):
            result = json.loads(get_database_stats())
            assert "error" in result
            assert "QCodes not available" in result["error"]

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_handles_errors(self, temp_dir):
        """Test get_database_stats handles errors gracefully."""
        invalid_db = temp_dir / "invalid.db"
        invalid_db.write_text("Not a database")

        result = json.loads(get_database_stats(str(invalid_db)))
        # Should have count_error or error
        assert "count_error" in result or "error" in result

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_get_database_stats_latest_run_id(self, qcodes_test_database):
        """Test stats includes latest run_id."""
        result = json.loads(get_database_stats(qcodes_test_database))
        assert result["latest_run_id"] == 3  # Highest run_id we inserted


class TestQueryToolsIntegration:
    """Test integration between query tools."""

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_all_tools_use_same_path(self, qcodes_test_database):
        """Test all tools use consistent database path."""
        experiments_result = json.loads(list_experiments(qcodes_test_database))
        stats_result = json.loads(get_database_stats(qcodes_test_database))
        dataset_result = json.loads(get_dataset_info(1, qcodes_test_database))

        assert experiments_result["database_path"] == qcodes_test_database
        assert stats_result["database_path"] == qcodes_test_database
        assert dataset_result["database_path"] == qcodes_test_database

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_all_tools_return_valid_json(self, qcodes_test_database):
        """Test all tools return valid JSON."""
        experiments = list_experiments(qcodes_test_database)
        dataset_info = get_dataset_info(1, qcodes_test_database)
        stats = get_database_stats(qcodes_test_database)

        json.loads(experiments)
        json.loads(dataset_info)
        json.loads(stats)

    def test_all_tools_without_qcodes_consistent(self):
        """Test all tools handle missing QCodes consistently."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.database.query_tools.QCODES_AVAILABLE",
            False,
        ):
            experiments = json.loads(list_experiments())
            dataset_info = json.loads(get_dataset_info(1))
            stats = json.loads(get_database_stats())

            assert "error" in experiments
            assert "error" in dataset_info
            assert "error" in stats

    @pytest.mark.skipif(not QCODES_AVAILABLE, reason="QCodes not available")
    def test_tools_work_with_same_database(self, qcodes_test_database):
        """Test tools work consistently with same database."""
        experiments = json.loads(list_experiments(qcodes_test_database))
        dataset_info = json.loads(get_dataset_info(1, qcodes_test_database))
        stats = json.loads(get_database_stats(qcodes_test_database))

        # All should reference same database
        assert experiments["database_path"] == qcodes_test_database
        assert dataset_info["database_path"] == qcodes_test_database
        assert stats["database_path"] == qcodes_test_database

        # Counts should be consistent
        assert experiments["experiment_count"] == stats["experiment_count"]
        total_runs = sum(
            _count_run_ids(e["run_ids"]) for e in experiments["experiments"]
        )
        assert total_runs == stats["total_dataset_count"]
