"""
Read-only QCoDeS tools for the Jupyter MCP server.

These tools provide safe, read-only access to QCoDeS instruments
and Jupyter notebook functionality without arbitrary code execution.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Union

try:
    from .cache import ReadCache, RateLimiter, ParameterPoller
    from . import active_cell_bridge
except ImportError:
    # Handle case when running as standalone script
    from cache import ReadCache, RateLimiter, ParameterPoller
    import active_cell_bridge

logger = logging.getLogger(__name__)


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
        if ipython and hasattr(ipython, 'events'):
            ipython.events.register('pre_run_cell', self._capture_current_cell)
            logger.debug("Registered pre_run_cell event for current cell capture")
        else:
            logger.warning("Could not register pre_run_cell event - events system unavailable")
        
        logger.info("QCoDesReadOnlyTools initialized")
    
    def _capture_current_cell(self, info):
        """Capture the current cell content before execution.
        
        Args:
            info: IPython execution info object with raw_cell, cell_id, etc.
        """
        self.current_cell_content = info.raw_cell
        self.current_cell_id = getattr(info, 'cell_id', None)
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
        path_parts = parameter_name.split('.')
        current_obj = instr
        
        # Navigate through the hierarchy
        for i, part in enumerate(path_parts):
            # Check if this is the final parameter
            if i == len(path_parts) - 1:
                # This should be a parameter
                if not hasattr(current_obj, 'parameters'):
                    raise ValueError(f"Object '{'.'.join(path_parts[:i+1])}' has no parameters")
                
                if part not in current_obj.parameters:
                    available_params = list(current_obj.parameters.keys()) if hasattr(current_obj, 'parameters') else []
                    raise ValueError(f"Parameter '{part}' not found in '{'.'.join(path_parts[:i+1])}'. Available parameters: {available_params}")
                
                return current_obj.parameters[part]
            else:
                # This should be a submodule or channel
                if hasattr(current_obj, 'submodules') and part in current_obj.submodules:
                    current_obj = current_obj.submodules[part]
                elif hasattr(current_obj, part):
                    # Direct attribute access (e.g., ch01, ch02)
                    current_obj = getattr(current_obj, part)
                else:
                    # Look in submodules for the part
                    available_subs = []
                    if hasattr(current_obj, 'submodules'):
                        available_subs.extend(current_obj.submodules.keys())
                    # Add direct attributes that look like channels/submodules
                    for attr_name in dir(current_obj):
                        if not attr_name.startswith('_'):
                            attr_obj = getattr(current_obj, attr_name, None)
                            if hasattr(attr_obj, 'parameters') and attr_name not in available_subs:
                                available_subs.append(attr_name)
                    
                    raise ValueError(f"Submodule/channel '{part}' not found in '{'.'.join(path_parts[:i+1])}'. Available: {available_subs}")
        
        # If we get here with no path parts, it's a direct parameter
        if not hasattr(instr, 'parameters'):
            raise ValueError(f"Instrument '{instrument_name}' has no parameters")
        
        if parameter_name not in instr.parameters:
            available_params = list(instr.parameters.keys())
            raise ValueError(f"Parameter '{parameter_name}' not found in '{instrument_name}'. Available parameters: {available_params}")
        
        return instr.parameters[parameter_name]
    
    def _discover_parameters_recursive(self, obj, prefix="", depth=0, max_depth=4, visited=None):
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
            if hasattr(obj, 'parameters'):
                for param_name in obj.parameters.keys():
                    full_path = f"{prefix}.{param_name}" if prefix else param_name
                    parameters.append(full_path)
            
            # Recursively check submodules
            if hasattr(obj, 'submodules'):
                for sub_name, sub_obj in obj.submodules.items():
                    if sub_obj is not None:
                        sub_prefix = f"{prefix}.{sub_name}" if prefix else sub_name
                        sub_params = self._discover_parameters_recursive(
                            sub_obj, sub_prefix, depth + 1, max_depth, visited
                        )
                        parameters.extend(sub_params)
            
            # Check common channel/submodule attribute names (whitelist approach)
            channel_attrs = ['ch01', 'ch02', 'ch03', 'ch04', 'ch05', 'ch06', 'ch07', 'ch08',
                           'ch1', 'ch2', 'ch3', 'ch4', 'ch5', 'ch6', 'ch7', 'ch8',
                           'channel', 'channels', 'gate', 'gates', 'source', 'drain']
            
            for attr_name in channel_attrs:
                if hasattr(obj, attr_name):
                    try:
                        attr_obj = getattr(obj, attr_name, None)
                        if attr_obj is not None and hasattr(attr_obj, 'parameters'):
                            # Skip if already covered by submodules
                            if hasattr(obj, 'submodules') and attr_name in obj.submodules:
                                continue
                            attr_prefix = f"{prefix}.{attr_name}" if prefix else attr_name
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

    async def _read_parameter_live(self, instrument_name: str, parameter_name: str) -> Any:
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
                            asyncio.to_thread(self._discover_parameters_recursive, obj, max_depth=max_depth),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Parameter discovery timed out for instrument '{name}', using basic parameters")
                        # Fall back to direct parameters only
                        all_parameters = list(obj.parameters.keys()) if hasattr(obj, 'parameters') else []
                    
                    # Group parameters by hierarchy level
                    direct_params = []
                    channel_params = {}
                    
                    for param_path in all_parameters:
                        if '.' not in param_path:
                            direct_params.append(param_path)
                        else:
                            parts = param_path.split('.')
                            channel = parts[0]
                            if channel not in channel_params:
                                channel_params[channel] = []
                            channel_params[channel].append(param_path)
                    
                    instruments.append({
                        "name": name,
                        "type": obj.__class__.__name__,
                        "module": obj.__class__.__module__,
                        "label": getattr(obj, "label", name),
                        "address": getattr(obj, "address", None),
                        "parameters": direct_params,
                        "all_parameters": all_parameters,
                        "channel_parameters": channel_params,
                        "has_channels": len(channel_params) > 0,
                        "parameter_count": len(all_parameters)
                    })
            except (ImportError, AttributeError):
                # Not a QCoDeS instrument or QCoDeS not available
                continue
        
        logger.debug(f"Found {len(instruments)} QCoDeS instruments")
        return instruments
    
    async def instrument_info(self, name: str, with_values: bool = False, max_depth: int = 4) -> Dict[str, Any]:
        """Get detailed information about an instrument with hierarchical parameter structure.
        
        Args:
            name: Instrument name
            with_values: Include cached parameter values
            max_depth: Maximum hierarchy depth to search (default: 4, prevents infinite loops)
        """
        instr = self._get_instrument(name)
        
        # Get basic snapshot
        snapshot = await asyncio.to_thread(instr.snapshot, update=False)
        
        # Enhance with hierarchical information with depth limit and timeout
        try:
            # Add timeout protection (5 seconds max)
            all_parameters = await asyncio.wait_for(
                asyncio.to_thread(self._discover_parameters_recursive, instr, max_depth=max_depth),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning(f"Parameter discovery timed out for instrument '{name}', using basic parameters")
            # Fall back to direct parameters only
            all_parameters = list(instr.parameters.keys()) if hasattr(instr, 'parameters') else []
        
        # Group parameters by hierarchy
        direct_params = []
        channel_info = {}
        
        for param_path in all_parameters:
            if '.' not in param_path:
                direct_params.append(param_path)
            else:
                parts = param_path.split('.')
                channel = parts[0]
                if channel not in channel_info:
                    channel_info[channel] = {
                        'parameters': [],
                        'full_paths': []
                    }
                channel_info[channel]['parameters'].append('.'.join(parts[1:]))
                channel_info[channel]['full_paths'].append(param_path)
        
        # Add cached values if requested
        cached_values = {}
        if with_values:
            for param_path in all_parameters:
                key = self._make_cache_key(name, param_path)
                cached = await self.cache.get(key)
                if cached:
                    value, timestamp = cached
                    cached_values[param_path] = {
                        'value': value,
                        'timestamp': timestamp,
                        'age_seconds': time.time() - timestamp
                    }
        
        # Enhance snapshot with hierarchy info
        enhanced_snapshot = {
            **snapshot,
            'hierarchy_info': {
                'all_parameters': all_parameters,
                'direct_parameters': direct_params,
                'channel_info': channel_info,
                'parameter_count': len(all_parameters),
                'has_channels': len(channel_info) > 0
            }
        }
        
        if with_values and cached_values:
            enhanced_snapshot['cached_parameter_values'] = cached_values
        
        return enhanced_snapshot
    
    async def _get_single_parameter_value(self, instrument_name: str, parameter_name: str,
                                        fresh: bool = False) -> Dict[str, Any]:
        """Internal method to get a single parameter value with caching and rate limiting.

        Args:
            instrument_name: Name of the instrument
            parameter_name: Parameter path (supports hierarchical paths like "ch01.voltage")
            fresh: Force fresh read from hardware
        """
        key = self._make_cache_key(instrument_name, parameter_name)
        now = time.time()

        # Check cache first
        cached = await self.cache.get(key)

        if not fresh and cached:
            value, timestamp = cached
            return {
                "value": value,
                "timestamp": timestamp,
                "age_seconds": now - timestamp,
                "source": "cache",
                "stale": False
            }

        # Check rate limiting
        if cached and not await self.rate_limiter.can_access(instrument_name):
            value, timestamp = cached
            return {
                "value": value,
                "timestamp": timestamp,
                "age_seconds": now - timestamp,
                "source": "cache",
                "stale": True,
                "message": f"Rate limited (min interval: {self.min_interval_s}s)"
            }

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
                    "stale": False
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
                    "error": str(e)
                }
            else:
                raise

    async def get_parameter_values(self, queries: Union[List[Dict[str, Any]], Dict[str, Any]]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
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
                    queries.get("fresh", False)
                )
                result["query"] = queries
                return result
            except Exception as e:
                return {
                    "query": queries,
                    "error": str(e),
                    "source": "error"
                }

        # Handle batch query case
        results = []
        for query in queries:
            try:
                result = await self._get_single_parameter_value(
                    query["instrument"],
                    query["parameter"],
                    query.get("fresh", False)
                )
                result["query"] = query
                results.append(result)

            except Exception as e:
                results.append({
                    "query": query,
                    "error": str(e),
                    "source": "error"
                })

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
                "message": "No QCoDeS Station found in namespace"
            }
        
        # Get station snapshot
        try:
            snapshot = await asyncio.to_thread(station.snapshot, update=False)
            return snapshot
        except Exception as e:
            logger.error(f"Error getting station snapshot: {e}")
            raise
    
    async def list_variables(self, type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List variables in the Jupyter namespace."""
        variables = []
        
        for name, obj in self.namespace.items():
            # Skip private variables and built-ins
            if name.startswith('_'):
                continue
            
            var_type = type(obj).__name__
            var_module = getattr(type(obj), '__module__', 'builtins')
            
            # Apply type filter if specified
            if type_filter and type_filter.lower() not in var_type.lower():
                continue
            
            variables.append({
                "name": name,
                "type": var_type,
                "module": var_module,
                "size": len(obj) if hasattr(obj, '__len__') else None,
                "repr": repr(obj)[:100] + "..." if len(repr(obj)) > 100 else repr(obj)
            })
        
        return sorted(variables, key=lambda x: x["name"])
    
    async def get_variable_info(self, name: str) -> Dict[str, Any]:
        """Get detailed information about a variable."""
        if name not in self.namespace:
            raise ValueError(f"Variable '{name}' not found in namespace")
        
        obj = self.namespace[name]
        
        info = {
            "name": name,
            "type": type(obj).__name__,
            "module": getattr(type(obj), '__module__', 'builtins'),
            "size": len(obj) if hasattr(obj, '__len__') else None,
            "attributes": [attr for attr in dir(obj) if not attr.startswith('_')],
            "repr": repr(obj)[:500] + "..." if len(repr(obj)) > 500 else repr(obj)
        }
        
        # Add QCoDeS-specific info if it's an instrument
        try:
            from qcodes.instrument.base import InstrumentBase
            if isinstance(obj, InstrumentBase):
                info["qcodes_instrument"] = True
                info["parameters"] = list(obj.parameters.keys()) if hasattr(obj, 'parameters') else []
                info["address"] = getattr(obj, 'address', None)
        except ImportError:
            info["qcodes_instrument"] = False
        
        return info
    
    # Editing cell tools
    async def get_editing_cell(self, fresh_ms: Optional[int] = None) -> Dict[str, Any]:
        """Get the currently editing cell content from JupyterLab frontend.
        
        This captures the cell that is currently being edited in the frontend.
        
        Args:
            fresh_ms: Optional maximum age in milliseconds. If provided and the
                     cached snapshot is older, will request fresh data from frontend.
        
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
                    "bridge_status": active_cell_bridge.get_bridge_status()
                }
            
            # Calculate age
            now_ms = time.time() * 1000
            age_ms = now_ms - snapshot.get("ts_ms", 0)
            
            # Create response
            return {
                "cell_content": snapshot.get("text", ""),
                "cell_id": snapshot.get("cell_id"),
                "cell_index": snapshot.get("cell_index"),
                "cell_type": snapshot.get("cell_type", "code"),
                "notebook_path": snapshot.get("notebook_path"),
                "cursor": snapshot.get("cursor"),
                "selection": snapshot.get("selection"),
                "client_id": snapshot.get("client_id"),
                "length": len(snapshot.get("text", "")),
                "lines": len(snapshot.get("text", "").splitlines()),
                "captured": True,
                "age_ms": age_ms,
                "age_seconds": age_ms / 1000,
                "timestamp_ms": snapshot.get("ts_ms"),
                "source": "jupyterlab_frontend",
                "fresh_requested": fresh_ms is not None,
                "fresh_threshold_ms": fresh_ms,
                "is_stale": fresh_ms is not None and age_ms > fresh_ms
            }
            
        except Exception as e:
            logger.error(f"Error in get_editing_cell: {e}")
            return {
                "cell_content": None,
                "cell_id": None,
                "captured": False,
                "error": str(e),
                "source": "error",
                "bridge_status": active_cell_bridge.get_bridge_status()
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
                    "content": None
                }
            
            # Send update request to frontend
            result = active_cell_bridge.update_active_cell(content)
            
            # Add metadata
            result.update({
                "source": "update_editing_cell",
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "bridge_status": active_cell_bridge.get_bridge_status()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in update_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": content[:100] + "..." if len(content) > 100 else content,
                "source": "error"
            }
    
    async def execute_editing_cell(self) -> Dict[str, Any]:
        """Execute the currently editing cell in the JupyterLab frontend.
        
        UNSAFE: This tool executes code in the active notebook cell. The code will run
        in the frontend with output appearing in the notebook.
        
        Returns:
            Dictionary with execution status and response details
        """
        try:
            # Import the bridge module
            from . import active_cell_bridge
            
            # Send execution request to frontend
            result = active_cell_bridge.execute_active_cell()
            
            # Add metadata
            result.update({
                "source": "execute_editing_cell",
                "bridge_status": active_cell_bridge.get_bridge_status(),
                "warning": "UNSAFE: Code was executed in the active cell"
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in execute_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to execute code but failed"
            }

    async def add_new_cell(self, cell_type: str = "code", position: str = "below", content: str = "") -> Dict[str, Any]:
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
            result.update({
                "source": "add_new_cell",
                "bridge_status": active_cell_bridge.get_bridge_status(),
                "warning": "UNSAFE: New cell was added to the notebook"
            })

            return result

        except Exception as e:
            logger.error(f"Error in add_new_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to add cell but failed"
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
            result.update({
                "source": "delete_editing_cell",
                "bridge_status": active_cell_bridge.get_bridge_status(),
                "warning": "UNSAFE: Cell was deleted from the notebook"
            })

            return result

        except Exception as e:
            logger.error(f"Error in delete_editing_cell: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to delete cell but failed"
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
            result.update({
                "source": "apply_patch",
                "bridge_status": active_cell_bridge.get_bridge_status(),
                "warning": "UNSAFE: Cell content was modified via patch"
            })

            return result

        except Exception as e:
            logger.error(f"Error in apply_patch: {e}")
            return {
                "success": False,
                "error": str(e),
                "source": "error",
                "warning": "UNSAFE: Attempted to apply patch but failed"
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
    
    async def cleanup(self):
        """Clean up resources."""
        await self.poller.stop_all()
        await self.cache.clear()