"""
Dynamic tool creation system for the Jupyter MCP server.

Allows LLMs to create, update, and manage tools at runtime.
Enable with: %mcp_option add dynamictool (requires dangerous mode)
"""

from .spec import ToolSpec, ToolParameter, validate_tool_spec, create_tool_spec
from .registry import ToolRegistry
from .registrar import DynamicToolRegistrar
from .runtime import DynamicToolRuntime

__all__ = [
    # Spec classes
    "ToolSpec",
    "ToolParameter",
    "validate_tool_spec",
    "create_tool_spec",
    # Registry
    "ToolRegistry",
    # Tool registrar
    "DynamicToolRegistrar",
    # Runtime
    "DynamicToolRuntime",
]
