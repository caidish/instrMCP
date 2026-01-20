"""
MCP server interaction helpers for E2E tests.
"""

from __future__ import annotations

import itertools
import json
import re
import time
from typing import Any

import httpx


def _parse_sse_text(text: str) -> dict[str, Any]:
    """Parse Server-Sent Events (SSE) formatted text.

    Args:
        text: Response text, possibly in SSE format

    Returns:
        Parsed JSON-RPC response
    """
    if "data: " not in text:
        return json.loads(text)

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


class MCPClient:
    """MCP client for E2E tests with proper session handling."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)
        self._request_id = itertools.count(1)
        self.session_id: str | None = None

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _next_request_id(self) -> int:
        return next(self._request_id)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(
            f"{self.base_url}/mcp", json=payload, headers=self._headers()
        )
        resp.raise_for_status()
        return _parse_sse_text(resp.text)

    def initialize(self) -> None:
        """Initialize the MCP connection and establish session."""
        request_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0.0"},
            },
        }
        resp = self._client.post(
            f"{self.base_url}/mcp", json=payload, headers=self._headers()
        )
        resp.raise_for_status()
        self.session_id = resp.headers.get("mcp-session-id") or "default-session"

        # Send initialized notification
        self._client.post(
            f"{self.base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
            headers=self._headers(),
        )

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available MCP tools.

        Returns:
            List of tool dictionaries with 'name', 'description', etc.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {},
        }
        response = self._post(payload)
        result = response.get("result") or {}
        return result.get("tools") or []

    def list_resources(self) -> list[dict[str, Any]]:
        """List all available MCP resources.

        Returns:
            List of resource dictionaries.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "resources/list",
            "params": {},
        }
        response = self._post(payload)
        result = response.get("result") or {}
        return result.get("resources") or []

    def read_resource(self, uri: str) -> dict[str, Any]:
        """Read an MCP resource.

        Args:
            uri: Resource URI

        Returns:
            Resource content dictionary
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "resources/read",
            "params": {"uri": uri},
        }
        return self._post(payload)

    def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Call an MCP tool and return the result.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result dictionary
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }
        return self._post(payload)


def extract_port(output: str) -> int:
    """Extract port number from server start output.

    Args:
        output: Server output text

    Returns:
        Port number (defaults to 8123 if not found)
    """
    # Look for patterns like "localhost:8123" or "port 8123" or "Port: 8123"
    patterns = [
        r"localhost:(\d+)",
        r"127\.0\.0\.1:(\d+)",
        r"[Pp]ort[:\s]+(\d+)",
        r":(\d{4,5})",  # Any 4-5 digit port
    ]
    for pattern in patterns:
        match = re.search(pattern, output)
        if match:
            port = int(match.group(1))
            if 1024 <= port <= 65535:
                return port
    return 8123  # Default port


def wait_for_mcp_server(base_url: str, timeout_s: int = 30) -> bool:
    """Wait for MCP server to become available.

    Args:
        base_url: MCP server base URL (e.g., "http://localhost:8123")
        timeout_s: Timeout in seconds

    Returns:
        True if server is available, False otherwise
    """
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            with MCPClient(base_url) as client:
                client.initialize()
                # Also verify we can list tools
                tools = client.list_tools()
                if len(tools) > 0:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def call_mcp_tool(
    base_url: str, tool_name: str, arguments: dict[str, Any] | None = None
) -> dict:
    """Call an MCP tool and return the result.

    Args:
        base_url: MCP server base URL
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Tool result dictionary
    """
    with MCPClient(base_url) as client:
        client.initialize()
        return client.call_tool(tool_name, arguments)


def list_mcp_tools(base_url: str) -> list[dict]:
    """List all available MCP tools.

    Args:
        base_url: MCP server base URL

    Returns:
        List of tool dictionaries with 'name', 'description', etc.
    """
    with MCPClient(base_url) as client:
        client.initialize()
        return client.list_tools()


def list_mcp_resources(base_url: str) -> list[dict]:
    """List all available MCP resources.

    Args:
        base_url: MCP server base URL

    Returns:
        List of resource dictionaries
    """
    with MCPClient(base_url) as client:
        client.initialize()
        return client.list_resources()


def get_mcp_resource(base_url: str, uri: str) -> dict:
    """Get an MCP resource.

    Args:
        base_url: MCP server base URL
        uri: Resource URI

    Returns:
        Resource content dictionary
    """
    with MCPClient(base_url) as client:
        client.initialize()
        return client.read_resource(uri)


def parse_tool_result(response: dict) -> tuple[bool, str]:
    """Parse an MCP tool response.

    Args:
        response: MCP JSON-RPC response

    Returns:
        Tuple of (success, content_text)
    """
    if "error" in response:
        return False, response["error"].get("message", "Unknown error")

    if "result" not in response:
        return False, "No result in response"

    result = response["result"]
    if isinstance(result, dict) and "content" in result:
        contents = result["content"]
        if isinstance(contents, list) and len(contents) > 0:
            text_parts = []
            for content in contents:
                if isinstance(content, dict) and "text" in content:
                    text_parts.append(content["text"])
            return True, "\n".join(text_parts)

    return True, str(result)
