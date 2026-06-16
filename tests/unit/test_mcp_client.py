"""Unit tests for instrmcp.app.mcp_client (MCP-over-HTTP tool calls)."""

import asyncio
import json

from instrmcp.app import mcp_client


class FakeResponse:
    def __init__(self, status_code=200, text="", headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeClient:
    """Stand-in for httpx.AsyncClient that scripts responses by JSON-RPC method."""

    def __init__(self, *, tool_result=None, tool_error=False, no_session=False):
        self.tool_result = tool_result
        self.tool_error = tool_error
        self.no_session = no_session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, endpoint, json=None, headers=None):
        method = (json or {}).get("method")
        if method == "initialize":
            headers = {} if self.no_session else {"mcp-session-id": "sess-1"}
            return FakeResponse(200, "{}", headers)
        if method == "notifications/initialized":
            return FakeResponse(200, "{}")
        if method == "tools/call":
            if self.tool_error:
                return FakeResponse(
                    200,
                    _to_text({"jsonrpc": "2.0", "id": "call", "error": {"code": -1}}),
                )
            return FakeResponse(
                200,
                _to_text({"jsonrpc": "2.0", "id": "call", "result": self.tool_result}),
            )
        return FakeResponse(404, "")


def _to_text(payload):
    import json as _json

    return _json.dumps(payload)


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(mcp_client.httpx, "AsyncClient", lambda *a, **k: client)


def test_get_measureit_status_parses_json(monkeypatch):
    status = {"active": True, "sweeps": {"s1": {"state": "running", "progress": 0.5}}}
    result = {"content": [{"type": "text", "text": json.dumps(status)}]}
    _patch_client(monkeypatch, FakeClient(tool_result=result))
    out = asyncio.run(mcp_client.get_measureit_status())
    assert out == status


def test_get_measureit_status_tool_error_returns_none(monkeypatch):
    _patch_client(monkeypatch, FakeClient(tool_error=True))
    assert asyncio.run(mcp_client.get_measureit_status()) is None


def test_get_measureit_status_no_session_returns_none(monkeypatch):
    _patch_client(monkeypatch, FakeClient(no_session=True))
    assert asyncio.run(mcp_client.get_measureit_status()) is None


def test_call_tool_returns_result(monkeypatch):
    result = {"content": [{"type": "text", "text": "hi"}]}
    _patch_client(monkeypatch, FakeClient(tool_result=result))
    out = asyncio.run(mcp_client.call_tool("some_tool"))
    assert out == result


def test_extract_text():
    assert mcp_client._extract_text({"content": [{"type": "text", "text": "x"}]}) == "x"
    assert mcp_client._extract_text({"content": []}) is None


# ---------------------------------------------------------------------------
# Introspection (tools/list, resources/list, prompts/list, read, get) used by
# the embedded Inspector. The Inspector reuses the same handshake as call_tool.
# ---------------------------------------------------------------------------


class ScriptedClient:
    """Fake httpx.AsyncClient mapping a JSON-RPC method to a result payload.

    ``results`` maps method name -> result dict. A method absent from the map
    responds with a JSON-RPC error so callers exercise the error path.
    """

    def __init__(self, results, *, no_session=False):
        self.results = results
        self.no_session = no_session

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, endpoint, json=None, headers=None):
        method = (json or {}).get("method")
        if method == "initialize":
            hdrs = {} if self.no_session else {"mcp-session-id": "sess-1"}
            return FakeResponse(200, "{}", hdrs)
        if method == "notifications/initialized":
            return FakeResponse(200, "{}")
        if method in self.results:
            return FakeResponse(
                200,
                _to_text(
                    {"jsonrpc": "2.0", "id": "req", "result": self.results[method]}
                ),
            )
        return FakeResponse(
            200,
            _to_text({"jsonrpc": "2.0", "id": "req", "error": {"code": -32601}}),
        )


def test_list_tools_returns_tools(monkeypatch):
    tools = [{"name": "qcodes_instrument_info", "description": "..."}]
    _patch_client(monkeypatch, ScriptedClient({"tools/list": {"tools": tools}}))
    assert asyncio.run(mcp_client.list_tools()) == tools


def test_list_resources_returns_resources(monkeypatch):
    resources = [{"uri": "resource://available_instruments", "name": "Instruments"}]
    _patch_client(
        monkeypatch, ScriptedClient({"resources/list": {"resources": resources}})
    )
    assert asyncio.run(mcp_client.list_resources()) == resources


def test_list_prompts_returns_prompts(monkeypatch):
    prompts = [{"name": "analyze", "description": "..."}]
    _patch_client(monkeypatch, ScriptedClient({"prompts/list": {"prompts": prompts}}))
    assert asyncio.run(mcp_client.list_prompts()) == prompts


def test_list_tools_unsupported_returns_none(monkeypatch):
    # Server without the capability replies with a JSON-RPC error → None.
    _patch_client(monkeypatch, ScriptedClient({}))
    assert asyncio.run(mcp_client.list_tools()) is None


def test_read_resource_returns_contents(monkeypatch):
    contents = {"contents": [{"uri": "resource://x", "text": "hello"}]}
    _patch_client(monkeypatch, ScriptedClient({"resources/read": contents}))
    out = asyncio.run(mcp_client.read_resource("resource://x"))
    assert out == contents


def test_get_prompt_returns_messages(monkeypatch):
    result = {"messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}]}
    _patch_client(monkeypatch, ScriptedClient({"prompts/get": result}))
    out = asyncio.run(mcp_client.get_prompt("analyze", {"data": 1}))
    assert out == result


def test_request_no_session_returns_none(monkeypatch):
    _patch_client(
        monkeypatch, ScriptedClient({"tools/list": {"tools": []}}, no_session=True)
    )
    assert asyncio.run(mcp_client.list_tools()) is None
