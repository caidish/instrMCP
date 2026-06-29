"""Unit tests for instrmcp.app.inspector (synchronous facade for the GUI).

The Inspector wraps the async ``mcp_client`` calls in a blocking, structured
form Streamlit can render: ``{ok, ..., error}`` dicts. These tests monkeypatch
the async ``mcp_client`` functions, so no network/kernel is required.
"""

from instrmcp.app import inspector


def _aret(value):
    """Build an async stand-in returning ``value``."""

    async def _f(*a, **k):
        return value

    return _f


def test_inspect_returns_components(monkeypatch):
    tools = [{"name": "qcodes_instrument_info"}]
    resources = [{"uri": "resource://available_instruments"}]
    prompts = [{"name": "analyze"}]
    monkeypatch.setattr(inspector.mcp_client, "list_tools", _aret(tools))
    monkeypatch.setattr(inspector.mcp_client, "list_resources", _aret(resources))
    monkeypatch.setattr(inspector.mcp_client, "list_prompts", _aret(prompts))

    out = inspector.inspect()
    assert out["ok"] is True
    assert out["error"] is None
    assert out["tools"] == tools
    assert out["resources"] == resources
    assert out["prompts"] == prompts


def test_inspect_unreachable_when_tools_none(monkeypatch):
    # tools/list None means the handshake failed → server not reachable.
    monkeypatch.setattr(inspector.mcp_client, "list_tools", _aret(None))
    monkeypatch.setattr(inspector.mcp_client, "list_resources", _aret(None))
    monkeypatch.setattr(inspector.mcp_client, "list_prompts", _aret(None))

    out = inspector.inspect(host="127.0.0.1", port=8123)
    assert out["ok"] is False
    assert out["error"]
    assert "8123" in out["error"]
    assert out["tools"] == []


def test_inspect_tolerates_missing_resource_and_prompt_caps(monkeypatch):
    # A server with tools but no resources/prompts capability returns None for
    # those — the Inspector renders them as empty, not as a failure.
    monkeypatch.setattr(inspector.mcp_client, "list_tools", _aret([{"name": "t"}]))
    monkeypatch.setattr(inspector.mcp_client, "list_resources", _aret(None))
    monkeypatch.setattr(inspector.mcp_client, "list_prompts", _aret(None))

    out = inspector.inspect()
    assert out["ok"] is True
    assert out["resources"] == []
    assert out["prompts"] == []


def test_call_tool_sync_success(monkeypatch):
    result = {"content": [{"type": "text", "text": "42"}]}
    monkeypatch.setattr(inspector.mcp_client, "call_tool", _aret(result))

    out = inspector.call_tool_sync("answer", {"q": "x"})
    assert out["ok"] is True
    assert out["result"] == result
    assert out["text"] == "42"


def test_call_tool_sync_failure(monkeypatch):
    monkeypatch.setattr(inspector.mcp_client, "call_tool", _aret(None))

    out = inspector.call_tool_sync("broken")
    assert out["ok"] is False
    assert out["error"]


def test_read_resource_sync_success(monkeypatch):
    result = {"contents": [{"uri": "resource://x", "text": "hello"}]}
    monkeypatch.setattr(inspector.mcp_client, "read_resource", _aret(result))

    out = inspector.read_resource_sync("resource://x")
    assert out["ok"] is True
    assert out["result"] == result


def test_read_resource_sync_failure(monkeypatch):
    monkeypatch.setattr(inspector.mcp_client, "read_resource", _aret(None))

    out = inspector.read_resource_sync("resource://missing")
    assert out["ok"] is False
    assert out["error"]


def test_get_prompt_sync_success(monkeypatch):
    result = {"messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}]}
    monkeypatch.setattr(inspector.mcp_client, "get_prompt", _aret(result))

    out = inspector.get_prompt_sync("analyze", {"data": 1})
    assert out["ok"] is True
    assert out["result"] == result


def test_parse_json_args_empty_is_empty_dict():
    assert inspector.parse_json_args("") == ({}, None)
    assert inspector.parse_json_args("   ") == ({}, None)


def test_parse_json_args_valid_object():
    args, err = inspector.parse_json_args('{"detailed": true, "n": 3}')
    assert err is None
    assert args == {"detailed": True, "n": 3}


def test_parse_json_args_invalid_json():
    args, err = inspector.parse_json_args("{not json}")
    assert args is None
    assert "Invalid JSON" in err


def test_parse_json_args_non_object_rejected():
    args, err = inspector.parse_json_args("[1, 2, 3]")
    assert args is None
    assert "object" in err.lower()
