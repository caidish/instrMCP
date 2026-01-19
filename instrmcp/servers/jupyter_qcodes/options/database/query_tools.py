"""
Database query tools for QCodes database interaction.

Provides read-only access to QCodes databases for listing experiments,
querying datasets, and retrieving database statistics.
Rewritten based on databaseExample.ipynb patterns.

Thread Safety Fix:
    This module uses direct SQLite connections instead of QCoDeS's cached
    connections to avoid "SQLite objects created in a thread can only be
    used in that same thread" errors. The MCP server runs in a different
    thread than the Jupyter kernel, so we cannot share QCoDeS's connections.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict, List

try:
    from qcodes.dataset import experiments
    import qcodes as qc

    QCODES_AVAILABLE = True
except ImportError:
    QCODES_AVAILABLE = False

# Regex pattern for valid SQLite table names (alphanumeric and underscore only)
_VALID_TABLE_NAME_PATTERN = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"


@contextmanager
def thread_safe_db_connection(db_path: str):
    """
    Create a fresh SQLite connection for the current thread.

    This avoids the "SQLite objects created in a thread can only be used
    in that same thread" error by creating a new connection each time
    instead of reusing QCoDeS's cached connections.

    This is the canonical thread-safe database connection helper for all
    MCP server database operations. Import this from other modules instead
    of creating ad-hoc connections.

    Args:
        db_path: Path to the SQLite database file

    Yields:
        sqlite3.Connection object with Row factory enabled for dict-like access
    """
    # check_same_thread=False is safe here because:
    # 1. Each connection is created and closed within the same context manager call
    # 2. Connections are not shared or cached across threads
    # 3. This is a read-only operation (no concurrent writes to worry about)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enable dict-like row access
    try:
        yield conn
    finally:
        conn.close()


# Backward compatibility alias (deprecated, use thread_safe_db_connection)
_thread_safe_db_connection = thread_safe_db_connection


def _query_experiments_direct(db_path: str) -> List[Dict[str, Any]]:
    """
    Query experiments directly from SQLite, bypassing QCoDeS connection pool.

    Args:
        db_path: Path to the database file

    Returns:
        List of experiment dictionaries
    """
    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT exp_id, name, sample_name, format_string, start_time, end_time
            FROM experiments
            ORDER BY exp_id
        """)
        return [dict(row) for row in cursor.fetchall()]


def _query_datasets_for_experiment(db_path: str, exp_id: int) -> List[int]:
    """
    Query run IDs for a specific experiment directly from SQLite.

    Args:
        db_path: Path to the database file
        exp_id: Experiment ID

    Returns:
        List of run IDs belonging to this experiment
    """
    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT run_id FROM runs WHERE exp_id = ?
            ORDER BY run_id
        """,
            (exp_id,),
        )
        return [row[0] for row in cursor.fetchall()]


def _query_dataset_info_direct(db_path: str, run_id: int) -> Optional[Dict[str, Any]]:
    """
    Query dataset information directly from SQLite.

    Args:
        db_path: Path to the database file
        run_id: Run ID to query

    Returns:
        Dictionary with dataset info or None if not found
    """
    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get basic run info
        cursor.execute(
            """
            SELECT r.run_id, r.exp_id, r.name, r.result_table_name,
                   r.guid, r.run_timestamp, r.completed_timestamp,
                   r.is_completed, r.captured_run_id,
                   e.name as exp_name, e.sample_name
            FROM runs r
            JOIN experiments e ON r.exp_id = e.exp_id
            WHERE r.run_id = ?
        """,
            (run_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        result = dict(row)

        # Get parameters from layouts table
        # Note: QCodes schema uses 'parameter' column, not 'name'
        cursor.execute(
            """
            SELECT layout_id, parameter as name, label, unit, inferred_from
            FROM layouts
            WHERE run_id = ?
        """,
            (run_id,),
        )
        params_by_id = {}
        result["parameters"] = []
        for r in cursor.fetchall():
            param_dict = dict(r)
            layout_id = param_dict.pop("layout_id")
            params_by_id[layout_id] = param_dict["name"]
            param_dict["depends_on"] = []
            result["parameters"].append(param_dict)

        # Get dependency info from dependencies table
        # dependencies links layout_ids (dependent -> independent)
        cursor.execute(
            """
            SELECT d.dependent, d.independent
            FROM dependencies d
            JOIN layouts l ON d.dependent = l.layout_id
            WHERE l.run_id = ?
        """,
            (run_id,),
        )
        deps = {}
        for row in cursor.fetchall():
            dependent_id = row[0]
            independent_id = row[1]
            dependent_name = params_by_id.get(dependent_id)
            independent_name = params_by_id.get(independent_id)
            if dependent_name and independent_name:
                if dependent_name not in deps:
                    deps[dependent_name] = []
                deps[dependent_name].append(independent_name)

        # Add depends_on info to parameters
        for param in result["parameters"]:
            param["depends_on"] = deps.get(param["name"], [])

        # Get result count
        result_table = result.get("result_table_name")
        if result_table:
            try:
                # Validate table name to prevent SQL injection
                # Table names come from our DB but could be corrupted
                if not re.match(_VALID_TABLE_NAME_PATTERN, result_table):
                    result["number_of_results"] = None
                else:
                    # Safe to use - name validated against pattern
                    # Use double quotes for SQL identifiers (table names)
                    cursor.execute(f'SELECT COUNT(*) FROM "{result_table}"')
                    result["number_of_results"] = cursor.fetchone()[0]
            except Exception:
                result["number_of_results"] = None

        return result


def _query_run_metadata(db_path: str, run_id: int) -> Dict[str, Any]:
    """
    Query metadata for a run from the runs table.

    Args:
        db_path: Path to the database file
        run_id: Run ID

    Returns:
        Dictionary of metadata including measureit data
    """
    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()
        # QCodes stores MeasureIt metadata in 'measureit' column
        cursor.execute(
            """
            SELECT measureit, snapshot FROM runs WHERE run_id = ?
        """,
            (run_id,),
        )
        row = cursor.fetchone()
        result = {}
        if row:
            # Parse measureit metadata
            if row[0]:
                try:
                    result["measureit"] = row[0]  # Keep as string, parsed later
                except Exception:
                    pass
            # Optionally include snapshot (can be large)
            # if row[1]:
            #     result["snapshot"] = row[1]
        return result


def _count_datasets_direct(db_path: str) -> Dict[str, Any]:
    """
    Count datasets and get statistics directly from SQLite.

    Args:
        db_path: Path to the database file

    Returns:
        Dictionary with counts and statistics
    """
    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Count experiments
        cursor.execute("SELECT COUNT(*) FROM experiments")
        exp_count = cursor.fetchone()[0]

        # Count and get max run_id
        cursor.execute("SELECT COUNT(*), MAX(run_id) FROM runs")
        row = cursor.fetchone()
        dataset_count = row[0] if row else 0
        latest_run_id = row[1] if row else 0

        return {
            "experiment_count": exp_count,
            "total_dataset_count": dataset_count,
            "latest_run_id": latest_run_id or 0,
        }


def _count_measurement_types(db_path: str) -> Dict[str, int]:
    """
    Count measurement types from MeasureIt metadata directly from SQLite.

    Args:
        db_path: Path to the database file

    Returns:
        Dictionary mapping measurement type to count
    """
    measurement_types: Dict[str, int] = {}

    with _thread_safe_db_connection(db_path) as conn:
        cursor = conn.cursor()
        # QCodes stores MeasureIt data directly in 'measureit' column
        cursor.execute("SELECT measureit FROM runs")

        for row in cursor.fetchall():
            try:
                if row[0]:
                    # measureit column contains JSON string directly
                    measureit_data = (
                        json.loads(row[0]) if isinstance(row[0], str) else row[0]
                    )
                    mtype = measureit_data.get("class", "unknown")
                    measurement_types[mtype] = measurement_types.get(mtype, 0) + 1
                else:
                    measurement_types["qcodes"] = measurement_types.get("qcodes", 0) + 1
            except (json.JSONDecodeError, TypeError):
                measurement_types["unknown"] = measurement_types.get("unknown", 0) + 1

    return measurement_types


def _get_data_dir_constraint() -> Optional[Path]:
    """
    Get the data directory constraint from environment variable.

    When INSTRMCP_DATA_DIR is set, database resolution is constrained to
    only search within that directory. This prevents fallback to environment
    paths (MeasureIt, QCodes config) and ensures isolation in sandboxed
    environments like Codex.

    Returns:
        Path to data directory if INSTRMCP_DATA_DIR is set, None otherwise.
    """
    import os

    data_dir = os.environ.get("INSTRMCP_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return None


def _safe_mtime(path: Path) -> float:
    """Get a file's modified time, defaulting to 0 on errors."""
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0


def _select_default_database(db_files: list[Path]) -> Optional[Path]:
    """Choose Example_database.db if present; otherwise pick the newest file."""
    if not db_files:
        return None
    example_dbs = [
        db_file for db_file in db_files if db_file.name == "Example_database.db"
    ]
    if example_dbs:
        return max(example_dbs, key=_safe_mtime)
    return max(db_files, key=_safe_mtime)


def _find_nested_databases(base_dir: Path) -> list[Path]:
    """Find database files under nested Databases/ directories."""
    try:
        return list(base_dir.rglob("Databases/*.db"))
    except Exception:
        return []


def resolve_database_path(
    database_path: Optional[str] = None,
    data_dir: Optional[Path] = None,
    scan_nested: bool = False,
) -> tuple[str, dict]:
    """
    Resolve the database path using the following priority:
    1. Provided database_path parameter
    2. MeasureIt get_path("databases") -> Example_database.db (unless data_dir is set)
    3. QCodes default configuration (unless data_dir is set)

    When data_dir is set (explicitly or via INSTRMCP_DATA_DIR environment variable),
    fallback to MeasureIt and QCodes environment paths is DISABLED. This ensures
    database isolation in sandboxed environments.

    This is the canonical database path resolution function. Import this
    function from other modules instead of duplicating the logic.

    Args:
        database_path: Explicit database path
        data_dir: If set, restricts database search to this directory only
                  (no fallback to environment paths). If None, checks
                  INSTRMCP_DATA_DIR environment variable.
        scan_nested: If True, search nested "Databases" directories when
                     resolving a default database.

    Returns:
        tuple: (resolved_path, resolution_info)
            resolved_path: Absolute path to database file
            resolution_info: Dict with 'source', 'available_databases', 'tried_path'

    Raises:
        FileNotFoundError: If database path doesn't exist, with helpful suggestions
    """
    resolution_info = {"source": None, "available_databases": [], "tried_path": None}

    # Check for data_dir constraint from environment if not provided
    if data_dir is None:
        data_dir = _get_data_dir_constraint()

    # Track if we're in constrained mode
    is_constrained = data_dir is not None
    if is_constrained:
        resolution_info["data_dir_constraint"] = str(data_dir)

    # Case 1: Explicit path provided
    if database_path:
        db_path = Path(database_path)
        resolution_info["tried_path"] = str(db_path)

        # If constrained, verify the path is within data_dir
        if is_constrained:
            try:
                # Resolve both paths to absolute for comparison
                abs_db_path = db_path.resolve()
                abs_data_dir = data_dir.resolve()
                if not str(abs_db_path).startswith(str(abs_data_dir)):
                    resolution_info["available_databases"] = _list_available_databases(
                        data_dir, scan_nested=scan_nested
                    )
                    raise FileNotFoundError(
                        f"Database path '{database_path}' is outside the allowed "
                        f"data directory: {data_dir}\n\n"
                        "Available databases in data directory:\n"
                        + _format_available_databases(
                            resolution_info["available_databases"]
                        )
                    )
            except ValueError:
                # Path resolution failed - let it fall through to exists check
                pass

        if db_path.exists():
            resolution_info["source"] = "explicit"
            return str(db_path), resolution_info
        else:
            # Path doesn't exist - provide helpful error
            resolution_info["available_databases"] = _list_available_databases(
                data_dir, scan_nested=scan_nested
            )
            raise FileNotFoundError(
                f"Database not found: {database_path}\n\n"
                "Available databases:\n"
                + _format_available_databases(resolution_info["available_databases"])
                + "\n\nTip: Use database_list_all_available_db() to discover all databases"
            )

    # If constrained to data_dir, only search there - NO environment fallbacks
    if is_constrained:
        # Search for any .db file in data_dir
        if data_dir.exists():
            db_files = list(data_dir.glob("*.db"))
            if db_files:
                selected_db = _select_default_database(db_files)
                if selected_db:
                    if selected_db.name == "Example_database.db":
                        resolution_info["source"] = "data_dir_default"
                    else:
                        resolution_info["source"] = "data_dir_auto"
                    resolution_info["tried_path"] = str(selected_db)
                    return str(selected_db), resolution_info
            if scan_nested:
                nested_db_files = _find_nested_databases(data_dir)
                if nested_db_files:
                    selected_db = _select_default_database(nested_db_files)
                    if selected_db:
                        resolution_info["source"] = "data_dir_nested"
                        resolution_info["tried_path"] = str(selected_db)
                        return str(selected_db), resolution_info

        # No database found in constrained directory
        resolution_info["available_databases"] = _list_available_databases(
            data_dir, scan_nested=scan_nested
        )
        raise FileNotFoundError(
            f"No database found yet in data directory: {data_dir}\n\n"
            "Note: Database resolution is constrained to this directory "
            "(INSTRMCP_DATA_DIR is set).\n\n"
            "Available databases:\n"
            + _format_available_databases(resolution_info["available_databases"])
        )

    # Case 2: Try MeasureIt default (only if not constrained)
    try:
        from measureit import get_path

        db_dir = get_path("databases")
        default_db = db_dir / "Example_database.db"
        resolution_info["tried_path"] = str(default_db)

        if default_db.exists():
            resolution_info["source"] = "measureit_default"
            return str(default_db), resolution_info
    except (ImportError, ValueError, Exception):
        # MeasureIt not available or get_path failed
        pass

    # Optional: Scan nested Databases directories under MeasureIt data dir
    if scan_nested:
        try:
            from measureit import get_data_dir

            data_root = Path(get_data_dir())
            if data_root.exists():
                nested_db_files = _find_nested_databases(data_root)
                if nested_db_files:
                    selected_db = _select_default_database(nested_db_files)
                    if selected_db:
                        resolution_info["source"] = "measureit_nested"
                        resolution_info["tried_path"] = str(selected_db)
                        return str(selected_db), resolution_info
        except Exception:
            pass

    # Case 3: Fall back to QCodes config (only if not constrained)
    qcodes_db = Path(qc.config.core.db_location)
    resolution_info["tried_path"] = str(qcodes_db)

    if qcodes_db.exists():
        resolution_info["source"] = "qcodes_config"
        return str(qcodes_db), resolution_info

    # No database found - provide comprehensive error
    resolution_info["available_databases"] = _list_available_databases(
        scan_nested=scan_nested
    )

    # Build error message with tried paths
    tried_paths = []
    try:
        from measureit import get_path

        db_dir = get_path("databases")
        tried_paths.append(f"  1. MeasureIt default: {db_dir / 'Example_database.db'}")
    except Exception:
        tried_paths.append("  1. MeasureIt default: N/A (MeasureIt not available)")

    tried_paths.append(f"  2. QCodes config: {qcodes_db}")

    raise FileNotFoundError(
        "No database found yet. Searched:\n"
        + "\n".join(tried_paths)
        + "\n\n"
        + "Available databases:\n"
        + _format_available_databases(resolution_info["available_databases"])
    )


def _list_available_databases(
    data_dir: Optional[Path] = None,
    scan_nested: bool = False,
) -> list[dict]:
    """
    List available databases by searching common locations.

    When data_dir is specified, ONLY searches within that directory.
    When data_dir is None, searches MeasureIt and QCodes locations.

    Args:
        data_dir: If set, restricts search to this directory only.
                  If None, uses standard MeasureIt/QCodes locations.
        scan_nested: If True, search nested "Databases" directories.

    Returns:
        List of dicts with 'name', 'path', 'source', 'size_mb', 'accessible'
    """
    databases = []
    seen_paths = set()

    def add_database(db_file: Path, source: str) -> None:
        path_str = str(db_file)
        if path_str in seen_paths:
            return
        try:
            size_mb = round(db_file.stat().st_size / 1024 / 1024, 2)
            accessible = True
        except Exception:
            size_mb = 0
            accessible = False
        databases.append(
            {
                "name": db_file.name,
                "path": path_str,
                "source": source,
                "size_mb": size_mb,
                "accessible": accessible,
            }
        )
        seen_paths.add(path_str)

    # If constrained to data_dir, only search there
    if data_dir is not None:
        if data_dir.exists():
            for db_file in data_dir.glob("*.db"):
                add_database(db_file, "data_dir")
            if scan_nested:
                for db_file in _find_nested_databases(data_dir):
                    add_database(db_file, "data_dir_nested")
        return databases

    # Standard search: Check MeasureIt databases directory
    try:
        from measureit import get_path

        db_dir = get_path("databases")

        if db_dir.exists():
            for db_file in db_dir.glob("*.db"):
                add_database(db_file, "measureit")

        if scan_nested:
            try:
                from measureit import get_data_dir

                data_root = Path(get_data_dir())
                if data_root.exists():
                    for db_file in _find_nested_databases(data_root):
                        add_database(db_file, "measureit_nested")
            except Exception:
                pass
    except (ImportError, ValueError, Exception):
        pass

    # Check QCodes config location
    try:
        qcodes_db = Path(qc.config.core.db_location)
        if qcodes_db.exists():
            add_database(qcodes_db, "qcodes_config")
    except Exception:
        pass

    return databases


def _format_available_databases(databases: list[dict]) -> str:
    """Format database list for error messages."""
    if not databases:
        return (
            "  (none found yet)\n\n"
            "  Tip: Running an experiment will automatically create a database.\n"
            "  See the sweep code template for examples."
        )

    lines = []
    for db in databases:
        lines.append(f"  - {db['name']} ({db['size_mb']} MB) [{db['source']}]")
        lines.append(f"    {db['path']}")

    return "\n".join(lines)


def _format_run_ids_concise(run_ids: list[int]) -> str:
    """Format run IDs as a concise string (e.g., 1,2 or 6-16(11))."""
    if not run_ids:
        return ""
    run_ids_sorted = sorted(run_ids)
    if len(run_ids_sorted) <= 5:
        return ",".join(str(r) for r in run_ids_sorted)
    return f"{run_ids_sorted[0]}-{run_ids_sorted[-1]}({len(run_ids_sorted)})"


def list_experiments(
    database_path: Optional[str] = None,
    scan_nested: bool = False,
) -> str:
    """
    List all experiments in the specified QCodes database.

    Uses direct SQLite queries to avoid thread-safety issues with QCoDeS
    connection pool (the MCP server runs in a different thread than the
    Jupyter kernel).

    Args:
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.
        scan_nested: If True, also search nested "Databases" directories when
            resolving the default database path.

    Returns:
        JSON string containing experiment information including ID, name,
        sample_name, start_time, end_time, and run IDs.
    """
    if not QCODES_AVAILABLE:
        return json.dumps(
            {"error": "QCodes not available", "experiments": []}, indent=2
        )

    try:
        # Resolve database path
        resolved_path, resolution_info = resolve_database_path(
            database_path,
            scan_nested=scan_nested,
        )
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Use direct SQLite queries for thread safety
        exp_rows = _query_experiments_direct(resolved_path)

        result = {
            "database_path": resolved_path,
            "path_resolved_via": resolution_info["source"],
            "experiment_count": len(exp_rows),
            "experiments": [],
        }

        for exp in exp_rows:
            # Get run IDs for this experiment using direct query
            run_ids = _query_datasets_for_experiment(resolved_path, exp["exp_id"])

            exp_info = {
                "experiment_id": exp["exp_id"],
                "name": exp["name"],
                "sample_name": exp["sample_name"],
                "start_time": exp.get("start_time"),
                "end_time": exp.get("end_time"),
                "run_ids": _format_run_ids_concise(run_ids),
            }
            result["experiments"].append(exp_info)

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"error": f"Failed to list experiments: {str(e)}", "experiments": []},
            indent=2,
        )


def get_dataset_info(id: int, database_path: Optional[str] = None) -> str:
    """
    Get detailed information about a specific dataset.

    Uses direct SQLite queries for basic info and metadata to avoid
    thread-safety issues.

    Args:
        id: Dataset run ID to load (e.g., load_by_id(2))
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

    Returns:
        JSON string containing detailed dataset information with MeasureIt metadata
    """
    if not QCODES_AVAILABLE:
        return json.dumps({"error": "QCodes not available"}, indent=2)

    try:
        # Resolve database path
        resolved_path, resolution_info = resolve_database_path(database_path)
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Use direct SQLite query for basic info (thread-safe)
        dataset_info = _query_dataset_info_direct(resolved_path, id)

        if not dataset_info:
            return json.dumps(
                {"error": f"Dataset with run_id={id} not found"},
                indent=2,
            )

        # Get metadata directly from SQLite
        metadata = _query_run_metadata(resolved_path, id)

        # Extract detailed information
        result = {
            "database_path": resolved_path,
            "path_resolved_via": resolution_info["source"],
            "basic_info": {
                "run_id": dataset_info["run_id"],
                "captured_run_id": dataset_info.get("captured_run_id"),
                "name": dataset_info.get("name"),
                "guid": dataset_info.get("guid"),
                "completed": bool(dataset_info.get("is_completed")),
                "number_of_results": dataset_info.get("number_of_results"),
            },
            "experiment_info": {
                "experiment_id": dataset_info["exp_id"],
                "name": dataset_info.get("exp_name"),
                "sample_name": dataset_info.get("sample_name"),
            },
            "parameters": {},
            "metadata": metadata,
            "measureit_info": None,
        }

        # Get parameter information from direct query
        # Note: 'shape' is a runtime QCoDeS attribute not stored in the database
        for param in dataset_info.get("parameters", []):
            param_info = {
                "name": param["name"],
                "type": param.get("type"),
                "label": param.get("label"),
                "unit": param.get("unit"),
                "depends_on": param.get("depends_on"),
                "inferred_from": param.get("inferred_from"),
                "shape": None,  # Not available from database; requires QCoDeS runtime
            }
            result["parameters"][param["name"]] = param_info

        # Extract MeasureIt metadata specifically
        try:
            if "measureit" in metadata:
                measureit_json = metadata["measureit"]
                if isinstance(measureit_json, str):
                    measureit_metadata = json.loads(measureit_json)
                else:
                    measureit_metadata = measureit_json
                result["measureit_info"] = {
                    "class": measureit_metadata.get("class", "unknown"),
                    "module": measureit_metadata.get("module", "unknown"),
                    "attributes": measureit_metadata.get("attributes", {}),
                    "set_param": measureit_metadata.get("set_param"),
                    "set_params": measureit_metadata.get("set_params"),
                    "inner_sweep": measureit_metadata.get("inner_sweep"),
                    "outer_sweep": measureit_metadata.get("outer_sweep"),
                    "follow_params": measureit_metadata.get("follow_params", {}),
                }
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            pass

        # Add timestamp if available
        try:
            run_ts = dataset_info.get("run_timestamp")
            if run_ts:
                result["basic_info"]["timestamp"] = run_ts
                if isinstance(run_ts, (int, float)):
                    result["basic_info"]["timestamp_readable"] = datetime.fromtimestamp(
                        run_ts
                    ).isoformat()
        except Exception:
            pass

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"Failed to get dataset info: {str(e)}"}, indent=2)


def get_database_stats(database_path: Optional[str] = None) -> str:
    """
    Get database statistics and health information.

    Uses direct SQLite queries to avoid thread-safety issues with QCoDeS
    connection pool.

    Args:
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

    Returns:
        JSON string containing database statistics including path, size,
        experiment count, dataset count, and last modified time.
    """
    if not QCODES_AVAILABLE:
        return json.dumps({"error": "QCodes not available"}, indent=2)

    try:
        # Resolve database path
        resolved_path, resolution_info = resolve_database_path(database_path)
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Get database path
        db_path = Path(resolved_path)

        result = {
            "database_path": str(db_path),
            "path_resolved_via": resolution_info["source"],
            "database_size_readable": None,
            "last_modified": None,
            "experiment_count": 0,
            "total_dataset_count": 0,
            "latest_run_id": None,
            "measurement_types": {},
        }

        if db_path.exists():
            # Get file statistics
            stat = db_path.stat()
            size_bytes = stat.st_size
            result["database_size_readable"] = _format_file_size(size_bytes)
            result["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # Get counts using direct SQLite (thread-safe)
            try:
                counts = _count_datasets_direct(resolved_path)
                result["experiment_count"] = counts["experiment_count"]
                result["total_dataset_count"] = counts["total_dataset_count"]
                result["latest_run_id"] = counts["latest_run_id"]

                # Get measurement types from metadata (direct SQLite)
                measurement_types = _count_measurement_types(resolved_path)
                result["measurement_types"] = measurement_types

            except Exception as e:
                result["count_error"] = (
                    f"Could not count experiments/datasets: {str(e)}"
                )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"error": f"Failed to get database stats: {str(e)}"}, indent=2
        )


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def list_available_databases() -> str:
    """
    List all available QCodes databases across common locations.

    Uses direct SQLite queries to avoid thread-safety issues with QCoDeS
    connection pool.

    Searches:
    - MeasureIt databases directory (via measureit.get_path("databases"))
    - QCodes config location

    Returns:
        JSON string with available databases, their locations, and metadata
    """
    if not QCODES_AVAILABLE:
        return json.dumps({"error": "QCodes not available"}, indent=2)

    try:
        databases = _list_available_databases()

        # Try to get experiment counts for each database using direct SQLite
        for db_info in databases:
            try:
                exp_rows = _query_experiments_direct(db_info["path"])
                db_info["experiment_count"] = len(exp_rows)
            except Exception as e:
                db_info["experiment_count"] = None
                db_info["accessible"] = False
                db_info["error"] = str(e)

        # Get MeasureIt config info
        measureit_info = {}
        try:
            from measureit import get_data_dir, get_path

            measureit_info = {
                "data_dir": str(get_data_dir()),
                "databases_dir": str(get_path("databases")),
                "available": True,
            }
        except (ImportError, Exception):
            measureit_info = {"available": False}

        result = {
            "databases": databases,
            "total_count": len(databases),
            "measureit_config": measureit_info,
            "qcodes_default": str(qc.config.core.db_location),
        }

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)
