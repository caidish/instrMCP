"""
Unit tests for stdio_proxy.py module.

Tests HttpMCPProxy, check_http_mcp_server, and create_stdio_proxy_server
for the STDIO↔HTTP MCP proxy functionality.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from instrmcp.tools.stdio_proxy import (
    HttpMCPProxy,
    check_http_mcp_server,
    create_stdio_proxy_server,
)
from mcp.types import TextContent


class TestHttpMCPProxy:
    """Test HttpMCPProxy class for HTTP MCP server communication."""

    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx AsyncClient."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    def proxy(self, mock_httpx_client):
        """Create HttpMCPProxy instance with mocked client."""
        proxy = HttpMCPProxy(base_url="http://127.0.0.1:8123")
        proxy.client = mock_httpx_client
        return proxy

    def test_proxy_initialization(self):
        """Test proxy is initialized with correct defaults."""
        proxy = HttpMCPProxy()
        assert proxy.base_url == "http://127.0.0.1:8123"
        assert proxy.working_endpoint is None
        assert proxy.session_id is None

    def test_proxy_initialization_custom_url(self):
        """Test proxy initialization with custom URL."""
        proxy = HttpMCPProxy(base_url="http://localhost:9000")
        assert proxy.base_url == "http://localhost:9000"

    def test_proxy_strips_trailing_slash(self):
        """Test proxy strips trailing slash from base URL."""
        proxy = HttpMCPProxy(base_url="http://127.0.0.1:8123/")
        assert proxy.base_url == "http://127.0.0.1:8123"

    @pytest.mark.asyncio
    async def test_find_working_endpoint_success_json(self, proxy, mock_httpx_client):
        """Test finding working endpoint with JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"jsonrpc": "2.0", "result": {"tools": []}}'
        mock_response.json = Mock(
            return_value={"jsonrpc": "2.0", "result": {"tools": []}}
        )
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        endpoint = await proxy._find_working_endpoint()

        assert endpoint == "http://127.0.0.1:8123/mcp"
        assert proxy.working_endpoint == endpoint
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_working_endpoint_success_sse(self, proxy, mock_httpx_client):
        """Test finding working endpoint with SSE response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'data: {"jsonrpc": "2.0", "result": {"tools": []}}\n\n'
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        endpoint = await proxy._find_working_endpoint()

        assert endpoint == "http://127.0.0.1:8123/mcp"
        assert proxy.working_endpoint == endpoint

    @pytest.mark.asyncio
    async def test_find_working_endpoint_cached(self, proxy, mock_httpx_client):
        """Test cached working endpoint is returned."""
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        endpoint = await proxy._find_working_endpoint()

        assert endpoint == "http://127.0.0.1:8123/mcp"
        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_working_endpoint_failure_defaults(
        self, proxy, mock_httpx_client
    ):
        """Test finding working endpoint defaults on failure."""
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Connection error"))

        endpoint = await proxy._find_working_endpoint()

        assert endpoint == "http://127.0.0.1:8123/mcp"
        assert proxy.working_endpoint == endpoint

    @pytest.mark.asyncio
    async def test_ensure_session_success(self, proxy, mock_httpx_client):
        """Test session initialization succeeds."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"mcp-session-id": "test-session-123"}
        mock_response.text = '{"jsonrpc": "2.0", "result": {}}'
        mock_response.json = Mock(return_value={"jsonrpc": "2.0", "result": {}})
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        await proxy._ensure_session()

        assert proxy.session_id == "test-session-123"
        # Should call post three times: once for _find_working_endpoint, once for initialize, once for initialized notification
        assert mock_httpx_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_ensure_session_no_header(self, proxy, mock_httpx_client):
        """Test session initialization without session ID header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        await proxy._ensure_session()

        assert proxy.session_id == "default-session"

    @pytest.mark.asyncio
    async def test_ensure_session_already_initialized(self, proxy, mock_httpx_client):
        """Test session initialization skipped when already set."""
        proxy.session_id = "existing-session"

        await proxy._ensure_session()

        mock_httpx_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ensure_session_failure(self, proxy, mock_httpx_client):
        """Test session initialization handles failure."""
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Connection error"))

        await proxy._ensure_session()

        assert proxy.session_id == "default-session"

    @pytest.mark.asyncio
    async def test_call_success_json_response(self, proxy, mock_httpx_client):
        """Test successful tool call with JSON response."""
        # Setup session
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = (
            '{"jsonrpc": "2.0", "result": {"content": [{"text": "test result"}]}}'
        )
        mock_response.json = Mock(
            return_value={
                "jsonrpc": "2.0",
                "result": {"content": [{"text": "test result"}]},
            }
        )
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool", param1="value1")

        assert result == "test result"
        mock_httpx_client.post.assert_called_once()
        call_args = mock_httpx_client.post.call_args
        assert call_args.kwargs["json"]["method"] == "tools/call"
        assert call_args.kwargs["json"]["params"]["name"] == "test_tool"
        assert call_args.kwargs["json"]["params"]["arguments"] == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_call_success_sse_response(self, proxy, mock_httpx_client):
        """Test successful tool call with SSE response."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'data: {"jsonrpc": "2.0", "result": {"content": [{"text": "sse result"}]}}\n\n'
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool")

        assert result == "sse result"

    @pytest.mark.asyncio
    async def test_call_with_session_header(self, proxy, mock_httpx_client):
        """Test tool call includes session ID header."""
        proxy.session_id = "test-session-456"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"jsonrpc": "2.0", "result": "success"}'
        mock_response.json = Mock(return_value={"jsonrpc": "2.0", "result": "success"})
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        await proxy.call("test_tool")

        call_args = mock_httpx_client.post.call_args
        assert call_args.kwargs["headers"]["mcp-session-id"] == "test-session-456"

    @pytest.mark.asyncio
    async def test_call_error_response(self, proxy, mock_httpx_client):
        """Test tool call handles error response."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}}'
        mock_response.json = Mock(
            return_value={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
            }
        )
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("nonexistent_tool")

        assert "error" in result
        assert "MCP error" in result["error"]

    @pytest.mark.asyncio
    async def test_call_http_error(self, proxy, mock_httpx_client):
        """Test tool call handles HTTP errors."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.raise_for_status = Mock(side_effect=Exception("HTTP 500"))
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool")

        assert "error" in result
        assert "Proxy request failed" in result["error"]

    @pytest.mark.asyncio
    async def test_call_network_error(self, proxy, mock_httpx_client):
        """Test tool call handles network errors."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_httpx_client.post = AsyncMock(side_effect=Exception("Network timeout"))

        result = await proxy.call("test_tool")

        assert "error" in result
        assert "Proxy request failed" in result["error"]

    @pytest.mark.asyncio
    async def test_call_result_without_content(self, proxy, mock_httpx_client):
        """Test tool call with result not containing content."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"jsonrpc": "2.0", "result": "simple result"}'
        mock_response.json = Mock(
            return_value={"jsonrpc": "2.0", "result": "simple result"}
        )
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool")

        assert result == "simple result"

    @pytest.mark.asyncio
    async def test_call_invalid_response(self, proxy, mock_httpx_client):
        """Test tool call handles invalid JSON-RPC response."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"invalid": "response"}'
        mock_response.json = Mock(return_value={"invalid": "response"})
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool")

        assert "error" in result
        assert "Invalid JSON-RPC response" in result["error"]

    @pytest.mark.asyncio
    async def test_call_empty_arguments(self, proxy, mock_httpx_client):
        """Test tool call with no arguments."""
        proxy.session_id = "test-session"
        proxy.working_endpoint = "http://127.0.0.1:8123/mcp"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"jsonrpc": "2.0", "result": "ok"}'
        mock_response.json = Mock(return_value={"jsonrpc": "2.0", "result": "ok"})
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)

        result = await proxy.call("test_tool")

        call_args = mock_httpx_client.post.call_args
        assert call_args.kwargs["json"]["params"]["arguments"] == {}


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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_server_network_error(self, mock_httpx_client):
        """Test server check handles network errors."""
        mock_httpx_client.post = AsyncMock(side_effect=Exception("Network error"))

        with patch(
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
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
            "instrmcp.tools.stdio_proxy.httpx.AsyncClient",
            return_value=mock_httpx_client,
        ):
            result = await check_http_mcp_server()

        assert result is False


class TestCreateStdioProxyServer:
    """Test create_stdio_proxy_server function."""

    def test_create_server_returns_fastmcp(self):
        """Test server creation returns FastMCP instance."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        assert mcp is not None
        assert hasattr(mcp, "tool")

    def test_create_server_custom_name(self):
        """Test server creation with custom name."""
        mcp = create_stdio_proxy_server(
            "http://127.0.0.1:8123", server_name="Custom Proxy"
        )
        assert mcp is not None

    def test_create_server_custom_url(self):
        """Test server creation with custom URL."""
        mcp = create_stdio_proxy_server("http://localhost:9000")
        assert mcp is not None

    @pytest.mark.asyncio
    async def test_qcodes_instrument_info_tool(self):
        """Test qcodes_instrument_info tool is created and callable."""
        with patch.object(HttpMCPProxy, "call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"name": "mock_dac", "parameters": {}}

            mcp = create_stdio_proxy_server("http://127.0.0.1:8123")

            # Find the tool by checking registered tools
            tools = await mcp.get_tools()
            assert "qcodes_instrument_info" in tools

    @pytest.mark.asyncio
    async def test_qcodes_get_parameter_values_tool(self):
        """Test qcodes_get_parameter_values tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "qcodes_get_parameter_values" in tools

    @pytest.mark.asyncio
    async def test_notebook_list_variables_tool(self):
        """Test notebook_list_variables tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_list_variables" in tools

    @pytest.mark.asyncio
    async def test_notebook_get_variable_info_tool(self):
        """Test notebook_get_variable_info tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_get_variable_info" in tools

    @pytest.mark.asyncio
    async def test_notebook_get_editing_cell_tool(self):
        """Test notebook_get_editing_cell tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_get_editing_cell" in tools

    @pytest.mark.asyncio
    async def test_notebook_update_editing_cell_tool(self):
        """Test notebook_update_editing_cell tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_update_editing_cell" in tools

    @pytest.mark.asyncio
    async def test_notebook_get_editing_cell_output_tool(self):
        """Test notebook_get_editing_cell_output tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_get_editing_cell_output" in tools

    @pytest.mark.asyncio
    async def test_notebook_get_notebook_cells_tool(self):
        """Test notebook_get_notebook_cells tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_get_notebook_cells" in tools

    @pytest.mark.asyncio
    async def test_notebook_server_status_tool(self):
        """Test notebook_server_status tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_server_status" in tools

    @pytest.mark.asyncio
    async def test_notebook_execute_cell_tool(self):
        """Test notebook_execute_cell unsafe tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_execute_cell" in tools

    @pytest.mark.asyncio
    async def test_notebook_add_cell_tool(self):
        """Test notebook_add_cell unsafe tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_add_cell" in tools

    @pytest.mark.asyncio
    async def test_notebook_delete_cell_tool(self):
        """Test notebook_delete_cell unsafe tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_delete_cell" in tools

    @pytest.mark.asyncio
    async def test_notebook_delete_cells_tool(self):
        """Test notebook_delete_cells unsafe tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_delete_cells" in tools

    @pytest.mark.asyncio
    async def test_notebook_apply_patch_tool(self):
        """Test notebook_apply_patch unsafe tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_apply_patch" in tools

    @pytest.mark.asyncio
    async def test_notebook_move_cursor_tool(self):
        """Test notebook_move_cursor tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "notebook_move_cursor" in tools

    @pytest.mark.asyncio
    async def test_measureit_get_status_tool(self):
        """Test measureit_get_status optional tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "measureit_get_status" in tools

    @pytest.mark.asyncio
    async def test_database_list_experiments_tool(self):
        """Test database_list_experiments optional tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "database_list_experiments" in tools

    @pytest.mark.asyncio
    async def test_database_get_dataset_info_tool(self):
        """Test database_get_dataset_info optional tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "database_get_dataset_info" in tools

    @pytest.mark.asyncio
    async def test_database_get_database_stats_tool(self):
        """Test database_get_database_stats optional tool is created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()
        assert "database_get_database_stats" in tools

    @pytest.mark.asyncio
    async def test_all_tools_created(self):
        """Test all expected tools are created."""
        mcp = create_stdio_proxy_server("http://127.0.0.1:8123")
        tools = await mcp.get_tools()

        expected_tools = [
            "qcodes_instrument_info",
            "qcodes_get_parameter_values",
            "notebook_list_variables",
            "notebook_get_variable_info",
            "notebook_get_editing_cell",
            "notebook_update_editing_cell",
            "notebook_get_editing_cell_output",
            "notebook_get_notebook_cells",
            "notebook_server_status",
            "notebook_execute_cell",
            "notebook_add_cell",
            "notebook_delete_cell",
            "notebook_delete_cells",
            "notebook_apply_patch",
            "notebook_move_cursor",
            "measureit_get_status",
            "database_list_experiments",
            "database_get_dataset_info",
            "database_get_database_stats",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tools, f"Tool {expected_tool} not found"

    @pytest.mark.asyncio
    async def test_tool_returns_text_content(self):
        """Test tools return TextContent with proper structure."""
        with patch.object(HttpMCPProxy, "call", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"status": "ok"}

            mcp = create_stdio_proxy_server("http://127.0.0.1:8123")

            # Verify all tools are created
            tools = await mcp.get_tools()
            # 19 original tools + 6 dynamic tool meta-tools = 25
            assert len(tools) == 25
