"""
Unit tests for _wait_for_execution completion detection.

Tests the two-phase execution waiting mechanism that detects when cell
execution completes using last_execution_result identity as the primary
completion signal.
"""

import pytest
import asyncio
import time
import sys
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

from instrmcp.servers.jupyter_qcodes.tools import QCodesReadOnlyTools


class MockExecutionResult:
    """Mock IPython execution result object."""

    def __init__(self, execution_count=1, result=None, success=True):
        self.execution_count = execution_count
        self.result = result
        self.success = success


def create_mock_traceback():
    """Create a mock traceback object that can be formatted.

    We generate a real traceback by raising and catching an exception.
    """
    try:
        raise RuntimeError("mock error")
    except RuntimeError:
        import sys

        return sys.exc_info()[2]


class TestWaitForExecution:
    """Test _wait_for_execution completion detection."""

    @pytest.fixture
    def mock_ipython(self):
        """Create a mock IPython instance."""
        ipython = MagicMock()
        ipython.user_ns = {
            "In": [""],
            "Out": {},
        }
        ipython.execution_count = 0
        ipython.last_execution_result = None
        return ipython

    @pytest.fixture
    def tools(self, mock_ipython):
        """Create QCodesReadOnlyTools instance with mock IPython."""
        return QCodesReadOnlyTools(mock_ipython)

    @pytest.mark.asyncio
    async def test_fast_output_via_out_cache(self, tools, mock_ipython):
        """Test fast execution (1+1) completion detected via last_execution_result.

        NOTE: _wait_for_execution no longer retrieves output - it only waits
        for completion. Output retrieval is done separately via
        get_active_cell_output() for consistency.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate cell execution: 1+1
        async def simulate_execution():
            await asyncio.sleep(0.05)  # Small delay
            mock_ipython.execution_count = 1  # Count bumps at START
            mock_ipython.user_ns["In"].append("1+1")
            await asyncio.sleep(0.05)  # Execution time
            mock_ipython.user_ns["Out"][1] = 2  # Result appears in Out
            mock_ipython.last_execution_result = MockExecutionResult(1, result=2)

        # Start simulation and wait for execution
        asyncio.create_task(simulate_execution())

        result = await tools._wait_for_execution(initial_count, timeout=5.0)

        # _wait_for_execution only detects completion, not output
        assert result["status"] == "completed"
        assert result["has_error"] is False
        assert result["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_long_running_silent_cell(self, tools, mock_ipython):
        """Test long-running silent cell (time.sleep; x = 1) via last_execution_result.

        NOTE: _wait_for_execution no longer retrieves output - it only waits
        for completion. Output retrieval is done separately.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate long-running silent cell
        async def simulate_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1  # Count bumps at START
            mock_ipython.user_ns["In"].append("time.sleep(2); x = 1")
            # Simulate long execution (but we use shorter time in test)
            await asyncio.sleep(0.3)
            # No Out entry (assignment doesn't produce output)
            # last_execution_result changes when COMPLETE
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        start = time.time()
        result = await tools._wait_for_execution(initial_count, timeout=5.0)
        elapsed = time.time() - start

        assert result["status"] == "completed"
        assert result["has_error"] is False
        assert result["cell_number"] == 1
        # Should wait for last_execution_result to change, not return immediately
        assert elapsed >= 0.3  # Waited for execution to complete

    @pytest.mark.asyncio
    async def test_delayed_output_via_frontend(self, tools, mock_ipython):
        """Test delayed output (sleep; print) completion detected via last_execution_result.

        NOTE: _wait_for_execution no longer retrieves output - it only waits
        for completion. Output retrieval is done separately via
        get_active_cell_output() for consistency.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate delayed print output
        async def simulate_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("time.sleep(0.2); print('hello')")
            await asyncio.sleep(0.2)
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        result = await tools._wait_for_execution(initial_count, timeout=5.0)

        # _wait_for_execution only detects completion
        assert result["status"] == "completed"
        assert result["has_error"] is False
        assert result["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_error_detection_via_traceback_identity(self, tools, mock_ipython):
        """Test error detection via sys.last_traceback identity check."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Create a real traceback object that can be formatted
        new_tb = create_mock_traceback()

        # Save original sys attributes
        original_last_traceback = getattr(sys, "last_traceback", None)
        original_last_type = getattr(sys, "last_type", None)
        original_last_value = getattr(sys, "last_value", None)

        try:
            # Start with no traceback
            if hasattr(sys, "last_traceback"):
                delattr(sys, "last_traceback")

            async def simulate_execution():
                await asyncio.sleep(0.05)
                mock_ipython.execution_count = 1
                mock_ipython.user_ns["In"].append("1/0")
                await asyncio.sleep(0.05)
                # Error occurs - set sys.last_* attributes with real traceback
                sys.last_traceback = new_tb
                sys.last_type = ZeroDivisionError
                sys.last_value = ZeroDivisionError("division by zero")
                mock_ipython.last_execution_result = MockExecutionResult(
                    1, result=None, success=False
                )

            asyncio.create_task(simulate_execution())

            result = await tools._wait_for_execution(initial_count, timeout=5.0)

            assert result["status"] == "error"
            assert result["has_error"] is True
            assert result["error_type"] == "ZeroDivisionError"
        finally:
            # Restore original sys attributes
            if original_last_traceback is not None:
                sys.last_traceback = original_last_traceback
            elif hasattr(sys, "last_traceback"):
                delattr(sys, "last_traceback")
            if original_last_type is not None:
                sys.last_type = original_last_type
            if original_last_value is not None:
                sys.last_value = original_last_value

    @pytest.mark.asyncio
    async def test_repeated_same_type_error(self, tools, mock_ipython):
        """Test that repeated same-type errors are detected via traceback identity."""
        initial_count = 1  # Simulate second error after first
        initial_result = MockExecutionResult(1, result=None, success=False)
        mock_ipython.last_execution_result = initial_result
        mock_ipython.execution_count = 1
        mock_ipython.user_ns["In"].append('raise ValueError("first")')

        # Create real traceback objects (different instances)
        first_error_tb = create_mock_traceback()
        second_error_tb = create_mock_traceback()

        # Save original sys attributes
        original_last_traceback = getattr(sys, "last_traceback", None)
        original_last_type = getattr(sys, "last_type", None)
        original_last_value = getattr(sys, "last_value", None)

        try:
            # Set initial error state (first ValueError)
            sys.last_traceback = first_error_tb
            sys.last_type = ValueError
            sys.last_value = ValueError("first")

            async def simulate_second_error():
                await asyncio.sleep(0.05)
                mock_ipython.execution_count = 2  # Second execution starts
                mock_ipython.user_ns["In"].append('raise ValueError("second")')
                await asyncio.sleep(0.05)
                # Second error - DIFFERENT traceback object, same type
                sys.last_traceback = second_error_tb
                sys.last_value = ValueError("second")
                mock_ipython.last_execution_result = MockExecutionResult(
                    2, result=None, success=False
                )

            asyncio.create_task(simulate_second_error())

            result = await tools._wait_for_execution(initial_count, timeout=5.0)

            assert result["status"] == "error"
            assert result["has_error"] is True
            # Key: second ValueError is detected because traceback OBJECT changed
            assert result["error_type"] == "ValueError"
        finally:
            # Restore original sys attributes
            if original_last_traceback is not None:
                sys.last_traceback = original_last_traceback
            elif hasattr(sys, "last_traceback"):
                delattr(sys, "last_traceback")
            if original_last_type is not None:
                sys.last_type = original_last_type
            if original_last_value is not None:
                sys.last_value = original_last_value

    @pytest.mark.asyncio
    async def test_no_frontend_comms_uses_kernel_signals(self, tools, mock_ipython):
        """Test execution works without frontend comms using kernel signals.

        NOTE: _wait_for_execution only detects completion, it does not
        retrieve or check for output. Output is fetched separately.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        async def simulate_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("x = 42")
            await asyncio.sleep(0.1)
            # No Out entry, no frontend, but last_execution_result changes
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        result = await tools._wait_for_execution(initial_count, timeout=5.0)

        # _wait_for_execution only detects completion
        assert result["status"] == "completed"
        assert result["has_error"] is False
        assert result["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_frontend_error_output_detection(self, tools, mock_ipython):
        """Test error detection via sys.last_traceback identity.

        NOTE: _wait_for_execution no longer fetches frontend output.
        Errors are detected via sys.last_traceback identity change.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Create a real traceback object
        new_tb = create_mock_traceback()

        # Save original sys attributes
        original_last_traceback = getattr(sys, "last_traceback", None)
        original_last_type = getattr(sys, "last_type", None)
        original_last_value = getattr(sys, "last_value", None)

        try:
            # Start with no traceback
            if hasattr(sys, "last_traceback"):
                delattr(sys, "last_traceback")

            async def simulate_execution():
                await asyncio.sleep(0.05)
                mock_ipython.execution_count = 1
                mock_ipython.user_ns["In"].append("1/0")
                await asyncio.sleep(0.1)
                # Error occurs - set sys.last_* attributes
                sys.last_traceback = new_tb
                sys.last_type = ZeroDivisionError
                sys.last_value = ZeroDivisionError("division by zero")
                mock_ipython.last_execution_result = MockExecutionResult(
                    1, result=None, success=False
                )

            asyncio.create_task(simulate_execution())

            result = await tools._wait_for_execution(initial_count, timeout=5.0)

            assert result["status"] == "error"
            assert result["has_error"] is True
            assert result["error_type"] == "ZeroDivisionError"
        finally:
            # Restore original sys attributes
            if original_last_traceback is not None:
                sys.last_traceback = original_last_traceback
            elif hasattr(sys, "last_traceback"):
                delattr(sys, "last_traceback")
            if original_last_type is not None:
                sys.last_type = original_last_type
            if original_last_value is not None:
                sys.last_value = original_last_value

    @pytest.mark.asyncio
    async def test_timeout_when_no_completion_signal(self, tools, mock_ipython):
        """Test timeout when no completion signal arrives."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate execution that never completes
        async def simulate_stuck_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("while True: pass")
            # Never set last_execution_result

        asyncio.create_task(simulate_stuck_execution())

        result = await tools._wait_for_execution(initial_count, timeout=0.5)

        assert result["status"] == "timeout"
        assert "Timeout" in result["message"]

    @pytest.mark.asyncio
    async def test_execution_count_beyond_target(self, tools, mock_ipython):
        """Test detection when execution_count advances past target (another cell ran).

        When the execution count advances beyond the target, _wait_for_execution
        detects that the target cell completed (even if we missed the exact moment).
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        async def simulate_rapid_execution():
            # Use 0.08s delays (> Windows ~15.6ms timer resolution) to avoid race conditions
            await asyncio.sleep(0.08)
            mock_ipython.execution_count = 1  # First cell starts
            mock_ipython.user_ns["In"].append("x = 1")
            await asyncio.sleep(0.08)
            mock_ipython.execution_count = 2  # Second cell starts immediately
            mock_ipython.user_ns["In"].append("y = 2")

        asyncio.create_task(simulate_rapid_execution())

        result = await tools._wait_for_execution(initial_count, timeout=5.0)

        # _wait_for_execution detects completion when count advances past target
        assert result["status"] == "completed"
        assert result["has_error"] is False
        assert result["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_waits_until_execution_complete(self, tools, mock_ipython):
        """Test that _wait_for_execution waits until execution completes.

        NOTE: The previous 'grace period' tests are obsolete because
        _wait_for_execution no longer does output fetching.
        This test simply verifies we wait for completion.
        """
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        async def simulate_slow_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("time.sleep(0.5)")
            # Simulate 0.3s execution time
            await asyncio.sleep(0.3)
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_slow_execution())

        start = time.time()
        result = await tools._wait_for_execution(initial_count, timeout=5.0)
        end = time.time()

        assert result["status"] == "completed"
        # Should have waited for the execution to complete (~0.35s total)
        assert (end - start) >= 0.3

    # NOTE: The following tests were removed because they tested obsolete functionality:
    #
    # - test_grace_period_uses_cache_only
    # - test_final_fetch_bypasses_cache
    # - test_final_fetch_only_once
    # - test_late_output_captured_by_final_fetch
    #
    # These tests were for the old _wait_for_execution design that included output
    # retrieval with grace periods and cache management. The new design separates
    # execution waiting from output retrieval - _wait_for_execution only waits for
    # completion while output is fetched separately via get_active_cell_output().


class TestAsyncGetCellOutput:
    """Test that _get_cell_output is properly async."""

    @pytest.fixture
    def mock_ipython(self):
        """Create a mock IPython instance."""
        ipython = MagicMock()
        ipython.user_ns = {"In": [""], "Out": {}}
        ipython.execution_count = 0
        return ipython

    @pytest.fixture
    def tools(self, mock_ipython):
        """Create QCodesReadOnlyTools instance."""
        return QCodesReadOnlyTools(mock_ipython)

    @pytest.mark.asyncio
    async def test_get_cell_output_is_async(self, tools):
        """Test _get_cell_output doesn't block event loop."""
        import asyncio

        # Verify it's a coroutine function
        assert asyncio.iscoroutinefunction(tools._get_cell_output)

    @pytest.mark.asyncio
    async def test_get_cell_output_uses_async_sleep(self, tools):
        """Test _get_cell_output uses await asyncio.sleep, not time.sleep."""
        with patch("instrmcp.servers.jupyter_qcodes.active_cell_bridge") as mock_bridge:
            mock_bridge.get_cached_cell_output.return_value = None
            mock_bridge.get_cell_outputs.return_value = {"success": True}

            # This should not block
            start = time.time()
            await tools._get_cell_output(1)
            elapsed = time.time() - start

            # Should take ~0.1s (async sleep) not block indefinitely
            assert elapsed < 0.5
