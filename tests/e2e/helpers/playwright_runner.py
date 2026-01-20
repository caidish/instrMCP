"""
Playwright browser automation for notebook execution.
"""

from __future__ import annotations

import os
from urllib.parse import quote


def _reset_jupyterlab_workspace(page, base_url: str, token: str) -> None:
    """Reset JupyterLab workspace to ensure clean state.

    This closes all open tabs/notebooks, shuts down all kernels, and resets
    the workspace layout to prevent interference from previous sessions.

    Args:
        page: Playwright page object
        base_url: JupyterLab base URL
        token: Authentication token
    """
    # Navigate to JupyterLab main page with reset parameter
    lab_url = f"{base_url}/lab?token={token}&reset"
    page.goto(lab_url, wait_until="domcontentloaded", timeout=120000)

    # Wait for JupyterLab to be ready
    page.wait_for_selector(".jp-LabShell", timeout=60000)
    page.wait_for_timeout(2000)  # Give JupyterLab time to fully initialize

    # Reset workspace via JavaScript - close all activities and shut down kernels
    page.evaluate("""
() => {
    const app = window.jupyterapp || window.jupyterlab || window.jupyterApp || window.jupyterLab;
    if (!app) return false;

    // Shut down ALL running kernels first - this is critical!
    if (app.serviceManager && app.serviceManager.sessions) {
        app.serviceManager.sessions.running().then(sessions => {
            sessions.forEach(session => {
                try {
                    app.serviceManager.sessions.shutdown(session.id);
                } catch(e) {}
            });
        });
    }

    // Close all open tabs/activities in all areas
    if (app.shell) {
        // Close main area widgets
        if (app.shell.widgets) {
            const mainWidgets = Array.from(app.shell.widgets('main'));
            mainWidgets.forEach(w => {
                try { w.close(); } catch(e) {}
            });
        }

        // Also try closing via closeAll command
        if (app.commands && app.commands.hasCommand('application:close-all')) {
            app.commands.execute('application:close-all');
        }
    }

    // Clear any cached notebook state
    if (app.commands) {
        // Reset workspace layout
        if (app.commands.hasCommand('application:reset-layout')) {
            app.commands.execute('application:reset-layout');
        }
    }

    return true;
}
""")
    page.wait_for_timeout(2000)  # Wait for kernels to shut down and workspace reset

    # Handle any "Don't Save" dialogs that might appear
    for _ in range(3):  # Try multiple times in case dialogs keep appearing
        try:
            dont_save_btn = page.locator('button:has-text("Don\'t Save")')
            if dont_save_btn.count() > 0:
                dont_save_btn.first.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass

        try:
            discard_btn = page.locator('button:has-text("Discard")')
            if discard_btn.count() > 0:
                discard_btn.first.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass

        # Also handle "Shut Down" dialog for kernels
        try:
            shutdown_btn = page.locator('button:has-text("Shut Down")')
            if shutdown_btn.count() > 0:
                shutdown_btn.first.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass


def run_notebook_standalone(
    base_url: str,
    token: str,
    notebook_rel: str,
    cell_wait_ms: int = 1000,
) -> None:
    """Run a notebook via Playwright browser automation (standalone mode).

    Creates its own browser context - use this for fixtures that need
    isolation from pytest-playwright.

    Args:
        base_url: JupyterLab base URL
        token: Authentication token
        notebook_rel: Relative path to the notebook
        cell_wait_ms: Wait time after each cell in fallback mode
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is required. Install with `pip install playwright` "
            "and run `python -m playwright install`."
        ) from exc

    notebook_rel = notebook_rel.replace(os.sep, "/")
    notebook_url = f"{base_url}/lab/tree/{quote(notebook_rel)}?token={token}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # Reset JupyterLab workspace first to ensure clean state
            _reset_jupyterlab_workspace(page, base_url, token)

            # Now open the notebook
            page.goto(notebook_url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000
            )
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Notebook", timeout=120000
            )

            _run_all_cells(page, cell_wait_ms)
        finally:
            page.close()
            browser.close()


def run_notebook_playwright(
    page,
    base_url: str,
    token: str,
    notebook_rel: str,
    cell_wait_ms: int = 1000,
) -> None:
    """Run a notebook via Playwright browser automation.

    Args:
        page: Playwright page object (already opened)
        base_url: JupyterLab base URL
        token: Authentication token
        notebook_rel: Relative path to the notebook
        cell_wait_ms: Wait time after each cell in fallback mode
    """
    notebook_rel = notebook_rel.replace(os.sep, "/")
    notebook_name = notebook_rel.split("/")[-1]
    notebook_url = f"{base_url}/lab/tree/{quote(notebook_rel)}?token={token}"

    # Reset JupyterLab workspace first to ensure clean state
    _reset_jupyterlab_workspace(page, base_url, token)

    # Now open the notebook
    page.goto(notebook_url, wait_until="domcontentloaded", timeout=120000)
    page.wait_for_selector(".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000)
    page.wait_for_selector(
        ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Notebook", timeout=120000
    )

    # Verify we have the correct notebook open by checking the tab title
    page.wait_for_timeout(1000)

    # Double-check the notebook is loaded correctly
    tab_title = page.evaluate("""
    () => {
        const tab = document.querySelector('.jp-mod-current .lm-TabBar-tabLabel');
        return tab ? tab.textContent : '';
    }
    """)

    if notebook_name not in str(tab_title):
        # If wrong notebook, try navigating again
        page.goto(notebook_url, wait_until="domcontentloaded", timeout=120000)
        page.wait_for_selector(".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000)
        page.wait_for_timeout(2000)

    _run_all_cells(page, cell_wait_ms)


def _run_all_cells(page, cell_wait_ms: int) -> None:
    """Execute all cells in the notebook.

    Tries multiple methods in order:
    1. JavaScript command execution via JupyterLab API
    2. Menu UI interaction
    3. Shift+Enter for each cell (fallback)

    Args:
        page: Playwright page object
        cell_wait_ms: Wait time after each cell in fallback mode
    """
    ran = False
    # Method 1: Try JavaScript command execution
    try:
        ran = page.evaluate("""
() => {
  const app = window.jupyterapp || window.jupyterlab || window.jupyterApp || window.jupyterLab;
  if (!app || !app.commands) {
    return false;
  }
  const commands = ["runmenu:run-all", "notebook:run-all-cells"];
  for (const cmd of commands) {
    if (app.commands.hasCommand(cmd)) {
      app.commands.execute(cmd);
      return true;
    }
  }
  return false;
}
""")
    except Exception:
        ran = False

    if not ran:
        try:
            page.get_by_role("menuitem", name="Run").click(timeout=5000)
            page.get_by_role("menuitem", name="Run All Cells", exact=True).click(
                timeout=5000
            )
            ran = True
        except Exception:
            ran = False

    # Method 3: Fallback to Shift+Enter for each cell
    if not ran:
        locator = page.locator(".jp-Cell")
        count = locator.count()
        if count == 0:
            raise RuntimeError("No notebook cells found to run.")
        locator = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Cell")
        count = locator.count()
        if count == 0:
            raise RuntimeError("No visible notebook cells found to run.")

        # Wait for notebook to be fully loaded
        page.wait_for_timeout(2000)

        # Click first cell and ensure we're in command mode
        locator.first.scroll_into_view_if_needed()
        locator.first.click()
        page.wait_for_timeout(500)
        page.keyboard.press("Escape")  # Enter command mode
        page.wait_for_timeout(200)

        # Go to first cell with Ctrl+Home
        page.keyboard.press("Control+Home")
        page.wait_for_timeout(200)

        for _ in range(count):
            page.keyboard.press("Shift+Enter")
            if cell_wait_ms:
                page.wait_for_timeout(cell_wait_ms)

    # Wait for cells to finish executing (important for all methods)
    if ran:
        # If we used JS or menu, wait for execution to complete
        # Count cells in the notebook
        locator = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Cell")
        cell_count = locator.count()
        total_wait = cell_wait_ms * max(cell_count, 7)  # At least 7 cells worth
        page.wait_for_timeout(total_wait)


def get_page_for_notebook(
    browser,
    base_url: str,
    token: str,
    notebook_rel: str,
    cell_wait_ms: int = 1000,
):
    """Open a notebook and return the page for further testing.

    Args:
        browser: Playwright browser instance
        base_url: JupyterLab base URL
        token: Authentication token
        notebook_rel: Relative path to the notebook
        cell_wait_ms: Wait time after each cell

    Returns:
        Playwright page with the notebook open and all cells executed
    """
    page = browser.new_page()
    run_notebook_playwright(page, base_url, token, notebook_rel, cell_wait_ms)
    return page
