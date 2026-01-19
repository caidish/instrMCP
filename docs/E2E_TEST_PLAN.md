# InstrMCP E2E Test Plan

**Version**: 1.0
**Date**: 2026-01-19
**Status**: Planning
**Related Issue**: [#16](https://github.com/caidish/instrMCP/issues/16)

---

## 1. Overview

This document outlines the comprehensive end-to-end (E2E) testing strategy for InstrMCP, combining automated Playwright browser testing with the functional test scenarios from manual testing.

### Goals

- Verify instrmcp functionality with JupyterLab frontend
- Automate manual test scenarios for regression testing
- Ensure CI/CD integration with GitHub Actions
- Maintain test isolation without external instrument dependencies

---

## 2. Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Browser Automation | Playwright | Chromium-based browser control |
| Test Framework | pytest | Test runner and assertions |
| Integration | pytest-playwright | pytest + Playwright binding |
| CI Platform | GitHub Actions | Automated test execution |

### Installation

```bash
pip install playwright pytest-playwright
playwright install chromium
```

---

## 3. Directory Structure

```
tests/
├── e2e/
│   ├── conftest.py                    # Shared fixtures
│   ├── helpers/
│   │   ├── __init__.py
│   │   ├── jupyter_helpers.py         # JupyterLab automation helpers
│   │   ├── mcp_inspector_helpers.py   # MCP Inspector automation
│   │   └── mock_qcodes.py             # Mock QCodes station setup
│   ├── test_01_server_lifecycle.py    # Server start/stop/restart
│   ├── test_02_safe_mode_tools.py     # Safe mode tool testing
│   ├── test_03_unsafe_mode_tools.py   # Unsafe mode + consent dialogs
│   ├── test_04_dangerous_mode.py      # Dangerous mode consent bypass
│   ├── test_05_security_scanner.py    # Security pattern blocking
│   ├── test_06_optional_features.py   # MeasureIt, Database, DynamicTools
│   ├── test_07_frontend_widget.py     # Toolbar widget testing
│   ├── test_08_cell_targeting.py      # cell_id_notebook, index:N navigation
│   └── test_09_consent_dialogs.py     # Consent dialog UI testing
├── unit/
│   └── ...                            # Existing unit tests
└── playwright/
    └── ...                            # Existing Playwright helpers
```

---

## 4. Test Fixtures (conftest.py)

### 4.1 Core Fixtures

```python
import pytest
from playwright.sync_api import Page, Browser

@pytest.fixture(scope="session")
def browser_context(browser: Browser):
    """Create browser context with JupyterLab-appropriate settings."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )
    yield context
    context.close()

@pytest.fixture(scope="function")
def jupyter_page(browser_context) -> Page:
    """Create a new page with JupyterLab loaded."""
    page = browser_context.new_page()
    page.goto("http://localhost:8888/lab")
    page.wait_for_selector(".jp-Launcher", timeout=30000)
    yield page
    page.close()

@pytest.fixture(scope="function")
def notebook_page(jupyter_page: Page) -> Page:
    """Create a new notebook and return the page."""
    # Click Python 3 kernel in launcher
    jupyter_page.click('text=Python 3')
    jupyter_page.wait_for_selector('.jp-Notebook', timeout=10000)
    yield jupyter_page

@pytest.fixture(scope="function")
def mcp_server(notebook_page: Page):
    """Start MCP server and return connection info."""
    # Load extension and start server
    run_cell(notebook_page, "%load_ext instrmcp.extensions")
    run_cell(notebook_page, "%mcp_start")

    # Extract port from output
    output = get_cell_output(notebook_page)
    port = extract_port(output)

    yield {"page": notebook_page, "port": port, "url": f"http://localhost:{port}/mcp"}

    # Cleanup
    run_cell(notebook_page, "%mcp_stop")

@pytest.fixture(scope="function")
def mock_qcodes_station(notebook_page: Page):
    """Setup mock QCodes station for testing."""
    setup_code = '''
from qcodes import Station, Parameter
from qcodes.instrument import Instrument

class MockInstrument(Instrument):
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.add_parameter('voltage', unit='V', get_cmd=lambda: 1.23, set_cmd=lambda x: None)
        self.add_parameter('current', unit='A', get_cmd=lambda: 0.001, set_cmd=lambda x: None)
        self.add_parameter('frequency', unit='Hz', get_cmd=lambda: 1000, set_cmd=lambda x: None)

mock_instr = MockInstrument('mock_dmm')
station = Station()
station.add_component(mock_instr)
'''
    run_cell(notebook_page, setup_code)
    yield
    # Cleanup handled by notebook closure
```

### 4.2 Helper Functions

```python
def run_cell(page: Page, code: str, wait_for_output: bool = True):
    """Execute code in the active cell."""
    # Type code into active cell
    page.keyboard.type(code)
    # Execute cell
    page.keyboard.press("Shift+Enter")
    if wait_for_output:
        page.wait_for_selector('.jp-OutputArea-output', timeout=30000)

def get_cell_output(page: Page) -> str:
    """Get output text from the active cell."""
    output = page.locator('.jp-OutputArea-output').last
    return output.inner_text()

def extract_port(output: str) -> int:
    """Extract port number from server start output."""
    import re
    match = re.search(r'localhost:(\d+)', output)
    return int(match.group(1)) if match else 8123
```

---

## 5. Test Modules

### 5.1 Server Lifecycle Tests (`test_01_server_lifecycle.py`)

**Purpose**: Verify MCP server start/stop/restart and mode switching.

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| SL-001 | `test_extension_loading` | Extension loads without error | P0 |
| SL-002 | `test_toolbar_appears_without_load_ext` | Toolbar widget appears automatically | P0 |
| SL-003 | `test_server_start_default_safe_mode` | Server starts in safe mode by default | P0 |
| SL-004 | `test_mcp_status_not_running` | Status shows "not running" before start | P1 |
| SL-005 | `test_mcp_status_running` | Status shows running state and port | P0 |
| SL-006 | `test_server_stop` | Server stops cleanly | P0 |
| SL-007 | `test_server_restart` | Server restarts without error | P0 |
| SL-008 | `test_mode_switch_safe_to_unsafe` | Switch from safe to unsafe mode | P0 |
| SL-009 | `test_mode_switch_to_dangerous` | Switch to dangerous mode with warning | P0 |
| SL-010 | `test_mode_requires_restart` | Mode change requires restart to take effect | P1 |

```python
# Example implementation
class TestServerLifecycle:
    def test_extension_loading(self, notebook_page):
        """SL-001: Extension loads without error."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        output = get_cell_output(notebook_page)
        assert "error" not in output.lower()

    def test_server_start_default_safe_mode(self, notebook_page):
        """SL-003: Server starts in safe mode by default."""
        run_cell(notebook_page, "%load_ext instrmcp.extensions")
        run_cell(notebook_page, "%mcp_start")
        run_cell(notebook_page, "%mcp_status")
        output = get_cell_output(notebook_page)
        assert "mode" in output.lower()
        assert "safe" in output.lower()
```

---

### 5.2 Safe Mode Tools Tests (`test_02_safe_mode_tools.py`)

**Purpose**: Verify all read-only tools work correctly in safe mode.

#### Resource Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| SM-001 | `test_mcp_list_resources` | mcp_list_resources | P0 |
| SM-002 | `test_mcp_get_resource_valid` | mcp_get_resource | P0 |
| SM-003 | `test_mcp_get_resource_invalid` | mcp_get_resource | P1 |

#### Notebook Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| SM-010 | `test_notebook_server_status` | notebook_server_status | P0 |
| SM-011 | `test_notebook_list_variables_no_filter` | notebook_list_variables | P0 |
| SM-012 | `test_notebook_list_variables_type_filter` | notebook_list_variables | P1 |
| SM-013 | `test_notebook_read_variable_simple` | notebook_read_variable | P0 |
| SM-014 | `test_notebook_read_variable_detailed` | notebook_read_variable | P1 |
| SM-015 | `test_notebook_read_variable_numpy_array` | notebook_read_variable | P1 |
| SM-016 | `test_notebook_read_variable_dataframe` | notebook_read_variable | P1 |
| SM-017 | `test_notebook_read_variable_large_array` | notebook_read_variable | P1 |
| SM-018 | `test_notebook_read_variable_nonexistent` | notebook_read_variable | P1 |
| SM-020 | `test_notebook_read_active_cell_basic` | notebook_read_active_cell | P0 |
| SM-021 | `test_notebook_read_active_cell_detailed` | notebook_read_active_cell | P1 |
| SM-022 | `test_notebook_read_active_cell_line_range` | notebook_read_active_cell | P2 |
| SM-023 | `test_notebook_read_active_cell_markdown` | notebook_read_active_cell | P1 |
| SM-030 | `test_notebook_read_active_cell_output_success` | notebook_read_active_cell_output | P0 |
| SM-031 | `test_notebook_read_active_cell_output_error` | notebook_read_active_cell_output | P1 |
| SM-032 | `test_notebook_read_active_cell_output_no_output` | notebook_read_active_cell_output | P1 |
| SM-033 | `test_notebook_read_active_cell_output_markdown` | notebook_read_active_cell_output | P1 |
| SM-040 | `test_notebook_read_content_basic` | notebook_read_content | P0 |
| SM-041 | `test_notebook_read_content_with_output` | notebook_read_content | P1 |
| SM-042 | `test_notebook_read_content_detailed` | notebook_read_content | P2 |
| SM-050 | `test_notebook_move_cursor_above` | notebook_move_cursor | P0 |
| SM-051 | `test_notebook_move_cursor_below` | notebook_move_cursor | P0 |
| SM-052 | `test_notebook_move_cursor_top_bottom` | notebook_move_cursor | P1 |

#### QCodes Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| SM-060 | `test_qcodes_instrument_info_all` | qcodes_instrument_info | P0 |
| SM-061 | `test_qcodes_instrument_info_specific` | qcodes_instrument_info | P0 |
| SM-062 | `test_qcodes_instrument_info_detailed` | qcodes_instrument_info | P1 |
| SM-063 | `test_qcodes_instrument_info_with_values` | qcodes_instrument_info | P1 |
| SM-064 | `test_qcodes_instrument_info_invalid` | qcodes_instrument_info | P1 |
| SM-070 | `test_qcodes_get_parameter_info_basic` | qcodes_get_parameter_info | P0 |
| SM-071 | `test_qcodes_get_parameter_info_detailed` | qcodes_get_parameter_info | P1 |
| SM-072 | `test_qcodes_get_parameter_info_invalid` | qcodes_get_parameter_info | P1 |
| SM-080 | `test_qcodes_get_parameter_values_single` | qcodes_get_parameter_values | P0 |
| SM-081 | `test_qcodes_get_parameter_values_batch` | qcodes_get_parameter_values | P1 |
| SM-082 | `test_qcodes_get_parameter_values_detailed` | qcodes_get_parameter_values | P1 |
| SM-083 | `test_qcodes_get_parameter_values_invalid` | qcodes_get_parameter_values | P1 |

---

### 5.3 Unsafe Mode Tools Tests (`test_03_unsafe_mode_tools.py`)

**Purpose**: Verify unsafe tools require consent and function correctly.

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| UM-001 | `test_unsafe_mode_switch` | %mcp_unsafe | P0 |
| UM-002 | `test_unsafe_tools_visible` | Tools list | P0 |
| UM-010 | `test_notebook_update_editing_cell_consent_deny` | notebook_update_editing_cell | P0 |
| UM-011 | `test_notebook_update_editing_cell_consent_approve` | notebook_update_editing_cell | P0 |
| UM-012 | `test_notebook_update_editing_cell_verify_change` | notebook_update_editing_cell | P0 |
| UM-020 | `test_notebook_execute_active_cell_consent` | notebook_execute_active_cell | P0 |
| UM-021 | `test_notebook_execute_active_cell_output` | notebook_execute_active_cell | P0 |
| UM-022 | `test_notebook_execute_active_cell_error` | notebook_execute_active_cell | P1 |
| UM-023 | `test_notebook_execute_active_cell_timeout` | notebook_execute_active_cell | P1 |
| UM-030 | `test_notebook_add_cell_code_below` | notebook_add_cell | P0 |
| UM-031 | `test_notebook_add_cell_markdown_above` | notebook_add_cell | P0 |
| UM-032 | `test_notebook_add_cell_invalid_type` | notebook_add_cell | P1 |
| UM-033 | `test_notebook_add_cell_invalid_position` | notebook_add_cell | P1 |
| UM-040 | `test_notebook_delete_cell_consent_deny` | notebook_delete_cell | P0 |
| UM-041 | `test_notebook_delete_cell_consent_approve` | notebook_delete_cell | P0 |
| UM-050 | `test_notebook_apply_patch_consent` | notebook_apply_patch | P0 |
| UM-051 | `test_notebook_apply_patch_not_found` | notebook_apply_patch | P1 |

---

### 5.4 Dangerous Mode Tests (`test_04_dangerous_mode.py`)

**Purpose**: Verify consent bypass in dangerous mode.

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| DM-001 | `test_dangerous_mode_switch` | Switch to dangerous mode | P0 |
| DM-002 | `test_dangerous_mode_status` | Status shows dangerous mode | P0 |
| DM-010 | `test_consent_bypass_update_cell` | No consent dialog for update | P0 |
| DM-011 | `test_consent_bypass_execute_cell` | No consent dialog for execute | P0 |
| DM-012 | `test_consent_bypass_delete_cell` | No consent dialog for delete | P0 |
| DM-013 | `test_consent_bypass_apply_patch` | No consent dialog for patch | P0 |

---

### 5.5 Security Scanner Tests (`test_05_security_scanner.py`)

**Purpose**: Verify dangerous code patterns are blocked in unsafe mode.

#### Blocked Patterns

| Test ID | Test Name | Pattern Type | Priority |
|---------|-----------|--------------|----------|
| SS-001 | `test_block_environ_assignment` | Environment modification | P0 |
| SS-002 | `test_block_environ_update` | Environment modification | P0 |
| SS-003 | `test_block_putenv` | Environment modification | P0 |
| SS-010 | `test_block_exec` | Dynamic execution | P0 |
| SS-011 | `test_block_eval` | Dynamic execution | P0 |
| SS-012 | `test_block_compile` | Dynamic execution | P0 |
| SS-020 | `test_block_os_system` | Subprocess | P0 |
| SS-021 | `test_block_subprocess_run` | Subprocess | P0 |
| SS-022 | `test_block_subprocess_popen` | Subprocess | P0 |
| SS-030 | `test_block_aliased_system` | Aliased imports | P0 |
| SS-031 | `test_block_aliased_environ` | Aliased imports | P0 |
| SS-032 | `test_block_module_alias` | Aliased imports | P0 |

#### Allowed Patterns

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| SS-050 | `test_allow_numpy_operations` | NumPy is safe | P0 |
| SS-051 | `test_allow_print` | Basic print | P0 |
| SS-052 | `test_allow_arithmetic` | Basic math | P0 |
| SS-053 | `test_allow_os_path` | os.path operations | P1 |
| SS-054 | `test_allow_os_getcwd` | os.getcwd() | P1 |

---

### 5.6 Optional Features Tests (`test_06_optional_features.py`)

**Purpose**: Verify optional features work when enabled.

#### MeasureIt Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| OF-001 | `test_measureit_enable` | %mcp_option measureit | P1 |
| OF-002 | `test_measureit_tools_visible` | Tools list | P1 |
| OF-003 | `test_measureit_get_status_no_sweeps` | measureit_get_status | P1 |
| OF-004 | `test_measureit_resources` | mcp_list_resources | P2 |

#### Database Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| OF-010 | `test_database_enable` | %mcp_option database | P1 |
| OF-011 | `test_database_tools_visible` | Tools list | P1 |
| OF-012 | `test_database_list_all_available_db` | database_list_all_available_db | P1 |
| OF-013 | `test_database_list_experiments` | database_list_experiments | P1 |
| OF-014 | `test_database_get_dataset_info` | database_get_dataset_info | P2 |
| OF-015 | `test_database_get_database_stats` | database_get_database_stats | P2 |

#### Dynamic Tools

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| OF-020 | `test_dynamictool_requires_dangerous` | %mcp_option dynamictool | P1 |
| OF-021 | `test_dynamictool_enable_in_dangerous` | %mcp_option dynamictool | P1 |
| OF-022 | `test_dynamic_list_tools` | dynamic_list_tools | P1 |
| OF-023 | `test_dynamic_register_tool` | dynamic_register_tool | P1 |
| OF-024 | `test_dynamic_call_registered_tool` | Registered tool | P1 |
| OF-025 | `test_dynamic_inspect_tool` | dynamic_inspect_tool | P2 |
| OF-026 | `test_dynamic_update_tool` | dynamic_update_tool | P2 |
| OF-027 | `test_dynamic_revoke_tool` | dynamic_revoke_tool | P1 |
| OF-028 | `test_dynamic_registry_stats` | dynamic_registry_stats | P2 |

---

### 5.7 Frontend Widget Tests (`test_07_frontend_widget.py`)

**Purpose**: Verify JupyterLab toolbar widget functionality.

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| FW-001 | `test_toolbar_visible_without_extension` | Widget appears automatically | P0 |
| FW-002 | `test_toolbar_visible_with_extension` | Widget remains after %load_ext | P0 |
| FW-010 | `test_status_indicator_stopped` | Shows "Stopped" before start | P0 |
| FW-011 | `test_status_indicator_running` | Shows "Running" after start | P0 |
| FW-012 | `test_status_indicator_after_stop` | Shows "Stopped" after stop | P0 |
| FW-020 | `test_mode_selector_options` | Shows Safe/Unsafe/Dangerous | P0 |
| FW-021 | `test_mode_selector_safe` | Can select safe mode | P0 |
| FW-022 | `test_mode_selector_unsafe` | Can select unsafe mode | P0 |
| FW-023 | `test_mode_selector_dangerous` | Can select dangerous mode | P0 |
| FW-024 | `test_mode_selector_disabled_when_running` | Mode selector disabled when running | P1 |
| FW-030 | `test_start_button_enabled_when_stopped` | Start enabled when stopped | P1 |
| FW-031 | `test_stop_restart_enabled_when_running` | Stop/Restart enabled when running | P1 |
| FW-032 | `test_start_button_click` | Start button starts server | P0 |
| FW-033 | `test_stop_button_click` | Stop button stops server | P0 |
| FW-034 | `test_restart_button_click` | Restart button restarts server | P1 |
| FW-040 | `test_options_panel_visible` | Options panel opens | P1 |
| FW-041 | `test_options_measureit_toggle` | Can toggle measureit | P1 |
| FW-042 | `test_options_database_toggle` | Can toggle database | P1 |
| FW-043 | `test_options_dynamictool_requires_dangerous` | Dynamictool shows requirement | P2 |
| FW-044 | `test_options_disabled_when_running` | Options disabled when running | P1 |
| FW-050 | `test_port_display` | Port displayed matches status | P1 |
| FW-060 | `test_kernel_restart_handling` | Widget updates on kernel restart | P1 |

---

### 5.8 Cell Targeting Tests (`test_08_cell_targeting.py`)

**Purpose**: Verify cell_id_notebook and index:N navigation features.

| Test ID | Test Name | Tool | Priority |
|---------|-----------|------|----------|
| CT-001 | `test_read_content_cell_id_notebooks_single` | notebook_read_content | P0 |
| CT-002 | `test_read_content_cell_id_notebooks_multiple` | notebook_read_content | P0 |
| CT-003 | `test_read_content_cell_id_notebooks_mixed_types` | notebook_read_content | P1 |
| CT-004 | `test_read_content_cell_id_notebooks_out_of_bounds` | notebook_read_content | P1 |
| CT-010 | `test_move_cursor_index_first` | notebook_move_cursor | P0 |
| CT-011 | `test_move_cursor_index_middle` | notebook_move_cursor | P0 |
| CT-012 | `test_move_cursor_index_last` | notebook_move_cursor | P0 |
| CT-013 | `test_move_cursor_index_invalid` | notebook_move_cursor | P1 |
| CT-020 | `test_delete_cell_by_positions` | notebook_delete_cell | P0 |
| CT-021 | `test_delete_cell_multiple_positions` | notebook_delete_cell | P1 |
| CT-022 | `test_delete_cell_out_of_bounds` | notebook_delete_cell | P1 |

---

### 5.9 Consent Dialog Tests (`test_09_consent_dialogs.py`)

**Purpose**: Verify consent dialog UI behavior.

| Test ID | Test Name | Description | Priority |
|---------|-----------|-------------|----------|
| CD-001 | `test_consent_dialog_appears` | Dialog appears for unsafe ops | P0 |
| CD-002 | `test_consent_dialog_content` | Shows operation details | P0 |
| CD-003 | `test_consent_dialog_buttons` | Approve and Deny buttons | P0 |
| CD-004 | `test_consent_dialog_modal` | Dialog is modal | P1 |
| CD-010 | `test_consent_deny_returns_error` | Deny returns consent_denied | P0 |
| CD-011 | `test_consent_deny_no_change` | Deny preserves state | P0 |
| CD-020 | `test_consent_approve_returns_success` | Approve returns success | P0 |
| CD-021 | `test_consent_approve_applies_change` | Approve executes operation | P0 |

---

## 6. Test Data Setup

### 6.1 Standard Test Notebook

Create a standard notebook structure for consistent testing:

```python
STANDARD_NOTEBOOK_CELLS = [
    {"type": "markdown", "source": "# Test Notebook Header"},
    {"type": "code", "source": "x = 1", "execute": True},
    {"type": "markdown", "source": "## Section 1"},
    {"type": "code", "source": "y = 2", "execute": True},
    {"type": "code", "source": "# unexecuted code cell", "execute": False},
    {"type": "markdown", "source": "## Section 2"},
    {"type": "code", "source": "z = x + y", "execute": True},
    {"type": "code", "source": 'print("hello")', "execute": True},
]
```

### 6.2 Variable Test Data

```python
VARIABLE_TEST_SETUP = '''
import numpy as np
import pandas as pd

x = 42
my_list = [1, 2, 3]
my_dict = {"a": 1, "b": 2}
class MyClass: pass
obj = MyClass()

arr = np.array([[1, 2, 3], [4, 5, 6]])
df = pd.DataFrame({'col1': [1, 2, 3], 'col2': ['a', 'b', 'c']})
large_arr = np.zeros((1000, 1000))
'''
```

---

## 7. CI Integration

### 7.1 GitHub Actions Workflow

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -e .[dev]
          pip install playwright pytest-playwright
          playwright install chromium
          playwright install-deps

      - name: Start JupyterLab
        run: |
          jupyter lab --no-browser --port=8888 --NotebookApp.token='' &
          sleep 10

      - name: Run E2E tests
        run: |
          pytest tests/e2e/ -v --browser chromium --headed=false
        env:
          JUPYTER_TOKEN: ""

      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-artifacts
          path: |
            test-results/
            playwright-report/
```

### 7.2 Playwright Configuration

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
addopts = "--browser chromium"
testpaths = ["tests/e2e"]

# Playwright specific
[tool.playwright]
headless = true
slow_mo = 100
timeout = 30000
```

### 7.3 Artifact Collection

Configure Playwright to capture:
- Screenshots on failure
- Video recording (optional)
- Trace files for debugging

```python
# conftest.py
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when == "call" and rep.failed:
        page = item.funcargs.get("notebook_page")
        if page:
            page.screenshot(path=f"test-results/{item.name}-failure.png")
```

---

## 8. Known Issues to Verify

These issues were noted in previous testing cycles and should be verified as fixed:

| Issue | Description | Test IDs |
|-------|-------------|----------|
| Multi-delete | notebook_delete_cell deleted 2-5 cells instead of 1 | UM-040, UM-041 |
| Multi-patch | notebook_apply_patch applied 2-3 times | UM-050 |
| Markdown content | notebook_add_cell content not set for markdown | UM-031 |
| Invalid target | notebook_move_cursor returns success for invalid target | CT-013 |

---

## 9. Test Priority Definitions

| Priority | Description | When to Run |
|----------|-------------|-------------|
| P0 | Critical path, must pass | Every PR, every commit |
| P1 | Important functionality | Every PR |
| P2 | Edge cases, nice-to-have | Nightly/weekly |

---

## 10. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Set up `tests/e2e/` directory structure
- [ ] Implement `conftest.py` with core fixtures
- [ ] Implement helper functions in `helpers/`
- [ ] Create `test_01_server_lifecycle.py` (P0 tests)
- [ ] Verify CI workflow runs

### Phase 2: Core Safe Mode (Week 2)
- [ ] Implement `test_02_safe_mode_tools.py` (P0 tests)
- [ ] Implement mock QCodes station fixture
- [ ] Add variable test data setup

### Phase 3: Unsafe & Dangerous Mode (Week 3)
- [ ] Implement `test_03_unsafe_mode_tools.py`
- [ ] Implement `test_04_dangerous_mode.py`
- [ ] Implement `test_09_consent_dialogs.py`

### Phase 4: Security & Features (Week 4)
- [ ] Implement `test_05_security_scanner.py`
- [ ] Implement `test_06_optional_features.py`

### Phase 5: Frontend & Cell Targeting (Week 5)
- [ ] Implement `test_07_frontend_widget.py`
- [ ] Implement `test_08_cell_targeting.py`

### Phase 6: Polish & P1/P2 Tests (Week 6)
- [ ] Add remaining P1 tests
- [ ] Add P2 edge case tests
- [ ] Performance optimization
- [ ] Documentation updates

---

## 11. Test Execution Commands

```bash
# Run all E2E tests
pytest tests/e2e/ -v

# Run specific test module
pytest tests/e2e/test_01_server_lifecycle.py -v

# Run with headed browser (for debugging)
pytest tests/e2e/ -v --headed

# Run only P0 tests
pytest tests/e2e/ -v -m "p0"

# Run with coverage
pytest tests/e2e/ -v --cov=instrmcp --cov-report=html

# Run with Playwright trace
pytest tests/e2e/ -v --tracing=on
```

---

## 12. Appendix: Expected Tool Lists

### Safe Mode Tools
- `mcp_list_resources`
- `mcp_get_resource`
- `notebook_server_status`
- `notebook_list_variables`
- `notebook_read_variable`
- `notebook_read_active_cell`
- `notebook_read_active_cell_output`
- `notebook_read_content`
- `notebook_move_cursor`
- `qcodes_instrument_info`
- `qcodes_get_parameter_info`
- `qcodes_get_parameter_values`

### Additional Unsafe Mode Tools
- `notebook_update_editing_cell`
- `notebook_execute_active_cell`
- `notebook_add_cell`
- `notebook_delete_cell`
- `notebook_apply_patch`

### Optional MeasureIt Tools
- `measureit_get_status`
- `measureit_wait_for_sweep`
- `measureit_kill_sweep`

### Optional Database Tools
- `database_list_all_available_db`
- `database_list_experiments`
- `database_get_dataset_info`
- `database_get_database_stats`

### Optional Dynamic Tools (Dangerous Mode)
- `dynamic_register_tool`
- `dynamic_update_tool`
- `dynamic_revoke_tool`
- `dynamic_list_tools`
- `dynamic_inspect_tool`
- `dynamic_registry_stats`
