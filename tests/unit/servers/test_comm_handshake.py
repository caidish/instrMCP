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
        active_cell_bridge._KERNEL_COMM_MAP.clear()
        active_cell_bridge._CELL_OUTPUTS_CACHE.clear()
        active_cell_bridge._PENDING_REQUESTS.clear()


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

    def test_comm_open_adds_to_kernel_comm_map(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test opening a comm registers it in _KERNEL_COMM_MAP."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _KERNEL_COMM_MAP,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-123",
        ):
            register_comm_target()

            # Simulate frontend opening a comm with kernel_id in data
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-123"}
            )

            # Verify comm was added to kernel comm map
            assert "test-kernel-123" in _KERNEL_COMM_MAP
            assert _KERNEL_COMM_MAP["test-kernel-123"] == comm

    def test_comm_close_removes_from_kernel_comm_map(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test closing a comm removes it from _KERNEL_COMM_MAP."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _KERNEL_COMM_MAP,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-456",
        ):
            register_comm_target()

            # Open and then close a comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-456"}
            )
            assert "test-kernel-456" in _KERNEL_COMM_MAP

            comm.close()

            # Verify comm was removed
            assert "test-kernel-456" not in _KERNEL_COMM_MAP

    def test_snapshot_message_updates_last_snapshot(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test receiving a snapshot message updates _LAST_SNAPSHOT."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-snapshot",
        ):
            register_comm_target()

            # Open a comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-snapshot"}
            )

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

    def test_request_frontend_snapshot_sends_to_current_kernel_comm(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test request_frontend_snapshot sends request to current kernel's comm only."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            request_frontend_snapshot,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-request",
        ):
            register_comm_target()

            # Open a comm for this kernel
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-request"}
            )

            # Request snapshot
            request_frontend_snapshot()

            # Verify comm received the request
            assert len(comm._sent_messages) == 1
            assert comm._sent_messages[0] == {"type": "request_current"}

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
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-outputs",
        ):
            register_comm_target()

            # Open a comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-outputs"}
            )

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
                # Cache structure: {"data": output_data, "timestamp": ..., "kernel_id": ...}
                assert bridge._CELL_OUTPUTS_CACHE[1]["data"]["output_type"] == "execute_result"
                assert bridge._CELL_OUTPUTS_CACHE[2]["data"]["output_type"] == "stream"

    def test_multiple_kernels_lifecycle(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test managing comms from multiple kernels through their lifecycle."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            _KERNEL_COMM_MAP,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ):
            register_comm_target()

            # Open comms for 3 different kernels
            comm1 = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "kernel-1"}
            )
            comm2 = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "kernel-2"}
            )
            comm3 = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "kernel-3"}
            )

            assert len(_KERNEL_COMM_MAP) == 3

            # Close middle kernel's comm
            comm2.close()
            assert len(_KERNEL_COMM_MAP) == 2
            assert "kernel-1" in _KERNEL_COMM_MAP
            assert "kernel-2" not in _KERNEL_COMM_MAP
            assert "kernel-3" in _KERNEL_COMM_MAP

            # Close remaining comms
            comm1.close()
            comm3.close()
            assert len(_KERNEL_COMM_MAP) == 0

    def test_pong_message_handling(self, fake_ipython, cleanup_active_cell_globals):
        """Test handling pong message from frontend."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-pong",
        ):
            register_comm_target()

            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-pong"}
            )

            # Send pong message (should just log)
            pong_msg = {"content": {"data": {"type": "pong"}}}

            # Should not raise
            comm.simulate_message(pong_msg)

    def test_unknown_message_type(
        self,
        fake_ipython,
        cleanup_active_cell_globals,
        caplog,
        enable_instrmcp_log_capture,
    ):
        """Test handling unknown message type logs a warning."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
        )
        import logging

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-unknown",
        ):
            register_comm_target()

            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-unknown"}
            )

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
            _KERNEL_COMM_MAP,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-workflow",
        ):
            # Step 1: Register comm target
            register_comm_target()

            # Step 2: Frontend opens comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-workflow"}
            )
            assert "test-kernel-workflow" in _KERNEL_COMM_MAP

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
            assert "test-kernel-workflow" not in _KERNEL_COMM_MAP

    def test_no_comm_detected_scenario(self, fake_ipython, cleanup_active_cell_globals):
        """Test scenario that caused 'no comm detected' error in GitHub Issue #9."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            get_active_cell,
            _KERNEL_COMM_MAP,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-no-comm",
        ):
            # Register target
            register_comm_target()

            # Try to get active cell when no comm is connected
            result = get_active_cell()
            assert result is None  # Should handle gracefully

            # Now connect a comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-no-comm"}
            )

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

    def test_fresh_snapshot_metadata(self, fake_ipython, cleanup_active_cell_globals):
        """Test that fresh snapshot returns stale=False, source='live' with valid age_ms."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            get_active_cell,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-fresh",
        ):
            register_comm_target()

            # Open comm and send snapshot
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-fresh"}
            )
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

            # Get active cell (should be fresh)
            result = get_active_cell()

            # Verify fresh snapshot metadata
            assert result is not None
            assert result["stale"] is False
            assert result["source"] == "live"
            assert "age_ms" in result
            assert isinstance(result["age_ms"], float)
            assert result["age_ms"] >= 0
            assert result["age_ms"] < 1000  # Should be very fresh
            assert "stale_reason" not in result  # No stale reason for fresh data

    def test_no_active_comms_fallback_metadata(
        self, fake_ipython, cleanup_active_cell_globals
    ):
        """Test that no active comms fallback returns stale=True, source='cache', stale_reason='no_active_comms'."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            get_active_cell,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-fallback",
        ):
            register_comm_target()

            # Open comm, send snapshot, then close comm
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-fallback"}
            )
            snapshot_msg = {
                "content": {
                    "data": {
                        "type": "snapshot",
                        "path": "/test.ipynb",
                        "id": "cell-1",
                        "index": 0,
                        "text": "y = 100",
                        "cell_type": "code",
                        "ts_ms": int(time.time() * 1000),
                    }
                }
            }
            comm.simulate_message(snapshot_msg)

            # Close the comm so no active comms remain
            comm.close()

            # Wait a bit to ensure staleness
            time.sleep(0.1)

            # Request fresh data with fresh_ms requirement
            result = get_active_cell(fresh_ms=50)

            # Verify stale metadata due to no active comms
            assert result is not None
            assert result["stale"] is True
            assert result["source"] == "cache"
            assert "age_ms" in result
            assert isinstance(result["age_ms"], float)
            assert result["age_ms"] > 50  # Should be older than fresh_ms threshold
            assert result["stale_reason"] == "no_active_comms"

    def test_timeout_fallback_metadata(self, fake_ipython, cleanup_active_cell_globals):
        """Test that timeout fallback returns stale=True, source='cache', stale_reason='timeout'."""
        from instrmcp.servers.jupyter_qcodes.active_cell_bridge import (
            register_comm_target,
            get_active_cell,
        )

        with patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge.get_ipython",
            return_value=fake_ipython,
        ), patch(
            "instrmcp.servers.jupyter_qcodes.active_cell_bridge._get_kernel_id",
            return_value="test-kernel-timeout",
        ):
            register_comm_target()

            # Open comm and send initial snapshot
            comm = fake_ipython.kernel.comm_manager.open_comm(
                "mcp:active_cell", data={"kernel_id": "test-kernel-timeout"}
            )
            snapshot_msg = {
                "content": {
                    "data": {
                        "type": "snapshot",
                        "path": "/test.ipynb",
                        "id": "cell-1",
                        "index": 0,
                        "text": "z = 200",
                        "cell_type": "code",
                        "ts_ms": int(time.time() * 1000),
                    }
                }
            }
            comm.simulate_message(snapshot_msg)

            # Wait to make snapshot stale
            time.sleep(0.2)

            # Request fresh data with a very short timeout (frontend won't respond in time)
            # The comm is active but won't send a new snapshot, causing timeout
            result = get_active_cell(fresh_ms=50, timeout_s=0.1)

            # Verify stale metadata due to timeout
            assert result is not None
            assert result["stale"] is True
            assert result["source"] == "cache"
            assert "age_ms" in result
            assert isinstance(result["age_ms"], float)
            assert result["age_ms"] > 50  # Should be older than fresh_ms threshold
            assert result["stale_reason"] == "timeout"
