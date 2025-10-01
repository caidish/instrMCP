"""
Database query tools for QCodes database interaction.

Provides read-only access to QCodes databases for listing experiments,
querying datasets, and retrieving database statistics.
Rewritten based on databaseExample.ipynb patterns.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from qcodes.dataset import experiments, load_by_id, load_by_guid, load_by_run_spec
    import qcodes as qc

    QCODES_AVAILABLE = True
except ImportError:
    QCODES_AVAILABLE = False


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
        resolved_path = _resolve_database_path(database_path)

        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Get all experiments from specified database
        exp_list = experiments()

        result = {
            "database_path": resolved_path,
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
                    except:
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
        resolved_path = _resolve_database_path(database_path)

        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Load dataset by ID (following databaseExample pattern)
        dataset = load_by_id(id)

        # Extract detailed information
        result = {
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
        except:
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
        except:
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
        resolved_path = _resolve_database_path(database_path)

        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        # Get database path
        db_path = Path(resolved_path)

        result = {
            "database_path": str(db_path),
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
                        except:
                            measurement_types["unknown"] = (
                                measurement_types.get("unknown", 0) + 1
                            )
                    except:
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
