"""
Playwright browser automation for notebook execution.
"""

from __future__ import annotations

import os
from typing import Iterable
from urllib.parse import quote


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
    url = f"{base_url}/lab/tree/{quote(notebook_rel)}?token={token}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
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
        ran = page.evaluate(
            """
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
"""
        )
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
