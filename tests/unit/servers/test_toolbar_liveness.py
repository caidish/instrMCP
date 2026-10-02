"""Toolbar connection attestation liveness (instrMCP issue #48 A3).

The frontend attestation variable must describe *live* pages. A browser page
reload or a closed/killed tab used to leave `connected: True` and a growing
`connectionCount`, because the kernel-side comm object survives and sending to
a page that is gone does not fail. The frontend now sends a `toolbar_closing`
message on pagehide and a `heartbeat` every few seconds; the kernel drops a
comm that has been silent for longer than the liveness timeout.
"""

from typing import Any, Dict, List, Optional

import pytest

from instrmcp.servers.jupyter_qcodes import jupyter_mcp_extension as extension


class DummyToolbarComm:
    """Minimal kernel-side comm double for the toolbar control channel."""

    def __init__(self, comm_id: str = "toolbar-1"):
        self.comm_id = comm_id
        self._closed = False
        # Real kernel-side comms expose the kernel they belong to; _safe_comm_send
        # treats a missing kernel as a dead channel.
        self.kernel = object()
        self.sent: List[Dict[str, Any]] = []
        self._msg_handler = None
        self._close_handler = None

    # Kernel-side comm API used by the extension
    def on_msg(self, handler):
        self._msg_handler = handler

    def on_close(self, handler):
        self._close_handler = handler

    def send(self, data: Dict[str, Any]):
        if self._closed:
            raise RuntimeError("Comm is closed")
        self.sent.append(data)

    def close(self):
        self._closed = True
        if self._close_handler:
            self._close_handler({})

    # Test helpers
    def deliver(self, data: Dict[str, Any]):
        self._msg_handler({"content": {"data": data}})

    def open(self, data: Optional[Dict[str, Any]] = None):
        extension._handle_toolbar_control(self, {"content": {"data": data or {}}})


@pytest.fixture
def toolbar_state(monkeypatch):
    """Isolate toolbar module state and capture attestation publishes."""
    publishes: List[Dict[str, Any]] = []
    previous_user_ns = extension._toolbar_user_ns
    extension._toolbar_user_ns = {}
    extension._toolbar_comms.clear()
    extension._toolbar_connected_at = None

    def fake_publish() -> bool:
        publishes.append(
            {
                "connected": bool(extension._toolbar_comms),
                "count": len(extension._toolbar_comms),
                "connectedAt": extension._toolbar_connected_at,
            }
        )
        # Mirror the real function's namespace write so tests can read it back.
        extension._toolbar_user_ns[extension.FRONTEND_ATTESTATION_VARIABLE] = publishes[
            -1
        ]
        return True

    monkeypatch.setattr(extension, "_publish_frontend_attestation_locked", fake_publish)
    # Never start the background sweeper in tests; expiry is exercised directly.
    monkeypatch.setattr(extension, "_ensure_toolbar_sweeper", lambda: None)
    try:
        yield publishes, extension._toolbar_user_ns
    finally:
        extension._toolbar_comms.clear()
        extension._toolbar_connected_at = None
        extension._toolbar_user_ns = previous_user_ns


def test_opening_a_comm_publishes_connected_state(toolbar_state):
    publishes, _ = toolbar_state
    comm = DummyToolbarComm()
    comm.open()

    assert comm in extension._toolbar_comms
    assert publishes[-1]["connected"] is True
    assert publishes[-1]["count"] == 1
    assert publishes[-1]["connectedAt"] is not None
    assert getattr(comm, "_mcp_last_seen", None) is not None


def test_closing_message_drops_the_comm_immediately(toolbar_state):
    publishes, user_ns = toolbar_state
    comm = DummyToolbarComm()
    comm.open()

    comm.deliver({"type": "toolbar_closing"})

    assert comm not in extension._toolbar_comms
    assert comm._closed is True
    assert publishes[-1]["connected"] is False
    assert publishes[-1]["count"] == 0
    assert user_ns[extension.FRONTEND_ATTESTATION_VARIABLE]["connected"] is False


def test_heartbeat_refreshes_liveness(toolbar_state):
    comm = DummyToolbarComm()
    comm.open()

    comm._mcp_last_seen = 1000.0  # far in the past
    comm.deliver({"type": "heartbeat"})

    assert comm._mcp_last_seen > 1000.0
    assert not comm.sent  # heartbeat needs no reply


def test_any_message_refreshes_liveness(toolbar_state):
    comm = DummyToolbarComm()
    comm.open()

    comm._mcp_last_seen = 1000.0
    comm.deliver({"type": "get_status"})

    assert comm._mcp_last_seen > 1000.0
    # get_status still gets its reply
    assert comm.sent and comm.sent[-1]["type"] == "status"


def test_expiry_drops_only_silent_comms(toolbar_state):
    publishes, _ = toolbar_state
    stale = DummyToolbarComm("stale")
    fresh = DummyToolbarComm("fresh")
    stale.open()
    fresh.open()

    now = 10_000.0
    stale._mcp_last_seen = now - extension.TOOLBAR_LIVENESS_TIMEOUT_S - 1.0
    fresh._mcp_last_seen = now - 1.0

    dropped = extension._expire_stale_toolbar_comms(now=now)

    assert dropped is True
    assert stale not in extension._toolbar_comms
    assert stale._closed is True
    assert fresh in extension._toolbar_comms
    assert publishes[-1]["connected"] is True
    assert publishes[-1]["count"] == 1


def test_expiry_finds_nothing_when_all_comms_are_fresh(toolbar_state):
    publishes, _ = toolbar_state
    comm = DummyToolbarComm()
    comm.open()

    now = 10_000.0
    comm._mcp_last_seen = now - 1.0

    assert extension._expire_stale_toolbar_comms(now=now) is False
    assert comm in extension._toolbar_comms
    # No publish for a no-op sweep.
    assert publishes[-1]["count"] == 1
