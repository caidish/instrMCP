"""InstrMCP Command Line Interface

Main CLI entry point for InstrMCP server management.
"""

import argparse
import sys
import asyncio
from typing import Optional

from .config import config
from .servers import JupyterMCPServer, QCodesStationServer


async def run_jupyter_server(port: int = 3000, safe_mode: bool = True):
    """Run the Jupyter QCodes MCP server in standalone mode.

    Note: This is a standalone server that runs without Jupyter integration.
    For full Jupyter integration, use the magic commands in a Jupyter notebook.
    """
    print("=" * 60)
    print("⚠️  STANDALONE MODE")
    print("=" * 60)
    print("This server runs WITHOUT Jupyter integration.")
    print("For full features, use the Jupyter extension instead:")
    print("  1. Start Jupyter: jupyter lab")
    print("  2. Load extension: %load_ext instrmcp.extensions")
    print("  3. Start server: %mcp_start")
    print("=" * 60)
    print()
    print("❌ Error: Standalone mode is not fully implemented yet.")
    print("Please use the Jupyter extension for now.")
    sys.exit(1)


def run_qcodes_server(port: int = 3001):
    """Run the QCodes station MCP server."""
    server = QCodesStationServer(port=port)
    print(f"Starting QCodes station MCP server on port {port}")
    # QCodesStationServer uses .start() not .run()
    server.start()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="InstrMCP: Instrumentation Control MCP Server Suite",
        prog="instrmcp",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Jupyter server command
    jupyter_parser = subparsers.add_parser(
        "jupyter", help="Run Jupyter QCodes MCP server"
    )
    jupyter_parser.add_argument(
        "--port", type=int, default=3000, help="Server port (default: 3000)"
    )
    jupyter_parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Enable unsafe mode (allows code execution)",
    )

    # QCodes server command
    qcodes_parser = subparsers.add_parser(
        "qcodes", help="Run QCodes station MCP server"
    )
    qcodes_parser.add_argument(
        "--port", type=int, default=3001, help="Server port (default: 3001)"
    )

    # Config command
    config_parser = subparsers.add_parser(
        "config", help="Show configuration information"
    )

    # Version command
    version_parser = subparsers.add_parser("version", help="Show version information")

    args = parser.parse_args()

    if args.command == "jupyter":
        safe_mode = not args.unsafe
        asyncio.run(run_jupyter_server(port=args.port, safe_mode=safe_mode))
    elif args.command == "qcodes":
        run_qcodes_server(port=args.port)
    elif args.command == "config":
        print(f"InstrMCP Configuration:")
        print(f"Package path: {config.get_package_path()}")
        print(f"Config file: {config.get_config_file()}")
        print(f"User config directory: {config.get_user_config_dir()}")
        print()

        # Check for optional dependencies
        print("Optional Extensions:")

        # Check MeasureIt using importlib to avoid full import crash
        import importlib.util
        import subprocess

        measureit_spec = importlib.util.find_spec("MeasureIt")
        if measureit_spec is not None:
            # Try to import in subprocess to avoid crashing main process
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "import MeasureIt; print(getattr(MeasureIt, '__version__', 'unknown'))",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1,  # Reduced timeout since imports should be fast
                )
                if result.returncode == 0:
                    measureit_version = result.stdout.strip()
                    print(f"  ✅ MeasureIt: {measureit_version}")
                else:
                    print(f"  ⚠️  MeasureIt: Installed but failed to import")
                    # Extract first meaningful error line
                    errors = [
                        line
                        for line in result.stderr.split("\n")
                        if line.strip() and not line.startswith(" ")
                    ]
                    error_msg = errors[-1] if errors else "Unknown error"
                    if len(error_msg) > 70:
                        error_msg = error_msg[:70] + "..."
                    print(f"     Error: {error_msg}")
            except subprocess.TimeoutExpired:
                print(f"  ⚠️  MeasureIt: Installed but import timed out")
                print(f"     Possible dependency issue (e.g., NumPy compatibility)")
            except Exception as e:
                print(f"  ⚠️  MeasureIt: Installed but check failed")
                print(f"     Error: {str(e)[:70]}")
        else:
            print("  ❌ MeasureIt: Not installed")
            print("     Install from: https://github.com/nanophys/MeasureIt")
    elif args.command == "version":
        from . import __version__

        print(f"InstrMCP version {__version__}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
