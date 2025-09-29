"""
FastMCP server implementation for Jupyter QCoDeS integration.

This server provides read-only access to QCoDeS instruments and
Jupyter notebook functionality through MCP tools.
"""

import asyncio
import logging
import secrets
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

# MeasureIt integration (optional)
try:
    from ...extensions import MeasureIt as measureit_module
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

logger = logging.getLogger(__name__)


class JupyterMCPServer:
    """MCP server for Jupyter QCoDeS integration."""
    
    def __init__(self, ipython, host: str = "127.0.0.1", port: int = 8123, safe_mode: bool = True, enabled_options: set = None):
        self.ipython = ipython
        self.host = host
        self.port = port
        self.safe_mode = safe_mode
        self.enabled_options = enabled_options or set()
        self.running = False
        self.server_task: Optional[asyncio.Task] = None
        
        # Generate a random token for basic security
        self.token = secrets.token_urlsafe(32)
        
        # Initialize tools
        self.tools = QCodesReadOnlyTools(ipython)
        
        # Create FastMCP server
        server_name = f"Jupyter QCoDeS MCP Server ({'Safe' if safe_mode else 'Unsafe'} Mode)"
        self.mcp = FastMCP(server_name)
        self._register_resources()
        self._register_tools()
        
        mode_status = "safe" if safe_mode else "unsafe"
        logger.info(f"Jupyter MCP Server initialized on {host}:{port} in {mode_status} mode")

    def _register_resources(self):
        """Register MCP resources using the ResourceRegistrar."""
        resource_registrar = ResourceRegistrar(
            self.mcp,
            self.tools,
            enabled_options=self.enabled_options,
            measureit_module=measureit_module if MEASUREIT_AVAILABLE else None,
            db_module=db_integration if DATABASE_AVAILABLE else None
        )
        resource_registrar.register_all()

    def _register_tools(self):
        """Register all MCP tools using registrars."""

        # QCodes instrument tools
        qcodes_registrar = QCodesToolRegistrar(self.mcp, self.tools)
        qcodes_registrar.register_all()

        # Notebook tools
        notebook_registrar = NotebookToolRegistrar(self.mcp, self.tools, self.ipython)
        notebook_registrar.register_all()

        # Unsafe mode tools (if enabled)
        if not self.safe_mode:
            unsafe_registrar = UnsafeToolRegistrar(self.mcp, self.tools)
            unsafe_registrar.register_all()

        # Optional: MeasureIt tools
        if MEASUREIT_AVAILABLE and 'measureit' in self.enabled_options:
            measureit_registrar = MeasureItToolRegistrar(self.mcp, self.tools)
            measureit_registrar.register_all()

        # Optional: Database tools
        if DATABASE_AVAILABLE and 'database' in self.enabled_options:
            database_registrar = DatabaseToolRegistrar(self.mcp, db_integration)
            database_registrar.register_all()

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

    async def start(self):
        """Start the MCP server."""
        if self.running:
            return
        
        try:
            logger.info(f"Starting Jupyter MCP server on {self.host}:{self.port}")
            
            # Start the server in a separate task
            self.server_task = asyncio.create_task(self._run_server())
            self.running = True
            
            print(f"🚀 QCoDeS MCP Server running on http://{self.host}:{self.port}")
            print(f"🔑 Access token: {self.token}")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            raise
    
    async def _run_server(self):
        """Run the FastMCP server."""
        try:
            # Use FastMCP's run method - it handles the asyncio loop
            await asyncio.to_thread(
                self.mcp.run,
                transport="http",
                host=self.host,
                port=self.port,
                show_banner=False
            )
        except Exception as e:
            logger.error(f"MCP server error: {e}")
            raise
    
    async def stop(self):
        """Stop the MCP server."""
        if not self.running:
            return
        
        try:
            self.running = False
            
            # Clean up tools
            await self.tools.cleanup()
            
            # Cancel server task
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Jupyter MCP server stopped")
            print("🛑 QCoDeS MCP Server stopped")
            
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
    
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
        
        logger.info(f"MCP server mode changed from {old_mode_status} to {mode_status}")
        
        return {
            "old_mode": old_mode_status,
            "new_mode": mode_status,
            "server_running": self.running,
            "restart_required": True,
            "message": f"Server mode changed to {mode_status}. Restart required for tool changes to take effect."
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

        logger.info(f"MCP server options changed: added={added}, removed={removed}")

        return {
            "old_options": sorted(old_options),
            "new_options": sorted(enabled_options),
            "added_options": sorted(added),
            "removed_options": sorted(removed),
            "server_running": self.running,
            "restart_required": True,
            "message": f"Server options updated. Restart required for resource changes to take effect."
        }