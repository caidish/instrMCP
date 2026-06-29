"""
Unit tests for the notebook_execute_code unsafe tool registration
(bridge-independent kernel execution, instrMCP#29).
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from instrmcp.servers.jupyter_qcodes.core.notebook_unsafe_tools import (
    UnsafeToolRegistrar,
)


def make_mcp():
    mcp = MagicMock()
    mcp._tools = {}

    def tool_decorator(name=None, annotations=None, **kwargs):
        def wrapper(func):
            mcp._tools[name or func.__name__] = func
            return func

        return wrapper

    mcp.tool = tool_decorator
    return mcp


def make_tools():
    tools = MagicMock()
    tools.execute_code = AsyncMock(
        return_value={
            "success": True,
            "executed": True,
            "status": "completed",
            "has_output": True,
            "stdout": "42\n",
            "execution_count": 7,
        }
    )
    return tools


def test_registers_notebook_execute_code_tool():
    mcp = make_mcp()
    UnsafeToolRegistrar(mcp, make_tools(), consent_manager=None).register_all()
    assert "notebook_execute_code" in mcp._tools


@pytest.mark.asyncio
async def test_safe_code_delegates_to_execute_code():
    mcp = make_mcp()
    tools = make_tools()
    UnsafeToolRegistrar(mcp, tools, consent_manager=None).register_all()

    blocks = await mcp._tools["notebook_execute_code"](code="print(42)", timeout=5.0)

    tools.execute_code.assert_awaited_once()
    args, kwargs = tools.execute_code.call_args
    passed_code = kwargs.get("code", args[0] if args else None)
    assert passed_code == "print(42)"
    payload = json.loads(blocks[0].text)
    assert payload["status"] == "completed"
    assert payload["stdout"] == "42\n"


@pytest.mark.asyncio
async def test_dangerous_code_rejected_before_execution():
    mcp = make_mcp()
    tools = make_tools()
    UnsafeToolRegistrar(mcp, tools, consent_manager=None).register_all()

    blocks = await mcp._tools["notebook_execute_code"](
        code="import os; os.system('rm -rf /')", timeout=5.0
    )

    tools.execute_code.assert_not_called()
    payload = json.loads(blocks[0].text)
    assert payload.get("blocked") is True or payload.get("success") is False


@pytest.mark.asyncio
async def test_declined_consent_blocks_execution():
    mcp = make_mcp()
    tools = make_tools()
    consent = MagicMock()
    consent.request_consent = AsyncMock(
        return_value={"approved": False, "reason": "User declined"}
    )
    UnsafeToolRegistrar(mcp, tools, consent_manager=consent).register_all()

    blocks = await mcp._tools["notebook_execute_code"](code="print(1)", timeout=5.0)

    consent.request_consent.assert_awaited_once()
    tools.execute_code.assert_not_called()
    payload = json.loads(blocks[0].text)
    assert payload["success"] is False
