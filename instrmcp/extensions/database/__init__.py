"""
DEPRECATED: Database integration has moved.

This module is kept for backward compatibility.
New location: instrmcp.servers.jupyter_qcodes.options.database
"""

# Re-export from new location for backward compatibility
from instrmcp.servers.jupyter_qcodes.options.database import (
    list_experiments,
    get_dataset_info,
    get_database_stats,
    list_available_databases,
    get_current_database_config,
    get_recent_measurements,
)

__all__ = [
    "list_experiments",
    "get_dataset_info",
    "get_database_stats",
    "list_available_databases",
    "get_current_database_config",
    "get_recent_measurements",
]
