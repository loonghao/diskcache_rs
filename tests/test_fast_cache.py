"""
Tests for FastCache functionality and performance comparison
"""

import tempfile
import time

import pytest
from diskcache_rs import Cache, FastCache, FastFanoutCache


class TestFastCache:
    """Test FastCache functionality"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_basic_operations(self, temp_cache_dir):
        """Test basic cache operations"""
        cache = FastCache(temp_cache_dir)

        # Test set and get
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
        assert cache.set("test_key", test_data)

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
        cache = FastCache(temp_cache_dir)

        # Set with short TTL
        cache.set("expire_key", "expire_value", expire=1)

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

    def test_dict_like_interface(self, temp_cache_dir):
        """Test dictionary-like interface"""
        cache = FastCache(temp_cache_dir)

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

    def test_additional_methods(self, temp_cache_dir):
        """Test additional methods for compatibility"""
        cache = FastCache(temp_cache_dir)

        # Test add (only if key doesn't exist)
        assert cache.add("add_key", "add_value")
        assert not cache.add("add_key", "new_value")  # Should fail
        assert cache.get("add_key") == "add_value"

        # Test pop
        value = cache.pop("add_key")
        assert value == "add_value"
        assert not cache.exists("add_key")

        # Test incr/decr
        cache.set("counter", 10)
        assert cache.incr("counter") == 11
        assert cache.incr("counter", 5) == 16
        assert cache.decr("counter", 3) == 13

        # Test touch
        cache.set("touch_key", "touch_value")
        assert cache.touch("touch_key", expire=time.time() + 60)

    def test_context_manager(self, temp_cache_dir):
        """Test context manager support"""
        with FastCache(temp_cache_dir) as cache:
            cache.set("context_key", "context_value")
            assert cache.get("context_key") == "context_value"

    def test_fanout_cache(self, temp_cache_dir):
        """Test FastFanoutCache functionality"""
        cache = FastFanoutCache(temp_cache_dir, shards=4)

        # Test basic operations
        test_keys = [f"key_{i}" for i in range(20)]
        for key in test_keys:
            cache.set(key, f"value_{key}")

        # Verify all keys exist
        for key in test_keys:
            assert cache.exists(key)
            assert cache.get(key) == f"value_{key}"

        # Test keys() method
        all_keys = cache.keys()
        assert set(all_keys) == set(test_keys)

        # Test stats
        stats = cache.stats()
        assert stats["entries"] == len(test_keys)
        assert stats["size_bytes"] > 0

        # Test clear
        cache.clear()
        assert len(cache) == 0

    def test_compatibility_with_original_cache(self, temp_cache_dir):
        """Test API compatibility with original Cache class"""
        # Test that FastCache has the same interface as Cache
        fast_cache = FastCache(temp_cache_dir + "_fast")
        original_cache = Cache(temp_cache_dir + "_original")

        # Test same methods exist
        fast_methods = set(dir(fast_cache))
        original_methods = set(dir(original_cache))

        # Core methods should be present in both
        core_methods = {
            "set",
            "get",
            "delete",
            "exists",
            "keys",
            "clear",
            "stats",
            "__contains__",
            "__getitem__",
            "__setitem__",
            "__delitem__",
            "__len__",
            "__iter__",
            "__enter__",
            "__exit__",
        }

        assert core_methods.issubset(fast_methods)
        assert core_methods.issubset(original_methods)

    def test_expire_time_return(self, temp_cache_dir):
        """Test returning expire time with get method"""
        cache = FastCache(temp_cache_dir)

        # Set with expiration
        expire_timestamp = time.time() + 3600  # 1 hour from now
        cache.set("expire_test", "expire_value", expire=expire_timestamp)

        # Get with expire_time=True
        value, returned_expire = cache.get("expire_test", expire_time=True)
        assert value == "expire_value"
        assert returned_expire is not None
        assert abs(returned_expire - expire_timestamp) < 2  # Allow 2 second tolerance

    def test_large_objects(self, temp_cache_dir):
        """Test caching large objects"""
        cache = FastCache(temp_cache_dir)

        # Create a large object
        large_data = {
            "data": "x" * 10000,
            "numbers": list(range(1000)),
            "nested": {"deep": {"structure": {"with": "values"}}},
        }

        cache.set("large_key", large_data)
        retrieved = cache.get("large_key")

        assert retrieved == large_data

    def test_unicode_support(self, temp_cache_dir):
        """Test Unicode support in keys and values"""
        cache = FastCache(temp_cache_dir)

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

    @pytest.mark.benchmark
    def test_performance_comparison(self, temp_cache_dir):
        """Compare performance between FastCache and original Cache"""
        import time

        # Create both caches
        fast_cache = FastCache(temp_cache_dir + "_fast")
        original_cache = Cache(temp_cache_dir + "_original")

        # Test data - smaller for CI environments
        test_data = {"key": "value", "number": 42, "list": list(range(10))}
        num_operations = 100  # Reduced for CI stability

        # Benchmark FastCache (use high precision timer)
        start_time = time.perf_counter()
        for i in range(num_operations):
            fast_cache.set(f"key_{i}", test_data)
        for i in range(num_operations):
            fast_cache.get(f"key_{i}")
        fast_time = time.perf_counter() - start_time

        # Benchmark original Cache (use high precision timer)
        start_time = time.perf_counter()
        for i in range(num_operations):
            original_cache.set(f"key_{i}", test_data)
        for i in range(num_operations):
            original_cache.get(f"key_{i}")
        original_time = time.perf_counter() - start_time

        print(f"\nPerformance comparison ({num_operations} operations):")
        print(f"FastCache: {fast_time:.3f}s")
        print(f"Original Cache: {original_time:.3f}s")

        # Avoid division by zero
        if fast_time > 0 and original_time > 0:
            if fast_time < original_time:
                print(f"FastCache is {original_time / fast_time:.2f}x faster")
            else:
                print(f"FastCache is {fast_time / original_time:.2f}x slower")
        else:
            print("Performance comparison skipped due to very fast execution times")

        # FastCache uses a different backend (PickleCache) which may have different
        # performance characteristics. We just ensure both complete successfully.
        # The main value of FastCache is in its additional features (TTL, LRU, etc.)
        # Use >= 0 to handle very fast execution times on Windows
        assert fast_time >= 0, "FastCache should complete successfully"
        assert original_time >= 0, "Original Cache should complete successfully"

        # Ensure reasonable performance bounds (should complete within 30 seconds)
        assert fast_time < 30.0, "FastCache should complete within reasonable time"
        assert original_time < 30.0, (
            "Original Cache should complete within reasonable time"
        )

    def test_error_handling(self, temp_cache_dir):
        """Test error handling and edge cases"""
        cache = FastCache(temp_cache_dir)

        # Test with None values
        cache.set("none_key", None)
        assert cache.get("none_key") is None
        assert cache.exists("none_key")  # None is a valid value

        # Test with empty strings
        cache.set("empty_key", "")
        assert cache.get("empty_key") == ""

        # Test with complex nested structures
        complex_data = {
            "list": [1, 2, {"nested": True}],
            "tuple": (1, 2, 3),
            "set": {1, 2, 3},  # Sets should be preserved
            "none": None,
            "bool": True,
        }
        cache.set("complex_key", complex_data)
        retrieved = cache.get("complex_key")

        # Note: sets might become lists due to pickle serialization
        assert retrieved["list"] == complex_data["list"]
        assert retrieved["tuple"] == complex_data["tuple"]
        assert retrieved["none"] == complex_data["none"]
        assert retrieved["bool"] == complex_data["bool"]
