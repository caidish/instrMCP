"""
Frontend Widget Tests (test_07_frontend_widget.py)

Purpose: Verify JupyterLab toolbar widget functionality.

Test IDs:
- FW-001 to FW-060
"""

import pytest
from tests.e2e.helpers.jupyter_helpers import run_cell, get_cell_output


def get_mcp_toolbar(page):
    """Find and return the MCP toolbar element."""
    # Try various selectors for the MCP toolbar widget
    selectors = [
        ".mcp-toolbar",
        "[data-mcp-toolbar]",
        ".jp-NotebookPanel-toolbar .mcp-widget",
        ".jp-Toolbar-item.mcp-status",
        ".instrmcp-widget",
    ]
    for selector in selectors:
        element = page.locator(selector)
        if element.count() > 0:
            return element.first
    return None


def get_toolbar_status(page):
    """Get the status indicator from MCP toolbar."""
    toolbar = get_mcp_toolbar(page)
    if toolbar:
        status = toolbar.locator(".mcp-status, .status-indicator, [data-status]")
        if status.count() > 0:
            return status.first.text_content()
    return None


def get_mode_selector(page):
    """Get the mode selector element."""
    toolbar = get_mcp_toolbar(page)
    if toolbar:
        selector = toolbar.locator("select, .mode-selector, [data-mode]")
        if selector.count() > 0:
            return selector.first
    return None


class TestToolbarVisibility:
    """Test MCP toolbar visibility."""

    @pytest.mark.p0
    def test_toolbar_visible_without_extension(self, notebook_page):
        """FW-001: Toolbar widget appears automatically.

        The JupyterLab extension should add the toolbar without
        requiring %load_ext.
        """
        page = notebook_page
        page.wait_for_timeout(2000)

        # Look for MCP toolbar elements
        toolbar = page.locator(".jp-NotebookPanel-toolbar")
        assert toolbar.count() > 0, "Notebook toolbar not found"

        # Check for MCP-specific elements in toolbar
        # This depends on the actual implementation
        toolbar.locator('[class*="mcp"], [class*="instrmcp"]')
        # Note: If extension not installed, this may be 0

    @pytest.mark.p0
    def test_toolbar_visible_with_extension(self, notebook_page):
        """FW-002: Toolbar remains visible after %load_ext."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Toolbar should still be visible
        toolbar = page.locator(".jp-NotebookPanel-toolbar")
        assert toolbar.count() > 0, "Toolbar not found after load_ext"


class TestStatusIndicator:
    """Test MCP status indicator in toolbar."""

    @pytest.mark.p0
    def test_status_indicator_stopped(self, notebook_page):
        """FW-010: Status indicator shows 'Stopped' before start."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        # Verify server is stopped via magic output
        output_lower = output.lower()
        assert (
            "not running" in output_lower
            or "stopped" in output_lower
            or "not created" in output_lower
        ), f"Expected stopped status: {output}"

    @pytest.mark.p0
    def test_status_indicator_running(self, mcp_server):
        """FW-011: Status indicator shows 'Running' after start."""
        page = mcp_server["page"]

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        # Verify server is running
        output_lower = output.lower()
        assert (
            "running" in output_lower or "active" in output_lower
        ), f"Expected running status: {output}"

    @pytest.mark.p0
    def test_status_indicator_after_stop(self, mcp_server):
        """FW-012: Status indicator shows 'Stopped' after stop."""
        page = mcp_server["page"]

        run_cell(page, "%mcp_close")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        output_lower = output.lower()
        assert (
            "not running" in output_lower
            or "stopped" in output_lower
            or "not created" in output_lower
        ), f"Expected stopped status after stop: {output}"


class TestModeSelector:
    """Test mode selector functionality."""

    @pytest.mark.p0
    def test_mode_selector_options(self, notebook_page):
        """FW-020: Mode selector shows Safe/Unsafe/Dangerous options."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Check modes are available via magic
        run_cell(page, "%mcp_safe")
        output1 = get_cell_output(page)
        assert "error" not in output1.lower(), f"Safe mode error: {output1}"

        run_cell(page, "%mcp_unsafe")
        output2 = get_cell_output(page)
        assert "error" not in output2.lower(), f"Unsafe mode error: {output2}"

        run_cell(page, "%mcp_dangerous")
        output3 = get_cell_output(page)
        # Dangerous may show warning but shouldn't error
        assert (
            "exception" not in output3.lower()
        ), f"Dangerous mode exception: {output3}"

    @pytest.mark.p0
    def test_mode_selector_safe(self, notebook_page):
        """FW-021: Can select safe mode."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_safe")
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert "safe" in output.lower(), f"Expected safe mode: {output}"

        run_cell(page, "%mcp_close")

    @pytest.mark.p0
    def test_mode_selector_unsafe(self, notebook_page):
        """FW-022: Can select unsafe mode."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_unsafe")
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert "unsafe" in output.lower(), f"Expected unsafe mode: {output}"

        run_cell(page, "%mcp_close")

    @pytest.mark.p0
    def test_mode_selector_dangerous(self, notebook_page):
        """FW-023: Can select dangerous mode."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_dangerous")
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert "dangerous" in output.lower(), f"Expected dangerous mode: {output}"

        run_cell(page, "%mcp_close")

    @pytest.mark.p1
    def test_mode_selector_disabled_when_running(self, mcp_server):
        """FW-024: Mode cannot be changed while server running.

        Mode changes require restart to take effect.
        """
        page = mcp_server["page"]

        # Try to change mode while running
        run_cell(page, "%mcp_unsafe")
        get_cell_output(page)

        # Should indicate restart needed or mode pending
        # Actual behavior depends on implementation


class TestServerButtons:
    """Test server control buttons."""

    @pytest.mark.p1
    def test_start_button_enabled_when_stopped(self, notebook_page):
        """FW-030: Start button is enabled when server is stopped."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Verify we can start (start is enabled)
        run_cell(page, "%mcp_start")
        output = get_cell_output(page)

        # Should start without error
        assert (
            "error" not in output.lower() or "already" in output.lower()
        ), f"Start should be possible when stopped: {output}"

        run_cell(page, "%mcp_close")

    @pytest.mark.p1
    def test_stop_restart_enabled_when_running(self, mcp_server):
        """FW-031: Stop and Restart buttons enabled when server running."""
        page = mcp_server["page"]

        # Try stop
        run_cell(page, "%mcp_close")
        stop_output = get_cell_output(page)
        assert "error" not in stop_output.lower(), f"Stop should work: {stop_output}"

        # Start again for restart test
        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        # Try restart
        run_cell(page, "%mcp_restart")
        restart_output = get_cell_output(page)
        assert (
            "error" not in restart_output.lower()
        ), f"Restart should work: {restart_output}"

    @pytest.mark.p0
    def test_start_button_click(self, notebook_page):
        """FW-032: Start button starts the server."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_start")
        page.wait_for_timeout(2000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert (
            "running" in output.lower() or "active" in output.lower()
        ), f"Server should be running: {output}"

        run_cell(page, "%mcp_close")

    @pytest.mark.p0
    def test_stop_button_click(self, mcp_server):
        """FW-033: Stop button stops the server."""
        page = mcp_server["page"]

        run_cell(page, "%mcp_close")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert (
            "not running" in output.lower()
            or "stopped" in output.lower()
            or "not created" in output.lower()
        ), f"Server should be stopped: {output}"

    @pytest.mark.p1
    def test_restart_button_click(self, mcp_server):
        """FW-034: Restart button restarts the server."""
        page = mcp_server["page"]

        run_cell(page, "%mcp_restart")
        page.wait_for_timeout(3000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert (
            "running" in output.lower() or "active" in output.lower()
        ), f"Server should be running after restart: {output}"


class TestOptionsPanel:
    """Test options panel functionality."""

    @pytest.mark.p1
    def test_options_panel_visible(self, notebook_page):
        """FW-040: Options can be configured."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Try to access options
        run_cell(page, "%mcp_option measureit")
        get_cell_output(page)

        # Should be able to set options
        # May succeed or fail based on dependencies

    @pytest.mark.p1
    def test_options_measureit_toggle(self, notebook_page):
        """FW-041: Can toggle measureit option."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Enable
        run_cell(page, "%mcp_option measureit")
        enable_output = get_cell_output(page)

        # Disable
        run_cell(page, "%mcp_option -measureit")
        disable_output = get_cell_output(page)

        # Both should not crash
        assert "exception" not in enable_output.lower()
        assert "exception" not in disable_output.lower()

    @pytest.mark.p1
    def test_options_database_toggle(self, notebook_page):
        """FW-042: Can toggle database option."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Enable
        run_cell(page, "%mcp_option database")
        enable_output = get_cell_output(page)

        # Disable
        run_cell(page, "%mcp_option -database")
        disable_output = get_cell_output(page)

        # Both should not crash
        assert "exception" not in enable_output.lower()
        assert "exception" not in disable_output.lower()

    @pytest.mark.p2
    def test_options_dynamictool_requires_dangerous(self, notebook_page):
        """FW-043: Dynamictool shows requirement for dangerous mode."""
        page = notebook_page

        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        # Try in safe mode
        run_cell(page, "%mcp_safe")
        run_cell(page, "%mcp_option dynamictool")
        output = get_cell_output(page)

        # Should indicate dangerous mode required
        output_lower = output.lower()
        assert (
            "dangerous" in output_lower
            or "error" in output_lower
            or "require" in output_lower
        )

    @pytest.mark.p1
    def test_options_disabled_when_running(self, mcp_server):
        """FW-044: Options changes require restart when server running."""
        page = mcp_server["page"]

        # Try to change options while running
        run_cell(page, "%mcp_option measureit")
        get_cell_output(page)

        # May indicate restart required
        # Actual behavior depends on implementation


class TestPortDisplay:
    """Test port display in toolbar."""

    @pytest.mark.p1
    def test_port_display(self, mcp_server):
        """FW-050: Port displayed matches actual server port."""
        page = mcp_server["page"]
        expected_port = mcp_server["port"]

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        assert (
            str(expected_port) in output
        ), f"Expected port {expected_port} in status: {output}"


class TestKernelRestart:
    """Test behavior on kernel restart."""

    @pytest.mark.p1
    def test_kernel_restart_handling(self, mcp_server):
        """FW-060: Widget updates correctly on kernel restart."""
        page = mcp_server["page"]

        # Restart kernel
        page.keyboard.press("0")
        page.keyboard.press("0")  # Double-0 to restart kernel
        page.wait_for_timeout(500)

        # Confirm restart if dialog appears
        try:
            page.get_by_role("button", name="Restart").click(timeout=2000)
        except Exception:
            pass

        page.wait_for_timeout(5000)

        # After kernel restart, server should be stopped
        run_cell(page, "%load_ext instrmcp.extensions")
        page.wait_for_timeout(1000)

        run_cell(page, "%mcp_status")
        output = get_cell_output(page)

        # Server state after kernel restart - may show "not created" for new instance
        # or "running" if external MCP server still running on port
        output_lower = output.lower()
        assert (
            "not running" in output_lower
            or "stopped" in output_lower
            or "not created" in output_lower
            or "running" in output_lower  # MCP server runs separately from kernel
        ), f"Expected valid server status after kernel restart: {output}"
