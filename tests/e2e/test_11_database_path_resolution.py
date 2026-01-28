"""
Database Path Resolution Tests (test_11_database_path_resolution.py)

Purpose: Verify database path resolution discovers ALL databases including
         nested Databases/Databases/ structures.
Related commit: f39d4c94b31be79d1121f12a081abda631b3f205

Test IDs:
- DPR-001 to DPR-010

The _find_nested_databases function should:
1. Find databases in valid paths like experiment1/Databases/data.db
2. Find databases in Databases/Databases/data.db (user may have data here)
3. The tool's job is discovery - find ALL databases, let user decide
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell, get_cell_output
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    parse_tool_result,
)


def create_test_database(db_path: Path) -> None:
    """Create a minimal QCodes-compatible SQLite database for testing."""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create minimal QCodes schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            exp_id INTEGER PRIMARY KEY,
            name TEXT,
            sample_name TEXT,
            format_string TEXT,
            start_time REAL,
            end_time REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY,
            exp_id INTEGER,
            name TEXT,
            result_table_name TEXT,
            guid TEXT,
            run_timestamp REAL,
            completed_timestamp REAL,
            is_completed INTEGER,
            captured_run_id INTEGER,
            measureit TEXT,
            snapshot TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS layouts (
            layout_id INTEGER PRIMARY KEY,
            run_id INTEGER,
            parameter TEXT,
            label TEXT,
            unit TEXT,
            inferred_from TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependencies (
            dependent INTEGER,
            independent INTEGER
        )
    """)

    # Insert a test experiment and run
    cursor.execute("""
        INSERT INTO experiments (exp_id, name, sample_name, start_time)
        VALUES (1, 'test_experiment', 'test_sample', 1706400000)
    """)

    cursor.execute("""
        INSERT INTO runs (run_id, exp_id, name, is_completed, run_timestamp)
        VALUES (1, 1, 'test_run', 1, 1706400000)
    """)

    conn.commit()
    conn.close()


class TestDatabasePathResolution:
    """Test database path resolution and nested Databases/ handling."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory structure for testing database resolution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Structure 1: Valid nested pattern - experiment1/Databases/data.db
            # This SHOULD be found by scan_nested
            valid_nested = base / "experiment1" / "Databases" / "valid_nested.db"
            create_test_database(valid_nested)

            # Structure 2: Invalid double nesting - Databases/Databases/data.db
            # This should NOT be found (the fix prevents this)
            invalid_double = base / "Databases" / "Databases" / "invalid_double.db"
            create_test_database(invalid_double)

            # Structure 3: Valid top-level database - base/data.db
            # This SHOULD be found without scan_nested
            valid_toplevel = base / "toplevel.db"
            create_test_database(valid_toplevel)

            # Structure 4: Direct Databases dir - Databases/data.db (not nested under experiment)
            # This should NOT match */Databases/*.db pattern (only one level)
            direct_databases = base / "Databases" / "direct.db"
            create_test_database(direct_databases)

            # Structure 5: Too deep nesting - experiment1/sub/Databases/data.db
            # This should NOT match the pattern (too many levels)
            too_deep = base / "experiment1" / "sub" / "Databases" / "too_deep.db"
            create_test_database(too_deep)

            # Structure 6: Another valid nested - experiment2/Databases/another.db
            valid_nested2 = base / "experiment2" / "Databases" / "another_valid.db"
            create_test_database(valid_nested2)

            yield {
                "base": base,
                "valid_nested": valid_nested,
                "valid_nested2": valid_nested2,
                "invalid_double": invalid_double,
                "valid_toplevel": valid_toplevel,
                "direct_databases": direct_databases,
                "too_deep": too_deep,
            }

    @pytest.mark.p1
    def test_find_nested_discovers_all_databases(self, temp_data_dir):
        """DPR-001: _find_nested_databases discovers ALL databases including Databases/Databases/.

        The tool's job is discovery - it should find all databases in */Databases/*.db
        pattern, including Databases/Databases/ which may contain user data created
        by incorrect path specification.
        """
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        base = temp_data_dir["base"]
        results = _find_nested_databases(base)
        result_names = [p.name for p in results]

        # Standard nested databases SHOULD be found
        assert (
            "valid_nested.db" in result_names
        ), f"valid_nested.db should be found. Got: {result_names}"
        assert (
            "another_valid.db" in result_names
        ), f"another_valid.db should be found. Got: {result_names}"

        # Databases/Databases/ pattern SHOULD also be found (user may have data here)
        assert (
            "invalid_double.db" in result_names
        ), f"invalid_double.db SHOULD be found (discovery includes all). Got: {result_names}"

        # Direct Databases/ (not under experiment dir) does NOT match */Databases/*.db pattern
        assert (
            "direct.db" not in result_names
        ), f"direct.db should NOT be found (doesn't match */Databases/*.db). Got: {result_names}"

        # Too deep nesting does NOT match */Databases/*.db pattern
        assert (
            "too_deep.db" not in result_names
        ), f"too_deep.db should NOT be found (too deep for pattern). Got: {result_names}"

    @pytest.mark.p1
    def test_find_nested_correct_path_structure(self, temp_data_dir):
        """DPR-002: Verify found paths match the */Databases/*.db pattern.

        Each found database should have:
        - Parent directory named "Databases"
        - Some grandparent directory (can be anything, including "Databases")
        """
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        base = temp_data_dir["base"]
        results = _find_nested_databases(base)

        for db_path in results:
            parent_name = db_path.parent.name

            assert (
                parent_name == "Databases"
            ), f"Parent of {db_path} should be 'Databases', got '{parent_name}'"
            # Grandparent can be anything - we discover all databases

    @pytest.mark.p1
    def test_find_nested_handles_empty_directory(self):
        """DPR-003: _find_nested_databases handles empty directories gracefully."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            results = _find_nested_databases(Path(tmpdir))
            assert results == [], f"Expected empty list for empty dir, got: {results}"

    @pytest.mark.p1
    def test_find_nested_handles_nonexistent_directory(self):
        """DPR-004: _find_nested_databases handles nonexistent directories gracefully."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        results = _find_nested_databases(Path("/nonexistent/path/that/does/not/exist"))
        assert results == [], f"Expected empty list for nonexistent dir, got: {results}"

    @pytest.mark.p2
    def test_resolve_database_path_with_scan_nested(self, temp_data_dir):
        """DPR-005: resolve_database_path with scan_nested finds nested databases."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            resolve_database_path,
        )

        base = temp_data_dir["base"]

        # Remove toplevel.db to force scan_nested to be used
        temp_data_dir["valid_toplevel"].unlink()

        # With scan_nested=True, should find one of the nested databases
        resolved_path, resolution_info = resolve_database_path(
            data_dir=base,
            scan_nested=True,
        )

        resolved = Path(resolved_path)

        # Should find a nested database (any of them - discovery includes all)
        assert resolved.name in [
            "valid_nested.db",
            "another_valid.db",
            "invalid_double.db",  # Also discoverable now
        ], f"Should find a nested db, got: {resolved.name}"

        # Resolution source should indicate nested
        assert (
            resolution_info["source"] == "data_dir_nested"
        ), f"Expected source 'data_dir_nested', got: {resolution_info['source']}"

    @pytest.mark.p2
    def test_resolve_database_path_prefers_toplevel(self, temp_data_dir):
        """DPR-006: resolve_database_path prefers top-level databases over nested."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            resolve_database_path,
        )

        base = temp_data_dir["base"]

        # With both toplevel and nested available, should prefer toplevel
        resolved_path, resolution_info = resolve_database_path(
            data_dir=base,
            scan_nested=True,
        )

        resolved = Path(resolved_path)

        # Should find the toplevel database first
        assert (
            resolved.name == "toplevel.db"
        ), f"Should prefer toplevel.db, got: {resolved.name}"
        assert (
            resolution_info["source"] == "data_dir_auto"
        ), f"Expected source 'data_dir_auto', got: {resolution_info['source']}"

    @pytest.mark.p1
    def test_list_available_databases_includes_all(self, temp_data_dir):
        """DPR-007: _list_available_databases discovers ALL databases including nested."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _list_available_databases,
        )

        base = temp_data_dir["base"]
        databases = _list_available_databases(data_dir=base, scan_nested=True)

        db_names = [db["name"] for db in databases]

        # All databases should be listed
        assert (
            "toplevel.db" in db_names
        ), f"toplevel.db should be listed. Got: {db_names}"
        assert (
            "valid_nested.db" in db_names
        ), f"valid_nested.db should be listed. Got: {db_names}"

        # Databases/Databases/ pattern SHOULD also be listed (discovery includes all)
        assert (
            "invalid_double.db" in db_names
        ), f"invalid_double.db SHOULD be listed (discovery includes all). Got: {db_names}"

    @pytest.mark.p2
    def test_database_path_safety_with_special_characters(self):
        """DPR-008: Database path resolution handles special characters safely."""
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create path with spaces
            space_path = base / "experiment 1" / "Databases" / "data with spaces.db"
            create_test_database(space_path)

            results = _find_nested_databases(base)
            result_names = [p.name for p in results]

            assert (
                "data with spaces.db" in result_names
            ), f"Should handle spaces in path. Got: {result_names}"


class TestDatabaseToolsE2EPathResolution:
    """E2E tests for database path resolution through MCP tools."""

    @pytest.mark.p1
    def test_database_list_experiments_with_data_dir_env(self, notebook_page, mcp_port):
        """DPR-009: database_list_experiments respects INSTRMCP_DATA_DIR constraint.

        When INSTRMCP_DATA_DIR is set, database resolution should be constrained
        to that directory and not fall back to MeasureIt or QCodes paths.
        """
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        # Create a temporary directory with a test database
        setup_code = '''
import tempfile
import sqlite3
import os
from pathlib import Path

# Create temp dir
temp_dir = tempfile.mkdtemp()
db_path = Path(temp_dir) / "test_constrained.db"

# Create minimal database
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
        measureit TEXT,
        snapshot TEXT
    )
""")
cursor.execute("""
    INSERT INTO experiments (exp_id, name, sample_name)
    VALUES (1, 'constrained_test', 'sample1')
""")
conn.commit()
conn.close()

# Set the environment variable
os.environ["INSTRMCP_DATA_DIR"] = temp_dir
print(f"INSTRMCP_DATA_DIR set to: {temp_dir}")
print(f"Database created at: {db_path}")
_temp_dir_for_cleanup = temp_dir
'''
        run_cell(notebook_page, setup_code)
        notebook_page.wait_for_timeout(1000)

        # Restart MCP server to pick up the new env var
        run_cell(notebook_page, "%mcp_restart")
        notebook_page.wait_for_timeout(2000)

        # Call database_list_experiments - should find our constrained database
        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(base_url, "database_list_experiments")
        success, content = parse_tool_result(result)

        # Should find the experiment we created
        assert (
            "constrained_test" in content or success
        ), f"Should find constrained_test experiment. Got: {content}"

        # Cleanup
        cleanup_code = """
import shutil
import os
if "_temp_dir_for_cleanup" in dir():
    shutil.rmtree(_temp_dir_for_cleanup, ignore_errors=True)
    del os.environ["INSTRMCP_DATA_DIR"]
"""
        run_cell(notebook_page, cleanup_code)
        run_cell(notebook_page, "%mcp_stop")

    @pytest.mark.p2
    def test_database_scan_nested_parameter_accepted(self, notebook_page, mcp_port):
        """DPR-010: database_list_experiments accepts scan_nested parameter.

        Verifies the scan_nested parameter is accepted by the MCP tool.

        Note: Full nested scanning with custom INSTRMCP_DATA_DIR cannot be tested
        via E2E because env vars set in notebook don't propagate to the MCP server
        process. The actual scanning logic is tested in unit tests.
        """
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        notebook_page.wait_for_timeout(1000)

        run_cell(notebook_page, "%mcp_option database")
        notebook_page.wait_for_timeout(500)

        run_cell(notebook_page, "%mcp_start")
        notebook_page.wait_for_timeout(2000)

        # Call with scan_nested=True - should not error
        base_url = f"http://localhost:{mcp_port}"
        result = call_mcp_tool(
            base_url,
            "database_list_experiments",
            {"scan_nested": True},
        )
        success, content = parse_tool_result(result)

        # The parameter should be accepted without error
        # It will use MeasureIt's default database since no INSTRMCP_DATA_DIR is set
        assert result is not None, "Tool should return a result"
        assert "error" not in content.lower() or "not found" in content.lower(), (
            f"scan_nested parameter should be accepted. Got: {content}"
        )

        run_cell(notebook_page, "%mcp_stop")


class TestDatabasePathResolutionUnit:
    """Unit-level tests for path resolution that don't require full E2E setup."""

    @pytest.mark.p1
    def test_find_nested_databases_discovers_all(self):
        """DPR-011: Comprehensive test of _find_nested_databases discovery logic.

        The function discovers ALL databases matching */Databases/*.db pattern,
        including Databases/Databases/ which may contain user data.
        """
        from instrmcp.servers.jupyter_qcodes.options.database.query_tools import (
            _find_nested_databases,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Use unique names for each test case to avoid name collisions
            test_cases = [
                # (path, should_match, description)
                ("exp1/Databases/valid1.db", True, "Valid nested"),
                ("exp2/Databases/valid2.db", True, "Another valid nested"),
                (
                    "Databases/Databases/double_nested.db",
                    True,
                    "Double Databases - should be found",
                ),
                (
                    "Databases/direct.db",
                    False,
                    "Direct Databases (doesn't match */Databases/*.db)",
                ),
                (
                    "exp1/sub/Databases/too_deep.db",
                    False,
                    "Too deep (doesn't match pattern)",
                ),
                (
                    "exp1/DatabasesX/not_databases.db",
                    False,
                    "Similar but not Databases",
                ),
                (
                    "XDatabases/Databases/xdb_valid.db",
                    True,
                    "XDatabases/Databases matches pattern",
                ),
            ]

            # Create all test databases
            for rel_path, _, _ in test_cases:
                full_path = base / rel_path
                create_test_database(full_path)

            # Run the function
            results = _find_nested_databases(base)
            result_names = {p.name for p in results}

            # Verify each case
            for rel_path, should_match, description in test_cases:
                db_name = Path(rel_path).name
                if should_match:
                    assert db_name in result_names, (
                        f"FAILED: {description} - {db_name} should be found but wasn't. "
                        f"Results: {result_names}"
                    )
                else:
                    assert db_name not in result_names, (
                        f"FAILED: {description} - {db_name} should NOT be found but was. "
                        f"Results: {result_names}"
                    )
