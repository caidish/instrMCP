"""
JupyterLab automation helpers for E2E tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page


def run_cell(
    page: Page, code: str, wait_for_output: bool = True, timeout: int = 30000
) -> None:
    """Execute code in a new cell.

    Creates a new cell below, types the code, and executes it.

    Args:
        page: Playwright page object
        code: Code to execute in the cell
        wait_for_output: Whether to wait for output to appear
        timeout: Timeout in milliseconds for output
    """
    # Ensure we're in command mode
    page.keyboard.press("Escape")
    page.wait_for_timeout(100)

    # Add a new cell below current cell
    page.keyboard.press("B")
    page.wait_for_timeout(300)

    # Enter edit mode
    page.keyboard.press("Enter")
    page.wait_for_timeout(100)

    # Type the code
    page.keyboard.type(code, delay=5)
    page.wait_for_timeout(100)

    # Execute cell with Shift+Enter
    page.keyboard.press("Shift+Enter")

    if wait_for_output:
        # Wait for cell execution to complete
        page.wait_for_timeout(1000)  # Initial wait for execution to start
        try:
            # Wait for no cells to be executing (no asterisk in prompt)
            page.wait_for_function(
                """() => {
                    const prompts = document.querySelectorAll('.jp-InputPrompt');
                    for (const prompt of prompts) {
                        if (prompt.textContent && prompt.textContent.includes('*')) {
                            return false;
                        }
                    }
                    return true;
                }""",
                timeout=timeout,
            )
        except Exception:
            # Timeout - proceed anyway but log
            pass
        page.wait_for_timeout(500)  # Extra wait for output to render


def get_cell_output(page: Page, cell_index: int = -1) -> str:
    """Get output text from a cell.

    Args:
        page: Playwright page object
        cell_index: Index of cell to get output from (-1 for last executed)

    Returns:
        Output text from the cell
    """
    if cell_index == -1:
        # Get the last cell with output
        outputs = page.locator(".jp-Cell .jp-OutputArea-output")
        if outputs.count() == 0:
            return ""
        return outputs.last.inner_text()
    else:
        cells = page.locator(".jp-Cell")
        if cell_index >= cells.count():
            return ""
        cell = cells.nth(cell_index)
        output = cell.locator(".jp-OutputArea-output")
        if output.count() == 0:
            return ""
        return output.first.inner_text()


def get_all_cell_outputs(page: Page) -> list[str]:
    """Get output text from all cells.

    Args:
        page: Playwright page object

    Returns:
        List of output texts from all cells
    """
    outputs = []
    cells = page.locator(".jp-Cell")
    count = cells.count()
    for i in range(count):
        cell = cells.nth(i)
        output_area = cell.locator(".jp-OutputArea-output")
        if output_area.count() > 0:
            outputs.append(output_area.first.inner_text())
        else:
            outputs.append("")
    return outputs


def wait_for_cell_execution(page: Page, timeout: int = 30000) -> None:
    """Wait for all cell executions to complete.

    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds
    """
    try:
        page.wait_for_function(
            """() => {
                const prompts = document.querySelectorAll('.jp-InputPrompt');
                for (const prompt of prompts) {
                    if (prompt.textContent.includes('*')) {
                        return false;
                    }
                }
                return true;
            }""",
            timeout=timeout,
        )
    except Exception:
        pass


def clear_all_outputs(page: Page) -> None:
    """Clear all cell outputs in the notebook.

    Args:
        page: Playwright page object
    """
    # Try using Edit menu -> Clear All Outputs
    try:
        page.get_by_role("menuitem", name="Edit").click(timeout=2000)
        page.get_by_role("menuitem", name="Clear All Outputs").click(timeout=2000)
    except Exception:
        # Fallback to keyboard shortcut or JS
        page.evaluate("""
        () => {
            const app = window.jupyterapp || window.jupyterlab;
            if (app && app.commands) {
                app.commands.execute('editmenu:clear-all');
            }
        }
        """)


def select_cell(page: Page, index: int) -> None:
    """Select a cell by index.

    Args:
        page: Playwright page object
        index: Index of cell to select (0-based)
    """
    cells = page.locator(".jp-Cell")
    if index >= cells.count():
        raise IndexError(f"Cell index {index} out of range (total: {cells.count()})")

    cell = cells.nth(index)
    cell.click()


def get_active_cell_index(page: Page) -> int:
    """Get the index of the currently active cell.

    Args:
        page: Playwright page object

    Returns:
        Index of the active cell (0-based), or -1 if none
    """
    result = page.evaluate("""
    () => {
        const cells = document.querySelectorAll('.jp-Cell');
        for (let i = 0; i < cells.length; i++) {
            if (cells[i].classList.contains('jp-mod-active')) {
                return i;
            }
        }
        return -1;
    }
    """)
    return result


def count_cells(page: Page) -> int:
    """Count the number of cells in the notebook.

    Args:
        page: Playwright page object

    Returns:
        Number of cells
    """
    return page.locator(".jp-Cell").count()


def add_cell_below(page: Page, cell_type: str = "code") -> None:
    """Add a new cell below the current cell.

    Args:
        page: Playwright page object
        cell_type: Type of cell to add ("code" or "markdown")
    """
    # Press B to add cell below in command mode
    page.keyboard.press("Escape")  # Ensure command mode
    page.keyboard.press("B")

    if cell_type == "markdown":
        page.keyboard.press("M")


def delete_cell(page: Page) -> None:
    """Delete the currently selected cell.

    Args:
        page: Playwright page object
    """
    page.keyboard.press("Escape")  # Ensure command mode
    page.keyboard.press("D")
    page.keyboard.press("D")  # DD to delete


def get_cell_type(page: Page, index: int) -> str:
    """Get the type of a cell (code or markdown).

    Args:
        page: Playwright page object
        index: Index of cell

    Returns:
        Cell type ("code" or "markdown")
    """
    cells = page.locator(".jp-Cell")
    if index >= cells.count():
        raise IndexError(f"Cell index {index} out of range")

    cell = cells.nth(index)
    if cell.locator(".jp-MarkdownCell").count() > 0:
        return "markdown"
    return "code"


def get_cell_content(page: Page, index: int) -> str:
    """Get the source content of a cell.

    Args:
        page: Playwright page object
        index: Index of cell

    Returns:
        Cell source content
    """
    result = page.evaluate(f"""
    () => {{
        const cells = document.querySelectorAll('.jp-Cell');
        if ({index} >= cells.length) return '';
        const cell = cells[{index}];
        const editor = cell.querySelector('.jp-Editor');
        if (editor) {{
            // Try to get CodeMirror content
            const cm = editor.querySelector('.cm-content');
            if (cm) return cm.textContent || '';
        }}
        return '';
    }}
    """)
    return result


def setup_notebook_for_test(page: Page, cells: list[dict]) -> None:
    """Set up a notebook with specified cells.

    Args:
        page: Playwright page object
        cells: List of cell definitions with 'type', 'source', and optional 'execute' keys
    """
    for i, cell_def in enumerate(cells):
        cell_type = cell_def.get("type", "code")
        source = cell_def.get("source", "")
        execute = cell_def.get("execute", False)

        if i > 0:
            add_cell_below(page, cell_type)

        if cell_type == "markdown":
            # Switch to markdown mode
            page.keyboard.press("Escape")
            page.keyboard.press("M")

        # Enter edit mode and type content
        page.keyboard.press("Enter")
        page.keyboard.type(source, delay=5)

        if execute and cell_type == "code":
            page.keyboard.press("Shift+Enter")
            wait_for_cell_execution(page)
        else:
            page.keyboard.press("Escape")
