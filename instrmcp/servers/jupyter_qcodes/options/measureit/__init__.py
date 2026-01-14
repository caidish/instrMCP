"""
MeasureIt integration for the Jupyter MCP server.

Provides sweep monitoring, control tools, and code templates.
Enable with: %mcp_option add measureit
"""

from .templates import (
    get_sweep0d_template,
    get_sweep1d_template,
    get_sweep2d_template,
    get_simulsweep_template,
    get_sweepqueue_template,
    get_common_patterns_template,
    get_measureit_code_examples,
    # Data access templates (for loading saved data)
    get_database_access0d_template,
    get_database_access1d_template,
    get_database_access2d_template,
    get_database_access_simulsweep_template,
    get_database_access_sweepqueue_template,
)
from .tools import MeasureItToolRegistrar
from .backend import MeasureItBackend

__all__ = [
    # Templates
    "get_sweep0d_template",
    "get_sweep1d_template",
    "get_sweep2d_template",
    "get_simulsweep_template",
    "get_sweepqueue_template",
    "get_common_patterns_template",
    "get_measureit_code_examples",
    "get_database_access0d_template",
    "get_database_access1d_template",
    "get_database_access2d_template",
    "get_database_access_simulsweep_template",
    "get_database_access_sweepqueue_template",
    # Tool registrar
    "MeasureItToolRegistrar",
    # Backend
    "MeasureItBackend",
]
