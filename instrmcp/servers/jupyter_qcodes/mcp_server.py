"""
FastMCP server implementation for Jupyter QCoDeS integration.

This server provides read-only access to QCoDeS instruments and
Jupyter notebook functionality through MCP tools.
"""

import asyncio
import secrets
import sys
import threading
from typing import Dict, Any, Optional

from fastmcp import FastMCP

from .tools import QCodesReadOnlyTools
from .tools_unsafe import UnsafeToolRegistrar
from .registrars import (
    QCodesToolRegistrar,
    NotebookToolRegistrar,
    MeasureItToolRegistrar,
    DatabaseToolRegistrar,
    ResourceRegistrar,
)
from .dynamic_registrar import DynamicToolRegistrar
from instrmcp.logging_config import get_logger

# MeasureIt integration (optional)
try:
    from ...extensions import measureit as measureit_module

    MEASUREIT_AVAILABLE = True
except ImportError:
    measureit_module = None
    MEASUREIT_AVAILABLE = False

# Database integration (optional)
try:
    from ...extensions import database as db_integration

    DATABASE_AVAILABLE = True
except ImportError:
    db_integration = None
    DATABASE_AVAILABLE = False

logger = get_logger("server")


class JupyterMCPServer:
    """MCP server for Jupyter QCoDeS integration."""

    def __init__(
        self,
        ipython,
        host: str = "127.0.0.1",
        port: int = 8123,
        safe_mode: bool = True,
        dangerous_mode: bool = False,
        enabled_options: set = None,
    ):
        self.ipython = ipython
        self.host = host
        self.port = port
        self.safe_mode = safe_mode
        self.dangerous_mode = dangerous_mode
        self.enabled_options = enabled_options or set()
        self.running = False

        # Thread-isolated server state
        self._server_thread: Optional[threading.Thread] = None
        self._server_loop: Optional[asyncio.AbstractEventLoop] = None
        self._uvicorn_server = None
        self._ready_event = threading.Event()
        self._thread_error: Optional[Exception] = None
        self._server_started = False  # Own flag, not dependent on uvicorn internals

        # Generate a random token for basic security
        self.token = secrets.token_urlsafe(32)

        # Initialize tools
        self.tools = QCodesReadOnlyTools(ipython)

        # Create FastMCP server
        server_name = (
            f"Jupyter QCoDeS MCP Server ({'Safe' if safe_mode else 'Unsafe'} Mode)"
        )
        self.mcp = FastMCP(server_name)
        self._register_resources()
        self._register_tools()

        mode_status = "safe" if safe_mode else "unsafe"
        logger.debug(
            f"Jupyter MCP Server initialized on {host}:{port} in {mode_status} mode"
        )

    def _register_resources(self):
        """Register MCP resources using the ResourceRegistrar."""
        resource_registrar = ResourceRegistrar(
            self.mcp,
            self.tools,
            enabled_options=self.enabled_options,
            measureit_module=measureit_module if MEASUREIT_AVAILABLE else None,
            db_module=db_integration if DATABASE_AVAILABLE else None,
        )
        resource_registrar.register_all()

    def _register_tools(self):
        """Register all MCP tools using registrars."""

        # QCodes instrument tools
        qcodes_registrar = QCodesToolRegistrar(self.mcp, self.tools)
        qcodes_registrar.register_all()

        # Notebook tools (read-only)
        notebook_registrar = NotebookToolRegistrar(
            self.mcp,
            self.tools,
            self.ipython,
            safe_mode=self.safe_mode,
            dangerous_mode=self.dangerous_mode,
            enabled_options=self.enabled_options,
        )
        notebook_registrar.register_all()

        # Unsafe mode tools (if enabled)
        # Create consent manager for unsafe tools
        if not self.safe_mode:
            from instrmcp.servers.jupyter_qcodes.security.consent import ConsentManager

            # Use infinite timeout for consent requests
            # User will wait as long as needed to review and approve
            # In dangerous mode, bypass all consent dialogs
            consent_manager_for_unsafe = ConsentManager(
                self.ipython, timeout_seconds=None, bypass_mode=self.dangerous_mode
            )
            unsafe_registrar = UnsafeToolRegistrar(
                self.mcp, self.tools, consent_manager_for_unsafe
            )
            unsafe_registrar.register_all()

        # Optional: MeasureIt tools
        if MEASUREIT_AVAILABLE and "measureit" in self.enabled_options:
            measureit_registrar = MeasureItToolRegistrar(self.mcp, self.tools)
            measureit_registrar.register_all()

        # Optional: Database tools
        if DATABASE_AVAILABLE and "database" in self.enabled_options:
            database_registrar = DatabaseToolRegistrar(
                self.mcp,
                db_integration,
                tools=self.tools,
                safe_mode=self.safe_mode,
            )
            database_registrar.register_all()

        # Dynamic tool creation (meta-tools)
        # Requires dangerous mode AND explicit opt-in via %mcp_option dynamictool
        if self.dangerous_mode and "dynamictool" in self.enabled_options:
            auto_correct_json = "auto_correct_json" in self.enabled_options
            # Consent is enabled by default, can be bypassed via INSTRMCP_CONSENT_BYPASS=1
            # In dangerous mode, bypass all consent dialogs
            require_consent = True
            dynamic_registrar = DynamicToolRegistrar(
                self.mcp,
                self.ipython,
                auto_correct_json=auto_correct_json,
                require_consent=require_consent,
                bypass_consent=self.dangerous_mode,
            )
            dynamic_registrar.register_all()

        # Commented out: Parameter subscription tools (future feature)
        # @self.mcp.tool()
        # async def subscribe_parameter(instrument: str, parameter: str, interval_s: float = 1.0):
        #     """Subscribe to periodic parameter updates."""
        #     pass

        # Commented out: System tools (future feature)
        # @self.mcp.tool()
        # async def get_cache_stats():
        #     """Get parameter cache statistics."""
        #     pass

    def _run_server_in_thread(self):
        """Thread target: runs uvicorn with its own event loop.

        This runs in a dedicated background thread, isolated from IPython's
        main event loop. This allows %gui qt and other event loop changes
        to not affect the HTTP server.
        """
        # Windows: create a selector-based loop for THIS thread only
        # Don't use set_event_loop_policy() - that's process-global and would
        # affect IPython/qasync in the main thread
        if sys.platform == "win32":
            policy = asyncio.WindowsSelectorEventLoopPolicy()
            self._server_loop = policy.new_event_loop()
        else:
            self._server_loop = asyncio.new_event_loop()

        asyncio.set_event_loop(self._server_loop)
        try:
            self._server_loop.run_until_complete(self._async_serve())
        except Exception as e:
            self._thread_error = e
            self._ready_event.set()  # Unblock start_sync even on failure
            logger.error(f"Server thread error: {e}")
        finally:
            self._server_started = False
            try:
                self._server_loop.close()
            except Exception:
                pass
            self._server_loop = None

    async def _async_serve(self):
        """Async server runner within dedicated thread.

        Uses uvicorn.Server.serve() which properly initializes all internal
        state (lifespan, servers, etc.) before starting. We wrap it with
        a startup detection task to signal readiness.
        """
        import uvicorn

        app = self.mcp.http_app()
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=True,
        )
        self._uvicorn_server = uvicorn.Server(config)
        # Threads can't install signal handlers
        self._uvicorn_server.install_signal_handlers = lambda: None

        # Create a task to detect when server is ready
        async def signal_ready():
            # Poll until uvicorn reports started (checks internal state)
            while not self._uvicorn_server.started:
                if self._uvicorn_server.should_exit:
                    return  # Aborted before ready
                await asyncio.sleep(0.05)
            self._server_started = True
            self._ready_event.set()
            logger.debug(f"Uvicorn startup complete on {self.host}:{self.port}")

        # Start readiness monitor as background task
        ready_task = asyncio.create_task(signal_ready())

        try:
            # serve() handles all lifecycle: startup, main_loop, shutdown
            await self._uvicorn_server.serve()
        finally:
            self._server_started = False
            ready_task.cancel()
            try:
                await ready_task
            except asyncio.CancelledError:
                pass

    def start_sync(self):
        """Synchronous start - works from any context (including after %gui qt).

        This is the primary method for starting the server. It creates a
        dedicated background thread for uvicorn, making it immune to event
        loop changes in the main thread.
        """
        if self._server_thread and self._server_thread.is_alive():
            logger.debug("Server thread already running")
            return

        logger.debug(f"Starting Jupyter MCP server on {self.host}:{self.port}")

        # Clear state from previous runs
        self._ready_event.clear()
        self._thread_error = None
        self._uvicorn_server = None
        self._server_started = False

        self._server_thread = threading.Thread(
            target=self._run_server_in_thread, daemon=True, name="MCP-Server"
        )
        self._server_thread.start()

        # Wait for server to be ready (or fail)
        ready = self._ready_event.wait(timeout=5.0)

        # Check for startup failure
        if self._thread_error:
            # Thread failed with error - it should have exited, but ensure cleanup
            self._abort_orphaned_thread()
            raise RuntimeError(f"Server startup failed: {self._thread_error}")

        if not ready:
            # Timeout - thread may still be starting up, could bind port later
            # Signal it to stop and wait briefly to prevent port race
            self._abort_orphaned_thread()
            raise RuntimeError("Server startup timed out")

        self.running = True
        logger.debug("MCP server started successfully")

    def _abort_orphaned_thread(self):
        """Signal orphaned thread to stop and wait briefly.

        Called when start_sync times out or encounters an error.
        Prevents the thread from binding the port after we've given up.
        """
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        if self._server_thread and self._server_thread.is_alive():
            # Give it a brief moment to notice the stop flag
            self._server_thread.join(timeout=1.0)

            if self._server_thread.is_alive():
                logger.warning(
                    "Orphaned server thread still running after abort - "
                    "may cause port conflicts on next start"
                )

        # Clear references regardless - we've done our best
        self._server_thread = None
        self._uvicorn_server = None
        self._server_started = False
        self.running = False

    def stop_sync(self) -> bool:
        """Synchronous stop - works from any context (including after %gui qt).

        This is the primary method for stopping the server. It signals uvicorn
        to exit, waits for the thread to finish, and cleans up resources.

        Returns:
            True if server stopped successfully, False if timeout occurred.
        """
        if not self._server_thread or not self._server_thread.is_alive():
            # Already stopped or never started - clean up any stale state
            self._server_thread = None
            self._uvicorn_server = None
            self._server_started = False
            self.running = False
            # Cleanup tools even if server wasn't running (handles leaked resources)
            self._cleanup_tools_sync()
            return True

        logger.debug("Stopping MCP server...")

        # Phase 1: Request graceful shutdown
        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        # Wait briefly for graceful shutdown (allows clean client disconnection)
        self._server_thread.join(timeout=0.5)

        # Phase 2: Force exit if still running (kills active connections)
        if self._server_thread.is_alive():
            logger.debug("Forcing server shutdown (active connections)")
            if self._uvicorn_server:
                self._uvicorn_server.force_exit = True
            # Force-stop the event loop to ensure thread exits
            if self._server_loop:
                try:
                    self._server_loop.call_soon_threadsafe(self._server_loop.stop)
                except RuntimeError:
                    # Loop already closed or stopping
                    pass

        # Wait for thread to finish after force-stop
        self._server_thread.join(timeout=1.5)

        # Check if thread actually stopped
        if self._server_thread.is_alive():
            logger.warning("Server thread did not stop within timeout")
            # Even on timeout, we've force-stopped the loop, so clear state
            # to allow restart attempt (port should be released soon)

        # Clear state - server is down or will be momentarily
        self._server_thread = None
        self._uvicorn_server = None
        self._server_started = False
        self.running = False
        logger.debug("MCP server stopped")

        # Cleanup tools AFTER server is down to avoid conflicts
        self._cleanup_tools_sync()

        return True

    def _cleanup_tools_sync(self):
        """Run async tools cleanup synchronously.

        Strategy:
        1. Try new_event_loop() - works when cleanup doesn't touch IPython APIs
        2. If RuntimeError (IPython API access), try run_coroutine_threadsafe
           on server loop if still alive
        3. If both fail, log warning and continue (don't block server stop)
        """
        # First try: fresh event loop (simplest, works for most cleanup)
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.tools.cleanup())
                logger.debug("Tools cleanup completed (new loop)")
                return
            finally:
                loop.close()
        except RuntimeError as e:
            # May fail if cleanup touches IPython APIs expecting kernel loop
            logger.debug(f"new_event_loop cleanup failed: {e}, trying server loop")
        except Exception as e:
            logger.warning(f"Tools cleanup failed (new loop): {e}")
            return

        # Fallback: use server loop if still alive
        if self._server_loop and self._server_thread and self._server_thread.is_alive():
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.tools.cleanup(), self._server_loop
                )
                # Wait with timeout to avoid blocking indefinitely
                future.result(timeout=2.0)
                logger.debug("Tools cleanup completed (server loop)")
            except Exception as e:
                logger.warning(f"Tools cleanup failed (server loop): {e}")

    def is_running(self) -> bool:
        """Thread-safe running check.

        Uses our own _server_started flag rather than uvicorn internals.
        This avoids dependency on uvicorn's internal API which may change.
        """
        thread_alive = (
            self._server_thread is not None and self._server_thread.is_alive()
        )
        return thread_alive and self._server_started

    async def start(self):
        """Start the MCP server (async wrapper for start_sync).

        This async method is kept for backward compatibility but internally
        uses the synchronous thread-based approach.
        """
        self.start_sync()
        print(f"🚀 QCoDeS MCP Server running on http://{self.host}:{self.port}")
        print(f"🔑 Access token: {self.token}")

    async def stop(self):
        """Stop the MCP server (async wrapper for stop_sync).

        This async method is kept for backward compatibility but internally
        uses the synchronous thread-based approach. Cleanup is handled by
        stop_sync() so we don't duplicate it here.
        """
        success = self.stop_sync()
        if success:
            print("🛑 QCoDeS MCP Server stopped")
        else:
            print("⚠️  Server stop timed out - server may still be running")

    def set_safe_mode(self, safe_mode: bool) -> Dict[str, Any]:
        """Change the server's safe mode setting.

        Note: This requires server restart to take effect for tool registration.

        Args:
            safe_mode: True for safe mode, False for unsafe mode

        Returns:
            Dictionary with status information
        """
        old_mode = self.safe_mode
        self.safe_mode = safe_mode

        mode_status = "safe" if safe_mode else "unsafe"
        old_mode_status = "safe" if old_mode else "unsafe"

        logger.debug(f"MCP server mode changed from {old_mode_status} to {mode_status}")

        return {
            "old_mode": old_mode_status,
            "new_mode": mode_status,
            "server_running": self.running,
            "restart_required": True,
            "message": f"Server mode changed to {mode_status}. Restart required for tool changes to take effect.",
        }

    def set_enabled_options(self, enabled_options: set) -> Dict[str, Any]:
        """Change the server's enabled options.

        Note: This requires server restart to take effect for resource registration.

        Args:
            enabled_options: Set of enabled option names

        Returns:
            Dictionary with status information
        """
        old_options = self.enabled_options.copy()
        self.enabled_options = enabled_options.copy()

        added = enabled_options - old_options
        removed = old_options - enabled_options

        logger.debug(f"MCP server options changed: added={added}, removed={removed}")

        return {
            "old_options": sorted(old_options),
            "new_options": sorted(enabled_options),
            "added_options": sorted(added),
            "removed_options": sorted(removed),
            "server_running": self.running,
            "restart_required": True,
            "message": "Server options updated. Restart required for resource changes to take effect.",
        }
