#!/usr/bin/env python3
"""
InstrMCP setup utilities for post-installation configuration.
"""

from pathlib import Path


def setup_jupyter_extension():
    """Link and build JupyterLab extension."""
    try:
        import sys

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

        # Use Jupyter's system data directory (in conda env/venv)
        # Prefer env-specific over user-specific installation
        from jupyter_core.paths import jupyter_data_dir, ENV_JUPYTER_PATH

        # Get list of data directories, prefer the one in sys.prefix
        data_dirs = ENV_JUPYTER_PATH
        env_data_dir = None
        for d in data_dirs:
            if str(sys.prefix) in str(d):
                env_data_dir = Path(d)
                break

        # Fallback to jupyter_data_dir if not found
        if env_data_dir is None:
            env_data_dir = Path(jupyter_data_dir())

        lab_ext_dir = env_data_dir / "labextensions"

        print(f"🔍 Jupyter data dir: {env_data_dir}")
        print(f"🔍 Installing to: {lab_ext_dir}")

        lab_ext_dir.mkdir(parents=True, exist_ok=True)
        extension_link = lab_ext_dir / "mcp-active-cell-bridge"

        # Remove existing extension
        if extension_link.exists():
            if extension_link.is_symlink():
                extension_link.unlink()
            else:
                import shutil

                shutil.rmtree(extension_link)

        # Try symlink first (better for development)
        symlink_success = False
        try:
            extension_link.symlink_to(extension_path)
            # Verify it worked
            if (extension_link / "package.json").exists():
                print(f"✅ Extension symlinked to: {extension_link}")
                symlink_success = True
            else:
                extension_link.unlink()
                print("   Symlink verification failed, trying copy...")
        except (OSError, NotImplementedError, PermissionError) as e:
            print(f"   Symlink not available ({type(e).__name__}), trying copy...")

        # Fallback to copy if symlink failed
        if not symlink_success:
            import shutil

            shutil.copytree(extension_path, extension_link, symlinks=True)
            if (extension_link / "package.json").exists():
                print(f"✅ Extension copied to: {extension_link}")
                print("   (Using copy instead of symlink)")
            else:
                print("❌ Extension copy failed - files not accessible")
                return False

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
    """Run all post-install setup tasks.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
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

    # Return proper exit code: 0 for success, 1 for failure
    return 0 if success else 1


if __name__ == "__main__":
    setup_all()
