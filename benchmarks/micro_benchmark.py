#!/usr/bin/env python3
"""
微基准测试 - 分析每个操作的具体耗时
"""

import cProfile
import os
import pstats
import statistics
import sys
import tempfile
import time
from io import StringIO
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


def time_operation(func, iterations=1000):
    """精确计时一个操作"""
    times = []
    for i in range(iterations):
        start = time.perf_counter_ns()
        func(i)
        end = time.perf_counter_ns()
        times.append(end - start)  # nanoseconds

    return {
        "mean_ns": statistics.mean(times),
        "median_ns": statistics.median(times),
        "min_ns": min(times),
        "max_ns": max(times),
        "std_ns": statistics.stdev(times) if len(times) > 1 else 0,
        "ops_per_sec": 1_000_000_000 / statistics.mean(times),
    }


def profile_function(func, iterations=1000):
    """使用 cProfile 分析函数"""
    pr = cProfile.Profile()
    pr.enable()

    for i in range(iterations):
        func(i)

    pr.disable()

    # 获取统计信息
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(10)  # 显示前10个最耗时的函数

    return s.getvalue()


def analyze_set_operations():
    """分析 SET 操作的详细性能"""
    print("🔬 SET Operations Micro-Benchmark")
    print("=" * 60)

    test_data = b"x" * 1024  # 1KB test data

    # 测试 diskcache
    print("\n📊 Testing python-diskcache:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache")
        cache = diskcache.Cache(cache_dir)

        def set_diskcache(i):
            cache.set(f"key_{i}", test_data)

        # 预热
        for i in range(100):
            set_diskcache(i)

        # 基准测试
        stats = time_operation(set_diskcache, 1000)
        print(f"  Mean: {stats['mean_ns']:,.0f} ns ({stats['mean_ns'] / 1000:.1f} μs)")
        print(
            f"  Median: {stats['median_ns']:,.0f} ns ({stats['median_ns'] / 1000:.1f} μs)"
        )
        print(f"  Min: {stats['min_ns']:,.0f} ns ({stats['min_ns'] / 1000:.1f} μs)")
        print(f"  Max: {stats['max_ns']:,.0f} ns ({stats['max_ns'] / 1000:.1f} μs)")
        print(f"  Std: {stats['std_ns']:,.0f} ns ({stats['std_ns'] / 1000:.1f} μs)")
        print(f"  Ops/sec: {stats['ops_per_sec']:,.1f}")

        cache.close()

    # 测试 diskcache_rs
    print("\n📊 Testing diskcache_rs:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        def set_diskcache_rs(i):
            cache.set(f"key_{i}", test_data)

        # 预热
        for i in range(100):
            set_diskcache_rs(i)

        # 基准测试
        stats = time_operation(set_diskcache_rs, 1000)
        print(f"  Mean: {stats['mean_ns']:,.0f} ns ({stats['mean_ns'] / 1000:.1f} μs)")
        print(
            f"  Median: {stats['median_ns']:,.0f} ns ({stats['median_ns'] / 1000:.1f} μs)"
        )
        print(f"  Min: {stats['min_ns']:,.0f} ns ({stats['min_ns'] / 1000:.1f} μs)")
        print(f"  Max: {stats['max_ns']:,.0f} ns ({stats['max_ns'] / 1000:.1f} μs)")
        print(f"  Std: {stats['std_ns']:,.0f} ns ({stats['std_ns'] / 1000:.1f} μs)")
        print(f"  Ops/sec: {stats['ops_per_sec']:,.1f}")


def analyze_memory_allocation():
    """分析内存分配开销"""
    print("\n🧠 Memory Allocation Analysis")
    print("=" * 60)

    import tracemalloc

    # 测试不同大小的数据
    sizes = [100, 1024, 4096, 16384]

    for size in sizes:
        print(f"\n📏 Testing {size} bytes:")
        test_data = b"x" * size

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            # 开始内存跟踪
            tracemalloc.start()

            # 执行操作
            for i in range(100):
                cache.set(f"key_{i}", test_data)

            # 获取内存统计
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print(f"  Current memory: {current / 1024:.1f} KB")
            print(f"  Peak memory: {peak / 1024:.1f} KB")
            print(f"  Memory per op: {peak / 100:.1f} bytes")


def analyze_batch_operations():
    """分析批量操作性能"""
    print("\n📦 Batch Operations Analysis")
    print("=" * 60)

    test_data = b"x" * 1024
    batch_sizes = [1, 10, 100, 1000]

    for batch_size in batch_sizes:
        print(f"\n📊 Batch size: {batch_size}")

        # diskcache
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")
            cache = diskcache.Cache(cache_dir)

            start = time.perf_counter()
            for batch in range(10):  # 10 batches
                for i in range(batch_size):
                    cache.set(f"batch_{batch}_key_{i}", test_data)
            end = time.perf_counter()

            total_ops = 10 * batch_size
            diskcache_ops_per_sec = total_ops / (end - start)
            print(f"  diskcache: {diskcache_ops_per_sec:,.1f} ops/s")
            cache.close()

        # diskcache_rs
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            start = time.perf_counter()
            for batch in range(10):  # 10 batches
                for i in range(batch_size):
                    cache.set(f"batch_{batch}_key_{i}", test_data)
            end = time.perf_counter()

            total_ops = 10 * batch_size
            diskcache_rs_ops_per_sec = total_ops / (end - start)
            print(f"  diskcache_rs: {diskcache_rs_ops_per_sec:,.1f} ops/s")

            ratio = diskcache_rs_ops_per_sec / diskcache_ops_per_sec
            if ratio > 1:
                print(f"  Winner: diskcache_rs ({ratio:.2f}x faster)")
            else:
                print(f"  Winner: diskcache ({1 / ratio:.2f}x faster)")


def analyze_key_patterns():
    """分析不同键模式的性能"""
    print("\n🔑 Key Pattern Analysis")
    print("=" * 60)

    test_data = b"x" * 1024

    key_patterns = [
        ("Short keys", lambda i: f"k{i}"),
        ("Medium keys", lambda i: f"key_{i:06d}"),
        ("Long keys", lambda i: f"very_long_key_name_with_lots_of_characters_{i:010d}"),
        ("UUID-like", lambda i: f"xxxxxxxx-xxxx-4xxx-yxxx-{i:012d}"),
    ]

    for pattern_name, key_func in key_patterns:
        print(f"\n📊 {pattern_name}:")

        # diskcache
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache")
            cache = diskcache.Cache(cache_dir)

            def set_diskcache(i, cache=cache, key_func=key_func, test_data=test_data):
                cache.set(key_func(i), test_data)

            stats = time_operation(set_diskcache, 500)
            diskcache_ops = stats["ops_per_sec"]
            print(f"  diskcache: {diskcache_ops:,.1f} ops/s")
            cache.close()

        # diskcache_rs
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            def set_diskcache_rs(
                i, cache=cache, key_func=key_func, test_data=test_data
            ):
                cache.set(key_func(i), test_data)

            stats = time_operation(set_diskcache_rs, 500)
            diskcache_rs_ops = stats["ops_per_sec"]
            print(f"  diskcache_rs: {diskcache_rs_ops:,.1f} ops/s")

            ratio = diskcache_rs_ops / diskcache_ops
            if ratio > 1:
                print(f"  Winner: diskcache_rs ({ratio:.2f}x faster)")
            else:
                print(f"  Winner: diskcache ({1 / ratio:.2f}x faster)")


def main():
    """主函数"""
    print("🔬 diskcache_rs Micro-Benchmark Analysis")
    print("=" * 60)

    analyze_set_operations()
    analyze_memory_allocation()
    analyze_batch_operations()
    analyze_key_patterns()

    print("\n" + "=" * 60)
    print("✅ Micro-benchmark analysis completed!")


if __name__ == "__main__":
    main()
