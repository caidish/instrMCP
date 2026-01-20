"""
Process and port management utilities for E2E tests.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def wait_for_http(url: str, timeout_s: int = 30) -> bool:
    """Wait for an HTTP endpoint to become available.

    Args:
        url: URL to poll
        timeout_s: Maximum time to wait in seconds

    Returns:
        True if the endpoint became available, False if timeout
    """
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


def start_jupyter_server(
    repo_root: Path, port: int, token: str, log_path: Path
) -> tuple[subprocess.Popen, Path]:
    """Start a JupyterLab server as a subprocess.

    Args:
        repo_root: Root directory for JupyterLab
        port: Port to run JupyterLab on
        token: Authentication token
        log_path: Path to write logs

    Returns:
        Tuple of (subprocess handle, log path)
    """
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

    process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env=env,
        text=True,
    )
    log_file.close()
    return process, log_path


def kill_port(port: int, wait_for_release: bool = True) -> bool:
    """Kill any process listening on the given port.

    Args:
        port: Port number to kill processes on
        wait_for_release: If True, wait until port is actually free

    Returns:
        True if a process was killed, False otherwise
    """
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
        )
        pids = result.stdout.strip().split()
        if not pids or not pids[0]:
            return False
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass

        if wait_for_release:
            # Wait until port is actually released
            for _ in range(20):  # Up to 2 seconds
                if is_port_free(port):
                    return True
                time.sleep(0.1)
        else:
            time.sleep(0.5)
        return True
    except Exception:
        return False


def is_port_free(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check

    Returns:
        True if the port is free, False if in use
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_free_port() -> int:
    """Find an available port.

    Returns:
        An available port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def stop_process(process: subprocess.Popen) -> None:
    """Stop a subprocess gracefully, with forced kill as fallback.

    Args:
        process: The subprocess to stop
    """
    if process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
