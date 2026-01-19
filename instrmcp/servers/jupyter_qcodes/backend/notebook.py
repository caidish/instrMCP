"""
Notebook backend for read-only notebook operations.

Handles all read-only notebook operations including:
- Variable listing and inspection
- Cell content reading
- Cursor movement
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Set

from .base import BaseBackend, SharedState

logger = logging.getLogger(__name__)


class NotebookBackend(BaseBackend):
    """Backend for read-only notebook operations."""

    _INTERNAL_NAMES: Set[str] = {
        "In",
        "Out",
        "get_ipython",
        "exit",
        "quit",
        "open",
    }

    def __init__(self, state: SharedState):
        """Initialize notebook backend.

        Args:
            state: SharedState instance containing shared resources
        """
        super().__init__(state)
        # Import active_cell_bridge lazily to avoid circular imports
        self._bridge = None

    @property
    def bridge(self):
        """Lazy import of active_cell_bridge."""
        if self._bridge is None:
            try:
                from .. import active_cell_bridge

                self._bridge = active_cell_bridge
            except ImportError:
                import active_cell_bridge

                self._bridge = active_cell_bridge
        return self._bridge

    async def list_variables(
        self, type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List variables in the Jupyter namespace."""
        # Normalize "null" string to None (some MCP clients serialize null as "null")
        if type_filter and type_filter.strip().lower() == "null":
            type_filter = None

        hidden_names: Set[str] = set()
        if hasattr(self.ipython, "user_ns_hidden"):
            hidden = getattr(self.ipython, "user_ns_hidden", None)
            if isinstance(hidden, dict):
                hidden_names.update(hidden.keys())

        variables = []

        for name, obj in self.namespace.items():
            # Skip private variables and built-ins
            if name.startswith("_"):
                continue
            if name in self._INTERNAL_NAMES:
                continue
            if name in hidden_names:
                continue

            var_type = type(obj).__name__

            # Apply type filter if specified
            if type_filter and type_filter.lower() not in var_type.lower():
                continue

            variables.append(
                {
                    "name": name,
                    "type": var_type,
                }
            )

        return sorted(variables, key=lambda x: x["name"])

    async def get_variable_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a variable."""
        if name not in self.namespace:
            raise ValueError(f"Variable '{name}' not found in namespace")

        obj = self.namespace[name]

        # Get repr and truncate if needed
        obj_repr = repr(obj)
        repr_truncated = len(obj_repr) > 500
        if repr_truncated:
            obj_repr = obj_repr[:500] + "... [truncated]"

        info = {
            "name": name,
            "type": type(obj).__name__,
            "module": getattr(type(obj), "__module__", "builtins"),
            "size": len(obj) if hasattr(obj, "__len__") else None,
            "attributes": [attr for attr in dir(obj) if not attr.startswith("_")],
            "repr": obj_repr,
            "repr_truncated": repr_truncated,
        }

        # Add QCoDeS-specific info if it's an instrument
        try:
            from qcodes.instrument.base import InstrumentBase

            if isinstance(obj, InstrumentBase):
                info["qcodes_instrument"] = True
                info["parameters"] = (
                    list(obj.parameters.keys()) if hasattr(obj, "parameters") else []
                )
                info["address"] = getattr(obj, "address", None)
        except ImportError:
            info["qcodes_instrument"] = False

        return info

    async def get_editing_cell(
        self,
        fresh_ms: Optional[int] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        max_lines: int = 200,
    ) -> Dict[str, Any]:
        """Get the currently editing cell content from JupyterLab frontend.

        This captures the cell that is currently being edited in the frontend.

        Args:
            fresh_ms: Optional maximum age in milliseconds. If provided and the
                     cached snapshot is older, will request fresh data from frontend.
            line_start: Optional starting line number (1-indexed).
            line_end: Optional ending line number (1-indexed, inclusive).
            max_lines: Maximum number of lines to return (default: 200).

        Line selection logic:
            - If both line_start and line_end are provided: return those lines exactly
            - Else if total_lines <= max_lines: return all lines
            - Else if line_start is provided: return max_lines starting from line_start
            - Else if line_end is provided: return max_lines ending at line_end
            - Else: return first max_lines lines

        Returns:
            Dictionary with editing cell information or error status
        """
        try:
            snapshot = self.bridge.get_active_cell(fresh_ms=fresh_ms)

            if snapshot is None:
                return {
                    "cell_content": None,
                    "cell_id": None,
                    "captured": False,
                    "message": "No editing cell captured from frontend. Make sure the JupyterLab extension is installed and enabled.",
                    "source": "active_cell_bridge",
                    "bridge_status": self.bridge.get_bridge_status(),
                }

            # Calculate age
            now_ms = time.time() * 1000
            age_ms = now_ms - snapshot.get("ts_ms", 0)

            # Get full cell content
            full_text = snapshot.get("text", "")
            all_lines = full_text.splitlines()
            total_lines = len(all_lines)

            # Determine line range based on provided parameters
            if line_start is not None and line_end is not None:
                # Both provided: use exact range
                start = line_start - 1  # Convert to 0-indexed
                end = line_end  # Keep 1-indexed for slice end
            elif total_lines <= max_lines:
                # Small enough: return all lines
                start = 0
                end = total_lines
            elif line_start is not None:
                # Start provided: return max_lines from line_start
                start = line_start - 1
                end = start + max_lines
            elif line_end is not None:
                # End provided: return max_lines ending at line_end
                end = line_end
                start = max(0, end - max_lines)
            else:
                # Nothing provided: return first max_lines
                start = 0
                end = max_lines

            # Clamp to valid range - don't error if range is outside content
            start = max(0, min(start, total_lines))
            end = max(start, min(end, total_lines))

            # Extract requested lines (empty if range is beyond content)
            selected_lines = all_lines[start:end] if total_lines > 0 else []
            cell_content = "\n".join(selected_lines)

            # Create response
            return {
                "cell_content": cell_content,
                "cell_id": snapshot.get("cell_id"),
                "cell_index": snapshot.get("cell_index"),
                "cell_type": snapshot.get("cell_type", "code"),
                "notebook_path": snapshot.get("notebook_path"),
                "cursor": snapshot.get("cursor"),
                "selection": snapshot.get("selection"),
                "client_id": snapshot.get("client_id"),
                "length": len(cell_content),
                "lines": len(selected_lines),
                "total_lines": total_lines,
                "line_start": start + 1,  # Report as 1-indexed
                "line_end": end,
                "truncated": end < total_lines or start > 0,
                "captured": True,
                "age_ms": age_ms,
                "age_seconds": age_ms / 1000,
                "timestamp_ms": snapshot.get("ts_ms"),
                "source": "jupyterlab_frontend",
                "fresh_requested": fresh_ms is not None,
                "fresh_threshold_ms": fresh_ms,
                "is_stale": fresh_ms is not None and age_ms > fresh_ms,
            }

        except Exception as e:
            logger.error(f"Error in get_editing_cell: {e}")
            return {
                "cell_content": None,
                "cell_id": None,
                "captured": False,
                "error": str(e),
                "source": "error",
                "bridge_status": self.bridge.get_bridge_status(),
            }

    async def move_cursor(self, target: str) -> Dict[str, Any]:
        """Move cursor to a different cell in the notebook.

        Changes which cell is currently active (selected) in JupyterLab.
        This is a SAFE operation as it only changes selection without modifying content.

        Args:
            target: Where to move the cursor:
                   - "above": Move to cell above current
                   - "below": Move to cell below current
                   - "bottom": Move to the last cell in the notebook (by file order)
                   - "index:N": Move to cell at position N (0-indexed) - works for ALL cells

        Returns:
            Dictionary with operation status, old index, and new index
        """
        try:
            # Validate target
            valid_targets = ["above", "below", "bottom"]
            if target not in valid_targets and not target.startswith("index:"):
                return {
                    "success": False,
                    "error": f"Invalid target '{target}'. Must be 'above', 'below', 'bottom', or 'index:N'",
                    "source": "validation_error",
                }

            # Send move cursor request to frontend
            # Use asyncio.to_thread to avoid blocking the event loop during wait
            result = await asyncio.to_thread(self.bridge.move_cursor, target)

            # Add metadata
            result.update(
                {
                    "source": "move_cursor",
                    "bridge_status": self.bridge.get_bridge_status(),
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in move_cursor: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "target_requested": target,
            }
