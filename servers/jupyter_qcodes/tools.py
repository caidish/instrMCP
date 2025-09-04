"""
Read-only QCoDeS tools for the Jupyter MCP server.

These tools provide safe, read-only access to QCoDeS instruments
and Jupyter notebook functionality without arbitrary code execution.
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Union

from .cache import ReadCache, RateLimiter, ParameterPoller

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
        
        logger.info("QCoDesReadOnlyTools initialized")
    
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
        """Get parameter object from instrument."""
        instr = self._get_instrument(instrument_name)
        
        if not hasattr(instr, 'parameters'):
            raise ValueError(f"Instrument '{instrument_name}' has no parameters")
        
        if parameter_name not in instr.parameters:
            raise ValueError(f"Parameter '{parameter_name}' not found in '{instrument_name}'")
        
        return instr.parameters[parameter_name]
    
    async def _read_parameter_live(self, instrument_name: str, parameter_name: str) -> Any:
        """Read parameter value directly from hardware."""
        param = self._get_parameter(instrument_name, parameter_name)
        
        # Use asyncio.to_thread to avoid blocking the event loop
        return await asyncio.to_thread(param.get)
    
    # Core read-only tools
    
    async def list_instruments(self) -> List[Dict[str, Any]]:
        """List all QCoDeS instruments in the namespace."""
        instruments = []
        
        for name, obj in self.namespace.items():
            try:
                from qcodes.instrument.base import InstrumentBase
                if isinstance(obj, InstrumentBase):
                    instruments.append({
                        "name": name,
                        "type": obj.__class__.__name__,
                        "module": obj.__class__.__module__,
                        "label": getattr(obj, "label", name),
                        "address": getattr(obj, "address", None),
                        "parameters": list(obj.parameters.keys()) if hasattr(obj, 'parameters') else []
                    })
            except (ImportError, AttributeError):
                # Not a QCoDeS instrument or QCoDeS not available
                continue
        
        logger.debug(f"Found {len(instruments)} QCoDeS instruments")
        return instruments
    
    async def instrument_info(self, name: str, with_values: bool = False) -> Dict[str, Any]:
        """Get detailed information about an instrument."""
        instr = self._get_instrument(name)
        
        # Get snapshot (this might be slow if with_values=True)
        if with_values:
            # Only get cached values, don't update from hardware
            snapshot = await asyncio.to_thread(instr.snapshot, update=False)
            
            # Add cached values where available
            if hasattr(instr, 'parameters'):
                for param_name in instr.parameters:
                    key = (name, param_name)
                    cached = await self.cache.get(key)
                    if cached:
                        value, timestamp = cached
                        if 'parameters' in snapshot and param_name in snapshot['parameters']:
                            snapshot['parameters'][param_name]['cached_value'] = value
                            snapshot['parameters'][param_name]['cached_timestamp'] = timestamp
        else:
            snapshot = await asyncio.to_thread(instr.snapshot, update=False)
        
        return snapshot
    
    async def get_parameter_value(self, instrument_name: str, parameter_name: str, 
                                fresh: bool = False) -> Dict[str, Any]:
        """Get parameter value with caching and rate limiting."""
        key = (instrument_name, parameter_name)
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
    
    async def get_parameter_values(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get multiple parameter values in batch."""
        results = []
        
        for query in queries:
            try:
                result = await self.get_parameter_value(
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
    
    # Subscription tools
    
    async def subscribe_parameter(self, instrument_name: str, parameter_name: str, 
                                interval_s: float = 1.0) -> Dict[str, Any]:
        """Subscribe to periodic parameter updates."""
        # Validate parameters
        self._get_parameter(instrument_name, parameter_name)
        
        # Create a parameter reader function
        async def get_param_func(inst_name, param_name):
            return await self._read_parameter_live(inst_name, param_name)
        
        await self.poller.subscribe(
            instrument_name, parameter_name, interval_s, get_param_func
        )
        
        return {
            "instrument": instrument_name,
            "parameter": parameter_name,
            "interval_s": interval_s,
            "status": "subscribed"
        }
    
    async def unsubscribe_parameter(self, instrument_name: str, parameter_name: str) -> Dict[str, Any]:
        """Unsubscribe from parameter updates."""
        await self.poller.unsubscribe(instrument_name, parameter_name)
        
        return {
            "instrument": instrument_name,
            "parameter": parameter_name,
            "status": "unsubscribed"
        }
    
    async def list_subscriptions(self) -> Dict[str, Any]:
        """List current parameter subscriptions."""
        return self.poller.get_subscriptions()
    
    # System tools
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return await self.cache.get_stats()
    
    async def clear_cache(self) -> Dict[str, Any]:
        """Clear the parameter cache."""
        await self.cache.clear()
        return {"status": "cache_cleared"}
    
    async def cleanup(self):
        """Clean up resources."""
        await self.poller.stop_all()
        await self.cache.clear()