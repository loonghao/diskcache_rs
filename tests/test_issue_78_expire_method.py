"""
Tests for Cache.expire() and FanoutCache.expire() methods.

Addresses GitHub issue #78:
  https://github.com/loonghao/diskcache_rs/issues/78

The expire() method should remove expired items from the cache and return
the count of items removed, matching python-diskcache's API.
"""

import tempfile
import time

import pytest

from diskcache_rs import Cache, FanoutCache


class TestCacheExpire:
    """Tests for Cache.expire() method."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_expire_method_exists(self, temp_cache_dir):
        """Cache should have an expire() method (issue #78)."""
        cache = Cache(temp_cache_dir)
        assert hasattr(cache, "expire")
        assert callable(cache.expire)
        cache.close()

    def test_expire_returns_zero_on_empty_cache(self, temp_cache_dir):
        """expire() on an empty cache should return 0."""
        cache = Cache(temp_cache_dir)
        count = cache.expire()
        assert count == 0
        cache.close()

    def test_expire_returns_zero_when_no_expired_items(self, temp_cache_dir):
        """expire() should return 0 when no items have expired."""
        cache = Cache(temp_cache_dir)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.expire()
        assert count == 0
        assert len(cache) == 2
        cache.close()

    def test_expire_removes_expired_items(self, temp_cache_dir):
        """expire() should remove items that have expired and return count."""
        cache = Cache(temp_cache_dir)

        # Set items with short TTL
        cache.set("expire1", "value1", expire=0.5)
        cache.set("expire2", "value2", expire=0.5)
        cache.set("keep", "value3")  # No expiration

        assert len(cache) == 3

        # Wait for items to expire
        time.sleep(0.7)

        # Call expire()
        count = cache.expire()
        assert count == 2

        # Verify remaining items
        assert cache.get("keep") == "value3"
        assert cache.get("expire1") is None
        assert cache.get("expire2") is None
        cache.close()

    def test_expire_with_mixed_ttl(self, temp_cache_dir):
        """expire() should only remove items that have actually expired."""
        cache = Cache(temp_cache_dir)

        # Set items with different TTLs
        cache.set("short_ttl", "value1", expire=0.5)
        cache.set("long_ttl", "value2", expire=60)
        cache.set("no_ttl", "value3")

        # Wait for short TTL to expire
        time.sleep(0.7)

        count = cache.expire()
        assert count == 1

        # short_ttl should be gone, others remain
        assert cache.get("short_ttl") is None
        assert cache.get("long_ttl") == "value2"
        assert cache.get("no_ttl") == "value3"
        cache.close()

    def test_expire_returns_int(self, temp_cache_dir):
        """expire() should always return an integer."""
        cache = Cache(temp_cache_dir)
        result = cache.expire()
        assert isinstance(result, int)
        cache.close()

    def test_expire_with_now_parameter(self, temp_cache_dir):
        """expire() should accept an optional 'now' parameter."""
        cache = Cache(temp_cache_dir)
        # Just verify the parameter is accepted without error
        count = cache.expire(now=time.time())
        assert isinstance(count, int)
        cache.close()

    def test_expire_idempotent(self, temp_cache_dir):
        """Calling expire() multiple times should be safe."""
        cache = Cache(temp_cache_dir)
        cache.set("key", "value", expire=0.5)
        time.sleep(0.7)

        # First call removes the expired item
        count1 = cache.expire()
        assert count1 == 1

        # Second call should find nothing to remove
        count2 = cache.expire()
        assert count2 == 0
        cache.close()

    def test_expire_with_context_manager(self, temp_cache_dir):
        """expire() should work within context manager."""
        with Cache(temp_cache_dir) as cache:
            cache.set("key", "value", expire=0.5)
            time.sleep(0.7)
            count = cache.expire()
            assert count == 1


class TestFanoutCacheExpire:
    """Tests for FanoutCache.expire() method."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_expire_method_exists(self, temp_cache_dir):
        """FanoutCache should have an expire() method (issue #78)."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        assert hasattr(cache, "expire")
        assert callable(cache.expire)
        cache.close()

    def test_expire_returns_zero_on_empty_cache(self, temp_cache_dir):
        """expire() on an empty fanout cache should return 0."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        count = cache.expire()
        assert count == 0
        cache.close()

    def test_expire_returns_zero_when_no_expired_items(self, temp_cache_dir):
        """expire() should return 0 when no items have expired."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.expire()
        assert count == 0
        assert len(cache) == 2
        cache.close()

    def test_expire_removes_expired_items(self, temp_cache_dir):
        """expire() should remove expired items across all shards."""
        cache = FanoutCache(temp_cache_dir, shards=4)

        # Set items with short TTL
        cache.set("expire1", "value1", expire=0.5)
        cache.set("expire2", "value2", expire=0.5)
        cache.set("expire3", "value3", expire=0.5)
        cache.set("keep", "value4")  # No expiration

        assert len(cache) == 4

        # Wait for items to expire
        time.sleep(0.7)

        count = cache.expire()
        assert count == 3

        # Verify remaining items
        assert cache.get("keep") == "value4"
        assert cache.get("expire1") is None
        assert cache.get("expire2") is None
        assert cache.get("expire3") is None
        cache.close()

    def test_expire_with_mixed_ttl(self, temp_cache_dir):
        """expire() should only remove items that have actually expired."""
        cache = FanoutCache(temp_cache_dir, shards=4)

        cache.set("short", "value1", expire=0.5)
        cache.set("long", "value2", expire=60)
        cache.set("none", "value3")

        time.sleep(0.7)

        count = cache.expire()
        assert count == 1

        assert cache.get("short") is None
        assert cache.get("long") == "value2"
        assert cache.get("none") == "value3"
        cache.close()

    def test_expire_returns_int(self, temp_cache_dir):
        """expire() should always return an integer."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        result = cache.expire()
        assert isinstance(result, int)
        cache.close()

    def test_expire_with_now_parameter(self, temp_cache_dir):
        """expire() should accept an optional 'now' parameter."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        count = cache.expire(now=time.time())
        assert isinstance(count, int)
        cache.close()

    def test_expire_idempotent(self, temp_cache_dir):
        """Calling expire() multiple times should be safe."""
        cache = FanoutCache(temp_cache_dir, shards=4)
        cache.set("key", "value", expire=0.5)
        time.sleep(0.7)

        count1 = cache.expire()
        assert count1 == 1

        count2 = cache.expire()
        assert count2 == 0
        cache.close()

    def test_expire_with_context_manager(self, temp_cache_dir):
        """expire() should work within context manager."""
        with FanoutCache(temp_cache_dir, shards=4) as cache:
            cache.set("key", "value", expire=0.5)
            time.sleep(0.7)
            count = cache.expire()
            assert count == 1

    def test_expire_across_shards(self, temp_cache_dir):
        """expire() should clean up expired items distributed across shards."""
        cache = FanoutCache(temp_cache_dir, shards=8)

        # Add many items to spread across shards
        for i in range(20):
            cache.set(f"key_{i}", f"value_{i}", expire=0.5)

        assert len(cache) == 20

        time.sleep(0.7)

        count = cache.expire()
        assert count == 20
        assert len(cache) == 0
        cache.close()
