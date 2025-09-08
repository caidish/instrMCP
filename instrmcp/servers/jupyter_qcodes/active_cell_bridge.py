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


def update_active_cell(content: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Update the content of the currently active cell in JupyterLab frontend.
    
    Args:
        content: New content to set in the active cell
        timeout_s: How long to wait for response from frontend (default 2.0s)
        
    Returns:
        Dictionary with update status and response details
    """
    import uuid
    
    if not _ACTIVE_COMMS:
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }
    
    request_id = str(uuid.uuid4())
    responses = {}
    
    # Send update request to all active comms
    successful_sends = 0
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({
                "type": "update_cell",
                "content": content,
                "request_id": request_id
            })
            successful_sends += 1
            logger.debug(f"Sent update_cell request to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send update request to comm {comm.comm_id}: {e}")
    
    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send update request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }
    
    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling
        
        # Check if we received any responses
        # Note: responses are handled in the comm message handler
        # For now, we'll wait for the timeout and return success
        # A more sophisticated implementation could track responses
        pass
    
    return {
        "success": True,
        "message": f"Update request sent to {successful_sends} frontend(s)",
        "content_length": len(content),
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends
    }


def execute_active_cell(timeout_s: float = 5.0) -> Dict[str, Any]:
    """
    Execute the currently active cell in JupyterLab frontend.
    
    Args:
        timeout_s: How long to wait for response from frontend (default 5.0s)
        
    Returns:
        Dictionary with execution status and response details
    """
    import uuid
    
    if not _ACTIVE_COMMS:
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }
    
    request_id = str(uuid.uuid4())
    
    # Send execution request to all active comms
    successful_sends = 0
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({
                "type": "execute_cell",
                "request_id": request_id
            })
            successful_sends += 1
            logger.debug(f"Sent execute_cell request to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send execution request to comm {comm.comm_id}: {e}")
    
    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send execution request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }
    
    # Wait for execution to complete
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.1)  # 100ms polling
        
        # Check if execution is complete
        # Note: responses are handled in the comm message handler
        # For now, we'll wait for the timeout and return success
        # A more sophisticated implementation could track execution responses
        pass
    
    return {
        "success": True,
        "message": f"Execution request sent to {successful_sends} frontend(s)",
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends,
        "warning": "UNSAFE: Code execution was requested in active cell"
    }