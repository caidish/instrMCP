# InstrMCP E2E Test Suite

End-to-end tests for InstrMCP using Playwright browser automation with JupyterLab.

## Overview

This test suite validates the complete InstrMCP functionality by:
- Launching a real JupyterLab server
- Automating browser interactions via Playwright
- Testing MCP server operations through HTTP
- Verifying UI components and consent dialogs

## Prerequisites

```bash
# Install test dependencies
pip install playwright pytest-playwright httpx

# Install Playwright browsers
playwright install chromium
```

## Running Tests

```bash
# Activate the development environment
source ~/miniforge3/etc/profile.d/conda.sh && conda activate instrMCPdev

# Run all E2E tests
pytest tests/e2e/ -v

# Run a specific test file
pytest tests/e2e/test_01_server_lifecycle.py -v

# Run tests with a specific marker
pytest tests/e2e/ -v -m p0  # Priority 0 (critical) tests only
```

## Test Structure

```
tests/e2e/
├── README.md                      # This file
├── conftest.py                    # Pytest fixtures and setup
├── helpers/
│   ├── __init__.py               # Helper exports
│   ├── config.py                 # Test configuration constants
│   ├── jupyter_helpers.py        # JupyterLab automation (run_cell, etc.)
│   ├── mcp_helpers.py            # MCP HTTP client helpers
│   ├── mock_qcodes.py            # Mock QCodes definitions
│   ├── notebook.py               # Notebook file management
│   ├── process.py                # Jupyter server process management
│   └── playwright_runner.py      # Playwright page setup
├── notebooks/
│   ├── original/                 # Template notebooks (tracked in git)
│   │   ├── e2e_safe_mode.ipynb
│   │   ├── e2e_unsafe_mode.ipynb
│   │   ├── e2e_dangerous_mode.ipynb
│   │   └── e2e_dangerous_with_dynamictool.ipynb
│   └── _working/                 # Working copies (gitignored)
└── test_*.py                     # Test modules
```

## Test Modules

| Module | Purpose | Test IDs |
|--------|---------|----------|
| `test_01_server_lifecycle.py` | Server start/stop/restart, mode switching | SL-001 to SL-010 |
| `test_02_safe_mode_tools.py` | Read-only tools in safe mode | SM-001 to SM-083 |
| `test_03_unsafe_mode_tools.py` | Consent-requiring tools | UM-001 to UM-051 |
| `test_04_dangerous_mode.py` | Auto-approved consent operations | DM-001 to DM-020 |
| `test_05_security_scanner.py` | Dangerous code pattern blocking | SS-001 to SS-054 |
| `test_06_optional_features.py` | MeasureIt, Database, Dynamic Tools | OF-001 to OF-028 |
| `test_07_frontend_widget.py` | Toolbar widget and UI controls | FW-001 to FW-050 |
| `test_08_cell_targeting.py` | Cell ID and index navigation | CT-001 to CT-022 |
| `test_09_consent_dialogs.py` | Consent dialog UI behavior | CD-001 to CD-021 |

## Fixtures

### Session-Scoped Fixtures

- `jupyter_server` - Starts JupyterLab server for the test session
- `browser` / `context` - Playwright browser instances

### Function-Scoped Fixtures

- `notebook_page` - Fresh notebook page for each test
- `mcp_server` - MCP server in safe mode (default)
- `mcp_server_safe` - MCP server explicitly in safe mode
- `mcp_server_unsafe` - MCP server in unsafe mode
- `mcp_server_dangerous` - MCP server in dangerous mode (auto-approve consent)
- `mcp_server_dynamictool` - Dangerous mode with dynamic tools enabled
- `mock_qcodes_station` - Safe mode with mock QCodes instruments

## Architecture

```
Test Runner (pytest)
    │
    ├── Jupyter Server (subprocess)
    │   └── JupyterLab @ http://localhost:8888
    │       └── MCP Server @ http://localhost:8123
    │
    └── Playwright Browser
        └── Automates JupyterLab UI
            └── Runs cells, clicks buttons, etc.
```

### Communication Flow

1. **Test** creates fixtures → starts Jupyter server
2. **Playwright** opens browser → navigates to JupyterLab
3. **Helpers** run notebook cells → load InstrMCP extension
4. **MCP Client** sends HTTP requests → MCP server on port 8123
5. **Assertions** verify responses and UI state

## Key Helpers

### Jupyter Helpers (`jupyter_helpers.py`)

```python
from tests.e2e.helpers.jupyter_helpers import run_cell, get_cell_output, count_cells

# Run a cell and optionally wait for output
run_cell(page, "print('hello')", wait_for_output=True)

# Get the output of the current cell
output = get_cell_output(page)

# Count cells in the notebook
count = count_cells(page)
```

### MCP Helpers (`mcp_helpers.py`)

```python
from tests.e2e.helpers.mcp_helpers import call_mcp_tool, list_mcp_tools, parse_tool_result

# Call an MCP tool
result = call_mcp_tool(base_url, "notebook_read_active_cell")

# Parse the result
success, content = parse_tool_result(result)

# List available tools
tools = list_mcp_tools(base_url)
```

## Test Markers

Tests are marked with priority levels:

- `@pytest.mark.p0` - Critical functionality (must pass)
- `@pytest.mark.p1` - Important functionality
- `@pytest.mark.p2` - Nice-to-have functionality

Run by priority:
```bash
pytest tests/e2e/ -v -m p0      # Critical only
pytest tests/e2e/ -v -m "p0 or p1"  # Critical + important
```

## Test Results

Current status: **164 passed, 2 skipped**

Skipped tests:
- `test_consent_deny_returns_error` - Requires manual consent interaction
- `test_consent_deny_no_change` - Requires manual consent interaction

## Debugging

### Screenshots on Failure

Failed tests automatically save screenshots to:
```
tests/e2e/test-results/test_name[chromium]-failure.png
```

### Verbose Output

```bash
# Show more details
pytest tests/e2e/ -v --tb=long

# Show print statements
pytest tests/e2e/ -v -s
```

### Run Single Test

```bash
pytest tests/e2e/test_01_server_lifecycle.py::TestServerLifecycle::test_server_starts_successfully -v
```

## CI Integration

E2E tests run in GitHub Actions with:
- Ubuntu runner with display server (Xvfb)
- Playwright Chromium browser
- JupyterLab server started in background

See `.github/workflows/e2e.yml` for configuration.

## Contributing

When adding new tests:

1. Follow the naming convention: `test_XX_feature_name.py`
2. Add test ID comments (e.g., `"""XX-001: Test description."""`)
3. Use appropriate fixtures for the mode needed
4. Mark tests with priority (`@pytest.mark.p0`, etc.)
5. Run `black tests/e2e/` and `flake8 tests/e2e/` before committing
