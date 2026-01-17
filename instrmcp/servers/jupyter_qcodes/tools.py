"""
Read-only QCoDeS tools for the Jupyter MCP server.

This module provides the QCodesReadOnlyTools facade class that delegates
to domain-specific backends for QCodes, notebook, and MeasureIt operations.

The facade maintains backward compatibility while the actual implementation
is split across:
- backend/qcodes.py: QCodes instrument operations
- backend/notebook.py: Read-only notebook operations
- backend/notebook_unsafe.py: Unsafe notebook operations (modification, execution)
- options/measureit/backend.py: MeasureIt sweep operations (optional)
"""

import time
import logging
from typing import Dict, List, Any, Optional, Union

from .cache import ReadCache, RateLimiter, ParameterPoller
from .backend.base import SharedState
from .backend.qcodes import QCodesBackend
from .backend.notebook import NotebookBackend
from .backend.notebook_unsafe import NotebookUnsafeBackend

logger = logging.getLogger(__name__)


class QCodesReadOnlyTools:
    """Facade for read-only QCoDeS instruments and Jupyter integration.

    This class delegates to domain-specific backends while maintaining
    backward compatibility with the original monolithic interface.
    """

    def __init__(self, ipython, min_interval_s: float = 0.2):
        """Initialize the tools facade.

        Args:
            ipython: IPython instance for accessing notebook namespace
            min_interval_s: Minimum interval between hardware reads (rate limiting)
        """
        self.ipython = ipython
        self.namespace = ipython.user_ns
        self.min_interval_s = min_interval_s

        # Initialize caching and rate limiting
        self.cache = ReadCache()
        self.rate_limiter = RateLimiter(min_interval_s)
        self.poller = ParameterPoller(self.cache, self.rate_limiter)

        # Initialize current cell capture state
        self.current_cell_content = None
        self.current_cell_id = None
        self.current_cell_timestamp = None

        # Create shared state for all backends
        self._state = SharedState(
            ipython=ipython,
            namespace=ipython.user_ns,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            poller=self.poller,
            min_interval_s=min_interval_s,
        )

        # Initialize backends
        self._qcodes = QCodesBackend(self._state)
        self._notebook = NotebookBackend(self._state)
        self._notebook_unsafe = NotebookUnsafeBackend(self._state, self._notebook)
        self._measureit = None  # Lazy-loaded when needed

        # Register pre_run_cell event to capture current cell
        if ipython and hasattr(ipython, "events"):
            ipython.events.register("pre_run_cell", self._capture_current_cell)
            logger.debug("Registered pre_run_cell event for current cell capture")
        else:
            logger.warning(
                "Could not register pre_run_cell event - events system unavailable"
            )

        logger.debug("QCoDesReadOnlyTools initialized with backend delegation")

    def _capture_current_cell(self, info):
        """Capture the current cell content before execution.

        Args:
            info: IPython execution info object with raw_cell, cell_id, etc.
        """
        self.current_cell_content = info.raw_cell
        self.current_cell_id = getattr(info, "cell_id", None)
        self.current_cell_timestamp = time.time()

        # Also update shared state
        self._state.current_cell_content = self.current_cell_content
        self._state.current_cell_id = self.current_cell_id
        self._state.current_cell_timestamp = self.current_cell_timestamp

        logger.debug(f"Captured current cell: {len(info.raw_cell)} characters")

    @property
    def measureit_backend(self):
        """Lazy-load MeasureIt backend when first accessed."""
        if self._measureit is None:
            try:
                from .options.measureit.backend import MeasureItBackend

                self._measureit = MeasureItBackend(self._state)
            except ImportError:
                logger.debug("MeasureIt backend not available")
                raise
        return self._measureit

    # =========================================================================
    # QCodes Backend Delegation
    # =========================================================================

    async def list_instruments(self, max_depth: int = 4) -> List[Dict[str, Any]]:
        """List all QCoDeS instruments in the namespace."""
        return await self._qcodes.list_instruments(max_depth)

    async def instrument_info(
        self, name: str, with_values: bool = False, max_depth: int = 4
    ) -> Dict[str, Any]:
        """Get detailed information about an instrument."""
        return await self._qcodes.instrument_info(name, with_values, max_depth)

    async def get_parameter_info(
        self, instrument_name: str, parameter_name: str, detailed: bool = False
    ) -> Dict[str, Any]:
        """Get metadata information about a specific parameter."""
        return await self._qcodes.get_parameter_info(
            instrument_name, parameter_name, detailed
        )

    async def get_parameter_values(
        self, queries: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get parameter values - supports both single parameter and batch queries."""
        return await self._qcodes.get_parameter_values(queries)

    async def get_station_snapshot(self) -> Dict[str, Any]:
        """Get full station snapshot without parameter values."""
        return await self._qcodes.get_station_snapshot()

    async def cleanup(self):
        """Clean up resources."""
        return await self._qcodes.cleanup()

    # =========================================================================
    # Notebook Backend Delegation (Read-Only)
    # =========================================================================

    async def list_variables(
        self, type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List variables in the Jupyter namespace."""
        return await self._notebook.list_variables(type_filter)

    async def get_variable_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a variable."""
        return await self._notebook.get_variable_info(name)

    async def get_editing_cell(
        self,
        fresh_ms: Optional[int] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        max_lines: int = 200,
    ) -> Dict[str, Any]:
        """Get the currently editing cell content from JupyterLab frontend."""
        return await self._notebook.get_editing_cell(
            fresh_ms, line_start, line_end, max_lines
        )

    async def move_cursor(self, target: str) -> Dict[str, Any]:
        """Move cursor to a different cell in the notebook."""
        return await self._notebook.move_cursor(target)

    # =========================================================================
    # Notebook Unsafe Backend Delegation
    # =========================================================================

    async def update_editing_cell(self, content: str) -> Dict[str, Any]:
        """Update the content of the currently editing cell."""
        return await self._notebook_unsafe.update_editing_cell(content)

    async def execute_editing_cell(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Execute the currently editing cell and wait for output."""
        return await self._notebook_unsafe.execute_editing_cell(timeout)

    async def add_new_cell(
        self,
        cell_type: str = "code",
        position: str = "below",
        content: str = "",
    ) -> Dict[str, Any]:
        """Add a new cell in the notebook."""
        return await self._notebook_unsafe.add_new_cell(cell_type, position, content)

    async def delete_editing_cell(self) -> Dict[str, Any]:
        """Delete the currently editing cell."""
        return await self._notebook_unsafe.delete_editing_cell()

    async def apply_patch(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """Apply a patch to the current cell content."""
        return await self._notebook_unsafe.apply_patch(old_text, new_text)

    async def delete_cells_by_number(self, cell_numbers: List[int]) -> Dict[str, Any]:
        """Delete multiple cells by their execution count numbers."""
        return await self._notebook_unsafe.delete_cells_by_number(cell_numbers)

    # =========================================================================
    # MeasureIt Backend Delegation
    # =========================================================================

    async def get_measureit_status(self) -> Dict[str, Any]:
        """Check if any measureit sweep is currently running."""
        return await self.measureit_backend.get_measureit_status()

    async def wait_for_sweep(
        self, var_name: str, timeout: Optional[float] = None, kill: bool = True
    ) -> Dict[str, Any]:
        """Wait for a measureit sweep to finish."""
        return await self.measureit_backend.wait_for_sweep(var_name, timeout, kill)

    async def wait_for_all_sweeps(
        self, timeout: Optional[float] = None, kill: bool = True
    ) -> Dict[str, Any]:
        """Wait until all running measureit sweeps finish."""
        return await self.measureit_backend.wait_for_all_sweeps(timeout, kill)

    async def kill_sweep(self, var_name: str) -> Dict[str, Any]:
        """Kill a running MeasureIt sweep to release resources."""
        return await self.measureit_backend.kill_sweep(var_name)

    async def kill_all_sweeps(self) -> Dict[str, Any]:
        """Kill all MeasureIt sweeps to release resources."""
        return await self.measureit_backend.kill_all_sweeps()

    # =========================================================================
    # Internal Method Delegation (for backward compatibility with tests)
    # =========================================================================

    async def _wait_for_execution(
        self, initial_count: int, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Wait for cell execution to complete (internal method)."""
        return await self._notebook_unsafe._wait_for_execution(initial_count, timeout)

    async def _get_cell_output(
        self, cell_number: int, timeout_s: float = 0.5, bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get cell output from frontend (internal method)."""
        return await self._notebook_unsafe._get_cell_output(
            cell_number, timeout_s, bypass_cache
        )

    async def _get_single_parameter_value(
        self, instrument_name: str, parameter_name: str, fresh: bool = False
    ) -> Dict[str, Any]:
        """Get a single parameter value with caching (internal method)."""
        return await self._qcodes._get_single_parameter_value(
            instrument_name, parameter_name, fresh
        )

    def _make_cache_key(self, instrument_name: str, parameter_path: str) -> tuple:
        """Create a cache key for a parameter (internal method)."""
        return self._qcodes._make_cache_key(instrument_name, parameter_path)
