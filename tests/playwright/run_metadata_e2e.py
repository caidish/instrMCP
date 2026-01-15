"""
Playwright-driven E2E runner for MCP tool/resource metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import httpx

try:
    from tests.playwright.mcp_metadata_client import (
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
        save_snapshot,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from mcp_metadata_client import (  # type: ignore[no-redef]
        MCPMetadataClient,
        build_metadata_snapshot,
        compare_metadata,
        load_snapshot,
        save_snapshot,
    )

DEFAULT_TOKEN = "instrmcp-playwright"
DEFAULT_JUPYTER_PORT = 8888
DEFAULT_MCP_URL = "http://127.0.0.1:8123"
DEFAULT_NOTEBOOK = (
    Path(__file__).parent / "notebooks" / "metadata_e2e.ipynb"
)
DEFAULT_SNAPSHOT = Path(__file__).parent / "metadata_snapshot.json"
DEFAULT_JUPYTER_LOG = Path(__file__).parent / "jupyter_lab.log"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MCP metadata E2E checks via Playwright."
    )
    parser.add_argument(
        "--mode",
        choices=("snapshot", "verify"),
        default="verify",
        help="Create a metadata snapshot or verify against an existing one.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="Path for metadata snapshot JSON.",
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
        help="JSON file with a list of code cell strings to append and run.",
    )
    parser.add_argument(
        "--skip-jupyter",
        action="store_true",
        help="Assume JupyterLab is already running.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip running the notebook via Playwright.",
    )
    parser.add_argument(
        "--keep-jupyter",
        action="store_true",
        help="Leave JupyterLab running after the script finishes.",
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
        "--mcp-url",
        default=DEFAULT_MCP_URL,
        help="Base URL for the MCP server.",
    )
    parser.add_argument(
        "--cell-wait-ms",
        type=int,
        default=500,
        help="Wait time after running each cell in fallback mode.",
    )
    return parser.parse_args()


def _wait_for_http(url: str, timeout_s: int = 30) -> bool:
    start = time.time()
    with httpx.Client(timeout=5.0) as client:
        while time.time() - start < timeout_s:
            try:
                resp = client.get(url)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(1)
    return False


def _start_jupyter_server(
    repo_root: Path, port: int, token: str, log_path: Path
) -> tuple[subprocess.Popen[str], Path]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w")

    env = os.environ.copy()
    env["INSTRMCP_REPO_ROOT"] = str(repo_root)

    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "lab",
        "--no-browser",
        "--ip=127.0.0.1",
        f"--port={port}",
        "--ServerApp.port_retries=0",
        f"--ServerApp.token={token}",
        "--ServerApp.password=",
        f"--ServerApp.root_dir={repo_root}",
    ]

    process: subprocess.Popen[str] = subprocess.Popen(  # type: ignore[assignment]
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    log_file.close()
    return process, log_path


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def _load_extra_cells(path: Path | None) -> list[str]:
    if not path:
        return []
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        raise ValueError("extra cells file must be a JSON list of strings")
    return data


def _run_notebook_playwright(
    base_url: str,
    token: str,
    notebook_rel: str,
    extra_cells: Iterable[str],
    cell_wait_ms: int,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright is required. Install with `pip install playwright` "
            "and run `python -m playwright install`."
        ) from exc

    notebook_rel = notebook_rel.replace(os.sep, "/")
    url = f"{base_url}/lab/tree/{quote(notebook_rel)}?token={token}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000
            )
            page.wait_for_selector(
                ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Notebook", timeout=120000
            )

            if extra_cells:
                _append_cells(page, list(extra_cells))

            _run_all_cells(page, cell_wait_ms)
        finally:
            page.close()
            browser.close()


def _append_cells(page, cells: list[str]) -> None:
    locator = page.locator(
        ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Cell"
    )
    if locator.count() == 0:
        raise RuntimeError("No notebook cells found to append to.")

    locator.last.scroll_into_view_if_needed()
    locator.last.click()
    page.keyboard.press("Escape")

    for cell in cells:
        page.keyboard.press("B")
        page.keyboard.press("Enter")
        page.keyboard.insert_text(cell)
        page.keyboard.press("Shift+Enter")
        page.keyboard.press("Escape")


def _run_all_cells(page, cell_wait_ms: int) -> None:
    ran = False
    try:
        ran = page.evaluate(
            """
() => {
  const app = window.jupyterapp || window.jupyterlab || window.jupyterApp || window.jupyterLab;
  if (!app || !app.commands) {
    return false;
  }
  const commands = ["runmenu:run-all", "notebook:run-all-cells"];
  for (const cmd of commands) {
    if (app.commands.hasCommand(cmd)) {
      app.commands.execute(cmd);
      return true;
    }
  }
  return false;
}
"""
        )
    except Exception:
        ran = False

    if not ran:
        try:
            page.get_by_role("menuitem", name="Run").click(timeout=5000)
            page.get_by_role("menuitem", name="Run All Cells").click(timeout=5000)
            ran = True
        except Exception:
            ran = False

    if not ran:
        locator = page.locator(".jp-Cell")
        count = locator.count()
        if count == 0:
            raise RuntimeError("No notebook cells found to run.")
        locator = page.locator(
            ".jp-NotebookPanel:not(.lm-mod-hidden) .jp-Cell"
        )
        count = locator.count()
        if count == 0:
            raise RuntimeError("No visible notebook cells found to run.")
        locator.first.scroll_into_view_if_needed()
        locator.first.click()
        for _ in range(count):
            page.keyboard.press("Shift+Enter")
            if cell_wait_ms:
                page.wait_for_timeout(cell_wait_ms)


def _wait_for_mcp(base_url: str, timeout_s: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        client = MCPMetadataClient(base_url)
        try:
            client.initialize()
            return True
        except Exception:
            time.sleep(1)
        finally:
            client.close()
    return False


def _snapshot_metadata(mcp_url: str) -> dict:
    client = MCPMetadataClient(mcp_url)
    client.initialize()
    tools = client.list_tools()
    resources = client.list_resources()
    client.close()
    return build_metadata_snapshot(tools, resources)


def main() -> int:
    args = _parse_args()
    repo_root = Path(__file__).resolve().parents[2]

    notebook_path = args.notebook.resolve()
    if not notebook_path.exists():
        print(f"Notebook not found: {notebook_path}")
        return 2

    try:
        notebook_rel = notebook_path.relative_to(repo_root).as_posix()
    except ValueError:
        print("Notebook must be under the repository root.")
        return 2

    jupyter_port = args.jupyter_port
    jupyter_base_url = f"http://127.0.0.1:{jupyter_port}"
    jupyter_proc = None

    try:
        if not args.skip_jupyter:
            if not _is_port_free(jupyter_port):
                new_port = _find_free_port()
                print(
                    f"Port {jupyter_port} is in use; switching to {new_port}."
                )
                jupyter_port = new_port
                jupyter_base_url = f"http://127.0.0.1:{jupyter_port}"
            jupyter_proc, _log_path = _start_jupyter_server(
                repo_root, jupyter_port, args.jupyter_token, args.jupyter_log
            )
            ready = _wait_for_http(f"{jupyter_base_url}/lab?token={args.jupyter_token}")
            if not ready:
                print("JupyterLab did not become ready in time.")
                return 2

        if not args.skip_playwright:
            extra_cells = _load_extra_cells(args.extra_cells)
            _run_notebook_playwright(
                jupyter_base_url,
                args.jupyter_token,
                notebook_rel,
                extra_cells,
                args.cell_wait_ms,
            )

        if not _wait_for_mcp(args.mcp_url):
            print("MCP server did not become ready in time.")
            return 2

        snapshot = _snapshot_metadata(args.mcp_url)
        if args.mode == "snapshot":
            save_snapshot(snapshot, args.snapshot)
            print(f"Saved metadata snapshot to {args.snapshot}")
            return 0

        if not args.snapshot.exists():
            print(f"Snapshot not found: {args.snapshot}")
            print("Run with --mode snapshot to create it.")
            return 2

        expected = load_snapshot(args.snapshot)
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
            _stop_process(jupyter_proc)


if __name__ == "__main__":
    raise SystemExit(main())
