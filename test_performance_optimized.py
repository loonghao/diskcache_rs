#!/usr/bin/env python3
"""
Test the performance improvements with memory cache
"""

import os
import sys
import time
import tempfile
import statistics

import diskcache_rs

def benchmark_read_performance():
    """Test read performance with and without memory cache"""
    print("🚀 Testing Read Performance Optimization")
    print("=" * 50)
    
    # Test data
    test_data = {
        f"key_{i}": f"value_{i}_" + "x" * 100  # ~110 bytes each
        for i in range(1000)
    }
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Test 1: Without memory cache
        print("\n📊 Test 1: Without Memory Cache")
        cache_no_mem = diskcache_rs.PyCache(
            temp_dir + "_no_mem",
            max_size=10*1024*1024,
            max_entries=10000
        )
        
        # Populate cache
        for key, value in test_data.items():
            cache_no_mem.set(key, value.encode())
        
        # Measure read performance
        read_times = []
        for _ in range(100):  # 100 reads
            start = time.perf_counter()
            for i in range(0, 100, 10):  # Read every 10th item
                key = f"key_{i}"
                cache_no_mem.get(key)
            end = time.perf_counter()
            read_times.append(end - start)
        
        avg_time_no_mem = statistics.mean(read_times)
        print(f"Average time for 10 reads: {avg_time_no_mem*1000:.2f}ms")
        print(f"Average time per read: {avg_time_no_mem*100:.2f}ms")
        
        # Test 2: With memory cache (default settings)
        print("\n📊 Test 2: With Memory Cache (Default)")
        cache_with_mem = diskcache_rs.PyCache(
            temp_dir + "_with_mem",
            max_size=10*1024*1024,
            max_entries=10000
        )
        
        # Populate cache
        for key, value in test_data.items():
            cache_with_mem.set(key, value.encode())
        
        # First read to populate memory cache
        for i in range(0, 100, 10):
            key = f"key_{i}"
            cache_with_mem.get(key)
        
        # Measure read performance (should hit memory cache)
        read_times_mem = []
        for _ in range(100):  # 100 reads
            start = time.perf_counter()
            for i in range(0, 100, 10):  # Read every 10th item
                key = f"key_{i}"
                cache_with_mem.get(key)
            end = time.perf_counter()
            read_times_mem.append(end - start)
        
        avg_time_with_mem = statistics.mean(read_times_mem)
        print(f"Average time for 10 reads: {avg_time_with_mem*1000:.2f}ms")
        print(f"Average time per read: {avg_time_with_mem*100:.2f}ms")
        
        # Calculate improvement
        if avg_time_with_mem > 0:
            speedup = avg_time_no_mem / avg_time_with_mem
            print(f"\n🚀 Memory cache speedup: {speedup:.2f}x")
        
        # Get memory cache stats
        print(f"\nMemory cache stats: {cache_with_mem.stats()}")

def test_cache_hit_patterns():
    """Test different cache hit patterns"""
    print("\n🎯 Testing Cache Hit Patterns")
    print("=" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Populate with 100 items
        for i in range(100):
            cache.set(f"item_{i}", f"data_{i}".encode())
        
        # Pattern 1: Sequential access (should benefit from memory cache)
        print("\n📈 Pattern 1: Sequential Access")
        start = time.perf_counter()
        for _ in range(10):  # 10 rounds
            for i in range(20):  # Access first 20 items
                cache.get(f"item_{i}")
        sequential_time = time.perf_counter() - start
        print(f"Sequential access time: {sequential_time*1000:.2f}ms")
        
        # Pattern 2: Random access (mixed memory/disk hits)
        print("\n🎲 Pattern 2: Random Access")
        import random
        random_keys = [f"item_{random.randint(0, 99)}" for _ in range(200)]
        
        start = time.perf_counter()
        for key in random_keys:
            cache.get(key)
        random_time = time.perf_counter() - start
        print(f"Random access time: {random_time*1000:.2f}ms")
        
        # Pattern 3: Working set (should be very fast)
        print("\n💼 Pattern 3: Working Set (10 items)")
        working_set = [f"item_{i}" for i in range(10)]
        
        # Prime the working set
        for key in working_set:
            cache.get(key)
        
        start = time.perf_counter()
        for _ in range(100):  # 100 rounds
            for key in working_set:
                cache.get(key)
        working_set_time = time.perf_counter() - start
        print(f"Working set time: {working_set_time*1000:.2f}ms")
        print(f"Average per access: {working_set_time*10:.2f}ms")

def test_memory_cache_eviction():
    """Test memory cache eviction behavior"""
    print("\n🗑️ Testing Memory Cache Eviction")
    print("=" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create cache with small memory limit
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Add items that should exceed memory cache
        print("Adding 1000 items...")
        for i in range(1000):
            data = f"item_{i}_" + "x" * 1000  # ~1KB each
            cache.set(f"key_{i}", data.encode())
        
        # Test access patterns
        print("\nTesting access to recently added items (should be in memory)...")
        start = time.perf_counter()
        for i in range(990, 1000):  # Last 10 items
            cache.get(f"key_{i}")
        recent_time = time.perf_counter() - start
        print(f"Recent items access time: {recent_time*1000:.2f}ms")
        
        print("\nTesting access to old items (should be on disk)...")
        start = time.perf_counter()
        for i in range(0, 10):  # First 10 items
            cache.get(f"key_{i}")
        old_time = time.perf_counter() - start
        print(f"Old items access time: {old_time*1000:.2f}ms")
        
        if old_time > 0:
            ratio = old_time / recent_time if recent_time > 0 else float('inf')
            print(f"Disk vs Memory ratio: {ratio:.2f}x")

def test_cloud_drive_performance():
    """Test performance on cloud drive"""
    print("\n☁️ Testing Cloud Drive Performance")
    print("=" * 40)
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_perf_optimized"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping cloud drive test")
        return
    
    try:
        os.makedirs(cloud_path, exist_ok=True)
        cache = diskcache_rs.PyCache(cloud_path)
        
        # Test write performance
        print("Testing write performance...")
        write_times = []
        for i in range(100):
            data = f"cloud_data_{i}_" + "x" * 500  # ~512 bytes
            start = time.perf_counter()
            cache.set(f"cloud_key_{i}", data.encode())
            end = time.perf_counter()
            write_times.append(end - start)
        
        avg_write = statistics.mean(write_times)
        print(f"Average write time: {avg_write*1000:.2f}ms")
        
        # Test read performance (first read - from disk)
        print("Testing read performance (from disk)...")
        read_times_disk = []
        for i in range(100):
            start = time.perf_counter()
            cache.get(f"cloud_key_{i}")
            end = time.perf_counter()
            read_times_disk.append(end - start)
        
        avg_read_disk = statistics.mean(read_times_disk)
        print(f"Average read time (disk): {avg_read_disk*1000:.2f}ms")
        
        # Test read performance (second read - from memory cache)
        print("Testing read performance (from memory)...")
        read_times_mem = []
        for i in range(100):
            start = time.perf_counter()
            cache.get(f"cloud_key_{i}")
            end = time.perf_counter()
            read_times_mem.append(end - start)
        
        avg_read_mem = statistics.mean(read_times_mem)
        print(f"Average read time (memory): {avg_read_mem*1000:.2f}ms")
        
        if avg_read_mem > 0:
            speedup = avg_read_disk / avg_read_mem
            print(f"Memory cache speedup on cloud drive: {speedup:.2f}x")
        
        # Clean up
        cache.clear()
        
    except Exception as e:
        print(f"Cloud drive test failed: {e}")

def main():
    print("🔬 Performance Optimization Tests")
    print("=" * 60)
    
    try:
        benchmark_read_performance()
        test_cache_hit_patterns()
        test_memory_cache_eviction()
        test_cloud_drive_performance()
        
        print("\n🎉 All performance tests completed!")
        
    except Exception as e:
        print(f"\n❌ Performance test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
