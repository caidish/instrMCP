"""
Jupyter QCoDeS MCP Extension

A read-only MCP server that provides access to QCoDeS instruments
running in a Jupyter kernel without arbitrary code execution.
"""

__version__ = "0.1.0"

# Re-export extension loading functions
from .jupyter_mcp_extension import load_ipython_extension, unload_ipython_extension

__all__ = ["load_ipython_extension", "unload_ipython_extension"]
