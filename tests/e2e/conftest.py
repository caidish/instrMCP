"""
Pytest configuration and shared fixtures for E2E tests.

Uses a notebook-based approach:
1. Pre-built notebooks in notebooks/original/
2. Copies to notebooks/_working/ before each test session
3. Runs all cells via Playwright automation
4. Interacts with MCP server via HTTP
"""

from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest

# Import helpers
from tests.e2e.helpers import (
    DEFAULT_TOKEN,
    DEFAULT_JUPYTER_PORT,
    DEFAULT_MCP_PORT,
    DEFAULT_JUPYTER_LOG,
    SAFE_MODE_NOTEBOOK,
    UNSAFE_MODE_NOTEBOOK,
    DANGEROUS_MODE_NOTEBOOK,
    DANGEROUS_DYNAMICTOOL_NOTEBOOK,
    MEASUREIT_SWEEPQUEUE_NOTEBOOK,
    TEST_RESULTS_DIR,
    prepare_working_notebook,
    cleanup_working_notebook,
    get_notebook_relative_path,
    wait_for_http,
    start_jupyter_server,
    kill_port,
    is_port_free,
    find_free_port,
    stop_process,
    run_notebook_playwright,
    wait_for_mcp_server,
)


def pytest_addoption(parser):
    """Add custom pytest options."""
    parser.addoption(
        "--jupyter-url",
        default=f"http://localhost:{DEFAULT_JUPYTER_PORT}",
        help="JupyterLab URL",
    )
    parser.addoption(
        "--jupyter-token",
        default=DEFAULT_TOKEN,
        help="JupyterLab authentication token",
    )
    parser.addoption(
        "--mcp-port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help="MCP server port",
    )
    parser.addoption(
        "--skip-jupyter-start",
        action="store_true",
        help="Skip starting JupyterLab (assume already running)",
    )
    parser.addoption(
        "--cell-wait-ms",
        type=int,
        default=2000,
        help="Wait time after running each cell",
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "p0: Priority 0 (critical) tests")
    config.addinivalue_line("markers", "p1: Priority 1 (important) tests")
    config.addinivalue_line("markers", "p2: Priority 2 (nice-to-have) tests")
    config.addinivalue_line("markers", "slow: Tests that take longer to run")


@pytest.fixture(scope="session")
def jupyter_url(request) -> str:
    """Get JupyterLab URL from command line options."""
    return request.config.getoption("--jupyter-url")


@pytest.fixture(scope="session")
def jupyter_token(request) -> str:
    """Get JupyterLab token from command line options."""
    return request.config.getoption("--jupyter-token")


@pytest.fixture(scope="session")
def mcp_port(request) -> int:
    """Get MCP port from command line options."""
    return request.config.getoption("--mcp-port")


@pytest.fixture(scope="session")
def cell_wait_ms(request) -> int:
    """Get cell wait time from command line options."""
    return request.config.getoption("--cell-wait-ms")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def browser_context_args():
    """Configure browser context arguments."""
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def jupyter_server(request, jupyter_token, repo_root) -> Generator[dict, None, None]:
    """Start JupyterLab server for the test session.

    Yields:
        Dictionary with jupyter_url and token
    """
    skip_start = request.config.getoption("--skip-jupyter-start")

    if skip_start:
        # Use existing server
        jupyter_port = DEFAULT_JUPYTER_PORT
        jupyter_url = f"http://127.0.0.1:{jupyter_port}"
        yield {"url": jupyter_url, "token": jupyter_token, "process": None}
        return

    # Kill any existing processes on default ports
    kill_port(DEFAULT_MCP_PORT)
    kill_port(DEFAULT_JUPYTER_PORT)
    cleanup_working_notebook()

    # Find a free port for Jupyter
    jupyter_port = DEFAULT_JUPYTER_PORT
    if not is_port_free(jupyter_port):
        jupyter_port = find_free_port()
        print(f"Port {DEFAULT_JUPYTER_PORT} in use, using {jupyter_port}")

    jupyter_url = f"http://127.0.0.1:{jupyter_port}"

    # Start Jupyter server
    process, log_path = start_jupyter_server(
        repo_root, jupyter_port, jupyter_token, DEFAULT_JUPYTER_LOG
    )

    # Wait for server to be ready
    ready = wait_for_http(f"{jupyter_url}/lab?token={jupyter_token}", timeout_s=60)
    if not ready:
        stop_process(process)
        pytest.fail("JupyterLab did not start in time")

    yield {"url": jupyter_url, "token": jupyter_token, "process": process}

    # Cleanup
    if process:
        stop_process(process)
    kill_port(DEFAULT_MCP_PORT)
    cleanup_working_notebook()


@pytest.fixture(scope="function")
def mcp_server_safe(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in safe mode via notebook.

    Yields:
        Dictionary with page, port, url, and mode
    """
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        SAFE_MODE_NOTEBOOK,
        "safe",
    )


@pytest.fixture(scope="function")
def mcp_server(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in safe mode (alias for mcp_server_safe)."""
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        SAFE_MODE_NOTEBOOK,
        "safe",
    )


@pytest.fixture(scope="function")
def mcp_server_unsafe(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in unsafe mode via notebook.

    Yields:
        Dictionary with page, port, url, and mode
    """
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        UNSAFE_MODE_NOTEBOOK,
        "unsafe",
    )


@pytest.fixture(scope="function")
def mcp_server_dangerous(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in dangerous mode via notebook.

    Yields:
        Dictionary with page, port, url, and mode
    """
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        DANGEROUS_MODE_NOTEBOOK,
        "dangerous",
    )


@pytest.fixture(scope="function")
def mcp_server_dynamictool(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in dangerous mode with dynamictool enabled.

    Yields:
        Dictionary with page, port, url, and mode
    """
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        DANGEROUS_DYNAMICTOOL_NOTEBOOK,
        "dangerous+dynamictool",
    )


@pytest.fixture(scope="function")
def mcp_server_measureit_sweepqueue(
    page, jupyter_server, mcp_port, cell_wait_ms, repo_root
) -> Generator[dict, None, None]:
    """Start MCP server in dangerous mode with MeasureIt and SweepQueue setup.

    Yields:
        Dictionary with page, port, url, and mode
    """
    yield from _setup_mcp_server(
        page,
        jupyter_server,
        mcp_port,
        cell_wait_ms,
        repo_root,
        MEASUREIT_SWEEPQUEUE_NOTEBOOK,
        "dangerous+measureit",
    )


def _setup_mcp_server(
    page,
    jupyter_server,
    mcp_port,
    cell_wait_ms,
    repo_root,
    notebook_path: Path,
    mode: str,
) -> Generator[dict, None, None]:
    """Common setup logic for MCP server fixtures.

    Args:
        page: Playwright page
        jupyter_server: Jupyter server fixture
        mcp_port: Expected MCP port
        cell_wait_ms: Wait time after each cell
        repo_root: Repository root path
        notebook_path: Path to the notebook to run
        mode: Server mode name

    Yields:
        Dictionary with page, port, url, and mode
    """
    # Kill any existing MCP server on the port
    kill_port(mcp_port)

    # Clean up working notebook
    cleanup_working_notebook()

    # Prepare working notebook
    working_notebook = prepare_working_notebook(notebook_path)
    notebook_rel = get_notebook_relative_path(working_notebook, repo_root)

    # Run the notebook using the provided page
    run_notebook_playwright(
        page,
        jupyter_server["url"],
        jupyter_server["token"],
        notebook_rel,
        cell_wait_ms,
    )

    # Wait for MCP server to be ready
    base_url = f"http://localhost:{mcp_port}"
    if not wait_for_mcp_server(base_url, timeout_s=30):
        pytest.fail(f"MCP server did not start within timeout at {base_url}")

    yield {
        "page": page,
        "port": mcp_port,
        "url": base_url,
        "mode": mode,
    }

    # Cleanup
    kill_port(mcp_port)
    cleanup_working_notebook()


@pytest.fixture(scope="function")
def notebook_page(page, jupyter_server, repo_root, cell_wait_ms):
    """Fixture that provides a page with a notebook open but no MCP server.

    Useful for testing notebook operations without MCP.
    """
    cleanup_working_notebook()

    # Prepare working notebook (use safe mode notebook as base)
    working_notebook = prepare_working_notebook(SAFE_MODE_NOTEBOOK)
    notebook_rel = get_notebook_relative_path(working_notebook, repo_root)

    # Open the notebook but don't run all cells - just navigate to it
    notebook_url = f"{jupyter_server['url']}/lab/tree/{notebook_rel}?token={jupyter_server['token']}"

    page.goto(notebook_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_selector(".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000)
    page.wait_for_selector(
        ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Notebook", timeout=120000
    )
    page.wait_for_timeout(2000)

    yield page

    cleanup_working_notebook()


@pytest.fixture(scope="function")
def jupyter_page(page, jupyter_server):
    """Create a page with JupyterLab loaded but no notebook open.

    Useful for testing launcher and general JupyterLab functionality.
    """
    full_url = f"{jupyter_server['url']}/lab?token={jupyter_server['token']}"
    page.goto(full_url, wait_until="domcontentloaded", timeout=60000)

    # Wait for JupyterLab to be ready
    page.wait_for_selector(".jp-LabShell", timeout=60000)
    page.wait_for_timeout(2000)

    yield page


@pytest.fixture(scope="function")
def test_variables(mcp_server):
    """Fixture that provides MCP server with test variables set up.

    The safe mode notebook already creates test variables (test_int, test_str, etc.),
    so this fixture just returns mcp_server. For tests expecting 'x', the variable
    is aliased from test_int.
    """
    # The safe mode notebook already has test variables defined in cell 7
    # test_int = 42, test_str = "hello world", etc.
    # We don't need to add more - tests should use these variable names
    yield mcp_server


@pytest.fixture(scope="function")
def mock_qcodes_station(mcp_server):
    """Fixture that provides MCP server with mock QCodes station set up.

    The safe mode notebook already sets up QCodes with mock instruments,
    so this just aliases mcp_server.
    """
    # The safe mode notebook already sets up a QCodes station with mock_dac1 and mock_dac2
    # These tests expect mock_dmm, so we need to add it
    from tests.e2e.helpers.mock_qcodes import MOCK_QCODES_SETUP

    page = mcp_server["page"]

    # Add and run cell with QCodes setup
    page.evaluate("""
    () => {
        const app = window.jupyterapp || window.jupyterlab || window.jupyterApp || window.jupyterLab;
        if (app && app.commands) {
            app.commands.execute('notebook:insert-cell-below');
        }
    }
    """)
    page.wait_for_timeout(500)

    # Type the QCodes setup code
    page.keyboard.type(MOCK_QCODES_SETUP, delay=1)
    page.wait_for_timeout(500)

    # Execute the cell
    page.keyboard.press("Shift+Enter")
    page.wait_for_timeout(3000)

    yield mcp_server


# Hooks for capturing screenshots on failure
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture screenshot on test failure."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        # Try to get page from various fixtures
        page = None
        for fixture_name in ["page", "notebook_page", "jupyter_page"]:
            page = item.funcargs.get(fixture_name)
            if page:
                break

        # Also check mcp_server fixtures
        if not page:
            for fixture_name in [
                "mcp_server",
                "mcp_server_safe",
                "mcp_server_unsafe",
                "mcp_server_dangerous",
                "mcp_server_dynamictool",
            ]:
                mcp = item.funcargs.get(fixture_name)
                if mcp and "page" in mcp:
                    page = mcp["page"]
                    break

        if page:
            try:
                # Create test-results directory if needed
                TEST_RESULTS_DIR.mkdir(exist_ok=True)

                # Capture screenshot
                screenshot_path = TEST_RESULTS_DIR / f"{item.name}-failure.png"
                page.screenshot(path=str(screenshot_path))
                print(f"\nScreenshot saved to: {screenshot_path}")
            except Exception as e:
                print(f"\nFailed to capture screenshot: {e}")
