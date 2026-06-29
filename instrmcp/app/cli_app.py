"""argparse wiring + handlers for the InstrMCP App subcommands.

Kept separate from :mod:`instrmcp.cli` so the main CLI stays a thin registrar.
Milestone 1 implements: ``launch``, ``doctor``, ``status``, ``stop``, ``profiles``,
``install-kernel``, ``uninstall-kernel``. ``restart`` and ``logs`` (which talk to the
live supervisor API) arrive in Milestone 2.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

# Commands handled by this module (used by cli.main dispatch).
APP_COMMANDS = {
    "launch",
    "app",
    "doctor",
    "status",
    "stop",
    "restart",
    "logs",
    "profiles",
    "install-kernel",
    "uninstall-kernel",
}


def setup_app_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Register the App subcommands on the main CLI's subparsers."""
    # launch
    p = subparsers.add_parser("launch", help="Launch instrmcp (JupyterLab + MCP)")
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument("--no-browser", action="store_true", help="Do not open a browser")
    p.add_argument(
        "--force", action="store_true", help="Launch even if doctor reports failures"
    )

    # app (Streamlit control panel)
    p = subparsers.add_parser(
        "app", help="Open the Streamlit control panel (requires instrmcp[gui])"
    )
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument(
        "--port", type=int, default=8501, help="Streamlit port (default 8501)"
    )

    # doctor
    p = subparsers.add_parser("doctor", help="Run environment/readiness diagnostics")
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # status
    p = subparsers.add_parser("status", help="Show launcher/runtime status")
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument("--json", action="store_true", dest="as_json", help="JSON output")

    # stop
    p = subparsers.add_parser("stop", help="Stop a running launcher")
    p.add_argument("--profile", default="default", help="Profile name")

    # restart
    p = subparsers.add_parser("restart", help="Restart a runtime component")
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument(
        "--component",
        choices=["kernel", "mcp", "all"],
        default="kernel",
        help="Component to restart (default: kernel)",
    )

    # logs
    p = subparsers.add_parser("logs", help="Show launcher/JupyterLab logs")
    p.add_argument("--profile", default="default", help="Profile name")
    p.add_argument("--component", default=None, help="Filter by component")
    p.add_argument(
        "--lines", type=int, default=200, help="Number of lines (default 200)"
    )
    p.add_argument("--follow", action="store_true", help="Stream new log lines")

    # profiles
    pp = subparsers.add_parser("profiles", help="Inspect available profiles")
    pps = pp.add_subparsers(dest="profiles_command", help="Profiles commands")
    pps.add_parser("list", help="List discoverable profiles")
    show = pps.add_parser("show", help="Show a resolved profile")
    show.add_argument("name", nargs="?", default="default", help="Profile name")
    path = pps.add_parser("path", help="Show the file a profile resolves to")
    path.add_argument("name", nargs="?", default="default", help="Profile name")

    # install-kernel / uninstall-kernel
    p = subparsers.add_parser(
        "install-kernel", help="Install the auto-loading 'instrmcp' kernelspec"
    )
    p.add_argument("--profile", default="default", help="Profile name")
    p = subparsers.add_parser(
        "uninstall-kernel", help="Remove the 'instrmcp' kernelspec"
    )
    p.add_argument("--profile", default="default", help="Profile name")


def handle_app_command(args: argparse.Namespace) -> int:
    """Dispatch an App subcommand. Returns a process exit code."""
    if args.command == "launch":
        return _handle_launch(args)
    if args.command == "app":
        return _handle_app(args)
    if args.command == "doctor":
        return _handle_doctor(args)
    if args.command == "status":
        return _handle_status(args)
    if args.command == "stop":
        return _handle_stop(args)
    if args.command == "restart":
        return _handle_restart(args)
    if args.command == "logs":
        return _handle_logs(args)
    if args.command == "profiles":
        return _handle_profiles(args)
    if args.command == "install-kernel":
        return _handle_install_kernel(args)
    if args.command == "uninstall-kernel":
        return _handle_uninstall_kernel(args)
    return 1


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _handle_launch(args: argparse.Namespace) -> int:
    from instrmcp.app.launcher import run_launch

    return run_launch(
        profile_name=args.profile,
        no_browser=args.no_browser,
        force=args.force,
    )


def _handle_app(args: argparse.Namespace) -> int:
    import importlib.util
    import subprocess
    import sys
    from pathlib import Path

    if importlib.util.find_spec("streamlit") is None:
        print("The InstrMCP app needs Streamlit, which is not installed.")
        print("Install the GUI extra:")
        print("    pip install 'instrmcp[gui]'")
        print("or directly:")
        print("    pip install streamlit")
        return 1

    app_path = Path(__file__).parent / "streamlit_app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(args.port),
        "--",
        "--profile",
        args.profile,
    ]
    print(
        f"Opening InstrMCP app on http://localhost:{args.port} (profile: {args.profile})"
    )

    import signal

    # Make `kill <pid>` (SIGTERM) unwind like Ctrl+C so the warning below still runs.
    def _on_term(signum, frame):
        raise KeyboardInterrupt

    old_term = signal.signal(signal.SIGTERM, _on_term)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        return 0
    finally:
        signal.signal(signal.SIGTERM, old_term)
        _warn_if_backend_running(args.profile)


def _warn_if_backend_running(profile_name: str) -> None:
    """After the app exits, warn if the supervisor + JupyterLab are still running.

    The app spawns the supervisor detached (so closing the GUI doesn't kill a running
    experiment), so it outlives the app. Remind the user how to stop it.
    """
    base, _info = _live_api(profile_name)
    if base is None:
        return
    print()
    print("⚠️  The InstrMCP app closed, but JupyterLab + the supervisor are still")
    print("    running in the background (your experiment is not interrupted).")
    print("    To stop them and free the ports, run:")
    print(f"        instrmcp stop --profile {profile_name}")


def _handle_doctor(args: argparse.Namespace) -> int:
    from instrmcp.app.doctor import run_doctor_sync
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    report = run_doctor_sync(profile)
    if args.as_json:
        print(report.model_dump_json(indent=2))
    else:
        print(report.render())
    return 0 if report.ok else 1


# -- live supervisor API helpers --------------------------------------------


def _live_api(profile_name: str):
    """Return ``(base_url, info)`` if a supervisor is live, else ``(None, info)``."""
    from instrmcp.app import runfile

    info = runfile.read_run_file(profile_name)
    if (
        info
        and runfile.process_alive(info.get("pid", -1))
        and info.get("supervisor_port")
    ):
        return f"http://127.0.0.1:{info['supervisor_port']}", info
    return None, info


def _print_status(data: dict) -> None:
    print(f"Profile:    {data.get('profile')}")
    print(f"State:      {data.get('aggregate')}")
    for name, c in (data.get("components") or {}).items():
        detail = c.get("detail", "")
        print(f"  {name:10s} {c.get('state'):9s} {detail}")
    if data.get("jupyter_url"):
        print(f"JupyterLab: {data['jupyter_url']}")
    mcp = data.get("mcp") or {}
    print(f"MCP:        {mcp.get('host')}:{mcp.get('port')} (mode {mcp.get('mode')})")


def _handle_status(args: argparse.Namespace) -> int:
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    base, info = _live_api(profile.name)
    if base:
        try:
            import httpx

            data = httpx.get(f"{base}/status", timeout=10.0).json()
            if args.as_json:
                print(json.dumps(data, indent=2))
            else:
                _print_status(data)
            return 0
        except Exception:
            pass  # fall through to offline view

    # Offline view (no live supervisor): probe MCP directly.
    from instrmcp.utils.stdio_proxy import check_http_mcp_server

    mcp_up = asyncio.run(check_http_mcp_server(profile.mcp.host, profile.mcp.port))
    status = {
        "profile": profile.name,
        "launcher_running": False,
        "mcp_reachable": mcp_up,
        "run_file": info,
    }
    if args.as_json:
        print(json.dumps(status, indent=2))
        return 0
    print(f"Profile:          {profile.name}")
    print("Launcher running: no")
    print(
        f"MCP reachable:    {'yes' if mcp_up else 'no'} "
        f"({profile.mcp.host}:{profile.mcp.port})"
    )
    return 0


def _handle_stop(args: argparse.Namespace) -> int:
    from instrmcp.app import runfile
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    base, info = _live_api(profile.name)
    if not info:
        print(f"No running launcher found for profile '{profile.name}'.")
        return 0

    pid = info.get("pid", -1)
    if not runfile.process_alive(pid):
        print("Launcher process is not alive; cleaning up run file.")
        runfile.remove_run_file(profile.name)
        return 0

    # Prefer a graceful API stop; fall back to SIGTERM.
    if base:
        try:
            import httpx

            httpx.post(f"{base}/stop", timeout=10.0)
        except Exception:
            runfile.terminate_process(pid)
    else:
        runfile.terminate_process(pid)

    print(f"Stopping launcher (pid {pid})...")
    for _ in range(50):
        if not runfile.process_alive(pid):
            break
        time.sleep(0.1)
    runfile.remove_run_file(profile.name)
    print("Stopped." if not runfile.process_alive(pid) else "Still exiting.")
    return 0


def _handle_restart(args: argparse.Namespace) -> int:
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    base, _info = _live_api(profile.name)
    if not base:
        print(f"No running launcher for profile '{profile.name}'. Start it first.")
        return 1

    import httpx

    component = args.component
    try:
        if component in ("kernel", "all"):
            r = httpx.post(f"{base}/restart-kernel", timeout=20.0)
            data = r.json()
            if data.get("ok"):
                print(f"Kernel(s) restarted: {data.get('restarted')}")
            else:
                print(f"Kernel restart: {data.get('message')}")
        if component in ("mcp", "all"):
            r = httpx.post(f"{base}/restart-mcp", timeout=10.0)
            print(f"MCP restart: {r.json().get('message')}")
    except Exception as e:
        print(f"Error contacting supervisor: {e}")
        return 1
    return 0


def _handle_logs(args: argparse.Namespace) -> int:
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    base, _info = _live_api(profile.name)
    if not base:
        print(f"No running launcher for profile '{profile.name}'.")
        return 1

    import httpx

    def _fetch(lines: int) -> list:
        params = {"lines": lines}
        if args.component:
            params["component"] = args.component
        return (
            httpx.get(f"{base}/logs", params=params, timeout=10.0)
            .json()
            .get("logs", [])
        )

    def _emit(records: list) -> None:
        for rec in records:
            print(f"[{rec['component']}] {rec['line']}")

    if not args.follow:
        _emit(_fetch(args.lines))
        return 0

    seen_ts = 0.0
    try:
        records = _fetch(args.lines)
        _emit(records)
        if records:
            seen_ts = records[-1]["ts"]
        while True:
            time.sleep(1.0)
            new = [r for r in _fetch(500) if r["ts"] > seen_ts]
            if new:
                _emit(new)
                seen_ts = new[-1]["ts"]
    except KeyboardInterrupt:
        return 0


def _handle_profiles(args: argparse.Namespace) -> int:
    from instrmcp.app.profiles import list_profiles, load_profile, profile_search_paths

    cmd = getattr(args, "profiles_command", None)
    if cmd == "list" or cmd is None:
        for info in list_profiles():
            print(f"  {info.name:20s} [{info.source}]  {info.path}")
        return 0

    if cmd == "show":
        try:
            profile = load_profile(args.name)
        except (FileNotFoundError, ValueError) as e:
            print(f"Error: {e}")
            return 1
        try:
            import yaml

            print(yaml.safe_dump(profile.model_dump(), sort_keys=False))
        except ImportError:
            print(json.dumps(profile.model_dump(), indent=2))
        return 0

    if cmd == "path":
        for path, source in profile_search_paths(args.name):
            if path.exists():
                print(f"{path} [{source}]")
                return 0
        if args.name == "default":
            print("<bundled>")
            return 0
        print(f"Profile '{args.name}' not found.")
        return 1

    return 1


def _handle_install_kernel(args: argparse.Namespace) -> int:
    from instrmcp.app.install_kernel import install_kernel
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    resource_dir = install_kernel(profile)
    print(f"Installed kernelspec '{profile.jupyter.kernel_name}' at:\n  {resource_dir}")
    print(
        f"  mode={profile.mcp.mode} options={sorted(profile.mcp.options)} "
        f"autostart={profile.mcp.autostart}"
    )
    return 0


def _handle_uninstall_kernel(args: argparse.Namespace) -> int:
    from instrmcp.app.install_kernel import uninstall_kernel
    from instrmcp.app.profiles import load_profile

    try:
        profile = load_profile(args.profile)
        kernel_name = profile.jupyter.kernel_name
    except (FileNotFoundError, ValueError):
        kernel_name = "instrmcp"

    removed = uninstall_kernel(kernel_name)
    print(
        f"Removed kernelspec '{kernel_name}'."
        if removed
        else f"No kernelspec '{kernel_name}' was installed."
    )
    return 0
