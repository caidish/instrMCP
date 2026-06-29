"""
Kernel Busy/Idle State Tests (test_12_kernel_state.py)

Purpose: Verify the kernel-awareness tools (`notebook_kernel_status` and
`notebook_wait_for_kernel`) work end-to-end against a real JupyterLab kernel.

The critical property under test: because the MCP HTTP server runs on its own
background thread, these tools must respond CORRECTLY EVEN WHILE the kernel main
thread is fully blocked executing a long `time.sleep(...)` cell. That is exactly
the stalled-kernel situation that motivated the feature.

Test IDs:
- KS-001 to KS-004

These tools are read-only and available in safe mode.
"""

import json

import pytest

from tests.e2e.helpers.jupyter_helpers import run_cell
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    list_mcp_tools,
    parse_tool_result,
)


def _status(url: str, arguments: dict | None = None) -> dict:
    """Call notebook_kernel_status and return the parsed JSON payload."""
    result = call_mcp_tool(url, "notebook_kernel_status", arguments or {})
    success, content = parse_tool_result(result)
    assert success, f"notebook_kernel_status failed: {content}"
    return json.loads(content)


def _wait(url: str, arguments: dict) -> dict:
    """Call notebook_wait_for_kernel and return the parsed JSON payload."""
    result = call_mcp_tool(url, "notebook_wait_for_kernel", arguments)
    success, content = parse_tool_result(result)
    assert success, f"notebook_wait_for_kernel failed: {content}"
    return json.loads(content)


def _start_long_cell(page, seconds: int) -> None:
    """Start a blocking sleep cell WITHOUT waiting for it to finish.

    This leaves the kernel main thread blocked so we can observe the busy state.
    """
    run_cell(page, f"import time\ntime.sleep({seconds})", wait_for_output=False)


class TestKernelStateTools:
    """End-to-end tests for kernel busy/idle awareness."""

    @pytest.mark.p1
    def test_kernel_status_tools_available(self, mcp_server):
        """KS-000: Both kernel tools are exposed in safe mode."""
        tools = list_mcp_tools(mcp_server["url"])
        names = [t.get("name") for t in tools if isinstance(t, dict)]
        assert "notebook_kernel_status" in names, names
        assert "notebook_wait_for_kernel" in names, names

    @pytest.mark.p0
    def test_kernel_status_idle(self, mcp_server):
        """KS-001: kernel_status reports idle when nothing is running."""
        # Ensure any setup execution has drained.
        drained = _wait(mcp_server["url"], {"timeout": 30, "poll_interval": 0.5})
        assert drained["state"] == "idle", drained

        status = _status(mcp_server["url"])
        assert status["state"] == "idle", status
        assert status["busy_for_seconds"] == 0.0, status
        assert status["running_cell_preview"] is None, status

    @pytest.mark.p0
    def test_kernel_status_busy_during_blocking_cell(self, mcp_server):
        """KS-002: kernel_status reports busy while a sleep cell blocks the kernel.

        Proves the MCP server responds while the kernel main thread is blocked,
        and that wait_for_kernel then observes completion.
        """
        page = mcp_server["page"]

        # Make sure we start idle.
        _wait(mcp_server["url"], {"timeout": 30, "poll_interval": 0.5})

        # Launch a 10s blocking cell and let execution actually start.
        _start_long_cell(page, 10)
        page.wait_for_timeout(2500)

        # The kernel main thread is now blocked in time.sleep, yet the MCP
        # server (separate thread) must still answer this read.
        status = _status(mcp_server["url"], {"detailed": True})
        assert status["state"] == "busy", status
        assert status["busy_for_seconds"] >= 0.0, status
        assert status["running_cell_preview"] is not None, status
        assert "sleep" in status["running_cell_preview"], status

        # wait_for_kernel should block until the sleep finishes, then report idle.
        waited = _wait(mcp_server["url"], {"timeout": 30, "poll_interval": 0.5})
        assert waited["state"] == "idle", waited
        assert waited["timed_out"] is False, waited

        # And a follow-up status confirms idle.
        final = _status(mcp_server["url"])
        assert final["state"] == "idle", final

    @pytest.mark.p1
    def test_wait_for_kernel_times_out_while_busy(self, mcp_server):
        """KS-003: wait_for_kernel reports a timeout while the kernel stays busy."""
        page = mcp_server["page"]

        _wait(mcp_server["url"], {"timeout": 30, "poll_interval": 0.5})

        # Launch a long blocking cell.
        _start_long_cell(page, 15)
        page.wait_for_timeout(2000)

        # Wait with a short timeout while the cell is still sleeping.
        timed = _wait(mcp_server["url"], {"timeout": 2, "poll_interval": 0.5})
        assert timed["state"] == "busy", timed
        assert timed["timed_out"] is True, timed
        assert timed["running_cell_preview"] is not None, timed
        assert "hint" in timed, timed

        # Drain so the kernel returns to idle before the fixture tears down.
        drained = _wait(mcp_server["url"], {"timeout": 30, "poll_interval": 0.5})
        assert drained["state"] == "idle", drained
