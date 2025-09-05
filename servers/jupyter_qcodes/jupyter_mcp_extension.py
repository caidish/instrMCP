"""
IPython extension entry point for the Jupyter QCoDeS MCP server.

Load this extension in Jupyter with:
%load_ext servers.jupyter_qcodes.jupyter_mcp_extension

Or add to your Jupyter startup by adding this line to:
~/.ipython/profile_default/startup/00-load-mcp-extension.py
"""

import asyncio
import logging
from typing import Optional

from .mcp_server import JupyterMCPServer
from .active_cell_bridge import register_comm_target

logger = logging.getLogger(__name__)

# Global server instance
_server: Optional[JupyterMCPServer] = None
_server_task: Optional[asyncio.Task] = None


def load_ipython_extension(ipython):
    """Load the MCP extension when IPython starts."""
    global _server, _server_task
    
    try:
        logger.info("Loading Jupyter QCoDeS MCP extension...")
        
        # Check if we're in a Jupyter environment
        shell_type = ipython.__class__.__name__
        if shell_type != 'ZMQInteractiveShell':
            logger.warning(f"MCP extension designed for Jupyter, got {shell_type}")
        
        # Get the current event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, this shouldn't happen in Jupyter
            logger.error("No asyncio event loop found")
            return
        
        # Register comm target for active cell tracking
        register_comm_target()
        
        # Create and start the MCP server
        _server = JupyterMCPServer(ipython)
        _server_task = loop.create_task(_start_server_task())
        
        logger.info("Jupyter QCoDeS MCP extension loaded successfully")
        print("🚀 QCoDeS MCP Server starting...")
        
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
        "task_cancelled": _server_task and _server_task.cancelled()
    }