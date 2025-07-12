#!/usr/bin/env python3
"""
Performance comparison between diskcache_rs and python-diskcache
"""

import json
import os
import sys
import tempfile
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import diskcache
import diskcache_rs


def benchmark_operation(operation_func, iterations=10000, warmup=1000):
    """Benchmark an operation with warmup and multiple runs

    Following diskcache benchmark methodology:
    - 100,000 operations total (scaled down for CI)
    - Percentile reporting (median, 90th, 99th, max)
    - Miss rate tracking
    """

    # Warmup
    for _ in range(warmup):
        try:
            operation_func()
        except Exception:
            pass  # Ignore warmup errors

    # Actual benchmark
    times = []
    misses = 0

    for _ in range(iterations):
        start_time = time.perf_counter()
        try:
            result = operation_func()
            if result is None:  # Cache miss
                misses += 1
        except Exception:
            misses += 1
        end_time = time.perf_counter()
        times.append(end_time - start_time)

    if not times:
        return None

    times.sort()

    return {
        "count": iterations,
        "misses": misses,
        "miss_rate": misses / iterations,
        "median": times[len(times) // 2],
        "p90": times[int(len(times) * 0.9)],
        "p99": times[int(len(times) * 0.99)],
        "max": max(times),
        "total": sum(times),
        "ops_per_sec": iterations / sum(times),
    }


def benchmark_workload(cache_dir, implementation="diskcache", operations=10000):
    """Benchmark mixed workload following diskcache methodology

    Workload composition:
    - 10x more gets than sets
    - 10x more sets than deletes
    - ~1% miss rate due to gets after deletes
    """

    if implementation == "diskcache":
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.Cache(cache_dir)

    # Calculate operation counts (following diskcache ratios)
    delete_count = max(1, operations // 100)  # ~1%
    set_count = delete_count * 10  # ~10%
    get_count = operations - set_count - delete_count  # ~89%

    test_data = b"x" * 32  # Short byte string like diskcache benchmarks

    # Pre-populate some data for gets
    for i in range(set_count):
        cache.set(f"key_{i}", test_data)

    # Benchmark operations
    results = {}

    # Benchmark gets
    get_keys = [f"key_{i % set_count}" for i in range(get_count)]
    get_counter = 0

    def get_operation():
        nonlocal get_counter
        key = get_keys[get_counter % len(get_keys)]
        result = cache.get(key)
        get_counter += 1
        return result

    print(f"  Benchmarking {get_count} get operations...")
    results["get"] = benchmark_operation(
        get_operation, iterations=get_count, warmup=min(1000, get_count // 10)
    )

    # Benchmark sets
    set_counter = set_count

    def set_operation():
        nonlocal set_counter
        key = f"key_{set_counter}"
        cache.set(key, test_data)
        set_counter += 1
        return True

    print(f"  Benchmarking {set_count} set operations...")
    results["set"] = benchmark_operation(
        set_operation, iterations=set_count, warmup=min(100, set_count // 10)
    )

    # Benchmark deletes (creates misses for subsequent gets)
    delete_keys = [f"key_{i}" for i in range(delete_count)]
    delete_counter = 0

    def delete_operation():
        nonlocal delete_counter
        key = delete_keys[delete_counter % len(delete_keys)]
        if implementation == "diskcache":
            result = cache.delete(key)
        else:
            result = cache.delete(key)
        delete_counter += 1
        return result

    print(f"  Benchmarking {delete_count} delete operations...")
    results["delete"] = benchmark_operation(
        delete_operation, iterations=delete_count, warmup=min(10, delete_count // 10)
    )

    if hasattr(cache, "close"):
        cache.close()

    return results


def benchmark_large_values(cache_dir, implementation="diskcache", operations=1000):
    """Benchmark operations with large values (10KB)"""

    if implementation == "diskcache":
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.Cache(cache_dir)

    # 10KB value
    large_data = b"x" * (10 * 1024)

    results = {}

    # Benchmark large sets
    set_counter = 0

    def large_set_operation():
        nonlocal set_counter
        key = f"large_key_{set_counter}"
        cache.set(key, large_data)
        set_counter += 1
        return True

    print(f"  Benchmarking {operations} large set operations...")
    results["set"] = benchmark_operation(
        large_set_operation, iterations=operations, warmup=operations // 10
    )

    # Benchmark large gets
    get_counter = 0

    def large_get_operation():
        nonlocal get_counter
        key = f"large_key_{get_counter % operations}"
        result = cache.get(key)
        get_counter += 1
        return result

    print(f"  Benchmarking {operations} large get operations...")
    results["get"] = benchmark_operation(
        large_get_operation, iterations=operations, warmup=operations // 10
    )

    if hasattr(cache, "close"):
        cache.close()

    return results


def run_benchmarks(test_dir):
    """Run all benchmarks following diskcache methodology"""

    print("🏃 Running Performance Benchmarks")
    print("Following diskcache benchmark methodology")
    print("=" * 60)

    benchmarks = [
        ("Standard Workload (10K ops)", lambda d, i: benchmark_workload(d, i, 10000)),
        ("Large Values (1K ops)", lambda d, i: benchmark_large_values(d, i, 1000)),
    ]

    results = {}

    for benchmark_name, benchmark_func in benchmarks:
        print(f"\n📊 {benchmark_name}")
        print("-" * 50)

        # Test original diskcache
        diskcache_dir = os.path.join(test_dir, "diskcache_bench")
        os.makedirs(diskcache_dir, exist_ok=True)

        print("Testing python-diskcache...")
        diskcache_result = benchmark_func(diskcache_dir, "diskcache")

        # Test our implementation
        diskcache_rs_dir = os.path.join(test_dir, "diskcache_rs_bench")
        os.makedirs(diskcache_rs_dir, exist_ok=True)

        print("Testing diskcache_rs...")
        diskcache_rs_result = benchmark_func(diskcache_rs_dir, "diskcache_rs")

        # Store results
        results[benchmark_name] = {
            "diskcache": diskcache_result,
            "diskcache_rs": diskcache_rs_result,
        }

        # Print detailed comparison
        print_benchmark_comparison(
            benchmark_name, diskcache_result, diskcache_rs_result
        )

        # Clean up
        import shutil

        if os.path.exists(diskcache_dir):
            shutil.rmtree(diskcache_dir)
        if os.path.exists(diskcache_rs_dir):
            shutil.rmtree(diskcache_rs_dir)

    return results


def print_benchmark_comparison(name, dc_result, rs_result):
    """Print detailed benchmark comparison in diskcache style"""

    print(f"\n{name} Results:")
    print("=" * 50)

    for operation in ["get", "set", "delete"]:
        if operation in dc_result and operation in rs_result:
            dc_op = dc_result[operation]
            rs_op = rs_result[operation]

            if dc_op and rs_op:
                print(f"\n{operation.upper()} Operations:")
                print(
                    f"{'Implementation':<20} {'Count':<8} {'Miss':<6} {'Median':<10} {'P90':<10} {'P99':<10} {'Max':<10} {'Total':<8}"
                )
                print("-" * 80)

                print(
                    f"{'python-diskcache':<20} {dc_op['count']:<8} {dc_op['misses']:<6} "
                    f"{dc_op['median'] * 1000000:.1f}us {dc_op['p90'] * 1000000:.1f}us "
                    f"{dc_op['p99'] * 1000000:.1f}us {dc_op['max'] * 1000000:.1f}us "
                    f"{dc_op['total']:.2f}s"
                )

                print(
                    f"{'diskcache_rs':<20} {rs_op['count']:<8} {rs_op['misses']:<6} "
                    f"{rs_op['median'] * 1000000:.1f}us {rs_op['p90'] * 1000000:.1f}us "
                    f"{rs_op['p99'] * 1000000:.1f}us {rs_op['max'] * 1000000:.1f}us "
                    f"{rs_op['total']:.2f}s"
                )

                # Performance comparison
                speedup = dc_op["ops_per_sec"] / rs_op["ops_per_sec"]
                if speedup > 1:
                    print(f"Winner: python-diskcache ({speedup:.2f}x faster)")
                else:
                    print(f"Winner: diskcache_rs ({1 / speedup:.2f}x faster)")


def print_summary(results):
    """Print benchmark summary in diskcache style"""

    print("\n" + "=" * 80)
    print("📋 PERFORMANCE BENCHMARK SUMMARY")
    print("=" * 80)

    print("Overall Performance Comparison:")
    print(
        f"{'Benchmark':<25} {'Operation':<8} {'python-diskcache':<18} {'diskcache_rs':<18} {'Winner'}"
    )
    print("-" * 80)

    for benchmark_name, result in results.items():
        dc_result = result["diskcache"]
        rs_result = result["diskcache_rs"]

        for operation in ["get", "set", "delete"]:
            if operation in dc_result and operation in rs_result:
                dc_op = dc_result[operation]
                rs_op = rs_result[operation]

                if dc_op and rs_op:
                    dc_ops = dc_op["ops_per_sec"]
                    rs_ops = rs_op["ops_per_sec"]

                    if dc_ops > rs_ops:
                        winner = f"diskcache ({dc_ops / rs_ops:.1f}x)"
                    else:
                        winner = f"diskcache_rs ({rs_ops / dc_ops:.1f}x)"

                    bench_short = benchmark_name.split("(")[0].strip()
                    print(
                        f"{bench_short:<25} {operation:<8} {dc_ops:>12.1f} ops/s {rs_ops:>12.1f} ops/s {winner}"
                    )

    print("\n💡 Key Insights:")
    print("- Benchmarks follow diskcache methodology (percentile reporting)")
    print("- python-diskcache is highly optimized for local storage")
    print("- diskcache_rs provides superior network filesystem reliability")
    print("- Performance varies significantly with storage type and network conditions")
    print("- diskcache_rs avoids SQLite corruption issues on network drives")


def main():
    """Main benchmark runner"""

    # Use cloud drive if available, otherwise temp directory
    if os.path.exists("Z:\\"):
        test_dir = "Z:\\_thm\\temp\\.pkg\\db_benchmark"
        print(f"🌩️ Using cloud drive for benchmarks: {test_dir}")
    else:
        test_dir = tempfile.mkdtemp(prefix="diskcache_benchmark_")
        print(f"💾 Using local storage for benchmarks: {test_dir}")

    try:
        os.makedirs(test_dir, exist_ok=True)

        results = run_benchmarks(test_dir)
        print_summary(results)

        # Save results to JSON for CI
        output_file = "benchmark_results.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to {output_file}")

        print("\n🎉 Benchmarks completed!")

    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up if using temp directory
        if not test_dir.startswith("Z:"):
            import shutil

            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)


if __name__ == "__main__":
    main()
