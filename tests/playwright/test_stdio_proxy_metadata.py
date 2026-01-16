"""
Test that stdio_proxy metadata aligns with direct HTTP MCP server metadata.

This test verifies that FastMCP's as_proxy() correctly mirrors all tool and
resource metadata from the HTTP backend. This is critical because Claude
Desktop/Code uses the stdio proxy interface.

The test:
1. Connects to the running HTTP MCP server
2. Creates a FastMCP proxy pointing to the same server
3. Compares tools and resources between HTTP and proxy
4. Optionally compares against the baseline snapshot
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

try:
    from tests.playwright.mcp_metadata_client import (
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
    )
except ImportError:
    from mcp_metadata_client import (
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
    )

DEFAULT_MCP_URL = "http://127.0.0.1:8123"
DEFAULT_SNAPSHOT = Path(__file__).parent / "metadata_snapshot.json"


def verify_http_server_running(mcp_url: str = DEFAULT_MCP_URL) -> bool:
    """Check if the HTTP MCP server is running."""
    try:
        client = MCPMetadataClient(mcp_url)
        client.initialize()
        client.close()
        return True
    except Exception:
        return False


def get_http_metadata(mcp_url: str = DEFAULT_MCP_URL) -> dict:
    """Get metadata from the HTTP MCP server."""
    client = MCPMetadataClient(mcp_url)
    client.initialize()
    tools = client.list_tools()
    resources = client.list_resources()
    client.close()
    return build_metadata_snapshot(tools, resources)


def _tool_to_dict(tool: Any) -> dict:
    """Convert a FastMCP tool object to a comparable dict."""

    def _annotations_to_dict(annotations: Any) -> dict:
        if annotations is None:
            return {}
        if isinstance(annotations, dict):
            return annotations
        if hasattr(annotations, "model_dump"):
            return annotations.model_dump()
        if hasattr(annotations, "dict"):
            return annotations.dict()
        return {}

    def _schema_properties(schema: Any) -> dict:
        if isinstance(schema, dict):
            properties = schema.get("properties")
            if isinstance(properties, dict):
                return properties
        return {}

    annotations = _annotations_to_dict(getattr(tool, "annotations", None))
    title = annotations.get("title") or getattr(tool, "title", None)

    # Get input schema properties for arguments
    # Parameters can be a dict (proxy) or a pydantic model
    args_summary = {}
    if hasattr(tool, "parameters") and tool.parameters:
        params = tool.parameters
        if isinstance(params, dict):
            # Proxy tool - parameters is already a dict
            properties = _schema_properties(params) or _schema_properties(
                params.get("schema")
            )
        elif hasattr(params, "model_json_schema"):
            # Regular tool - parameters is a pydantic model
            schema_dict = params.model_json_schema()
            properties = _schema_properties(schema_dict)
        elif hasattr(params, "json_schema"):
            properties = _schema_properties(params.json_schema())
        elif hasattr(params, "schema"):
            properties = _schema_properties(params.schema)
        else:
            properties = {}

        if not properties:
            input_schema = getattr(tool, "input_schema", None) or getattr(
                tool, "inputSchema", None
            )
            properties = _schema_properties(input_schema)

        for arg_name, arg_spec in properties.items():
            if isinstance(arg_spec, dict):
                args_summary[arg_name] = {"description": arg_spec.get("description")}

    return {
        "title": title,
        "description": getattr(tool, "description", None)
        or annotations.get("description"),
        "arguments": args_summary,
    }


def _resource_to_dict(resource: Any) -> dict:
    """Convert a FastMCP resource object to a comparable dict."""
    return {
        "name": getattr(resource, "name", None),
        "description": getattr(resource, "description", None),
    }


async def get_proxy_metadata(mcp_url: str = DEFAULT_MCP_URL) -> dict:
    """Get metadata from the FastMCP proxy.

    This creates a proxy to the HTTP MCP server and extracts
    tools/resources from the proxy object directly.
    """
    mcp_endpoint = f"{mcp_url.rstrip('/')}/mcp"

    # Create the proxy
    proxy = FastMCP.as_proxy(
        ProxyClient(mcp_endpoint),
        name="MetadataTest Proxy",
    )

    # Get tools and resources from the proxy
    # These methods query the backend and cache the results
    tools_dict = await proxy.get_tools()
    resources_dict = await proxy.get_resources()

    # Build snapshot in the same format as HTTP metadata
    tool_map = {}
    for name, tool in tools_dict.items():
        tool_map[name] = _tool_to_dict(tool)

    resource_map = {}
    for uri, resource in resources_dict.items():
        resource_map[str(uri)] = _resource_to_dict(resource)

    return {"tools": tool_map, "resources": resource_map}


def main() -> int:
    """Run the stdio proxy metadata alignment test."""
    parser = argparse.ArgumentParser(
        description="Verify stdio_proxy metadata aligns with HTTP MCP server."
    )
    parser.add_argument(
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        help="Base URL for the MCP server.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="Path to metadata snapshot for comparison.",
    )
    parser.add_argument(
        "--compare-snapshot",
        action="store_true",
        help="Compare proxy metadata against snapshot file instead of live HTTP.",
    )
    args = parser.parse_args()

    # Check HTTP server is running
    print(f"Checking HTTP MCP server at {args.mcp_url}...")
    if not verify_http_server_running(args.mcp_url):
        print("ERROR: HTTP MCP server is not running.")
        print("Start it first with the metadata_e2e notebook or run_metadata_e2e.py")
        return 2

    print("HTTP server is running. Getting metadata...")

    # Get HTTP metadata
    http_metadata = get_http_metadata(args.mcp_url)
    print(
        f"  HTTP: {len(http_metadata['tools'])} tools, "
        f"{len(http_metadata['resources'])} resources"
    )

    # Get proxy metadata
    print("Creating FastMCP proxy and getting metadata...")
    try:
        proxy_metadata = asyncio.run(get_proxy_metadata(args.mcp_url))
        print(
            f"  Proxy: {len(proxy_metadata['tools'])} tools, "
            f"{len(proxy_metadata['resources'])} resources"
        )
    except Exception as e:
        print(f"ERROR: Failed to get proxy metadata: {e}")
        return 2

    # Compare HTTP vs Proxy
    print("\nComparing HTTP vs Proxy metadata...")
    errors = compare_metadata(http_metadata, proxy_metadata)
    if errors:
        print("MISMATCH: HTTP and Proxy metadata differ:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("OK: HTTP and Proxy metadata match!")

    # Optionally compare against snapshot
    if args.compare_snapshot:
        if not args.snapshot.exists():
            print(f"\nWARNING: Snapshot file not found: {args.snapshot}")
            return 0

        print(f"\nComparing Proxy metadata against snapshot...")
        snapshot = load_snapshot(args.snapshot)
        errors = compare_metadata(snapshot, proxy_metadata)
        if errors:
            print("MISMATCH: Proxy metadata differs from snapshot:")
            for error in errors:
                print(f"  - {error}")
            return 1
        print("OK: Proxy metadata matches snapshot!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
