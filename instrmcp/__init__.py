"""
InstrMCP: Instrumentation Control MCP Server Suite

A comprehensive MCP server suite for physics laboratory instrumentation control,
enabling Large Language Models to interact directly with physics instruments
and measurement systems through standardized MCP interfaces.
"""

__version__ = "2.3.5"
__author__ = "Jiaqi Cai"
__email__ = "jiaqic@mit.edu"
__license__ = "MIT"

# Lazy imports to avoid loading heavy dependencies at import time
# Use: from instrmcp import servers, tools when needed

# Version info accessible as instrmcp.version_info
version_info = tuple(int(x) for x in __version__.split("."))

# Package metadata
__all__ = ["__version__", "__author__", "__email__", "__license__", "version_info"]

# Package description
DESCRIPTION = "MCP server suite for physics laboratory instrumentation control"
LONG_DESCRIPTION = __doc__

# Supported Python versions
PYTHON_REQUIRES = ">=3.8"

# Core dependencies
INSTALL_REQUIRES = ["fastmcp>=0.1.0", "mcp>=1.0.0", "pyyaml>=6.0", "httpx>=0.25.0"]

# Optional dependency groups
EXTRAS_REQUIRE = {
    "jupyter": ["jupyterlab>=4.0.0", "ipython>=8.0.0", "notebook>=6.4.0"],
    "qcodes": [
        "qcodes>=0.45.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "matplotlib>=3.7.0",
        "scipy>=1.10.0",
    ],
    "redpitaya": ["pyrpl>=0.9.4", "scipy>=1.10.0", "numpy>=1.24.0"],
    "dev": [
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
        "pytest-cov>=4.0.0",
        "black>=23.0.0",
        "flake8>=6.0.0",
        "mypy>=1.0.0",
        "pre-commit>=3.0.0",
    ],
}

# Add "full" extras that includes everything
EXTRAS_REQUIRE["full"] = (
    EXTRAS_REQUIRE["jupyter"] + EXTRAS_REQUIRE["qcodes"] + EXTRAS_REQUIRE["redpitaya"]
)
