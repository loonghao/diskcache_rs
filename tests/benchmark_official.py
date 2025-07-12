#!/usr/bin/env python3
"""
Official diskcache-style benchmarks for diskcache_rs

This script replicates the official diskcache benchmarks to provide
direct performance comparisons. Based on:
https://grantjenks.com/docs/diskcache/cache-benchmarks.html

Workload characteristics:
- Single Access: 1 worker process, 100,000 operations
- Concurrent Access: 8 worker processes, 800,000 total operations
- Operation mix: 89% gets, 9% sets, 1% deletes
- ~10% cache miss rate
"""

import argparse
import os
import random
import statistics
import tempfile
import time
from collections import defaultdict

# Import both implementations for comparison
try:
    import diskcache

    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False

from diskcache_rs import Cache as RustCache


class BenchmarkRunner:
    """Runs official diskcache-style benchmarks"""

    def __init__(self, operations=100000, key_range=1000):
        self.operations = operations
        self.key_range = key_range
        self.results = defaultdict(list)

    def generate_workload(self):
        """Generate the official diskcache workload pattern"""
        workload = []

        # 89% gets (88,966 operations)
        get_count = int(self.operations * 0.89)
        for _ in range(get_count):
            key = f"key_{random.randint(0, self.key_range)}"
            workload.append(("get", key))

        # 9% sets (9,021 operations)
        set_count = int(self.operations * 0.09)
        for i in range(set_count):
            key = f"set_key_{i}"
            value = f"value_{i}"
            workload.append(("set", key, value))

        # 1% deletes (1,012 operations)
        delete_count = self.operations - get_count - set_count
        for _ in range(delete_count):
            key = f"key_{random.randint(0, self.key_range // 2)}"
            workload.append(("delete", key))

        # Shuffle to simulate real-world access patterns
        random.shuffle(workload)
        return workload

    def run_single_access_rust(self, cache_dir):
        """Run single access benchmark with Rust cache"""
        cache = RustCache(cache_dir)
        workload = self.generate_workload()

        # Pre-populate cache with some data
        for i in range(self.key_range // 2):
            cache.set(f"key_{i}", f"initial_value_{i}")

        timings = {"get": [], "set": [], "delete": []}
        misses = {"get": 0, "set": 0, "delete": 0}

        for operation in workload:
            op_type = operation[0]
            start_time = time.perf_counter()

            try:
                if op_type == "get":
                    result = cache.get(operation[1])
                    if result is None:
                        misses["get"] += 1
                elif op_type == "set":
                    cache.set(operation[1], operation[2])
                elif op_type == "delete":
                    try:
                        del cache[operation[1]]
                    except KeyError:
                        misses["delete"] += 1
            except Exception:
                misses[op_type] += 1

            end_time = time.perf_counter()
            timings[op_type].append(
                (end_time - start_time) * 1_000_000
            )  # Convert to microseconds

        return timings, misses

    def run_single_access_python(self, cache_dir):
        """Run single access benchmark with Python diskcache"""
        if not DISKCACHE_AVAILABLE:
            return None, None

        cache = diskcache.Cache(cache_dir)
        workload = self.generate_workload()

        # Pre-populate cache with some data
        for i in range(self.key_range // 2):
            cache.set(f"key_{i}", f"initial_value_{i}")

        timings = {"get": [], "set": [], "delete": []}
        misses = {"get": 0, "set": 0, "delete": 0}

        for operation in workload:
            op_type = operation[0]
            start_time = time.perf_counter()

            try:
                if op_type == "get":
                    result = cache.get(operation[1])
                    if result is None:
                        misses["get"] += 1
                elif op_type == "set":
                    cache.set(operation[1], operation[2])
                elif op_type == "delete":
                    try:
                        del cache[operation[1]]
                    except KeyError:
                        misses["delete"] += 1
            except Exception:
                misses[op_type] += 1

            end_time = time.perf_counter()
            timings[op_type].append(
                (end_time - start_time) * 1_000_000
            )  # Convert to microseconds

        cache.close()
        return timings, misses

    def print_results(self, name, timings, misses):
        """Print results in official diskcache format"""
        print(f"\nTimings for {name}")
        print("=" * 79)
        print(
            f"{'Action':>9} {'Count':>9} {'Miss':>9} {'Median':>9} {'P90':>9} {'P99':>9} {'Max':>9} {'Total':>9}"
        )
        print("=" * 79)

        total_time = 0
        total_count = 0

        for op_type in ["get", "set", "delete"]:
            if timings[op_type]:
                times = timings[op_type]
                count = len(times)
                miss = misses[op_type]
                median = statistics.median(times)
                p90 = statistics.quantiles(times, n=10)[8]  # 90th percentile
                p99 = statistics.quantiles(times, n=100)[98]  # 99th percentile
                max_time = max(times)
                op_total = sum(times) / 1_000_000  # Convert back to seconds

                total_time += op_total
                total_count += count

                print(
                    f"{op_type:>9} {count:>9} {miss:>9} {median:>8.3f}us {p90:>8.3f}us {p99:>8.3f}us {max_time:>8.3f}us {op_total:>8.3f}s"
                )

        print("=" * 79)
        print(
            f"{'Total':>9} {total_count:>9} {'':<9} {'':<9} {'':<9} {'':<9} {'':<9} {total_time:>8.3f}s"
        )
        print("=" * 79)


def main():
    parser = argparse.ArgumentParser(
        description="Run official diskcache-style benchmarks"
    )
    parser.add_argument(
        "-n",
        "--operations",
        type=int,
        default=10000,
        help="Number of operations (default: 10000, official: 100000)",
    )
    parser.add_argument(
        "-k",
        "--key-range",
        type=int,
        default=1000,
        help="Range of keys (default: 1000)",
    )
    parser.add_argument(
        "--rust-only", action="store_true", help="Only run Rust benchmarks"
    )
    parser.add_argument(
        "--python-only",
        action="store_true",
        help="Only run Python diskcache benchmarks",
    )

    args = parser.parse_args()

    if args.python_only and not DISKCACHE_AVAILABLE:
        print("Error: diskcache not available for Python benchmarks")
        return 1

    print(f"Running benchmarks with {args.operations:,} operations")
    print(f"Key range: {args.key_range}")
    print("=" * 79)

    runner = BenchmarkRunner(args.operations, args.key_range)

    # Run Rust benchmarks
    if not args.python_only:
        print("\n🦀 Running Rust diskcache_rs benchmarks...")
        with tempfile.TemporaryDirectory() as temp_dir:
            rust_dir = os.path.join(temp_dir, "rust_cache")
            start_time = time.time()
            rust_timings, rust_misses = runner.run_single_access_rust(rust_dir)
            rust_total_time = time.time() - start_time

            runner.print_results("diskcache_rs.Cache", rust_timings, rust_misses)
            print(f"Total benchmark time: {rust_total_time:.3f}s")

    # Run Python benchmarks
    if not args.rust_only and DISKCACHE_AVAILABLE:
        print("\n🐍 Running Python diskcache benchmarks...")
        with tempfile.TemporaryDirectory() as temp_dir:
            python_dir = os.path.join(temp_dir, "python_cache")
            start_time = time.time()
            python_timings, python_misses = runner.run_single_access_python(python_dir)
            python_total_time = time.time() - start_time

            if python_timings:
                runner.print_results("diskcache.Cache", python_timings, python_misses)
                print(f"Total benchmark time: {python_total_time:.3f}s")

    print("\n✅ Benchmarks completed!")
    return 0


if __name__ == "__main__":
    exit(main())
