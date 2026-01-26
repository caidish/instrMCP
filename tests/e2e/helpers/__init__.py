"""Helper modules for E2E testing."""

from .config import (
    DEFAULT_TOKEN,
    DEFAULT_JUPYTER_PORT,
    DEFAULT_MCP_PORT,
    DEFAULT_MCP_URL,
    NOTEBOOKS_DIR,
    ORIGINAL_NOTEBOOKS_DIR,
    WORKING_NOTEBOOK_DIR,
    SAFE_MODE_NOTEBOOK,
    UNSAFE_MODE_NOTEBOOK,
    DANGEROUS_MODE_NOTEBOOK,
    DANGEROUS_DYNAMICTOOL_NOTEBOOK,
    MEASUREIT_SWEEPQUEUE_NOTEBOOK,
    TEST_RESULTS_DIR,
    DEFAULT_JUPYTER_LOG,
)

from .notebook import (
    prepare_working_notebook,
    cleanup_working_notebook,
    get_notebook_relative_path,
)

from .process import (
    wait_for_http,
    start_jupyter_server,
    kill_port,
    is_port_free,
    find_free_port,
    stop_process,
)

from .playwright_runner import (
    run_notebook_playwright,
    run_notebook_standalone,
    get_page_for_notebook,
)

from .jupyter_helpers import (
    run_cell,
    get_cell_output,
    get_all_cell_outputs,
    wait_for_cell_execution,
    clear_all_outputs,
    select_cell,
    get_active_cell_index,
    count_cells,
)

from .mcp_helpers import (
    extract_port,
    call_mcp_tool,
    list_mcp_tools,
    wait_for_mcp_server,
    parse_tool_result,
)

from .mock_qcodes import (
    MOCK_QCODES_SETUP,
    VARIABLE_TEST_SETUP,
    STANDARD_NOTEBOOK_CELLS,
)

__all__ = [
    # Config
    "DEFAULT_TOKEN",
    "DEFAULT_JUPYTER_PORT",
    "DEFAULT_MCP_PORT",
    "DEFAULT_MCP_URL",
    "NOTEBOOKS_DIR",
    "ORIGINAL_NOTEBOOKS_DIR",
    "WORKING_NOTEBOOK_DIR",
    "SAFE_MODE_NOTEBOOK",
    "UNSAFE_MODE_NOTEBOOK",
    "DANGEROUS_MODE_NOTEBOOK",
    "DANGEROUS_DYNAMICTOOL_NOTEBOOK",
    "MEASUREIT_SWEEPQUEUE_NOTEBOOK",
    "TEST_RESULTS_DIR",
    "DEFAULT_JUPYTER_LOG",
    # Notebook
    "prepare_working_notebook",
    "cleanup_working_notebook",
    "get_notebook_relative_path",
    # Process
    "wait_for_http",
    "start_jupyter_server",
    "kill_port",
    "is_port_free",
    "find_free_port",
    "stop_process",
    # Playwright runner
    "run_notebook_playwright",
    "run_notebook_standalone",
    "get_page_for_notebook",
    # Jupyter helpers
    "run_cell",
    "get_cell_output",
    "get_all_cell_outputs",
    "wait_for_cell_execution",
    "clear_all_outputs",
    "select_cell",
    "get_active_cell_index",
    "count_cells",
    # MCP helpers
    "extract_port",
    "call_mcp_tool",
    "list_mcp_tools",
    "wait_for_mcp_server",
    "parse_tool_result",
    # Mock QCodes
    "MOCK_QCODES_SETUP",
    "VARIABLE_TEST_SETUP",
    "STANDARD_NOTEBOOK_CELLS",
]
