"""
Notebook preparation and cleanup utilities for E2E tests.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .config import WORKING_NOTEBOOK_DIR


def prepare_working_notebook(original_notebook: Path) -> Path:
    """Copy notebook to working directory with a unique name for isolated execution.

    Uses a unique filename to ensure JupyterLab creates a fresh kernel for each test.
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

    # Create unique notebook name to force fresh kernel
    unique_id = uuid.uuid4().hex[:8]
    base_name = original_notebook.stem
    unique_name = f"{base_name}_{unique_id}.ipynb"
    working_notebook = WORKING_NOTEBOOK_DIR / unique_name
    shutil.copy2(original_notebook, working_notebook)

    return working_notebook


def cleanup_working_notebook() -> None:
    """Clean up working notebook directory."""
    if WORKING_NOTEBOOK_DIR.exists():
        shutil.rmtree(WORKING_NOTEBOOK_DIR, ignore_errors=True)


def get_notebook_relative_path(notebook_path: Path, repo_root: Path) -> str:
    """Get the notebook path relative to the repo root.

    Args:
        notebook_path: Absolute path to the notebook
        repo_root: Path to the repository root

    Returns:
        Relative path as a string with forward slashes
    """
    try:
        return notebook_path.relative_to(repo_root).as_posix()
    except ValueError:
        raise ValueError("Notebook must be under the repository root")
