"""
QCoDeS database integration for the Jupyter MCP server.

Provides experiment and dataset query tools.
Enable with: %mcp_option add database
"""

from .query_tools import (
    list_experiments,
    get_dataset_info,
    get_database_stats,
    list_available_databases,
    thread_safe_db_connection,
)

from .resources import get_current_database_config, get_recent_measurements
from .tools import DatabaseToolRegistrar

__all__ = [
    # Query tools
    "list_experiments",
    "get_dataset_info",
    "get_database_stats",
    "list_available_databases",
    "thread_safe_db_connection",
    # Resources
    "get_current_database_config",
    "get_recent_measurements",
    # Tool registrar
    "DatabaseToolRegistrar",
]
