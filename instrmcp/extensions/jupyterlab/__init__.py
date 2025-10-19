"""JupyterLab extension registration for InstrMCP."""

from pathlib import Path


def _jupyter_labextension_paths():
    """Return metadata for the JupyterLab extension."""
    here = Path(__file__).parent.resolve()
    extension_dir = here / "mcp_active_cell_bridge" / "labextension"

    return [{"src": str(extension_dir), "dest": "mcp-active-cell-bridge"}]


def get_extension_path():
    """Get the path to the JupyterLab extension."""
    here = Path(__file__).parent.resolve()
    return here / "mcp_active_cell_bridge" / "labextension"
