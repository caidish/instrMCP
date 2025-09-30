"""
Unit tests for cache.py module.

Tests ReadCache, RateLimiter, and ParameterPoller classes used for
managing QCodes parameter reads and rate limiting.
"""

import pytest
import asyncio
import time
from instrmcp.servers.jupyter_qcodes.cache import ReadCache, RateLimiter, ParameterPoller


class TestReadCache:
    """Test ReadCache class for parameter value caching."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test cache is initialized empty."""
        cache = ReadCache()
        stats = await cache.get_stats()
        assert stats["size"] == 0
        assert stats["keys"] == []

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self):
        """Test setting and getting cached values."""
        cache = ReadCache()
        key = ("mock_dac", "ch01.voltage")
        value = 3.14
        timestamp = time.time()

        await cache.set(key, value, timestamp)
        result = await cache.get(key)

        assert result is not None
        assert result[0] == value
        assert result[1] == timestamp

    @pytest.mark.asyncio
    async def test_cache_get_nonexistent(self):
        """Test getting a non-existent key returns None."""
        cache = ReadCache()
        result = await cache.get(("nonexistent", "parameter"))
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_update(self):
        """Test updating an existing cache entry."""
        cache = ReadCache()
        key = ("mock_dac", "voltage")

        # First set
        await cache.set(key, 1.0, time.time())
        result1 = await cache.get(key)
        assert result1[0] == 1.0

        # Update
        new_time = time.time() + 1
        await cache.set(key, 2.0, new_time)
        result2 = await cache.get(key)
        assert result2[0] == 2.0
        assert result2[1] == new_time

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test clearing all cached values."""
        cache = ReadCache()
        await cache.set(("inst1", "param1"), 1.0)
        await cache.set(("inst2", "param2"), 2.0)

        stats_before = await cache.get_stats()
        assert stats_before["size"] == 2

        await cache.clear()

        stats_after = await cache.get_stats()
        assert stats_after["size"] == 0

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test cache statistics reporting."""
        cache = ReadCache()
        t1 = time.time()
        await cache.set(("inst1", "param1"), 1.0, t1)
        await asyncio.sleep(0.01)
        t2 = time.time()
        await cache.set(("inst2", "param2"), 2.0, t2)

        stats = await cache.get_stats()
        assert stats["size"] == 2
        assert len(stats["keys"]) == 2
        assert stats["oldest_timestamp"] == pytest.approx(t1, rel=0.01)
        assert stats["newest_timestamp"] == pytest.approx(t2, rel=0.01)

    @pytest.mark.asyncio
    async def test_cache_thread_safety(self):
        """Test cache is thread-safe with concurrent access."""
        cache = ReadCache()
        key = ("inst", "param")

        async def writer(value):
            await cache.set(key, value)
            await asyncio.sleep(0.001)

        async def reader():
            result = await cache.get(key)
            return result

        # Run concurrent writes and reads
        await asyncio.gather(
            writer(1), writer(2), writer(3),
            reader(), reader(), reader()
        )

        # Should complete without errors
        result = await cache.get(key)
        assert result is not None
        assert result[0] in [1, 2, 3]


class TestRateLimiter:
    """Test RateLimiter class for instrument access rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test rate limiter is initialized properly."""
        limiter = RateLimiter(min_interval_s=0.1)
        # Should allow first access immediately
        can_access = await limiter.can_access("inst1")
        assert can_access is True

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_rapid_access(self):
        """Test rate limiter blocks rapid consecutive access."""
        limiter = RateLimiter(min_interval_s=0.1)
        instrument_name = "inst1"

        # First access should be allowed
        assert await limiter.can_access(instrument_name) is True
        await limiter.record_access(instrument_name)

        # Immediate second access should be blocked
        assert await limiter.can_access(instrument_name) is False

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_after_interval(self):
        """Test rate limiter allows access after minimum interval."""
        limiter = RateLimiter(min_interval_s=0.05)
        instrument_name = "inst1"

        # First access
        await limiter.record_access(instrument_name)

        # Wait for interval to pass
        await asyncio.sleep(0.06)

        # Should be allowed now
        assert await limiter.can_access(instrument_name) is True

    @pytest.mark.asyncio
    async def test_rate_limiter_independent_instruments(self):
        """Test rate limiter treats different instruments independently."""
        limiter = RateLimiter(min_interval_s=0.1)
        inst1 = "inst1"
        inst2 = "inst2"

        # Access inst1
        await limiter.record_access(inst1)

        # inst2 should still be accessible
        assert await limiter.can_access(inst2) is True

    @pytest.mark.asyncio
    async def test_rate_limiter_wait_if_needed(self):
        """Test waiting if rate limit would be exceeded."""
        limiter = RateLimiter(min_interval_s=0.05)
        instrument_name = "inst1"

        # Record access
        await limiter.record_access(instrument_name)

        # Wait if needed
        start_time = time.time()
        await limiter.wait_if_needed(instrument_name)
        elapsed = time.time() - start_time

        # Should have waited approximately the minimum interval
        assert elapsed >= 0.04  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_rate_limiter_get_instrument_lock(self):
        """Test getting instrument-specific locks."""
        limiter = RateLimiter(min_interval_s=0.1)
        instrument_name = "inst1"

        # Get lock twice - should return the same lock
        lock1 = limiter.get_instrument_lock(instrument_name)
        lock2 = limiter.get_instrument_lock(instrument_name)

        assert lock1 is lock2
        assert isinstance(lock1, asyncio.Lock)


class TestParameterPoller:
    """Test ParameterPoller class for background parameter polling."""

    @pytest.mark.asyncio
    async def test_poller_initialization(self):
        """Test poller is initialized properly."""
        cache = ReadCache()
        limiter = RateLimiter(min_interval_s=0.1)
        poller = ParameterPoller(cache, limiter)

        # Should initialize without errors
        assert poller.cache == cache
        assert poller.rate_limiter == limiter
        assert poller.subscriptions == {}
        assert poller.tasks == {}

    @pytest.mark.asyncio
    async def test_poller_get_subscriptions(self):
        """Test getting subscription status."""
        cache = ReadCache()
        limiter = RateLimiter(min_interval_s=0.1)
        poller = ParameterPoller(cache, limiter)

        # Initially empty
        status = poller.get_subscriptions()
        assert status["subscriptions"] == []
        assert status["active_tasks"] == 0

    @pytest.mark.asyncio
    async def test_poller_subscribe_and_unsubscribe(self):
        """Test subscribing and unsubscribing to parameters."""
        cache = ReadCache()
        limiter = RateLimiter(min_interval_s=0.1)
        poller = ParameterPoller(cache, limiter)

        # Mock get function - must NOT be async for asyncio.to_thread
        def mock_get_func(inst, param):
            return 42.0

        # Subscribe
        await poller.subscribe("inst1", "param1", 0.1, mock_get_func)

        assert ("inst1", "param1") in poller.subscriptions
        assert ("inst1", "param1") in poller.tasks

        # Unsubscribe
        await poller.unsubscribe("inst1", "param1")

        assert ("inst1", "param1") not in poller.subscriptions
        assert ("inst1", "param1") not in poller.tasks

    @pytest.mark.asyncio
    async def test_poller_stop_all(self):
        """Test stopping all polling tasks."""
        cache = ReadCache()
        limiter = RateLimiter(min_interval_s=0.1)
        poller = ParameterPoller(cache, limiter)

        # Mock get function - must NOT be async
        def mock_get_func(inst, param):
            return 42.0

        # Subscribe to multiple parameters
        await poller.subscribe("inst1", "param1", 0.1, mock_get_func)
        await poller.subscribe("inst2", "param2", 0.1, mock_get_func)

        assert len(poller.tasks) == 2

        # Stop all
        await poller.stop_all()

        assert len(poller.tasks) == 0
        assert poller.running is False
