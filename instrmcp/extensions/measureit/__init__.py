"""
DEPRECATED: MeasureIt integration has moved.

This module is kept for backward compatibility.
New location: instrmcp.servers.jupyter_qcodes.options.measureit
"""

# Re-export from new location for backward compatibility
from instrmcp.servers.jupyter_qcodes.options.measureit import (
    get_sweep0d_template,
    get_sweep1d_template,
    get_sweep2d_template,
    get_simulsweep_template,
    get_sweepqueue_template,
    get_common_patterns_template,
    get_measureit_code_examples,
    get_database_access0d_template,
    get_database_access1d_template,
    get_database_access2d_template,
    get_database_access_simulsweep_template,
    get_database_access_sweepqueue_template,
)

__all__ = [
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
]
