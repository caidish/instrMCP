"""
Unit tests for MeasureIt backend with SweepQueue support.

Tests that the backend correctly handles both BaseSweep and SweepQueue objects.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from instrmcp.servers.jupyter_qcodes.options.measureit.backend import (
    MeasureItBackend,
    _is_sweep,
    _get_progress_state,
)


class MockProgressState:
    """Mock progress state for testing."""

    def __init__(self, state_value="running", progress=0.5, is_queued=False):
        self.state = MagicMock()
        self.state.value = state_value
        self.progress = progress
        self.time_elapsed = 10.0
        self.time_remaining = 10.0
        self.error_message = None
        self.is_queued = is_queued


class MockBaseSweep:
    """Mock BaseSweep for testing."""

    def __init__(self, state="running"):
        self.progressState = MockProgressState(state)
        self.__module__ = "measureit.sweep.sweep1d"

    def kill(self):
        self.progressState.state.value = "stopped"

    def thread(self):
        return MagicMock()


class MockSweepQueue:
    """Mock SweepQueue for testing."""

    def __init__(self, state="running"):
        self.current_sweep = MockBaseSweep(state)
        self.__module__ = "measureit.tools.sweep_queue"
        self.queue = []  # Empty queue by default
        self._last_error = None
        self._effective_state = state  # Track the effective state

    def status(self):
        """Return comprehensive status dict like real SweepQueue."""
        current_state = None
        if self.current_sweep and hasattr(self.current_sweep, "progressState"):
            current_state = self.current_sweep.progressState.state.value

        # Determine effective state
        if self._last_error:
            effective_state = "stopped"
        elif current_state in ("running", "ramping"):
            effective_state = "running"
        elif current_state == "paused":
            effective_state = "paused"
        elif current_state == "error":
            effective_state = "error"
        elif self.queue:
            effective_state = "pending"
        else:
            effective_state = "idle"

        return {
            "effective_state": effective_state,
            "current_sweep_state": current_state,
            "queue_length": len(self.queue),
            "current_sweep_type": (
                type(self.current_sweep).__name__ if self.current_sweep else None
            ),
            "last_error": self._last_error,
        }

    def kill(self):
        if self.current_sweep:
            self.current_sweep.kill()

    def kill_all(self):
        """Kill current sweep and clear queue."""
        if self.current_sweep:
            self.current_sweep.kill()
        self.queue.clear()
        self._last_error = None

    def thread(self):
        return MagicMock()


class TestHelperFunctions:
    """Test helper functions for sweep detection and state access."""

    def test_is_sweep_with_base_sweep(self):
        """Test _is_sweep() with BaseSweep object."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            sweep = MockBaseSweep()
            assert _is_sweep(sweep) is True

    def test_is_sweep_with_sweep_queue(self):
        """Test _is_sweep() with SweepQueue object."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ):
            queue = MockSweepQueue()
            assert _is_sweep(queue) is True

    def test_is_sweep_with_non_sweep(self):
        """Test _is_sweep() with non-sweep object."""
        assert _is_sweep("not a sweep") is False
        assert _is_sweep(123) is False
        assert _is_sweep(None) is False

    def test_get_progress_state_from_base_sweep(self):
        """Test _get_progress_state() with BaseSweep."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            sweep = MockBaseSweep()
            progress_state = _get_progress_state(sweep)
            assert progress_state is not None
            assert progress_state.state.value == "running"

    def test_get_progress_state_from_sweep_queue(self):
        """Test _get_progress_state() with SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ):
            queue = MockSweepQueue()
            progress_state = _get_progress_state(queue)
            assert progress_state is not None
            assert progress_state.state.value == "running"

    def test_get_progress_state_from_sweep_queue_no_current_sweep(self):
        """Test _get_progress_state() with SweepQueue that has no current sweep."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ):
            queue = MockSweepQueue()
            queue.current_sweep = None
            progress_state = _get_progress_state(queue)
            assert progress_state is None

    def test_get_progress_state_from_non_sweep(self):
        """Test _get_progress_state() with non-sweep object."""
        progress_state = _get_progress_state("not a sweep")
        assert progress_state is None


class TestMeasureItBackend:
    """Test MeasureItBackend class with SweepQueue support."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock SharedState."""
        state = MagicMock()
        state.namespace = {}
        state.kernel = MagicMock()
        return state

    @pytest.fixture
    def backend(self, mock_state):
        """Create a MeasureItBackend instance."""
        return MeasureItBackend(mock_state)

    @pytest.mark.asyncio
    async def test_get_measureit_status_with_base_sweep(self, backend, mock_state):
        """Test get_measureit_status() with BaseSweep."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            sweep = MockBaseSweep()
            mock_state.namespace["my_sweep"] = sweep

            result = await backend.get_measureit_status()

            assert result["active"] is True
            assert "my_sweep" in result["sweeps"]
            assert result["sweeps"]["my_sweep"]["state"] == "running"
            assert result["sweeps"]["my_sweep"]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_get_measureit_status_with_sweep_queue(self, backend, mock_state):
        """Test get_measureit_status() with SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            queue = MockSweepQueue()
            mock_state.namespace["my_queue"] = queue

            result = await backend.get_measureit_status()

            assert result["active"] is True
            assert "my_queue" in result["sweeps"]
            assert result["sweeps"]["my_queue"]["state"] == "running"

    @pytest.mark.asyncio
    async def test_get_measureit_status_with_multiple_sweeps(self, backend, mock_state):
        """Test get_measureit_status() with both BaseSweep and SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            sweep = MockBaseSweep()
            queue = MockSweepQueue()
            mock_state.namespace["my_sweep"] = sweep
            mock_state.namespace["my_queue"] = queue

            result = await backend.get_measureit_status()

            assert result["active"] is True
            assert len(result["sweeps"]) == 2
            assert "my_sweep" in result["sweeps"]
            assert "my_queue" in result["sweeps"]

    @pytest.mark.asyncio
    async def test_get_measureit_status_with_sweep_queue_no_current_sweep(
        self, backend, mock_state
    ):
        """Test get_measureit_status() with SweepQueue that has no current sweep."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            queue = MockSweepQueue()
            queue.current_sweep = None
            mock_state.namespace["my_queue"] = queue

            result = await backend.get_measureit_status()

            # Queue without current sweep is now shown with "idle" effective_state
            assert result["active"] is False
            assert "my_queue" in result["sweeps"]
            assert result["sweeps"]["my_queue"]["state"] == "idle"

    @pytest.mark.asyncio
    async def test_get_measureit_status_skips_queued_sweeps(self, backend, mock_state):
        """Test that sweeps with is_queued=True are excluded from status."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            # Create a queue and individual sweeps
            queue = MockSweepQueue(state="running")
            sweep1 = MockBaseSweep(state="running")  # Current sweep in queue
            sweep2 = MockBaseSweep(state="idle")  # Queued, waiting
            sweep3 = MockBaseSweep(state="idle")  # Queued, waiting

            # Mark sweep2 and sweep3 as queued
            sweep2.progressState.is_queued = True
            sweep3.progressState.is_queued = True

            mock_state.namespace["sweep_queue"] = queue
            mock_state.namespace["s1"] = sweep1
            mock_state.namespace["s2"] = sweep2
            mock_state.namespace["s3"] = sweep3

            result = await backend.get_measureit_status()

            # Only sweep_queue and s1 should be in results, not s2 or s3
            assert "sweep_queue" in result["sweeps"]
            assert "s1" in result["sweeps"]
            assert "s2" not in result["sweeps"]
            assert "s3" not in result["sweeps"]

    @pytest.mark.asyncio
    async def test_kill_all_sweeps_skips_queued_sweeps(self, backend, mock_state):
        """Test that kill_all_sweeps() skips sweeps with is_queued=True.

        This test only verifies that queued sweeps are excluded from the kill list.
        It doesn't test actual killing (which requires Qt mocking).
        """
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ):
            # Create only queued sweeps (no queue object to avoid Qt kill logic)
            sweep1 = MockBaseSweep(state="idle")  # Queued, waiting
            sweep2 = MockBaseSweep(state="idle")  # Queued, waiting

            # Mark both sweeps as queued
            sweep1.progressState.is_queued = True
            sweep2.progressState.is_queued = True

            mock_state.namespace["s1"] = sweep1
            mock_state.namespace["s2"] = sweep2

            result = await backend.kill_all_sweeps()

            # No sweeps should be killed since they're all queued
            assert result["success"] is True
            assert result["killed_count"] == 0
            assert result["message"] == "No sweeps found in namespace"

    @pytest.mark.asyncio
    async def test_kill_sweep_with_sweep_queue(self, backend, mock_state):
        """Test kill_sweep() with SweepQueue (already stopped state)."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "PyQt5.QtCore.QMetaObject", create=True
        ) as mock_qmeta, patch(
            "PyQt5.QtCore.QObject", create=True
        ), patch(
            "PyQt5.QtCore.Qt", create=True
        ), patch(
            "PyQt5.QtCore.pyqtSlot", lambda: lambda x: x
        ):
            # Create a queue that's already stopped (skip the running path)
            queue = MockSweepQueue(state="stopped")
            mock_state.namespace["my_queue"] = queue

            # Mock QMetaObject.invokeMethod to simulate successful kill
            mock_qmeta.invokeMethod = MagicMock()

            result = await backend.kill_sweep("my_queue")

            # Should successfully kill the queue (already stopped)
            assert result["success"] is True
            assert result["sweep_name"] == "my_queue"

    @pytest.mark.asyncio
    async def test_kill_sweep_with_non_sweep(self, backend, mock_state):
        """Test kill_sweep() with non-sweep object."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ):
            mock_state.namespace["not_sweep"] = "just a string"

            result = await backend.kill_sweep("not_sweep")

            assert result["success"] is False
            assert "not a MeasureIt sweep" in result["error"]

    @pytest.mark.asyncio
    async def test_kill_all_sweeps_with_mixed_sweeps(self, backend, mock_state):
        """Test kill_all_sweeps() with both BaseSweep and SweepQueue (stopped state)."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "PyQt5.QtCore.QMetaObject", create=True
        ) as mock_qmeta, patch(
            "PyQt5.QtCore.QObject", create=True
        ), patch(
            "PyQt5.QtCore.Qt", create=True
        ), patch(
            "PyQt5.QtCore.pyqtSlot", lambda: lambda x: x
        ):
            # Create stopped sweeps to avoid running Qt code path
            sweep = MockBaseSweep(state="stopped")
            queue = MockSweepQueue(state="stopped")
            mock_state.namespace["my_sweep"] = sweep
            mock_state.namespace["my_queue"] = queue

            # Mock QMetaObject.invokeMethod to simulate successful kill
            mock_qmeta.invokeMethod = MagicMock()

            result = await backend.kill_all_sweeps()

            # Should kill both sweeps
            assert result["success"] is True
            assert result["killed_count"] == 2
            assert "my_sweep" in result["results"]
            assert "my_queue" in result["results"]

    @pytest.mark.asyncio
    async def test_wait_for_sweep_with_sweep_queue(self, backend, mock_state):
        """Test wait_for_sweep() with SweepQueue (already done)."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "PyQt5.QtCore.QMetaObject", create=True
        ) as mock_qmeta, patch(
            "PyQt5.QtCore.QObject", create=True
        ), patch(
            "PyQt5.QtCore.Qt", create=True
        ), patch(
            "PyQt5.QtCore.pyqtSlot", lambda: lambda x: x
        ):
            # Create a queue that's already done (idle state)
            queue = MockSweepQueue(state="stopped")
            mock_state.namespace["my_queue"] = queue

            # Mock QMetaObject.invokeMethod to simulate successful kill
            mock_qmeta.invokeMethod = MagicMock()

            result = await backend.wait_for_sweep("my_queue", timeout=30.0, kill=True)

            # Should find the sweep and kill it since it's already done
            assert result["sweep"] is not None
            assert result["sweep"]["variable_name"] == "my_queue"
            assert result["killed"] is True
