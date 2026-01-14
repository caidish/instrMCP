"""
MeasureIt backend for sweep operations.

Handles all MeasureIt-related operations including:
- Sweep status monitoring
- Waiting for sweep completion
- Killing sweeps
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional

from ...backend.base import BaseBackend, SharedState

logger = logging.getLogger(__name__)

# Delay in seconds between checks for wait_for_all_sweeps and wait_for_sweep
WAIT_DELAY = 1.0

# Import MeasureIt types with fallback
try:
    from measureit.sweep.base_sweep import BaseSweep
    from measureit.sweep.progress import SweepState

    SWEEP_STATE_ERROR = SweepState.ERROR.value  # "error"
    SWEEP_STATE_RUNNING = (SweepState.RAMPING.value, SweepState.RUNNING.value)
except ImportError:  # pragma: no cover - MeasureIt optional
    BaseSweep = None  # type: ignore[assignment]
    SWEEP_STATE_ERROR = "error"
    SWEEP_STATE_RUNNING = ("ramping", "running")


class MeasureItBackend(BaseBackend):
    """Backend for MeasureIt sweep operations."""

    def __init__(self, state: SharedState):
        """Initialize MeasureIt backend.

        Args:
            state: SharedState instance containing shared resources
        """
        super().__init__(state)

    async def get_measureit_status(self) -> Dict[str, Any]:
        """Check if any measureit sweep is currently running.

        Returns information about active measureit sweeps in the notebook namespace,
        including sweep type, status, and basic configuration if available.

        Returns:
            Dict containing:
                - active: bool - whether any sweep is active
                - sweeps: Dict mapping variable names to Dicts of active sweep information:
                    "variable_name" (str),  "type" (str), "module_name" (str), "state" (str), "progress" (float or None), "time_elapsed" (float or None), "time_remaining" (float or None)
                - error: str (if any error occurred)
        """
        try:
            if BaseSweep is None:
                return {
                    "active": False,
                    "sweeps": {},
                    "error": "MeasureIt library not available",
                }

            result = {"active": False, "sweeps": {}}

            # Look for MeasureIt sweep objects in the namespace
            for var_name, var_value in self.namespace.items():
                # Skip private/internal variables
                if var_name.startswith("_"):
                    continue

                if isinstance(var_value, BaseSweep):
                    sweep_info = {
                        "variable_name": var_name,
                        "type": type(var_value).__name__,
                        "module": getattr(var_value, "__module__", ""),
                    }
                    progress_state = var_value.progressState
                    sweep_info["state"] = progress_state.state.value
                    result["active"] = result["active"] or (
                        sweep_info["state"] in SWEEP_STATE_RUNNING
                    )
                    sweep_info["progress"] = progress_state.progress
                    sweep_info["time_elapsed"] = progress_state.time_elapsed
                    sweep_info["time_remaining"] = progress_state.time_remaining

                    # Capture error information if present
                    error_message = getattr(progress_state, "error_message", None)
                    if error_message:
                        sweep_info["error_message"] = error_message

                    result["sweeps"][var_name] = sweep_info

            return result

        except Exception as e:
            logger.error(f"Error checking MeasureIt status: {e}")
            return {"active": False, "sweeps": {}, "error": str(e)}

    async def kill_sweep(self, var_name: str) -> Dict[str, Any]:
        """Kill a running MeasureIt sweep to release resources.

        UNSAFE: This tool stops a running sweep, which may leave instruments
        in an intermediate state. Use when a sweep needs to be terminated
        due to timeout, error, or user request.

        Args:
            var_name: Name of the sweep variable in the notebook namespace

        Returns:
            Dict containing:
                success: bool - whether the kill was successful
                sweep_name: str - name of the sweep
                previous_state: str - state before kill
                error: str (if any error occurred)
        """
        try:
            if BaseSweep is None:
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": "MeasureIt library not available",
                }

            # Check if the variable exists in namespace
            if var_name not in self.namespace:
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": f"Variable '{var_name}' not found in namespace",
                }

            sweep = self.namespace[var_name]

            # Verify it's a sweep object
            if not isinstance(sweep, BaseSweep):
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": f"Variable '{var_name}' is not a MeasureIt sweep (got {type(sweep).__name__})",
                }

            # Get state before kill
            previous_state = sweep.progressState.state.value

            # Execute sweep.kill() via Qt's thread-safe mechanism
            #
            # The MCP server runs in a separate thread from the sweep's Qt thread.
            # We use QMetaObject.invokeMethod with QueuedConnection to queue the
            # kill directly on the sweep's Qt thread - the same mechanism MeasureIt
            # uses internally. This bypasses Tornado/asyncio entirely.
            try:
                from PyQt5.QtCore import QObject, QMetaObject, Qt, pyqtSlot

                QueuedConnection = Qt.QueuedConnection
            except ImportError:
                from PyQt6.QtCore import QObject, QMetaObject, Qt, pyqtSlot

                # PyQt6 moved ConnectionType to an enum
                QueuedConnection = Qt.ConnectionType.QueuedConnection

            # Create or reuse a kill proxy that lives on the sweep's thread
            proxy = getattr(sweep, "_mcp_kill_proxy", None)
            if proxy is None:

                class _KillProxy(QObject):
                    def __init__(self, target_sweep):
                        super().__init__()
                        self._sweep = target_sweep

                    @pyqtSlot()
                    def do_kill(self):
                        self._sweep.kill()

                proxy = _KillProxy(sweep)
                proxy.moveToThread(sweep.thread())
                sweep._mcp_kill_proxy = proxy

            # Queue the kill on the sweep's Qt thread
            QMetaObject.invokeMethod(proxy, "do_kill", QueuedConnection)

            # Wait briefly for the kill to take effect
            # The kill is queued and will execute when Qt processes events
            await asyncio.sleep(0.5)

            # Verify the sweep was killed
            new_state = sweep.progressState.state.value

            return {
                "success": True,
                "sweep_name": var_name,
                "sweep_type": type(sweep).__name__,
                "previous_state": previous_state,
                "new_state": new_state,
                "message": f"Sweep '{var_name}' killed successfully. Resources released.",
                "warning": "UNSAFE: Sweep was terminated. Instruments may need re-initialization.",
            }

        except Exception as e:
            logger.error(f"Error killing sweep '{var_name}': {e}")
            return {
                "success": False,
                "sweep_name": var_name,
                "error": str(e),
            }

    async def wait_for_sweep(
        self, var_name: str, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Wait for a measureit sweep with a given variable name to finish and kill it.

        Waits for the sweep with the given name to stop running, kills it to release
        hardware resources, and returns information about it.

        Sweeps are killed in the following cases:
        - If already in error state when called: killed immediately
        - If already finished (done state) when called: killed immediately
        - If it enters error state while waiting: killed immediately
        - When it finishes successfully: killed to release hardware resources

        Note: If timeout is reached, the sweep is NOT killed (still running);
        a kill_suggestion is provided for the user to decide.

        Args:
            var_name: Name of the sweep variable to wait for.
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            Dict containing:
                sweep: Dict of information about the sweep as in get_measureit_status, or None if no
                running sweep with this name exists.
                error: str (if any error occurred, including timeout or sweep error)
                timed_out: bool (True if timeout was reached)
                sweep_error: bool (True if sweep ended with error state)
                killed: bool (True if sweep was killed successfully)
                kill_result: Dict with result of killing the sweep
        """
        status = await self.get_measureit_status()
        if status.get("error"):
            return {"sweep": None, "error": status["error"]}
        target = status["sweeps"].get(var_name)

        if not target:
            return {"sweep": None}

        # Check if sweep is already in error state - kill it and return error info
        if target["state"] == SWEEP_STATE_ERROR:
            error_msg = target.get(
                "error_message", f"Sweep '{var_name}' is already in error state"
            )
            logger.warning(
                "Sweep '%s' already in error state: %s. Killing sweep.",
                var_name,
                error_msg,
            )

            # Kill the errored sweep (kill_sweep handles timeout internally)
            kill_result = await self.kill_sweep(var_name)

            return {
                "sweep": target,
                "error": error_msg,
                "sweep_error": True,
                "killed": kill_result.get("success", False),
                "kill_result": kill_result,
            }

        # If sweep is already done (not running, not error), kill to release resources
        if target["state"] not in SWEEP_STATE_RUNNING:
            logger.info(
                "Sweep '%s' already done (state: %s). Killing to release resources.",
                var_name,
                target["state"],
            )
            kill_result = await self.kill_sweep(var_name)
            return {
                "sweep": target,
                "killed": kill_result.get("success", False),
                "kill_result": kill_result,
            }

        start_time = time.time()
        while True:
            await asyncio.sleep(WAIT_DELAY)

            # Refresh status FIRST, then check timeout (so we have accurate state)
            status = await self.get_measureit_status()
            if status.get("error"):
                return {"sweep": target, "error": status["error"]}

            # Update target with latest state (None if sweep disappeared)
            target = status["sweeps"].get(var_name)

            if not target:
                # Sweep no longer in namespace
                return {"sweep": None}

            # Check for error state FIRST - kill before returning timeout
            if target["state"] == SWEEP_STATE_ERROR:
                error_msg = target.get("error_message", "Sweep ended with error")
                logger.warning(
                    "Sweep '%s' entered error state: %s. Killing sweep.",
                    var_name,
                    error_msg,
                )
                kill_result = await self.kill_sweep(var_name)
                return {
                    "sweep": target,
                    "error": error_msg,
                    "sweep_error": True,
                    "killed": kill_result.get("success", False),
                    "kill_result": kill_result,
                }

            # Check timeout AFTER error handling
            if timeout is not None and (time.time() - start_time) > timeout:
                return {
                    "sweep": target,
                    "error": f"Timeout after {timeout}s waiting for sweep '{var_name}' to complete",
                    "timed_out": True,
                    "kill_suggestion": f"Use measureit_kill_sweep('{var_name}') to stop the sweep and release resources",
                }

            if target["state"] not in SWEEP_STATE_RUNNING:
                break

        # Sweep finished successfully - kill to release hardware resources
        kill_result = await self.kill_sweep(var_name)

        return {
            "sweep": target,
            "killed": kill_result.get("success", False),
            "kill_result": kill_result,
        }

    async def wait_for_all_sweeps(
        self, timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Wait until all running measureit sweeps finish and kill them to release resources.

        Waits until all currently running sweeps have stopped running, kills them to release
        hardware resources, and returns information about them.

        Sweeps are killed in the following cases:
        - If already in error state when called: killed immediately (but waiting continues)
        - If already finished (done state) when called: killed immediately
        - If they enter error state while waiting: killed immediately (but waiting continues)
        - When they finish successfully: killed to release hardware resources

        Note: If timeout is reached, sweeps are NOT killed (still running);
        a kill_suggestion is provided for the user to decide.

        Args:
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            Dict containing:
                sweeps: Dict mapping variable names to Dicts of information about the initially running sweeps as in get_measureit_status, empty if no sweeps were running.
                error: str (if any error occurred, including timeout or sweep error)
                timed_out: bool (True if timeout was reached)
                sweep_error: bool (True if any sweep ended with error state)
                errored_sweeps: list of sweep names that had errors (if any)
                killed: bool (True if sweeps were killed successfully)
                kill_results: Dict mapping sweep names to kill results
        """
        try:
            status = await self.get_measureit_status()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("wait_for_all_sweeps failed to get status: %s", exc)
            return {"sweeps": None, "error": str(exc)}

        if status.get("error"):
            return {"sweeps": None, "error": status["error"]}

        sweeps = status["sweeps"]

        # Track all sweeps we'll monitor and their final results
        all_kill_results = {}
        error_messages = []
        errored_sweeps = []

        # Kill sweeps already in error state (but continue waiting for running ones)
        already_errored = {
            k: v for k, v in sweeps.items() if v["state"] == SWEEP_STATE_ERROR
        }
        for name, sweep_info in already_errored.items():
            error_msg = sweep_info.get(
                "error_message", f"Sweep '{name}' is already in error state"
            )
            error_messages.append(f"{name}: {error_msg}")
            errored_sweeps.append(name)
            logger.warning(
                "Sweep '%s' already in error state: %s. Killing sweep.",
                name,
                error_msg,
            )
            all_kill_results[name] = await self.kill_sweep(name)

        # Kill sweeps already in done state (to release resources)
        already_done = {
            k: v
            for k, v in sweeps.items()
            if v["state"] not in SWEEP_STATE_RUNNING and v["state"] != SWEEP_STATE_ERROR
        }
        for name in already_done.keys():
            logger.info("Sweep '%s' already done. Killing to release resources.", name)
            all_kill_results[name] = await self.kill_sweep(name)

        initial_running = {
            k: v for k, v in sweeps.items() if v["state"] in SWEEP_STATE_RUNNING
        }

        # If no running sweeps, return results from already-handled sweeps
        if not initial_running:
            if not already_errored and not already_done:
                return {"sweeps": None}
            # Return combined results
            all_sweeps = {**already_errored, **already_done}
            all_killed = bool(all_kill_results) and all(
                r.get("success", False) for r in all_kill_results.values()
            )
            result = {
                "sweeps": all_sweeps,
                "killed": all_killed,
                "kill_results": all_kill_results,
            }
            if errored_sweeps:
                result["error"] = "; ".join(error_messages)
                result["sweep_error"] = True
                result["errored_sweeps"] = errored_sweeps
            return result

        start_time = time.time()
        while True:
            await asyncio.sleep(WAIT_DELAY)

            # Refresh status FIRST, then check timeout (so we have accurate state)
            status = await self.get_measureit_status()

            if status.get("error"):
                return {"sweeps": initial_running, "error": status["error"]}

            current_sweeps = status["sweeps"]
            still_running = False
            loop_errored = []

            # Update initial_running with latest state and detect errors
            for k in initial_running.keys():
                if k in current_sweeps:
                    initial_running[k] = current_sweeps[k]
                    state = current_sweeps[k]["state"]

                    if state in SWEEP_STATE_RUNNING:
                        still_running = True
                    elif state == SWEEP_STATE_ERROR:
                        loop_errored.append(k)

            # Kill any errored sweeps (do this BEFORE timeout check so we don't miss them)
            if loop_errored:
                for name in loop_errored:
                    if name not in errored_sweeps:  # Don't double-kill
                        sweep_info = initial_running.get(name, {})
                        msg = sweep_info.get(
                            "error_message", f"Sweep '{name}' ended with error"
                        )
                        error_messages.append(f"{name}: {msg}")
                        errored_sweeps.append(name)
                        logger.warning(
                            "Sweep '%s' entered error state: %s. Killing sweep.",
                            name,
                            msg,
                        )
                        all_kill_results[name] = await self.kill_sweep(name)

            # Check timeout AFTER processing errors (so errored sweeps get killed)
            if timeout is not None and (time.time() - start_time) > timeout:
                running_names = [
                    k
                    for k, v in initial_running.items()
                    if v["state"] in SWEEP_STATE_RUNNING
                ]

                # Combine all sweeps and include already-killed results
                all_sweeps = {**already_errored, **already_done, **initial_running}
                all_killed = bool(all_kill_results) and all(
                    r.get("success", False) for r in all_kill_results.values()
                )
                result = {
                    "sweeps": all_sweeps,
                    "error": f"Timeout after {timeout}s waiting for sweeps to complete",
                    "timed_out": True,
                    "kill_suggestion": (
                        ", ".join(
                            [f"measureit_kill_sweep('{n}')" for n in running_names]
                        )
                        if running_names
                        else None
                    ),
                }
                if all_kill_results:
                    result["kill_results"] = all_kill_results
                    result["killed"] = all_killed
                if errored_sweeps:
                    result["sweep_error"] = True
                    result["errored_sweeps"] = errored_sweeps
                    result["error"] = f"Timeout after {timeout}s; errors: " + "; ".join(
                        error_messages
                    )
                return result

            if not still_running:
                break

        # Kill all finished sweeps to release hardware resources
        for name in initial_running.keys():
            if name not in all_kill_results:  # Don't double-kill errored ones
                all_kill_results[name] = await self.kill_sweep(name)

        # Combine all results
        all_sweeps = {**already_errored, **already_done, **initial_running}
        all_killed = bool(all_kill_results) and all(
            r.get("success", False) for r in all_kill_results.values()
        )

        result = {
            "sweeps": all_sweeps,
            "killed": all_killed,
            "kill_results": all_kill_results,
        }
        if errored_sweeps:
            result["error"] = "; ".join(error_messages)
            result["sweep_error"] = True
            result["errored_sweeps"] = errored_sweeps

        return result
