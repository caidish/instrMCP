"""Unit tests for instrmcp.app.profiles."""

import pytest

from instrmcp.app.profiles import (
    McpCfg,
    Profile,
    _deep_merge,
    list_profiles,
    load_profile,
    validate_profile,
)


def test_load_default_profile():
    p = load_profile()
    assert p.name == "default"
    assert p.mcp.port == 8123
    assert p.jupyter.port == 8888
    assert p.supervisor_port == 8124
    assert p.mcp.mode == "safe"
    assert p.mcp.autostart is True


def test_load_named_default_explicit():
    assert load_profile("default").name == "default"


def test_load_missing_profile_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_profile("does-not-exist-xyz")


def test_list_profiles_includes_bundled_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    names = [i.name for i in list_profiles()]
    assert "default" in names


def test_deep_merge():
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    over = {"nested": {"y": 3, "z": 4}, "b": 5}
    assert _deep_merge(base, over) == {
        "a": 1,
        "b": 5,
        "nested": {"x": 1, "y": 3, "z": 4},
    }


def test_project_profile_override(tmp_path, monkeypatch):
    proj = tmp_path / ".instrmcp" / "profiles"
    proj.mkdir(parents=True)
    (proj / "lab.yaml").write_text("mcp:\n  port: 9999\n")
    monkeypatch.chdir(tmp_path)
    p = load_profile("lab")
    assert p.mcp.port == 9999  # overridden
    assert p.jupyter.port == 8888  # inherited from bundled default
    assert p.name == "lab"


def test_validate_port_collision():
    p = Profile(mcp=McpCfg(port=8888))  # collides with jupyter.port 8888
    errs = validate_profile(p)
    assert any("Port 8888" in e for e in errs)


def test_validate_unknown_option():
    p = Profile(mcp=McpCfg(options=["bogus"]))
    assert any("Unknown MCP option" in e for e in validate_profile(p))


def test_validate_dynamictool_requires_dangerous():
    p = Profile(mcp=McpCfg(options=["dynamictool"], mode="safe"))
    assert any("dangerous" in e for e in validate_profile(p))


def test_validate_clean_default():
    assert validate_profile(load_profile()) == []


def test_load_bundled_demo_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no project/user profiles in play
    p = load_profile("demo")
    assert p.name == "demo"
    assert p.measureit.enabled is True
    assert "measureit" in p.mcp.options
    assert p.jupyter.port == 8888  # inherited from bundled default


def test_list_includes_bundled_demo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    names = [i.name for i in list_profiles()]
    assert "default" in names
    assert "demo" in names
