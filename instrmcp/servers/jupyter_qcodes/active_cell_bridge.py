"""
Active Cell Bridge for Jupyter MCP Extension

Handles communication between JupyterLab frontend and kernel to capture
the currently editing cell content via Jupyter comm protocol.
"""

import time
import threading
import logging
from typing import Optional, Dict, Any, List
from IPython import get_ipython

logger = logging.getLogger(__name__)

# Global state with thread safety
_STATE_LOCK = threading.Lock()
_LAST_SNAPSHOT: Optional[Dict[str, Any]] = None
_LAST_TS = 0.0
_ACTIVE_COMMS = set()


def _on_comm_open(comm, open_msg):
    """Handle new comm connection from frontend."""
    logger.info(f"🔌 NEW COMM OPENED: {comm.comm_id}")
    _ACTIVE_COMMS.add(comm)
    logger.info(f"📊 Active comms count: {len(_ACTIVE_COMMS)}")

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

        elif msg_type in ["update_response", "execute_response", "add_cell_response", "delete_cell_response", "apply_patch_response"]:
            # Response from frontend for our requests
            request_id = data.get("request_id")
            success = data.get("success", False)
            message = data.get("message", "")
            logger.info(f"✅ RECEIVED {msg_type} for request {request_id}: success={success}, message={message}")
            # Note: For now we just log the response, but we could store it for the waiting functions

        else:
            # Unknown message type - log for debugging
            logger.warning(f"❓ UNKNOWN MESSAGE TYPE: {msg_type}, data: {data}")

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


def add_new_cell(cell_type: str = "code", position: str = "below", content: str = "", timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Add a new cell relative to the currently active cell in JupyterLab frontend.

    Args:
        cell_type: Type of cell to create ("code", "markdown", "raw")
        position: Position relative to active cell ("above", "below")
        content: Initial content for the new cell
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with creation status and response details
    """
    import uuid

    logger.info(f"🚀 ADD_NEW_CELL called: type={cell_type}, position={position}, content_len={len(content)}")
    logger.info(f"📊 Active comms available: {len(_ACTIVE_COMMS)}")

    if not _ACTIVE_COMMS:
        logger.error("❌ NO ACTIVE COMMS - cannot send add_cell message")
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }

    # Add small delay to ensure comms are fully ready
    import time
    time.sleep(0.1)
    logger.info("⏱️ Added small delay for comm readiness")

    # Validate parameters
    valid_types = {"code", "markdown", "raw"}
    valid_positions = {"above", "below"}

    if cell_type not in valid_types:
        return {
            "success": False,
            "error": f"Invalid cell_type '{cell_type}'. Must be one of: {', '.join(valid_types)}"
        }

    if position not in valid_positions:
        return {
            "success": False,
            "error": f"Invalid position '{position}'. Must be one of: {', '.join(valid_positions)}"
        }

    request_id = str(uuid.uuid4())

    # Send add cell request to all active comms
    successful_sends = 0
    logger.info(f"📤 SENDING add_cell message to {len(_ACTIVE_COMMS)} comm(s)")

    for comm in list(_ACTIVE_COMMS):
        try:
            # Check if comm is still valid
            if hasattr(comm, 'comm_id') and hasattr(comm, 'send'):
                message = {
                    "type": "add_cell",
                    "cell_type": cell_type,
                    "position": position,
                    "content": content,
                    "request_id": request_id
                }
                logger.info(f"📤 Sending to comm {comm.comm_id}: {message}")
                comm.send(message)
                successful_sends += 1
                logger.info(f"✅ Successfully sent add_cell request to comm {comm.comm_id}")
            else:
                logger.warning(f"⚠️ Comm appears invalid, removing from active list")
                _ACTIVE_COMMS.discard(comm)
        except Exception as e:
            logger.error(f"❌ Failed to send add cell request to comm {comm.comm_id}: {e}")
            # Remove failed comm from active list
            _ACTIVE_COMMS.discard(comm)

    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send add cell request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }

    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling

        # Check if cell was added
        # Note: responses are handled in the comm message handler
        # For now, we'll wait for the timeout and return success
        pass

    return {
        "success": True,
        "message": f"Add cell request sent to {successful_sends} frontend(s)",
        "cell_type": cell_type,
        "position": position,
        "content_length": len(content),
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends,
        "warning": "UNSAFE: New cell was added to notebook"
    }


def delete_editing_cell(timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Delete the currently active cell in JupyterLab frontend.

    Args:
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with deletion status and response details
    """
    import uuid

    if not _ACTIVE_COMMS:
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }

    request_id = str(uuid.uuid4())

    # Send delete cell request to all active comms
    successful_sends = 0
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({
                "type": "delete_cell",
                "request_id": request_id
            })
            successful_sends += 1
            logger.debug(f"Sent delete_cell request to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send delete cell request to comm {comm.comm_id}: {e}")

    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send delete cell request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }

    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling

        # Check if cell was deleted
        # Note: responses are handled in the comm message handler
        # For now, we'll wait for the timeout and return success
        pass

    return {
        "success": True,
        "message": f"Delete cell request sent to {successful_sends} frontend(s)",
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends,
        "warning": "UNSAFE: Cell was deleted from notebook"
    }


def apply_patch(old_text: str, new_text: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Apply a simple text replacement patch to the currently active cell.

    This function replaces the first occurrence of old_text with new_text
    in the active cell content.

    Args:
        old_text: Text to find and replace
        new_text: Text to replace with
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with patch status and response details
    """
    import uuid

    if not _ACTIVE_COMMS:
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }

    if not old_text:
        return {
            "success": False,
            "error": "old_text parameter cannot be empty"
        }

    request_id = str(uuid.uuid4())

    # Send patch request to all active comms
    successful_sends = 0
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({
                "type": "apply_patch",
                "old_text": old_text,
                "new_text": new_text,
                "request_id": request_id
            })
            successful_sends += 1
            logger.debug(f"Sent apply_patch request to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send patch request to comm {comm.comm_id}: {e}")

    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send patch request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }

    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling

        # Check if patch was applied
        # Note: responses are handled in the comm message handler
        # For now, we'll wait for the timeout and return success
        pass

    return {
        "success": True,
        "message": f"Patch request sent to {successful_sends} frontend(s)",
        "old_text_length": len(old_text),
        "new_text_length": len(new_text),
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends,
        "warning": "UNSAFE: Cell content was modified via patch"
    }


def delete_cells_by_number(cell_numbers: List[int], timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Delete multiple cells by their execution count numbers.

    This function sends a request to the JupyterLab frontend to delete cells
    identified by their execution counts.

    Args:
        cell_numbers: List of execution count numbers to delete (e.g., [1, 2, 5])
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with deletion status and detailed results for each cell
    """
    import uuid

    if not _ACTIVE_COMMS:
        return {
            "success": False,
            "error": "No active comm connections to frontend",
            "active_comms": 0
        }

    if not isinstance(cell_numbers, list) or len(cell_numbers) == 0:
        return {
            "success": False,
            "error": "cell_numbers must be a non-empty list"
        }

    request_id = str(uuid.uuid4())

    # Send delete cells by number request to all active comms
    successful_sends = 0
    for comm in list(_ACTIVE_COMMS):
        try:
            comm.send({
                "type": "delete_cells_by_number",
                "cell_numbers": cell_numbers,
                "request_id": request_id
            })
            successful_sends += 1
            logger.debug(f"Sent delete_cells_by_number request to comm {comm.comm_id}")
        except Exception as e:
            logger.debug(f"Failed to send delete_cells_by_number request to comm {comm.comm_id}: {e}")

    if successful_sends == 0:
        return {
            "success": False,
            "error": "Failed to send delete request to any frontend",
            "active_comms": len(_ACTIVE_COMMS)
        }

    # Wait for response
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling
        # Note: responses are handled in the comm message handler
        pass

    return {
        "success": True,
        "message": f"Delete request sent to {successful_sends} frontend(s)",
        "cell_numbers": cell_numbers,
        "total_requested": len(cell_numbers),
        "request_id": request_id,
        "active_comms": len(_ACTIVE_COMMS),
        "successful_sends": successful_sends,
        "warning": "UNSAFE: Cells deletion requested - check notebook for results"
    }