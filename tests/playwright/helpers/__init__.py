"""
Shared helpers for Playwright E2E tests.

This module provides utilities for:
- Configuration and argument parsing
- Process and port management
- Notebook preparation/cleanup
- Playwright browser automation
"""

from .config import (
    DEFAULT_JUPYTER_LOG,
    DEFAULT_JUPYTER_PORT,
    DEFAULT_MCP_PORT,
    DEFAULT_MCP_URL,
    DEFAULT_NOTEBOOK,
    DEFAULT_SNAPSHOT,
    DEFAULT_TOKEN,
    USER_CONFIG_PATH,
    USER_SNAPSHOT,
    WORKING_NOTEBOOK_DIR,
    get_snapshot_path,
    has_user_config,
    parse_e2e_args,
)
from .notebook import (
    cleanup_working_notebook,
    load_extra_cells,
    prepare_working_notebook,
)
from .playwright_runner import (
    run_notebook_playwright,
)
from .process import (
    find_free_port,
    is_port_free,
    kill_port,
    start_jupyter_server,
    stop_process,
    wait_for_http,
    wait_for_mcp,
)

__all__ = [
    # Config
    "DEFAULT_JUPYTER_LOG",
    "DEFAULT_JUPYTER_PORT",
    "DEFAULT_MCP_PORT",
    "DEFAULT_MCP_URL",
    "DEFAULT_NOTEBOOK",
    "DEFAULT_SNAPSHOT",
    "DEFAULT_TOKEN",
    "USER_CONFIG_PATH",
    "USER_SNAPSHOT",
    "WORKING_NOTEBOOK_DIR",
    "get_snapshot_path",
    "has_user_config",
    "parse_e2e_args",
    # Notebook
    "cleanup_working_notebook",
    "load_extra_cells",
    "prepare_working_notebook",
    # Playwright
    "run_notebook_playwright",
    # Process
    "find_free_port",
    "is_port_free",
    "kill_port",
    "start_jupyter_server",
    "stop_process",
    "wait_for_http",
    "wait_for_mcp",
]
