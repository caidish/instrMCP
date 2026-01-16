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
import subprocess
from pathlib import Path

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


# ============================================================================
# STDIO MCP Client for validation via proxy
# ============================================================================


class StdioMCPClient:
    """MCP client that communicates with a proxy subprocess via STDIO.

    This client spawns the claude_launcher.py subprocess and sends
    JSON-RPC commands via STDIN, receiving responses via STDOUT.

    Used by `instrmcp metadata validate` to test the full communication path:
    CLI → STDIO → stdio_proxy → HTTP → MCP Server

    Usage:
        client = StdioMCPClient()
        try:
            client.start()
            tools = client.list_tools()
            resources = client.list_resources()
        finally:
            client.stop()
    """

    def __init__(
        self,
        launcher_path: str | None = None,
        mcp_url: str = "http://127.0.0.1:8123",
    ):
        """Initialize the STDIO MCP client.

        Args:
            launcher_path: Path to the launcher script. If None, uses the
                           bundled claude_launcher.py.
            mcp_url: URL of the MCP server (used for error messages).
        """
        self.launcher_path = launcher_path
        self.mcp_url = mcp_url
        self._process: subprocess.Popen | None = None
        self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _find_launcher(self) -> str:
        """Find the launcher script path."""
        if self.launcher_path:
            return self.launcher_path

        # Try to find claude_launcher.py relative to this file
        import sys

        # Check common locations
        candidates = [
            Path(__file__).parent.parent.parent.parent
            / "claudedesktopsetting"
            / "claude_launcher.py",
            Path.home()
            / "GitHub"
            / "instrMCP"
            / "claudedesktopsetting"
            / "claude_launcher.py",
        ]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

        raise FileNotFoundError(
            "Could not find claude_launcher.py. "
            "Please specify --launcher-path or ensure instrMCP is properly installed."
        )

    def start(self, timeout: float = 10.0) -> None:
        """Start the proxy subprocess and initialize the MCP session.

        Args:
            timeout: Timeout in seconds for initialization.

        Raises:
            RuntimeError: If subprocess fails to start or initialize.
            FileNotFoundError: If launcher script not found.
        """
        import subprocess
        import sys

        launcher = self._find_launcher()
        logger.info(f"Starting STDIO proxy: {launcher}")

        self._process = subprocess.Popen(
            [sys.executable, launcher],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
        )

        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "InstrMCP CLI Validator", "version": "1.0.0"},
            },
        }

        response = self._send_request(init_request, timeout)
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"Initialize failed: {error.get('message', error)}")

        # Send initialized notification
        self._send_notification(
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        )

        logger.info("STDIO proxy initialized successfully")

    def stop(self) -> None:
        """Stop the proxy subprocess."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
            finally:
                self._process = None

    def _send_request(self, request: dict, timeout: float = 10.0) -> dict:
        """Send a JSON-RPC request and return the response.

        Args:
            request: JSON-RPC request dict.
            timeout: Timeout in seconds.

        Returns:
            JSON-RPC response dict.

        Raises:
            RuntimeError: If subprocess is not running or communication fails.
        """
        import select

        if not self._process or self._process.poll() is not None:
            raise RuntimeError("Subprocess is not running")

        # Write request
        request_str = json.dumps(request) + "\n"
        self._process.stdin.write(request_str)
        self._process.stdin.flush()

        # Read response with timeout
        import time

        start = time.time()
        response_lines = []

        while time.time() - start < timeout:
            # Check if process has output
            if self._process.stdout.readable():
                line = self._process.stdout.readline()
                if line:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        response = json.loads(line)
                        if (
                            isinstance(response, dict)
                            and response.get("id") == request["id"]
                        ):
                            return response
                    except json.JSONDecodeError:
                        # Not a complete JSON response yet
                        response_lines.append(line)
                        continue
            time.sleep(0.01)

        # Check stderr for errors
        if self._process.stderr:
            stderr = self._process.stderr.read()
            if stderr:
                raise RuntimeError(f"Proxy error: {stderr}")

        raise RuntimeError(f"Timeout waiting for response to {request.get('method')}")

    def _send_notification(self, notification: dict) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or self._process.poll() is not None:
            raise RuntimeError("Subprocess is not running")

        notification_str = json.dumps(notification) + "\n"
        self._process.stdin.write(notification_str)
        self._process.stdin.flush()

    def list_tools(self, timeout: float = 10.0) -> list[dict]:
        """Get the list of registered tools from the server.

        Returns:
            List of tool dicts with name, description, inputSchema.
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {},
        }

        response = self._send_request(request, timeout)
        if "error" in response:
            raise RuntimeError(f"tools/list failed: {response['error']}")

        result = response.get("result", {})
        return result.get("tools", [])

    def list_resources(self, timeout: float = 10.0) -> list[dict]:
        """Get the list of registered resources from the server.

        Returns:
            List of resource dicts with uri, name, description.
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "resources/list",
            "params": {},
        }

        response = self._send_request(request, timeout)
        if "error" in response:
            raise RuntimeError(f"resources/list failed: {response['error']}")

        result = response.get("result", {})
        return result.get("resources", [])
