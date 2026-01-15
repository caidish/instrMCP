"""
MCP metadata client utilities for Playwright E2E tests.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Dict, Iterable

import httpx

DEFAULT_MCP_URL = "http://127.0.0.1:8123"


def _parse_sse_text(text: str) -> Dict[str, Any]:
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


class MCPMetadataClient:
    """Minimal MCP client for tool/resource metadata extraction."""

    def __init__(self, base_url: str = DEFAULT_MCP_URL):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=30.0)
        self._request_id = itertools.count(1)
        self.session_id: str | None = None

    def close(self) -> None:
        self._client.close()

    def _next_request_id(self) -> int:
        return next(self._request_id)

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        return headers

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self._client.post(
            f"{self.base_url}/mcp", json=payload, headers=self._headers()
        )
        resp.raise_for_status()
        return _parse_sse_text(resp.text)

    def initialize(self) -> None:
        request_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "InstrMCP Playwright", "version": "1.0.0"},
            },
        }
        resp = self._client.post(
            f"{self.base_url}/mcp", json=payload, headers=self._headers()
        )
        resp.raise_for_status()
        self.session_id = resp.headers.get("mcp-session-id") or "default-session"

        self._client.post(
            f"{self.base_url}/mcp",
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            headers=self._headers(),
        )

    def list_tools(self) -> Iterable[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "tools/list",
            "params": {},
        }
        response = self._post(payload)
        result = response.get("result") or {}
        return result.get("tools") or []

    def list_resources(self) -> Iterable[Dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "resources/list",
            "params": {},
        }
        response = self._post(payload)
        result = response.get("result") or {}
        return result.get("resources") or []


def _tool_summary(tool: Dict[str, Any]) -> Dict[str, Any]:
    annotations = tool.get("annotations") or {}
    input_schema = tool.get("inputSchema") or {}
    properties = input_schema.get("properties") if isinstance(input_schema, dict) else {}

    args_summary = {}
    if isinstance(properties, dict):
        for arg_name, arg_spec in properties.items():
            if isinstance(arg_spec, dict):
                args_summary[arg_name] = {"description": arg_spec.get("description")}

    return {
        "title": annotations.get("title") or tool.get("title"),
        "description": tool.get("description"),
        "arguments": args_summary,
    }


def build_metadata_snapshot(
    tools: Iterable[Dict[str, Any]], resources: Iterable[Dict[str, Any]]
) -> Dict[str, Any]:
    tool_map: Dict[str, Any] = {}
    for tool in tools:
        name = tool.get("name")
        if not name:
            continue
        tool_map[name] = _tool_summary(tool)

    resource_map: Dict[str, Any] = {}
    for resource in resources:
        uri = resource.get("uri")
        if not uri:
            continue
        resource_map[str(uri)] = {
            "name": resource.get("name"),
            "description": resource.get("description"),
        }

    return {"tools": tool_map, "resources": resource_map}


def save_snapshot(snapshot: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))


def load_snapshot(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def compare_metadata(expected: Dict[str, Any], actual: Dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for section in ("tools", "resources"):
        expected_map = expected.get(section) or {}
        actual_map = actual.get(section) or {}

        expected_keys = set(expected_map)
        actual_keys = set(actual_map)

        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)

        for key in missing:
            errors.append(f"Missing {section[:-1]}: {key}")
        for key in extra:
            errors.append(f"Unexpected {section[:-1]}: {key}")

        for key in sorted(expected_keys & actual_keys):
            if expected_map[key] != actual_map[key]:
                errors.append(f"{section[:-1].title()} metadata mismatch: {key}")

    return errors
