"""
Tool and resource registrars for the Jupyter MCP server.

This package contains modular registrars that organize tool and resource
registration by category, making the codebase more maintainable.

Meta-tools (consolidated):
- NotebookMetaToolRegistrar: 13 actions → 1 tool
- QCodesMetaToolRegistrar: 2 actions → 1 tool
- DatabaseMetaToolRegistrar: 4 actions → 1 tool
- DynamicMetaToolRegistrar: 6 actions → 1 tool
"""

from .notebook_meta_tool import NotebookMetaToolRegistrar
from .qcodes_meta_tool import QCodesMetaToolRegistrar
from .database_meta_tool import DatabaseMetaToolRegistrar
from .dynamic_meta_tool import DynamicMetaToolRegistrar
from .measureit_tools import MeasureItToolRegistrar
from .resources import ResourceRegistrar

# Legacy imports (for backward compatibility)
from .qcodes_tools import QCodesToolRegistrar
from .database_tools import DatabaseToolRegistrar

__all__ = [
    # Meta-tools (preferred)
    "NotebookMetaToolRegistrar",
    "QCodesMetaToolRegistrar",
    "DatabaseMetaToolRegistrar",
    "DynamicMetaToolRegistrar",
    "MeasureItToolRegistrar",
    "ResourceRegistrar",
    # Legacy (backward compatibility)
    "QCodesToolRegistrar",
    "DatabaseToolRegistrar",
]
