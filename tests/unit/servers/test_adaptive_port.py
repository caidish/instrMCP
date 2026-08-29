"""Tests for an OS-assigned Jupyter MCP listener port."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from instrmcp.servers.jupyter_qcodes import jupyter_mcp_extension as extension
from instrmcp.servers.jupyter_qcodes.mcp_server import JupyterMCPServer


def test_start_server_passes_requested_loopback_endpoint():
    server = MagicMock()
    server.host = "127.0.0.1"
    server.port = 43123
    server.is_running.return_value = True

    previous = extension._server
    extension._server = None
    try:
        with patch(
            "IPython.core.getipython.get_ipython", return_value=MagicMock()
        ), patch.object(extension, "JupyterMCPServer", return_value=server) as factory:
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
        extension._server = previous


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
