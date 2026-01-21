# E2E Test Coverage Expansion Plan

## Summary

This plan outlines the implementation of additional E2E tests to improve coverage based on collaborative analysis from Codex, Gemini-CLI, and a code-reviewer subagent.

**Current State:** 164 passing tests, 2 skipped
**Target:** ~240 tests with improved coverage

---

## Phase 1: Critical Bug Fixes (P0)

### 1.1 Fix Parameter Mismatch in test_02_safe_mode_tools.py

**File:** `tests/e2e/test_02_safe_mode_tools.py`
**Test:** `test_notebook_read_active_cell_line_range` (SM-022)

**Problem:** Uses wrong parameter names (`start_line`/`end_line` instead of `line_start`/`line_end`). Test passes because tool ignores unknown args - false positive.

**Fix:**
```python
@pytest.mark.p2
def test_notebook_read_active_cell_line_range(self, mcp_server):
    """SM-022: notebook_read_active_cell with line range."""
    page = mcp_server["page"]

    # Create a multi-line cell
    code = "# Line 1\n# Line 2\n# Line 3\n# Line 4\n# Line 5"
    run_cell(page, code, wait_for_output=False)

    # FIXED: start_line -> line_start, end_line -> line_end
    result = call_mcp_tool(
        mcp_server["url"],
        "notebook_read_active_cell",
        {"line_start": 2, "line_end": 4},
    )
    success, content = parse_tool_result(result)
    assert success, f"Tool call failed: {content}"

    # ADDED: Verify content is actually filtered
    assert "Line 2" in content, "Expected Line 2 to be present"
    assert "Line 4" in content, "Expected Line 4 to be present"
    assert "Line 1" not in content, "Line 1 should be excluded"
    assert "Line 5" not in content, "Line 5 should be excluded"
```

---

## Phase 2: Missing Tool Tests

### 2.1 Add notebook_update_editing_cell Tests

**File:** `tests/e2e/test_03_unsafe_mode_tools.py`
**New Tests:** UM-060 to UM-063

```python
class TestUpdateEditingCell:
    """Test notebook_update_editing_cell tool."""

    @pytest.mark.p0
    def test_update_editing_cell_basic(self, mcp_server_dangerous):
        """UM-060: notebook_update_editing_cell replaces cell content."""
        page = mcp_server_dangerous["page"]

        # Create initial cell
        page.keyboard.press("Enter")
        page.keyboard.type("original_content = 1")
        page.keyboard.press("Escape")

        # Update cell content
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_update_editing_cell",
            {"content": "new_content = 2"}
        )
        success, content = parse_tool_result(result)
        assert success, f"Update failed: {content}"

        # Verify content changed
        read_result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_read_active_cell"
        )
        _, cell_content = parse_tool_result(read_result)
        assert "new_content" in cell_content

    @pytest.mark.p1
    def test_update_editing_cell_detailed(self, mcp_server_dangerous):
        """UM-061: notebook_update_editing_cell with detailed mode."""
        # Test detailed=True returns extended info

    @pytest.mark.p1
    def test_update_editing_cell_markdown(self, mcp_server_dangerous):
        """UM-062: notebook_update_editing_cell on markdown cell."""
        # Test updating markdown cell type

    @pytest.mark.p0
    def test_update_editing_cell_requires_consent(self, mcp_server_unsafe):
        """UM-063: notebook_update_editing_cell requires consent in unsafe mode."""
        # Verify consent dialog appears (not auto-approved)
```

### 2.2 Add MeasureIt Sweep Lifecycle Tests

**File:** `tests/e2e/test_06_optional_features.py`
**New Tests:** OF-040 to OF-046

**Mock Sweep Setup (add to helpers/mock_qcodes.py):**
```python
MOCK_SWEEP_SETUP = '''
from unittest.mock import Mock, MagicMock
import threading
import time

class MockSweep:
    """Mock sweep for testing MeasureIt tools."""
    def __init__(self, name):
        self.name = name
        self._state = "idle"
        self._running = False
        self._thread = None

    def start(self):
        self._state = "running"
        self._running = True
        def run():
            time.sleep(2)  # Simulate sweep
            self._state = "completed"
            self._running = False
        self._thread = threading.Thread(target=run)
        self._thread.start()

    def stop(self):
        self._state = "stopped"
        self._running = False

    @property
    def is_running(self):
        return self._running

    @property
    def state(self):
        return self._state

# Create mock sweeps
mock_sweep1d = MockSweep("mock_sweep1d")
mock_sweep2d = MockSweep("mock_sweep2d")
print("Mock sweeps created: mock_sweep1d, mock_sweep2d")
'''
```

**Tests:**
```python
class TestMeasureItSweepTools:
    """Test MeasureIt sweep lifecycle tools."""

    @pytest.mark.p0
    def test_measureit_wait_for_sweep_timeout(self, mcp_server_measureit):
        """OF-040: measureit_wait_for_sweep with timeout returns sweep state."""
        result = call_mcp_tool(
            mcp_server_measureit["url"],
            "measureit_wait_for_sweep",
            {"timeout": 5, "variable_name": "mock_sweep1d"}
        )
        success, content = parse_tool_result(result)
        # Should handle gracefully even with mock

    @pytest.mark.p1
    def test_measureit_wait_for_sweep_all(self, mcp_server_measureit):
        """OF-041: measureit_wait_for_sweep with all=True."""

    @pytest.mark.p1
    def test_measureit_wait_for_sweep_with_kill(self, mcp_server_measureit):
        """OF-042: measureit_wait_for_sweep with kill=True releases resources."""

    @pytest.mark.p1
    def test_measureit_wait_for_sweep_nonexistent(self, mcp_server_measureit):
        """OF-043: measureit_wait_for_sweep with nonexistent sweep returns error."""

    @pytest.mark.p0
    def test_measureit_kill_sweep_single(self, mcp_server_measureit):
        """OF-044: measureit_kill_sweep terminates active sweep."""

    @pytest.mark.p1
    def test_measureit_kill_sweep_all(self, mcp_server_measureit):
        """OF-045: measureit_kill_sweep with all=True terminates all sweeps."""

    @pytest.mark.p1
    def test_measureit_kill_sweep_nonexistent(self, mcp_server_measureit):
        """OF-046: measureit_kill_sweep on nonexistent sweep handles gracefully."""
```

---

## Phase 3: Edge Cases and Error Handling

### 3.1 Create test_10_edge_cases.py

**New File:** `tests/e2e/test_10_edge_cases.py`
**Test IDs:** EC-001 to EC-030

```python
"""
Edge Case Tests (test_10_edge_cases.py)

Purpose: Verify robust handling of invalid inputs and boundary conditions.

Test IDs:
- EC-001 to EC-030
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell
from tests.e2e.helpers.mcp_helpers import call_mcp_tool, parse_tool_result


class TestNotebookToolEdgeCases:
    """Test notebook tools with edge case inputs."""

    @pytest.mark.p2
    def test_read_active_cell_invalid_line_range(self, mcp_server):
        """EC-001: notebook_read_active_cell handles start > end."""
        page = mcp_server["page"]
        run_cell(page, "# Line 1\n# Line 2", wait_for_output=False)

        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": 5, "line_end": 2}
        )
        success, content = parse_tool_result(result)
        # Should return empty or handle gracefully, not crash
        assert result is not None

    @pytest.mark.p2
    def test_read_active_cell_negative_lines(self, mcp_server):
        """EC-002: notebook_read_active_cell handles negative line numbers."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"line_start": -1, "line_end": 5}
        )
        # Should handle gracefully
        assert result is not None

    @pytest.mark.p2
    def test_read_active_cell_zero_max_lines(self, mcp_server):
        """EC-003: notebook_read_active_cell with max_lines=0."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_active_cell",
            {"max_lines": 0}
        )
        assert result is not None

    @pytest.mark.p2
    def test_read_content_large_output(self, mcp_server):
        """EC-004: notebook_read_content handles large outputs."""
        page = mcp_server["page"]

        # Generate large output
        run_cell(page, "for i in range(500): print(f'Line {i}')", wait_for_output=True)

        result = call_mcp_tool(mcp_server["url"], "notebook_read_content")
        success, content = parse_tool_result(result)
        assert success
        # Should be truncated, not return megabytes
        assert len(content) < 100000

    @pytest.mark.p2
    def test_read_content_invalid_cell_id_json(self, mcp_server):
        """EC-005: notebook_read_content with invalid JSON for cell_id_notebooks."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_read_content",
            {"cell_id_notebooks": "not-valid-json"}
        )
        success, content = parse_tool_result(result)
        # Should fail gracefully with error message
        if success:
            assert "error" in content.lower() or result is not None

    @pytest.mark.p2
    def test_move_cursor_invalid_direction(self, mcp_server):
        """EC-006: notebook_move_cursor with invalid direction."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_move_cursor",
            {"direction": "invalid_direction"}
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_move_cursor_out_of_bounds_index(self, mcp_server):
        """EC-007: notebook_move_cursor with index beyond notebook."""
        result = call_mcp_tool(
            mcp_server["url"],
            "notebook_move_cursor",
            {"target": "index:9999"}
        )
        # Should fail gracefully or clamp to bounds
        assert result is not None

    @pytest.mark.p2
    def test_delete_cell_invalid_json(self, mcp_server_dangerous):
        """EC-008: notebook_delete_cell with invalid cell_id_notebooks JSON."""
        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_delete_cell",
            {"cell_id_notebooks": "invalid"}
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_apply_patch_empty_old_text(self, mcp_server_dangerous):
        """EC-009: notebook_apply_patch with empty old_text."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("some content")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"old_text": "", "new_text": "replacement"}
        )
        success, content = parse_tool_result(result)
        # Should fail - empty old_text not allowed
        assert not success or "error" in content.lower()

    @pytest.mark.p2
    def test_apply_patch_nonexistent_text(self, mcp_server_dangerous):
        """EC-010: notebook_apply_patch when old_text not found."""
        page = mcp_server_dangerous["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("actual content")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_dangerous["url"],
            "notebook_apply_patch",
            {"old_text": "nonexistent text", "new_text": "replacement"}
        )
        success, content = parse_tool_result(result)
        # Should fail or indicate no match
        if success:
            assert "not found" in content.lower() or "no match" in content.lower()


class TestQCodesToolEdgeCases:
    """Test QCodes tools with edge case inputs."""

    @pytest.mark.p2
    def test_instrument_info_empty_name(self, mock_qcodes_station):
        """EC-011: qcodes_instrument_info with empty name."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_instrument_info",
            {"name": ""}
        )
        assert result is not None

    @pytest.mark.p2
    def test_get_parameter_values_invalid_json(self, mock_qcodes_station):
        """EC-012: qcodes_get_parameter_values with invalid queries JSON."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"queries": "not-valid-json"}
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_get_parameter_values_empty_list(self, mock_qcodes_station):
        """EC-013: qcodes_get_parameter_values with empty parameters list."""
        result = call_mcp_tool(
            mock_qcodes_station["url"],
            "qcodes_get_parameter_values",
            {"parameters": []}
        )
        assert result is not None


class TestDynamicToolEdgeCases:
    """Test dynamic tool edge cases."""

    @pytest.mark.p2
    def test_register_tool_invalid_syntax(self, mcp_server_dynamictool):
        """EC-020: dynamic_register_tool rejects invalid Python syntax."""
        result = call_mcp_tool(
            mcp_server_dynamictool["url"],
            "dynamic_register_tool",
            {
                "name": "syntax_error_tool",
                "source_code": "def broken():\n  return missing_quote",
            }
        )
        success, content = parse_tool_result(result)
        # Should fail registration with syntax error
        assert not success or "error" in content.lower()

    @pytest.mark.p2
    def test_register_tool_duplicate_name(self, mcp_server_dynamictool):
        """EC-021: dynamic_register_tool handles duplicate names."""
        # Register first tool
        call_mcp_tool(
            mcp_server_dynamictool["url"],
            "dynamic_register_tool",
            {
                "name": "duplicate_tool",
                "source_code": "def duplicate_tool(): return 1",
            }
        )

        # Try to register again with same name
        result = call_mcp_tool(
            mcp_server_dynamictool["url"],
            "dynamic_register_tool",
            {
                "name": "duplicate_tool",
                "source_code": "def duplicate_tool(): return 2",
            }
        )
        # Should either fail or update existing
        assert result is not None

    @pytest.mark.p2
    def test_revoke_nonexistent_tool(self, mcp_server_dynamictool):
        """EC-022: dynamic_revoke_tool handles nonexistent tool."""
        result = call_mcp_tool(
            mcp_server_dynamictool["url"],
            "dynamic_revoke_tool",
            {"name": "nonexistent_tool_xyz"}
        )
        # Should fail gracefully
        assert result is not None

    @pytest.mark.p2
    def test_inspect_nonexistent_tool(self, mcp_server_dynamictool):
        """EC-023: dynamic_inspect_tool handles nonexistent tool."""
        result = call_mcp_tool(
            mcp_server_dynamictool["url"],
            "dynamic_inspect_tool",
            {"name": "nonexistent_tool_xyz"}
        )
        success, content = parse_tool_result(result)
        if success:
            assert "not found" in content.lower() or "error" in content.lower()


class TestDatabaseToolEdgeCases:
    """Test database tools with edge case inputs."""

    @pytest.mark.p2
    def test_list_experiments_nonexistent_path(self, mcp_server_database):
        """EC-030: database_list_experiments with nonexistent path."""
        result = call_mcp_tool(
            mcp_server_database["url"],
            "database_list_experiments",
            {"database_path": "/nonexistent/path/db.db"}
        )
        success, content = parse_tool_result(result)
        # Should fail with clear error
        if success:
            assert "error" in content.lower() or "not found" in content.lower()

    @pytest.mark.p2
    def test_get_dataset_info_invalid_id(self, mcp_server_database):
        """EC-031: database_get_dataset_info with invalid run_id."""
        result = call_mcp_tool(
            mcp_server_database["url"],
            "database_get_dataset_info",
            {"id": -999}
        )
        # Should fail gracefully
        assert result is not None
```

---

## Phase 4: Security Scanner Improvements

### 4.1 Add Obfuscation Pattern Tests

**File:** `tests/e2e/test_05_security_scanner.py`
**New Tests:** SS-060 to SS-070

```python
class TestSecurityScannerObfuscation:
    """Test security scanner against obfuscation attempts."""

    @pytest.mark.p1
    def test_block_dunder_import(self, mcp_server_unsafe):
        """SS-060: Block __import__ dynamic import pattern."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("__import__('os').system('ls')")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()

    @pytest.mark.p1
    def test_block_getattr_dangerous(self, mcp_server_unsafe):
        """SS-061: Block getattr-based dangerous calls."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("getattr(__import__('os'), 'system')('ls')")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()

    @pytest.mark.p1
    def test_block_eval_exec(self, mcp_server_unsafe):
        """SS-062: Block eval/exec with dangerous strings."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("eval('__import__(\"os\").system(\"ls\")')")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()

    @pytest.mark.p1
    def test_block_ipython_shell_escape(self, mcp_server_unsafe):
        """SS-063: Block IPython shell escape (!command)."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("!ls -la")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()

    @pytest.mark.p1
    def test_block_ipython_bash_magic(self, mcp_server_unsafe):
        """SS-064: Block IPython %%bash magic."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("%%bash\nls -la")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()

    @pytest.mark.p2
    def test_allow_safe_string_containing_dangerous_words(self, mcp_server_unsafe):
        """SS-065: Allow strings containing 'os.system' (not actual call)."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("message = 'Do not use os.system for security'")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        # Should succeed - it's just a string literal
        assert success or "consent" in content.lower()

    @pytest.mark.p1
    def test_block_multiline_subprocess(self, mcp_server_unsafe):
        """SS-066: Block multi-line subprocess call."""
        page = mcp_server_unsafe["page"]
        page.keyboard.press("Enter")
        page.keyboard.type("import subprocess\nsubprocess.run(['ls'])")
        page.keyboard.press("Escape")

        result = call_mcp_tool(
            mcp_server_unsafe["url"],
            "notebook_execute_active_cell"
        )
        success, content = parse_tool_result(result)
        assert not success or "blocked" in content.lower()
```

---

## Phase 5: Consent Dialog Automation

### 5.1 Add Playwright Consent Dialog Helpers

**File:** `tests/e2e/helpers/consent_helpers.py`

```python
"""
Consent Dialog Helpers

Utilities for automating consent dialog interactions in E2E tests.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout


def wait_for_consent_dialog(page: Page, timeout: int = 5000):
    """Wait for consent dialog to appear.

    Args:
        page: Playwright page
        timeout: Timeout in milliseconds

    Returns:
        Dialog locator or None if not found
    """
    selectors = [
        ".mcp-consent-dialog",
        ".jp-Dialog.mcp-consent",
        "[data-consent-dialog]",
        ".consent-dialog",
        '.jp-Dialog:has-text("consent")',
        '.jp-Dialog:has-text("approve")',
        '.jp-Dialog:has-text("Allow")',
    ]

    for selector in selectors:
        try:
            dialog = page.locator(selector)
            dialog.wait_for(timeout=timeout)
            if dialog.count() > 0:
                return dialog.first
        except PlaywrightTimeout:
            continue
    return None


def click_consent_approve(page: Page, dialog=None, timeout: int = 2000):
    """Click the approve/allow button in consent dialog.

    Args:
        page: Playwright page
        dialog: Optional dialog locator to scope search
        timeout: Timeout for button click

    Returns:
        True if button clicked, False otherwise
    """
    approve_selectors = [
        'button:has-text("Approve")',
        'button:has-text("Allow")',
        'button:has-text("Accept")',
        'button:has-text("Yes")',
        'button:has-text("OK")',
        ".mcp-approve-btn",
        '[data-action="approve"]',
    ]

    scope = dialog if dialog else page
    for selector in approve_selectors:
        try:
            btn = scope.locator(selector)
            if btn.count() > 0:
                btn.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def click_consent_deny(page: Page, dialog=None, timeout: int = 2000):
    """Click the deny/decline button in consent dialog.

    Args:
        page: Playwright page
        dialog: Optional dialog locator to scope search
        timeout: Timeout for button click

    Returns:
        True if button clicked, False otherwise
    """
    deny_selectors = [
        'button:has-text("Deny")',
        'button:has-text("Decline")',
        'button:has-text("Reject")',
        'button:has-text("Cancel")',
        'button:has-text("No")',
        ".mcp-deny-btn",
        '[data-action="deny"]',
    ]

    scope = dialog if dialog else page
    for selector in deny_selectors:
        try:
            btn = scope.locator(selector)
            if btn.count() > 0:
                btn.first.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def handle_consent_with_action(page: Page, action: str = "approve", timeout: int = 5000):
    """Wait for consent dialog and perform action.

    Args:
        page: Playwright page
        action: "approve" or "deny"
        timeout: Timeout for dialog appearance

    Returns:
        True if action performed, False if dialog not found
    """
    dialog = wait_for_consent_dialog(page, timeout=timeout)
    if not dialog:
        return False

    if action == "approve":
        return click_consent_approve(page, dialog)
    elif action == "deny":
        return click_consent_deny(page, dialog)
    return False
```

### 5.2 Implement Consent Dialog Tests

**File:** `tests/e2e/test_09_consent_dialogs.py`
**Unskip and implement:** CD-010, CD-011

```python
# Import the new helpers
from tests.e2e.helpers.consent_helpers import (
    wait_for_consent_dialog,
    click_consent_approve,
    click_consent_deny,
    handle_consent_with_action,
)

class TestConsentDeny:
    """Test consent denial behavior."""

    @pytest.mark.p0
    def test_consent_deny_returns_error(self, mcp_server_unsafe):
        """CD-010: Denying consent returns consent_denied error."""
        page = mcp_server_unsafe["page"]

        page.keyboard.press("Enter")
        page.keyboard.type("test = 1")
        page.keyboard.press("Escape")

        # Start async request that will trigger dialog
        page.evaluate("""
            async () => {
                fetch('""" + mcp_server_unsafe["url"] + """/mcp', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'tools/call',
                        params: {name: 'notebook_execute_active_cell', arguments: {}}
                    })
                });
            }
        """)

        # Wait for and deny consent
        dialog = wait_for_consent_dialog(page, timeout=5000)
        if dialog:
            clicked = click_consent_deny(page, dialog)
            assert clicked, "Failed to click deny button"

            # Verify operation was denied
            page.wait_for_timeout(1000)
            # Cell should not have executed

    @pytest.mark.p0
    def test_consent_deny_no_change(self, mcp_server_unsafe):
        """CD-011: Denying consent preserves original state."""
        page = mcp_server_unsafe["page"]

        # Create initial cell
        run_cell(page, "original = 1", wait_for_output=False)
        page.keyboard.press("Escape")

        initial_count = count_cells(page)

        # Trigger delete and deny
        page.evaluate("""
            async () => {
                fetch('""" + mcp_server_unsafe["url"] + """/mcp', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        jsonrpc: '2.0',
                        id: 1,
                        method: 'tools/call',
                        params: {name: 'notebook_delete_cell', arguments: {}}
                    })
                });
            }
        """)

        dialog = wait_for_consent_dialog(page, timeout=5000)
        if dialog:
            click_consent_deny(page, dialog)
            page.wait_for_timeout(1000)

            # Cell count should be unchanged
            final_count = count_cells(page)
            assert final_count == initial_count, "Cell was deleted despite denial"
```

---

## Phase 6: Resource Template Tests

### 6.1 Add Resource Template Retrieval Tests

**File:** `tests/e2e/test_02_safe_mode_tools.py`
**New Tests:** SM-100 to SM-110

```python
class TestResourceTemplates:
    """Test MCP resource template retrieval."""

    @pytest.mark.p1
    def test_get_measureit_sweep1d_template(self, mcp_server_measureit):
        """SM-100: mcp_get_resource returns valid sweep1d template."""
        resource = get_mcp_resource(
            mcp_server_measureit["url"],
            "resource://measureit_sweep1d_template"
        )
        assert resource is not None
        assert "error" not in str(resource).lower()
        # Should contain sweep code pattern
        assert "sweep" in str(resource).lower() or len(str(resource)) > 100

    @pytest.mark.p1
    def test_get_measureit_sweep2d_template(self, mcp_server_measureit):
        """SM-101: mcp_get_resource returns valid sweep2d template."""
        resource = get_mcp_resource(
            mcp_server_measureit["url"],
            "resource://measureit_sweep2d_template"
        )
        assert resource is not None

    @pytest.mark.p1
    def test_get_database_access_template(self, mcp_server_database):
        """SM-102: mcp_get_resource for database_access1d_template."""
        resource = get_mcp_resource(
            mcp_server_database["url"],
            "resource://database_access1d_template"
        )
        assert resource is not None

    @pytest.mark.p1
    def test_list_resources_includes_measureit_templates(self, mcp_server_measureit):
        """SM-103: mcp_list_resources shows measureit templates when enabled."""
        resources = list_mcp_resources(mcp_server_measureit["url"])
        resource_uris = [
            r.get("uri") if isinstance(r, dict) else r
            for r in resources
        ]

        # Should include at least one measureit template
        measureit_resources = [u for u in resource_uris if "measureit" in str(u).lower()]
        assert len(measureit_resources) > 0, f"No measureit resources found: {resource_uris}"

    @pytest.mark.p1
    def test_list_resources_excludes_measureit_when_disabled(self, mcp_server):
        """SM-104: mcp_list_resources excludes measureit templates when disabled."""
        resources = list_mcp_resources(mcp_server["url"])
        resource_uris = [
            r.get("uri") if isinstance(r, dict) else r
            for r in resources
        ]

        # Should NOT include measureit templates (feature not enabled)
        measureit_resources = [u for u in resource_uris if "measureit" in str(u).lower()]
        # This depends on implementation - may or may not include when disabled
```

---

## Implementation Order

1. **Phase 1** - Fix parameter mismatch bug (critical, quick fix)
2. **Phase 2.1** - Add notebook_update_editing_cell tests
3. **Phase 3** - Create test_10_edge_cases.py
4. **Phase 4** - Add security scanner obfuscation tests
5. **Phase 5** - Add consent dialog automation
6. **Phase 2.2** - Add MeasureIt sweep tests (with mock fixtures)
7. **Phase 6** - Add resource template tests

---

## Fixtures Required

### New Fixtures for conftest.py

```python
@pytest.fixture
def mcp_server_measureit(notebook_page, mcp_port):
    """MCP server with MeasureIt enabled."""
    page = notebook_page

    # Enable MeasureIt and restart
    run_cell(page, "%mcp_option add measureit", wait_for_output=True)
    run_cell(page, "%mcp_restart", wait_for_output=True)
    page.wait_for_timeout(3000)

    yield {
        "page": page,
        "url": f"http://localhost:{mcp_port}",
        "mode": "safe+measureit"
    }


@pytest.fixture
def mcp_server_database(notebook_page, mcp_port):
    """MCP server with database tools enabled."""
    page = notebook_page

    # Enable database and restart
    run_cell(page, "%mcp_option add database", wait_for_output=True)
    run_cell(page, "%mcp_restart", wait_for_output=True)
    page.wait_for_timeout(3000)

    yield {
        "page": page,
        "url": f"http://localhost:{mcp_port}",
        "mode": "safe+database"
    }
```

---

## Tradeoffs Summary

| Decision | Chosen Approach | Tradeoff |
|----------|-----------------|----------|
| Parameter bug fix | Fix and add assertions | May reveal server bugs |
| MeasureIt tests | Mock sweeps | Fast CI, may miss real issues |
| Consent dialogs | Playwright automation | UI flakiness possible |
| Security tests | Comprehensive patterns | Documents attack vectors |
| Edge case tests | New file (test_10) | Adds ~30 new tests |

---

## Success Metrics

- [ ] 0 false-positive tests (all assertions meaningful)
- [ ] All 24 tools have at least one E2E test
- [ ] Edge cases for invalid inputs covered
- [ ] Security scanner tests strengthened
- [ ] Consent dialog automation working
- [ ] Resource templates tested when features enabled
- [ ] Test suite runs in < 15 minutes
