"""InstrMCP Streamlit control panel.

A user-friendly GUI over the supervisor: pick a profile, launch JupyterLab + the
supervisor, watch live status/logs/MeasureIt, run diagnostics, and recover — all
without the terminal.

Design note: this is a *control panel + monitor*. The MCP server is hosted inside the
notebook kernel, so it is started with the one-click **Start** button in the InstrMCP
notebook toolbar (safe mode), not from here. This app launches/monitors JupyterLab and
the supervisor and shows when MCP comes up.

Run via ``instrmcp app`` (which calls ``streamlit run`` on this file).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

import httpx
import streamlit as st

from instrmcp.app import runfile
from instrmcp.app.doctor import run_doctor_sync
from instrmcp.app.profiles import list_profiles, load_profile

REQUEST_TIMEOUT = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="default")
    # Ignore Streamlit's own args.
    args, _ = parser.parse_known_args()
    return args


def _supervisor_base(profile_name: str):
    """Return (base_url, info) if a supervisor for the profile is live, else (None, info)."""
    info = runfile.read_run_file(profile_name)
    if (
        info
        and runfile.process_alive(info.get("pid", -1))
        and info.get("supervisor_port")
    ):
        return f"http://127.0.0.1:{info['supervisor_port']}", info
    return None, info


def _get(base: str, path: str, **params):
    return httpx.get(f"{base}{path}", params=params or None, timeout=REQUEST_TIMEOUT)


def _post(base: str, path: str):
    return httpx.post(f"{base}{path}", timeout=REQUEST_TIMEOUT)


def _launch_supervisor(profile_name: str) -> None:
    """Spawn `instrmcp launch` as a detached background process."""
    log_dir = runfile.RUN_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{profile_name}.gui.log"
    with open(log_path, "ab") as log:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "instrmcp.cli",
                "launch",
                "--profile",
                profile_name,
                "--no-browser",
                "--force",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


_STATE_COLOR = {
    "ready": "🟢",
    "starting": "🟡",
    "degraded": "🟠",
    "error": "🔴",
    "stopped": "⚪",
    "idle": "⚪",
}


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------


def main() -> None:
    args = _parse_args()
    st.set_page_config(page_title="InstrMCP", page_icon="🔬", layout="wide")

    st.title("🔬 InstrMCP")

    # Sidebar: profile selection.
    profile_names = [p.name for p in list_profiles()]
    default_idx = (
        profile_names.index(args.profile) if args.profile in profile_names else 0
    )
    profile_name = st.sidebar.selectbox("Profile", profile_names, index=default_idx)

    try:
        profile = load_profile(profile_name)
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to load profile '{profile_name}': {e}")
        return

    base, info = _supervisor_base(profile_name)

    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"MCP target: {profile.mcp.host}:{profile.mcp.port} · mode {profile.mcp.mode}"
    )
    st.sidebar.caption(f"Supervisor port: {profile.supervisor_port}")

    # Not running: offer launch + doctor.
    if base is None:
        st.warning("The launcher is not running for this profile.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "🚀 Launch instrmcp", type="primary", use_container_width=True
            ):
                _launch_supervisor(profile_name)
                st.info("Launching JupyterLab + supervisor… this page will refresh.")
                time.sleep(2.5)
                st.rerun()
        with col2:
            if st.button("🩺 Run Doctor", use_container_width=True):
                st.session_state["_doctor"] = run_doctor_sync(profile).model_dump()
        _render_doctor()
        _render_help()
        return

    # Running: live panels.
    top = st.columns([1, 1, 1, 1])
    with top[0]:
        if st.button("🩺 Doctor", use_container_width=True):
            try:
                st.session_state["_doctor"] = _get(base, "/doctor").json()
            except Exception:  # noqa: BLE001
                st.session_state["_doctor"] = run_doctor_sync(profile).model_dump()
    with top[1]:
        if st.button("🔄 Restart kernel", use_container_width=True):
            try:
                st.toast(
                    _post(base, "/restart-kernel").json().get("message", "requested")
                )
            except Exception as e:  # noqa: BLE001
                st.toast(f"failed: {e}")
    with top[2]:
        if st.button("ℹ️ Restart MCP", use_container_width=True):
            st.info(_post(base, "/restart-mcp").json().get("message", ""))
    with top[3]:
        if st.button("🛑 Stop", use_container_width=True):
            try:
                _post(base, "/stop")
            except Exception:  # noqa: BLE001
                pass
            st.info("Stop requested.")
            time.sleep(2)
            st.rerun()

    _render_status(base)
    _render_help(compact=True)
    _render_logs(base)
    _render_doctor()


@st.fragment(run_every=2.0)
def _render_status(base: str) -> None:
    try:
        data = _get(base, "/status").json()
    except Exception:  # noqa: BLE001
        st.warning("Launcher stopped or unreachable. Refresh the page.")
        return

    agg = (data.get("aggregate") or "idle").lower()
    st.subheader(f"{_STATE_COLOR.get(agg, '⚪')} Overall: {agg}")

    comps = data.get("components") or {}
    cols = st.columns(max(len(comps), 1))
    for col, (name, c) in zip(cols, comps.items()):
        state = (c.get("state") or "idle").lower()
        col.metric(name.capitalize(), state)
        col.caption(c.get("detail", ""))

    url = data.get("jupyter_url")
    if url:
        st.link_button("🔗 Open JupyterLab", url)

    # MeasureIt
    m = data.get("measureit") or {}
    if m.get("enabled"):
        status = m.get("status")
        with st.expander(
            "MeasureIt sweeps", expanded=bool(status and status.get("active"))
        ):
            if status and status.get("active"):
                for sname, sw in (status.get("sweeps") or {}).items():
                    prog = sw.get("progress")
                    line = f"**{sname}** — {sw.get('state', '?')}"
                    if prog is not None:
                        line += f" ({round(prog * 100)}%)"
                    st.write(line)
            else:
                st.caption("no active sweeps")


@st.fragment(run_every=3.0)
def _render_logs(base: str) -> None:
    st.subheader("Logs")
    try:
        data = _get(base, "/logs", lines=200).json()
    except Exception:  # noqa: BLE001
        st.caption("logs unavailable")
        return
    lines = [f"[{r['component']}] {r['line']}" for r in data.get("logs", [])]
    st.code("\n".join(lines[-200:]) or "(no logs yet)", language="text")


def _render_doctor() -> None:
    report = st.session_state.get("_doctor")
    if not report:
        return
    st.subheader("Doctor")
    sym = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
    for c in report.get("checks", []):
        line = f"{sym.get(c['status'], '?')} **{c['name']}** — {c['detail']}"
        st.write(line)
        if c.get("fix") and c["status"] != "ok":
            st.caption(f"fix: {c['fix']}")


def _render_help(compact: bool = False) -> None:
    with st.expander("How to start the MCP server", expanded=not compact):
        st.markdown("""
1. Click **Open JupyterLab** above (or use the launched browser tab).
2. Open a notebook (any Python 3 kernel — the InstrMCP extension auto-loads).
3. In the notebook **toolbar**, click **Start** in the InstrMCP controls
   (it starts in **safe / read-only** mode by default).
4. This panel will show **MCP → ready** within a couple of seconds.

Safe mode means the model can read instruments and the notebook but cannot
execute code without your explicit consent. Switch modes from the toolbar.
""")


# Streamlit executes this file top-to-bottom on every run/rerun.
main()
