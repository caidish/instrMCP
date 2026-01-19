"""
Test that stdio_proxy metadata aligns with direct HTTP MCP server metadata.

This test verifies that FastMCP's as_proxy() correctly mirrors all tool and
resource metadata from the HTTP backend. This is critical because Claude
Desktop/Code uses the stdio proxy interface.

The test:
1. Starts JupyterLab and runs a notebook to start the MCP server (by default)
2. Connects to the running HTTP MCP server
3. Creates a FastMCP proxy pointing to the same server
4. Compares tools and resources between HTTP and proxy
5. Optionally compares against the baseline snapshot
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient

try:
    from tests.playwright.helpers import (
        cleanup_working_notebook,
        DEFAULT_JUPYTER_LOG,
        DEFAULT_JUPYTER_PORT,
        DEFAULT_MCP_PORT,
        DEFAULT_MCP_URL,
        DEFAULT_NOTEBOOK,
        DEFAULT_SNAPSHOT,
        DEFAULT_TOKEN,
        find_free_port,
        is_port_free,
        kill_port,
        load_extra_cells,
        prepare_working_notebook,
        run_notebook_playwright,
        start_jupyter_server,
        stop_process,
        wait_for_http,
        wait_for_mcp,
    )
    from tests.playwright.metadata_client import (
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
    )
except ImportError:
    from helpers import (  # type: ignore[no-redef]
        cleanup_working_notebook,
        DEFAULT_JUPYTER_LOG,
        DEFAULT_JUPYTER_PORT,
        DEFAULT_MCP_PORT,
        DEFAULT_MCP_URL,
        DEFAULT_NOTEBOOK,
        DEFAULT_SNAPSHOT,
        DEFAULT_TOKEN,
        find_free_port,
        is_port_free,
        kill_port,
        load_extra_cells,
        prepare_working_notebook,
        run_notebook_playwright,
        start_jupyter_server,
        stop_process,
        wait_for_http,
        wait_for_mcp,
    )
    from metadata_client import (  # type: ignore[no-redef]
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
    )


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


def launch_mcp_server(args: argparse.Namespace) -> tuple:
    """Launch JupyterLab and run notebook to start MCP server.

    Args:
        args: Parsed arguments containing jupyter/notebook config

    Returns:
        Tuple of (jupyter_proc, mcp_port)
    """
    repo_root = Path(__file__).resolve().parents[2]

    original_notebook = args.notebook.resolve()
    if not original_notebook.exists():
        raise FileNotFoundError(f"Notebook not found: {original_notebook}")

    jupyter_port = args.jupyter_port
    jupyter_base_url = f"http://127.0.0.1:{jupyter_port}"
    mcp_port = args.mcp_port

    # Clean up existing processes if requested
    if args.clean:
        if kill_port(mcp_port):
            print(f"Killed existing process on MCP port {mcp_port}.")
        if kill_port(jupyter_port):
            print(f"Killed existing process on Jupyter port {jupyter_port}.")
        cleanup_working_notebook()

    # Copy notebook to working directory
    working_notebook = prepare_working_notebook(original_notebook)
    try:
        notebook_rel = working_notebook.relative_to(repo_root).as_posix()
    except ValueError:
        raise ValueError("Notebook must be under the repository root.")

    # Start JupyterLab
    if not is_port_free(jupyter_port):
        new_port = find_free_port()
        print(f"Port {jupyter_port} is in use; switching to {new_port}.")
        jupyter_port = new_port
        jupyter_base_url = f"http://127.0.0.1:{jupyter_port}"

    jupyter_proc, _log_path = start_jupyter_server(
        repo_root, jupyter_port, args.jupyter_token, args.jupyter_log
    )

    ready = wait_for_http(f"{jupyter_base_url}/lab?token={args.jupyter_token}")
    if not ready:
        stop_process(jupyter_proc)
        cleanup_working_notebook()
        raise RuntimeError("JupyterLab did not become ready in time.")

    # Run notebook via Playwright
    extra_cells = load_extra_cells(args.extra_cells)
    run_notebook_playwright(
        jupyter_base_url,
        args.jupyter_token,
        notebook_rel,
        extra_cells,
        args.cell_wait_ms,
    )

    # Wait for MCP server
    if not wait_for_mcp(args.mcp_url):
        stop_process(jupyter_proc)
        kill_port(mcp_port)
        cleanup_working_notebook()
        raise RuntimeError("MCP server did not become ready in time.")

    return jupyter_proc, mcp_port


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
        help="Compare proxy metadata against snapshot file.",
    )
    # Playwright launch options (launches by default)
    parser.add_argument(
        "--skip-launch",
        action="store_true",
        help="Skip launching MCP server (assume it's already running).",
    )
    parser.add_argument(
        "--notebook",
        type=Path,
        default=DEFAULT_NOTEBOOK,
        help="Notebook to execute in JupyterLab.",
    )
    parser.add_argument(
        "--extra-cells",
        type=Path,
        help="JSON file with extra code cells to append and run.",
    )
    parser.add_argument(
        "--jupyter-port",
        type=int,
        default=DEFAULT_JUPYTER_PORT,
        help="JupyterLab port to use.",
    )
    parser.add_argument(
        "--jupyter-token",
        default=DEFAULT_TOKEN,
        help="JupyterLab auth token to use.",
    )
    parser.add_argument(
        "--jupyter-log",
        type=Path,
        default=DEFAULT_JUPYTER_LOG,
        help="Log file path for the JupyterLab process.",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=DEFAULT_MCP_PORT,
        help="MCP server port (used for cleanup).",
    )
    parser.add_argument(
        "--cell-wait-ms",
        type=int,
        default=1000,
        help="Wait time after running each cell.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Kill existing processes on Jupyter and MCP ports before starting.",
    )
    parser.add_argument(
        "--keep-jupyter",
        action="store_true",
        help="Leave JupyterLab running after the test.",
    )
    args = parser.parse_args()

    jupyter_proc = None
    mcp_port = args.mcp_port

    try:
        # Launch MCP server via Playwright (by default)
        if not args.skip_launch:
            print("Launching MCP server via Playwright...")
            jupyter_proc, mcp_port = launch_mcp_server(args)
            print("MCP server is ready.")
        else:
            # Check HTTP server is running
            print(f"Checking HTTP MCP server at {args.mcp_url}...")
            if not verify_http_server_running(args.mcp_url):
                print("ERROR: HTTP MCP server is not running.")
                print(
                    "Start it first with run_metadata_e2e.py "
                    "or remove --skip-launch flag"
                )
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

            print("\nComparing Proxy metadata against snapshot...")
            snapshot = load_snapshot(args.snapshot)
            errors = compare_metadata(snapshot, proxy_metadata)
            if errors:
                print("MISMATCH: Proxy metadata differs from snapshot:")
                for error in errors:
                    print(f"  - {error}")
                return 1
            print("OK: Proxy metadata matches snapshot!")

        return 0

    finally:
        # Cleanup if we launched the server
        if jupyter_proc and not args.keep_jupyter:
            print("\nCleaning up...")
            stop_process(jupyter_proc)
            kill_port(mcp_port)
            cleanup_working_notebook()


if __name__ == "__main__":
    raise SystemExit(main())
