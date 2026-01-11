"""
Read-only QCoDeS tools for the Jupyter MCP server.

These tools provide safe, read-only access to QCoDeS instruments
and Jupyter notebook functionality without arbitrary code execution.
"""

import asyncio
import re
import time
import logging
from typing import Dict, List, Any, Optional, Union

try:
    from measureit.sweep.base_sweep import BaseSweep
    from measureit.sweep.progress import SweepState
except ImportError:  # pragma: no cover - MeasureIt optional
    BaseSweep = None  # type: ignore[assignment]

try:
    from .cache import ReadCache, RateLimiter, ParameterPoller
    from . import active_cell_bridge
except ImportError:
    # Handle case when running as standalone script
    from cache import ReadCache, RateLimiter, ParameterPoller
    import active_cell_bridge

logger = logging.getLogger(__name__)

# Delay in seconds between checks for wait_for_all_sweeps and wait_for_sweep
WAIT_DELAY = 1.0


class QCodesReadOnlyTools:
    """Read-only tools for QCoDeS instruments and Jupyter integration."""

    def __init__(self, ipython, min_interval_s: float = 0.2):
        self.ipython = ipython
        self.namespace = ipython.user_ns
        self.min_interval_s = min_interval_s

        # Initialize caching and rate limiting
        self.cache = ReadCache()
        self.rate_limiter = RateLimiter(min_interval_s)
        self.poller = ParameterPoller(self.cache, self.rate_limiter)

        # Initialize current cell capture
        self.current_cell_content = None
        self.current_cell_id = None
        self.current_cell_timestamp = None

        # Register pre_run_cell event to capture current cell
        if ipython and hasattr(ipython, "events"):
            ipython.events.register("pre_run_cell", self._capture_current_cell)
            logger.debug("Registered pre_run_cell event for current cell capture")
        else:
            logger.warning(
                "Could not register pre_run_cell event - events system unavailable"
            )

        logger.debug("QCoDesReadOnlyTools initialized")

    def _capture_current_cell(self, info):
        """Capture the current cell content before execution.

        Args:
            info: IPython execution info object with raw_cell, cell_id, etc.
        """
        self.current_cell_content = info.raw_cell
        self.current_cell_id = getattr(info, "cell_id", None)
        self.current_cell_timestamp = time.time()
        logger.debug(f"Captured current cell: {len(info.raw_cell)} characters")

    def _get_instrument(self, name: str):
        """Get instrument from namespace."""
        if name not in self.namespace:
            raise ValueError(f"Instrument '{name}' not found in namespace")

        instr = self.namespace[name]

        # Check if it's a QCoDeS instrument
        try:
            from qcodes.instrument.base import InstrumentBase

            if not isinstance(instr, InstrumentBase):
                raise ValueError(f"'{name}' is not a QCoDeS instrument")
        except ImportError:
            # QCoDeS not available, assume it's valid
            pass

        return instr

    def _get_parameter(self, instrument_name: str, parameter_name: str):
        """Get parameter object from instrument, supporting hierarchical paths.

        Args:
            instrument_name: Name of the instrument in namespace
            parameter_name: Parameter name or hierarchical path (e.g., "ch01.voltage", "submodule.param")

        Returns:
            Parameter object
        """
        instr = self._get_instrument(instrument_name)

        # Split parameter path for hierarchical access
        path_parts = parameter_name.split(".")
        current_obj = instr

        # Navigate through the hierarchy
        for i, part in enumerate(path_parts):
            # Check if this is the final parameter
            if i == len(path_parts) - 1:
                # This should be a parameter
                if not hasattr(current_obj, "parameters"):
                    raise ValueError(
                        f"Object '{'.'.join(path_parts[: i + 1])}' has no parameters"
                    )

                if part not in current_obj.parameters:
                    available_params = (
                        list(current_obj.parameters.keys())
                        if hasattr(current_obj, "parameters")
                        else []
                    )
                    raise ValueError(
                        f"Parameter '{part}' not found in '{'.'.join(path_parts[: i + 1])}'. Available parameters: {available_params}"
                    )

                return current_obj.parameters[part]
            else:
                # This should be a submodule or channel
                if (
                    hasattr(current_obj, "submodules")
                    and part in current_obj.submodules
                ):
                    current_obj = current_obj.submodules[part]
                elif hasattr(current_obj, part):
                    # Direct attribute access (e.g., ch01, ch02)
                    current_obj = getattr(current_obj, part)
                else:
                    # Look in submodules for the part
                    available_subs = []
                    if hasattr(current_obj, "submodules"):
                        available_subs.extend(current_obj.submodules.keys())
                    # Add direct attributes that look like channels/submodules
                    for attr_name in dir(current_obj):
                        if not attr_name.startswith("_"):
                            attr_obj = getattr(current_obj, attr_name, None)
                            if (
                                hasattr(attr_obj, "parameters")
                                and attr_name not in available_subs
                            ):
                                available_subs.append(attr_name)

                    raise ValueError(
                        f"Submodule/channel '{part}' not found in '{'.'.join(path_parts[: i + 1])}'. Available: {available_subs}"
                    )

        # If we get here with no path parts, it's a direct parameter
        if not hasattr(instr, "parameters"):
            raise ValueError(f"Instrument '{instrument_name}' has no parameters")

        if parameter_name not in instr.parameters:
            available_params = list(instr.parameters.keys())
            raise ValueError(
                f"Parameter '{parameter_name}' not found in '{instrument_name}'. Available parameters: {available_params}"
            )

        return instr.parameters[parameter_name]

    def _discover_parameters_recursive(
        self, obj, prefix="", depth=0, max_depth=4, visited=None
    ):
        """Recursively discover all parameters in an object hierarchy with cycle protection.

        Args:
            obj: The object to search (instrument, submodule, channel)
            prefix: Current path prefix (e.g., "ch01" or "submodule.channel")
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops
            visited: Set of already visited object IDs

        Returns:
            List of parameter paths
        """
        # Initialize visited set on first call
        if visited is None:
            visited = set()

        # Stop at max depth to prevent infinite recursion
        if depth >= max_depth:
            logger.debug(f"Reached max depth {max_depth} at prefix '{prefix}'")
            return []

        # Prevent circular references by tracking visited objects
        obj_id = id(obj)
        if obj_id in visited:
            logger.debug(f"Skipping already visited object at prefix '{prefix}'")
            return []

        visited.add(obj_id)
        parameters = []

        try:
            # Add direct parameters
            if hasattr(obj, "parameters"):
                for param_name in obj.parameters.keys():
                    full_path = f"{prefix}.{param_name}" if prefix else param_name
                    parameters.append(full_path)

            # Recursively check submodules
            if hasattr(obj, "submodules"):
                for sub_name, sub_obj in obj.submodules.items():
                    if sub_obj is not None:
                        sub_prefix = f"{prefix}.{sub_name}" if prefix else sub_name
                        sub_params = self._discover_parameters_recursive(
                            sub_obj, sub_prefix, depth + 1, max_depth, visited
                        )
                        parameters.extend(sub_params)

            # Check common channel/submodule attribute names (whitelist approach)
            channel_attrs = [
                "ch01",
                "ch02",
                "ch03",
                "ch04",
                "ch05",
                "ch06",
                "ch07",
                "ch08",
                "ch1",
                "ch2",
                "ch3",
                "ch4",
                "ch5",
                "ch6",
                "ch7",
                "ch8",
                "channel",
                "channels",
                "gate",
                "gates",
                "source",
                "drain",
            ]

            for attr_name in channel_attrs:
                if hasattr(obj, attr_name):
                    try:
                        attr_obj = getattr(obj, attr_name, None)
                        if attr_obj is not None and hasattr(attr_obj, "parameters"):
                            # Skip if already covered by submodules
                            if (
                                hasattr(obj, "submodules")
                                and attr_name in obj.submodules
                            ):
                                continue
                            attr_prefix = (
                                f"{prefix}.{attr_name}" if prefix else attr_name
                            )
                            attr_params = self._discover_parameters_recursive(
                                attr_obj, attr_prefix, depth + 1, max_depth, visited
                            )
                            parameters.extend(attr_params)
                    except Exception as e:
                        logger.debug(f"Error accessing attribute '{attr_name}': {e}")
                        continue

        except Exception as e:
            logger.error(f"Error in parameter discovery at prefix '{prefix}': {e}")
        finally:
            # Remove from visited set to allow revisiting through other paths at same level
            visited.discard(obj_id)

        return parameters

    def _make_cache_key(self, instrument_name: str, parameter_path: str) -> tuple:
        """Create a cache key for a parameter.

        Args:
            instrument_name: Name of the instrument
            parameter_path: Full parameter path (e.g., "voltage", "ch01.voltage", "submodule.param")

        Returns:
            Tuple cache key
        """
        return (instrument_name, parameter_path)

    async def _read_parameter_live(
        self, instrument_name: str, parameter_name: str
    ) -> Any:
        """Read parameter value directly from hardware.

        Args:
            instrument_name: Name of the instrument
            parameter_name: Parameter path (supports hierarchical paths like "ch01.voltage")
        """
        param = self._get_parameter(instrument_name, parameter_name)

        # Use asyncio.to_thread to avoid blocking the event loop
        return await asyncio.to_thread(param.get)

    # Core read-only tools

    async def list_instruments(self, max_depth: int = 4) -> List[Dict[str, Any]]:
        """List all QCoDeS instruments in the namespace with hierarchical parameter discovery.

        Args:
            max_depth: Maximum hierarchy depth to search (default: 4, prevents infinite loops)
        """
        instruments = []

        for name, obj in self.namespace.items():
            try:
                from qcodes.instrument.base import InstrumentBase

                if isinstance(obj, InstrumentBase):
                    # Discover all parameters recursively with depth limit and timeout
                    try:
                        # Add timeout protection (5 seconds max)
                        all_parameters = await asyncio.wait_for(
                            asyncio.to_thread(
                                self._discover_parameters_recursive,
                                obj,
                                max_depth=max_depth,
                            ),
                            timeout=5.0,
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Parameter discovery timed out for instrument '{name}', using basic parameters"
                        )
                        # Fall back to direct parameters only
                        all_parameters = (
                            list(obj.parameters.keys())
                            if hasattr(obj, "parameters")
                            else []
                        )

                    # Group parameters by hierarchy level
                    direct_params = []
                    channel_params = {}

                    for param_path in all_parameters:
                        if "." not in param_path:
                            direct_params.append(param_path)
                        else:
                            parts = param_path.split(".")
                            channel = parts[0]
                            if channel not in channel_params:
                                channel_params[channel] = []
                            channel_params[channel].append(param_path)

                    instruments.append(
                        {
                            "name": name,
                            "type": obj.__class__.__name__,
                            "module": obj.__class__.__module__,
                            "label": getattr(obj, "label", name),
                            "address": getattr(obj, "address", None),
                            "parameters": direct_params,
                            "all_parameters": all_parameters,
                            "channel_parameters": channel_params,
                            "has_channels": len(channel_params) > 0,
                            "parameter_count": len(all_parameters),
                        }
                    )
            except (ImportError, AttributeError):
                # Not a QCoDeS instrument or QCoDeS not available
                continue

        logger.debug(f"Found {len(instruments)} QCoDeS instruments")
        return instruments

    async def instrument_info(
        self, name: str, with_values: bool = False, max_depth: int = 4
    ) -> Dict[str, Any]:
        """Get detailed information about an instrument with hierarchical parameter structure.

        Args:
            name: Instrument name or "*" to list all instruments
            with_values: Include cached parameter values
            max_depth: Maximum hierarchy depth to search (default: 4, prevents infinite loops)
        """
        # Handle wildcard to list all instruments
        if name == "*":
            instruments = await self.list_instruments(max_depth=max_depth)
            return {
                "instruments": instruments,
                "count": len(instruments),
                "note": "Use specific instrument name for detailed info with cached values",
            }

        instr = self._get_instrument(name)

        # Get basic snapshot
        snapshot = await asyncio.to_thread(instr.snapshot, update=False)

        # Enhance with hierarchical information with depth limit and timeout
        try:
            # Add timeout protection (5 seconds max)
            all_parameters = await asyncio.wait_for(
                asyncio.to_thread(
                    self._discover_parameters_recursive, instr, max_depth=max_depth
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Parameter discovery timed out for instrument '{name}', using basic parameters"
            )
            # Fall back to direct parameters only
            all_parameters = (
                list(instr.parameters.keys()) if hasattr(instr, "parameters") else []
            )

        # Group parameters by hierarchy
        direct_params = []
        channel_info = {}

        for param_path in all_parameters:
            if "." not in param_path:
                direct_params.append(param_path)
            else:
                parts = param_path.split(".")
                channel = parts[0]
                if channel not in channel_info:
                    channel_info[channel] = {"parameters": [], "full_paths": []}
                channel_info[channel]["parameters"].append(".".join(parts[1:]))
                channel_info[channel]["full_paths"].append(param_path)

        # Add cached values if requested
        cached_values = {}
        if with_values:
            for param_path in all_parameters:
                key = self._make_cache_key(name, param_path)
                cached = await self.cache.get(key)
                if cached:
                    value, timestamp = cached
                    cached_values[param_path] = {
                        "value": value,
                        "timestamp": timestamp,
                        "age_seconds": time.time() - timestamp,
                    }

        # Enhance snapshot with hierarchy info
        enhanced_snapshot = {
            **snapshot,
            "hierarchy_info": {
                "all_parameters": all_parameters,
                "direct_parameters": direct_params,
                "channel_info": channel_info,
                "parameter_count": len(all_parameters),
                "has_channels": len(channel_info) > 0,
            },
        }

        if with_values and cached_values:
            enhanced_snapshot["cached_parameter_values"] = cached_values

        return enhanced_snapshot

    async def get_parameter_info(
        self, instrument_name: str, parameter_name: str, detailed: bool = False
    ) -> Dict[str, Any]:
        """Get metadata information about a specific parameter.

        Args:
            instrument_name: Name of the instrument in namespace
            parameter_name: Parameter path (e.g., "voltage", "ch01.voltage")
            detailed: If False (default), return core metadata only;
                     if True, return all available metadata including cache

        Returns:
            Dictionary with parameter metadata
        """
        param = self._get_parameter(instrument_name, parameter_name)

        # Core metadata (always returned)
        info: Dict[str, Any] = {
            "name": param.name,
            "label": getattr(param, "label", None),
            "unit": getattr(param, "unit", None),
            "gettable": getattr(param, "gettable", False),
            "settable": getattr(param, "settable", False),
        }

        # Get validator info (vals) - contains limits
        vals = getattr(param, "vals", None)
        if vals is not None:
            vals_type = type(vals).__name__
            vals_info: Dict[str, Any] = {"type": vals_type}
            # Extract min/max for range-based validators (Numbers, Ints, etc.)
            if hasattr(vals, "_min_value"):
                vals_info["min_value"] = vals._min_value
            if hasattr(vals, "_max_value"):
                vals_info["max_value"] = vals._max_value
            # Only include valid_values for truly enumerated validators (Enum, OnOff, Bool)
            # NOT for Numbers/Ints which have valid_values as (min, max) tuple
            if vals_type in ("Enum", "OnOff", "Bool", "Strings"):
                if hasattr(vals, "_valid_values"):
                    vals_info["valid_values"] = list(vals._valid_values)
                elif hasattr(vals, "valid_values"):
                    vals_info["valid_values"] = list(vals.valid_values)
            info["vals"] = vals_info
        else:
            info["vals"] = None

        if not detailed:
            return info

        # Extended metadata (only when detailed=True)
        info["full_name"] = getattr(param, "full_name", None)
        info["instrument"] = instrument_name
        info["parameter_path"] = parameter_name

        # Scale and offset (only on some parameter types like DelegateParameter)
        if hasattr(param, "scale"):
            info["scale"] = param.scale
        if hasattr(param, "offset"):
            info["offset"] = param.offset

        # Additional optional attributes
        info["docstring"] = getattr(param, "__doc__", None)
        info["post_delay"] = getattr(param, "post_delay", None)
        info["step"] = getattr(param, "step", None)
        info["inter_delay"] = getattr(param, "inter_delay", None)

        # Cache information
        cache = getattr(param, "cache", None)
        if cache is not None:
            cache_info: Dict[str, Any] = {}
            try:
                cache_info["raw_value"] = cache.raw_value
                cache_info["timestamp"] = cache.timestamp
                if cache.timestamp:
                    cache_info["age_seconds"] = time.time() - cache.timestamp
            except Exception:
                cache_info["error"] = "Unable to read cache"
            info["cache"] = cache_info

        return info

    async def _get_single_parameter_value(
        self, instrument_name: str, parameter_name: str, fresh: bool = False
    ) -> Dict[str, Any]:
        """Internal method to get a single parameter value with caching and rate limiting.

        Args:
            instrument_name: Name of the instrument
            parameter_name: Parameter path (supports hierarchical paths like "ch01.voltage")
            fresh: Force fresh read from hardware
        """
        key = self._make_cache_key(instrument_name, parameter_name)
        now = time.time()

        # Check cache first (fast path for non-fresh reads)
        cached = await self.cache.get(key)

        if not fresh and cached:
            value, timestamp = cached
            return {
                "value": value,
                "timestamp": timestamp,
                "age_seconds": now - timestamp,
                "source": "cache",
                "stale": False,
            }

        # Check rate limiting BEFORE any live read (applies to all live reads)
        can_access = await self.rate_limiter.can_access(instrument_name)

        if not can_access:
            # Rate limited - return cached value if available
            if cached:
                value, timestamp = cached
                return {
                    "value": value,
                    "timestamp": timestamp,
                    "age_seconds": now - timestamp,
                    "source": "cache",
                    "stale": True,
                    "rate_limited": True,
                    "message": f"Rate limited (min interval: {self.min_interval_s}s)",
                }
            # No cache - must wait for rate limit before reading
            # (fall through to live read which will wait_if_needed)

        # Read fresh value from hardware
        try:
            async with self.rate_limiter.get_instrument_lock(instrument_name):
                await self.rate_limiter.wait_if_needed(instrument_name)

                value = await self._read_parameter_live(instrument_name, parameter_name)
                read_time = time.time()

                await self.cache.set(key, value, read_time)
                await self.rate_limiter.record_access(instrument_name)

                return {
                    "value": value,
                    "timestamp": read_time,
                    "age_seconds": 0,
                    "source": "live",
                    "stale": False,
                }

        except Exception as e:
            logger.error(f"Error reading {instrument_name}.{parameter_name}: {e}")

            # Fall back to cached value if available
            if cached:
                value, timestamp = cached
                return {
                    "value": value,
                    "timestamp": timestamp,
                    "age_seconds": now - timestamp,
                    "source": "cache",
                    "stale": True,
                    "error": str(e),
                }
            else:
                raise

    async def get_parameter_values(
        self, queries: Union[List[Dict[str, Any]], Dict[str, Any]]
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """Get parameter values - supports both single parameter and batch queries.

        Args:
            queries: Single query dict or list of query dicts
                    Single: {"instrument": "name", "parameter": "param", "fresh": false}
                    Batch: [{"instrument": "name1", "parameter": "param1"}, ...]

        Returns:
            Single result dict or list of result dicts
        """
        # Handle single query case
        if isinstance(queries, dict):
            try:
                result = await self._get_single_parameter_value(
                    queries["instrument"],
                    queries["parameter"],
                    queries.get("fresh", False),
                )
                result["query"] = queries
                return result
            except Exception as e:
                return {"query": queries, "error": str(e), "source": "error"}

        # Handle batch query case
        results = []
        for query in queries:
            try:
                result = await self._get_single_parameter_value(
                    query["instrument"], query["parameter"], query.get("fresh", False)
                )
                result["query"] = query
                results.append(result)

            except Exception as e:
                results.append({"query": query, "error": str(e), "source": "error"})

        return results

    async def station_snapshot(self) -> Dict[str, Any]:
        """Get full station snapshot without parameter values."""
        station = None

        # Look for QCoDeS Station in namespace
        for name, obj in self.namespace.items():
            try:
                from qcodes.station import Station

                if isinstance(obj, Station):
                    station = obj
                    break
            except ImportError:
                continue

        if station is None:
            # No station found, return basic info
            instruments = await self.list_instruments()
            return {
                "station": None,
                "instruments": instruments,
                "message": "No QCoDeS Station found in namespace",
            }

        # Get station snapshot
        try:
            snapshot = await asyncio.to_thread(station.snapshot, update=False)
            return snapshot
        except Exception as e:
            logger.error(f"Error getting station snapshot: {e}")
            raise

    async def list_variables(
        self, type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List variables in the Jupyter namespace."""
        # Normalize "null" string to None (some MCP clients serialize null as "null")
        if type_filter and type_filter.strip().lower() == "null":
            type_filter = None

        variables = []

        for name, obj in self.namespace.items():
            # Skip private variables and built-ins
            if name.startswith("_"):
                continue

            var_type = type(obj).__name__
            var_module = getattr(type(obj), "__module__", "builtins")

            # Apply type filter if specified
            if type_filter and type_filter.lower() not in var_type.lower():
                continue

            variables.append(
                {
                    "name": name,
                    "type": var_type,
                    "module": var_module,
                    "size": len(obj) if hasattr(obj, "__len__") else None,
                    "repr": (
                        repr(obj)[:100] + "..." if len(repr(obj)) > 100 else repr(obj)
                    ),
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

    # Editing cell tools
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
            snapshot = active_cell_bridge.get_active_cell(fresh_ms=fresh_ms)

            if snapshot is None:
                return {
                    "cell_content": None,
                    "cell_id": None,
                    "captured": False,
                    "message": "No editing cell captured from frontend. Make sure the JupyterLab extension is installed and enabled.",
                    "source": "active_cell_bridge",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
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
                "bridge_status": active_cell_bridge.get_bridge_status(),
            }

    async def update_editing_cell(self, content: str) -> Dict[str, Any]:
        """Update the content of the currently editing cell in JupyterLab frontend.

        This sends a request to the frontend to update the currently active cell
        with the provided content.

        Args:
            content: New Python code content to set in the active cell

        Returns:
            Dictionary with update status and response details
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Validate input
            if not isinstance(content, str):
                return {
                    "success": False,
                    "error": f"Content must be a string, got {type(content).__name__}",
                    "content": None,
                }

            # Send update request to frontend
            result = active_cell_bridge.update_active_cell(content)

            # Add metadata
            result.update(
                {
                    "source": "update_editing_cell",
                    "content_preview": (
                        content[:100] + "..." if len(content) > 100 else content
                    ),
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in update_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": content[:100] + "..." if len(content) > 100 else content,
                "source": "error",
            }

    async def _get_cell_output(
        self, cell_number: int, timeout_s: float = 0.5, bypass_cache: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Request and retrieve cell output from JupyterLab frontend.

        Args:
            cell_number: Execution count of the cell
            timeout_s: Timeout for waiting for response
            bypass_cache: If True, skip cache and always request fresh from frontend.
                         Use this for final fetch to ensure late outputs are captured.

        Returns:
            Dictionary with output data or None if not available
        """
        # First check cache (unless bypassing)
        if not bypass_cache:
            cached = active_cell_bridge.get_cached_cell_output(cell_number)
            if cached:
                return cached

        # Request from frontend
        result = active_cell_bridge.get_cell_outputs([cell_number], timeout_s=timeout_s)
        if not result.get("success"):
            return None

        # Wait a bit for response to arrive and be cached (non-blocking)
        await asyncio.sleep(0.1)

        # Check cache again
        return active_cell_bridge.get_cached_cell_output(cell_number)

    def _process_frontend_output(
        self,
        frontend_output: Optional[Dict[str, Any]],
        target_count: int,
        cell_input: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Process frontend output and return result dict if error or output found.

        Args:
            frontend_output: Output from frontend (may be None)
            target_count: Cell execution count
            cell_input: Cell source code

        Returns:
            Result dict if error or output found, None otherwise
        """
        if not frontend_output:
            return None

        outputs = frontend_output.get("outputs", [])

        # Check if outputs contain an error
        for output in outputs:
            if output.get("type") == "error":
                return {
                    "status": "error",
                    "has_error": True,
                    "has_output": True,
                    "cell_number": target_count,
                    "input": cell_input,
                    "error_type": output.get("ename", "Unknown"),
                    "error_message": output.get("evalue", ""),
                    "traceback": "\n".join(output.get("traceback", [])),
                    "outputs": outputs,
                }

        # Check if outputs contain data
        if frontend_output.get("has_output"):
            return {
                "status": "completed",
                "has_error": False,
                "has_output": True,
                "cell_number": target_count,
                "input": cell_input,
                "outputs": outputs,
            }

        return None

    async def _wait_for_execution(
        self, initial_count: int, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Wait for cell execution to complete.

        Two-phase approach:
        1. Wait for execution_count to increase (execution started)
        2. Wait for last_execution_result to change (execution completed)

        The primary completion signal is `last_execution_result` identity change,
        which is set at the END of IPython's run_cell. This handles all cells
        including long-running silent ones (e.g., `time.sleep(10); x = 1`).

        After completion is detected, a short grace period allows frontend
        outputs to propagate before returning.

        Args:
            initial_count: The execution_count before triggering execution
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            Dictionary with execution status and output
        """
        import sys
        import traceback as tb_module

        start_time = time.time()
        poll_interval = 0.1  # 100ms
        OUTPUT_GRACE = 0.5  # seconds to wait for frontend outputs after completion

        # Capture initial state for identity comparison
        initial_last_traceback = getattr(sys, "last_traceback", None)
        initial_last_result = getattr(self.ipython, "last_execution_result", None)

        target_count = None
        completion_detected_time = None  # When last_execution_result changed
        post_completion_fetch_done = False  # Track if we've done final frontend fetch

        while (time.time() - start_time) < timeout:
            current_count = getattr(self.ipython, "execution_count", 0)

            # Phase 1: Wait for execution to START
            if target_count is None:
                if current_count > initial_count:
                    target_count = current_count
                    # Execution started - continue to phase 2
                else:
                    await asyncio.sleep(poll_interval)
                    continue

            # Phase 2: Wait for execution to COMPLETE
            In = self.ipython.user_ns.get("In", [])
            Out = self.ipython.user_ns.get("Out", {})
            cell_input = In[target_count] if target_count < len(In) else ""

            # Check 1: Error detected (compare traceback object identity, not type)
            current_last_traceback = getattr(sys, "last_traceback", None)
            if (
                current_last_traceback is not None
                and current_last_traceback is not initial_last_traceback
            ):
                # New error occurred - return immediately
                error_type = getattr(sys, "last_type", None)
                return {
                    "status": "error",
                    "has_error": True,
                    "has_output": False,
                    "cell_number": target_count,
                    "input": cell_input,
                    "error_type": error_type.__name__ if error_type else "Unknown",
                    "error_message": str(getattr(sys, "last_value", "")),
                    "traceback": "".join(tb_module.format_tb(current_last_traceback)),
                }

            # Check 2: last_execution_result changed (primary completion signal)
            current_last_result = getattr(self.ipython, "last_execution_result", None)
            execution_completed = (
                current_last_result is not None
                and current_last_result is not initial_last_result
            )

            if execution_completed and completion_detected_time is None:
                completion_detected_time = time.time()

            # Check 3: Frontend outputs
            # Strategy: Before completion, poll frontend. After completion, only check
            # cache during grace period to avoid spamming frontend. After grace elapses,
            # do ONE final frontend fetch to catch late outputs.
            if completion_detected_time is None:
                # Before completion: poll frontend as usual
                frontend_output = await self._get_cell_output(target_count)
            else:
                # After completion: only check cache (no new frontend requests)
                frontend_output = active_cell_bridge.get_cached_cell_output(
                    target_count
                )

            # Process frontend output (check for errors or data)
            result = self._process_frontend_output(
                frontend_output, target_count, cell_input
            )
            if result:
                return result

            # Check 4: Out cache populated (expression result)
            if target_count in Out:
                return {
                    "status": "completed",
                    "has_error": False,
                    "has_output": True,
                    "cell_number": target_count,
                    "input": cell_input,
                    "output": str(Out[target_count]),
                }

            # Check 5: Execution count advanced beyond target (another cell ran)
            # Re-read execution_count to catch rapid changes since loop start
            # (Windows asyncio.sleep has ~15.6ms resolution, causing race conditions)
            fresh_count = getattr(self.ipython, "execution_count", 0)
            if fresh_count > target_count:
                if not post_completion_fetch_done:
                    post_completion_fetch_done = True
                    final_output = await self._get_cell_output(
                        target_count, bypass_cache=True
                    )
                    result = self._process_frontend_output(
                        final_output, target_count, cell_input
                    )
                    if result:
                        return result
                return {
                    "status": "completed",
                    "has_error": False,
                    "has_output": False,
                    "cell_number": target_count,
                    "input": cell_input,
                    "message": "Cell executed successfully with no output",
                }

            # Check 6: Completion detected + grace period elapsed (silent cell)
            # After grace period, do ONE final frontend fetch to catch late outputs
            if completion_detected_time is not None:
                grace_elapsed = time.time() - completion_detected_time
                if grace_elapsed >= OUTPUT_GRACE:
                    # Final frontend fetch after grace period (only once)
                    if not post_completion_fetch_done:
                        post_completion_fetch_done = True
                        final_output = await self._get_cell_output(
                            target_count, bypass_cache=True
                        )
                        result = self._process_frontend_output(
                            final_output, target_count, cell_input
                        )
                        if result:
                            return result

                    # No output after final fetch - return completed with no output
                    return {
                        "status": "completed",
                        "has_error": False,
                        "has_output": False,
                        "cell_number": target_count,
                        "input": cell_input,
                        "message": "Cell executed (no output)",
                    }

            await asyncio.sleep(poll_interval)

        # Timeout
        return {
            "status": "timeout",
            "has_error": False,
            "has_output": False,
            "cell_number": target_count or 0,
            "message": f"Timeout after {timeout}s waiting for execution to complete",
        }

    async def execute_editing_cell(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Execute the currently editing cell and wait for output.

        UNSAFE: This tool executes code in the active notebook cell. The code will run
        in the frontend with output appearing in the notebook.

        Args:
            timeout: Maximum seconds to wait for execution to complete (default: 30)

        Returns:
            Dictionary with execution status AND output/error details
        """
        try:
            # 1. Capture current execution count and cell text from bridge
            initial_count = getattr(self.ipython, "execution_count", 0)
            # Get cell text from bridge snapshot BEFORE execution (most reliable)
            bridge_snapshot = active_cell_bridge.get_active_cell()
            cell_text_from_bridge = (
                bridge_snapshot.get("text", "") if bridge_snapshot else ""
            )

            # 2. Send execution request to frontend
            exec_result = active_cell_bridge.execute_active_cell()

            if not exec_result.get("success"):
                exec_result.update(
                    {
                        "source": "execute_editing_cell",
                        "warning": "UNSAFE: Attempted to execute code but request failed",
                    }
                )
                return exec_result

            # 3. Wait for execution to complete (polls execution_count)
            output_result = await self._wait_for_execution(initial_count, timeout)

            # 4. Handle timeout
            if output_result.get("status") == "timeout":
                return {
                    "success": True,
                    "executed": True,
                    "execution_count": 0,
                    **output_result,
                    "source": "execute_editing_cell",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                    "warning": "UNSAFE: Code was executed in the active cell",
                }

            # 5. Combine results
            combined_result = {
                "success": True,
                "executed": True,
                "execution_count": output_result.get("cell_number", 0),
                **output_result,
                "source": "execute_editing_cell",
                "bridge_status": active_cell_bridge.get_bridge_status(),
                "warning": "UNSAFE: Code was executed in the active cell",
            }

            # 6. Detect if a MeasureIt sweep was started and extract sweep names
            # Use bridge text (captured before execution) as fallback if IPython In[] is empty
            cell_input = output_result.get("input", "") or cell_text_from_bridge
            sweep_pattern = r"(\w+)\.start\s*\("
            sweep_matches = re.findall(sweep_pattern, cell_input)

            if sweep_matches:
                combined_result["sweep_detected"] = True
                combined_result["sweep_names"] = sweep_matches
                if len(sweep_matches) == 1:
                    combined_result["suggestion"] = (
                        f"A sweep appears to have been started. "
                        f"Use measureit_wait_for_sweep with sweep name "
                        f"'{sweep_matches[0]}' to wait for completion."
                    )
                else:
                    names = ", ".join(f"'{n}'" for n in sweep_matches)
                    combined_result["suggestion"] = (
                        f"Multiple sweeps appear to have been started ({names}). "
                        f"Use measureit_wait_for_sweep with sweep names or "
                        f"measureit_wait_for_all_sweeps() to wait for completion."
                    )

            return combined_result

        except Exception as e:
            logger.error(f"Error in execute_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to execute code but failed",
            }

    async def add_new_cell(
        self, cell_type: str = "code", position: str = "below", content: str = ""
    ) -> Dict[str, Any]:
        """Add a new cell in the notebook.

        UNSAFE: This tool adds new cells to the notebook. The cell will be created
        relative to the currently active cell.

        Args:
            cell_type: Type of cell to create ("code", "markdown", "raw")
            position: Position relative to active cell ("above", "below")
            content: Initial content for the new cell

        Returns:
            Dictionary with creation status and response details
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Send add cell request to frontend
            result = active_cell_bridge.add_new_cell(cell_type, position, content)

            # Add metadata
            result.update(
                {
                    "source": "add_new_cell",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                    "warning": "UNSAFE: New cell was added to the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in add_new_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to add cell but failed",
            }

    async def delete_editing_cell(self) -> Dict[str, Any]:
        """Delete the currently editing cell.

        UNSAFE: This tool deletes the currently active cell from the notebook.
        Use with caution as this action cannot be undone easily.

        Returns:
            Dictionary with deletion status and response details
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Send delete cell request to frontend
            result = active_cell_bridge.delete_editing_cell()

            # Add metadata
            result.update(
                {
                    "source": "delete_editing_cell",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cell was deleted from the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in delete_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to delete cell but failed",
            }

    async def apply_patch(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """Apply a patch to the current cell content.

        UNSAFE: This tool modifies the content of the currently active cell by
        replacing the first occurrence of old_text with new_text.

        Args:
            old_text: Text to find and replace
            new_text: Text to replace with

        Returns:
            Dictionary with patch status and response details
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Send patch request to frontend
            result = active_cell_bridge.apply_patch(old_text, new_text)

            # Add metadata
            result.update(
                {
                    "source": "apply_patch",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cell content was modified via patch",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in apply_patch: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to apply patch but failed",
            }

    async def delete_cells_by_number(self, cell_numbers: List[int]) -> Dict[str, Any]:
        """Delete multiple cells by their execution count numbers.

        UNSAFE: This tool deletes cells from the notebook by their execution count.
        Use with caution as this action cannot be undone easily.

        Args:
            cell_numbers: List of execution count numbers (e.g., [1, 2, 5])

        Returns:
            Dictionary with deletion status and detailed results for each cell
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Send delete cells by number request to frontend
            result = active_cell_bridge.delete_cells_by_number(cell_numbers)

            # Add metadata
            result.update(
                {
                    "source": "delete_cells_by_number",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
                    "warning": "UNSAFE: Cells were deleted from the notebook",
                }
            )

            return result

        except Exception as e:
            logger.error(f"Error in delete_cells_by_number: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "cell_numbers_requested": cell_numbers,
                "warning": "UNSAFE: Attempted to delete cells but failed",
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
                   - "<number>": Move to cell with that execution count (e.g., "5" for [5])

        Returns:
            Dictionary with operation status, old index, and new index
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge

            # Validate target
            valid_targets = ["above", "below", "bottom"]
            if target not in valid_targets:
                try:
                    int(target)  # Check if it's a number
                except ValueError:
                    return {
                        "success": False,
                        "error": f"Invalid target '{target}'. Must be 'above', 'below', 'bottom', or a cell number",
                        "source": "validation_error",
                    }

            # Send move cursor request to frontend
            # Use asyncio.to_thread to avoid blocking the event loop during wait
            result = await asyncio.to_thread(active_cell_bridge.move_cursor, target)

            # Add metadata
            result.update(
                {
                    "source": "move_cursor",
                    "bridge_status": active_cell_bridge.get_bridge_status(),
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

    # # Subscription tools

    # async def subscribe_parameter(self, instrument_name: str, parameter_name: str,
    #                             interval_s: float = 1.0) -> Dict[str, Any]:
    #     """Subscribe to periodic parameter updates."""
    #     # Validate parameters
    #     self._get_parameter(instrument_name, parameter_name)

    #     # Create a parameter reader function
    #     async def get_param_func(inst_name, param_name):
    #         return await self._read_parameter_live(inst_name, param_name)

    #     await self.poller.subscribe(
    #         instrument_name, parameter_name, interval_s, get_param_func
    #     )

    #     return {
    #         "instrument": instrument_name,
    #         "parameter": parameter_name,
    #         "interval_s": interval_s,
    #         "status": "subscribed"
    #     }

    # async def unsubscribe_parameter(self, instrument_name: str, parameter_name: str) -> Dict[str, Any]:
    #     """Unsubscribe from parameter updates."""
    #     await self.poller.unsubscribe(instrument_name, parameter_name)

    #     return {
    #         "instrument": instrument_name,
    #         "parameter": parameter_name,
    #         "status": "unsubscribed"
    #     }

    # async def list_subscriptions(self) -> Dict[str, Any]:
    #     """List current parameter subscriptions."""
    #     return self.poller.get_subscriptions()

    # # System tools

    # async def get_cache_stats(self) -> Dict[str, Any]:
    #     """Get cache statistics."""
    #     return await self.cache.get_stats()

    # async def clear_cache(self) -> Dict[str, Any]:
    #     """Clear the parameter cache."""
    #     await self.cache.clear()
    #     return {"status": "cache_cleared"}

    async def wait_for_all_sweeps(self, timeout: float | None = None) -> Dict[str, Any]:
        """Wait until all running measureit sweeps finish.

        Waits until all currently running sweeps have stopped running and returns information about them.

        Args:
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            Dict containing:
                sweeps: Dict mapping variable names to Dicts of information about the initially running sweeps as in get_measureit_status, empty if no sweeps were running.
                error: str (if any error occurred, including timeout or sweep error)
                timed_out: bool (True if timeout was reached)
                sweep_error: bool (True if any sweep ended with error state)
                errored_sweeps: list of sweep names that had errors (if any)
        """
        try:
            status = await self.get_measureit_status()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("wait_for_all_sweeps failed to get status: %s", exc)
            return {"sweeps": None, "error": str(exc)}

        if status.get("error"):
            return {"sweeps": None, "error": status["error"]}

        sweeps = status["sweeps"]
        initial_running = {
            k: v for k, v in sweeps.items() if v["state"] in ("ramping", "running")
        }

        if not initial_running:
            return {"sweeps": None}

        start_time = time.time()
        while True:
            await asyncio.sleep(WAIT_DELAY)

            # Check timeout
            if timeout is not None and (time.time() - start_time) > timeout:
                running_names = [
                    k
                    for k, v in initial_running.items()
                    if v["state"] in ("ramping", "running")
                ]
                return {
                    "sweeps": initial_running,
                    "error": f"Timeout after {timeout}s waiting for sweeps to complete",
                    "timed_out": True,
                    "kill_suggestion": (
                        ", ".join(
                            [f"measureit_kill_sweep('{n}')" for n in running_names]
                        )
                        if running_names
                        else None
                    ),
                }

            status = await self.get_measureit_status()

            if status.get("error"):
                return {"sweeps": initial_running, "error": status["error"]}

            current_sweeps = status["sweeps"]
            still_running = False
            errored_sweeps = []

            for k in initial_running.keys():
                if k in current_sweeps:
                    initial_running[k] = current_sweeps[k]
                    state = current_sweeps[k]["state"]

                    if state in ("ramping", "running"):
                        still_running = True
                    elif state == "error":
                        errored_sweeps.append(k)

            # If any sweep has errored, return immediately with error info
            if errored_sweeps:
                error_messages = []
                for name in errored_sweeps:
                    sweep_info = initial_running.get(name, {})
                    msg = sweep_info.get(
                        "error_message", f"Sweep '{name}' ended with error"
                    )
                    error_messages.append(msg)

                return {
                    "sweeps": initial_running,
                    "error": "; ".join(error_messages),
                    "sweep_error": True,
                    "errored_sweeps": errored_sweeps,
                    "kill_suggestion": ", ".join(
                        [f"measureit_kill_sweep('{n}')" for n in errored_sweeps]
                    ),
                }

            if not still_running:
                break

        return {"sweeps": initial_running}

    async def wait_for_sweep(
        self, var_name: str, timeout: float | None = None
    ) -> Dict[str, Any]:
        """Wait for a measureit sweep with a given variable name to finish.

        Waits for the sweep with the given name to stop running and returns information about it.

        Args:
            var_name: Name of the sweep variable to wait for.
            timeout: Maximum time to wait in seconds. If None, wait indefinitely.

        Returns:
            Dict containing:
                sweep: Dict of information about the sweep as in get_measureit_status, or None if no
                running sweep with this name exists.
                error: str (if any error occurred, including timeout or sweep error)
                timed_out: bool (True if timeout was reached)
                sweep_error: bool (True if sweep ended with error state)
        """
        status = await self.get_measureit_status()
        if status.get("error"):
            return {"sweep": None, "error": status["error"]}
        target = status["sweeps"].get(var_name)

        if not target or target["state"] not in ("ramping", "running"):
            return {"sweep": None}

        start_time = time.time()
        while True:
            await asyncio.sleep(WAIT_DELAY)

            # Check timeout
            if timeout is not None and (time.time() - start_time) > timeout:
                return {
                    "sweep": target,
                    "error": f"Timeout after {timeout}s waiting for sweep '{var_name}' to complete",
                    "timed_out": True,
                    "kill_suggestion": f"Use measureit_kill_sweep('{var_name}') to stop the sweep and release resources",
                }

            status = await self.get_measureit_status()
            if status.get("error"):
                return {"sweep": target, "error": status["error"]}
            target = status["sweeps"].get(var_name)

            if not target:
                break

            # Check for error state - return early with error message
            if target["state"] == "error":
                error_msg = target.get("error_message", "Sweep ended with error")
                return {
                    "sweep": target,
                    "error": error_msg,
                    "sweep_error": True,
                    "kill_suggestion": f"Use measureit_kill_sweep('{var_name}') to release resources after error",
                }

            if target["state"] not in ["ramping", "running"]:
                break

        return {"sweep": target}

    async def get_measureit_status(self) -> Dict[str, Any]:
        """Check if any measureit sweep is currently running.

        Returns information about active measureit sweeps in the notebook namespace,
        including sweep type, status, and basic configuration if available.

        Returns:
            Dict containing:
                - active: bool - whether any sweep is active
                - sweeps: Dict mapping variable names to Dicts of active sweep information:
                    "variable_name" (str),  "type" (str), "module_name" (str), "state" (str), "progress" (float or None), "time_elapsed" (float or None), "time_remaining" (float or None)
                - error: str (if any error occurred)
        """
        try:
            if BaseSweep is None:
                return {
                    "active": False,
                    "sweeps": {},
                    "error": "MeasureIt library not available",
                }

            result = {"active": False, "sweeps": {}}

            # Look for MeasureIt sweep objects in the namespace
            for var_name, var_value in self.namespace.items():
                # Skip private/internal variables
                if var_name.startswith("_"):
                    continue

                if isinstance(var_value, BaseSweep):
                    sweep_info = {
                        "variable_name": var_name,
                        "type": type(var_value).__name__,
                        "module": getattr(var_value, "__module__", ""),
                    }
                    progress_state = var_value.progressState
                    sweep_info["state"] = progress_state.state.value
                    result["active"] = result["active"] or (
                        sweep_info["state"] in ("ramping", "running")
                    )
                    sweep_info["progress"] = progress_state.progress
                    sweep_info["time_elapsed"] = progress_state.time_elapsed
                    sweep_info["time_remaining"] = progress_state.time_remaining

                    # Capture error information if present
                    error_message = getattr(progress_state, "error_message", None)
                    if error_message:
                        sweep_info["error_message"] = error_message

                    result["sweeps"][var_name] = sweep_info

            return result

        except Exception as e:
            logger.error(f"Error checking MeasureIt status: {e}")
            return {"active": False, "sweeps": {}, "error": str(e)}

    async def kill_sweep(self, var_name: str) -> Dict[str, Any]:
        """Kill a running MeasureIt sweep to release resources.

        UNSAFE: This tool stops a running sweep, which may leave instruments
        in an intermediate state. Use when a sweep needs to be terminated
        due to timeout, error, or user request.

        Args:
            var_name: Name of the sweep variable in the notebook namespace

        Returns:
            Dict containing:
                success: bool - whether the kill was successful
                sweep_name: str - name of the sweep
                previous_state: str - state before kill
                error: str (if any error occurred)
        """
        try:
            if BaseSweep is None:
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": "MeasureIt library not available",
                }

            # Check if the variable exists in namespace
            if var_name not in self.namespace:
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": f"Variable '{var_name}' not found in namespace",
                }

            sweep = self.namespace[var_name]

            # Verify it's a sweep object
            if not isinstance(sweep, BaseSweep):
                return {
                    "success": False,
                    "sweep_name": var_name,
                    "error": f"Variable '{var_name}' is not a MeasureIt sweep (got {type(sweep).__name__})",
                }

            # Get state before kill
            previous_state = sweep.progressState.state.value

            # Kill the sweep
            await asyncio.to_thread(sweep.kill)

            # Verify the sweep was killed
            new_state = sweep.progressState.state.value

            return {
                "success": True,
                "sweep_name": var_name,
                "sweep_type": type(sweep).__name__,
                "previous_state": previous_state,
                "new_state": new_state,
                "message": f"Sweep '{var_name}' killed successfully. Resources released.",
                "warning": "UNSAFE: Sweep was terminated. Instruments may need re-initialization.",
            }

        except Exception as e:
            logger.error(f"Error killing sweep '{var_name}': {e}")
            return {
                "success": False,
                "sweep_name": var_name,
                "error": str(e),
            }

    async def cleanup(self):
        """Clean up resources."""
        await self.poller.stop_all()
        await self.cache.clear()
