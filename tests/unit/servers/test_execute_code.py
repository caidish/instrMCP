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
