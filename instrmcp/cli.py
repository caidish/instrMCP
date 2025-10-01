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
    """Run the Jupyter QCodes MCP server."""
    server = JupyterMCPServer(port=port, safe_mode=safe_mode)
    print(f"Starting Jupyter QCodes MCP server on port {port}")
    print(f"Safe mode: {'enabled' if safe_mode else 'disabled'}")
    await server.run()


async def run_qcodes_server(port: int = 3001):
    """Run the QCodes station MCP server."""
    server = QCodesStationServer(port=port)
    print(f"Starting QCodes station MCP server on port {port}")
    await server.run()


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
        asyncio.run(run_qcodes_server(port=args.port))
    elif args.command == "config":
        print(f"InstrMCP Configuration:")
        print(f"Package path: {config.get_package_path()}")
        print(f"Config file: {config.get_config_file()}")
        print(f"User config directory: {config.get_user_config_dir()}")
    elif args.command == "version":
        from . import __version__

        print(f"InstrMCP version {__version__}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
