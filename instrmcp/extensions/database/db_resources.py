"""
Database resources for providing dynamic database information.

These resources provide real-time information about the current database
state, recent measurements, and extracted measurement patterns.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from qcodes.dataset import experiments, load_by_id
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


def get_current_database_config(database_path: Optional[str] = None) -> str:
    """
    Get current database configuration and connection information.

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

        # Test connection
        try:
            exp_list = experiments()
            config["connection_status"] = "connected"
            config["experiment_count"] = len(exp_list)
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


def get_recent_measurements(
    limit: int = 20, database_path: Optional[str] = None
) -> str:
    """
    Get metadata for recent measurements across all experiments.

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

        # Temporarily set the database location
        original_db_location = qc.config.core.db_location
        qc.config.core.db_location = resolved_path

        result = {
            "database_path": resolved_path,
            "limit": limit,
            "recent_measurements": [],
            "retrieved_at": datetime.now().isoformat(),
        }

        # Find recent datasets by scanning backwards from high run IDs
        all_datasets = []

        # Start from a high run ID and work backwards to find recent measurements
        for run_id in range(1000, 0, -1):
            if len(all_datasets) >= limit * 2:  # Get more than needed for sorting
                break

            try:
                dataset = load_by_id(run_id)

                # Extract MeasureIt metadata if available
                measureit_metadata = None
                measurement_type = "unknown"
                try:
                    if hasattr(dataset, "metadata") and "measureit" in dataset.metadata:
                        measureit_metadata = json.loads(dataset.metadata["measureit"])
                        measurement_type = measureit_metadata.get("class", "unknown")
                except (json.JSONDecodeError, KeyError, AttributeError):
                    pass

                dataset_info = {
                    "run_id": dataset.run_id,
                    "captured_run_id": dataset.captured_run_id,
                    "experiment_name": dataset.exp_name,
                    "sample_name": dataset.sample_name,
                    "name": dataset.name,
                    "completed": dataset.completed,
                    "number_of_results": len(dataset),
                    "parameters": list(dataset.parameters.keys()),
                    "timestamp": None,
                    "timestamp_readable": None,
                    "measurement_type": measurement_type,
                }

                # Try to get timestamp for sorting
                try:
                    if (
                        hasattr(dataset, "run_timestamp_raw")
                        and dataset.run_timestamp_raw
                    ):
                        dataset_info["timestamp"] = dataset.run_timestamp_raw
                        dataset_info["timestamp_readable"] = datetime.fromtimestamp(
                            dataset.run_timestamp_raw
                        ).isoformat()
                except:
                    pass

                all_datasets.append(dataset_info)

            except Exception:
                # Dataset doesn't exist, continue
                continue

        # Sort by timestamp (most recent first), then by run_id for datasets without timestamps
        all_datasets.sort(
            key=lambda x: (x["timestamp"] or 0, x["run_id"]), reverse=True
        )

        # Take the most recent ones
        result["recent_measurements"] = all_datasets[:limit]
        result["total_available"] = len(all_datasets)

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return json.dumps(
            {
                "error": f"Failed to get recent measurements: {str(e)}",
                "recent_measurements": [],
            },
            indent=2,
        )
    finally:
        # Restore original database location
        if "original_db_location" in locals():
            qc.config.core.db_location = original_db_location
