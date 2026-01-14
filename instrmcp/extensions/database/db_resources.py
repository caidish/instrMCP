"""
Database resources for providing dynamic database information.

These resources provide real-time information about the current database
state, recent measurements, and extracted measurement patterns.

Thread Safety Fix:
    This module uses direct SQLite connections instead of QCoDeS's cached
    connections to avoid "SQLite objects created in a thread can only be
    used in that same thread" errors. The MCP server runs in a different
    thread than the Jupyter kernel, so we cannot share QCoDeS's connections.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import qcodes as qc

    QCODES_AVAILABLE = True
except ImportError:
    QCODES_AVAILABLE = False

# Import the canonical thread-safe connection helper and shared constant
from .query_tools import thread_safe_db_connection, _VALID_TABLE_NAME_PATTERN


def _resolve_database_path(database_path: Optional[str] = None) -> str:
    """
    Resolve the database path using the following priority:
    1. Provided database_path parameter
    2. MeasureItHome environment variable (if set) -> use Example_database.db
    3. QCodes default configuration

    Args:
        database_path: Explicit database path

    Returns:
        Resolved database path
    """
    if database_path:
        return database_path

    # Check if MeasureIt is available and use its default databases
    measureit_home = os.environ.get("MeasureItHome")
    if measureit_home:
        # Default to Example_database.db in MeasureIt/Databases/
        return str(Path(measureit_home) / "Databases" / "Example_database.db")

    # Fall back to QCodes default
    return str(qc.config.core.db_location)


def get_current_database_config(database_path: Optional[str] = None) -> str:
    """
    Get current database configuration and connection information.

    Uses direct SQLite queries to avoid thread-safety issues with QCoDeS
    connection pool (the MCP server runs in a different thread than the
    Jupyter kernel).

    Args:
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

    Returns:
        JSON string containing database path, status, and configuration details.
    """
    if not QCODES_AVAILABLE:
        return json.dumps(
            {"error": "QCodes not available", "status": "unavailable"}, indent=2
        )

    try:
        # Resolve database path
        resolved_path = _resolve_database_path(database_path)

        config = {
            "database_path": resolved_path,
            "database_exists": False,
            "connection_status": "unknown",
            "qcodes_version": qc.__version__,
            "configuration": {},
            "last_checked": datetime.now().isoformat(),
        }

        # Check database existence
        try:
            db_path = Path(resolved_path)
            config["database_exists"] = db_path.exists()

            if db_path.exists():
                config["database_size_bytes"] = db_path.stat().st_size
                config["database_modified"] = datetime.fromtimestamp(
                    db_path.stat().st_mtime
                ).isoformat()
        except Exception as e:
            config["path_check_error"] = str(e)

        # Test connection using direct SQLite (thread-safe)
        try:
            with thread_safe_db_connection(resolved_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM experiments")
                exp_count = cursor.fetchone()[0]
                config["connection_status"] = "connected"
                config["experiment_count"] = exp_count
        except Exception as e:
            config["connection_status"] = "error"
            config["connection_error"] = str(e)

        # Get relevant QCodes configuration
        try:
            config["configuration"] = {
                "db_location": str(qc.config.core.db_location),
                "db_debug": getattr(qc.config.core, "db_debug", False),
                "default_fmt": getattr(
                    qc.config.gui, "default_fmt", "data/{name}_{counter}"
                ),
                "notebook": getattr(qc.config.gui, "notebook", True),
            }
        except Exception as e:
            config["config_error"] = str(e)

        return json.dumps(config, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"error": f"Failed to get database config: {str(e)}", "status": "error"},
            indent=2,
        )


def _get_result_count(cursor, run_id: int) -> Optional[int]:
    """
    Get result count for a run from its result table.

    Args:
        cursor: SQLite cursor from an open connection
        run_id: Run ID to get result count for

    Returns:
        Number of results or None if table doesn't exist/is invalid
    """
    cursor.execute("SELECT result_table_name FROM runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    if not row or not row[0]:
        return None

    table_name = row[0]
    # Validate table name to prevent SQL injection
    if not re.match(_VALID_TABLE_NAME_PATTERN, table_name):
        return None

    try:
        # Use double quotes for SQL identifiers (table names), not single quotes
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        return cursor.fetchone()[0]
    except Exception:
        return None


def get_recent_measurements(
    limit: int = 20, database_path: Optional[str] = None
) -> str:
    """
    Get metadata for recent measurements across all experiments.

    Uses direct SQLite queries with efficient ORDER BY/LIMIT instead of
    scanning run IDs backwards. This is both thread-safe and performant.

    Args:
        limit: Maximum number of recent measurements to return
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

    Returns:
        JSON string containing recent measurement metadata
    """
    if not QCODES_AVAILABLE:
        return json.dumps(
            {"error": "QCodes not available", "recent_measurements": []}, indent=2
        )

    try:
        # Resolve database path
        resolved_path = _resolve_database_path(database_path)

        result = {
            "database_path": resolved_path,
            "limit": limit,
            "recent_measurements": [],
            "retrieved_at": datetime.now().isoformat(),
        }

        with thread_safe_db_connection(resolved_path) as conn:
            cursor = conn.cursor()

            # Get recent runs directly from SQLite with efficient query
            # Fetch more than needed to account for any filtering
            cursor.execute(
                """
                SELECT r.run_id, r.captured_run_id, r.exp_id, r.name,
                       r.is_completed, r.run_timestamp, r.measureit,
                       r.run_description, r.result_table_name,
                       e.name as exp_name, e.sample_name
                FROM runs r
                JOIN experiments e ON r.exp_id = e.exp_id
                ORDER BY r.run_id DESC
                LIMIT ?
            """,
                (limit * 2,),
            )

            for row in cursor.fetchall():
                row_dict = dict(row)

                # Parse MeasureIt metadata for measurement type
                measurement_type = "qcodes"
                if row_dict.get("measureit"):
                    try:
                        measureit_data = json.loads(row_dict["measureit"])
                        measurement_type = measureit_data.get("class", "unknown")
                    except json.JSONDecodeError:
                        measurement_type = "unknown"

                # Parse run_description for parameter list
                parameters = []
                if row_dict.get("run_description"):
                    try:
                        desc = json.loads(row_dict["run_description"])
                        paramspecs = desc.get("interdependencies", {}).get(
                            "paramspecs", []
                        )
                        parameters = [p.get("name", "") for p in paramspecs]
                    except json.JSONDecodeError:
                        pass

                # Get result count from result table
                result_count = _get_result_count(cursor, row_dict["run_id"])

                dataset_info = {
                    "run_id": row_dict["run_id"],
                    "captured_run_id": row_dict.get("captured_run_id"),
                    "experiment_name": row_dict.get("exp_name"),
                    "sample_name": row_dict.get("sample_name"),
                    "name": row_dict.get("name"),
                    "completed": bool(row_dict.get("is_completed")),
                    "number_of_results": result_count,
                    "parameters": parameters,
                    "timestamp": row_dict.get("run_timestamp"),
                    "timestamp_readable": None,
                    "measurement_type": measurement_type,
                }

                # Format timestamp
                if dataset_info["timestamp"]:
                    try:
                        dataset_info["timestamp_readable"] = datetime.fromtimestamp(
                            dataset_info["timestamp"]
                        ).isoformat()
                    except (ValueError, TypeError):
                        pass

                result["recent_measurements"].append(dataset_info)

        # Sort by timestamp and take limit
        result["recent_measurements"].sort(
            key=lambda x: (x["timestamp"] or 0, x["run_id"]), reverse=True
        )
        # Store count before truncating to reflect actual available count
        result["total_available"] = len(result["recent_measurements"])
        result["recent_measurements"] = result["recent_measurements"][:limit]

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {
                "error": f"Failed to get recent measurements: {str(e)}",
                "recent_measurements": [],
            },
            indent=2,
        )
