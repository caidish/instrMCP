"""
Unit tests for cache.py module.

Tests ReadCache, RateLimiter, and ParameterPoller classes used for
managing QCodes parameter reads and rate limiting.
"""

import pytest
import pytest_asyncio
import asyncio
import time
from instrmcp.servers.jupyter_qcodes.cache import (
    ReadCache,
    RateLimiter,
    ParameterPoller,
)


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
            writer(1), writer(2), writer(3), reader(), reader(), reader()
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


class TestGetSingleParameterValueRateLimiting:
    """Test _get_single_parameter_value method rate limiting behavior.

    These tests verify the fix for unconditional rate limiting checks before all live reads.
    """

    @pytest_asyncio.fixture
    async def mock_tools(self):
        """Create a mock QCodesReadOnlyTools instance with mocked dependencies."""
        from unittest.mock import AsyncMock, MagicMock
        from instrmcp.servers.jupyter_qcodes.tools import QCodesReadOnlyTools

        # Create a minimal mock IPython without events attribute to skip registration
        mock_ipython = MagicMock()
        mock_ipython.user_ns = {}
        # Remove events attribute entirely so hasattr returns False
        if hasattr(mock_ipython, "events"):
            del mock_ipython.events

        # Create tools instance
        tools = QCodesReadOnlyTools(mock_ipython, min_interval_s=0.1)

        # Mock the _read_parameter_live method
        tools._read_parameter_live = AsyncMock(return_value=42.0)

        return tools

    @pytest.mark.asyncio
    async def test_first_read_with_recent_access_no_cache(self, mock_tools):
        """Test first read with recent access (no cache) waits before reading.

        Scenario: Rate limiter has recent access, no cache exists.
        Expected: Should wait before doing live read (via wait_if_needed).
        """
        instrument_name = "inst1"
        parameter_name = "voltage"

        # Simulate recent access by recording an access
        await mock_tools.rate_limiter.record_access(instrument_name)

        # Verify rate limiter would block immediate access
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is False, "Rate limiter should block immediate access"

        # Track if wait_if_needed was called by measuring time
        start_time = time.time()
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=False
        )
        elapsed = time.time() - start_time

        # Should have waited approximately the minimum interval
        assert elapsed >= 0.09, f"Expected wait of ~0.1s, got {elapsed}s"

        # Should return live read result
        assert result["value"] == 42.0
        assert result["source"] == "live"
        assert result["stale"] is False

        # _read_parameter_live should have been called
        mock_tools._read_parameter_live.assert_called_once_with(
            instrument_name, parameter_name
        )

    @pytest.mark.asyncio
    async def test_rate_limited_with_cache_and_fresh_returns_stale(self, mock_tools):
        """Test rate limited with cache and fresh=True returns stale cache value.

        Scenario: Rate limiter blocks access, cache has a value, fresh=True is set.
        Expected: Returns cached value with rate_limited=True and stale=True.

        Note: With fresh=False, the cache fast-path would return the cached value
        immediately without checking rate limiting, which is correct behavior.
        Rate limiting only matters when we want a fresh read but are blocked.
        """
        instrument_name = "inst1"
        parameter_name = "voltage"
        key = mock_tools._make_cache_key(instrument_name, parameter_name)

        # Pre-populate cache with a value
        cached_value = 3.14
        cached_timestamp = time.time() - 5.0  # 5 seconds old
        await mock_tools.cache.set(key, cached_value, cached_timestamp)

        # Record recent access to trigger rate limiting
        await mock_tools.rate_limiter.record_access(instrument_name)

        # Verify rate limiter would block
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is False

        # Call with fresh=True to skip cache fast-path and hit rate limiting check
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=True
        )

        # Should return cached value with rate_limited flag
        assert result["value"] == cached_value
        assert result["timestamp"] == cached_timestamp
        assert result["source"] == "cache"
        assert result["stale"] is True
        assert result["rate_limited"] is True
        assert "Rate limited" in result["message"]
        assert result["age_seconds"] == pytest.approx(5.0, abs=0.1)

        # _read_parameter_live should NOT have been called
        mock_tools._read_parameter_live.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_true_no_cache_honors_rate_limiting(self, mock_tools):
        """Test fresh=True with no cache still honors rate limiting.

        Scenario: fresh=True is set with recent access, no cache exists.
        Expected: Should wait before doing live read, not bypass rate limiting.
        """
        instrument_name = "inst1"
        parameter_name = "voltage"

        # Verify no cache exists
        key = mock_tools._make_cache_key(instrument_name, parameter_name)
        cached = await mock_tools.cache.get(key)
        assert cached is None

        # Record recent access to trigger rate limiting
        await mock_tools.rate_limiter.record_access(instrument_name)

        # Verify rate limiter would block
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is False

        # Call with fresh=True
        start_time = time.time()
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=True
        )
        elapsed = time.time() - start_time

        # Should have waited approximately the minimum interval
        assert elapsed >= 0.09, f"Expected wait of ~0.1s, got {elapsed}s"

        # Should return live read result
        assert result["value"] == 42.0
        assert result["source"] == "live"
        assert result["stale"] is False

        # _read_parameter_live should have been called
        mock_tools._read_parameter_live.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limited_no_cache_waits_for_live_read(self, mock_tools):
        """Test rate limited without cache falls through to live read with wait.

        Scenario: Rate limiter blocks access, no cache exists.
        Expected: Should wait then perform live read.
        """
        instrument_name = "inst1"
        parameter_name = "voltage"

        # Record recent access to trigger rate limiting
        await mock_tools.rate_limiter.record_access(instrument_name)

        # Verify no cache exists
        key = mock_tools._make_cache_key(instrument_name, parameter_name)
        cached = await mock_tools.cache.get(key)
        assert cached is None

        # Verify rate limiter would block
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is False

        # Call method
        start_time = time.time()
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=False
        )
        elapsed = time.time() - start_time

        # Should have waited approximately the minimum interval
        assert elapsed >= 0.09, f"Expected wait of ~0.1s, got {elapsed}s"

        # Should return live read result
        assert result["value"] == 42.0
        assert result["source"] == "live"
        assert result["stale"] is False

        # _read_parameter_live should have been called
        mock_tools._read_parameter_live.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_rate_limit_with_cache_uses_cache(self, mock_tools):
        """Test that cache is used when not rate limited and fresh=False.

        Scenario: No recent access, cache exists, fresh=False.
        Expected: Returns cached value immediately without checking hardware.
        """
        instrument_name = "inst1"
        parameter_name = "voltage"
        key = mock_tools._make_cache_key(instrument_name, parameter_name)

        # Pre-populate cache
        cached_value = 2.71
        cached_timestamp = time.time() - 2.0
        await mock_tools.cache.set(key, cached_value, cached_timestamp)

        # No recent access - rate limiter should allow access
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is True

        # Call with fresh=False (should use cache)
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=False
        )

        # Should return cached value
        assert result["value"] == cached_value
        assert result["timestamp"] == cached_timestamp
        assert result["source"] == "cache"
        assert result["stale"] is False  # Not stale since we wanted cache
        assert "rate_limited" not in result

        # _read_parameter_live should NOT have been called
        mock_tools._read_parameter_live.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_rate_limit_no_cache_immediate_live_read(self, mock_tools):
        """Test immediate live read when not rate limited and no cache.

        Scenario: No recent access, no cache.
        Expected: Performs live read immediately without waiting.
        """
        instrument_name = "inst1"
        parameter_name = "voltage"

        # Verify no cache exists
        key = mock_tools._make_cache_key(instrument_name, parameter_name)
        cached = await mock_tools.cache.get(key)
        assert cached is None

        # No recent access - rate limiter should allow
        can_access = await mock_tools.rate_limiter.can_access(instrument_name)
        assert can_access is True

        # Call method
        start_time = time.time()
        result = await mock_tools._get_single_parameter_value(
            instrument_name, parameter_name, fresh=False
        )
        elapsed = time.time() - start_time

        # Should NOT have waited (should be fast, relaxed for CI)
        assert elapsed < 0.2, f"Expected immediate read, got {elapsed}s"

        # Should return live read result
        assert result["value"] == 42.0
        assert result["source"] == "live"
        assert result["stale"] is False

        # _read_parameter_live should have been called
        mock_tools._read_parameter_live.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, mock_tools):
        """Test cache key generation for different parameter paths."""
        # Simple parameter
        key1 = mock_tools._make_cache_key("inst1", "voltage")
        assert key1 == ("inst1", "voltage")

        # Hierarchical parameter
        key2 = mock_tools._make_cache_key("inst1", "ch01.voltage")
        assert key2 == ("inst1", "ch01.voltage")

        # Different instruments should have different keys
        key3 = mock_tools._make_cache_key("inst2", "voltage")
        assert key3 != key1
