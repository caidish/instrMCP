"""Unit tests for instrmcp.app.components and instrmcp.app.supervisor (poll logic)."""

import asyncio

from instrmcp.app import supervisor as sup_mod
from instrmcp.app.components import Component, ComponentState, aggregate_state
from instrmcp.app.profiles import Profile
from instrmcp.app.supervisor import Supervisor


class FakeProc:
    def __init__(self, returncode=None, pid=4321):
        self.returncode = returncode
        self.pid = pid


# -- aggregate_state ---------------------------------------------------------


def test_aggregate_ready():
    comps = {"a": Component("a"), "b": Component("b", observed=True)}
    comps["a"].set(ComponentState.READY)
    comps["b"].set(ComponentState.READY)
    assert aggregate_state(comps) == ComponentState.READY


def test_aggregate_spawned_error_is_error():
    comps = {"a": Component("a")}
    comps["a"].set(ComponentState.ERROR)
    assert aggregate_state(comps) == ComponentState.ERROR


def test_aggregate_observed_error_is_degraded_not_error():
    comps = {"mcp": Component("mcp", observed=True)}
    comps["mcp"].set(ComponentState.ERROR)
    assert aggregate_state(comps) == ComponentState.DEGRADED


def test_aggregate_starting():
    comps = {"a": Component("a"), "b": Component("b", observed=True)}
    comps["a"].set(ComponentState.STARTING)
    comps["b"].set(ComponentState.READY)
    assert aggregate_state(comps) == ComponentState.STARTING


# -- Supervisor poll logic ---------------------------------------------------


def test_poll_jupyter_transitions():
    s = Supervisor(Profile())
    s._jupyter_proc = FakeProc(returncode=None, pid=99)
    s.jupyter_url = None
    s._poll_jupyter()
    assert s.components["jupyter"].state == ComponentState.STARTING

    s.jupyter_url = "http://127.0.0.1:8888/lab?token=x"
    s._poll_jupyter()
    assert s.components["jupyter"].state == ComponentState.READY

    s._jupyter_proc = FakeProc(returncode=1)
    s._poll_jupyter()
    assert s.components["jupyter"].state == ComponentState.ERROR


def test_poll_mcp_up_then_down(monkeypatch):
    s = Supervisor(Profile())

    async def up(host="127.0.0.1", port=8123):
        return True

    monkeypatch.setattr(sup_mod, "check_http_mcp_server", up)
    asyncio.run(s._poll_mcp())
    assert s.components["mcp"].state == ComponentState.READY

    async def down(host="127.0.0.1", port=8123):
        return False

    monkeypatch.setattr(sup_mod, "check_http_mcp_server", down)
    asyncio.run(s._poll_mcp())
    assert s.components["mcp"].state == ComponentState.DEGRADED


def test_poll_mcp_waiting_when_never_up(monkeypatch):
    s = Supervisor(Profile())

    async def down(host="127.0.0.1", port=8123):
        return False

    monkeypatch.setattr(sup_mod, "check_http_mcp_server", down)
    asyncio.run(s._poll_mcp())
    # Never been ready -> waiting (STARTING), not DEGRADED.
    assert s.components["mcp"].state == ComponentState.STARTING


def test_snapshot_shape():
    s = Supervisor(Profile())
    snap = s.snapshot()
    assert snap["profile"] == "default"
    assert "jupyter" in snap["components"]
    assert "mcp" in snap["components"]
    assert snap["mcp"]["port"] == 8123
    assert snap["measureit"]["enabled"] is False
