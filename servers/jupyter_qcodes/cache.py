"""
Caching and rate limiting for QCoDeS parameter reads.
"""

import asyncio
import time
import logging
from typing import Dict, Tuple, Any, Optional

logger = logging.getLogger(__name__)


class ReadCache:
    """Thread-safe cache for QCoDeS parameter values with timestamps."""
    
    def __init__(self):
        # (instrument_name, parameter_name) -> (value, timestamp)
        self.data: Dict[Tuple[str, str], Tuple[Any, float]] = {}
        self.lock = asyncio.Lock()
    
    async def get(self, key: Tuple[str, str]) -> Optional[Tuple[Any, float]]:
        """Get cached value and timestamp for a parameter."""
        async with self.lock:
            return self.data.get(key)
    
    async def set(self, key: Tuple[str, str], value: Any, timestamp: Optional[float] = None):
        """Set cached value with timestamp for a parameter."""
        if timestamp is None:
            timestamp = time.time()
        async with self.lock:
            self.data[key] = (value, timestamp)
    
    async def clear(self):
        """Clear all cached values."""
        async with self.lock:
            self.data.clear()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        async with self.lock:
            return {
                "size": len(self.data),
                "keys": list(self.data.keys()),
                "oldest_timestamp": min((ts for _, ts in self.data.values()), default=0),
                "newest_timestamp": max((ts for _, ts in self.data.values()), default=0)
            }


class RateLimiter:
    """Rate limiter for QCoDeS instrument access."""
    
    def __init__(self, min_interval_s: float = 0.2):
        self.min_interval_s = min_interval_s
        # instrument_name -> last_access_time
        self.last_access: Dict[str, float] = {}
        # Per-instrument locks to serialize access
        self.locks: Dict[str, asyncio.Lock] = {}
        self.lock = asyncio.Lock()
    
    def get_instrument_lock(self, instrument_name: str) -> asyncio.Lock:
        """Get or create a lock for an instrument."""
        if instrument_name not in self.locks:
            self.locks[instrument_name] = asyncio.Lock()
        return self.locks[instrument_name]
    
    async def can_access(self, instrument_name: str) -> bool:
        """Check if instrument can be accessed (rate limit check)."""
        async with self.lock:
            last_time = self.last_access.get(instrument_name, 0)
            return (time.time() - last_time) >= self.min_interval_s
    
    async def record_access(self, instrument_name: str):
        """Record that instrument was accessed."""
        async with self.lock:
            self.last_access[instrument_name] = time.time()
    
    async def wait_if_needed(self, instrument_name: str):
        """Wait if rate limit would be exceeded."""
        async with self.lock:
            last_time = self.last_access.get(instrument_name, 0)
            elapsed = time.time() - last_time
            if elapsed < self.min_interval_s:
                wait_time = self.min_interval_s - elapsed
                logger.debug(f"Rate limiting {instrument_name}: waiting {wait_time:.3f}s")
                await asyncio.sleep(wait_time)


class ParameterPoller:
    """Background poller for subscribed parameters."""
    
    def __init__(self, cache: ReadCache, rate_limiter: RateLimiter):
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.subscriptions: Dict[Tuple[str, str], float] = {}  # (inst, param) -> interval_s
        self.tasks: Dict[Tuple[str, str], asyncio.Task] = {}
        self.running = False
    
    async def subscribe(self, instrument_name: str, parameter_name: str, 
                      interval_s: float, get_parameter_func):
        """Subscribe to periodic parameter updates."""
        key = (instrument_name, parameter_name)
        
        # Cancel existing subscription if any
        await self.unsubscribe(instrument_name, parameter_name)
        
        self.subscriptions[key] = interval_s
        
        # Start polling task
        task = asyncio.create_task(
            self._poll_parameter(instrument_name, parameter_name, interval_s, get_parameter_func)
        )
        self.tasks[key] = task
        
        logger.info(f"Subscribed to {instrument_name}.{parameter_name} at {interval_s}s interval")
    
    async def unsubscribe(self, instrument_name: str, parameter_name: str):
        """Unsubscribe from parameter updates."""
        key = (instrument_name, parameter_name)
        
        if key in self.tasks:
            task = self.tasks.pop(key)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self.subscriptions.pop(key, None)
        logger.info(f"Unsubscribed from {instrument_name}.{parameter_name}")
    
    async def _poll_parameter(self, instrument_name: str, parameter_name: str, 
                             interval_s: float, get_parameter_func):
        """Continuously poll a parameter at the specified interval."""
        key = (instrument_name, parameter_name)
        
        while key in self.subscriptions:
            try:
                # Use the rate limiter and instrument lock
                async with self.rate_limiter.get_instrument_lock(instrument_name):
                    await self.rate_limiter.wait_if_needed(instrument_name)
                    
                    # Get the parameter value
                    value = await asyncio.to_thread(get_parameter_func, instrument_name, parameter_name)
                    
                    # Cache the value
                    await self.cache.set(key, value)
                    await self.rate_limiter.record_access(instrument_name)
                    
                    logger.debug(f"Polled {instrument_name}.{parameter_name} = {value}")
            
            except Exception as e:
                logger.error(f"Error polling {instrument_name}.{parameter_name}: {e}")
            
            # Wait for next poll
            await asyncio.sleep(interval_s)
    
    async def stop_all(self):
        """Stop all polling tasks."""
        for key in list(self.tasks.keys()):
            instrument_name, parameter_name = key
            await self.unsubscribe(instrument_name, parameter_name)
        self.running = False
    
    def get_subscriptions(self) -> Dict[str, Any]:
        """Get current subscription status."""
        return {
            "subscriptions": list(self.subscriptions.keys()),
            "active_tasks": len(self.tasks),
            "intervals": dict(self.subscriptions)
        }