"""
Mock IPython kernel and components for testing.

Provides mock implementations of IPython components needed for
testing Jupyter integration without running a full kernel.
"""

from unittest.mock import MagicMock, Mock
from typing import Dict, Any, List, Optional
import time


class MockExecutionInfo:
    """Mock IPython execution info object."""

    def __init__(self, raw_cell: str, cell_id: Optional[str] = None):
        self.raw_cell = raw_cell
        self.cell_id = cell_id or f"cell_{int(time.time() * 1000)}"
        self.store_history = True


class MockIPythonEvents:
    """Mock IPython events system for testing."""

    def __init__(self):
        self._callbacks = {
            "pre_run_cell": [],
            "post_run_cell": [],
            "pre_execute": [],
            "post_execute": [],
        }

    def register(self, event_type: str, callback):
        """Register an event callback."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)

    def unregister(self, event_type: str, callback):
        """Unregister an event callback."""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)

    def trigger(self, event_type: str, *args, **kwargs):
        """Trigger an event (for testing purposes)."""
        if event_type in self._callbacks:
            for callback in self._callbacks[event_type]:
                callback(*args, **kwargs)


class MockIPythonKernel:
    """Mock IPython kernel for testing Jupyter integration."""

    def __init__(self, user_namespace: Optional[Dict[str, Any]] = None):
        self.user_ns = user_namespace or {}
        self.user_ns_hidden = {}
        self.events = MockIPythonEvents()
        self.execution_count = 0
        self.last_execution_result = None
        self.last_execution_succeeded = True
        self.history_manager = Mock()

        # Mock display system
        self.display_pub = Mock()

    def run_cell(
        self, cell_content: str, silent: bool = False, store_history: bool = True
    ):
        """Execute a cell (mock implementation)."""
        self.execution_count += 1

        # Create execution info
        exec_info = MockExecutionInfo(cell_content)

        # Trigger pre_run_cell event
        self.events.trigger("pre_run_cell", exec_info)

        # Mock execution (just return success)
        result = Mock()
        result.success = True
        result.result = None
        result.error_in_exec = None

        self.last_execution_result = result
        self.last_execution_succeeded = True

        # Trigger post_run_cell event
        self.events.trigger("post_run_cell", result)

        return result

    def ex(self, cmd: str):
        """Execute a command (simplified mock)."""
        exec(cmd, self.user_ns)

    def push(self, variables: Dict[str, Any]):
        """Push variables to the namespace."""
        self.user_ns.update(variables)

    def get_parent(self):
        """Get parent message (mock)."""
        return {"header": {"msg_id": "test_msg_id"}}


def create_mock_ipython_with_instruments(
    instruments: Dict[str, Any],
) -> MockIPythonKernel:
    """Create a mock IPython kernel with instruments in the namespace."""
    namespace = instruments.copy()
    return MockIPythonKernel(user_namespace=namespace)


def create_mock_ipython_with_data(data: Dict[str, Any]) -> MockIPythonKernel:
    """Create a mock IPython kernel with data variables in the namespace."""
    namespace = data.copy()
    return MockIPythonKernel(user_namespace=namespace)
