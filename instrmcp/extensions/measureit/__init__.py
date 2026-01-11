"""
MeasureIt integration for InstrMCP.

Provides optional MeasureIt templates and functionality when enabled.
"""

from .measureit_templates import (
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

__all__ = [
    "get_sweep0d_template",
    "get_sweep1d_template",
    "get_sweep2d_template",
    "get_simulsweep_template",
    "get_sweepqueue_template",
    "get_common_patterns_template",
    "get_measureit_code_examples",
    # Data access templates
    "get_database_access0d_template",
    "get_database_access1d_template",
    "get_database_access2d_template",
    "get_database_access_simulsweep_template",
    "get_database_access_sweepqueue_template",
]
