"""
Codex CLI launcher for Jupyter QCoDeS MCP server (STDIO proxy).

This launcher runs a local MCP server over STDIO for Codex to connect to,
while proxying MCP JSON-RPC requests to the HTTP server (e.g. http://127.0.0.1:8123/mcp).

Environment variables:
- JUPYTER_MCP_HOST: Host of the HTTP MCP server (default: 127.0.0.1)
- JUPYTER_MCP_PORT: Port of the HTTP MCP server (default: 8123)
"""

import os
import sys
import asyncio
import logging

# Keep stdout clean for STDIO transport
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Reuse the existing proxy implementation
from instrmcp.utils.stdio_proxy import (
    create_stdio_proxy_server,
    check_http_mcp_server,
)


def main() -> None:
    host = os.getenv("JUPYTER_MCP_HOST", "127.0.0.1")
    port_str = os.getenv("JUPYTER_MCP_PORT", "8123")
    try:
        port = int(port_str)
    except ValueError:
        port = 8123

    jupyter_url = f"http://{host}:{port}"

    async def check_and_setup():
        running = await check_http_mcp_server(host=host, port=port)
        if not running:
            raise RuntimeError(f"Jupyter MCP server not reachable at {jupyter_url}/mcp")
        return create_stdio_proxy_server(jupyter_url, server_name="InstrMCP Proxy")

    try:
        loop = asyncio.get_running_loop()
        mcp = loop.run_until_complete(check_and_setup())
    except RuntimeError:
        mcp = asyncio.run(check_and_setup())

    # Run over STDIO for Codex
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        if os.getenv("DEBUG"):
            print(f"❌ Server error: {e}", file=sys.stderr)
        sys.exit(1)
