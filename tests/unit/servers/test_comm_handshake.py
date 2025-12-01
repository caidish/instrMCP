"""
Unit tests for comm handshake and Python 3.13 compatibility.

Tests the frontend/backend comm protocol, including:
- broadcast_server_status Python 3.13 asyncio fix
- Active cell bridge comm registration and message handling
- Comm lifecycle (open, message, close)
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch, call
from typing import Dict, Any, List


class DummyComm:
    """Mock Comm object for testing comm protocol."""

    def __init__(self, target_name: str, comm_id: str = "test-comm-123"):
        self.target_name = target_name
        self.comm_id = comm_id
        self._closed = False
        self._sent_messages: List[Dict[str, Any]] = []
        self._msg_handler = None
        self._close_handler = None

    def send(self, data: Dict[str, Any]):
        """Record sent messages."""
        if self._closed:
            raise RuntimeError("Comm is closed")
        self._sent_messages.append(data)

    def on_msg(self, handler):
        """Register message handler."""
        self._msg_handler = handler

    def on_close(self, handler):
        """Register close handler."""
        self._close_handler = handler

    def close(self):
        """Close the comm."""
        self._closed = True
        if self._close_handler:
            self._close_handler({})

    def simulate_message(self, msg: Dict[str, Any]):
        """Simulate receiving a message from frontend."""
        if self._msg_handler:
            self._msg_handler(msg)


class FakeCommManager:
    """Mock IPython kernel comm_manager."""

    def __init__(self):
        self._targets: Dict[str, Any] = {}
        self._comms: List[DummyComm] = []

    def register_target(self, target_name: str, handler):
        """Register a comm target."""
        self._targets[target_name] = handler

    def open_comm(self, target_name: str, data: Dict[str, Any] = None) -> DummyComm:
        """Simulate frontend opening a comm."""
        if target_name not in self._targets:
            raise ValueError(f"No such comm target: {target_name}")

        comm = DummyComm(target_name)
        open_msg = {"content": {"data": data or {}}}

        # Call the registered handler
        handler = self._targets[target_name]
        handler(comm, open_msg)

        self._comms.append(comm)
        return comm


class FakeIPython:
    """Mock IPython instance with kernel."""

    def __init__(self):
        self.kernel = MagicMock()
        self.kernel.comm_manager = FakeCommManager()


@pytest.fixture
def fake_ipython():
    """Create a fake IPython instance."""
    return FakeIPython()


@pytest.fixture
def cleanup_active_cell_globals():
    """Reset active_cell_bridge globals after each test."""
    yield
    # Clean up globals
    from instrmcp.servers.jupyter_qcodes import active_cell_bridge

    with active_cell_bridge._STATE_LOCK:
        active_cell_bridge._LAST_SNAPSHOT = None
        active_cell_bridge._LAST_TS = 0.0
        active_cell_bridge._ACTIVE_COMMS.clear()
        active_cell_bridge._CELL_OUTPUTS_CACHE.clear()


@pytest.fixture
def cleanup_status_comm():
    """Reset broadcast status comm after each test."""
    yield
    # Clean up global status comm
    from instrmcp.servers.jupyter_qcodes import jupyter_mcp_extension

    jupyter_mcp_extension._status_comm = None


class TestBroadcastServerStatusPython313:
    """Test broadcast_server_status with existing toolbar comms."""

    def test_broadcast_with_existing_toolbar_comm(
        self, fake_ipython, cleanup_status_comm, caplog
    ):
        """Test broadcast_server_status sends through existing toolbar comms."""
        from instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension import (
            broadcast_server_status,
            _toolbar_comms,
        )

        # Create a mock comm to receive broadcasts
        sent_messages = []

        class MockToolbarComm:
            def __init__(self):
                self._closed = False
                self.is_disposed = False
                self.kernel = MagicMock()
                self.kernel.is_alive.return_value = True

            def send(self, data):
                sent_messages.append(data)

        mock_comm = MockToolbarComm()

        # Add the mock comm to the tracked set
        _toolbar_comms.add(mock_comm)
        try:
            # Call broadcast_server_status
            broadcast_server_status("server_ready", {"port": 3000})

            # Verify message was sent through the tracked comm
            assert len(sent_messages) == 1
            msg = sent_messages[0]
            assert msg["type"] == "status_broadcast"
            assert msg["status"] == "server_ready"
            assert "details" in msg
            assert msg["details"].get("port") == 3000
            assert "timestamp" in msg
            assert isinstance(msg["timestamp"], float)
        finally:
            _toolbar_comms.discard(mock_comm)

    def test_broadcast_with_no_toolbar_comms(
        self, fake_ipython, cleanup_status_comm, caplog
    ):
        """Test broadcast_server_status when no toolbar comms are connected."""
        from instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension import (
            broadcast_server_status,
            _toolbar_comms,
        )

        # Ensure no comms are tracked
        original_comms = _toolbar_comms.copy()
        _toolbar_comms.clear()

        try:
            # Call broadcast_server_status - should not raise
            broadcast_server_status("server_stopped")
            # Just verify it doesn't crash when no comms are available
        finally:
            _toolbar_comms.update(original_comms)

    def test_broadcast_without_ipython(self, cleanup_status_comm):
        """Test broadcast_server_status gracefully handles missing IPython."""
        from instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension import (
            broadcast_server_status,
        )

        with patch(
            "IPython.core.getipython.get_ipython",
            return_value=None,
        ):
            # Should not raise, just return early
            broadcast_server_status("server_ready")

    def test_broadcast_without_kernel(self, cleanup_status_comm):
        """Test broadcast_server_status handles IPython without kernel."""
        from instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension import (
            broadcast_server_status,
        )

        fake_ip = MagicMock()
        # Remove kernel attribute
        delattr(fake_ip, "kernel") if hasattr(fake_ip, "kernel") else None
        fake_ip.kernel = None

        with patch(
            "IPython.core.getipython.get_ipython",
            return_value=fake_ip,
        ):
            # Should not raise, just return early
            broadcast_server_status("server_ready")


class TestActiveCellBridge:
    """Test active cell bridge comm protocol."""

    def test_register_comm_target(self, fake_ipython, cleanup_active_cell_globals):
        """Test registering the comm target."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Verify target was registered
            assert "mcp:active_cell" in fake_ipython.kernel.comm_manager._targets

    def test_comm_open_adds_to_active_comms(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test opening a comm adds it to _ACTIVE_COMMS."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _ACTIVE_COMMS,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Simulate frontend opening a comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Verify comm was added to active comms
            assert comm in _ACTIVE_COMMS
            assert len(_ACTIVE_COMMS) == 1

    def test_comm_close_removes_from_active_comms(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test closing a comm removes it from _ACTIVE_COMMS."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _ACTIVE_COMMS,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open and then close a comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")
            assert comm in _ACTIVE_COMMS

            comm.close()

            # Verify comm was removed
            assert comm not in _ACTIVE_COMMS

    def test_snapshot_message_updates_last_snapshot(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test receiving a snapshot message updates _LAST_SNAPSHOT."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _LAST_SNAPSHOT,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open a comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Simulate frontend sending a snapshot
            snapshot_msg = {
                "content": {
                    "data": {
                        "type": "snapshot",
                        "path": "/path/to/notebook.ipynb",
                        "id": "cell-123",
                        "index": 5,
                        "cell_type": "code",
                        "text": "print('hello world')",
                        "cursor": {"line": 0, "column": 5},
                        "selection": None,
                        "client_id": "client-xyz",
                        "ts_ms": 1234567890000,
                    }
                }
            }

            comm.simulate_message(snapshot_msg)

            # Verify snapshot was stored
            import instrmcp.servers.jupyter_qcodes.active_cell_bridge as bridge

            with bridge._STATE_LOCK:
                assert bridge._LAST_SNAPSHOT is not None
                assert (
                    bridge._LAST_SNAPSHOT["notebook_path"] == "/path/to/notebook.ipynb"
                )
                assert bridge._LAST_SNAPSHOT["cell_id"] == "cell-123"
                assert bridge._LAST_SNAPSHOT["cell_index"] == 5
                assert bridge._LAST_SNAPSHOT["text"] == "print('hello world')"

    def test_request_frontend_snapshot_sends_to_all_comms(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test request_frontend_snapshot sends request to all active comms."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            request_frontend_snapshot,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open multiple comms
            comm1 = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")
            comm2 = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Request snapshot
            request_frontend_snapshot()

            # Verify both comms received the request
            assert len(comm1._sent_messages) == 1
            assert comm1._sent_messages[0] == {"type": "request_current"}

            assert len(comm2._sent_messages) == 1
            assert comm2._sent_messages[0] == {"type": "request_current"}

    def test_cell_outputs_cache_updates(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test receiving cell outputs updates the cache."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _CELL_OUTPUTS_CACHE,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open a comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Simulate frontend sending cell outputs
            outputs_msg = {
                "content": {
                    "data": {
                        "type": "get_cell_outputs_response",
                        "outputs": {
                            "1": {
                                "output_type": "execute_result",
                                "data": {"text/plain": "42"},
                            },
                            "2": {
                                "output_type": "stream",
                                "name": "stdout",
                                "text": "Hello\n",
                            },
                        },
                    }
                }
            }

            comm.simulate_message(outputs_msg)

            # Verify cache was updated
            import instrmcp.servers.jupyter_qcodes.active_cell_bridge as bridge

            with bridge._STATE_LOCK:
                assert 1 in bridge._CELL_OUTPUTS_CACHE
                assert 2 in bridge._CELL_OUTPUTS_CACHE
                assert bridge._CELL_OUTPUTS_CACHE[1]["output_type"] == "execute_result"
                assert bridge._CELL_OUTPUTS_CACHE[2]["output_type"] == "stream"

    def test_multiple_comms_lifecycle(self, fake_ipython, cleanup_active_cell_globals):
        """Test managing multiple comms through their lifecycle."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _ACTIVE_COMMS,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open 3 comms
            comm1 = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")
            comm2 = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")
            comm3 = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            assert len(_ACTIVE_COMMS) == 3

            # Close middle comm
            comm2.close()
            assert len(_ACTIVE_COMMS) == 2
            assert comm1 in _ACTIVE_COMMS
            assert comm2 not in _ACTIVE_COMMS
            assert comm3 in _ACTIVE_COMMS

            # Close remaining comms
            comm1.close()
            comm3.close()
            assert len(_ACTIVE_COMMS) == 0

    def test_pong_message_handling(self, fake_ipython, cleanup_active_cell_globals):
        """Test handling pong message from frontend."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Send pong message (should just log)
            pong_msg = {"content": {"data": {"type": "pong"}}}

            # Should not raise
            comm.simulate_message(pong_msg)

    def test_unknown_message_type(
        self, fake_ipython, cleanup_active_cell_globals, caplog
    ):
        """Test handling unknown message type logs a warning."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )
        import logging

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Send unknown message type
            unknown_msg = {
                "content": {"data": {"type": "mystery_message", "foo": "bar"}}
            }

            with caplog.at_level(logging.WARNING):
                comm.simulate_message(unknown_msg)

                # Check warning was logged
                assert any(
                    "UNKNOWN MESSAGE TYPE" in record.message
                    for record in caplog.records
                )


class TestCommHandshakeIntegration:
    """Integration tests for complete comm handshake workflow."""

    def test_full_handshake_workflow(
        self, fake_ipython, cleanup_active_cell_globals, cleanup_status_comm
    ):
        """Test complete workflow: register → open → snapshot → request → close."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            request_frontend_snapshot,
            _LAST_SNAPSHOT,
            _ACTIVE_COMMS,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            # Step 1: Register comm target
            register_comm_target()

            # Step 2: Frontend opens comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")
            assert len(_ACTIVE_COMMS) == 1

            # Step 3: Backend requests snapshot
            request_frontend_snapshot()
            assert len(comm._sent_messages) == 1
            assert comm._sent_messages[0]["type"] == "request_current"

            # Step 4: Frontend sends snapshot
            snapshot_msg = {
                "content": {
                    "data": {
                        "type": "snapshot",
                        "path": "/test.ipynb",
                        "id": "cell-1",
                        "index": 0,
                        "text": "x = 42",
                        "cell_type": "code",
                        "ts_ms": int(time.time() * 1000),
                    }
                }
            }
            comm.simulate_message(snapshot_msg)

            # Verify snapshot was captured
            import instrmcp.servers.jupyter_qcodes.active_cell_bridge as bridge

            with bridge._STATE_LOCK:
                assert bridge._LAST_SNAPSHOT is not None
                assert bridge._LAST_SNAPSHOT["text"] == "x = 42"

            # Step 5: Close comm
            comm.close()
            assert len(_ACTIVE_COMMS) == 0

    def test_no_comm_detected_scenario(self, fake_ipython, cleanup_active_cell_globals):
        """Test scenario that caused 'no comm detected' error in GitHub Issue #9."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            get_active_cell,
            _ACTIVE_COMMS,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            # Register target
            register_comm_target()

            # Try to get active cell when no comm is connected
            result = get_active_cell()
            assert result is None  # Should handle gracefully

            # Now connect a comm
            comm = fake_ipython.kernel.comm_manager.open_comm("mcp:active_cell")

            # Send snapshot
            snapshot_msg = {
                "content": {
                    "data": {
                        "type": "snapshot",
                        "path": "/test.ipynb",
                        "id": "cell-1",
                        "index": 0,
                        "text": "print('test')",
                        "cell_type": "code",
                        "ts_ms": int(time.time() * 1000),
                    }
                }
            }
            comm.simulate_message(snapshot_msg)

            # Now get_active_cell should work
            result = get_active_cell()
            assert result is not None
            assert result["text"] == "print('test')"
