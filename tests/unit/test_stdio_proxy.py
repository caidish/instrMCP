"""
Unit tests for stdio_proxy.py module.

Tests check_http_mcp_server function for the STDIO↔HTTP MCP proxy functionality.

Note: Tests for create_stdio_proxy_server are done manually via integration testing.
The function uses FastMCP.as_proxy() which requires a live backend connection.
"""

import pytest
from unittest.mock import AsyncMock, patch, Mock
from instrmcp.utils.stdio_proxy import check_http_mcp_server


class TestCheckHttpMcpServer:
    """Test check_http_mcp_server function."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx AsyncClient."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.mark.asyncio
    async def test_check_server_success_json(self, mock_httpx_client):
        """Test successful server check with JSON response."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.headers = {"mcp-session-id": "test-session"}

        mock_test_response = Mock()
        mock_test_response.status_code = 200
        mock_test_response.text = '{"jsonrpc": "2.0", "result": {"tools": []}}'
        mock_test_response.json = Mock(
            return_value={"jsonrpc": "2.0", "result": {"tools": []}}
        )

        mock_httpx_client.post = AsyncMock(
            side_effect=[
                mock_init_response,  # initialize
                mock_init_response,  # initialized notification
                mock_test_response,  # tools/list
            ]
        )

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_server_success_sse(self, mock_httpx_client):
        """Test successful server check with SSE response."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.headers = {"mcp-session-id": "test-session"}

        mock_test_response = Mock()
        mock_test_response.status_code = 200
        mock_test_response.text = (
            'data: {"jsonrpc": "2.0", "result": {"tools": []}}\n\n'
        )

        mock_httpx_client.post = AsyncMock(
            side_effect=[
                mock_init_response,
                mock_init_response,
                mock_test_response,
            ]
        )

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_server_custom_host_port(self, mock_httpx_client):
        """Test server check with custom host and port."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.headers = {"mcp-session-id": "test-session"}

        mock_test_response = Mock()
        mock_test_response.status_code = 200
        mock_test_response.text = '{"jsonrpc": "2.0", "result": {}}'
        mock_test_response.json = Mock(return_value={"jsonrpc": "2.0", "result": {}})

        mock_httpx_client.post = AsyncMock(
            side_effect=[
                mock_init_response,
                mock_init_response,
                mock_test_response,
            ]
        )

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server(host="localhost", port=9000)

        assert result is True
        # Verify the endpoint was called with correct URL
        call_args = mock_httpx_client.post.call_args_list[0]
        assert "http://localhost:9000/mcp" in str(call_args)

    @pytest.mark.asyncio
    async def test_check_server_init_failure(self, mock_httpx_client):
        """Test server check fails on initialization."""
        mock_response = Mock()
        mock_response.status_code = 500

        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_no_session_id(self, mock_httpx_client):
        """Test server check fails without session ID."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}

        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_tools_list_failure(self, mock_httpx_client):
        """Test server check fails on tools/list."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.headers = {"mcp-session-id": "test-session"}

        mock_test_response = Mock()
        mock_test_response.status_code = 500

        mock_httpx_client.post = AsyncMock(
            side_effect=[
                mock_init_response,
                mock_init_response,
                mock_test_response,
            ]
        )

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_network_error(self, mock_httpx_client):
        """Test server check handles network errors."""
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Network error"))

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_invalid_response(self, mock_httpx_client):
        """Test server check fails on invalid response."""
        mock_init_response = Mock()
        mock_init_response.status_code = 200
        mock_init_response.headers = {"mcp-session-id": "test-session"}

        mock_test_response = Mock()
        mock_test_response.status_code = 200
        mock_test_response.text = '{"invalid": "response"}'
        mock_test_response.json = Mock(return_value={"invalid": "response"})

        mock_httpx_client.post = AsyncMock(
            side_effect=[
                mock_init_response,
                mock_init_response,
                mock_test_response,
            ]
        )

        with patch(
            "instrmcp.utils.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False
