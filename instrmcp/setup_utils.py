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
    """Link and build JupyterLab extension."""
    try:
        # Get the path to the extension
        package_dir = Path(__file__).parent
        extension_path = (
            package_dir
            / "extensions"
            / "jupyterlab"
            / "mcp_active_cell_bridge"
            / "labextension"
        )

        if not extension_path.exists():
            print(f"❌ Extension not found at: {extension_path}")
            return False

        print("🔧 Linking JupyterLab extension...")

        # Create symlink in labextensions directory
        import site
        import sys

        # Try to find the jupyter labextensions directory
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            # We're in a virtual environment
            lab_ext_dir = Path(sys.prefix) / "share" / "jupyter" / "labextensions"
        else:
            # Use site-packages location
            site_packages = Path(site.getsitepackages()[0])
            lab_ext_dir = (
                site_packages.parent.parent.parent
                / "share"
                / "jupyter"
                / "labextensions"
            )

        lab_ext_dir.mkdir(parents=True, exist_ok=True)
        extension_link = lab_ext_dir / "mcp-active-cell-bridge"

        # Remove existing link/directory if it exists
        if extension_link.exists() or extension_link.is_symlink():
            if extension_link.is_dir() and not extension_link.is_symlink():
                shutil.rmtree(extension_link)
            else:
                extension_link.unlink()

        # Try to create symlink, fallback to copy on Windows if permission denied
        import platform

        try:
            extension_link.symlink_to(extension_path)
            print(f"✅ Extension linked to: {extension_link}")
        except (OSError, NotImplementedError) as e:
            # Symlink failed (likely Windows without Developer Mode)
            # Fallback to copying files
            if platform.system() == "Windows":
                print("⚠️  Symlink failed (Windows requires Developer Mode or Admin)")
                print("📁 Copying extension files instead...")
                shutil.copytree(extension_path, extension_link)
                print(f"✅ Extension copied to: {extension_link}")
            else:
                raise  # Re-raise on non-Windows systems

        print("✅ JupyterLab extension setup completed (no rebuild required)")
        return True

    except Exception as e:
        print(f"❌ Error setting up extension: {e}")
        import traceback

        traceback.print_exc()
        return False


def setup_jupyter_config():
    """Minimal setup - InstrMCP extensions are loaded manually."""
    print(
        "📋 InstrMCP IPython extension is loaded manually - no auto-configuration needed"
    )
    print("📖 To load the extension, use: %load_ext instrmcp.extensions")
    return True


def setup_all():
    """Run all post-install setup tasks."""
    print("🚀 Setting up InstrMCP...")

    success = True

    # Setup JupyterLab extension
    if not setup_jupyter_extension():
        print(
            "⚠️  JupyterLab extension setup failed, but you can install it manually later"
        )
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
