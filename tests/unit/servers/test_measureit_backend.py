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

    def __init__(self, state_value="running", progress=0.5):
        self.state = MagicMock()
        self.state.value = state_value
        self.progress = progress
        self.time_elapsed = 10.0
        self.time_remaining = 10.0
        self.error_message = None


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

    def kill(self):
        if self.current_sweep:
            self.current_sweep.kill()

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

            # Queue without current sweep should not be included
            assert result["active"] is False
            assert "my_queue" not in result["sweeps"]

    @pytest.mark.asyncio
    async def test_kill_sweep_with_sweep_queue(self, backend, mock_state):
        """Test kill_sweep() with SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QMetaObject"
        ) as mock_qmeta, patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QObject"
        ):
            queue = MockSweepQueue()
            mock_state.namespace["my_queue"] = queue

            # Mock QMetaObject.invokeMethod to simulate successful kill
            mock_qmeta.invokeMethod = MagicMock()

            result = await backend.kill_sweep("my_queue")

            # Should successfully kill the queue
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
        """Test kill_all_sweeps() with both BaseSweep and SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QMetaObject"
        ) as mock_qmeta, patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QObject"
        ):
            sweep = MockBaseSweep()
            queue = MockSweepQueue()
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
        """Test wait_for_sweep() with SweepQueue."""
        with patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.SweepQueue",
            MockSweepQueue,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.BaseSweep",
            MockBaseSweep,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QMetaObject"
        ) as mock_qmeta, patch(
            "instrmcp.servers.jupyter_qcodes.options.measureit.backend.QObject"
        ):
            # Create a queue that's already done
            queue = MockSweepQueue(state="done")
            mock_state.namespace["my_queue"] = queue

            # Mock QMetaObject.invokeMethod to simulate successful kill
            mock_qmeta.invokeMethod = MagicMock()

            result = await backend.wait_for_sweep("my_queue", timeout=30.0, kill=True)

            # Should find the sweep and kill it since it's already done
            assert result["sweep"] is not None
            assert result["sweep"]["variable_name"] == "my_queue"
            assert result["killed"] is True
