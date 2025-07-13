#!/usr/bin/env python3
"""
Optimization validation test for diskcache_rs
Focuses on validating that our optimizations are working correctly
"""

import time
import random
import string
import statistics
import tempfile
import os
from typing import List, Dict, Any, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from diskcache_rs import Cache as RustCache
except ImportError:
    print("❌ diskcache_rs not available!")
    exit(1)


class OptimizationValidator:
    def __init__(self):
        self.data_sizes = [
            (100, "100B"),
            (1024, "1KB"), 
            (4096, "4KB"),
            (16384, "16KB"),
            (32768, "32KB"),
            (65536, "64KB"),
        ]
        
    def generate_test_data(self, size: int) -> bytes:
        """Generate random test data of specified size"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=size)).encode()
    
    def measure_operation_time(self, operation, *args, **kwargs) -> float:
        """Measure operation execution time in microseconds"""
        start_time = time.perf_counter()
        result = operation(*args, **kwargs)
        end_time = time.perf_counter()
        return (end_time - start_time) * 1_000_000
    
    def test_basic_operations(self, cache_dir: str, test_count: int = 100):
        """Test basic SET/GET/DELETE operations"""
        print(f"🔧 Basic Operations Test ({test_count} operations)")
        print("=" * 60)
        
        cache = RustCache(cache_dir)
        
        for data_size, size_name in self.data_sizes:
            test_data = self.generate_test_data(data_size)
            
            # Test SET performance
            set_times = []
            for i in range(test_count):
                key = f"set_test_{i:06d}"
                duration = self.measure_operation_time(cache.set, key, test_data)
                set_times.append(duration)
            
            # Test GET performance
            get_times = []
            for i in range(test_count):
                key = f"set_test_{i:06d}"
                duration = self.measure_operation_time(cache.get, key)
                get_times.append(duration)
            
            # Test DELETE performance
            delete_times = []
            for i in range(test_count):
                key = f"set_test_{i:06d}"
                duration = self.measure_operation_time(cache.delete, key)
                delete_times.append(duration)
            
            print(f"\n📊 {size_name} Performance:")
            print(f"  SET:    {statistics.mean(set_times):6.1f}μs avg, {1_000_000/statistics.mean(set_times):8.1f} ops/s")
            print(f"  GET:    {statistics.mean(get_times):6.1f}μs avg, {1_000_000/statistics.mean(get_times):8.1f} ops/s")
            print(f"  DELETE: {statistics.mean(delete_times):6.1f}μs avg, {1_000_000/statistics.mean(delete_times):8.1f} ops/s")
        
        return cache
    
    def test_data_integrity(self, cache, test_count: int = 100):
        """Test data integrity across different sizes"""
        print(f"\n🔍 Data Integrity Test ({test_count} entries)")
        print("=" * 60)
        
        test_data_map = {}
        
        # Store data of different sizes
        for i in range(test_count):
            data_size = random.choice([100, 1024, 4096, 16384, 32768])
            test_data = self.generate_test_data(data_size)
            key = f"integrity_test_{i:06d}"
            
            cache.set(key, test_data)
            test_data_map[key] = test_data
        
        # Verify all data
        integrity_errors = 0
        for key, expected_data in test_data_map.items():
            retrieved_data = cache.get(key)
            if retrieved_data != expected_data:
                integrity_errors += 1
                print(f"❌ Integrity error for key {key}")
        
        if integrity_errors == 0:
            print("✅ All data integrity checks passed!")
        else:
            print(f"❌ {integrity_errors} integrity errors found!")
        
        return integrity_errors == 0
    
    def test_concurrent_access(self, cache_factory, thread_count: int = 4, ops_per_thread: int = 100):
        """Test concurrent access performance and safety"""
        print(f"\n🚀 Concurrent Access Test ({thread_count} threads, {ops_per_thread} ops each)")
        print("=" * 60)
        
        test_data = self.generate_test_data(1024)
        
        def worker_thread(thread_id: int) -> Dict[str, float]:
            cache = cache_factory()
            times = {"set": [], "get": [], "delete": []}
            
            # SET operations
            for i in range(ops_per_thread):
                key = f"thread_{thread_id}_key_{i:06d}"
                duration = self.measure_operation_time(cache.set, key, test_data)
                times["set"].append(duration)
            
            # GET operations
            for i in range(ops_per_thread):
                key = f"thread_{thread_id}_key_{i:06d}"
                duration = self.measure_operation_time(cache.get, key)
                times["get"].append(duration)
            
            # DELETE operations
            for i in range(ops_per_thread):
                key = f"thread_{thread_id}_key_{i:06d}"
                duration = self.measure_operation_time(cache.delete, key)
                times["delete"].append(duration)
            
            return {
                "set_avg": statistics.mean(times["set"]),
                "get_avg": statistics.mean(times["get"]),
                "delete_avg": statistics.mean(times["delete"]),
            }
        
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = [executor.submit(worker_thread, i) for i in range(thread_count)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.perf_counter()
        total_time = end_time - start_time
        total_ops = thread_count * ops_per_thread * 3  # SET + GET + DELETE
        
        # Calculate averages across all threads
        avg_set = statistics.mean([r["set_avg"] for r in results])
        avg_get = statistics.mean([r["get_avg"] for r in results])
        avg_delete = statistics.mean([r["delete_avg"] for r in results])
        
        print(f"Total operations: {total_ops}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Overall throughput: {total_ops / total_time:.1f} ops/s")
        print(f"Average latencies:")
        print(f"  SET:    {avg_set:6.1f}μs")
        print(f"  GET:    {avg_get:6.1f}μs")
        print(f"  DELETE: {avg_delete:6.1f}μs")
        
        return total_ops / total_time
    
    def test_cache_size_limits(self, cache_dir: str):
        """Test cache behavior with size limits"""
        print(f"\n📏 Cache Size Limits Test")
        print("=" * 60)
        
        # Create cache with size limit
        cache = RustCache(cache_dir, max_size=1024*1024)  # 1MB limit
        
        test_data = self.generate_test_data(10240)  # 10KB per entry
        entries_added = 0
        
        # Add entries until we hit the limit
        for i in range(200):  # Should exceed 1MB limit
            key = f"size_test_{i:06d}"
            try:
                cache.set(key, test_data)
                entries_added += 1
            except Exception as e:
                print(f"Exception at entry {i}: {e}")
                break
        
        print(f"Entries added: {entries_added}")
        print(f"Theoretical max: {1024*1024 // 10240} entries")
        
        # Verify some entries still exist
        existing_count = 0
        for i in range(min(50, entries_added)):
            key = f"size_test_{i:06d}"
            if cache.get(key) is not None:
                existing_count += 1
        
        print(f"Entries still accessible: {existing_count}/50 checked")
        
        return cache
    
    def test_performance_regression(self, cache_dir: str):
        """Test for performance regressions"""
        print(f"\n📈 Performance Regression Test")
        print("=" * 60)
        
        cache = RustCache(cache_dir)
        
        # Expected performance thresholds (ops/s)
        performance_thresholds = {
            "100B": {"set": 15000, "get": 300000, "delete": 200000},
            "1KB": {"set": 10000, "get": 150000, "delete": 150000},  # Adjusted for realistic expectations
            "4KB": {"set": 7000, "get": 100000, "delete": 100000},
            "16KB": {"set": 3000, "get": 50000, "delete": 50000},
            "32KB": {"set": 2000, "get": 20000, "delete": 20000},
            "64KB": {"set": 1000, "get": 10000, "delete": 10000},
        }
        
        regression_found = False
        
        for data_size, size_name in self.data_sizes:
            test_data = self.generate_test_data(data_size)
            test_count = 100
            
            # Measure SET performance
            set_times = []
            for i in range(test_count):
                key = f"perf_test_{i:06d}"
                duration = self.measure_operation_time(cache.set, key, test_data)
                set_times.append(duration)
            
            set_ops_per_sec = 1_000_000 / statistics.mean(set_times)
            
            # Measure GET performance
            get_times = []
            for i in range(test_count):
                key = f"perf_test_{i:06d}"
                duration = self.measure_operation_time(cache.get, key)
                get_times.append(duration)
            
            get_ops_per_sec = 1_000_000 / statistics.mean(get_times)
            
            # Measure DELETE performance
            delete_times = []
            for i in range(test_count):
                key = f"perf_test_{i:06d}"
                duration = self.measure_operation_time(cache.delete, key)
                delete_times.append(duration)
            
            delete_ops_per_sec = 1_000_000 / statistics.mean(delete_times)
            
            # Check against thresholds
            thresholds = performance_thresholds.get(size_name, {})
            
            print(f"\n{size_name} Performance:")
            
            for op, actual_perf in [("set", set_ops_per_sec), ("get", get_ops_per_sec), ("delete", delete_ops_per_sec)]:
                threshold = thresholds.get(op, 0)
                status = "✅" if actual_perf >= threshold else "❌"
                if actual_perf < threshold:
                    regression_found = True
                
                print(f"  {op.upper():>6}: {actual_perf:8.1f} ops/s (threshold: {threshold:8.1f}) {status}")
        
        if not regression_found:
            print("\n✅ No performance regressions detected!")
        else:
            print("\n❌ Performance regressions detected!")
        
        return not regression_found


def main():
    """Main test execution"""
    print("🔬 diskcache_rs Optimization Validation Test Suite")
    print("=" * 70)
    
    validator = OptimizationValidator()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test basic operations
        cache = validator.test_basic_operations(os.path.join(temp_dir, "basic_test"))
        
        # Test data integrity
        integrity_ok = validator.test_data_integrity(cache)
        
        # Test concurrent access
        def create_cache():
            return RustCache(os.path.join(temp_dir, f"concurrent_{threading.current_thread().ident}"))
        
        throughput = validator.test_concurrent_access(create_cache)
        
        # Test cache size limits
        cache_with_limits = validator.test_cache_size_limits(os.path.join(temp_dir, "size_test"))
        
        # Test performance regression
        perf_ok = validator.test_performance_regression(os.path.join(temp_dir, "perf_test"))
    
    print("\n" + "=" * 70)
    print("📋 Test Summary:")
    print(f"  Data Integrity: {'✅ PASS' if integrity_ok else '❌ FAIL'}")
    print(f"  Performance:    {'✅ PASS' if perf_ok else '❌ FAIL'}")
    print(f"  Throughput:     {throughput:.1f} ops/s")
    
    if integrity_ok and perf_ok:
        print("\n🎉 All optimization validations passed!")
        return 0
    else:
        print("\n⚠️  Some validations failed!")
        return 1


if __name__ == "__main__":
    exit(main())
