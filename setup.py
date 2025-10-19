#!/usr/bin/env python3
"""Custom setup.py to handle JupyterLab extension installation."""

import os
from pathlib import Path
from setuptools import setup

# Get all files in labextension directory recursively
labext_path = Path("instrmcp/extensions/jupyterlab/mcp_active_cell_bridge/labextension")
data_files = []

for root, dirs, files in os.walk(labext_path):
    if files:
        # Get relative path from labextension directory
        rel_path = Path(root).relative_to(labext_path)
        # Target installation directory
        if rel_path == Path("."):
            target = "share/jupyter/labextensions/mcp-active-cell-bridge"
        else:
            target = f"share/jupyter/labextensions/mcp-active-cell-bridge/{rel_path}"
        # Add all files in this directory
        file_paths = [os.path.join(root, f) for f in files]
        data_files.append((target, file_paths))

# Run setup with dynamic data_files
setup(
    data_files=data_files,
)
