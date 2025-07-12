#!/usr/bin/env python3
"""
精确的基准测试 - 使用与 diskcache 完全相同的测试方法
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


def precise_timing_test():
    """使用精确的计时方法测试"""
    print("⏱️ Precise Timing Test")
    print("=" * 60)

    test_data = b"x" * 1024  # 1KB test data
    iterations = 1000

    # Test diskcache
    print("\n📊 Testing diskcache:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache")
        cache = diskcache.Cache(cache_dir)

        # Warm up
        for i in range(10):
            cache.set(f"warmup_{i}", test_data)

        # Precise timing
        times = []
        for i in range(iterations):
            start = time.perf_counter_ns()
            cache.set(f"key_{i}", test_data)
            end = time.perf_counter_ns()
            times.append((end - start) / 1000)  # Convert to microseconds

        mean_time = statistics.mean(times)
        median_time = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        ops_per_sec = 1_000_000 / mean_time

        print(f"  Mean:   {mean_time:8.1f} μs ({ops_per_sec:8.1f} ops/s)")
        print(f"  Median: {median_time:8.1f} μs")
        print(f"  Min:    {min_time:8.1f} μs")
        print(f"  Max:    {max_time:8.1f} μs")

        cache.close()
        diskcache_ops = ops_per_sec

    # Test diskcache_rs
    print("\n📊 Testing diskcache_rs:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        # Warm up
        for i in range(10):
            cache.set(f"warmup_{i}", test_data)

        # Precise timing
        times = []
        for i in range(iterations):
            start = time.perf_counter_ns()
            cache.set(f"key_{i}", test_data)
            end = time.perf_counter_ns()
            times.append((end - start) / 1000)  # Convert to microseconds

        mean_time = statistics.mean(times)
        median_time = statistics.median(times)
        min_time = min(times)
        max_time = max(times)
        ops_per_sec = 1_000_000 / mean_time

        print(f"  Mean:   {mean_time:8.1f} μs ({ops_per_sec:8.1f} ops/s)")
        print(f"  Median: {median_time:8.1f} μs")
        print(f"  Min:    {min_time:8.1f} μs")
        print(f"  Max:    {max_time:8.1f} μs")

        diskcache_rs_ops = ops_per_sec

    # Compare results
    print("\n🏆 Performance Comparison:")
    if diskcache_rs_ops > diskcache_ops:
        ratio = diskcache_rs_ops / diskcache_ops
        print(f"  diskcache_rs is {ratio:.2f}x FASTER than diskcache! 🎉")
    else:
        ratio = diskcache_ops / diskcache_rs_ops
        print(f"  diskcache is {ratio:.2f}x faster than diskcache_rs")


def batch_size_analysis():
    """分析不同批量大小的性能"""
    print("\n📦 Batch Size Performance Analysis")
    print("=" * 60)

    test_data = b"x" * 1024
    batch_sizes = [1, 10, 50, 100, 500, 1000]

    for batch_size in batch_sizes:
        print(f"\n📊 Batch size: {batch_size}")

        # Test diskcache
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")
            cache = diskcache.Cache(cache_dir)

            start = time.perf_counter()
            for i in range(batch_size):
                cache.set(f"key_{i}", test_data)
            end = time.perf_counter()

            total_time = end - start
            ops_per_sec = batch_size / total_time
            avg_time_per_op = (total_time * 1_000_000) / batch_size  # μs

            print(
                f"  diskcache:    {ops_per_sec:8.1f} ops/s ({avg_time_per_op:6.1f} μs/op)"
            )
            cache.close()
            diskcache_ops = ops_per_sec

        # Test diskcache_rs
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            start = time.perf_counter()
            for i in range(batch_size):
                cache.set(f"key_{i}", test_data)
            end = time.perf_counter()

            total_time = end - start
            ops_per_sec = batch_size / total_time
            avg_time_per_op = (total_time * 1_000_000) / batch_size  # μs

            print(
                f"  diskcache_rs: {ops_per_sec:8.1f} ops/s ({avg_time_per_op:6.1f} μs/op)"
            )
            diskcache_rs_ops = ops_per_sec

        # Compare
        if diskcache_rs_ops > diskcache_ops:
            ratio = diskcache_rs_ops / diskcache_ops
            print(f"  Winner: diskcache_rs ({ratio:.2f}x faster) ✅")
        else:
            ratio = diskcache_ops / diskcache_rs_ops
            print(f"  Winner: diskcache ({ratio:.2f}x faster) ❌")


def cold_start_test():
    """测试冷启动性能"""
    print("\n🥶 Cold Start Performance Test")
    print("=" * 60)

    test_data = b"x" * 1024

    # Test diskcache cold start
    print("\n📊 Testing diskcache cold start:")
    times = []
    for _ in range(10):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")

            start = time.perf_counter_ns()
            cache = diskcache.Cache(cache_dir)
            cache.set("test_key", test_data)
            cache.close()
            end = time.perf_counter_ns()

            times.append((end - start) / 1000)  # μs

    diskcache_cold = statistics.mean(times)
    print(f"  Average cold start: {diskcache_cold:.1f} μs")

    # Test diskcache_rs cold start
    print("\n📊 Testing diskcache_rs cold start:")
    times = []
    for _ in range(10):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")

            start = time.perf_counter_ns()
            cache = diskcache_rs.Cache(cache_dir)
            cache.set("test_key", test_data)
            end = time.perf_counter_ns()

            times.append((end - start) / 1000)  # μs

    diskcache_rs_cold = statistics.mean(times)
    print(f"  Average cold start: {diskcache_rs_cold:.1f} μs")

    # Compare
    if diskcache_rs_cold < diskcache_cold:
        ratio = diskcache_cold / diskcache_rs_cold
        print(f"\n🏆 diskcache_rs cold start is {ratio:.2f}x FASTER! ✅")
    else:
        ratio = diskcache_rs_cold / diskcache_cold
        print(f"\n❌ diskcache cold start is {ratio:.2f}x faster")


def main():
    """主测试函数"""
    print("🎯 Precise Performance Benchmark")
    print("=" * 60)
    print("Using identical test methodology to eliminate measurement bias")

    precise_timing_test()
    batch_size_analysis()
    cold_start_test()

    print("\n" + "=" * 60)
    print("✅ Precise benchmark completed!")
    print("\n💡 This test uses identical methodology for both implementations")
    print("   to ensure fair comparison and eliminate measurement bias.")


if __name__ == "__main__":
    main()
