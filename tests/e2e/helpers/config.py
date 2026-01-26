"""
Configuration constants for E2E tests.
"""

from __future__ import annotations

from pathlib import Path

# Default configuration values
DEFAULT_TOKEN = "e2e-test-token"
DEFAULT_JUPYTER_PORT = 8888
DEFAULT_MCP_PORT = 8123
DEFAULT_MCP_URL = "http://127.0.0.1:8123"

# Notebook paths
NOTEBOOKS_DIR = Path(__file__).parent.parent / "notebooks"
ORIGINAL_NOTEBOOKS_DIR = NOTEBOOKS_DIR / "original"
WORKING_NOTEBOOK_DIR = NOTEBOOKS_DIR / "_working"

# Test notebooks
SAFE_MODE_NOTEBOOK = ORIGINAL_NOTEBOOKS_DIR / "e2e_safe_mode.ipynb"
UNSAFE_MODE_NOTEBOOK = ORIGINAL_NOTEBOOKS_DIR / "e2e_unsafe_mode.ipynb"
DANGEROUS_MODE_NOTEBOOK = ORIGINAL_NOTEBOOKS_DIR / "e2e_dangerous_mode.ipynb"
DANGEROUS_DYNAMICTOOL_NOTEBOOK = (
    ORIGINAL_NOTEBOOKS_DIR / "e2e_dangerous_with_dynamictool.ipynb"
)
MEASUREIT_SWEEPQUEUE_NOTEBOOK = (
    ORIGINAL_NOTEBOOKS_DIR / "e2e_measureit_sweepqueue.ipynb"
)

# Test results
TEST_RESULTS_DIR = Path(__file__).parent.parent / "test-results"

# Log paths
DEFAULT_JUPYTER_LOG = Path(__file__).parent.parent / "jupyter_lab.log"
