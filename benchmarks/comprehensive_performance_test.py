#!/usr/bin/env python3
"""
Comprehensive performance test suite for diskcache_rs
Tests all major operations across different data sizes and scenarios
"""

import time
import random
import string
import statistics
import tempfile
import shutil
import os
from typing import List, Dict, Any, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import diskcache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False
    print("⚠️  python-diskcache not available, skipping baseline comparisons")

try:
    from diskcache_rs import Cache as RustCache
    DISKCACHE_RS_AVAILABLE = True
except ImportError:
    DISKCACHE_RS_AVAILABLE = False
    print("❌ diskcache_rs not available!")
    exit(1)


class PerformanceTester:
    def __init__(self):
        self.data_sizes = [
            (100, "100B"),
            (1024, "1KB"), 
            (4096, "4KB"),
            (16384, "16KB"),
            (32768, "32KB"),
            (65536, "64KB"),
            (131072, "128KB"),
            (262144, "256KB"),
        ]
        
        self.test_counts = {
            "quick": 100,
            "standard": 500,
            "intensive": 1000,
        }
        
    def generate_test_data(self, size: int) -> bytes:
        """Generate random test data of specified size"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=size)).encode()
    
    def generate_keys(self, count: int) -> List[str]:
        """Generate unique test keys"""
        return [f"test_key_{i:06d}" for i in range(count)]
    
    def measure_operation(self, operation, *args, **kwargs) -> Tuple[float, Any]:
        """Measure operation execution time and return result"""
        start_time = time.perf_counter()
        result = operation(*args, **kwargs)
        end_time = time.perf_counter()
        return (end_time - start_time) * 1_000_000, result  # Return microseconds
    
    def run_set_performance_test(self, cache, data_size: int, count: int) -> Dict[str, float]:
        """Test SET operation performance"""
        test_data = self.generate_test_data(data_size)
        keys = self.generate_keys(count)
        times = []
        
        for key in keys:
            duration, _ = self.measure_operation(cache.set, key, test_data)
            times.append(duration)
        
        return {
            "avg": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "p95": statistics.quantiles(times, n=20)[18],  # 95th percentile
            "ops_per_sec": 1_000_000 / statistics.mean(times),
        }
    
    def run_get_performance_test(self, cache, data_size: int, count: int) -> Dict[str, float]:
        """Test GET operation performance"""
        test_data = self.generate_test_data(data_size)
        keys = self.generate_keys(count)
        
        # First populate the cache
        for key in keys:
            cache.set(key, test_data)
        
        # Now measure GET performance
        times = []
        for key in keys:
            duration, result = self.measure_operation(cache.get, key)
            times.append(duration)
            assert result == test_data, "Data integrity check failed"
        
        return {
            "avg": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "p95": statistics.quantiles(times, n=20)[18],
            "ops_per_sec": 1_000_000 / statistics.mean(times),
        }
    
    def run_delete_performance_test(self, cache, data_size: int, count: int) -> Dict[str, float]:
        """Test DELETE operation performance"""
        test_data = self.generate_test_data(data_size)
        keys = self.generate_keys(count)
        
        # First populate the cache
        for key in keys:
            cache.set(key, test_data)
        
        # Now measure DELETE performance
        times = []
        for key in keys:
            duration, result = self.measure_operation(cache.delete, key)
            times.append(duration)
            assert result is True, "Delete should return True for existing keys"
        
        return {
            "avg": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "p95": statistics.quantiles(times, n=20)[18],
            "ops_per_sec": 1_000_000 / statistics.mean(times),
        }
    
    def run_mixed_workload_test(self, cache, data_size: int, count: int) -> Dict[str, Any]:
        """Test mixed workload (70% GET, 20% SET, 10% DELETE)"""
        test_data = self.generate_test_data(data_size)
        keys = self.generate_keys(count)
        
        # Pre-populate with some data
        for i in range(count // 2):
            cache.set(keys[i], test_data)
        
        operations = []
        # 70% GET, 20% SET, 10% DELETE
        for _ in range(count):
            rand = random.random()
            if rand < 0.7:  # GET
                operations.append(("get", random.choice(keys)))
            elif rand < 0.9:  # SET
                operations.append(("set", random.choice(keys), test_data))
            else:  # DELETE
                operations.append(("delete", random.choice(keys)))
        
        times = {"get": [], "set": [], "delete": []}
        
        for op in operations:
            if op[0] == "get":
                duration, _ = self.measure_operation(cache.get, op[1])
                times["get"].append(duration)
            elif op[0] == "set":
                duration, _ = self.measure_operation(cache.set, op[1], op[2])
                times["set"].append(duration)
            else:  # delete
                duration, _ = self.measure_operation(cache.delete, op[1])
                times["delete"].append(duration)
        
        results = {}
        for op_type, time_list in times.items():
            if time_list:
                results[op_type] = {
                    "avg": statistics.mean(time_list),
                    "ops_per_sec": 1_000_000 / statistics.mean(time_list),
                    "count": len(time_list),
                }
        
        return results
    
    def run_concurrent_test(self, cache_factory, data_size: int, thread_count: int, ops_per_thread: int) -> Dict[str, float]:
        """Test concurrent performance"""
        test_data = self.generate_test_data(data_size)
        
        def worker_thread(thread_id: int) -> List[float]:
            times = []
            for i in range(ops_per_thread):
                key = f"thread_{thread_id}_key_{i}"
                duration, _ = self.measure_operation(cache_factory().set, key, test_data)
                times.append(duration)
            return times
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(thread_count)]
            all_times = []
            for future in as_completed(futures):
                all_times.extend(future.result())
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        total_ops = thread_count * ops_per_thread
        
        return {
            "total_ops": total_ops,
            "total_time": total_time,
            "throughput": total_ops / total_time,
            "avg_latency": statistics.mean(all_times),
            "p95_latency": statistics.quantiles(all_times, n=20)[18],
        }
    
    def run_cache_size_scaling_test(self, cache, data_size: int) -> Dict[str, Any]:
        """Test performance as cache size grows"""
        test_data = self.generate_test_data(data_size)
        cache_sizes = [100, 500, 1000, 5000, 10000]
        results = {}
        
        for size in cache_sizes:
            # Populate cache to target size
            keys = self.generate_keys(size)
            for key in keys:
                cache.set(key, test_data)
            
            # Measure performance on additional operations
            test_keys = self.generate_keys(100)
            times = []
            for key in test_keys:
                duration, _ = self.measure_operation(cache.set, f"new_{key}", test_data)
                times.append(duration)
            
            results[size] = {
                "avg_latency": statistics.mean(times),
                "ops_per_sec": 1_000_000 / statistics.mean(times),
            }
        
        return results

    def print_performance_comparison(self, operation: str, data_size_name: str,
                                   diskcache_results: Dict, diskcache_rs_results: Dict):
        """Print performance comparison between diskcache and diskcache_rs"""
        print(f"\n📊 {operation} Performance - {data_size_name}:")
        print("=" * 60)

        if DISKCACHE_AVAILABLE and diskcache_results:
            print(f"diskcache:     {diskcache_results['avg']:8.1f}μs avg, "
                  f"{diskcache_results['median']:8.1f}μs median, "
                  f"{diskcache_results['ops_per_sec']:8.1f} ops/s")

        print(f"diskcache_rs:  {diskcache_rs_results['avg']:8.1f}μs avg, "
              f"{diskcache_rs_results['median']:8.1f}μs median, "
              f"{diskcache_rs_results['ops_per_sec']:8.1f} ops/s")

        if DISKCACHE_AVAILABLE and diskcache_results:
            speedup = diskcache_results['avg'] / diskcache_rs_results['avg']
            if speedup > 1:
                print(f"🚀 diskcache_rs is {speedup:.1f}x faster")
            else:
                print(f"⚠️  diskcache is {1/speedup:.1f}x faster")

        print(f"📈 P95 latency: {diskcache_rs_results['p95']:.1f}μs")
        print(f"⚡ Min latency: {diskcache_rs_results['min']:.1f}μs")
        print(f"🐌 Max latency: {diskcache_rs_results['max']:.1f}μs")

    def run_comprehensive_test_suite(self, test_intensity: str = "standard"):
        """Run the complete performance test suite"""
        print("🔬 diskcache_rs Comprehensive Performance Test Suite")
        print("=" * 70)

        test_count = self.test_counts[test_intensity]
        print(f"Test intensity: {test_intensity} ({test_count} operations per test)")

        # Test each operation across different data sizes
        for data_size, size_name in self.data_sizes:
            print(f"\n🎯 Testing {size_name} data...")

            # Create temporary directories for caches
            with tempfile.TemporaryDirectory() as temp_dir:
                diskcache_dir = os.path.join(temp_dir, "diskcache")
                diskcache_rs_dir = os.path.join(temp_dir, "diskcache_rs")

                # Initialize caches
                diskcache_cache = None
                if DISKCACHE_AVAILABLE:
                    diskcache_cache = diskcache.Cache(diskcache_dir)

                diskcache_rs_cache = RustCache(diskcache_rs_dir)

                # Test SET operations
                print(f"  Testing SET operations...")
                diskcache_set_results = None
                if diskcache_cache:
                    diskcache_set_results = self.run_set_performance_test(
                        diskcache_cache, data_size, test_count
                    )

                diskcache_rs_set_results = self.run_set_performance_test(
                    diskcache_rs_cache, data_size, test_count
                )

                self.print_performance_comparison(
                    "SET", size_name, diskcache_set_results, diskcache_rs_set_results
                )

                # Test GET operations
                print(f"  Testing GET operations...")
                diskcache_get_results = None
                if diskcache_cache:
                    diskcache_get_results = self.run_get_performance_test(
                        diskcache_cache, data_size, test_count
                    )

                diskcache_rs_get_results = self.run_get_performance_test(
                    diskcache_rs_cache, data_size, test_count
                )

                self.print_performance_comparison(
                    "GET", size_name, diskcache_get_results, diskcache_rs_get_results
                )

                # Test DELETE operations
                print(f"  Testing DELETE operations...")
                diskcache_delete_results = None
                if diskcache_cache:
                    diskcache_delete_results = self.run_delete_performance_test(
                        diskcache_cache, data_size, test_count
                    )

                diskcache_rs_delete_results = self.run_delete_performance_test(
                    diskcache_rs_cache, data_size, test_count
                )

                self.print_performance_comparison(
                    "DELETE", size_name, diskcache_delete_results, diskcache_rs_delete_results
                )

                # Clean up for next test
                if diskcache_cache:
                    try:
                        diskcache_cache.close()
                    except:
                        pass
                del diskcache_rs_cache
                import gc
                gc.collect()

        # Test mixed workload
        print(f"\n🔀 Mixed Workload Test (70% GET, 20% SET, 10% DELETE)")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as temp_dir:
            diskcache_rs_cache = RustCache(os.path.join(temp_dir, "mixed_test"))
            mixed_results = self.run_mixed_workload_test(diskcache_rs_cache, 1024, test_count)

            for op_type, results in mixed_results.items():
                print(f"{op_type.upper():>6}: {results['avg']:8.1f}μs avg, "
                      f"{results['ops_per_sec']:8.1f} ops/s ({results['count']} ops)")

        # Test concurrent performance
        print(f"\n🚀 Concurrent Performance Test")
        print("=" * 60)

        def create_cache():
            temp_dir = tempfile.mkdtemp()
            return RustCache(temp_dir)

        concurrent_results = self.run_concurrent_test(
            create_cache, 1024, thread_count=4, ops_per_thread=test_count // 4
        )

        print(f"Threads: 4")
        print(f"Total operations: {concurrent_results['total_ops']}")
        print(f"Total time: {concurrent_results['total_time']:.3f}s")
        print(f"Throughput: {concurrent_results['throughput']:.1f} ops/s")
        print(f"Avg latency: {concurrent_results['avg_latency']:.1f}μs")
        print(f"P95 latency: {concurrent_results['p95_latency']:.1f}μs")

        # Test cache size scaling
        print(f"\n📈 Cache Size Scaling Test")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as temp_dir:
            scaling_cache = RustCache(os.path.join(temp_dir, "scaling_test"))
            scaling_results = self.run_cache_size_scaling_test(scaling_cache, 1024)

            print("Cache Size | Avg Latency | Ops/sec")
            print("-" * 35)
            for size, results in scaling_results.items():
                print(f"{size:>9} | {results['avg_latency']:>10.1f}μs | {results['ops_per_sec']:>7.1f}")


def main():
    """Main test execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive performance test for diskcache_rs")
    parser.add_argument("--intensity", choices=["quick", "standard", "intensive"],
                       default="standard", help="Test intensity level")

    args = parser.parse_args()

    tester = PerformanceTester()
    tester.run_comprehensive_test_suite(args.intensity)

    print("\n" + "=" * 70)
    print("✅ Comprehensive performance test completed!")


if __name__ == "__main__":
    main()
