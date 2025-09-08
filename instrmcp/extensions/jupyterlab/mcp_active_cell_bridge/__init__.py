"""MCP Active Cell Bridge JupyterLab Extension"""

from ._version import __version__

def _jupyter_labextension_paths():
    return [{"src": "labextension", "dest": "mcp-active-cell-bridge"}]