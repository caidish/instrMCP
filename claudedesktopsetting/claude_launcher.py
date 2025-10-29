"""
Claude Desktop launcher for Jupyter QCoDeS MCP server.

This script provides STDIO transport compatibility for Claude Desktop while
using a shared STDIO↔HTTP proxy implementation.
"""

import asyncio
import sys
import os
import logging

# Configure logging for clean STDIO communication
# Only suppress INFO and DEBUG levels, keep WARNING, ERROR, CRITICAL for debugging
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.ERROR)  # Suppress FastMCP INFO messages
logging.getLogger("mcp").setLevel(logging.ERROR)  # Suppress MCP INFO messages
logging.getLogger("httpx").setLevel(logging.WARNING)  # Suppress HTTP request logs
logging.getLogger("asyncio").setLevel(logging.WARNING)  # Suppress asyncio logs

# Import from pip-installed instrmcp package
from fastmcp import FastMCP
from instrmcp.tools.stdio_proxy import (
    create_stdio_proxy_server,
    check_http_mcp_server,
)

logger = logging.getLogger(__name__)


def create_proxy_server(jupyter_url: str) -> FastMCP:
    return create_stdio_proxy_server(jupyter_url, server_name="Jupyter QCoDeS Proxy")


def main():
    """Main launcher."""

    async def check_and_setup():
        # Check if Jupyter server is running
        jupyter_running = await check_http_mcp_server()

        if jupyter_running:
            return create_proxy_server("http://127.0.0.1:8123")
        else:
            raise Exception("jupyter is not running.")

    # Check if we're in an event loop already
    try:
        loop = asyncio.get_running_loop()
        # We're in a loop, use run_until_complete
        mcp = loop.run_until_complete(check_and_setup())
    except RuntimeError:
        # No loop running, create new one
        mcp = asyncio.run(check_and_setup())

    # Run with STDIO transport for Claude Desktop compatibility
    # Suppress banner for clean STDIO communication
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Silently exit on Ctrl+C for clean STDIO
        sys.exit(0)
    except Exception as e:
        # Only log errors to stderr in debug mode
        if os.getenv("DEBUG"):
            print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)
