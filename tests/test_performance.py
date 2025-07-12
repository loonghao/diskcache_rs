"""
Performance tests for diskcache_rs
"""

import concurrent.futures
import os
import statistics
import tempfile
import time

import pytest

# Import both implementations for comparison
try:
    import diskcache

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

from diskcache_rs import Cache as RustCache


class TestPerformance:
    """Performance and benchmark tests"""

    def test_basic_performance(self, cache, benchmark_data):
        """Test basic operation performance"""
        keys = benchmark_data["keys"][:100]  # Use subset for unit tests
        values = benchmark_data["values"][:100]

        # Measure set operations
        start_time = time.perf_counter()
        for key, value in zip(keys, values):
            cache.set(key, value)
        set_time = time.perf_counter() - start_time

        # Measure get operations
        start_time = time.perf_counter()
        for key in keys:
            cache.get(key)
        get_time = time.perf_counter() - start_time

        # Basic performance assertions (adjust thresholds as needed)
        assert set_time < 5.0, f"Set operations too slow: {set_time:.2f}s"
        assert get_time < 2.0, f"Get operations too slow: {get_time:.2f}s"

        print(f"Performance - Set: {set_time:.3f}s, Get: {get_time:.3f}s")

    def test_concurrent_performance(self, cache, benchmark_data):
        """Test performance under concurrent load"""
        keys = benchmark_data["keys"][:50]
        values = benchmark_data["values"][:50]

        def worker(worker_id, keys_subset, values_subset):
            """Worker function for concurrent testing"""
            start_time = time.perf_counter()

            # Each worker handles a subset of keys
            for key, value in zip(keys_subset, values_subset):
                cache.set(f"worker_{worker_id}_{key}", value)

            for key in keys_subset:
                cache.get(f"worker_{worker_id}_{key}")

            return time.perf_counter() - start_time

        # Split work among workers
        num_workers = 4
        chunk_size = len(keys) // num_workers

        start_time = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for i in range(num_workers):
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < num_workers - 1 else len(keys)

                future = executor.submit(
                    worker, i, keys[start_idx:end_idx], values[start_idx:end_idx]
                )
                futures.append(future)

            worker_times = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        total_time = time.perf_counter() - start_time

        # Performance assertions
        assert total_time < 10.0, f"Concurrent operations too slow: {total_time:.2f}s"
        assert max(worker_times) < 8.0, (
            f"Slowest worker too slow: {max(worker_times):.2f}s"
        )

        print(
            f"Concurrent performance - Total: {total_time:.3f}s, Max worker: {max(worker_times):.3f}s"
        )

    def test_large_value_performance(self, cache, benchmark_data):
        """Test performance with large values"""
        large_value = benchmark_data["large_value"]

        # Test multiple large value operations
        times = []
        for i in range(10):
            start_time = time.perf_counter()
            cache.set(f"large_key_{i}", large_value)
            retrieved = cache.get(f"large_key_{i}")
            end_time = time.perf_counter()

            assert retrieved == large_value
            times.append(end_time - start_time)

        avg_time = statistics.mean(times)
        max_time = max(times)

        # Performance assertions for 100KB values
        assert avg_time < 1.0, (
            f"Large value operations too slow on average: {avg_time:.3f}s"
        )
        assert max_time < 2.0, (
            f"Slowest large value operation too slow: {max_time:.3f}s"
        )

        print(f"Large value performance - Avg: {avg_time:.3f}s, Max: {max_time:.3f}s")

    def test_memory_usage_stability(self, cache, benchmark_data):
        """Test that memory usage remains stable under load"""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Perform many operations
        keys = benchmark_data["keys"]
        values = benchmark_data["values"]

        for i in range(3):  # Multiple rounds
            for key, value in zip(keys, values):
                cache.set(f"round_{i}_{key}", value)

            # Clear some data
            if i > 0:
                for key in keys[::2]:  # Delete every other key
                    cache.delete(f"round_{i - 1}_{key}")

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory should not increase excessively (adjust threshold as needed)
        max_increase = 100 * 1024 * 1024  # 100MB
        assert memory_increase < max_increase, (
            f"Memory usage increased too much: {memory_increase / 1024 / 1024:.1f}MB"
        )

        print(f"Memory usage increase: {memory_increase / 1024 / 1024:.1f}MB")

    def test_cache_size_performance(self, temp_cache_dir):
        """Test performance with different cache sizes"""
        from diskcache_rs import Cache

        cache_configs = [
            (1024 * 1024, 1000),  # 1MB, 1K entries
            (10 * 1024 * 1024, 5000),  # 10MB, 5K entries
            (100 * 1024 * 1024, 10000),  # 100MB, 10K entries
        ]

        results = []

        for max_size, max_entries in cache_configs:
            cache = Cache(temp_cache_dir, max_size=max_size, max_entries=max_entries)

            # Test with subset of operations
            test_keys = [f"size_test_{i}" for i in range(100)]
            test_value = b"x" * 1024  # 1KB value

            start_time = time.perf_counter()
            for key in test_keys:
                cache.set(key, test_value)
            for key in test_keys:
                cache.get(key)
            end_time = time.perf_counter()

            operation_time = end_time - start_time
            results.append((max_size, max_entries, operation_time))

            # Clean up for next test
            cache.clear()

        # Print results for analysis
        for max_size, max_entries, op_time in results:
            print(
                f"Cache size {max_size // 1024 // 1024}MB, {max_entries} entries: {op_time:.3f}s"
            )

        # Basic assertion - operations should complete in reasonable time
        for _, _, op_time in results:
            assert op_time < 5.0, f"Cache operations too slow: {op_time:.2f}s"

    @pytest.mark.benchmark
    def test_comparison_benchmark(self, temp_cache_dir, benchmark_data):
        """Benchmark comparison with original diskcache (if available)"""
        try:
            import diskcache

            diskcache_available = True
        except ImportError:
            diskcache_available = False
            pytest.skip(
                "Original diskcache not available for comparison. Install with: uv add diskcache"
            )

        from diskcache_rs import Cache

        # Test data
        keys = benchmark_data["keys"][:100]
        values = benchmark_data["values"][:100]

        # Test diskcache_rs
        rs_cache = Cache(temp_cache_dir + "_rs")
        start_time = time.perf_counter()
        for key, value in zip(keys, values):
            rs_cache.set(key, value)
        for key in keys:
            rs_cache.get(key)
        rs_time = time.perf_counter() - start_time

        # Test original diskcache
        if diskcache_available:
            dc_cache = diskcache.Cache(temp_cache_dir + "_dc")
            start_time = time.perf_counter()
            for key, value in zip(keys, values):
                dc_cache.set(key, value)
            for key in keys:
                dc_cache.get(key)
            dc_time = time.perf_counter() - start_time

            print(
                f"Benchmark comparison - diskcache_rs: {rs_time:.3f}s, diskcache: {dc_time:.3f}s"
            )

            # Both should complete in reasonable time
            assert rs_time < 10.0, f"diskcache_rs too slow: {rs_time:.2f}s"
            assert dc_time < 10.0, f"diskcache too slow: {dc_time:.2f}s"
        else:
            print(f"diskcache_rs benchmark: {rs_time:.3f}s")
            assert rs_time < 5.0, f"diskcache_rs too slow: {rs_time:.2f}s"


class TestOfficialBenchmarks:
    """Official diskcache-style benchmarks for comparison"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def rust_cache(self, temp_cache_dir):
        """Create a Rust cache instance"""
        cache_dir = os.path.join(temp_cache_dir, "rust_cache")
        return RustCache(cache_dir)

    @pytest.fixture
    def python_cache(self, temp_cache_dir):
        """Create a Python diskcache instance"""
        if not DISKCACHE_AVAILABLE:
            pytest.skip("diskcache not available")
        cache_dir = os.path.join(temp_cache_dir, "python_cache")
        cache = diskcache.Cache(cache_dir)
        yield cache
        # Explicitly close the cache to release file locks on Windows
        try:
            cache.close()
        except Exception:
            pass

    def test_single_access_workload_rust(self, benchmark, rust_cache):
        """
        Single access workload: 100,000 operations
        - 88,966 gets (89%)
        - 9,021 sets (9%)
        - 1,012 deletes (1%)

        This matches the official diskcache benchmark workload.
        """

        def single_access_workload():
            # Pre-populate some data
            for i in range(1000):
                rust_cache.set(f"key_{i}", f"value_{i}".encode())

            # Simulate the workload pattern
            operations = 0

            # 88,966 gets (with ~10% miss rate)
            for i in range(8897):  # Scaled down 10x for reasonable test time
                key = f"key_{i % 1100}"  # Some keys won't exist (miss rate)
                rust_cache.get(key)
                operations += 1

            # 9,021 sets
            for i in range(902):  # Scaled down 10x
                rust_cache.set(f"new_key_{i}", f"new_value_{i}".encode())
                operations += 1

            # 1,012 deletes
            for i in range(101):  # Scaled down 10x
                try:
                    del rust_cache[f"key_{i}"]
                except KeyError:
                    pass  # Some keys may not exist
                operations += 1

            return operations

        result = benchmark(single_access_workload)
        assert result > 9000  # Should complete all operations

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_single_access_workload_python(self, benchmark, python_cache):
        """Same workload as above but with Python diskcache for comparison"""

        def single_access_workload():
            # Pre-populate some data
            for i in range(1000):
                python_cache.set(f"key_{i}", f"value_{i}")

            operations = 0

            # 88,966 gets (with ~10% miss rate)
            for i in range(8897):  # Scaled down 10x
                key = f"key_{i % 1100}"
                python_cache.get(key)
                operations += 1

            # 9,021 sets
            for i in range(902):  # Scaled down 10x
                python_cache.set(f"new_key_{i}", f"new_value_{i}")
                operations += 1

            # 1,012 deletes
            for i in range(101):  # Scaled down 10x
                try:
                    del python_cache[f"key_{i}"]
                except KeyError:
                    pass
                operations += 1

            return operations

        result = benchmark(single_access_workload)
        assert result > 9000


class TestBenchmarks:
    """Benchmark tests using pytest-benchmark"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def rust_cache(self, temp_cache_dir):
        """Create a Rust cache instance"""
        cache_dir = os.path.join(temp_cache_dir, "rust_cache")
        return RustCache(cache_dir)

    @pytest.fixture
    def python_cache(self, temp_cache_dir):
        """Create a Python diskcache instance"""
        if not DISKCACHE_AVAILABLE:
            pytest.skip("diskcache not available")
        cache_dir = os.path.join(temp_cache_dir, "python_cache")
        cache = diskcache.Cache(cache_dir)
        yield cache
        # Explicitly close the cache to release file locks on Windows
        try:
            cache.close()
        except Exception:
            pass

    def test_benchmark_rust_cache_set(self, benchmark, rust_cache):
        """Benchmark Rust cache set operations"""

        def set_operation():
            rust_cache.set("benchmark_key", b"benchmark_value")

        benchmark(set_operation)

    def test_benchmark_rust_cache_get(self, benchmark, rust_cache):
        """Benchmark Rust cache get operations"""
        # Pre-populate cache
        rust_cache.set("benchmark_key", b"benchmark_value")

        def get_operation():
            return rust_cache.get("benchmark_key")

        result = benchmark(get_operation)
        assert result == b"benchmark_value"

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_benchmark_python_cache_set(self, benchmark, python_cache):
        """Benchmark Python cache set operations"""

        def set_operation():
            python_cache.set("benchmark_key", "benchmark_value")

        benchmark(set_operation)

    @pytest.mark.skipif(not DISKCACHE_AVAILABLE, reason="diskcache not available")
    def test_benchmark_python_cache_get(self, benchmark, python_cache):
        """Benchmark Python cache get operations"""
        # Pre-populate cache
        python_cache.set("benchmark_key", "benchmark_value")

        def get_operation():
            return python_cache.get("benchmark_key")

        result = benchmark(get_operation)
        assert result == "benchmark_value"

    def test_benchmark_rust_bulk_operations(self, benchmark, rust_cache):
        """Benchmark bulk operations with Rust cache"""

        def bulk_operations():
            # Set 100 items
            for i in range(100):
                rust_cache.set(f"bulk_key_{i}", f"bulk_value_{i}".encode())

            # Get 100 items
            results = []
            for i in range(100):
                result = rust_cache.get(f"bulk_key_{i}")
                results.append(result)

            return results

        results = benchmark(bulk_operations)
        assert len(results) == 100
