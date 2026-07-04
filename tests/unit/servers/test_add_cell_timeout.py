"""
Reproducing test for the markdown add_cell false-timeout bug.

Bug: `notebook_add_cell(cell_type="markdown")` returns
    {"success": false, "error": "Timeout waiting for frontend response after 2.0s"}
even though the markdown cell IS added. The frontend does an EXTRA async hop for
markdown (insertBelow -> changeCellType), so its `add_cell_response` (success=True)
arrives a bit LATER than the old hardcoded 2.0s default. Code cells respond within
2.0s and work fine.

These tests simulate a frontend that responds SUCCESSFULLY but slightly slower than
the old 2.0s default, deterministically (no real sleeps): a fake threading.Event
whose `.wait(timeout)` delivers the matching `add_cell_response` only when the
caller's timeout is long enough (>= 2.5s). With the old 2.0s default the wait
returns False (the buggy false-timeout); with the fixed ~10s default it succeeds.
"""

import pytest
import threading as _real_threading
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from instrmcp.servers.jupyter_qcodes import active_cell_bridge


# --------------------------------------------------------------------------- #
# Minimal comm test doubles (mirrors tests/unit/servers/test_comm_handshake.py)
# --------------------------------------------------------------------------- #
class DummyComm:
    """Mock Comm object for testing comm protocol."""

    def __init__(self, target_name: str, comm_id: str = "test-comm-md"):
        self.target_name = target_name
        self.comm_id = comm_id
        self._closed = False
        self._sent_messages: List[Dict[str, Any]] = []
        self._msg_handler = None
        self._close_handler = None

    def send(self, data: Dict[str, Any]):
        if self._closed:
            raise RuntimeError("Comm is closed")
        self._sent_messages.append(data)

    def on_msg(self, handler):
        self._msg_handler = handler

    def on_close(self, handler):
        self._close_handler = handler

    def close(self):
        self._closed = True
        if self._close_handler:
            self._close_handler({})

    def simulate_message(self, msg: Dict[str, Any]):
        if self._msg_handler:
            self._msg_handler(msg)


class FakeCommManager:
    def __init__(self):
        self._targets: Dict[str, Any] = {}
        self._comms: List[DummyComm] = []

    def register_target(self, target_name: str, handler):
        self._targets[target_name] = handler

    def open_comm(self, target_name: str, data: Dict[str, Any] = None) -> DummyComm:
        if target_name not in self._targets:
            raise ValueError(f"No such comm target: {target_name}")
        comm = DummyComm(target_name)
        self._targets[target_name](comm, {"content": {"data": data or {}}})
        self._comms.append(comm)
        return comm


class FakeIPython:
    def __init__(self):
        self.kernel = MagicMock()
        self.kernel.comm_manager = FakeCommManager()


@pytest.fixture
def fake_ipython():
    return FakeIPython()


@pytest.fixture
def cleanup_active_cell_globals():
    yield
    with active_cell_bridge._STATE_LOCK:
        active_cell_bridge._LAST_SNAPSHOT = None
        active_cell_bridge._LAST_TS = 0.0
        active_cell_bridge._KERNEL_COMM_MAP.clear()
        active_cell_bridge._CELL_OUTPUTS_CACHE.clear()
        active_cell_bridge._PENDING_REQUESTS.clear()


# --------------------------------------------------------------------------- #
# Deterministic "slow but successful frontend" primitives
# --------------------------------------------------------------------------- #
class _ThreadingShim:
    """Stand-in for the `threading` module inside active_cell_bridge.

    Overrides only `Event`; everything else delegates to the real threading
    module. Replacing the module-level `threading` NAME (not threading.Event
    globally) keeps the real threading module untouched for the rest of the
    process.
    """

    def __init__(self, event_cls):
        self.Event = event_cls

    def __getattr__(self, name):
        return getattr(_real_threading, name)


class FakeFrontendEvent:
    """Fake threading.Event modelling a frontend that answers SUCCESSFULLY but
    slower than the old 2.0s default.

    `.wait(timeout)`:
      - timeout < deliver_threshold (2.5s)  -> return False  (buggy false timeout)
      - timeout >= deliver_threshold        -> deliver a matching `add_cell_response`
                                               (success=True) through the REAL
                                               _on_msg handler, then return True.
    """

    comm: DummyComm = None
    deliver_threshold: float = 2.5
    response_success: bool = True
    response_message: str = "Markdown cell added"
    last_timeout: float = None

    def __init__(self):
        self._flag = False

    # Only .set() and .wait() are used by _send_and_wait / _on_msg.
    def set(self):
        self._flag = True

    def is_set(self):
        return self._flag

    def clear(self):
        self._flag = False

    def wait(self, timeout=None):
        FakeFrontendEvent.last_timeout = timeout
        if timeout is None or timeout < FakeFrontendEvent.deliver_threshold:
            # Old 2.0s default: the (slow) markdown response has not arrived yet.
            return False

        # Long enough: find our own request_id, then deliver the successful
        # response via the real comm handler (exercises the add_cell_response
        # branch of _on_msg, which calls event.set()).
        request_id = None
        with active_cell_bridge._STATE_LOCK:
            for rid, entry in list(active_cell_bridge._PENDING_REQUESTS.items()):
                if entry[0] is self:
                    request_id = rid
                    break
        if request_id is None or FakeFrontendEvent.comm is None:
            return False

        FakeFrontendEvent.comm.simulate_message(
            {
                "content": {
                    "data": {
                        "type": "add_cell_response",
                        "request_id": request_id,
                        "success": FakeFrontendEvent.response_success,
                        "message": FakeFrontendEvent.response_message,
                    }
                }
            }
        )
        return self._flag


def _arm_fake_frontend(comm, monkeypatch):
    """Point the fake frontend at `comm` and install the Event shim."""
    FakeFrontendEvent.comm = comm
    FakeFrontendEvent.deliver_threshold = 2.5
    FakeFrontendEvent.response_success = True
    FakeFrontendEvent.response_message = "Markdown cell added"
    FakeFrontendEvent.last_timeout = None
    monkeypatch.setattr(
        active_cell_bridge, "threading", _ThreadingShim(FakeFrontendEvent)
    )


class LateRaceEvent:
    """Fake threading.Event modelling the timeout/response RACE.

    The frontend response lands in _PENDING_REQUESTS (via the real _on_msg
    handler) in the narrow window right as `wait()` gives up, so `wait()` returns
    False (reports a timeout) even though a valid success response is now present.

    Before the fix, `_send_and_wait`'s timeout branch popped and discarded that
    response, returning a false timeout. After the fix, it always pops-and-checks
    for a response before declaring a timeout, so the late-but-valid response is
    honored.
    """

    comm: DummyComm = None

    def __init__(self):
        self._flag = False

    def set(self):
        self._flag = True

    def is_set(self):
        return self._flag

    def clear(self):
        self._flag = False

    def wait(self, timeout=None):
        # Deliver the response through the REAL _on_msg (stores [event, data] and
        # calls event.set()), then report a timeout anyway to model the race.
        request_id = None
        with active_cell_bridge._STATE_LOCK:
            for rid, entry in list(active_cell_bridge._PENDING_REQUESTS.items()):
                if entry[0] is self:
                    request_id = rid
                    break
        if request_id is not None and LateRaceEvent.comm is not None:
            LateRaceEvent.comm.simulate_message(
                {
                    "content": {
                        "data": {
                            "type": "add_cell_response",
                            "request_id": request_id,
                            "success": True,
                            "message": "Markdown cell added (late)",
                        }
                    }
                }
            )
        # Report timeout despite the response having just arrived.
        return False


# --------------------------------------------------------------------------- #
# PRIMARY TEST: bridge-level add_new_cell(cell_type="markdown")
# --------------------------------------------------------------------------- #
def test_markdown_add_cell_slow_success_is_not_false_timeout(
    fake_ipython, cleanup_active_cell_globals, monkeypatch
):
    """A slow-but-successful markdown add must report success=True, not a
    false 2.0s timeout.

    FAILS on current code (add_new_cell default timeout_s=2.0 -> wait returns
    False -> false timeout). PASSES once the default is raised to ~10s.
    """
    with patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
        return_value=fake_ipython,
    ), patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
        return_value="test-kernel-md",
    ):
        active_cell_bridge.register_comm_target()
        comm = fake_ipython.kernel.comm_manager.open_comm(
            "mcp:active_cell", data={"kernel_id": "test-kernel-md"}
        )
        _arm_fake_frontend(comm, monkeypatch)

        # Call with the FUNCTION DEFAULT timeout (do NOT pass timeout_s):
        # this is exactly the code path the bug reproducer hits.
        result = active_cell_bridge.add_new_cell(
            cell_type="markdown", position="below", content="# Title"
        )

    assert result["success"] is True, (
        "markdown add_cell reported failure despite a successful (slow) frontend "
        f"response -> false timeout bug: {result!r}"
    )
    assert result.get("message") == "Markdown cell added"
    assert result.get("cell_type") == "markdown"

    # The effective default timeout must be long enough to honor the markdown
    # round-trip (the fix), not the old 2.0s.
    assert FakeFrontendEvent.last_timeout is not None
    assert FakeFrontendEvent.last_timeout >= 2.5, (
        f"add_new_cell default timeout is too short "
        f"({FakeFrontendEvent.last_timeout}s); markdown adds will false-timeout"
    )


# --------------------------------------------------------------------------- #
# COMPANION TEST (recommended): backend layer that hardcodes timeout_s=2.0
# Guards against a partial fix that raises only the bridge default while
# leaving backend/notebook_unsafe.py pinned at 2.0.
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_backend_markdown_add_cell_is_not_false_timeout(
    fake_ipython, cleanup_active_cell_globals, monkeypatch
):
    """NotebookUnsafeBackend.add_new_cell (the layer closest to the MCP tool
    `notebook_add_cell`) must not report a false timeout for a slow markdown add.

    FAILS on current code because backend/notebook_unsafe.py hardcodes
    timeout_s=2.0 when calling bridge.add_new_cell. PASSES once that hardcode is
    removed / threaded through the new ~10s default.
    """
    from instrmcp.servers.jupyter_qcodes.backend.notebook_unsafe import (
        NotebookUnsafeBackend,
    )

    with patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
        return_value=fake_ipython,
    ), patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
        return_value="test-kernel-md-backend",
    ):
        active_cell_bridge.register_comm_target()
        comm = fake_ipython.kernel.comm_manager.open_comm(
            "mcp:active_cell", data={"kernel_id": "test-kernel-md-backend"}
        )
        _arm_fake_frontend(comm, monkeypatch)

        # state / notebook_backend are unused by add_new_cell -> mocks are fine.
        backend = NotebookUnsafeBackend(MagicMock(), MagicMock())
        result = await backend.add_new_cell(
            cell_type="markdown", position="below", content="# Title"
        )

    assert result["success"] is True, (
        "backend.add_new_cell reported a false timeout for a successful (slow) "
        f"markdown add -> hardcoded 2.0s at notebook_unsafe.py: {result!r}"
    )
    assert FakeFrontendEvent.last_timeout is not None
    assert FakeFrontendEvent.last_timeout >= 2.5, (
        "backend hardcodes a too-short timeout "
        f"({FakeFrontendEvent.last_timeout}s) instead of the fixed default"
    )


# --------------------------------------------------------------------------- #
# RACE TEST: a valid response that lands right as wait() times out must be
# honored, not discarded as a false timeout (the bridge-stability fix).
# --------------------------------------------------------------------------- #
def test_add_cell_late_response_race_is_honored_not_false_timeout(
    fake_ipython, cleanup_active_cell_globals, monkeypatch
):
    """If a success response arrives in the window right as wait() times out,
    `_send_and_wait` must return that success rather than a false timeout.

    FAILS on the pre-fix code (the timeout branch popped and discarded the
    already-stored response). PASSES after the fix (always pop-and-check the
    response under the lock before declaring a timeout).
    """
    with patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
        return_value=fake_ipython,
    ), patch(
        "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
        return_value="test-kernel-race",
    ):
        active_cell_bridge.register_comm_target()
        comm = fake_ipython.kernel.comm_manager.open_comm(
            "mcp:active_cell", data={"kernel_id": "test-kernel-race"}
        )
        LateRaceEvent.comm = comm
        monkeypatch.setattr(
            active_cell_bridge, "threading", _ThreadingShim(LateRaceEvent)
        )

        result = active_cell_bridge.add_new_cell(
            cell_type="markdown", position="below", content="# Title"
        )

    assert result["success"] is True, (
        "a valid frontend response that landed as wait() timed out was discarded "
        f"as a false timeout: {result!r}"
    )
    assert result.get("message") == "Markdown cell added (late)"

    # The pending request must be cleaned up (no leak) regardless of the race.
    with active_cell_bridge._STATE_LOCK:
        assert len(active_cell_bridge._PENDING_REQUESTS) == 0
