"""
Shared STDIO↔HTTP MCP proxy utilities.

Provides a small MCP server over STDIO that forwards initialize/initialized and
tools/* JSON-RPC calls to an HTTP MCP server (e.g., http://127.0.0.1:8123/mcp).

Used by both Claude Desktop and Codex launchers to avoid code duplication.

This module uses FastMCP's built-in proxy pattern (FastMCP.as_proxy) to automatically
mirror tools, resources, and prompts from the backend server. This ensures that:
1. Tool descriptions are automatically forwarded to MCP clients
2. New tools added to the backend are automatically available
3. No manual synchronization of tool definitions is required
"""

from __future__ import annotations

import json
import logging

import httpx
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

logger = logging.getLogger(__name__)


def _parse_sse_text(text: str) -> dict:
    """
    Parse SSE response text for standalone functions.

    Returns the last valid JSON-RPC response from the SSE stream.
    """
    if "data: " not in text:
        return json.loads(text)

    # Parse all SSE data events and return the last valid one
    last_valid = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
                if isinstance(payload, dict) and "jsonrpc" in payload:
                    last_valid = payload
            except json.JSONDecodeError:
                continue

    if last_valid is None:
        raise ValueError("No valid JSON-RPC response found in SSE stream")
    return last_valid


async def check_http_mcp_server(host: str = "127.0.0.1", port: int = 8123) -> bool:
    """Check if the HTTP MCP server is running and responding."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            endpoint = f"http://{host}:{port}/mcp"
            init_request = {
                "jsonrpc": "2.0",
                "id": "test-init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "Proxy Test", "version": "1.0.0"},
                },
            }

            init_resp = await client.post(
                endpoint,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            if init_resp.status_code != 200:
                return False

            session_id = init_resp.headers.get("mcp-session-id")
            if not session_id:
                return False

            await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )

            test_resp = await client.post(
                endpoint,
                json={
                    "jsonrpc": "2.0",
                    "id": "test-tools",
                    "method": "tools/list",
                    "params": {},
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "mcp-session-id": session_id,
                },
            )
            if test_resp.status_code != 200:
                return False

            payload = _parse_sse_text(test_resp.text)
            return "jsonrpc" in payload and ("result" in payload or "error" in payload)
    except Exception:
        return False


# ============================================================================
# Main proxy server creation using FastMCP.as_proxy()
# ============================================================================


def create_stdio_proxy_server(
    base_url: str, server_name: str = "InstrMCP Proxy"
) -> FastMCP:
    """Create an MCP proxy server that forwards requests to an HTTP backend.

    This uses FastMCP's built-in proxy pattern which automatically:
    - Mirrors all tools with their descriptions and schemas
    - Mirrors all resources
    - Handles session management and request forwarding

    Args:
        base_url: URL of the HTTP MCP backend (e.g., "http://127.0.0.1:8123")
        server_name: Name for this proxy server

    Returns:
        FastMCP server instance configured as a proxy

    Note:
        Connection to the backend is lazy - errors will surface on first tool call,
        not at proxy creation time.
    """
    # Construct the MCP endpoint URL
    mcp_endpoint = f"{base_url.rstrip('/')}/mcp"

    # Create the proxy using FastMCP's built-in proxy pattern
    # ProxyClient handles Streamable HTTP transport automatically
    # Note: Connection is lazy - errors will surface on first tool call
    proxy = FastMCP.as_proxy(
        ProxyClient(mcp_endpoint),
        name=server_name,
    )
    logger.info(f"Created FastMCP proxy to {mcp_endpoint}")

    return proxy
