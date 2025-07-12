"""
Tests for PickleCache functionality
"""

import tempfile
import time

import pytest
from diskcache_rs import PickleCache, cache_object, clear_cache, get_cached_object


class TestPickleCache:
    """Test PickleCache functionality"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_basic_operations(self, temp_cache_dir):
        """Test basic cache operations"""
        cache = PickleCache(temp_cache_dir)

        # Test set and get
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        cache.set("test_key", test_data)

        retrieved = cache.get("test_key")
        assert retrieved == test_data

        # Test exists
        assert cache.exists("test_key")
        assert not cache.exists("nonexistent_key")

        # Test delete
        assert cache.delete("test_key")
        assert not cache.exists("test_key")
        assert cache.get("test_key") is None

    def test_expiration(self, temp_cache_dir):
        """Test TTL and expiration functionality"""
        cache = PickleCache(temp_cache_dir)

        # Set with short TTL
        cache.set("expire_key", "expire_value", ttl_seconds=1)

        # Should exist immediately
        assert cache.exists("expire_key")
        assert cache.get("expire_key") == "expire_value"

        # Check TTL
        ttl = cache.ttl("expire_key")
        assert ttl is not None and ttl > 0

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert not cache.exists("expire_key")
        assert cache.get("expire_key") is None

    def test_default_ttl(self, temp_cache_dir):
        """Test default TTL functionality"""
        cache = PickleCache(temp_cache_dir, default_ttl_seconds=2)

        # Set without explicit TTL (should use default)
        cache.set("default_ttl_key", "default_ttl_value")

        # Should exist
        assert cache.exists("default_ttl_key")

        # Check TTL
        ttl = cache.ttl("default_ttl_key")
        assert ttl is not None and ttl > 0

    def test_complex_objects(self, temp_cache_dir):
        """Test caching complex Python objects"""
        cache = PickleCache(temp_cache_dir)

        # Test various data types
        test_cases = [
            ("string", "hello world"),
            ("int", 42),
            ("float", 3.14159),
            ("list", [1, 2, 3, "four", 5.0]),
            ("dict", {"nested": {"data": True}, "count": 100}),
            ("tuple", (1, "two", 3.0)),
            ("set", {1, 2, 3, 4, 5}),
            ("bytes", b"binary data"),
        ]

        for key, value in test_cases:
            cache.set(key, value)
            retrieved = cache.get(key)
            assert retrieved == value, f"Failed for {key}: {value}"

    def test_keys_and_iteration(self, temp_cache_dir):
        """Test keys() method and iteration"""
        cache = PickleCache(temp_cache_dir)

        # Add some data
        test_keys = ["key1", "key2", "key3"]
        for key in test_keys:
            cache.set(key, f"value_{key}")

        # Test keys()
        keys = cache.keys()
        assert set(keys) == set(test_keys)

        # Test iteration
        iterated_keys = list(cache)
        assert set(iterated_keys) == set(test_keys)

        # Test __contains__
        for key in test_keys:
            assert key in cache

    def test_dict_like_interface(self, temp_cache_dir):
        """Test dictionary-like interface"""
        cache = PickleCache(temp_cache_dir)

        # Test __setitem__ and __getitem__
        cache["dict_key"] = {"dict": "value"}
        assert cache["dict_key"] == {"dict": "value"}

        # Test __delitem__
        del cache["dict_key"]
        assert "dict_key" not in cache

        # Test KeyError for missing key
        with pytest.raises(KeyError):
            _ = cache["missing_key"]

        with pytest.raises(KeyError):
            del cache["missing_key"]

    def test_stats(self, temp_cache_dir):
        """Test cache statistics"""
        cache = PickleCache(temp_cache_dir, max_size=1024 * 1024)  # 1MB limit

        # Initially empty
        stats = cache.stats()
        assert stats["entries"] == 0
        assert stats["size_bytes"] == 0
        assert "max_size_bytes" in stats

        # Add some data
        cache.set("stats_key", "stats_value")

        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["size_bytes"] > 0

    def test_clear(self, temp_cache_dir):
        """Test cache clearing"""
        cache = PickleCache(temp_cache_dir)

        # Add some data
        for i in range(5):
            cache.set(f"clear_key_{i}", f"clear_value_{i}")

        assert len(cache) == 5

        # Clear cache
        cache.clear()

        assert len(cache) == 0
        assert cache.keys() == []

    def test_expire_method(self, temp_cache_dir):
        """Test expire() method for setting TTL on existing keys"""
        cache = PickleCache(temp_cache_dir)

        # Set without TTL
        cache.set("expire_test", "expire_test_value")
        assert cache.ttl("expire_test") is None  # No expiration

        # Set TTL
        assert cache.expire("expire_test", 1)  # 1 second TTL
        ttl = cache.ttl("expire_test")
        assert ttl is not None and ttl > 0

        # Test with non-existent key
        assert not cache.expire("nonexistent", 60)

    def test_context_manager(self, temp_cache_dir):
        """Test context manager support"""
        with PickleCache(temp_cache_dir) as cache:
            cache.set("context_key", "context_value")
            assert cache.get("context_key") == "context_value"

    def test_convenience_functions(self, temp_cache_dir):
        """Test convenience functions"""
        # Test cache_object
        cache_object(temp_cache_dir, "conv_key", "conv_value", ttl_seconds=60)

        # Test get_cached_object
        value = get_cached_object(temp_cache_dir, "conv_key")
        assert value == "conv_value"

        # Test default value
        default_value = get_cached_object(temp_cache_dir, "missing_key", "default")
        assert default_value == "default"

        # Test clear_cache
        clear_cache(temp_cache_dir)
        value = get_cached_object(temp_cache_dir, "conv_key")
        assert value is None

    def test_large_objects(self, temp_cache_dir):
        """Test caching large objects"""
        cache = PickleCache(temp_cache_dir)

        # Create a large object
        large_data = {"data": "x" * 10000, "numbers": list(range(1000))}

        cache.set("large_key", large_data)
        retrieved = cache.get("large_key")

        assert retrieved == large_data

    def test_unicode_keys_and_values(self, temp_cache_dir):
        """Test Unicode support in keys and values"""
        cache = PickleCache(temp_cache_dir)

        unicode_data = {
            "中文": "Chinese text",
            "русский": "Russian text",
            "العربية": "Arabic text",
            "emoji": "🚀🎉🔥",
        }

        for key, value in unicode_data.items():
            cache.set(key, value)
            retrieved = cache.get(key)
            assert retrieved == value

    @pytest.mark.slow
    def test_size_limits_and_eviction(self, temp_cache_dir):
        """Test size limits and LRU eviction"""
        # Small cache size for testing
        cache = PickleCache(temp_cache_dir, max_size=1024)  # 1KB limit

        # Fill cache beyond limit
        for i in range(10):
            large_value = "x" * 200  # 200 bytes each
            cache.set(f"size_key_{i}", large_value)

        # Should have evicted some entries
        stats = cache.stats()
        assert stats["entries"] < 10
        assert stats["size_bytes"] <= 1024
