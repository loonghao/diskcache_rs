#!/usr/bin/env python3
"""
详细的性能分析 - 找出小数据 SET 操作的具体瓶颈
"""

import cProfile
import os
import pstats
import sys
import tempfile
import time
import tracemalloc
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


def profile_single_operation():
    """分析单个 SET 操作的详细耗时"""
    print("🔬 Single Operation Detailed Profiling")
    print("=" * 60)

    test_data = b"x" * 1024  # 1KB test data

    # Profile diskcache_rs
    print("\n📊 Profiling diskcache_rs single SET operation:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        # Warm up
        cache.set("warmup", test_data)

        # Profile with cProfile
        pr = cProfile.Profile()
        pr.enable()

        start = time.perf_counter_ns()
        cache.set("test_key", test_data)
        end = time.perf_counter_ns()

        pr.disable()

        print(f"Total time: {(end - start) / 1000:.1f} μs")

        # Show profile results
        s = StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats(15)
        print("Top functions by cumulative time:")
        print(s.getvalue())


def analyze_memory_patterns():
    """分析内存分配模式"""
    print("\n🧠 Memory Allocation Pattern Analysis")
    print("=" * 60)

    test_data = b"x" * 1024

    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        # Start memory tracing
        tracemalloc.start()

        # Baseline
        snapshot1 = tracemalloc.take_snapshot()

        # Single operation
        cache.set("test_key", test_data)
        snapshot2 = tracemalloc.take_snapshot()

        # Multiple operations
        for i in range(100):
            cache.set(f"key_{i}", test_data)
        snapshot3 = tracemalloc.take_snapshot()

        # Analyze differences
        print("\nMemory usage for single operation:")
        top_stats = snapshot2.compare_to(snapshot1, "lineno")
        for stat in top_stats[:10]:
            print(stat)

        print("\nMemory usage for 100 operations:")
        top_stats = snapshot3.compare_to(snapshot1, "lineno")
        for stat in top_stats[:10]:
            print(stat)

        tracemalloc.stop()


def compare_operation_breakdown():
    """对比操作分解"""
    print("\n⚡ Operation Breakdown Comparison")
    print("=" * 60)

    test_data = b"x" * 1024
    iterations = 1000

    # Test diskcache
    print("\n📊 diskcache operation breakdown:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache")
        cache = diskcache.Cache(cache_dir)

        # Measure different phases
        times = {"total": [], "key_validation": [], "serialization": [], "storage": []}

        for i in range(iterations):
            # Total time
            start_total = time.perf_counter_ns()
            cache.set(f"key_{i}", test_data)
            end_total = time.perf_counter_ns()
            times["total"].append(end_total - start_total)

        avg_total = sum(times["total"]) / len(times["total"]) / 1000  # μs
        print(f"Average total time: {avg_total:.1f} μs")
        print(f"Operations per second: {1_000_000 / avg_total:.1f}")

        cache.close()

    # Test diskcache_rs
    print("\n📊 diskcache_rs operation breakdown:")
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        times = {"total": []}

        for i in range(iterations):
            start_total = time.perf_counter_ns()
            cache.set(f"key_{i}", test_data)
            end_total = time.perf_counter_ns()
            times["total"].append(end_total - start_total)

        avg_total = sum(times["total"]) / len(times["total"]) / 1000  # μs
        print(f"Average total time: {avg_total:.1f} μs")
        print(f"Operations per second: {1_000_000 / avg_total:.1f}")

        # Calculate performance ratio
        diskcache_avg_time = sum(times["total"]) / len(times["total"]) / 1000
        print(
            f"Performance ratio: {avg_total / diskcache_avg_time:.2f}x slower than diskcache"
        )


def analyze_system_calls():
    """分析系统调用模式"""
    print("\n🔧 System Call Analysis")
    print("=" * 60)

    test_data = b"x" * 1024

    print("Analyzing file system operations...")

    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = os.path.join(temp_dir, "diskcache_rs")
        cache = diskcache_rs.Cache(cache_dir)

        # Count files before
        files_before = len(list(Path(cache_dir).rglob("*")))

        # Perform operations
        for i in range(10):
            cache.set(f"key_{i}", test_data)

        # Count files after
        files_after = len(list(Path(cache_dir).rglob("*")))

        print(f"Files created: {files_after - files_before}")
        print(f"Files per operation: {(files_after - files_before) / 10:.1f}")

        # List all files
        print("\nFiles in cache directory:")
        for file_path in sorted(Path(cache_dir).rglob("*")):
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"  {file_path.name}: {size} bytes")


def test_different_data_sizes():
    """测试不同数据大小的性能"""
    print("\n📏 Performance vs Data Size Analysis")
    print("=" * 60)

    sizes = [100, 500, 1024, 2048, 4096, 8192, 16384, 32768]

    for size in sizes:
        test_data = b"x" * size

        # Test diskcache_rs
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = os.path.join(temp_dir, "diskcache_rs")
            cache = diskcache_rs.Cache(cache_dir)

            times = []
            for i in range(100):
                start = time.perf_counter_ns()
                cache.set(f"key_{i}", test_data)
                end = time.perf_counter_ns()
                times.append(end - start)

            avg_time = sum(times) / len(times) / 1000  # μs
            ops_per_sec = 1_000_000 / avg_time

            print(f"{size:5d} bytes: {avg_time:6.1f} μs ({ops_per_sec:6.1f} ops/s)")


def main():
    """主分析函数"""
    print("🔬 Detailed Performance Profiling for diskcache_rs")
    print("=" * 60)

    profile_single_operation()
    analyze_memory_patterns()
    compare_operation_breakdown()
    analyze_system_calls()
    test_different_data_sizes()

    print("\n" + "=" * 60)
    print("✅ Detailed profiling completed!")
    print("\n💡 Key insights:")
    print("- Look for high-frequency function calls in the profile")
    print("- Check memory allocation patterns for unnecessary copies")
    print("- Analyze file system operations for optimization opportunities")
    print("- Compare performance across different data sizes")


if __name__ == "__main__":
    main()
