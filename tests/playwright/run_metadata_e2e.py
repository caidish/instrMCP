"""
Playwright-driven E2E runner for MCP tool/resource metadata.

This script orchestrates:
1. Starting JupyterLab server
2. Running a notebook via Playwright browser automation
3. Snapshotting or verifying MCP metadata
"""

from __future__ import annotations

from pathlib import Path

try:
    from tests.playwright.helpers import (
        cleanup_working_notebook,
        get_snapshot_path,
        has_user_config,
        is_port_free,
        find_free_port,
        kill_port,
        load_extra_cells,
        parse_e2e_args,
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
        save_snapshot,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from helpers import (  # type: ignore[no-redef]
        cleanup_working_notebook,
        get_snapshot_path,
        has_user_config,
        is_port_free,
        find_free_port,
        kill_port,
        load_extra_cells,
        parse_e2e_args,
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
        save_snapshot,
    )


def snapshot_metadata(mcp_url: str) -> dict:
    """Get current metadata from the MCP server.

    Args:
        mcp_url: MCP server base URL

    Returns:
        Metadata snapshot dict with tools and resources
    """
    client = MCPMetadataClient(mcp_url)
    client.initialize()
    tools = client.list_tools()
    resources = client.list_resources()
    client.close()
    return build_metadata_snapshot(tools, resources)


def main() -> int:
    """Main entry point for the E2E runner."""
    args = parse_e2e_args()
    repo_root = Path(__file__).resolve().parents[2]

    # Determine snapshot path based on user config presence
    snapshot_path = get_snapshot_path(args.snapshot)

    original_notebook = args.notebook.resolve()
    if not original_notebook.exists():
        print(f"Notebook not found: {original_notebook}")
        return 2

    jupyter_port = args.jupyter_port
    jupyter_base_url = f"http://127.0.0.1:{jupyter_port}"
    jupyter_proc = None
    mcp_port = args.mcp_port
    working_notebook = None

    # Clean up existing processes if requested
    if args.clean:
        if kill_port(mcp_port):
            print(f"Killed existing process on MCP port {mcp_port}.")
        if kill_port(jupyter_port):
            print(f"Killed existing process on Jupyter port {jupyter_port}.")
        cleanup_working_notebook()

    try:
        # Copy notebook to working directory to avoid modifying original
        working_notebook = prepare_working_notebook(original_notebook)
        try:
            notebook_rel = working_notebook.relative_to(repo_root).as_posix()
        except ValueError:
            print("Notebook must be under the repository root.")
            return 2

        if not args.skip_jupyter:
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
                print("JupyterLab did not become ready in time.")
                return 2

        if not args.skip_playwright:
            extra_cells = load_extra_cells(args.extra_cells)
            run_notebook_playwright(
                jupyter_base_url,
                args.jupyter_token,
                notebook_rel,
                extra_cells,
                args.cell_wait_ms,
            )

        if not wait_for_mcp(args.mcp_url):
            print("MCP server did not become ready in time.")
            return 2

        snapshot = snapshot_metadata(args.mcp_url)
        if args.mode == "snapshot":
            save_snapshot(snapshot, snapshot_path)
            print(f"Saved metadata snapshot to {snapshot_path}")
            return 0

        if not snapshot_path.exists():
            print(f"Snapshot not found: {snapshot_path}")
            print("Run with --mode snapshot to create it.")
            if has_user_config():
                print(
                    "Note: User config detected. "
                    "Create user snapshot with --mode snapshot"
                )
            return 2

        expected = load_snapshot(snapshot_path)
        errors = compare_metadata(expected, snapshot)
        if errors:
            print("Metadata mismatches detected:")
            for error in errors:
                print(f"- {error}")
            return 1

        print("Metadata check passed.")
        return 0
    finally:
        if jupyter_proc and not args.keep_jupyter:
            stop_process(jupyter_proc)
            # Also clean up MCP server that was started by the notebook
            kill_port(mcp_port)
        # Always clean up working notebook to avoid leaving modified copies
        if not args.keep_jupyter:
            cleanup_working_notebook()


if __name__ == "__main__":
    raise SystemExit(main())
