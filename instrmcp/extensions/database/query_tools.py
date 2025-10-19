"""
Database query tools for QCodes database interaction.

Provides read-only access to QCodes databases for listing experiments,
querying datasets, and retrieving database statistics.
Rewritten based on databaseExample.ipynb patterns.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from qcodes.dataset import experiments, load_by_id
    import qcodes as qc

    QCODES_AVAILABLE = True
except ImportError:
    QCODES_AVAILABLE = False


def _resolve_database_path(database_path: Optional[str] = None) -> tuple[str, dict]:
    """
    Resolve the database path using the following priority:
    1. Provided database_path parameter
    2. MeasureIt get_path("databases") -> Example_database.db
    3. QCodes default configuration

    Args:
        database_path: Explicit database path

    Returns:
        tuple: (resolved_path, resolution_info)
            resolved_path: Absolute path to database file
            resolution_info: Dict with 'source', 'available_databases', 'tried_path'

    Raises:
        FileNotFoundError: If database path doesn't exist, with helpful suggestions
    """
    resolution_info = {"source": None, "available_databases": [], "tried_path": None}

    # Case 1: Explicit path provided
    if database_path:
        db_path = Path(database_path)
        resolution_info["tried_path"] = str(db_path)

        if db_path.exists():
            resolution_info["source"] = "explicit"
            return str(db_path), resolution_info
        else:
            # Path doesn't exist - provide helpful error
            resolution_info["available_databases"] = _list_available_databases()
            raise FileNotFoundError(
                f"Database not found: {database_path}\n\n"
                "Available databases:\n"
                + _format_available_databases(resolution_info["available_databases"])
                + "\n\nTip: Use database_list_available() to discover all databases"
            )

    # Case 2: Try MeasureIt default
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

    # Case 3: Fall back to QCodes config
    qcodes_db = Path(qc.config.core.db_location)
    resolution_info["tried_path"] = str(qcodes_db)

    if qcodes_db.exists():
        resolution_info["source"] = "qcodes_config"
        return str(qcodes_db), resolution_info

    # No database found - provide comprehensive error
    resolution_info["available_databases"] = _list_available_databases()

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
        "No database found. Tried:\n"
        + "\n".join(tried_paths)
        + "\n\n"
        + "Available databases:\n"
        + _format_available_databases(resolution_info["available_databases"])
        + "\n\nTip: Set MeasureItHome environment variable or provide explicit path"
    )


def _list_available_databases() -> list[dict]:
    """
    List available databases by searching common locations.

    Returns:
        List of dicts with 'name', 'path', 'source', 'size_mb', 'accessible'
    """
    databases = []

    # Check MeasureIt databases directory
    try:
        from measureit import get_path

        db_dir = get_path("databases")

        if db_dir.exists():
            for db_file in db_dir.glob("*.db"):
                databases.append(
                    {
                        "name": db_file.name,
                        "path": str(db_file),
                        "source": "measureit",
                        "size_mb": round(db_file.stat().st_size / 1024 / 1024, 2),
                        "accessible": True,
                    }
                )
    except (ImportError, ValueError, Exception):
        pass

    # Check QCodes config location
    try:
        qcodes_db = Path(qc.config.core.db_location)
        if qcodes_db.exists():
            databases.append(
                {
                    "name": qcodes_db.name,
                    "path": str(qcodes_db),
                    "source": "qcodes_config",
                    "size_mb": round(qcodes_db.stat().st_size / 1024 / 1024, 2),
                    "accessible": True,
                }
            )
    except Exception:
        pass

    return databases


def _format_available_databases(databases: list[dict]) -> str:
    """Format database list for error messages."""
    if not databases:
        return "  (none found)"

    lines = []
    for db in databases:
        lines.append(f"  - {db['name']} ({db['size_mb']} MB) [{db['source']}]")
        lines.append(f"    {db['path']}")

    return "\n".join(lines)


def list_experiments(database_path: Optional[str] = None) -> str:
    """
    List all experiments in the specified QCodes database.

    Args:
        database_path: Path to database file. If None, uses MeasureIt default or QCodes config.

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
        resolved_path, resolution_info = _resolve_database_path(database_path)
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Get all experiments from specified database
        exp_list = experiments()

        result = {
            "database_path": resolved_path,
            "path_resolved_via": resolution_info["source"],
            "experiment_count": len(exp_list),
            "experiments": [],
        }

        for exp in exp_list:
            # Get run IDs for this experiment
            run_ids = []
            try:
                # Get all datasets in this experiment by querying the database
                # We'll iterate through known run IDs to find which belong to this experiment
                for dataset_id in range(1, 1000):  # Check first 1000 run IDs
                    try:
                        ds = load_by_id(dataset_id)
                        if ds.exp_id == exp.exp_id:
                            run_ids.append(dataset_id)
                    except Exception:
                        continue
                    # Stop if we haven't found any for a while
                    if len(run_ids) == 0 and dataset_id > 100:
                        break
                    if dataset_id - max(run_ids, default=0) > 50:
                        break
            except Exception:
                pass

            exp_info = {
                "experiment_id": exp.exp_id,
                "name": exp.name,
                "sample_name": exp.sample_name,
                "start_time": getattr(exp, "start_time", None),
                "end_time": getattr(exp, "end_time", None),
                "run_ids": sorted(run_ids),
                "dataset_count": len(run_ids),
                "format_string": getattr(exp, "format_string", None),
            }
            result["experiments"].append(exp_info)

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"error": f"Failed to list experiments: {str(e)}", "experiments": []},
            indent=2,
        )
    finally:
        # Restore original database location
        if "original_db_location" in locals():
            qc.config.core.db_location = original_db_location


def get_dataset_info(id: int, database_path: Optional[str] = None) -> str:
    """
    Get detailed information about a specific dataset.

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
        resolved_path, resolution_info = _resolve_database_path(database_path)
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Load dataset by ID (following databaseExample pattern)
        dataset = load_by_id(id)

        # Extract detailed information
        result = {
            "database_path": resolved_path,
            "path_resolved_via": resolution_info["source"],
            "basic_info": {
                "run_id": dataset.run_id,
                "captured_run_id": dataset.captured_run_id,
                "name": dataset.name,
                "guid": str(dataset.guid),
                "completed": dataset.completed,
                "number_of_results": len(dataset),
            },
            "experiment_info": {
                "experiment_id": dataset.exp_id,
                "name": dataset.exp_name,
                "sample_name": dataset.sample_name,
            },
            "parameters": {},
            "metadata": {},
            "measureit_info": None,
            "parameter_data": None,
        }

        # Get parameter information
        try:
            if hasattr(dataset.parameters, "items"):
                for param_name, param_spec in dataset.parameters.items():
                    param_info = {
                        "name": param_spec.name,
                        "type": param_spec.type,
                        "label": param_spec.label,
                        "unit": param_spec.unit,
                        "depends_on": param_spec.depends_on,
                        "shape": getattr(param_spec, "shape", None),
                    }
                    result["parameters"][param_name] = param_info
            else:
                # Parameters is a string (comma-separated parameter names)
                param_names = str(dataset.parameters).split(",")
                for param_name in param_names:
                    result["parameters"][param_name.strip()] = {
                        "name": param_name.strip()
                    }
        except Exception as e:
            result["parameters_error"] = str(e)

        # Get all metadata
        try:
            if hasattr(dataset, "metadata"):
                if hasattr(dataset.metadata, "items"):
                    result["metadata"] = dict(dataset.metadata)
                else:
                    result["metadata"] = {"raw": str(dataset.metadata)}
        except Exception:
            pass

        # Extract MeasureIt metadata specifically
        try:
            if hasattr(dataset, "metadata") and "measureit" in dataset.metadata:
                measureit_json = dataset.metadata["measureit"]
                measureit_metadata = json.loads(measureit_json)
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
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass

        # Get actual parameter data (limited to avoid huge responses)
        try:
            param_data = dataset.get_parameter_data()
            # Limit data size - only include first/last few points for large datasets
            limited_data = {}
            for param_name, param_dict in param_data.items():
                limited_data[param_name] = {}
                for setpoint_name, values in param_dict.items():
                    if len(values) > 20:  # If more than 20 points, show first/last 10
                        limited_data[param_name][setpoint_name] = {
                            "first_10": (
                                values[:10].tolist()
                                if hasattr(values, "tolist")
                                else list(values[:10])
                            ),
                            "last_10": (
                                values[-10:].tolist()
                                if hasattr(values, "tolist")
                                else list(values[-10:])
                            ),
                            "total_points": len(values),
                            "data_truncated": True,
                        }
                    else:
                        limited_data[param_name][setpoint_name] = {
                            "data": (
                                values.tolist()
                                if hasattr(values, "tolist")
                                else list(values)
                            ),
                            "total_points": len(values),
                            "data_truncated": False,
                        }
            result["parameter_data"] = limited_data
        except Exception as e:
            result["parameter_data_error"] = str(e)

        # Add timestamp if available
        try:
            if hasattr(dataset, "run_timestamp_raw") and dataset.run_timestamp_raw:
                result["basic_info"]["timestamp"] = dataset.run_timestamp_raw
                result["basic_info"]["timestamp_readable"] = datetime.fromtimestamp(
                    dataset.run_timestamp_raw
                ).isoformat()
        except Exception:
            pass

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps({"error": f"Failed to get dataset info: {str(e)}"}, indent=2)
    finally:
        # Restore original database location
        if "original_db_location" in locals():
            qc.config.core.db_location = original_db_location


def get_database_stats(database_path: Optional[str] = None) -> str:
    """
    Get database statistics and health information.

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
        resolved_path, resolution_info = _resolve_database_path(database_path)
    except FileNotFoundError as e:
        # Database path not found - return error with details
        return json.dumps(
            {"error": str(e), "error_type": "database_not_found"},
            indent=2,
        )

    try:
        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Get database path
        db_path = Path(resolved_path)

        result = {
            "database_path": str(db_path),
            "path_resolved_via": resolution_info["source"],
            "database_exists": db_path.exists(),
            "database_size_bytes": None,
            "database_size_readable": None,
            "last_modified": None,
            "experiment_count": 0,
            "total_dataset_count": 0,
            "qcodes_version": qc.__version__,
            "latest_run_id": None,
            "measurement_types": {},
        }

        if db_path.exists():
            # Get file statistics
            stat = db_path.stat()
            size_bytes = stat.st_size
            result["database_size_bytes"] = size_bytes
            result["database_size_readable"] = _format_file_size(size_bytes)
            result["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

            # Get experiment and dataset counts
            try:
                exp_list = experiments()
                result["experiment_count"] = len(exp_list)

                experiment_details = []
                measurement_types = {}
                latest_run_id = 0
                total_datasets = 0

                # Count datasets by finding the highest run ID
                for test_run_id in range(1, 1000):
                    try:
                        dataset = load_by_id(test_run_id)
                        latest_run_id = max(latest_run_id, test_run_id)
                        total_datasets += 1

                        # Count measurement types from MeasureIt metadata
                        try:
                            if (
                                hasattr(dataset, "metadata")
                                and "measureit" in dataset.metadata
                            ):
                                measureit_metadata = json.loads(
                                    dataset.metadata["measureit"]
                                )
                                mtype = measureit_metadata.get("class", "unknown")
                                measurement_types[mtype] = (
                                    measurement_types.get(mtype, 0) + 1
                                )
                            else:
                                measurement_types["qcodes"] = (
                                    measurement_types.get("qcodes", 0) + 1
                                )
                        except Exception:
                            measurement_types["unknown"] = (
                                measurement_types.get("unknown", 0) + 1
                            )
                    except Exception:
                        continue

                result["total_dataset_count"] = total_datasets
                result["latest_run_id"] = latest_run_id
                result["measurement_types"] = measurement_types

                # Get experiment details
                for exp in exp_list:
                    exp_detail = {
                        "experiment_id": exp.exp_id,
                        "name": exp.name,
                        "sample_name": exp.sample_name,
                        "start_time": getattr(exp, "start_time", None),
                        "end_time": getattr(exp, "end_time", None),
                    }
                    experiment_details.append(exp_detail)

                result["experiment_details"] = experiment_details

            except Exception as e:
                result["count_error"] = (
                    f"Could not count experiments/datasets: {str(e)}"
                )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {"error": f"Failed to get database stats: {str(e)}"}, indent=2
        )
    finally:
        # Restore original database location
        if "original_db_location" in locals():
            qc.config.core.db_location = original_db_location


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

        # Try to get experiment counts for each database
        for db_info in databases:
            try:
                # Temporarily set database location
                original_db_location = qc.config.core.db_location
                qc.config.core.db_location = db_info["path"]

                exp_list = experiments()
                db_info["experiment_count"] = len(exp_list)

                # Restore original location
                qc.config.core.db_location = original_db_location

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
