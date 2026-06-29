"""Run-file helpers.

When ``instrmcp launch`` starts a supervisor it writes a small JSON run file so that
later ``instrmcp status / stop / restart / logs`` invocations (separate processes) can
discover the live supervisor's API endpoint and pid.
"""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path
from typing import Optional

RUN_DIR = Path.home() / ".instrmcp" / "run"


def run_file_path(profile_name: str) -> Path:
    return RUN_DIR / f"{profile_name}.json"


def write_run_file(profile_name: str, info: dict) -> Path:
    """Write the run file for a profile (0o600)."""
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    path = run_file_path(profile_name)
    path.write_text(json.dumps(info, indent=2))
    os.chmod(path, 0o600)
    return path


def read_run_file(profile_name: str) -> Optional[dict]:
    """Read the run file for a profile, or None if absent/corrupt."""
    path = run_file_path(profile_name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def remove_run_file(profile_name: str) -> None:
    run_file_path(profile_name).unlink(missing_ok=True)


def process_alive(pid: int) -> bool:
    """Return True if a process with ``pid`` exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_process(pid: int) -> None:
    """Best-effort SIGTERM to ``pid`` (ignored if it's already gone)."""
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
