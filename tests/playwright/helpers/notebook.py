"""
Notebook preparation and cleanup utilities for E2E tests.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .config import WORKING_NOTEBOOK_DIR


def prepare_working_notebook(original_notebook: Path) -> Path:
    """Copy notebook to working directory for isolated execution.

    The working directory is within the repo so JupyterLab can access it.

    Args:
        original_notebook: Path to the original notebook

    Returns:
        Path to the working copy of the notebook
    """
    # Clean up any existing working directory
    if WORKING_NOTEBOOK_DIR.exists():
        shutil.rmtree(WORKING_NOTEBOOK_DIR)

    # Create working directory
    WORKING_NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)

    # Copy notebook to working directory
    working_notebook = WORKING_NOTEBOOK_DIR / original_notebook.name
    shutil.copy2(original_notebook, working_notebook)

    return working_notebook


def cleanup_working_notebook() -> None:
    """Clean up working notebook directory."""
    if WORKING_NOTEBOOK_DIR.exists():
        shutil.rmtree(WORKING_NOTEBOOK_DIR, ignore_errors=True)


def load_extra_cells(path: Path | None) -> list[str]:
    """Load extra cells from a JSON file.

    Args:
        path: Path to JSON file containing a list of cell code strings

    Returns:
        List of code strings for cells to add

    Raises:
        ValueError: If the file format is invalid
    """
    if not path:
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("extra cells file must be a JSON list of strings")
    return data
