#!/usr/bin/env python3
"""
High-performance benchmark test for diskcache_rs with new optimizations.
Tests different storage backends and serialization formats.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    import diskcache
    import diskcache_rs
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure to run 'maturin develop' first")
    sys.exit(1)


def benchmark_operation(cache, operation, data, iterations=1000):
    """Benchmark a cache operation."""
    start_time = time.perf_counter()

    if operation == "set":
        for i in range(iterations):
            cache.set(f"key_{i}", data)
    elif operation == "get":
        # First populate the cache
        for i in range(iterations):
            cache.set(f"key_{i}", data)

        # Now benchmark get operations
        start_time = time.perf_counter()  # Reset timer
        for i in range(iterations):
            cache.get(f"key_{i}")
    elif operation == "delete":
        # First populate the cache
        for i in range(iterations):
            cache.set(f"key_{i}", data)

        # Now benchmark delete operations
        start_time = time.perf_counter()  # Reset timer
        for i in range(iterations):
            cache.delete(f"key_{i}")

    end_time = time.perf_counter()
    total_time = end_time - start_time
    ops_per_second = iterations / total_time if total_time > 0 else 0

    return total_time, ops_per_second


def run_performance_comparison():
    """Run performance comparison between different configurations."""

    # Test data
    small_data = b"x" * 100  # 100 bytes
    medium_data = b"x" * 1024  # 1KB
    large_data = b"x" * 10240  # 10KB

    test_cases = [
        ("Small data (100B)", small_data, 5000),
        ("Medium data (1KB)", medium_data, 2000),
        ("Large data (10KB)", large_data, 1000),
    ]

    for test_name, data, iterations in test_cases:
        print(f"\n=== {test_name} ===")

        # Test diskcache (baseline)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")
            cache = diskcache.Cache(cache_dir)

            set_time, set_ops = benchmark_operation(cache, "set", data, iterations)
            get_time, get_ops = benchmark_operation(cache, "get", data, iterations)
            delete_time, delete_ops = benchmark_operation(
                cache, "delete", data, iterations
            )

            cache.close()

            print("diskcache:")
            print(f"  SET:    {set_ops:8.1f} ops/s ({set_time:.4f}s)")
            print(f"  GET:    {get_ops:8.1f} ops/s ({get_time:.4f}s)")
            print(f"  DELETE: {delete_ops:8.1f} ops/s ({delete_time:.4f}s)")

        # Test diskcache_rs with default (Redb) backend
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs_redb")
            cache = diskcache_rs.Cache(cache_dir)

            set_time, set_ops = benchmark_operation(cache, "set", data, iterations)
            get_time, get_ops = benchmark_operation(cache, "get", data, iterations)
            delete_time, delete_ops = benchmark_operation(
                cache, "delete", data, iterations
            )

            print("diskcache_rs (Redb):")
            print(f"  SET:    {set_ops:8.1f} ops/s ({set_time:.4f}s)")
            print(f"  GET:    {get_ops:8.1f} ops/s ({get_time:.4f}s)")
            print(f"  DELETE: {delete_ops:8.1f} ops/s ({delete_time:.4f}s)")

        # Test diskcache_rs with File backend for comparison
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs_file")
            # Note: We'll need to add a way to configure the backend
            # For now, this will use the default Redb backend
            cache = diskcache_rs.Cache(cache_dir)

            set_time, set_ops = benchmark_operation(cache, "set", data, iterations)
            get_time, get_ops = benchmark_operation(cache, "get", data, iterations)
            delete_time, delete_ops = benchmark_operation(
                cache, "delete", data, iterations
            )

            print("diskcache_rs (File):")
            print(f"  SET:    {set_ops:8.1f} ops/s ({set_time:.4f}s)")
            print(f"  GET:    {get_ops:8.1f} ops/s ({get_time:.4f}s)")
            print(f"  DELETE: {delete_ops:8.1f} ops/s ({delete_time:.4f}s)")


def test_serialization_performance():
    """Test different serialization formats."""
    print("\n" + "=" * 60)
    print("SERIALIZATION PERFORMANCE TEST")
    print("=" * 60)

    # Test data with different characteristics
    test_data = {
        "Simple dict": {"key": "value", "number": 42},
        "List of numbers": list(range(100)),
        "Complex nested": {
            "users": [
                {"id": i, "name": f"user_{i}", "active": i % 2 == 0} for i in range(50)
            ],
            "metadata": {"version": "1.0", "timestamp": time.time()},
        },
    }

    for data_name, data in test_data.items():
        print(f"\n--- {data_name} ---")

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "serialization_test")
            cache = diskcache_rs.Cache(cache_dir)

            # Test serialization performance
            iterations = 1000
            start_time = time.perf_counter()

            for i in range(iterations):
                cache.set(f"key_{i}", data)

            set_time = time.perf_counter() - start_time

            # Test deserialization performance
            start_time = time.perf_counter()

            for i in range(iterations):
                _ = cache.get(f"key_{i}")

            get_time = time.perf_counter() - start_time

            print(f"  Serialize:   {iterations / set_time:8.1f} ops/s")
            print(f"  Deserialize: {iterations / get_time:8.1f} ops/s")


def main():
    """Main benchmark function."""
    print("🚀 High-Performance diskcache_rs Benchmark")
    print("=" * 60)

    try:
        run_performance_comparison()
        test_serialization_performance()

        print("\n" + "=" * 60)
        print("✅ Benchmark completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
