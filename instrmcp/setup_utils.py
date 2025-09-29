#!/usr/bin/env python3
"""
InstrMCP setup utilities for post-installation configuration.
"""

import os
import shutil
import subprocess
from pathlib import Path
from jupyter_core.paths import jupyter_config_dir


def setup_jupyter_extension():
    """Build JupyterLab to include the extension."""
    try:
        print("🔧 Extension is automatically installed via pip...")
        print("🔨 Building JupyterLab with extension...")

        # Build JupyterLab to include the extension
        # The extension is already installed via pip install, just need to rebuild
        build_result = subprocess.run([
            "jupyter", "lab", "build", "--minimize=False"
        ], capture_output=True, text=True)

        if build_result.returncode == 0:
            print("✅ JupyterLab built successfully")
            return True
        else:
            print(f"⚠️  JupyterLab build failed: {build_result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error building JupyterLab: {e}")
        return False


def setup_jupyter_config():
    """Minimal setup - InstrMCP extensions are loaded manually."""
    print("📋 InstrMCP IPython extension is loaded manually - no auto-configuration needed")
    print("📖 To load the extension, use: %load_ext instrmcp.extensions")
    return True


def setup_all():
    """Run all post-install setup tasks."""
    print("🚀 Setting up InstrMCP...")
    
    success = True
    
    # Setup JupyterLab extension
    if not setup_jupyter_extension():
        print("⚠️  JupyterLab extension setup failed, but you can install it manually later")
        success = False
    
    # Setup basic configuration (just informational now)
    setup_jupyter_config()
    
    print("✅ InstrMCP setup completed!")
    print("📋 To use InstrMCP in Jupyter notebooks:")
    print("   1. Start Jupyter: jupyter lab")
    print("   2. Load extension: %load_ext instrmcp.extensions")
    print("   3. Check status: %mcp_status")
    
    if not success:
        print("📝 Note: If JupyterLab extension failed, you can install manually with:")
        print("   jupyter labextension develop /path/to/extension --overwrite")
    
    return success


if __name__ == "__main__":
    setup_all()