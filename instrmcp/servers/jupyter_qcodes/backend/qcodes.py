"""
QCodes backend for instrument operations.

Handles all QCodes-related operations including:
- Instrument discovery and information
- Parameter reading with caching and rate limiting
- Station snapshot
- Cleanup
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Set

from .base import BaseBackend, SharedState

logger = logging.getLogger(__name__)


class QCodesBackend(BaseBackend):
    """Backend for QCodes instrument operations and cache management."""

    _VALUE_KEYS: Set[str] = {"value", "raw_value", "timestamp", "ts"}

    def __init__(self, state: SharedState):
        """Initialize QCodes backend.

        Args:
            state: SharedState instance containing shared resources
        """
        super().__init__(state)

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

    def _strip_parameter_values(self, node: Any) -> None:
        """Remove parameter value fields from a QCoDeS snapshot in-place."""
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "parameters" and isinstance(value, dict):
                    for param in value.values():
                        if isinstance(param, dict):
                            for value_key in self._VALUE_KEYS:
                                param.pop(value_key, None)
                    continue
                self._strip_parameter_values(value)
        elif isinstance(node, list):
            for item in node:
                self._strip_parameter_values(item)

    def _cache_age_seconds(self, timestamp: Any) -> Optional[float]:
        """Compute cache age in seconds for float or datetime timestamps."""
        if timestamp is None:
            return None
        if isinstance(timestamp, (int, float)):
            return time.time() - float(timestamp)
        if isinstance(timestamp, datetime):
            now = datetime.now(tz=timestamp.tzinfo)
            return (now - timestamp).total_seconds()
        return None

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
        if not with_values:
            self._strip_parameter_values(snapshot)

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
            except Exception:
                cache_info["error"] = "Unable to read cache raw_value"
            try:
                timestamp = cache.timestamp
                cache_info["timestamp"] = timestamp
                age_seconds = self._cache_age_seconds(timestamp)
                if age_seconds is not None:
                    cache_info["age_seconds"] = age_seconds
            except Exception:
                cache_info.setdefault("error", "Unable to read cache timestamp")
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

    async def get_station_snapshot(self) -> Dict[str, Any]:
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

    async def cleanup(self):
        """Clean up resources."""
        await self.poller.stop_all()
        await self.cache.clear()
