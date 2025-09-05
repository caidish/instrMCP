"""
Active Cell Bridge for Jupyter MCP Extension

Handles communication between JupyterLab frontend and kernel to capture
the currently editing cell content via Jupyter comm protocol.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any
from IPython import get_ipython

logger = logging.getLogger(__name__)

# Global state with thread safety
_STATE_LOCK = threading.Lock()
_LAST_SNAPSHOT: Optional[Dict[str, Any]] = None
_LAST_TS = 0.0
_ACTIVE_COMMS = set()


def _on_comm_open(comm, open_msg):
    """Handle new comm connection from frontend."""
    logger.debug(f"New comm opened: {comm.comm_id}")
    _ACTIVE_COMMS.add(comm)

    def _on_msg(msg):
        """Handle incoming messages from frontend."""
        data = msg.get("content", {}).get("data", {})
        msg_type = data.get("type")
        
        if msg_type == "snapshot":
            # Store the cell snapshot
            snapshot = {
                "notebook_path": data.get("path"),
                "cell_id": data.get("id"),
                "cell_index": data.get("index"),
                "cell_type": data.get("cell_type", "code"),
                "text": data.get("text", ""),
                "cursor": data.get("cursor"),
                "selection": data.get("selection"),
                "client_id": data.get("client_id"),
                "ts_ms": data.get("ts_ms", int(time.time() * 1000)),
            }
            
            with _STATE_LOCK:
                global _LAST_SNAPSHOT, _LAST_TS
                _LAST_SNAPSHOT = snapshot
                _LAST_TS = time.time()
                
            logger.debug(f"Received cell snapshot: {len(snapshot.get('text', ''))} chars")
            
        elif msg_type == "pong":
            # Response to our ping request
            logger.debug("Received pong from frontend")

    def _on_close(msg):
        """Handle comm close."""
        logger.debug(f"Comm closed: {comm.comm_id}")
        _ACTIVE_COMMS.discard(comm)

    comm.on_msg(_on_msg)
    comm.on_close(_on_close)


def register_comm_target():
    """Register the comm target with IPython kernel."""
    ip = get_ipython()
    if not ip or not hasattr(ip, "kernel"):
        logger.warning("No IPython kernel found, cannot register comm target")
        return
    
    try:
        ip.kernel.comm_manager.register_target("mcp:active_cell", _on_comm_open)
        logger.info("Registered comm target 'mcp:active_cell'")
    except Exception as e:
        logger.error(f"Failed to register comm target: {e}")


def request_frontend_snapshot():
    """Request fresh snapshot from all connected frontends."""
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({"type": "request_current"})
            logger.debug(f"Sent request_current to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send request to comm {comm.comm_id}: {e}")


def get_active_cell(fresh_ms: Optional[int] = None, timeout_s: float = 0.3) -> Optional[Dict[str, Any]]:
    """
    Get the most recent active cell snapshot.
    
    Args:
        fresh_ms: If provided, require snapshot to be no older than this many milliseconds.
                 If snapshot is too old, will request fresh data from frontend.
        timeout_s: How long to wait for fresh data from frontend (default 0.3s)
    
    Returns:
        Dictionary with cell information or None if no data available
    """
    now = time.time()
    
    with _STATE_LOCK:
        if _LAST_SNAPSHOT is None:
            # No snapshot yet, try requesting from frontend
            pass
        else:
            age_ms = (now - _LAST_TS) * 1000 if _LAST_TS else float('inf')
            if fresh_ms is None or age_ms <= fresh_ms:
                # Snapshot is fresh enough
                return _LAST_SNAPSHOT.copy()

    # Need fresh data - request from frontends and wait
    if not _ACTIVE_COMMS:
        logger.debug("No active comms available for fresh data request")
        with _STATE_LOCK:
            return _LAST_SNAPSHOT.copy() if _LAST_SNAPSHOT else None

    # Request fresh data
    request_frontend_snapshot()
    
    # Wait for update with timeout
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling
        
        with _STATE_LOCK:
            if _LAST_SNAPSHOT is not None:
                age_ms = (time.time() - _LAST_TS) * 1000 if _LAST_TS else float('inf')
                if fresh_ms is None or age_ms <= fresh_ms:
                    return _LAST_SNAPSHOT.copy()
    
    # Timeout - return what we have
    with _STATE_LOCK:
        return _LAST_SNAPSHOT.copy() if _LAST_SNAPSHOT else None


def get_bridge_status() -> Dict[str, Any]:
    """Get status information about the bridge."""
    with _STATE_LOCK:
        return {
            "comm_target_registered": True,  # If this function is called, target is registered
            "active_comms": len(_ACTIVE_COMMS),
            "has_snapshot": _LAST_SNAPSHOT is not None,
            "last_snapshot_age_s": time.time() - _LAST_TS if _LAST_TS else None,
            "snapshot_summary": {
                "cell_type": _LAST_SNAPSHOT.get("cell_type") if _LAST_SNAPSHOT else None,
                "text_length": len(_LAST_SNAPSHOT.get("text", "")) if _LAST_SNAPSHOT else 0,
                "notebook_path": _LAST_SNAPSHOT.get("notebook_path") if _LAST_SNAPSHOT else None
            } if _LAST_SNAPSHOT else None
        }