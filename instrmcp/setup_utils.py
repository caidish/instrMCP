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
    """Install JupyterLab extension only."""
    try:
        # Get the path to the extension package (not the labextension subdirectory)
        package_dir = Path(__file__).parent
        extension_path = package_dir / "extensions" / "jupyterlab"
        
        if not extension_path.exists():
            print(f"❌ Extension not found at: {extension_path}")
            return False
        
        print("🔧 Installing JupyterLab extension...")
        
        # Install the extension in development mode
        result = subprocess.run([
            "jupyter", "labextension", "develop", str(extension_path), "--overwrite"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ JupyterLab extension installed successfully")
            
            # Build JupyterLab to include the extension
            print("🔨 Building JupyterLab with extension...")
            build_result = subprocess.run([
                "jupyter", "lab", "build", "--minimize=False"
            ], capture_output=True, text=True)
            
            if build_result.returncode == 0:
                print("✅ JupyterLab built successfully")
                return True
            else:
                print(f"⚠️  JupyterLab build failed: {build_result.stderr}")
                return False
        else:
            print(f"❌ Failed to install extension: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error installing JupyterLab extension: {e}")
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