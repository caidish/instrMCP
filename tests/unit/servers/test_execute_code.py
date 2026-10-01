"""
Unit tests for notebook_execute_code — the bridge-independent kernel execution
route (instrMCP#29). The code is sent to the kernel as a ZMQ execute_request via
a loopback jupyter_client; here we test the pure result assembly and the
execute_code control flow. The live-kernel client path is covered by the e2e.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

from instrmcp.servers.jupyter_qcodes.tools import QCodesReadOnlyTools


def make_backend():
    ip = MagicMock()
    ip.user_ns = {}
    ip.execution_count = 0
    return QCodesReadOnlyTools(ip)._notebook_unsafe


# ---- pure result assembly (_assemble_kernel_result) ----


def test_assemble_completed_with_stdout():
    b = make_backend()
    r = b._assemble_kernel_result(
        {"status": "ok", "execution_count": 7},
        {"stdout": ["42\n"], "stderr": [], "result": None, "error": None},
        "print(42)",
    )
    assert r["status"] == "completed"
    assert r["has_error"] is False
    assert r["has_output"] is True
    assert r["stdout"] == "42\n"
    assert r["execution_count"] == 7


def test_assemble_error_from_iopub():
    b = make_backend()
    r = b._assemble_kernel_result(
        {"status": "error", "execution_count": 3},
        {
            "stdout": [],
            "stderr": [],
            "result": None,
            "error": ("ValueError", "boom", ["tb-line-1", "tb-line-2"]),
        },
        "raise ValueError('boom')",
    )
    assert r["status"] == "error"
    assert r["has_error"] is True
    assert r["error_type"] == "ValueError"
    assert r["error_message"] == "boom"
    assert "tb-line-1" in r["traceback"]


def test_assemble_detects_sweep():
    b = make_backend()
    r = b._assemble_kernel_result(
        {"status": "ok", "execution_count": 1},
        {"stdout": [], "stderr": [], "result": None, "error": None},
        "sweep.start()",
    )
    assert r["sweep_detected"] is True
    assert "sweep" in r["sweep_names"]
    assert "measureit_wait_for_sweep" in r["suggestion"]


def test_assemble_includes_result_value():
    b = make_backend()
    r = b._assemble_kernel_result(
        {"status": "ok", "execution_count": 2},
        {"stdout": [], "stderr": [], "result": "99", "error": None},
        "x",
    )
    assert r["result"] == "99"


# ---- execute_code control flow (kernel client mocked) ----


@pytest.mark.asyncio
async def test_execute_code_returns_kernel_client_result(monkeypatch):
    tools = QCodesReadOnlyTools(MagicMock(user_ns={}, execution_count=0))
    canned = {
        "success": True,
        "executed": True,
        "status": "completed",
        "has_error": False,
        "has_output": True,
        "stdout": "hi\n",
        "execution_count": 5,
    }
    monkeypatch.setattr(
        tools._notebook_unsafe,
        "_exec_via_kernel_client",
        lambda code, timeout: canned,
    )
    result = await tools.execute_code("print('hi')", timeout=5.0)
    assert result == canned


@pytest.mark.asyncio
async def test_execute_code_fire_and_forget_returns_no_wait(monkeypatch):
    tools = QCodesReadOnlyTools(MagicMock(user_ns={}, execution_count=0))
    monkeypatch.setattr(
        tools._notebook_unsafe,
        "_exec_via_kernel_client",
        lambda code, timeout: None,
    )
    result = await asyncio.wait_for(tools.execute_code("x = 1", timeout=0), timeout=2.0)
    assert result["executed"] is True
    assert result["status"] == "no_wait"


def test_kernel_client_allows_cold_start_to_use_execution_timeout(monkeypatch):
    tools = QCodesReadOnlyTools(MagicMock(user_ns={}, execution_count=0))
    client = MagicMock()
    client.execute_interactive.return_value = {
        "content": {"status": "ok", "execution_count": 1}
    }
    monkeypatch.setattr("ipykernel.get_connection_file", lambda: "kernel.json")
    monkeypatch.setattr("jupyter_client.BlockingKernelClient", lambda **_kwargs: client)

    result = tools._notebook_unsafe._exec_via_kernel_client("x = 1", 45.0)

    client.wait_for_ready.assert_called_once_with(timeout=45.0)
    assert result["status"] == "completed"


def test_execution_guard_covers_readiness_and_execution():
    from instrmcp.servers.jupyter_qcodes.backend.notebook_unsafe import (
        _execution_guard_seconds,
    )

    # The kernel-readiness wait is max(30 s, timeout) and execution may then take
    # another full timeout, so the outer guard has to outlive both.
    assert _execution_guard_seconds(5.0) == 45.0
    assert _execution_guard_seconds(45.0) == 100.0
    for timeout in (1.0, 5.0, 30.0, 45.0, 120.0):
        assert _execution_guard_seconds(timeout) > max(30.0, timeout) + timeout


@pytest.mark.asyncio
async def test_execute_code_guard_does_not_fire_during_readiness(monkeypatch):
    """execute_code must pass the guard derived above to asyncio.wait_for."""
    tools = QCodesReadOnlyTools(MagicMock(user_ns={}, execution_count=0))
    backend = tools._notebook_unsafe
    monkeypatch.setattr(
        backend, "_exec_via_kernel_client", lambda code, timeout: {"sent": True}
    )
    captured = {}

    async def fake_wait_for(awaitable, timeout):
        captured["guard"] = timeout
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        return {"sent": True}

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    result = await backend.execute_code("1 + 1", timeout=5.0)

    assert captured["guard"] == 45.0
    assert result == {"sent": True}
