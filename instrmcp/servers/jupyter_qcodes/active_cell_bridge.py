"""
Active Cell Bridge for Jupyter MCP Extension

Handles communication between JupyterLab frontend and kernel to capture
the currently editing cell content via Jupyter comm protocol.
"""

import copy
import time
import threading
import logging
from typing import Optional, Dict, Any, List
from IPython.core.getipython import get_ipython

logger = logging.getLogger(__name__)

# Global state with thread safety
_STATE_LOCK = threading.Lock()
_LAST_SNAPSHOT: Optional[Dict[str, Any]] = None
_LAST_TS = 0.0
# FIX: Changed from set() to Dict to track comm-to-kernel association
# This prevents broadcasting to ALL comms - only sends to the current kernel's comm
_KERNEL_COMM_MAP: Dict[str, Any] = {}  # kernel_id -> comm (one-to-one mapping)

# Cell outputs cache with timestamps for staleness detection
# Structure: {exec_count: {"data": output_data, "timestamp": float, "kernel_id": str}}
_CELL_OUTPUTS_CACHE: Dict[int, Dict[str, Any]] = {}

# Default cache TTL in seconds (60 seconds)
# Cached outputs older than this are considered stale and will be refreshed
CELL_OUTPUT_CACHE_TTL_SECONDS = 60.0

# Response waiting mechanism for operations that need frontend confirmation
# Maps request_id -> [threading.Event, response_dict or None]
_PENDING_REQUESTS: Dict[str, List] = {}


def _get_kernel_id() -> Optional[str]:
    """
    Get the kernel ID for the current IPython session.

    IMPORTANT: This must return the same ID that JupyterLab's frontend uses
    (kernel.id), which is the UUID from the connection file name.

    The connection file is typically named: kernel-<UUID>.json
    JupyterLab uses this UUID as kernel.id.

    Returns:
        Kernel ID string or None if not in IPython context
    """
    import re

    ip = get_ipython()
    if ip and hasattr(ip, "kernel") and ip.kernel:
        # Method 1: Extract UUID from connection file (matches JupyterLab's kernel.id)
        try:
            from ipykernel import get_connection_file

            connection_file = get_connection_file()
            # Connection file format: /path/to/kernel-<UUID>.json
            match = re.search(r"kernel-([a-f0-9-]+)\.json", connection_file)
            if match:
                return match.group(1)
        except Exception as e:
            logger.debug(f"Could not extract kernel ID from connection file: {e}")

        # Method 2: Try kernel's ident (some versions expose this)
        ident = getattr(ip.kernel, "ident", None)
        if ident:
            return str(ident)

        # Method 3: Fallback to session.session (may not match frontend)
        session = getattr(ip.kernel, "session", None)
        if session:
            session_id = getattr(session, "session", None)
            if session_id:
                logger.warning(
                    f"Using session.session as kernel_id ({session_id}). "
                    "This may not match frontend's kernel.id."
                )
                return str(session_id)

        # Last resort: use object id (will definitely not match frontend)
        logger.warning("Using object id as kernel_id - frontend matching will fail")
        return f"kernel_{id(ip.kernel)}"
    return None


def _on_comm_open(comm, open_msg):
    """
    Handle new comm connection from frontend.

    FIX: Now registers comm with kernel ID instead of adding to global set.
    This ensures operations only target the correct kernel's frontend.
    """
    logger.debug(f"🔌 NEW COMM OPENED: {comm.comm_id}")

    # Get kernel_id from open message (sent by frontend) or detect at runtime
    data = open_msg.get("content", {}).get("data", {})
    kernel_id = data.get("kernel_id") or _get_kernel_id()

    if not kernel_id:
        logger.warning(
            "⚠️ Cannot register comm: no kernel_id available. "
            "Operations may fail until kernel is identified."
        )
        # Still set up handlers but without kernel association
        kernel_id = f"unknown_{comm.comm_id}"

    with _STATE_LOCK:
        # Close existing comm for this kernel (clean replacement)
        old_comm = _KERNEL_COMM_MAP.get(kernel_id)
        if old_comm and old_comm != comm:
            logger.debug(f"♻️ Replacing existing comm for kernel {kernel_id}")
            try:
                old_comm.close()
            except Exception as e:
                logger.debug(f"Failed to close old comm: {e}")
        _KERNEL_COMM_MAP[kernel_id] = comm

    logger.debug(
        f"📊 Registered comm for kernel: {kernel_id} "
        f"(total kernels: {len(_KERNEL_COMM_MAP)})"
    )

    # Store kernel_id on the comm for use in close handler
    comm._mcp_kernel_id = kernel_id

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

            logger.debug(
                f"Received cell snapshot: {len(snapshot.get('text', ''))} chars"
            )

        elif msg_type == "pong":
            # Response to our ping request
            logger.debug("Received pong from frontend")

        elif msg_type == "get_cell_outputs_response":
            # Response from frontend with cell outputs
            from .image_utils import process_outputs_list

            outputs = data.get("outputs", {})
            current_time = time.time()
            kernel_id = getattr(comm, "_mcp_kernel_id", "unknown")

            # Store outputs in cache with timestamp for staleness detection
            with _STATE_LOCK:
                for cell_num_str, output_data in outputs.items():
                    try:
                        cell_num = int(cell_num_str)
                        # Process images: save to temp files, replace base64 with paths
                        cell_outputs = output_data.get("outputs", [])
                        if cell_outputs:
                            processed, image_paths = process_outputs_list(cell_outputs)
                            output_data = dict(output_data)
                            output_data["outputs"] = processed
                            if image_paths:
                                output_data["image_paths"] = image_paths
                        _CELL_OUTPUTS_CACHE[cell_num] = {
                            "data": output_data,
                            "timestamp": current_time,
                            "kernel_id": kernel_id,
                        }
                    except ValueError:
                        pass

            logger.debug(f"Cached outputs for {len(outputs)} cells (with timestamps)")

        elif msg_type in [
            "update_response",
            "execute_response",
            "add_cell_response",
            "delete_cell_response",
            "apply_patch_response",
            "move_cursor_response",
            "get_active_cell_output_response",
            "get_notebook_structure_response",
            "get_cells_by_index_response",
            "delete_cells_by_index_response",
        ]:
            # Response from frontend for our requests
            request_id = data.get("request_id")
            success = data.get("success", False)
            message = data.get("message", "")

            # Log additional info for move_cursor_response
            if msg_type == "move_cursor_response" and success:
                old_index = data.get("old_index")
                new_index = data.get("new_index")
                logger.debug(f"✅ CURSOR MOVED: {old_index} → {new_index}")
            else:
                logger.debug(
                    f"✅ RECEIVED {msg_type} for request {request_id}: success={success}, message={message}"
                )

            # Resolve pending request if someone is waiting for the response
            if request_id:
                with _STATE_LOCK:
                    if request_id in _PENDING_REQUESTS:
                        event, _ = _PENDING_REQUESTS[request_id]
                        # Store the full response data
                        _PENDING_REQUESTS[request_id] = [event, data]
                        event.set()  # Wake up the waiting thread
                        logger.debug(f"✅ Resolved pending request {request_id}")

        else:
            # Unknown message type - log for debugging
            logger.warning(f"❓ UNKNOWN MESSAGE TYPE: {msg_type}, data: {data}")

    def _on_close(msg):
        """Handle comm close - remove from kernel mapping."""
        kernel_id = getattr(comm, "_mcp_kernel_id", None)
        logger.debug(f"Comm closed: {comm.comm_id} (kernel: {kernel_id})")

        with _STATE_LOCK:
            # Only remove if this comm is still the registered one for this kernel
            if kernel_id and _KERNEL_COMM_MAP.get(kernel_id) == comm:
                del _KERNEL_COMM_MAP[kernel_id]
                logger.debug(
                    f"🗑️ Removed comm for kernel {kernel_id} "
                    f"(remaining kernels: {len(_KERNEL_COMM_MAP)})"
                )

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
        logger.debug("Registered comm target 'mcp:active_cell'")
    except Exception as e:
        logger.error(f"Failed to register comm target: {e}")


def request_frontend_snapshot():
    """Request fresh snapshot from current kernel's frontend."""
    kernel_id = _get_kernel_id()
    if not kernel_id:
        logger.debug("Cannot request snapshot: no kernel_id")
        return

    with _STATE_LOCK:
        comm = _KERNEL_COMM_MAP.get(kernel_id)

    if not comm:
        logger.debug(f"Cannot request snapshot: no comm for kernel {kernel_id}")
        return

    try:
        comm.send({"type": "request_current"})
        logger.debug(f"Sent request_current to comm {comm.comm_id}")
    except Exception as e:
        logger.debug(f"Failed to send request to comm {comm.comm_id}: {e}")


def _send_to_kernel(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a message to the current kernel's comm only.

    This is the core fix for bugs #1 and #2 - instead of broadcasting to ALL
    comms (which caused operations to repeat N times), we now send to only
    the comm associated with the current kernel.

    Args:
        payload: Message payload (type, request_id, and operation-specific data)

    Returns:
        Result dict with success status, request_id, kernel_id, or error
    """
    import uuid

    kernel_id = _get_kernel_id()
    if not kernel_id:
        return {
            "success": False,
            "error": "Cannot identify current kernel - are you in a Jupyter notebook?",
        }

    with _STATE_LOCK:
        comm = _KERNEL_COMM_MAP.get(kernel_id)

    if not comm:
        return {
            "success": False,
            "error": f"No active frontend connection for kernel {kernel_id}",
            "kernel_id": kernel_id,
            "hint": "Ensure the JupyterLab extension is loaded and connected",
        }

    # Add request_id if not present
    if "request_id" not in payload:
        payload["request_id"] = str(uuid.uuid4())

    try:
        comm.send(payload)
        return {
            "success": True,
            "message": f"{payload.get('type', 'unknown')} request sent",
            "request_id": payload["request_id"],
            "kernel_id": kernel_id,
        }
    except Exception as e:
        logger.error(f"Failed to send {payload.get('type')}: {e}")
        # Clean up dead comm
        with _STATE_LOCK:
            if _KERNEL_COMM_MAP.get(kernel_id) == comm:
                del _KERNEL_COMM_MAP[kernel_id]
                logger.debug(f"Removed dead comm for kernel {kernel_id}")
        return {
            "success": False,
            "error": f"Send failed: {e}",
            "kernel_id": kernel_id,
        }


def _send_and_wait(payload: Dict[str, Any], timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Send a message to the frontend and wait for the response.

    This function allows operations to wait for and return the actual frontend
    response, including error messages for failures like "cell not found".

    Args:
        payload: Message payload (type, and operation-specific data)
        timeout_s: How long to wait for response from frontend

    Returns:
        The actual response from frontend, or error dict on timeout/failure
    """
    import uuid

    # Generate request_id if not present
    request_id = payload.get("request_id") or str(uuid.uuid4())
    payload["request_id"] = request_id

    # Create event for waiting
    event = threading.Event()
    with _STATE_LOCK:
        _PENDING_REQUESTS[request_id] = [event, None]

    try:
        # Send the message using existing function (which will use our request_id)
        send_result = _send_to_kernel(payload)

        if not send_result["success"]:
            # Send failed, clean up and return the error
            with _STATE_LOCK:
                _PENDING_REQUESTS.pop(request_id, None)
            return send_result

        # Wait for response with timeout
        if event.wait(timeout=timeout_s):
            # Got response
            with _STATE_LOCK:
                _, response = _PENDING_REQUESTS.pop(request_id, [None, None])

            if response:
                # Return the full response from frontend
                return {
                    "success": response.get("success", False),
                    "message": response.get("message", ""),
                    "request_id": request_id,
                    "kernel_id": send_result.get("kernel_id"),
                    # Include any additional fields from frontend response
                    **{
                        k: v
                        for k, v in response.items()
                        if k not in ["type", "request_id", "success", "message"]
                    },
                }
            else:
                return {
                    "success": False,
                    "error": "Response received but data was empty",
                    "request_id": request_id,
                }
        else:
            # Timeout
            with _STATE_LOCK:
                _PENDING_REQUESTS.pop(request_id, None)
            return {
                "success": False,
                "error": f"Timeout waiting for frontend response after {timeout_s}s",
                "request_id": request_id,
                "kernel_id": send_result.get("kernel_id"),
            }

    except Exception as e:
        # Clean up on any error
        with _STATE_LOCK:
            _PENDING_REQUESTS.pop(request_id, None)
        logger.error(f"Error in _send_and_wait: {e}")
        return {
            "success": False,
            "error": f"Error waiting for response: {e}",
            "request_id": request_id,
        }


def _get_current_comm() -> Optional[Any]:
    """
    Get the comm for the current kernel (for read operations).

    Returns:
        Comm object or None if not available
    """
    kernel_id = _get_kernel_id()
    if not kernel_id:
        return None

    with _STATE_LOCK:
        return _KERNEL_COMM_MAP.get(kernel_id)


def _wrap_snapshot_with_metadata(
    snapshot: Optional[Dict[str, Any]],
    stale: bool,
    source: str,
    age_ms: float,
    stale_reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Wrap a snapshot with staleness metadata.

    Args:
        snapshot: The snapshot dict to wrap (will be deep copied)
        stale: Whether the data is stale
        source: "live" (fresh enough to use) or "cache" (stale/fallback).
                Note: "live" means data meets freshness threshold, not necessarily
                that it was just fetched from frontend.
        age_ms: Age of the snapshot in milliseconds
        stale_reason: Reason for staleness (e.g., "no_active_comms", "timeout")

    Returns:
        Deep copy of snapshot with metadata added, or None if snapshot is None
    """
    if snapshot is None:
        return None

    # Use deepcopy to prevent mutations from corrupting the cached _LAST_SNAPSHOT
    result = copy.deepcopy(snapshot)
    result["stale"] = stale
    result["source"] = source
    result["age_ms"] = age_ms
    if stale_reason:
        result["stale_reason"] = stale_reason
    return result


def get_active_cell(
    fresh_ms: Optional[int] = None, timeout_s: float = 0.3
) -> Optional[Dict[str, Any]]:
    """
    Get the most recent active cell snapshot.

    Args:
        fresh_ms: If provided, require snapshot to be no older than this many milliseconds.
                 If snapshot is too old, will request fresh data from frontend.
        timeout_s: How long to wait for fresh data from frontend (default 0.3s)

    Returns:
        Dictionary with cell information or None if no data available.
        Includes metadata fields:
        - stale (bool): Whether the data is stale
        - source (str): "live" or "cache"
        - age_ms (float): Age of the snapshot in milliseconds
        - stale_reason (str, optional): Reason for staleness if stale=True
    """
    now = time.time()

    with _STATE_LOCK:
        if _LAST_SNAPSHOT is None:
            # No snapshot yet, try requesting from frontend
            pass
        else:
            age_ms = (now - _LAST_TS) * 1000 if _LAST_TS else None
            # Snapshot is fresh if: no freshness required OR (age is known AND within threshold)
            if fresh_ms is None or (age_ms is not None and age_ms <= fresh_ms):
                # Snapshot is fresh enough
                return _wrap_snapshot_with_metadata(
                    _LAST_SNAPSHOT, stale=False, source="live", age_ms=age_ms
                )

    # Need fresh data - request from current kernel's frontend
    comm = _get_current_comm()
    if not comm:
        logger.debug("No active comm available for fresh data request")
        with _STATE_LOCK:
            if _LAST_SNAPSHOT is None:
                return None
            age_ms = (time.time() - _LAST_TS) * 1000 if _LAST_TS else None
            return _wrap_snapshot_with_metadata(
                _LAST_SNAPSHOT,
                stale=True,
                source="cache",
                age_ms=age_ms,
                stale_reason="no_active_comms",
            )

    # Request fresh data
    request_frontend_snapshot()

    # Wait for update with timeout
    start_time = time.time()
    while time.time() - start_time < timeout_s:
        time.sleep(0.05)  # 50ms polling

        with _STATE_LOCK:
            if _LAST_SNAPSHOT is not None:
                age_ms = (time.time() - _LAST_TS) * 1000 if _LAST_TS else None
                if fresh_ms is None or (age_ms is not None and age_ms <= fresh_ms):
                    return _wrap_snapshot_with_metadata(
                        _LAST_SNAPSHOT, stale=False, source="live", age_ms=age_ms
                    )

    # Timeout - return what we have (marked as stale)
    with _STATE_LOCK:
        if _LAST_SNAPSHOT is None:
            return None
        age_ms = (time.time() - _LAST_TS) * 1000 if _LAST_TS else None
        return _wrap_snapshot_with_metadata(
            _LAST_SNAPSHOT,
            stale=True,
            source="cache",
            age_ms=age_ms,
            stale_reason="timeout",
        )


def get_bridge_status() -> Dict[str, Any]:
    """Get status information about the bridge."""
    with _STATE_LOCK:
        return {
            "comm_target_registered": True,  # If this function is called, target is registered
            "active_kernels": len(_KERNEL_COMM_MAP),
            "kernel_ids": list(_KERNEL_COMM_MAP.keys()),
            "current_kernel_id": _get_kernel_id(),
            "has_snapshot": _LAST_SNAPSHOT is not None,
            "last_snapshot_age_s": time.time() - _LAST_TS if _LAST_TS else None,
            "snapshot_summary": (
                {
                    "cell_type": (
                        _LAST_SNAPSHOT.get("cell_type") if _LAST_SNAPSHOT else None
                    ),
                    "text_length": (
                        len(_LAST_SNAPSHOT.get("text", "")) if _LAST_SNAPSHOT else 0
                    ),
                    "notebook_path": (
                        _LAST_SNAPSHOT.get("notebook_path") if _LAST_SNAPSHOT else None
                    ),
                }
                if _LAST_SNAPSHOT
                else None
            ),
        }


def update_active_cell(content: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Update the content of the currently active cell in JupyterLab frontend.

    FIX: Now sends to only the current kernel's comm instead of all comms.

    Args:
        content: New content to set in the active cell
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with update status and response details
    """
    result = _send_to_kernel({"type": "update_cell", "content": content})

    if result["success"]:
        result["content_length"] = len(content)

    return result


def execute_active_cell(timeout_s: float = 5.0) -> Dict[str, Any]:
    """
    Execute the currently active cell in JupyterLab frontend.

    FIX: Now sends to only the current kernel's comm instead of all comms.

    Args:
        timeout_s: How long to wait for response from frontend (default 5.0s)

    Returns:
        Dictionary with execution status and response details
    """
    result = _send_to_kernel({"type": "execute_cell"})

    if result["success"]:
        result["warning"] = "UNSAFE: Code execution was requested in active cell"

    return result


def add_new_cell(
    cell_type: str = "code",
    position: str = "below",
    content: str = "",
    timeout_s: float = 2.0,
) -> Dict[str, Any]:
    """
    Add a new cell relative to the currently active cell in JupyterLab frontend.

    FIX: Now sends to only the current kernel's comm instead of all comms and
    waits for the frontend response to report actual success/failure.

    Args:
        cell_type: Type of cell to create ("code", "markdown", "raw")
        position: Position relative to active cell ("above", "below", "end")
                  "end" appends the cell at the very end of the notebook
        content: Initial content for the new cell
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with creation status and response details
    """
    logger.debug(
        f"🚀 ADD_NEW_CELL called: type={cell_type}, position={position}, content_len={len(content)}"
    )

    # Validate parameters
    valid_types = {"code", "markdown", "raw"}
    valid_positions = {"above", "below", "end"}

    if cell_type not in valid_types:
        return {
            "success": False,
            "error": f"Invalid cell_type '{cell_type}'. Must be one of: {', '.join(valid_types)}",
        }

    if position not in valid_positions:
        return {
            "success": False,
            "error": f"Invalid position '{position}'. Must be one of: {', '.join(valid_positions)}",
        }

    result = _send_and_wait(
        {
            "type": "add_cell",
            "cell_type": cell_type,
            "position": position,
            "content": content,
        },
        timeout_s=timeout_s,
    )

    if result["success"]:
        result["cell_type"] = cell_type
        result["position"] = position
        result["content_length"] = len(content)
        result["warning"] = "UNSAFE: New cell was added to notebook"

    return result


def delete_editing_cell(timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Delete the currently active cell in JupyterLab frontend.

    FIX: Now sends to only the current kernel's comm instead of all comms.
    This is the primary fix for Bug #1 - previously this function would send
    delete requests to ALL connected frontends, causing 2-5 cells to be deleted.

    Args:
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with deletion status and response details
    """
    result = _send_to_kernel({"type": "delete_cell"})

    if result["success"]:
        result["warning"] = "UNSAFE: Cell was deleted from notebook"

    return result


def apply_patch(old_text: str, new_text: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Apply a simple text replacement patch to the currently active cell.

    FIX: Now sends to only the current kernel's comm instead of all comms.
    This is the primary fix for Bug #2 - previously this function would send
    patch requests to ALL connected frontends, causing the patch to apply
    multiple times (e.g., "y = 2" -> "y = 200" became "y = 2000000").

    This function replaces the first occurrence of old_text with new_text
    in the active cell content.

    Args:
        old_text: Text to find and replace
        new_text: Text to replace with
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with patch status and response details
    """
    if not old_text:
        return {"success": False, "error": "old_text parameter cannot be empty"}

    result = _send_to_kernel(
        {
            "type": "apply_patch",
            "old_text": old_text,
            "new_text": new_text,
        }
    )

    if result["success"]:
        result["old_text_length"] = len(old_text)
        result["new_text_length"] = len(new_text)
        result["warning"] = "UNSAFE: Cell content was modified via patch"

    return result


def delete_cells_by_number(
    cell_numbers: List[int], timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Delete multiple cells by their execution count numbers.

    FIX: Now sends to only the current kernel's comm instead of all comms.

    This function sends a request to the JupyterLab frontend to delete cells
    identified by their execution counts.

    Args:
        cell_numbers: List of execution count numbers to delete (e.g., [1, 2, 5])
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with deletion status and detailed results for each cell
    """
    if not isinstance(cell_numbers, list) or len(cell_numbers) == 0:
        return {"success": False, "error": "cell_numbers must be a non-empty list"}

    result = _send_to_kernel(
        {
            "type": "delete_cells_by_number",
            "cell_numbers": cell_numbers,
        }
    )

    if result["success"]:
        result["cell_numbers"] = cell_numbers
        result["total_requested"] = len(cell_numbers)
        result["warning"] = (
            "UNSAFE: Cells deletion requested - check notebook for results"
        )

    return result


def get_cached_cell_output(
    cell_number: int,
    max_age_seconds: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get cached output for a specific cell from the frontend response cache.

    Implements timestamp-based cache validation to avoid returning stale
    error states that no longer reflect the current cell state.

    Args:
        cell_number: Execution count number of the cell
        max_age_seconds: Maximum age of cached data in seconds.
                        If None, uses CELL_OUTPUT_CACHE_TTL_SECONDS (default 60s).
                        If 0, returns cached data regardless of age.

    Returns:
        Dictionary with output data if available and not expired, None otherwise.
        The returned dict includes metadata:
        - "data": The actual output data
        - "timestamp": When the data was cached
        - "age_seconds": How old the cached data is
        - "stale": Whether the data exceeds max_age_seconds
    """
    if max_age_seconds is None:
        max_age_seconds = CELL_OUTPUT_CACHE_TTL_SECONDS

    with _STATE_LOCK:
        cache_entry = _CELL_OUTPUTS_CACHE.get(cell_number)
        if cache_entry is None:
            return None

        current_time = time.time()
        cached_timestamp = cache_entry.get("timestamp", 0)
        age_seconds = current_time - cached_timestamp

        # Check if cache entry is expired (unless max_age is 0, meaning no expiry)
        is_stale = max_age_seconds > 0 and age_seconds > max_age_seconds

        if is_stale:
            # Remove stale entry from cache
            del _CELL_OUTPUTS_CACHE[cell_number]
            logger.debug(
                f"Cache entry for cell {cell_number} expired "
                f"(age: {age_seconds:.1f}s > TTL: {max_age_seconds}s)"
            )
            return None

        # Return the cached data with metadata
        return {
            "data": cache_entry.get("data"),
            "timestamp": cached_timestamp,
            "age_seconds": age_seconds,
            "stale": False,
            "kernel_id": cache_entry.get("kernel_id"),
        }


def invalidate_cell_output_cache(
    cell_numbers: Optional[List[int]] = None,
    older_than_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Invalidate (clear) cached cell outputs.

    This function helps prevent stale error states from persisting in the cache.
    It can be called after cell re-execution to ensure fresh data is fetched.

    Args:
        cell_numbers: List of specific cell numbers to invalidate.
                     If None, invalidates all cached cells.
        older_than_seconds: Only invalidate entries older than this many seconds.
                           If None, invalidates regardless of age.

    Returns:
        Dictionary with invalidation results:
        - "invalidated_count": Number of cache entries removed
        - "remaining_count": Number of entries still in cache
        - "cell_numbers": List of cell numbers that were invalidated
    """
    current_time = time.time()
    invalidated = []

    with _STATE_LOCK:
        if cell_numbers is None:
            # Invalidate all or by age
            cells_to_check = list(_CELL_OUTPUTS_CACHE.keys())
        else:
            cells_to_check = cell_numbers

        for cell_num in cells_to_check:
            if cell_num not in _CELL_OUTPUTS_CACHE:
                continue

            cache_entry = _CELL_OUTPUTS_CACHE[cell_num]
            should_invalidate = True

            if older_than_seconds is not None:
                cached_timestamp = cache_entry.get("timestamp", 0)
                age_seconds = current_time - cached_timestamp
                should_invalidate = age_seconds > older_than_seconds

            if should_invalidate:
                del _CELL_OUTPUTS_CACHE[cell_num]
                invalidated.append(cell_num)

        remaining_count = len(_CELL_OUTPUTS_CACHE)

    logger.debug(
        f"Invalidated {len(invalidated)} cache entries, {remaining_count} remaining"
    )

    return {
        "invalidated_count": len(invalidated),
        "remaining_count": remaining_count,
        "cell_numbers": invalidated,
    }


def get_cell_outputs(cell_numbers: List[int], timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Get outputs for specific cells from the JupyterLab frontend.

    FIX: Now sends to only the current kernel's comm instead of all comms.

    Retrieves cell outputs (stdout, stderr, execute_result, errors) from
    the notebook model in the JupyterLab frontend.

    Args:
        cell_numbers: List of execution count numbers to get outputs for (e.g., [1, 2, 5])
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with outputs for each requested cell number
    """
    if not isinstance(cell_numbers, list) or len(cell_numbers) == 0:
        return {"success": False, "error": "cell_numbers must be a non-empty list"}

    result = _send_to_kernel(
        {
            "type": "get_cell_outputs",
            "cell_numbers": cell_numbers,
        }
    )

    if result["success"]:
        result["cell_numbers"] = cell_numbers

    return result


def move_cursor(target: str, timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Move cursor to a different cell in the notebook.

    Waits for frontend response to return actual success/failure status,
    including errors when the target cell does not exist.

    Args:
        target: Where to move the cursor:
               - "above": Move to cell above current
               - "below": Move to cell below current
               - "bottom": Move to the last cell in the notebook (by file order)
               - "index:N": Move to cell at position N (0-indexed) - works for ALL cells
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with operation status, old index, and new index.
        Returns success=False with error message if target cell not found.
    """
    # Validate target
    valid_targets = ["above", "below", "bottom"]
    if target not in valid_targets and not target.startswith("index:"):
        return {
            "success": False,
            "error": f"Invalid target '{target}'. Must be 'above', 'below', 'bottom', or 'index:N'",
        }

    # Use _send_and_wait to get actual frontend response
    result = _send_and_wait(
        {
            "type": "move_cursor",
            "target": str(target),
        },
        timeout_s=timeout_s,
    )

    if result["success"]:
        result["target"] = target

    return result


def get_active_cell_output(timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Get the output of the currently active cell directly from JupyterLab frontend.

    This function retrieves the output from the cell that is currently selected
    in JupyterLab, avoiding stale state issues with IPython's In/Out history.

    FIX for Bug #10: The previous implementation used IPython's sys.last_value
    and Out history which can be stale. This directly queries the JupyterLab
    frontend for the active cell's current outputs.

    Args:
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with:
        - success (bool): Whether the operation succeeded
        - cell_type (str): Type of the active cell ("code", "markdown", etc.)
        - cell_index (int): Index of the active cell in the notebook
        - execution_count (int|None): Execution count for code cells
        - has_output (bool): Whether the cell has any output
        - has_error (bool): Whether the cell output contains an error
        - outputs (list): List of output objects (stream, execute_result, error, etc.)
        - image_paths (list): File paths of saved images (if any)
        - message (str): Status message
    """
    from .image_utils import process_outputs_list

    result = _send_and_wait(
        {"type": "get_active_cell_output"},
        timeout_s=timeout_s,
    )

    # Process images: save to temp files, replace base64 with paths
    if result.get("success") and "outputs" in result:
        processed, image_paths = process_outputs_list(result["outputs"])
        result["outputs"] = processed
        if image_paths:
            result["image_paths"] = image_paths

    return result


def get_notebook_structure(timeout_s: float = 2.0) -> Dict[str, Any]:
    """
    Get lightweight notebook structure (metadata only, no source code).

    This function retrieves the list of all cells in the notebook with their
    metadata (type, position, execution count) but WITHOUT source code,
    making it fast for large notebooks.

    Args:
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with:
        - success (bool): Whether the operation succeeded
        - total_cells (int): Total number of cells in notebook
        - active_cell_index (int): Index of currently active cell
        - cells (list): List of cell metadata dicts with:
            - cell_id_notebook (int): Position in notebook (0-indexed)
            - cell_type (str): "code", "markdown", or "raw"
            - cell_execution_number (int|None): IPython counter or null
        - error (str): Error message if failed
    """
    result = _send_and_wait(
        {"type": "get_notebook_structure"},
        timeout_s=timeout_s,
    )
    return result


def get_cells_by_index(
    cell_id_notebooks: List[int], timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Get specific cells by position index (with source code).

    This function fetches specific cells from the notebook by their position,
    allowing targeted retrieval of cell content without fetching the entire notebook.

    Args:
        cell_id_notebooks: List of cell indices to fetch (0-indexed positions)
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with:
        - success (bool): Whether the operation succeeded
        - cells (list): List of cell dicts with:
            - cell_id_notebook (int): Position in notebook
            - cell_type (str): "code", "markdown", or "raw"
            - cell_execution_number (int|None): IPython counter or null
            - source (str): Cell source code
        - error (str): Error message if failed
    """
    result = _send_and_wait(
        {
            "type": "get_cells_by_index",
            "cell_id_notebooks": cell_id_notebooks,
        },
        timeout_s=timeout_s,
    )
    return result


def delete_cells_by_index(
    cell_id_notebooks: List[int], timeout_s: float = 2.0
) -> Dict[str, Any]:
    """
    Delete cells by position index (works for ALL cells including unexecuted ones).

    This function deletes cells from the notebook by their position, allowing
    deletion of markdown cells or unexecuted code cells that don't have
    execution counts.

    IMPORTANT: This function also invalidates the output cache for any deleted
    cells that had execution counts, preventing stale data issues.

    Args:
        cell_id_notebooks: List of cell indices to delete (0-indexed positions)
        timeout_s: How long to wait for response from frontend (default 2.0s)

    Returns:
        Dictionary with:
        - success (bool): Whether the operation succeeded
        - deleted_count (int): Number of cells deleted
        - cleared_count (int): Number of cells cleared (if last cell)
        - invalidated_exec_counts (list): Execution counts that were invalidated
        - message (str): Status message
    """
    result = _send_and_wait(
        {
            "type": "delete_cells_by_index",
            "cell_id_notebooks": cell_id_notebooks,
        },
        timeout_s=timeout_s,
    )

    # Invalidate cache entries for deleted cells
    if result.get("success") and result.get("invalidated_exec_counts"):
        with _STATE_LOCK:
            for exec_count in result["invalidated_exec_counts"]:
                _CELL_OUTPUTS_CACHE.pop(exec_count, None)
        logger.debug(
            f"Invalidated cache for {len(result['invalidated_exec_counts'])} cells"
        )

    return result
