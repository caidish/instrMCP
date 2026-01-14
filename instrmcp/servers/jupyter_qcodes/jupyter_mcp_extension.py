"""
IPython extension entry point for the Jupyter QCoDeS MCP server.

This extension is automatically loaded when installing instrmcp.
Manual loading: %load_ext instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension
"""

import asyncio
import time
from typing import Any, Dict, Optional

from IPython.core.magic import Magics, line_magic, magics_class

from .mcp_server import JupyterMCPServer
from .active_cell_bridge import register_comm_target
from instrmcp.utils.logging_config import setup_logging, get_logger

# Initialize unified logging system
setup_logging()
logger = get_logger("comm")

# Global server instance and mode tracking
_server: Optional[JupyterMCPServer] = None
_desired_mode: bool = True  # True = safe, False = unsafe
_dangerous_mode: bool = False  # True = bypass all consent dialogs
_server_host: str = "127.0.0.1"  # Default host
_server_port: int = 8123  # Default port

# Global options tracking
_enabled_options: set = set()  # Set of enabled option names

# Note: We create a fresh comm for each broadcast to avoid stale socket issues

# Toolbar control comms tracking (for safe sends)
import threading

_toolbar_comms: set = set()  # Active toolbar control comms
_toolbar_comms_lock = threading.Lock()  # Lock for thread-safe access to _toolbar_comms


def _safe_comm_send(comm, payload: dict, caller: str = "unknown") -> bool:
    """Safely send a message on a comm, handling closed/disposed/dead kernel state.

    Returns True if send succeeded, False otherwise.
    """
    comm_id = id(comm) if comm else "None"
    msg_type = payload.get("type", "unknown") if payload else "unknown"

    if comm is None:
        logger.debug(f"_safe_comm_send({caller}): comm is None, skipping")
        return False

    closed = getattr(comm, "_closed", False)
    disposed = getattr(comm, "is_disposed", False)
    kernel = getattr(comm, "kernel", None)

    logger.debug(
        f"_safe_comm_send({caller}): comm={comm_id}, "
        f"msg_type={msg_type}, closed={closed}, disposed={disposed}, "
        f"kernel={'present' if kernel else 'None'}"
    )

    # Check if comm is closed or disposed
    if closed or disposed:
        logger.debug(f"_safe_comm_send({caller}): SKIP - closed/disposed")
        with _toolbar_comms_lock:
            _toolbar_comms.discard(comm)
        return False

    # Check if kernel is still present (not torn down)
    if kernel is None:
        logger.debug(f"_safe_comm_send({caller}): SKIP - kernel is None")
        with _toolbar_comms_lock:
            _toolbar_comms.discard(comm)
        return False

    try:
        logger.debug(f"_safe_comm_send({caller}): SENDING...")
        comm.send(payload)
        logger.debug(f"_safe_comm_send({caller}): SENT OK")
        return True
    except Exception as e:
        logger.debug(f"_safe_comm_send({caller}): FAILED - {e}")
        # Remove from tracked comms on any failure
        with _toolbar_comms_lock:
            _toolbar_comms.discard(comm)
        return False


# Single source of truth for available options
# Each option has: description, requires_mode (None = no mode requirement)
VALID_OPTIONS: Dict[str, Dict[str, Any]] = {
    "measureit": {
        "description": "Enable MeasureIt sweep tools",
        "requires_mode": None,
    },
    "database": {
        "description": "Enable database tools",
        "requires_mode": None,
    },
    "dynamictool": {
        "description": "Enable dynamic tool creation (requires dangerous mode)",
        "requires_mode": "dangerous",
    },
    "auto_correct_json": {
        "description": "Auto-correct malformed JSON in dynamic tools",
        "requires_mode": None,
    },
}


def _auto_detect_options() -> Dict[str, bool]:
    """Auto-detect available optional features and return detection results.

    Checks for:
    - measureit: MeasureIt package availability
    - database: QCodes database availability
    - auto_correct_json: Always enabled (built-in feature)

    Returns:
        Dictionary mapping option names to detection status (True if detected)
    """
    import importlib.util

    detected = {}

    # Check for MeasureIt
    try:
        measureit_spec = importlib.util.find_spec("measureit")
        detected["measureit"] = measureit_spec is not None
        if detected["measureit"]:
            logger.debug("Auto-detected: MeasureIt package available")
    except Exception as e:
        logger.debug(f"MeasureIt detection failed: {e}")
        detected["measureit"] = False

    # Check for QCodes database support (lightweight spec check, no blocking import)
    try:
        qcodes_spec = importlib.util.find_spec("qcodes")
        if qcodes_spec is not None:
            # Use spec check instead of import to avoid blocking during extension load
            detected["database"] = (
                importlib.util.find_spec("qcodes.dataset") is not None
            )
            if detected["database"]:
                logger.debug("Auto-detected: QCodes database available")
        else:
            detected["database"] = False
    except Exception as e:
        logger.debug(f"QCodes database detection failed: {e}")
        detected["database"] = False

    # auto_correct_json is always available (built-in feature)
    detected["auto_correct_json"] = True
    logger.debug("Auto-detected: auto_correct_json enabled by default")

    return detected


def _apply_auto_detected_options() -> list:
    """Apply auto-detected options to the global _enabled_options set.

    Returns:
        List of option names that were auto-enabled.
    """
    detected = _auto_detect_options()
    auto_enabled = []

    for option, available in detected.items():
        if available and option not in _enabled_options:
            _enabled_options.add(option)
            auto_enabled.append(option)

    if auto_enabled:
        logger.info(f"Auto-enabled options: {', '.join(auto_enabled)}")

    return auto_enabled


def _get_mode_display() -> Dict[str, str]:
    """Return the current mode name and icon."""
    if _dangerous_mode:
        return {"mode": "dangerous", "icon": "☠️"}
    if _desired_mode:
        return {"mode": "safe", "icon": "🛡️"}
    return {"mode": "unsafe", "icon": "⚠️"}


def _get_current_config() -> dict:
    """Return the current MCP server configuration and state."""
    mode_info = _get_mode_display()
    host = _server.host if _server else _server_host
    port = _server.port if _server else _server_port

    server_running = bool(_server and _server.is_running())

    return {
        "mode": mode_info["mode"],
        "enabled_options": sorted(_enabled_options),
        "available_options": [
            {
                "name": k,
                "description": v["description"],
                "requires_mode": v.get("requires_mode"),
            }
            for k, v in VALID_OPTIONS.items()
        ],
        "dangerous": _dangerous_mode,
        "server_running": server_running,
        "host": host,
        "port": port,
    }


def _do_set_mode(mode: str, announce: bool = False) -> str:
    """Update desired mode flags and broadcast config change."""
    global _desired_mode, _dangerous_mode

    normalized = (mode or "").lower()
    if normalized not in {"safe", "unsafe", "dangerous"}:
        raise ValueError(f"Invalid mode '{mode}'. Must be safe, unsafe, or dangerous.")

    _desired_mode = normalized == "safe"
    _dangerous_mode = normalized == "dangerous"

    # Update running server flags so frontends get accurate state even before restart
    if _server:
        try:
            _server.set_safe_mode(_desired_mode)
            _server.dangerous_mode = _dangerous_mode
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Could not update running server mode: {exc}")

    if announce:
        mode_info = _get_mode_display()
        if mode_info["mode"] == "safe":
            print("🛡️  Mode set to safe")
            if _server and _server.is_running():
                print("⚠️  Server restart required for tool changes to take effect")
                print("   Use: %mcp_restart")
            else:
                print("✅ Mode will take effect when server starts")
        elif mode_info["mode"] == "unsafe":
            print("⚠️  Mode set to unsafe")
            print("⚠️  UNSAFE MODE: execute_editing_cell tool will be available")
            if _server and _server.is_running():
                print("⚠️  Server restart required for tool changes to take effect")
                print("   Use: %mcp_restart")
            else:
                print("✅ Mode will take effect when server starts")
        else:
            print("⚠️⚠️⚠️  DANGEROUS MODE ENABLED  ⚠️⚠️⚠️")
            print("All consent dialogs will be automatically approved!")
            print("This mode bypasses all safety confirmations.")
            if _server and _server.is_running():
                print("⚠️  Server restart required for changes to take effect")
                print("   Use: %mcp_restart")
            else:
                print("✅ Mode will take effect when server starts")

    broadcast_server_status("config_changed", _get_current_config())
    return normalized


def _do_set_option(option: str, enabled: bool, announce: bool = False) -> bool:
    """Enable/disable an option, mirror to running server, and broadcast."""
    option_info = VALID_OPTIONS.get(option)
    if not option_info:
        raise ValueError(
            f"Invalid option '{option}'. Valid options: {', '.join(sorted(VALID_OPTIONS))}"
        )

    # Block enable if mode requirement not met
    requires_mode = option_info.get("requires_mode")
    if enabled and requires_mode:
        current_mode = (
            "dangerous" if _dangerous_mode else ("safe" if _desired_mode else "unsafe")
        )
        if current_mode != requires_mode:
            raise ValueError(
                f"Option '{option}' requires {requires_mode} mode. "
                f"Current mode: {current_mode}. Switch to {requires_mode} mode first."
            )

    changed = False
    if enabled and option not in _enabled_options:
        _enabled_options.add(option)
        changed = True
    elif not enabled and option in _enabled_options:
        _enabled_options.remove(option)
        changed = True

    if changed and _server and _server.is_running():
        try:
            _server.set_enabled_options(_enabled_options)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Could not update running server options: {exc}")

    if changed:
        broadcast_server_status("config_changed", _get_current_config())
        if announce:
            print(f"{'✅ Added' if enabled else '❌ Removed'}: {option}")
    elif announce:
        print(f"ℹ️  Option '{option}' already {'enabled' if enabled else 'disabled'}")

    return changed


def _do_start_server(announce: bool = True) -> None:
    """Start the MCP server and broadcast status.

    This is a synchronous function that uses the thread-isolated server.
    It works from any context, including after %gui qt.
    """
    global _server

    if _server and _server.is_running():
        if announce:
            print("✅ MCP server already running")
        return

    if announce:
        print("🚀 Starting MCP server...")

    try:
        from IPython.core.getipython import get_ipython

        ipython = get_ipython()
        if not ipython:
            if announce:
                print("❌ Could not get IPython instance")
            return

        _server = JupyterMCPServer(
            ipython,
            safe_mode=_desired_mode,
            dangerous_mode=_dangerous_mode,
            enabled_options=_enabled_options,
        )
        _server.start_sync()

        mode_info = _get_mode_display()
        if announce:
            print(
                f"✅ MCP server started in {mode_info['icon']} {mode_info['mode']} mode"
            )
            print(f"   Running on http://{_server.host}:{_server.port}")
            if _dangerous_mode:
                print("⚠️⚠️⚠️  All consent dialogs auto-approved!")
            elif not _desired_mode:
                print("⚠️  UNSAFE MODE: execute_editing_cell tool is available")

        broadcast_server_status("server_ready", _get_current_config())

    except Exception as e:
        if announce:
            print(f"❌ Failed to start MCP server: {e}")
        logger.error(f"Failed to start MCP server: {e}")
        raise


def _do_stop_server(announce: bool = True) -> bool:
    """Stop the MCP server and broadcast status.

    This is a synchronous function that uses the thread-isolated server.
    It works from any context, including after %gui qt.

    Returns:
        True if server stopped successfully, False if timeout or error occurred.
    """
    global _server

    if not _server:
        if announce:
            print("❌ MCP server not initialized")
        return True  # Nothing to stop

    if not _server.is_running():
        if announce:
            print("✅ MCP server already stopped")
        _server = None  # Clean up stale reference
        return True

    if announce:
        print("🛑 Stopping MCP server...")

    try:
        success = _server.stop_sync()

        if success:
            _server = None
            if announce:
                print("✅ MCP server stopped")
            broadcast_server_status("server_stopped", _get_current_config())
            return True
        else:
            # Timeout occurred - server thread still alive
            # Do NOT clear _server or broadcast "stopped" - server is still running!
            if announce:
                print("⚠️  Server stop timed out - server may still be running")
                print("   The server thread did not exit within 5 seconds.")
                print("   Try again or restart the kernel if the issue persists.")
            logger.error("Server stop timed out - thread still alive")
            return False

    except Exception as e:
        if announce:
            print(f"❌ Failed to stop MCP server: {e}")
        logger.error(f"Failed to stop MCP server: {e}")
        raise


def _do_restart_server(announce: bool = True) -> bool:
    """Restart the MCP server and broadcast status updates.

    This is a synchronous function that uses the thread-isolated server.
    It works from any context, including after %gui qt.

    Returns:
        True if restart succeeded, False if stop timed out (cannot restart).
    """
    global _server

    if announce:
        print("🔄 Restarting MCP server...")

    try:
        from IPython.core.getipython import get_ipython

        ipython = get_ipython()
        if not ipython:
            if announce:
                print("❌ Could not get IPython instance")
            return False

        # Stop existing server if running
        if _server and _server.is_running():
            success = _server.stop_sync()
            if not success:
                # Timeout occurred - cannot restart while old server is still running
                if announce:
                    print("⚠️  Cannot restart: previous server did not stop in time")
                    print("   The server thread is still alive on the same port.")
                    print("   Try again or restart the kernel if the issue persists.")
                logger.error("Cannot restart: stop timed out")
                return False
            broadcast_server_status("server_stopped", _get_current_config())

        _server = None

        # Create and start new server
        _server = JupyterMCPServer(
            ipython,
            safe_mode=_desired_mode,
            dangerous_mode=_dangerous_mode,
            enabled_options=_enabled_options,
        )

        _server.start_sync()

        mode_info = _get_mode_display()
        if announce:
            print(
                f"✅ MCP server restarted in {mode_info['icon']} {mode_info['mode']} mode"
            )
            print(f"   Running on http://{_server.host}:{_server.port}")
            if _dangerous_mode:
                print("⚠️⚠️⚠️  All consent dialogs auto-approved!")
            elif not _desired_mode:
                print("⚠️  UNSAFE MODE: execute_editing_cell tool is now available")

        broadcast_server_status("server_ready", _get_current_config())
        return True

    except Exception as e:
        if announce:
            print(f"❌ Failed to restart MCP server: {e}")
        logger.error(f"Failed to restart MCP server: {e}")
        raise


def _handle_toolbar_control(comm, open_msg):
    """Comm handler for toolbar control messages."""
    comm_id = id(comm)
    logger.debug(f"_handle_toolbar_control: NEW comm opened, id={comm_id}")
    with _toolbar_comms_lock:
        logger.debug(f"_toolbar_comms before add: {len(_toolbar_comms)} comms")
        # Track this comm for safe sending
        _toolbar_comms.add(comm)
        logger.debug(f"_toolbar_comms after add: {len(_toolbar_comms)} comms")

    def _send_sync_result(comm_ref, success: bool, error: str = None):
        """Send result after synchronous operation completes."""
        comm_id = id(comm_ref) if comm_ref else "None"
        logger.debug(f"_send_sync_result: comm={comm_id}, success={success}")

        # Check if comm is still tracked (not closed/removed)
        with _toolbar_comms_lock:
            if comm_ref not in _toolbar_comms:
                logger.debug("_send_sync_result: SKIP - comm not in _toolbar_comms")
                return

        # Check if kernel is still present (not torn down)
        if getattr(comm_ref, "kernel", None) is None:
            logger.debug("_send_sync_result: SKIP - kernel is None")
            with _toolbar_comms_lock:
                _toolbar_comms.discard(comm_ref)
            return

        payload = {
            "type": "result",
            "success": success,
            "details": _get_current_config(),
        }
        if error:
            payload["error"] = error

        # _safe_comm_send will handle any remaining errors and discard comm if needed
        _safe_comm_send(comm_ref, payload, caller="_send_sync_result")

    def on_msg(msg):
        data = msg.get("content", {}).get("data", {}) if msg else {}
        msg_type = data.get("type")
        logger.debug(f"on_msg received: {msg_type}")

        if msg_type == "get_status":
            _safe_comm_send(
                comm, {"type": "status", **_get_current_config()}, caller="get_status"
            )
            return

        if msg_type == "start_server":
            logger.debug("on_msg: calling start_server (sync)")
            try:
                _do_start_server(announce=False)
                _send_sync_result(comm, success=True)
            except Exception as e:
                logger.error(f"start_server failed: {e}")
                _send_sync_result(comm, success=False, error=str(e))
            return

        if msg_type == "stop_server":
            logger.debug("on_msg: calling stop_server (sync)")
            try:
                success = _do_stop_server(announce=False)
                if success:
                    _send_sync_result(comm, success=True)
                else:
                    _send_sync_result(
                        comm,
                        success=False,
                        error="Server stop timed out - thread still alive",
                    )
            except Exception as e:
                logger.error(f"stop_server failed: {e}")
                _send_sync_result(comm, success=False, error=str(e))
            return

        if msg_type == "restart_server":
            logger.debug("on_msg: calling restart_server (sync)")
            try:
                success = _do_restart_server(announce=False)
                if success:
                    _send_sync_result(comm, success=True)
                else:
                    _send_sync_result(
                        comm,
                        success=False,
                        error="Cannot restart: previous server did not stop in time",
                    )
            except Exception as e:
                logger.error(f"restart_server failed: {e}")
                _send_sync_result(comm, success=False, error=str(e))
            return

        if msg_type == "set_mode":
            # Reject mode changes when server is running
            if _server and _server.is_running():
                _safe_comm_send(
                    comm,
                    {
                        "type": "result",
                        "success": False,
                        "error": "Cannot change mode while server is running",
                    },
                    caller="set_mode_reject",
                )
                return
            try:
                _do_set_mode(data.get("mode"), announce=False)
                _safe_comm_send(
                    comm,
                    {
                        "type": "result",
                        "success": True,
                        "details": _get_current_config(),
                    },
                    caller="set_mode_ok",
                )
            except Exception as exc:
                _safe_comm_send(
                    comm,
                    {"type": "result", "success": False, "error": str(exc)},
                    caller="set_mode_err",
                )
            return

        if msg_type == "set_option":
            # Reject option changes when server is running
            if _server and _server.is_running():
                _safe_comm_send(
                    comm,
                    {
                        "type": "result",
                        "success": False,
                        "error": "Cannot change options while server is running",
                    },
                    caller="set_option_reject",
                )
                return
            option = data.get("option")
            enabled = bool(data.get("enabled"))
            try:
                changed = _do_set_option(option, enabled, announce=False)
                _safe_comm_send(
                    comm,
                    {
                        "type": "result",
                        "success": True,
                        "changed": changed,
                        "details": _get_current_config(),
                    },
                    caller="set_option_ok",
                )
            except Exception as exc:
                _safe_comm_send(
                    comm,
                    {"type": "result", "success": False, "error": str(exc)},
                    caller="set_option_err",
                )
            return

        _safe_comm_send(
            comm,
            {
                "type": "result",
                "success": False,
                "error": f"Unknown toolbar message type: {msg_type}",
            },
            caller="unknown_msg_type",
        )

    def on_close(msg):
        logger.debug(f"on_close: comm {id(comm)} closed by frontend")
        with _toolbar_comms_lock:
            _toolbar_comms.discard(comm)

    comm.on_msg(on_msg)
    comm.on_close(on_close)


@magics_class
class MCPMagics(Magics):
    """Magic commands for MCP server control."""

    @line_magic
    def mcp_safe(self, line):
        """Switch MCP server to safe mode."""
        _do_set_mode("safe", announce=True)

    @line_magic
    def mcp_unsafe(self, line):
        """Switch MCP server to unsafe mode."""
        _do_set_mode("unsafe", announce=True)

    @line_magic
    def mcp_dangerous(self, line):
        """Switch MCP server to dangerous mode - all operations auto-approved."""
        _do_set_mode("dangerous", announce=True)

    @line_magic
    def mcp_status(self, line):
        """Show MCP server status."""
        if _dangerous_mode:
            mode_icon = "☠️"
            mode_name = "dangerous"
        elif _desired_mode:
            mode_icon = "🛡️"
            mode_name = "safe"
        else:
            mode_icon = "⚠️"
            mode_name = "unsafe"

        print(f"{mode_icon} MCP Server Status:")
        print(f"   Desired Mode: {mode_name}")
        if _dangerous_mode:
            print("   ⚠️  All consent dialogs auto-approved!")

        if _server:
            is_running = _server.is_running()
            print(f"   Server Running: {'✅' if is_running else '❌'}")
            print(f"   Host: {_server.host}:{_server.port}")

            if not _desired_mode:
                print("   Unsafe tools: execute_editing_cell (when running)")
        else:
            print("   Server Instance: ❌ Not created yet")
            if not _desired_mode:
                print("   Unsafe tools: execute_editing_cell (will be available)")

        # Show available commands based on state
        if not _server or not _server.is_running():
            print("   Available: %mcp_start")
        else:
            print("   Available: %mcp_close, %mcp_restart")

    @line_magic
    def mcp_start(self, line):
        """Start the MCP server.

        This uses synchronous server start, which works from any context
        including after %gui qt.
        """
        try:
            _do_start_server(announce=True)
        except Exception as e:
            # Error already printed by _do_start_server
            pass

    @line_magic
    def mcp_close(self, line):
        """Stop the MCP server.

        This uses synchronous server stop, which works from any context
        including after %gui qt.
        """
        try:
            _do_stop_server(announce=True)
        except Exception as e:
            # Error already printed by _do_stop_server
            pass

    @line_magic
    def mcp_option(self, line):
        """Enable or disable optional MCP features using add/remove subcommands."""
        parts = line.strip().split()
        valid_options = set(VALID_OPTIONS.keys())

        if not parts:
            # Show current options status
            print("🎛️  MCP Options Status:")
            print(
                f"   Enabled options: {', '.join(sorted(_enabled_options)) if _enabled_options else 'None'}"
            )
            print("   Available options:")
            for name, info in VALID_OPTIONS.items():
                req = (
                    f" (requires {info['requires_mode']} mode)"
                    if info.get("requires_mode")
                    else ""
                )
                print(f"   - {name}: {info['description']}{req}")
            print()
            print("   Usage:")
            print("   %mcp_option add measureit database    # Add multiple options")
            print("   %mcp_option remove measureit          # Remove single option")
            print("   %mcp_option list                      # Show current status")
            print()
            print("   Legacy syntax (deprecated):")
            print("   %mcp_option measureit                 # Enable single option")
            print("   %mcp_option -measureit                # Disable single option")
            return

        subcommand = parts[0].lower()

        changes_made = False

        if subcommand in ["add", "remove"]:
            # New subcommand style
            if len(parts) < 2:
                print(f"❌ No options specified for '{subcommand}' command")
                print(f"   Usage: %mcp_option {subcommand} <option1> [option2] ...")
                return

            options = parts[1:]

            # Validate all options first
            invalid_options = [opt for opt in options if opt not in valid_options]
            if invalid_options:
                print(f"❌ Invalid options: {', '.join(invalid_options)}")
                print(f"   Valid options: {', '.join(sorted(valid_options))}")
                return

            # Apply changes
            changes_messages = []
            if subcommand == "add":
                for option in options:
                    if _do_set_option(option, True, announce=False):
                        changes_messages.append(f"✅ Added: {option}")
                    else:
                        changes_messages.append(f"ℹ️  Already enabled: {option}")
            else:  # remove
                for option in options:
                    if _do_set_option(option, False, announce=False):
                        changes_messages.append(f"❌ Removed: {option}")
                    else:
                        changes_messages.append(f"ℹ️  Not enabled: {option}")

            # Show results
            for change in changes_messages:
                print(change)
            changes_made = any(
                change.startswith(("✅", "❌")) for change in changes_messages
            )

        elif subcommand == "list":
            # Show status
            print("🎛️  MCP Options Status:")
            print(
                f"   Enabled options: {', '.join(sorted(_enabled_options)) if _enabled_options else 'None'}"
            )
            return

        else:
            # Legacy single-option style (backward compatibility)
            print(
                "⚠️  Legacy syntax detected. Consider using: %mcp_option add/remove <options>"
            )

            option_name = parts[0]
            disable = False

            if option_name.startswith("-"):
                disable = True
                option_name = option_name[1:]

            # Validate option name
            if option_name not in valid_options:
                print(f"❌ Unknown option: {option_name}")
                print(f"   Valid options: {', '.join(sorted(valid_options))}")
                return

            # Enable/disable option
            changes_made = _do_set_option(option_name, not disable, announce=False)
            if changes_made:
                print(f"{'❌ Removed' if disable else '✅ Added'}: {option_name}")
            else:
                print(
                    f"ℹ️  Option '{option_name}' was already "
                    f"{'disabled' if disable else 'enabled'}"
                )

        # Update server if running (for all code paths that make changes)
        if subcommand in ["add", "remove"] or (subcommand not in ["list"] and parts):
            if changes_made:
                if _server and _server.is_running():
                    print(
                        "⚠️  Server restart required for option changes to take effect"
                    )
                    print("   Use: %mcp_restart")
                else:
                    print("✅ Changes will take effect when server starts")
            else:
                print("ℹ️  No option changes applied.")

    @line_magic
    def mcp_restart(self, line):
        """Restart the MCP server to apply mode changes.

        This uses synchronous server restart, which works from any context
        including after %gui qt.
        """
        try:
            _do_restart_server(announce=True)
        except Exception as e:
            # Error already printed by _do_restart_server
            pass


def load_ipython_extension(ipython):
    """Load the MCP extension when IPython starts."""
    try:
        logger.debug("Loading Jupyter QCoDeS MCP extension...")

        # Suppress expected ipykernel.comm errors about missing comm target
        # These are normal before the MCP server starts
        import logging as _logging

        class MCPCommFilter(_logging.Filter):
            """Filter to suppress expected comm target errors before MCP server starts."""

            def filter(self, record):
                # Suppress only the specific error about mcp:active_cell not being registered
                if (
                    record.levelname == "ERROR"
                    and "No such comm target registered: mcp:active_cell"
                    in record.getMessage()
                ):
                    return False  # Don't log this error
                return True  # Log everything else

        ipykernel_comm_logger = _logging.getLogger("ipykernel.comm")
        ipykernel_comm_logger.addFilter(MCPCommFilter())

        # Check if we're in a Jupyter environment
        shell_type = ipython.__class__.__name__
        if shell_type != "ZMQInteractiveShell":
            logger.warning(f"MCP extension designed for Jupyter, got {shell_type}")

        # Get or create an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one for terminal IPython
            logger.debug("No event loop found, creating one for terminal IPython")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception as e:
                logger.error(f"Could not create event loop: {e}")
                # Still register magic commands even without event loop

        # Register comm target for active cell tracking
        register_comm_target()
        try:
            ipython.kernel.comm_manager.register_target(
                "mcp:toolbar_control", _handle_toolbar_control
            )
            logger.debug("Registered comm target 'mcp:toolbar_control'")
        except Exception as e:
            logger.error(f"Failed to register toolbar control comm target: {e}")

        # Auto-detect and enable available optional features
        auto_enabled = _apply_auto_detected_options()

        # Broadcast initial server status (not started yet)
        broadcast_server_status("server_not_started", _get_current_config())

        # Register magic commands
        magic_instance = MCPMagics(ipython)
        ipython.register_magic_function(magic_instance.mcp_safe, "line", "mcp_safe")
        ipython.register_magic_function(magic_instance.mcp_unsafe, "line", "mcp_unsafe")
        ipython.register_magic_function(
            magic_instance.mcp_dangerous, "line", "mcp_dangerous"
        )
        ipython.register_magic_function(magic_instance.mcp_option, "line", "mcp_option")
        ipython.register_magic_function(magic_instance.mcp_status, "line", "mcp_status")
        ipython.register_magic_function(magic_instance.mcp_start, "line", "mcp_start")
        ipython.register_magic_function(magic_instance.mcp_close, "line", "mcp_close")
        ipython.register_magic_function(
            magic_instance.mcp_restart, "line", "mcp_restart"
        )

        # Don't create server instance yet - it will be created when started
        logger.debug("Jupyter QCoDeS MCP extension loaded successfully")
        print("✅ QCoDeS MCP extension loaded")
        print("🛡️  Default mode: safe")
        if auto_enabled:
            print(f"🔍 Auto-enabled: {', '.join(sorted(auto_enabled))}")
        print("📋 Use %mcp_status to check server status")
        print("⚠️  Use %mcp_unsafe to switch to unsafe mode (if needed)")
        print("🚀 Use %mcp_start to start the server")

    except Exception as e:
        logger.error(f"Failed to load MCP extension: {e}")
        print(f"❌ Failed to load QCoDeS MCP extension: {e}")


def unload_ipython_extension(ipython):
    """Unload the MCP extension when IPython shuts down."""
    global _server

    try:
        logger.debug("Unloading Jupyter QCoDeS MCP extension...")

        if _server and _server.is_running():
            # Use sync stop - works from any context
            success = _server.stop_sync()
            if success:
                _server = None
                print("🛑 QCoDeS MCP Server stopped")
            else:
                # Timeout - server thread still running
                # Don't clear _server to avoid duplicate starts
                print("⚠️  Server stop timed out during unload")
                logger.warning("Server stop timed out during extension unload")
        else:
            _server = None
            print("🛑 QCoDeS MCP Server stopped")

        logger.debug("Jupyter QCoDeS MCP extension unloaded")

    except Exception as e:
        logger.error(f"Error unloading MCP extension: {e}")


def get_server() -> Optional[JupyterMCPServer]:
    """Get the current MCP server instance."""
    return _server


def get_server_status() -> dict:
    """Get server status information.

    Returns thread-safe status using the server's is_running() method.
    """
    return {
        "server_exists": _server is not None,
        "server_running": _server is not None and _server.is_running(),
    }


def _do_broadcast_sends(payload: dict, status: str):
    """Actually perform the comm sends.

    This is separated from broadcast_server_status to allow scheduling
    on the IO loop (when running) or direct calling (when not running),
    avoiding deadlocks when called from the main kernel thread.

    Thread-safe: uses _toolbar_comms_lock when accessing _toolbar_comms.
    """
    with _toolbar_comms_lock:
        comms_to_send = list(_toolbar_comms)
    logger.debug(f"_do_broadcast_sends: sending to {len(comms_to_send)} comms")

    for comm in comms_to_send:
        _safe_comm_send(comm, payload, caller=f"broadcast_{status}")


def broadcast_server_status(status: str, details: Optional[dict] = None):
    """Broadcast server status to all connected toolbar frontends.

    Sends through existing toolbar control comms instead of creating new Comms.

    This function handles different execution contexts to avoid deadlocks:
    - If IO loop is running: schedules sends via call_soon_threadsafe
    - If IO loop exists but not running: calls sends directly (sync context)
    - If no IO loop available: skips broadcast with a warning

    This approach is safer than using a daemon thread, as Jupyter comms are
    not thread-safe.
    """
    logger.debug(f"broadcast_server_status: status={status}")

    timestamp = time.time()

    payload_details: Dict[str, Any] = _get_current_config()
    if details:
        payload_details.update(details)

    payload = {
        "type": "status_broadcast",
        "status": status,
        "timestamp": timestamp,
        "details": payload_details,
    }

    # Try to schedule on IO loop to avoid blocking the main kernel thread
    # This prevents deadlocks when called from magic commands like %mcp_close
    loop = None

    # First, try to get a running loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this context, try to get the event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

    # Schedule on the loop if available and not closed
    if loop is not None and not loop.is_closed():
        if loop.is_running():
            try:
                # Use thread-safe method since we might be called from any thread
                loop.call_soon_threadsafe(_do_broadcast_sends, payload, status)
                logger.debug(f"broadcast_server_status: scheduled thread-safe on loop")
                return
            except RuntimeError as e:
                # Loop was closed between our check and the call
                logger.warning(
                    f"broadcast_server_status: loop closed during scheduling: {e}"
                )
        else:
            # Loop exists but not running - call directly since call_soon would never execute
            # This is safe because we're in the same thread context (no async contention)
            logger.debug(f"broadcast_server_status: loop not running, calling directly")
            _do_broadcast_sends(payload, status)
            return

    # No usable loop available - log and skip
    # We intentionally skip rather than use a daemon thread because:
    # 1. Jupyter comms are not thread-safe
    # 2. A missed broadcast is recoverable (frontend can poll status)
    # 3. Using a thread could cause hangs or dropped messages
    logger.warning(
        f"broadcast_server_status: no running event loop available, "
        f"skipping broadcast for status={status}"
    )
