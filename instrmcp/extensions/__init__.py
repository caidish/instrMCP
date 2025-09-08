"""
InstrMCP Extensions

Jupyter and IPython extensions for InstrMCP integration.
"""

from . import jupyterlab

__all__ = ["jupyterlab", "load_ipython_extension", "unload_ipython_extension"]

# IPython extension functions
def load_ipython_extension(ipython):
    """Load the InstrMCP IPython extension."""
    from ..servers.jupyter_qcodes import load_ipython_extension as load_jupyter_qcodes
    load_jupyter_qcodes(ipython)

def unload_ipython_extension(ipython):
    """Unload the InstrMCP IPython extension."""
    from ..servers.jupyter_qcodes import unload_ipython_extension as unload_jupyter_qcodes
    unload_jupyter_qcodes(ipython)

# Auto-loading configuration for Jupyter
def load_jupyter_extension(ipython):
    """Auto-load entry point for Jupyter extensions."""
    # Load the jupyter_qcodes extension
    from ..servers.jupyter_qcodes import load_ipython_extension as load_jupyter_qcodes
    load_jupyter_qcodes(ipython)

def unload_jupyter_extension(ipython):
    """Auto-unload entry point for Jupyter extensions."""
    from ..servers.jupyter_qcodes import unload_ipython_extension as unload_jupyter_qcodes
    unload_jupyter_qcodes(ipython)