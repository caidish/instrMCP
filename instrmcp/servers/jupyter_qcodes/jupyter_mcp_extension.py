"""
IPython extension entry point for the Jupyter QCoDeS MCP server.

This extension is automatically loaded when installing instrmcp.
Manual loading: %load_ext instrmcp.servers.jupyter_qcodes.jupyter_mcp_extension
"""

import asyncio
import logging
from typing import Optional

from IPython.core.magic import Magics, line_magic, magics_class
from IPython.core.magic_arguments import magic_arguments, parse_argstring, argument

from .mcp_server import JupyterMCPServer
from .active_cell_bridge import register_comm_target

logger = logging.getLogger(__name__)

# Global server instance and mode tracking
_server: Optional[JupyterMCPServer] = None
_server_task: Optional[asyncio.Task] = None
_desired_mode: bool = True  # True = safe, False = unsafe
_server_host: str = "127.0.0.1"  # Default host
_server_port: int = 8123  # Default port

# Global options tracking
_enabled_options: set = set()  # Set of enabled option names


@magics_class
class MCPMagics(Magics):
    """Magic commands for MCP server control."""

    @line_magic
    def mcp_safe(self, line):
        """Switch MCP server to safe mode."""
        global _server, _desired_mode

        _desired_mode = True
        print("🛡️  Mode set to safe")

        if _server and _server.running:
            # Update the running server's mode flag too
            _server.set_safe_mode(True)
            print("⚠️  Server restart required for tool changes to take effect")
            print("   Use: %mcp_restart")
        else:
            print("✅ Mode will take effect when server starts")

    @line_magic
    def mcp_unsafe(self, line):
        """Switch MCP server to unsafe mode."""
        global _server, _desired_mode

        _desired_mode = False
        print("⚠️  Mode set to unsafe")
        print("⚠️  UNSAFE MODE: execute_editing_cell tool will be available")

        if _server and _server.running:
            # Update the running server's mode flag too
            _server.set_safe_mode(False)
            print("⚠️  Server restart required for tool changes to take effect")
            print("   Use: %mcp_restart")
        else:
            print("✅ Mode will take effect when server starts")

    @line_magic
    def mcp_status(self, line):
        """Show MCP server status."""
        global _server, _server_task, _desired_mode

        mode_icon = "🛡️" if _desired_mode else "⚠️"
        mode_name = "safe" if _desired_mode else "unsafe"

        print(f"{mode_icon} MCP Server Status:")
        print(f"   Desired Mode: {mode_name}")

        if _server:
            print(f"   Server Running: {'✅' if _server.running else '❌'}")
            print(f"   Host: {_server.host}:{_server.port}")
            print(
                f"   Task: {'✅ Active' if _server_task and not _server_task.done() else '❌ Inactive'}"
            )

            if not _desired_mode:
                print("   Unsafe tools: execute_editing_cell (when running)")
        else:
            print("   Server Instance: ❌ Not created yet")
            if not _desired_mode:
                print("   Unsafe tools: execute_editing_cell (will be available)")

        # Show available commands based on state
        if not _server or not _server.running:
            print("   Available: %mcp_start")
        else:
            print("   Available: %mcp_close, %mcp_restart")

    @line_magic
    def mcp_start(self, line):
        """Start the MCP server."""
        global _server, _server_task, _desired_mode

        if _server and _server.running:
            print("✅ MCP server already running")
            return

        async def start_server():
            global _server, _server_task
            print("🚀 Starting MCP server...")

            try:
                # Get IPython instance from the shell
                from IPython import get_ipython

                ipython = get_ipython()
                if not ipython:
                    print("❌ Could not get IPython instance")
                    return

                # Create NEW server instance with the desired mode and options
                _server = JupyterMCPServer(
                    ipython, safe_mode=_desired_mode, enabled_options=_enabled_options
                )
                _server_task = asyncio.create_task(_start_server_task())
                await asyncio.sleep(0.1)  # Give it a moment to start

                mode_icon = "🛡️" if _desired_mode else "⚠️"
                mode_name = "safe" if _desired_mode else "unsafe"
                print(f"✅ MCP server started in {mode_icon} {mode_name} mode")

                if not _desired_mode:
                    print("⚠️  UNSAFE MODE: execute_editing_cell tool is available")

            except Exception as e:
                print(f"❌ Failed to start MCP server: {e}")

        # Run start in the current event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(start_server())
        except RuntimeError:
            print("❌ No event loop available for server start")

    @line_magic
    def mcp_close(self, line):
        """Stop the MCP server."""
        global _server, _server_task

        if not _server:
            print("❌ MCP server not initialized")
            return

        if not _server.running:
            print("✅ MCP server already stopped")
            return

        async def stop_server():
            global _server_task
            print("🛑 Stopping MCP server...")

            try:
                # Stop the server
                await _stop_server_task()

                # Cancel the task
                if _server_task and not _server_task.done():
                    _server_task.cancel()
                    try:
                        await _server_task
                    except asyncio.CancelledError:
                        pass

                _server_task = None
                print("✅ MCP server stopped")

            except Exception as e:
                print(f"❌ Failed to stop MCP server: {e}")

        # Run stop in the current event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(stop_server())
        except RuntimeError:
            print("❌ No event loop available for server stop")

    @line_magic
    def mcp_option(self, line):
        """Enable or disable optional MCP features using add/remove subcommands."""
        global _server, _enabled_options

        parts = line.strip().split()
        valid_options = {"measureit", "database", "auto_correct_json"}

        if not parts:
            # Show current options status
            print("🎛️  MCP Options Status:")
            print(
                f"   Enabled options: {', '.join(sorted(_enabled_options)) if _enabled_options else 'None'}"
            )
            print("   Available options:")
            print("   - measureit: Enable MeasureIt template resources")
            print("   - database: Enable database integration tools and resources")
            print(
                "   - auto_correct_json: Enable automatic JSON error correction (experimental)"
            )
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
            changes_made = []
            if subcommand == "add":
                for option in options:
                    if option not in _enabled_options:
                        _enabled_options.add(option)
                        changes_made.append(f"✅ Added: {option}")
                    else:
                        changes_made.append(f"ℹ️  Already enabled: {option}")
            else:  # remove
                for option in options:
                    if option in _enabled_options:
                        _enabled_options.remove(option)
                        changes_made.append(f"❌ Removed: {option}")
                    else:
                        changes_made.append(f"ℹ️  Not enabled: {option}")

            # Show results
            for change in changes_made:
                print(change)

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
            if disable:
                if option_name in _enabled_options:
                    _enabled_options.remove(option_name)
                    print(f"❌ Removed: {option_name}")
                else:
                    print(f"ℹ️  Option '{option_name}' was not enabled")
            else:
                _enabled_options.add(option_name)
                print(f"✅ Added: {option_name}")

        # Update server if running (for all code paths that make changes)
        if subcommand in ["add", "remove"] or (subcommand not in ["list"] and parts):
            if _server and _server.running:
                # Update the server's options
                _server.set_enabled_options(_enabled_options)
                print("⚠️  Server restart required for option changes to take effect")
                print("   Use: %mcp_restart")
            else:
                print("✅ Changes will take effect when server starts")

    @line_magic
    def mcp_restart(self, line):
        """Restart the MCP server to apply mode changes."""
        global _server, _server_task, _desired_mode

        if not _server:
            print("❌ No server to restart. Use %mcp_start instead.")
            return

        async def restart_server():
            global _server, _server_task
            print("🔄 Restarting MCP server...")

            try:
                # Get IPython instance before stopping server
                from IPython import get_ipython

                ipython = get_ipython()
                if not ipython:
                    print("❌ Could not get IPython instance")
                    return

                # Stop current server
                await _stop_server_task()

                # Cancel existing task
                if _server_task and not _server_task.done():
                    _server_task.cancel()
                    try:
                        await _server_task
                    except asyncio.CancelledError:
                        pass

                # Create completely NEW server with desired mode and options
                _server = JupyterMCPServer(
                    ipython, safe_mode=_desired_mode, enabled_options=_enabled_options
                )

                # Start new server
                _server_task = asyncio.create_task(_start_server_task())
                await asyncio.sleep(0.1)  # Give it a moment to start

                mode_icon = "🛡️" if _desired_mode else "⚠️"
                mode_name = "safe" if _desired_mode else "unsafe"
                print(f"✅ MCP server restarted in {mode_icon} {mode_name} mode")

                if not _desired_mode:
                    print("⚠️  UNSAFE MODE: execute_editing_cell tool is now available")

            except Exception as e:
                print(f"❌ Failed to restart MCP server: {e}")

        # Run restart in the current event loop
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(restart_server())
        except RuntimeError:
            print("❌ No event loop available for restart")


def load_ipython_extension(ipython):
    """Load the MCP extension when IPython starts."""
    global _server, _server_task

    try:
        logger.info("Loading Jupyter QCoDeS MCP extension...")

        # Check if we're in a Jupyter environment
        shell_type = ipython.__class__.__name__
        if shell_type != "ZMQInteractiveShell":
            logger.warning(f"MCP extension designed for Jupyter, got {shell_type}")

        # Get or create an event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one for terminal IPython
            logger.info("No event loop found, creating one for terminal IPython")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception as e:
                logger.error(f"Could not create event loop: {e}")
                # Still register magic commands even without event loop
                pass

        # Register comm target for active cell tracking
        register_comm_target()

        # Register magic commands
        magic_instance = MCPMagics(ipython)
        ipython.register_magic_function(magic_instance.mcp_safe, "line", "mcp_safe")
        ipython.register_magic_function(magic_instance.mcp_unsafe, "line", "mcp_unsafe")
        ipython.register_magic_function(magic_instance.mcp_option, "line", "mcp_option")
        ipython.register_magic_function(magic_instance.mcp_status, "line", "mcp_status")
        ipython.register_magic_function(magic_instance.mcp_start, "line", "mcp_start")
        ipython.register_magic_function(magic_instance.mcp_close, "line", "mcp_close")
        ipython.register_magic_function(
            magic_instance.mcp_restart, "line", "mcp_restart"
        )

        # Don't create server instance yet - it will be created when started
        logger.info("Jupyter QCoDeS MCP extension loaded successfully")
        print("✅ QCoDeS MCP extension loaded")
        print("🛡️  Default mode: safe")
        print("📋 Use %mcp_status to check server status")
        print("⚠️  Use %mcp_unsafe to switch to unsafe mode (if needed)")
        print("🚀 Use %mcp_start to start the server")

    except Exception as e:
        logger.error(f"Failed to load MCP extension: {e}")
        print(f"❌ Failed to load QCoDeS MCP extension: {e}")


def unload_ipython_extension(ipython):
    """Unload the MCP extension when IPython shuts down."""
    global _server, _server_task

    try:
        logger.info("Unloading Jupyter QCoDeS MCP extension...")

        if _server_task and not _server_task.done():
            _server_task.cancel()

        if _server:
            # Try to get the event loop to stop the server
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_stop_server_task())
            except RuntimeError:
                # No event loop, can't clean up properly
                logger.warning("No event loop available for cleanup")

        _server = None
        _server_task = None

        logger.info("Jupyter QCoDeS MCP extension unloaded")
        print("🛑 QCoDeS MCP Server stopped")

    except Exception as e:
        logger.error(f"Error unloading MCP extension: {e}")


async def _start_server_task():
    """Start the MCP server in the background."""
    global _server

    if not _server:
        return

    try:
        await _server.start()
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        print(f"❌ MCP server error: {e}")


async def _stop_server_task():
    """Stop the MCP server."""
    global _server

    if _server:
        try:
            await _server.stop()
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")


def get_server() -> Optional[JupyterMCPServer]:
    """Get the current MCP server instance."""
    return _server


def get_server_status() -> dict:
    """Get server status information."""
    global _server, _server_task

    return {
        "server_exists": _server is not None,
        "server_running": _server and _server.running,
        "task_exists": _server_task is not None,
        "task_done": _server_task and _server_task.done(),
        "task_cancelled": _server_task and _server_task.cancelled(),
    }
