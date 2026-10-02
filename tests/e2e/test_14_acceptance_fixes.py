"""
Acceptance fixes from issue #48 (work package A), e2e coverage.

A1. `notebook_add_cell(cell_type="markdown")` used to wait out the 10 s frontend
    timeout although the cell was added and saved: the cell-type change replaces
    the active cell widget, a snapshot send then saw a stale cell whose model was
    already null, and its error path dropped the active-cell comm from the
    extension's maps. The in-flight add-cell reply could then no longer be sent.
A2. A refused add on a notebook changed on disk reported only
    `{"success": false}`; the reason (changed-on-disk) must reach the caller.
A3. A page reload or a closed/killed tab left the attestation at
    `connected: True` with a growing `connectionCount`; the kernel side has to
    learn the page went away (pagehide message, plus a heartbeat timeout for the
    hard case).

Each test drives the real JupyterLab + kernel stack. On Windows the suite cannot
run multi-test sessions (the harness's kill_port uses `lsof`), so run these one
at a time with `-k`.
"""

import glob
import json
import pathlib
import time

import pytest

from tests.e2e.helpers.jupyter_helpers import count_cells
from tests.e2e.helpers.mcp_helpers import (
    call_mcp_tool,
    parse_tool_result,
)

ATTESTATION_VAR = "qdevbot_instrmcp_frontend"

ATTESTATION_READER = (
    "import json as _json\n"
    "print('ATTEST' + _json.dumps("
    f"get_ipython().user_ns.get('{ATTESTATION_VAR}')))"
)


def _call_json(url: str, tool: str, args: dict | None = None) -> dict:
    """Call an MCP tool and parse its JSON payload (transport must succeed)."""
    ok, text = parse_tool_result(call_mcp_tool(url, tool, args))
    assert ok, f"{tool} JSON-RPC call failed: {text}"
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:  # pragma: no cover
        pytest.fail(f"{tool} did not return JSON: {exc}\nraw: {text!r}")


def _attestation(url: str) -> dict | None:
    """Read the frontend attestation variable through a kernel-side code run."""
    result = _call_json(url, "notebook_execute_code", {"code": ATTESTATION_READER})
    stdout = result.get("stdout") or ""
    for line in stdout.splitlines():
        if line.startswith("ATTEST"):
            return json.loads(line[len("ATTEST") :])
    return None


def _working_notebook() -> pathlib.Path:
    matches = sorted(glob.glob("tests/e2e/notebooks/_working/*.ipynb"))
    assert matches, "no working notebook found"
    return pathlib.Path(matches[0])


class TestAddCellAcceptance:
    """A1 / A2: add-cell result and timing."""

    @pytest.mark.p0
    def test_markdown_add_cell_returns_success_quickly(self, mcp_server_dangerous):
        """A1: a markdown add reports success well under the 10 s timeout."""
        url = mcp_server_dangerous["url"]
        page = mcp_server_dangerous["page"]
        initial = count_cells(page)

        started = time.time()
        result = _call_json(
            url,
            "notebook_add_cell",
            {
                "cell_type": "markdown",
                "position": "end",
                "content": "# Acceptance heading",
            },
        )
        elapsed = time.time() - started

        assert (
            result.get("success") is True
        ), f"markdown add_cell did not succeed after {elapsed:.1f}s -> {result}"
        assert elapsed < 3.0, (
            f"markdown add_cell took {elapsed:.1f}s (frontend timeout is 10s); "
            "the reply is being swallowed"
        )
        assert count_cells(page) == initial + 1

    @pytest.mark.p0
    def test_add_cell_on_externally_changed_notebook_reports_reason(
        self, mcp_server_dangerous
    ):
        """A2: a refusal on a changed-on-disk notebook must carry the reason."""
        url = mcp_server_dangerous["url"]

        notebook = _working_notebook()
        payload = json.loads(notebook.read_text(encoding="utf-8"))
        payload.setdefault("cells", []).append(
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": ["external edit\n"],
            }
        )
        notebook.write_text(json.dumps(payload, indent=1), encoding="utf-8")

        before = notebook.read_bytes()
        result = _call_json(
            url,
            "notebook_add_cell",
            {"cell_type": "code", "position": "end", "content": "1 + 1"},
        )

        assert result.get("success") is False, result
        reason = result.get("error") or result.get("message") or ""
        assert (
            "changed" in reason.lower()
        ), f"add-cell refusal did not carry the changed-on-disk reason -> {result}"
        assert notebook.read_bytes() == before, "refusal must not rewrite the file"


class TestAttestationLiveness:
    """A3: the attestation follows page liveness."""

    @pytest.mark.p0
    def test_reload_drops_and_rebuilds_connection(self, mcp_server_dangerous):
        """A3: a browser reload must not leave the old page counted.

        The durable evidence is that the connection count never grows past the
        live page (the old code reached 2 and kept the old ``connectedAt``) and
        that the rebuilt page carries a fresh ``connectedAt``. The disconnected
        transient itself can be shorter than the sampling interval of a fast
        reload, so it is recorded but not required here; the killed-tab test
        below asserts the disconnected end state deterministically.
        """
        url = mcp_server_dangerous["url"]
        page = mcp_server_dangerous["page"]

        before = _attestation(url)
        assert before and before["connected"] is True, before
        old_connected_at = before["connectedAt"]

        samples = []
        page.reload(wait_until="domcontentloaded")

        deadline = time.time() + 60
        saw_disconnected = False
        rebuilt = False
        while time.time() < deadline:
            current = _attestation(url)
            if current is not None:
                samples.append(current)
                if current.get("connected") is False:
                    saw_disconnected = True
                if current.get("connected") is True and current.get(
                    "connectedAt"
                ) not in (None, old_connected_at):
                    rebuilt = True
                    break
            time.sleep(0.2)

        page.wait_for_selector(".jp-NotebookPanel:not(.lm-mod-hidden)", timeout=120000)
        final = samples[-1] if samples else None
        max_count = (
            max((s.get("connectionCount") or 0) for s in samples) if samples else 0
        )

        assert (
            rebuilt
        ), f"reload never rebuilt the connection with a fresh connectedAt -> {final}"
        assert max_count <= 1, (
            "the dead page kept counting after the reload (old-code signature): "
            f"max connectionCount={max_count}, samples={samples[:8]}"
        )
        assert final and final["connected"] is True, final
        assert final["connectionCount"] == 1, final
        assert (
            final["connectedAt"] != old_connected_at
        ), "the rebuilt connection must carry a fresh connectedAt"
        # Informational: a slow reload exposes the disconnected transient.
        print(f"reload: saw_disconnected={saw_disconnected}, samples={len(samples)}")

    @pytest.mark.p1
    def test_killed_tab_expires_via_heartbeat_timeout(self, mcp_server_dangerous):
        """A3 (hard case): a page that dies silently expires by liveness timeout."""
        url = mcp_server_dangerous["url"]
        page = mcp_server_dangerous["page"]

        before = _attestation(url)
        assert before and before["connected"] is True, before

        # A hard close does not run beforeunload/pagehide handlers.
        page.close(run_before_unload=False)

        final = None
        deadline = time.time() + 45
        while time.time() < deadline:
            current = _attestation(url)
            if current is not None:
                final = current
                if current.get("connected") is False:
                    break
            time.sleep(2)

        assert final is not None and final["connected"] is False, (
            "a killed page kept the attestation connected: " f"{final}"
        )
        assert final["connectionCount"] == 0, final
