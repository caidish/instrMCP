"""
DEPRECATED: Dynamic tool system has moved.

This module is kept for backward compatibility.
New location: instrmcp.servers.jupyter_qcodes.options.dynamic_tool
"""

# Re-export from new location for backward compatibility
from instrmcp.servers.jupyter_qcodes.options.dynamic_tool import (
    ToolSpec,
    ToolParameter,
    validate_tool_spec,
    create_tool_spec,
    ToolRegistry,
)

__all__ = [
    "ToolSpec",
    "ToolParameter",
    "validate_tool_spec",
    "create_tool_spec",
    "ToolRegistry",
]
