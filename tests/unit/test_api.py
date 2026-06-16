"""Unit tests for instrmcp.app.api (Starlette routes) using a fake supervisor."""

import pytest
from starlette.testclient import TestClient

from instrmcp.app.api import create_app
from instrmcp.app.logs import LogStore


class FakeSupervisor:
    def __init__(self):
        self.logs = LogStore()
        self.measureit_status = None
        self.stop_requested = False
        self.kernel_restarted = False

        class _P:
            name = "default"

            class measureit:
                enabled = False

            class mcp:
                host = "127.0.0.1"
                port = 8123
                mode = "safe"

        self.profile = _P()

    def snapshot(self):
        return {"profile": "default", "aggregate": "ready", "components": {}}

    def request_stop(self):
        self.stop_requested = True

    async def restart_kernel(self):
        self.kernel_restarted = True
        return {"ok": True, "restarted": ["abc"]}


@pytest.fixture
def client():
    sup = FakeSupervisor()
    sup.logs.append("jupyter", "hello world")
    app = create_app(sup)
    app.state.sup = sup
    return TestClient(app), sup


def test_status_endpoint(client):
    c, _ = client
    r = c.get("/status")
    assert r.status_code == 200
    assert r.json()["aggregate"] == "ready"


def test_logs_endpoint(client):
    c, _ = client
    r = c.get("/logs")
    assert r.status_code == 200
    body = r.json()
    assert "jupyter" in body["components"]
    assert any("hello world" in rec["line"] for rec in body["logs"])


def test_stop_endpoint_requests_stop(client):
    c, sup = client
    r = c.post("/stop")
    assert r.status_code == 202
    assert sup.stop_requested is True


def test_restart_kernel_endpoint(client):
    c, sup = client
    r = c.post("/restart-kernel")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert sup.kernel_restarted is True


def test_restart_mcp_is_advisory(client):
    c, _ = client
    r = c.post("/restart-mcp")
    assert r.status_code == 202
    assert r.json()["advisory"] is True


def test_measureit_endpoint(client):
    c, _ = client
    r = c.get("/measureit")
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_events_ws_initial_snapshot(client):
    c, _ = client
    with c.websocket_connect("/events") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "status"
        assert msg["status"]["aggregate"] == "ready"
