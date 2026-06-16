"""Unit tests for instrmcp.app.doctor."""

import pytest

from instrmcp.app import doctor
from instrmcp.app.profiles import McpCfg, Profile


@pytest.fixture(autouse=True)
def _patch_externals(monkeypatch):
    """Isolate doctor from the real environment (kernelspec, ports, MCP)."""
    monkeypatch.setattr(doctor, "kernel_installed", lambda name="instrmcp": True)
    monkeypatch.setattr(
        doctor,
        "installed_kernel_metadata",
        lambda name="instrmcp": {"mode": "safe", "options": [], "autostart": True},
    )

    async def _no_mcp(host="127.0.0.1", port=8123):
        return False

    monkeypatch.setattr(doctor, "check_http_mcp_server", _no_mcp)
    monkeypatch.setattr(doctor, "_port_listening", lambda h, p, timeout=0.5: False)


def test_doctor_healthy_default():
    rep = doctor.run_doctor_sync(Profile())
    assert rep.ok
    names = {c.name for c in rep.checks}
    assert "Python" in names
    assert any(c.name.startswith("kernelspec") for c in rep.checks)


def test_doctor_invalid_profile_fails():
    rep = doctor.run_doctor_sync(Profile(mcp=McpCfg(port=8888)))
    assert not rep.ok
    assert any(
        c.name == "profile validation" and c.status == "fail" for c in rep.checks
    )


def test_doctor_missing_kernelspec_warns_not_fails(monkeypatch):
    # The kernelspec is optional now (toolbar flow works without it), so a missing
    # kernelspec is a warning, not a failure, and must not block launch.
    monkeypatch.setattr(doctor, "kernel_installed", lambda name="instrmcp": False)
    rep = doctor.run_doctor_sync(Profile())
    assert rep.ok  # warnings tolerated
    assert any(
        c.name.startswith("kernelspec") and c.status == "warn" for c in rep.checks
    )


def test_doctor_drift_warns(monkeypatch):
    monkeypatch.setattr(
        doctor,
        "installed_kernel_metadata",
        lambda name="instrmcp": {
            "mode": "dangerous",
            "options": ["measureit"],
            "autostart": True,
        },
    )
    rep = doctor.run_doctor_sync(Profile())  # default is safe / no options
    assert any(c.name == "kernelspec drift" and c.status == "warn" for c in rep.checks)


def test_doctor_render():
    text = doctor.run_doctor_sync(Profile()).render()
    assert "Doctor Check" in text
