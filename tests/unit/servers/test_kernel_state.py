"""
Unit tests for kernel busy/idle tracking.

Tests the pre/post_run_cell callbacks that maintain the kernel_busy flag in
SharedState, and the NotebookBackend.kernel_status / wait_for_kernel methods
that read it. These work comm-free, so they remain correct even while the
kernel main thread would be blocked in a real stall.
"""

import pytest
import asyncio
from unittest.mock import MagicMock

from instrmcp.servers.jupyter_qcodes.tools import QCodesReadOnlyTools


class MockExecutionInfo:
    """Mock IPython pre_run_cell info object."""

    def __init__(self, raw_cell="", cell_id=None):
        self.raw_cell = raw_cell
        self.cell_id = cell_id


@pytest.fixture
def mock_ipython():
    ipython = MagicMock()
    ipython.user_ns = {"In": [""], "Out": {}}
    ipython.execution_count = 0
    # events.register is a no-op MagicMock; callbacks are invoked directly in tests
    return ipython


@pytest.fixture
def tools(mock_ipython):
    return QCodesReadOnlyTools(mock_ipython)


def _enter_cell(tools, mock_ipython, source="x = 1"):
    """Simulate the kernel starting to run a cell (pre_run_cell)."""
    mock_ipython.execution_count += 1
    tools._capture_current_cell(MockExecutionInfo(raw_cell=source))


def _exit_cell(tools):
    """Simulate the kernel finishing a cell (post_run_cell)."""
    tools._mark_cell_complete(MagicMock())


class TestKernelStateTracking:
    @pytest.mark.asyncio
    async def test_idle_by_default(self, tools):
        status = await tools.kernel_status()
        assert status["state"] == "idle"
        assert status["busy_for_seconds"] == 0.0
        assert status["running_cell_preview"] is None

    @pytest.mark.asyncio
    async def test_busy_after_pre_run_cell(self, tools, mock_ipython):
        _enter_cell(tools, mock_ipython, source="import time; time.sleep(30)")
        status = await tools.kernel_status()
        assert status["state"] == "busy"
        assert status["busy_for_seconds"] >= 0.0
        assert status["running_cell_preview"] == "import time; time.sleep(30)"

    @pytest.mark.asyncio
    async def test_idle_after_post_run_cell(self, tools, mock_ipython):
        _enter_cell(tools, mock_ipython)
        _exit_cell(tools)
        status = await tools.kernel_status()
        assert status["state"] == "idle"
        assert status["running_cell_preview"] is None
        assert status["last_idle_seconds_ago"] is not None

    @pytest.mark.asyncio
    async def test_preview_truncated_to_200_chars(self, tools, mock_ipython):
        long_source = "a" * 500
        _enter_cell(tools, mock_ipython, source=long_source)
        status = await tools.kernel_status()
        assert len(status["running_cell_preview"]) == 200

    @pytest.mark.asyncio
    async def test_wait_returns_immediately_when_idle(self, tools):
        result = await tools.wait_for_kernel(timeout=5.0, poll_interval=0.01)
        assert result["state"] == "idle"
        assert result["timed_out"] is False
        assert result["waited_seconds"] >= 0.0

    @pytest.mark.asyncio
    async def test_wait_times_out_while_busy(self, tools, mock_ipython):
        _enter_cell(tools, mock_ipython, source="while True: pass")
        result = await tools.wait_for_kernel(timeout=0.05, poll_interval=0.01)
        assert result["state"] == "busy"
        assert result["timed_out"] is True
        assert result["running_cell_preview"] == "while True: pass"
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_wait_returns_when_cell_finishes(self, tools, mock_ipython):
        """wait_for_kernel should return idle once post_run_cell fires."""
        _enter_cell(tools, mock_ipython, source="long_cell()")

        async def finish_soon():
            await asyncio.sleep(0.05)
            _exit_cell(tools)

        finisher = asyncio.create_task(finish_soon())
        result = await tools.wait_for_kernel(timeout=5.0, poll_interval=0.01)
        await finisher
        assert result["state"] == "idle"
        assert result["timed_out"] is False
