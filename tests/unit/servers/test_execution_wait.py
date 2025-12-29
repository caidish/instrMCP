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
        """Test fast output (1+1) detected via Out cache."""
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

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None  # No frontend outputs
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"
        assert result["has_output"] is True
        assert result["output"] == "2"
        assert result["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_long_running_silent_cell(self, tools, mock_ipython):
        """Test long-running silent cell (time.sleep; x = 1) via last_execution_result."""
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

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None  # No frontend outputs
            start = time.time()
            result = await tools._wait_for_execution(initial_count, timeout=5.0)
            elapsed = time.time() - start

        assert result["status"] == "completed"
        assert result["has_output"] is False
        assert result["cell_number"] == 1
        # Should wait for last_execution_result to change, not return immediately
        assert elapsed >= 0.3  # Waited for execution to complete

    @pytest.mark.asyncio
    async def test_delayed_output_via_frontend(self, tools, mock_ipython):
        """Test delayed output (sleep; print) via frontend outputs."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate delayed print output
        frontend_output = None

        async def simulate_execution():
            nonlocal frontend_output
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("time.sleep(0.2); print('hello')")
            await asyncio.sleep(0.2)
            # Frontend outputs populated after execution
            frontend_output = {
                "has_output": True,
                "outputs": [{"type": "stream", "name": "stdout", "text": "hello\n"}],
            }
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        async def mock_get_output(cell_number, bypass_cache=False):
            return frontend_output

        with patch.object(tools, "_get_cell_output", side_effect=mock_get_output):
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"
        assert result["has_output"] is True
        assert result["outputs"][0]["text"] == "hello\n"

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

            with patch.object(
                tools, "_get_cell_output", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = None
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

            with patch.object(
                tools, "_get_cell_output", new_callable=AsyncMock
            ) as mock_get:
                mock_get.return_value = None
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
        """Test execution works without frontend comms using kernel signals."""
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

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            # Simulate no frontend connection
            mock_get.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"
        assert result["has_output"] is False
        assert result["message"] == "Cell executed (no output)"

    @pytest.mark.asyncio
    async def test_frontend_error_output_detection(self, tools, mock_ipython):
        """Test error detection via frontend outputs with type='error'."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        frontend_output = None

        async def simulate_execution():
            nonlocal frontend_output
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("1/0")
            await asyncio.sleep(0.1)
            # Frontend populates error output
            frontend_output = {
                "has_output": True,
                "outputs": [
                    {
                        "type": "error",
                        "ename": "ZeroDivisionError",
                        "evalue": "division by zero",
                        "traceback": [
                            "Traceback...",
                            "ZeroDivisionError: division by zero",
                        ],
                    }
                ],
            }
            mock_ipython.last_execution_result = MockExecutionResult(
                1, result=None, success=False
            )

        asyncio.create_task(simulate_execution())

        async def mock_get_output(cell_number, bypass_cache=False):
            return frontend_output

        # Don't trigger sys.last_traceback check
        with (
            patch.object(tools, "_get_cell_output", side_effect=mock_get_output),
            patch.object(sys, "last_traceback", None, create=True),
        ):
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "error"
        assert result["has_error"] is True
        assert result["error_type"] == "ZeroDivisionError"
        assert "division by zero" in result["error_message"]

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

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=0.5)

        assert result["status"] == "timeout"
        assert "Timeout" in result["message"]

    @pytest.mark.asyncio
    async def test_execution_count_beyond_target(self, tools, mock_ipython):
        """Test detection when execution_count advances past target (another cell ran)."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        async def simulate_rapid_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1  # First cell starts
            mock_ipython.user_ns["In"].append("x = 1")
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 2  # Second cell starts immediately
            mock_ipython.user_ns["In"].append("y = 2")

        asyncio.create_task(simulate_rapid_execution())

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"
        assert result["has_output"] is False
        assert result["message"] == "Cell executed successfully with no output"

    @pytest.mark.asyncio
    async def test_grace_period_only_after_completion(self, tools, mock_ipython):
        """Test grace period only starts after last_execution_result changes."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        completion_time = None

        async def simulate_slow_execution():
            nonlocal completion_time
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("time.sleep(0.5)")
            # Simulate 0.3s execution time
            await asyncio.sleep(0.3)
            completion_time = time.time()
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_slow_execution())

        with patch.object(
            tools, "_get_cell_output", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None
            start = time.time()
            result = await tools._wait_for_execution(initial_count, timeout=5.0)
            end = time.time()

        assert result["status"] == "completed"
        # Should have waited ~0.3s for execution + ~0.2s grace period
        assert (end - start) >= 0.4

    @pytest.mark.asyncio
    async def test_grace_period_uses_cache_only(self, tools, mock_ipython):
        """Test that during grace period, only cache is checked (no frontend requests)."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        completion_detected = False
        frontend_calls_after_completion = []

        async def simulate_execution():
            nonlocal completion_detected
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("x = 1")
            await asyncio.sleep(0.1)
            completion_detected = True
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        async def track_get_cell_output(cell_number, bypass_cache=False):
            # Track calls made after completion
            if completion_detected:
                frontend_calls_after_completion.append(
                    {"cell_number": cell_number, "bypass_cache": bypass_cache}
                )
            return None

        with (
            patch.object(
                tools, "_get_cell_output", side_effect=track_get_cell_output
            ) as mock_get,
            patch(
                "instrmcp.servers.jupyter_qcodes.tools.active_cell_bridge.get_cached_cell_output"
            ) as mock_cache,
        ):
            mock_cache.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"

        # Before completion: _get_cell_output called normally
        # During grace period: NO calls to _get_cell_output (only cache checked)
        # After grace period: ONE final call with bypass_cache=True

        # Filter calls made after completion
        calls_during_grace = [
            c for c in frontend_calls_after_completion if not c["bypass_cache"]
        ]
        final_bypass_calls = [
            c for c in frontend_calls_after_completion if c["bypass_cache"]
        ]

        # During grace period: should NOT call _get_cell_output (only cache)
        assert len(calls_during_grace) == 0, (
            "Expected no frontend calls during grace period, "
            f"but got {len(calls_during_grace)} calls"
        )

        # After grace period: should have exactly ONE bypass_cache=True call
        assert (
            len(final_bypass_calls) == 1
        ), f"Expected 1 final bypass call, got {len(final_bypass_calls)}"

        # Verify cache was checked during grace period
        assert mock_cache.called, "Cache should be checked during grace period"

    @pytest.mark.asyncio
    async def test_final_fetch_bypasses_cache(self, tools, mock_ipython):
        """Test that final fetch after grace period uses bypass_cache=True."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        final_fetch_params = None

        async def simulate_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("x = 1")
            await asyncio.sleep(0.1)
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)

        asyncio.create_task(simulate_execution())

        call_count = 0

        async def track_bypass_cache(cell_number, bypass_cache=False):
            nonlocal final_fetch_params, call_count
            call_count += 1
            # Track the last call with bypass_cache=True
            if bypass_cache:
                final_fetch_params = {
                    "cell_number": cell_number,
                    "bypass_cache": bypass_cache,
                    "call_order": call_count,
                }
            return None

        with (
            patch.object(
                tools, "_get_cell_output", side_effect=track_bypass_cache
            ) as mock_get,
            patch(
                "instrmcp.servers.jupyter_qcodes.tools.active_cell_bridge.get_cached_cell_output"
            ) as mock_cache,
        ):
            mock_cache.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"

        # Verify final fetch used bypass_cache=True
        assert (
            final_fetch_params is not None
        ), "Expected a final fetch with bypass_cache=True"
        assert final_fetch_params["bypass_cache"] is True
        assert final_fetch_params["cell_number"] == 1

    @pytest.mark.asyncio
    async def test_final_fetch_only_once(self, tools, mock_ipython):
        """Test that post_completion_fetch_done flag prevents duplicate final fetches."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        bypass_cache_calls = []

        async def simulate_rapid_execution():
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append("x = 1")
            await asyncio.sleep(0.1)
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)
            # Wait for grace period to elapse, then bump execution_count
            await asyncio.sleep(0.6)  # Grace period (0.5s) + buffer
            mock_ipython.execution_count = 2  # Trigger Check 5

        asyncio.create_task(simulate_rapid_execution())

        async def track_bypass_calls(cell_number, bypass_cache=False):
            if bypass_cache:
                bypass_cache_calls.append(
                    {"cell_number": cell_number, "time": time.time()}
                )
            return None

        with (
            patch.object(tools, "_get_cell_output", side_effect=track_bypass_calls),
            patch(
                "instrmcp.servers.jupyter_qcodes.tools.active_cell_bridge.get_cached_cell_output"
            ) as mock_cache,
        ):
            mock_cache.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        assert result["status"] == "completed"

        # Should have exactly ONE bypass_cache=True call, even though both
        # Check 5 (execution_count > target) and Check 6 (grace elapsed) could trigger
        assert (
            len(bypass_cache_calls) == 1
        ), f"Expected exactly 1 bypass call, got {len(bypass_cache_calls)}"

    @pytest.mark.asyncio
    async def test_late_output_captured_by_final_fetch(self, tools, mock_ipython):
        """Test that outputs arriving after completion are captured by final fetch."""
        initial_count = 0
        initial_result = None
        mock_ipython.last_execution_result = initial_result

        # Simulate output that arrives late (during grace period)
        late_output = None

        async def simulate_execution_with_late_output():
            nonlocal late_output
            await asyncio.sleep(0.05)
            mock_ipython.execution_count = 1
            mock_ipython.user_ns["In"].append(
                "import time; print('late'); time.sleep(0.01)"
            )
            await asyncio.sleep(0.1)
            # Execution completes, but output hasn't arrived yet
            mock_ipython.last_execution_result = MockExecutionResult(1, result=None)
            # Output arrives during grace period (after completion)
            await asyncio.sleep(0.2)
            late_output = {
                "has_output": True,
                "outputs": [{"type": "stream", "name": "stdout", "text": "late\n"}],
            }

        asyncio.create_task(simulate_execution_with_late_output())

        async def mock_get_output(cell_number, bypass_cache=False):
            # Only return late output when bypass_cache=True (final fetch)
            if bypass_cache:
                return late_output
            return None

        with (
            patch.object(tools, "_get_cell_output", side_effect=mock_get_output),
            patch(
                "instrmcp.servers.jupyter_qcodes.tools.active_cell_bridge.get_cached_cell_output"
            ) as mock_cache,
        ):
            mock_cache.return_value = None
            result = await tools._wait_for_execution(initial_count, timeout=5.0)

        # Late output should be captured by final fetch
        assert result["status"] == "completed"
        assert result["has_output"] is True
        assert result["outputs"][0]["text"] == "late\n"


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
        with patch(
            "instrmcp.servers.jupyter_qcodes.tools.active_cell_bridge"
        ) as mock_bridge:
            mock_bridge.get_cached_cell_output.return_value = None
            mock_bridge.get_cell_outputs.return_value = {"success": True}

            # This should not block
            start = time.time()
            await tools._get_cell_output(1)
            elapsed = time.time() - start

            # Should take ~0.1s (async sleep) not block indefinitely
            assert elapsed < 0.5
