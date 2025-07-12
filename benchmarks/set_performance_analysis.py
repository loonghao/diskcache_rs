#!/usr/bin/env python3
"""
详细分析 SET 操作的性能瓶颈
"""

import os
import statistics
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
    sys.exit(1)


def profile_operation(func, iterations=1000):
    """Profile an operation and return detailed timing stats."""
    times = []

    for i in range(iterations):
        start = time.perf_counter()
        func(i)
        end = time.perf_counter()
        times.append((end - start) * 1_000_000)  # Convert to microseconds

    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "p90": statistics.quantiles(times, n=10)[8],
        "p99": statistics.quantiles(times, n=100)[98],
        "total": sum(times),
    }


def analyze_set_performance():
    """Analyze SET performance in detail."""
    print("🔍 SET Performance Analysis")
    print("=" * 60)

    # Test different data sizes
    data_sizes = [
        (100, "100B"),
        (1024, "1KB"),
        (4096, "4KB"),
        (16384, "16KB"),
        (32768, "32KB"),  # threshold
        (65536, "64KB"),
    ]

    for size, label in data_sizes:
        print(f"\n📊 Testing {label} data:")
        print("-" * 40)

        test_data = b"x" * size

        # Test diskcache
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")
            cache = diskcache.Cache(cache_dir)

            def set_diskcache(i, cache=cache, test_data=test_data):
                cache.set(f"key_{i}", test_data)

            stats = profile_operation(set_diskcache, 1000)
            cache.close()

            print(
                f"diskcache:     {stats['mean']:8.1f}μs avg, {stats['median']:8.1f}μs median, {1_000_000 / stats['mean']:8.1f} ops/s"
            )

        # Test diskcache_rs
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            def set_diskcache_rs(i, cache=cache, test_data=test_data):
                cache.set(f"key_{i}", test_data)

            stats = profile_operation(set_diskcache_rs, 1000)

            print(
                f"diskcache_rs:  {stats['mean']:8.1f}μs avg, {stats['median']:8.1f}μs median, {1_000_000 / stats['mean']:8.1f} ops/s"
            )

            # Calculate and display ratio
            baseline_time = 1_000_000 / (1_000_000 / stats["mean"])
            if stats["mean"] > baseline_time:
                ratio = stats["mean"] / baseline_time
                print(f"Ratio: diskcache is {ratio:.2f}x faster")
            else:
                ratio = baseline_time / stats["mean"]
                print(f"Ratio: diskcache_rs is {ratio:.2f}x faster")


def analyze_memory_vs_disk_threshold():
    """Analyze the impact of memory vs disk threshold."""
    print("\n🎯 Memory vs Disk Threshold Analysis")
    print("=" * 60)

    test_data = b"x" * 1024  # 1KB data

    # Test with different configurations if possible
    # For now, just test current behavior
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        # Warm up
        for i in range(100):
            cache.set(f"warmup_{i}", test_data)

        # Test pure memory operations (small data)
        def set_small_data(i):
            cache.set(f"small_{i}", test_data)

        stats = profile_operation(set_small_data, 1000)
        print(
            f"Small data (1KB): {stats['mean']:8.1f}μs avg, {1_000_000 / stats['mean']:8.1f} ops/s"
        )

        # Test disk operations (large data)
        large_data = b"x" * 64 * 1024  # 64KB

        def set_large_data(i):
            cache.set(f"large_{i}", large_data)

        stats = profile_operation(
            set_large_data, 100
        )  # Fewer iterations for large data
        print(
            f"Large data (64KB): {stats['mean']:8.1f}μs avg, {1_000_000 / stats['mean']:8.1f} ops/s"
        )


def analyze_concurrent_performance():
    """Analyze concurrent SET performance."""
    print("\n🚀 Concurrent Performance Analysis")
    print("=" * 60)

    import queue
    import threading

    test_data = b"x" * 1024
    num_threads = 4
    ops_per_thread = 250

    def worker(cache, thread_id, results_queue):
        times = []
        for i in range(ops_per_thread):
            start = time.perf_counter()
            cache.set(f"thread_{thread_id}_key_{i}", test_data)
            end = time.perf_counter()
            times.append((end - start) * 1_000_000)
        results_queue.put(times)

    # Test diskcache_rs concurrent performance
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        results_queue = queue.Queue()
        threads = []

        start_time = time.perf_counter()

        for thread_id in range(num_threads):
            thread = threading.Thread(
                target=worker, args=(cache, thread_id, results_queue)
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        end_time = time.perf_counter()

        # Collect all times
        all_times = []
        while not results_queue.empty():
            all_times.extend(results_queue.get())

        total_ops = num_threads * ops_per_thread
        total_time = end_time - start_time

        print(f"Concurrent SET ({num_threads} threads):")
        print(f"  Total ops: {total_ops}")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Throughput: {total_ops / total_time:.1f} ops/s")
        print(f"  Avg latency: {statistics.mean(all_times):.1f}μs")


def main():
    """Main analysis function."""
    print("🔬 diskcache_rs SET Performance Deep Analysis")
    print("=" * 60)

    analyze_set_performance()
    analyze_memory_vs_disk_threshold()
    analyze_concurrent_performance()

    print("\n" + "=" * 60)
    print("✅ Analysis completed!")


if __name__ == "__main__":
    main()
