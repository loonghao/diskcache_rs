"""
Simple benchmark tests for CI environment
"""

import os
import tempfile
import time

import pytest
from diskcache_rs import Cache


class TestCIBenchmarks:
    """Simple benchmark tests that work reliably in CI"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def cache(self, temp_cache_dir):
        """Create a cache instance"""
        cache_dir = os.path.join(temp_cache_dir, "test_cache")
        return Cache(cache_dir)

    def test_benchmark_basic_operations(self, benchmark, cache):
        """Basic benchmark test for CI"""

        def basic_operations():
            # Simple operations that should work in any environment
            cache.set("test_key", "test_value")
            value = cache.get("test_key")
            exists = "test_key" in cache
            cache.delete("test_key")
            return value, exists

        result = benchmark(basic_operations)
        value, exists = result
        assert value == "test_value"
        assert exists is True

    def test_benchmark_bulk_operations(self, benchmark, cache):
        """Benchmark bulk operations"""

        def bulk_operations():
            # Store 100 items
            for i in range(100):
                cache.set(f"bulk_key_{i}", f"bulk_value_{i}")

            # Read 100 items
            results = []
            for i in range(100):
                result = cache.get(f"bulk_key_{i}")
                results.append(result)

            return len(results)

        result = benchmark(bulk_operations)
        assert result == 100

    def test_performance_timing(self, cache):
        """Manual timing test that doesn't require pytest-benchmark"""
        # Test set operations
        start_time = time.perf_counter()
        for i in range(1000):
            cache.set(f"timing_key_{i}", f"timing_value_{i}")
        set_time = time.perf_counter() - start_time

        # Test get operations
        start_time = time.perf_counter()
        for i in range(1000):
            cache.get(f"timing_key_{i}")
        get_time = time.perf_counter() - start_time

        # Test delete operations
        start_time = time.perf_counter()
        for i in range(1000):
            cache.delete(f"timing_key_{i}")
        delete_time = time.perf_counter() - start_time

        print("Performance results for 1000 operations:")
        print(f"  Set:    {set_time:.3f}s ({1000 / set_time:.1f} ops/sec)")
        print(f"  Get:    {get_time:.3f}s ({1000 / get_time:.1f} ops/sec)")
        print(f"  Delete: {delete_time:.3f}s ({1000 / delete_time:.1f} ops/sec)")

        # Basic performance assertions
        assert set_time < 10.0, f"Set operations too slow: {set_time:.2f}s"
        assert get_time < 5.0, f"Get operations too slow: {get_time:.2f}s"
        assert delete_time < 5.0, f"Delete operations too slow: {delete_time:.2f}s"

    def test_api_compatibility(self, cache):
        """Test that all diskcache API methods work"""
        # Basic operations
        assert cache.set("api_key", "api_value") is True
        assert cache.get("api_key") == "api_value"
        assert "api_key" in cache
        assert len(cache) >= 1

        # Advanced operations
        assert cache.add("new_key", "new_value") is True
        assert cache.add("new_key", "different_value") is False  # Should not overwrite

        # Increment/decrement
        cache.set("counter", 10)
        assert cache.incr("counter", 5) == 15
        assert cache.decr("counter", 3) == 12

        # Pop operation
        cache.set("pop_key", "pop_value")
        assert cache.pop("pop_key") == "pop_value"
        assert cache.get("pop_key") is None

        # Touch operation
        cache.set("touch_key", "touch_value")
        assert cache.touch("touch_key") is True
        assert cache.touch("nonexistent_key") is False

        # Stats
        stats = cache.stats()
        assert isinstance(stats, dict)

        # Volume
        volume = cache.volume()
        assert isinstance(volume, int)
        assert volume >= 0

        # Clear
        count = cache.clear()
        assert isinstance(count, int)
        assert len(cache) == 0

        print("✅ All API compatibility tests passed")

    def test_error_handling(self, cache):
        """Test error handling and edge cases"""
        # Test with None values
        cache.set("none_key", None)
        assert cache.get("none_key") is None

        # Test with empty strings
        cache.set("empty_key", "")
        assert cache.get("empty_key") == ""

        # Test with large values
        large_value = "x" * 10000
        cache.set("large_key", large_value)
        assert cache.get("large_key") == large_value

        # Test non-existent keys
        assert cache.get("nonexistent") is None
        assert cache.pop("nonexistent", "default") == "default"

        # Test increment with non-existent key
        result = cache.incr("new_counter", default=100)
        assert result == 101

        print("✅ All error handling tests passed")


if __name__ == "__main__":
    # Allow running this file directly for quick testing
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(os.path.join(temp_dir, "direct_test"))

        # Quick functionality test
        cache.set("direct_key", "direct_value")
        assert cache.get("direct_key") == "direct_value"

        print("✅ Direct test passed")
