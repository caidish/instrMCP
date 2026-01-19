"""
Configuration constants and argument parsing for E2E tests.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Default configuration values
DEFAULT_TOKEN = "instrmcp-playwright"
DEFAULT_JUPYTER_PORT = 8888
DEFAULT_MCP_PORT = 8123
DEFAULT_MCP_URL = "http://127.0.0.1:8123"
DEFAULT_NOTEBOOK = (
    Path(__file__).parent.parent / "notebooks" / "original" / "metadata_e2e.ipynb"
)
DEFAULT_SNAPSHOT = Path(__file__).parent.parent / "metadata_snapshot.json"
USER_SNAPSHOT = Path(__file__).parent.parent / "metadata_snapshot_user.json"
USER_CONFIG_PATH = Path.home() / ".instrmcp" / "metadata.yaml"
DEFAULT_JUPYTER_LOG = Path(__file__).parent.parent / "jupyter_lab.log"
# Working copy directory (within repo so JupyterLab can access it)
WORKING_NOTEBOOK_DIR = Path(__file__).parent.parent / "notebooks" / "_working"


def has_user_config() -> bool:
    """Check if user has a custom metadata config file."""
    return USER_CONFIG_PATH.exists()


def get_snapshot_path(explicit_path: Path | None) -> Path:
    """Get the appropriate snapshot path based on user config presence.

    Args:
        explicit_path: Explicitly specified path (takes precedence)

    Returns:
        Path to use for snapshot operations
    """
    if explicit_path and explicit_path != DEFAULT_SNAPSHOT:
        # User explicitly specified a path
        return explicit_path

    if has_user_config():
        print(f"Note: User config detected at {USER_CONFIG_PATH}")
        print(f"      Using user snapshot: {USER_SNAPSHOT}")
        return USER_SNAPSHOT

    return DEFAULT_SNAPSHOT


def parse_e2e_args() -> argparse.Namespace:
    """Parse command-line arguments for the E2E runner."""
    parser = argparse.ArgumentParser(
        description="Run MCP metadata E2E checks via Playwright."
    )
    parser.add_argument(
        "--mode",
        choices=("snapshot", "verify"),
        default="verify",
        help="Create a metadata snapshot or verify against an existing one.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="Path for metadata snapshot JSON.",
    )
    parser.add_argument(
        "--notebook",
        type=Path,
        default=DEFAULT_NOTEBOOK,
        help="Notebook to execute in JupyterLab.",
    )
    parser.add_argument(
        "--extra-cells",
        type=Path,
        help="JSON file with a list of code cell strings to append and run.",
    )
    parser.add_argument(
        "--skip-jupyter",
        action="store_true",
        help="Assume JupyterLab is already running.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip running the notebook via Playwright.",
    )
    parser.add_argument(
        "--keep-jupyter",
        action="store_true",
        help="Leave JupyterLab running after the script finishes.",
    )
    parser.add_argument(
        "--jupyter-port",
        type=int,
        default=DEFAULT_JUPYTER_PORT,
        help="JupyterLab port to use.",
    )
    parser.add_argument(
        "--jupyter-token",
        default=DEFAULT_TOKEN,
        help="JupyterLab auth token to use.",
    )
    parser.add_argument(
        "--jupyter-log",
        type=Path,
        default=DEFAULT_JUPYTER_LOG,
        help="Log file path for the JupyterLab process.",
    )
    parser.add_argument(
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        help="Base URL for the MCP server.",
    )
    parser.add_argument(
        "--cell-wait-ms",
        type=int,
        default=1000,
        help="Wait time after running each cell in fallback mode.",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help="MCP server port (used for cleanup).",
    )
    return parser.parse_args()
