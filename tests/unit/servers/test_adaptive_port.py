"""Tests for an OS-assigned Jupyter MCP listener port."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from instrmcp.servers.jupyter_qcodes import jupyter_mcp_extension as extension
from instrmcp.servers.jupyter_qcodes.mcp_server import JupyterMCPServer


class FakeServer:
    def __init__(self, ipython, host="127.0.0.1", port=8123, **kwargs):
        self.host = host
        self.port = port
        self.running = False
        self.start_error = None

    def start_sync(self):
        if self.start_error is not None:
            raise self.start_error
        if self.port == 0:
            self.port = 43123
        self.running = True

    def is_running(self):
        return self.running

    def stop_sync(self):
        self.running = False
        return True


def test_start_server_passes_requested_loopback_endpoint():
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=FakeServer
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            extension._do_start_server(
                announce=False,
                host="127.0.0.1",
                port=0,
            )

        factory.assert_called_once_with(
            factory.call_args.args[0],
            host="127.0.0.1",
            port=0,
            safe_mode=extension._desired_mode,
            dangerous_mode=extension._dangerous_mode,
            enabled_options=extension._enabled_options,
        )
    finally:
        extension._server, extension._server_host, extension._server_port = previous


def test_server_records_the_port_chosen_by_the_operating_system():
    listener = SimpleNamespace(sockets=[MagicMock()])
    listener.sockets[0].getsockname.return_value = ("127.0.0.1", 43123)
    uvicorn_server = SimpleNamespace(servers=[listener])
    server = object.__new__(JupyterMCPServer)
    server.host = "127.0.0.1"
    server.port = 0
    server._uvicorn_server = uvicorn_server

    server._record_bound_port()

    assert server.port == 43123


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
@pytest.mark.parametrize("running", [True, False])
def test_restart_preserves_bound_endpoint(host, running):
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    extension._server_host, extension._server_port = "127.0.0.1", 8123
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=FakeServer
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            extension._do_start_server(announce=False, host=host, port=0)
            if not running:
                extension._server.stop_sync()
                # The existing server's endpoint takes precedence over stored values.
                extension._server_host, extension._server_port = "127.0.0.1", 8123

            assert extension._do_restart_server(announce=False) is True

            assert factory.call_count == 2
            assert factory.call_args.kwargs["host"] == host
            assert factory.call_args.kwargs["port"] == 43123
            assert extension._server.is_running()
            assert extension._server.host == host
            assert extension._server.port == 43123
            assert extension._get_current_config()["port"] == 43123
            assert (extension._server_host, extension._server_port) == (host, 43123)
    finally:
        extension._server, extension._server_host, extension._server_port = previous


def test_stop_then_start_reuses_explicit_port():
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    extension._server_host, extension._server_port = "127.0.0.1", 8123
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=FakeServer
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            extension._do_start_server(announce=False, port=9123)
            assert extension._do_stop_server(announce=False) is True
            assert extension._get_current_config()["port"] == 9123

            extension._do_start_server(announce=False)

            assert factory.call_count == 2
            assert factory.call_args.kwargs["port"] == 9123
            assert extension._server.port == 9123
    finally:
        extension._server, extension._server_host, extension._server_port = previous


def test_start_running_server_is_noop_unless_endpoint_differs():
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    extension._server_host, extension._server_port = "127.0.0.1", 8123
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=FakeServer
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            extension._do_start_server(announce=False, port=0)
            original = extension._server

            extension._do_start_server(announce=False)
            extension._do_start_server(announce=False, port=0)
            extension._do_start_server(announce=False, port=43123)
            with pytest.raises(RuntimeError, match="different endpoint"):
                extension._do_start_server(announce=False, port=9999)
            with pytest.raises(RuntimeError, match="different endpoint"):
                extension._do_start_server(announce=False, host="0.0.0.0", port=0)

            assert factory.call_count == 1
            assert extension._server is original
    finally:
        extension._server, extension._server_host, extension._server_port = previous


def test_restart_without_server_uses_stored_defaults():
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    extension._server_host, extension._server_port = "127.0.0.1", 8123
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=FakeServer
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            assert extension._do_restart_server(announce=False) is True

            assert factory.call_count == 1
            assert factory.call_args.kwargs["host"] == "127.0.0.1"
            assert factory.call_args.kwargs["port"] == 8123
            assert extension._get_current_config()["port"] == 8123
    finally:
        extension._server, extension._server_host, extension._server_port = previous


@pytest.mark.parametrize("restart", [False, True])
def test_failed_start_does_not_update_stored_endpoint(restart):
    previous = extension._server, extension._server_host, extension._server_port
    extension._server = None
    extension._server_host, extension._server_port = "127.0.0.1", 8123
    start_error = OSError("port already in use")

    def failing_factory(*args, **kwargs):
        server = FakeServer(*args, **kwargs)
        server.start_error = start_error
        return server

    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(
            extension, "JupyterMCPServer", side_effect=failing_factory
        ) as factory, patch.object(
            extension, "broadcast_server_status"
        ):
            if restart:
                extension._server = FakeServer(None, host="0.0.0.0", port=9123)
                extension._server.start_sync()

            with pytest.raises(OSError) as exc_info:
                if restart:
                    extension._do_restart_server(announce=False)
                else:
                    extension._do_start_server(announce=False, host="0.0.0.0", port=0)

            assert exc_info.value is start_error
            assert factory.call_count == 1  # No retry or alternate-port fallback.
            assert factory.call_args.kwargs["port"] == (9123 if restart else 0)
            assert (extension._server_host, extension._server_port) == (
                "127.0.0.1",
                8123,
            )
    finally:
        extension._server, extension._server_host, extension._server_port = previous
