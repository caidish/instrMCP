"""
Playwright browser automation for notebook execution.
"""

from __future__ import annotations

import os
from typing import Iterable
from urllib.parse import quote


def _reset_jupyterlab_workspace(page, base_url: str, token: str) -> None:
    """Reset JupyterLab workspace to ensure clean state.

    This closes all open tabs/notebooks and resets the workspace layout
    to prevent interference from previous sessions.

    Args:
        page: Playwright page object
        base_url: JupyterLab base URL
        token: Authentication token
    """
    # Navigate to JupyterLab main page first
    lab_url = f"{base_url}/lab?token={token}"
    page.goto(lab_url, wait_until="domcontentloaded", timeout=120000)

    # Wait for JupyterLab to be ready
    page.wait_for_selector(".jp-LabShell", timeout=60000)
    page.wait_for_timeout(2000)  # Give JupyterLab time to fully initialize

    # Reset workspace via JavaScript - close all activities and reset layout
    page.evaluate("""
() => {
    const app = window.jupyterapp || window.jupyterlab || window.jupyterApp || window.jupyterLab;
    if (!app) return false;

    // Close all open tabs/activities
    if (app.shell && app.shell.widgets) {
        const widgets = Array.from(app.shell.widgets('main'));
        widgets.forEach(w => w.close());
    }

    // Reset workspace layout if command available
    if (app.commands && app.commands.hasCommand('application:reset-layout')) {
        app.commands.execute('application:reset-layout');
    }

    return true;
}
""")
    page.wait_for_timeout(1000)  # Wait for workspace reset to complete


def run_notebook_playwright(
    base_url: str,
    token: str,
    notebook_rel: str,
    extra_cells: Iterable[str],
    cell_wait_ms: int,
) -> None:
    """Run a notebook via Playwright browser automation.

    Args:
        base_url: JupyterLab base URL
        token: Authentication token
        notebook_rel: Relative path to the notebook
        extra_cells: Additional cells to append before running
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
            print("  Resetting JupyterLab workspace...")
            _reset_jupyterlab_workspace(page, base_url, token)

            # Now open the notebook
            print(f"  Opening notebook: {notebook_rel}")
            page.goto(notebook_url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000
            )
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Notebook", timeout=120000
            )

            if extra_cells:
                _append_cells(page, list(extra_cells))

            _run_all_cells(page, cell_wait_ms)
        finally:
            page.close()
            browser.close()


def _append_cells(page, cells: list[str]) -> None:
    """Append code cells to the current notebook.

    Args:
        page: Playwright page object
        cells: List of code strings for new cells
    """
    locator = page.locator(".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Cell")
    if locator.count() == 0:
        raise RuntimeError("No notebook cells found to append to.")

    locator.last.scroll_into_view_if_needed()
    locator.last.click()
    page.keyboard.press("Escape")

    for cell in cells:
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.insert_text(cell)
        page.keyboard.press("Shift+Enter")
        page.keyboard.press("Escape")


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
        total_wait = cell_wait_ms * 7  # 7 cells in the notebook
        print(f"  Waiting {total_wait}ms for cell execution to complete...")
        page.wait_for_timeout(total_wait)
