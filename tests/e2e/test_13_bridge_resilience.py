"""
Bridge Resilience Tests (test_13_bridge_resilience.py)

Purpose: Durable e2e coverage for the JupyterLab notebook-bridge "stale state"
work (instrMCP #29 / PRs #30, #32, #33), folding two previously-throwaway local
harnesses (/tmp/bridge_repro/repro.py, e2e_execute_code.py) into the suite.

Background:
A listener leak in the browser extension (``src/index.ts``) connected a new
``sharedModel.changed`` listener on every ``activeCellChanged`` without
disconnecting the old one. Under load this could turn a cell edit into a storm
of concurrent ``sendSnapshot()`` / ``comm.send()`` calls that wedged the single
JupyterLab kernel-message chain: ``execute_active_cell`` stopped running the
cell and ``add_cell`` timed out at 2.0s, while the renderer and kernel stayed
alive. PR #30 removed the leak (one live listener at a time), #33 hardened the
comm path, and #32 added ``notebook_execute_code`` as a bridge-independent
recovery route (loopback ``BlockingKernelClient``).

NOTE on the wedge (important): it is a timing-sensitive race and is NOT
deterministically reproducible in this e2e harness. The original reproduction
(repro.py against the qdevBot task notebook) runs 30/30 cycles clean even
against the *unpatched, leak-present* frontend on contemporary hardware - and
neither the dangerous nor the MeasureIt/qt fixture wedges at 80 rapid cycles
with the leak present. So BR-001 below is an honest burst/responsiveness smoke
test (it exercises the exact pattern and catches gross bridge breakage /
latency blowups), NOT a guard that fails when the leak is reintroduced. The
leak fix itself lives in TypeScript (``stopTrackingActiveCell`` in src/index.ts)
and is verified by the #30 change / code inspection, not e2e. The genuinely
load-bearing safety net here is BR-012: the deterministic recovery path
(``notebook_execute_code``) for when the frontend bridge is gone.

Test IDs:
- BR-001: Rapid add_cell + execute_active_cell burst stays responsive (smoke).
- BR-010: notebook_execute_code is registered and runs on the real kernel.
- BR-011: notebook_execute_code shares the kernel namespace + advances exec count.
- BR-012: With the frontend dead, add_cell fails but execute_code still runs.

All tests use the dangerous-mode fixture (auto-approves the consent that
execute_active_cell / execute_code require) and the live kernel the dangerous
notebook already provides - no qdevBot task and no %mcp_restart dance.
"""

import json

import pytest

from tests.e2e.helpers.jupyter_helpers import count_cells
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    list_mcp_tools,
    parse_tool_result,
)

# Cycles for the burst/responsiveness smoke test (BR-001). NOT a leak guard -
# the listener-leak wedge is a timing race not reproducible in-harness (see the
# module docstring). 25 rapid add+execute cycles still catches gross bridge
# breakage and latency blowups.
BURST_CYCLES = 25


def _call_json(url: str, tool: str, args: dict | None = None) -> dict:
    """Call an MCP tool and parse its JSON payload.

    Returns the decoded tool result dict. Asserts the JSON-RPC call itself
    succeeded (transport-level), not that the tool's own ``success`` field is
    True - callers inspect that themselves.
    """
    ok, text = parse_tool_result(call_mcp_tool(url, tool, args))
    assert ok, f"{tool} JSON-RPC call failed: {text}"
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:  # pragma: no cover
        pytest.fail(f"{tool} did not return JSON: {exc}\nraw: {text!r}")


class TestBridgeBurstResponsiveness:
    """BR-001: a rapid add+execute burst keeps the bridge responsive.

    Smoke test, not a leak guard - see the module docstring on why the
    listener-leak wedge is not deterministically reproducible in this harness.
    """

    @pytest.mark.p1
    @pytest.mark.slow
    def test_rapid_add_execute_burst_stays_responsive(self, mcp_server_dangerous):
        """BR-001: Rapid add_cell + execute_active_cell burst stays responsive.

        Replays the agent pattern associated with the original wedge and asserts
        the bridge keeps mutating + executing cells throughout: every add
        succeeds, no execute returns a 'timeout' status, and the notebook grows
        one cell per cycle. Catches gross bridge breakage / latency blowups; it
        does not (and cannot, in this harness) reproduce the timing-sensitive
        listener-leak wedge.
        """
        url = mcp_server_dangerous["url"]
        page = mcp_server_dangerous["page"]

        initial_count = count_cells(page)

        for n in range(1, BURST_CYCLES + 1):
            # Add a trivial cell at the end (becomes the active cell).
            add = _call_json(
                url,
                "notebook_add_cell",
                {
                    "cell_type": "code",
                    "position": "end",
                    "content": f"_burst_marker_{n} = {n}",
                },
            )
            assert (
                add.get("success") is True
            ), f"cycle {n}: notebook_add_cell did not succeed -> {add}"
            page.wait_for_timeout(150)

            # Execute the just-added cell; a 'timeout' status means the bridge
            # stopped driving the kernel.
            exe = _call_json(
                url, "notebook_execute_active_cell", {"timeout": 20, "detailed": False}
            )
            assert (
                exe.get("status") != "timeout"
            ), f"cycle {n}: execute_active_cell timed out -> {exe}"
            page.wait_for_timeout(150)

        # Every add must have landed a cell - a wedged/broken bridge stops
        # mutating the notebook.
        final_count = count_cells(page)
        assert final_count >= initial_count + BURST_CYCLES, (
            f"notebook did not grow by {BURST_CYCLES} cells "
            f"({initial_count} -> {final_count}); bridge stopped adding cells"
        )


class TestExecuteCodeKernelDirect:
    """BR-010/011: notebook_execute_code runs bridge-independently on the kernel."""

    @pytest.mark.p0
    def test_execute_code_registered_and_runs(self, mcp_server_dangerous):
        """BR-010: notebook_execute_code is exposed and runs on the real kernel."""
        url = mcp_server_dangerous["url"]

        tool_names = {t["name"] for t in list_mcp_tools(url)}
        assert (
            "notebook_execute_code" in tool_names
        ), f"notebook_execute_code not registered; available: {sorted(tool_names)}"

        out = _call_json(
            url, "notebook_execute_code", {"code": "print(6 * 7)", "timeout": 20}
        )
        assert out.get("status") == "completed", f"execute_code did not complete: {out}"
        assert "42" in out.get("stdout", ""), f"stdout missing '42': {out!r}"
        assert isinstance(
            out.get("execution_count"), int
        ), f"execution_count not an int: {out!r}"

    @pytest.mark.p1
    def test_execute_code_shares_namespace_and_advances_count(
        self, mcp_server_dangerous
    ):
        """BR-011: execute_code shares the kernel namespace + advances exec count."""
        url = mcp_server_dangerous["url"]

        first = _call_json(
            url, "notebook_execute_code", {"code": "e2e_marker = 1234", "timeout": 20}
        )
        assert first.get("status") == "completed", f"set marker failed: {first}"
        ec1 = first.get("execution_count")

        second = _call_json(
            url, "notebook_execute_code", {"code": "print(e2e_marker)", "timeout": 20}
        )
        assert second.get("status") == "completed", f"read marker failed: {second}"
        assert "1234" in second.get(
            "stdout", ""
        ), f"namespace not shared across execute_code calls: {second!r}"

        ec2 = second.get("execution_count")
        assert (
            isinstance(ec1, int) and isinstance(ec2, int) and ec2 > ec1
        ), f"execution_count did not advance: {ec1} -> {ec2}"


class TestFrontendKilledRecovery:
    """BR-012: execute_code is the deterministic recovery path when the bridge dies."""

    @pytest.mark.p0
    def test_execute_code_survives_frontend_death(self, mcp_server_dangerous):
        """BR-012: kill the frontend -> add_cell fails but execute_code still runs.

        Navigating the page to about:blank tears down the JupyterLab frontend
        (and its active-cell comm) while leaving the kernel + MCP HTTP server
        alive. notebook_add_cell needs the frontend and must fail; the
        kernel-direct notebook_execute_code must still run.
        """
        url = mcp_server_dangerous["url"]
        page = mcp_server_dangerous["page"]

        # Sanity: execute_code works while the frontend is alive.
        alive = _call_json(
            url, "notebook_execute_code", {"code": "print('pre-kill')", "timeout": 20}
        )
        assert alive.get("status") == "completed", f"pre-kill execute failed: {alive}"

        # Kill the frontend: destroy the JupyterLab JS app (closes the comm ws).
        # Using goto(about:blank) instead of page.close() keeps the Playwright
        # page object valid for pytest-playwright's own teardown.
        page.goto("about:blank")
        page.wait_for_timeout(1500)

        # add_cell now depends on a dead frontend -> it must fail (it times out
        # against the missing comm within ~2s and reports failure).
        ok, add_text = parse_tool_result(
            call_mcp_tool(
                url,
                "notebook_add_cell",
                {"cell_type": "code", "position": "end", "content": "print('x')"},
            )
        )
        low = add_text.lower()
        add_failed = (
            (not ok)
            or ('"success": false' in low)
            or ("frontend" in low)
            or ("timeout" in low)
        )
        assert add_failed, f"add_cell should fail with the frontend dead: {add_text}"

        # The kernel-direct route still works - this is the recovery path.
        recovered = _call_json(
            url,
            "notebook_execute_code",
            {"code": "print('alive without frontend')", "timeout": 20},
        )
        assert (
            recovered.get("status") == "completed"
        ), f"execute_code should still run with the frontend dead: {recovered}"
        assert "alive without frontend" in recovered.get(
            "stdout", ""
        ), f"execute_code stdout missing after frontend death: {recovered!r}"
