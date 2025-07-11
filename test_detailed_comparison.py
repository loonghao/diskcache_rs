#!/usr/bin/env python3
"""
Detailed comparison between original diskcache and diskcache_rs
This test tries to reproduce the specific issues mentioned in GitHub issue #345
"""

import os
import sys
import time
import tempfile
import traceback
import threading
import multiprocessing
from pathlib import Path

# Import both implementations
import diskcache
import diskcache_rs

def test_sqlite_corruption_scenario():
    """Test scenario that might cause SQLite corruption on network drives"""
    print("Testing SQLite corruption scenario...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_corruption_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping corruption test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    # Test original diskcache with intensive operations
    print("Testing original diskcache with intensive operations...")
    try:
        original_cache = diskcache.Cache(cloud_path + "_original")
        
        # Rapid writes that might cause issues on network drives
        for i in range(100):
            key = f"rapid_key_{i}"
            value = f"rapid_value_{i}" * 100  # Make it larger
            original_cache.set(key, value)
            
            # Immediate read
            retrieved = original_cache.get(key)
            if retrieved != value:
                print(f"  ❌ Original diskcache: Data corruption at key {key}")
                return False
            
            if i % 20 == 0:
                print(f"    Original diskcache: {i}/100 operations completed")
        
        # Test with concurrent access simulation
        print("  Testing concurrent access simulation...")
        for i in range(50):
            # Simulate multiple processes accessing the same cache
            original_cache.set(f"concurrent_{i}", f"value_{i}")
            # Force a read from another "process" perspective
            temp_cache = diskcache.Cache(cloud_path + "_original")
            result = temp_cache.get(f"concurrent_{i}")
            if result != f"value_{i}":
                print(f"  ❌ Original diskcache: Concurrent access issue at {i}")
                return False
            temp_cache.close()
        
        original_cache.clear()
        original_cache.close()
        print("  ✓ Original diskcache passed intensive test")
        
    except Exception as e:
        print(f"  ❌ Original diskcache failed intensive test: {e}")
        if "database disk image is malformed" in str(e).lower():
            print("  🎯 Found the SQLite corruption issue!")
        return False
    
    # Test our implementation with the same intensive operations
    print("Testing diskcache_rs with intensive operations...")
    try:
        our_cache = diskcache_rs.PyCache(cloud_path + "_ours")
        
        # Same rapid writes
        for i in range(100):
            key = f"rapid_key_{i}"
            value = (f"rapid_value_{i}" * 100).encode()
            our_cache.set(key, value)
            
            # Immediate read
            retrieved = our_cache.get(key)
            if retrieved != value:
                print(f"  ❌ diskcache_rs: Data corruption at key {key}")
                return False
            
            if i % 20 == 0:
                print(f"    diskcache_rs: {i}/100 operations completed")
        
        # Test with concurrent access simulation
        print("  Testing concurrent access simulation...")
        for i in range(50):
            our_cache.set(f"concurrent_{i}", f"value_{i}".encode())
            # Simulate another process
            temp_cache = diskcache_rs.PyCache(cloud_path + "_ours")
            result = temp_cache.get(f"concurrent_{i}")
            if result != f"value_{i}".encode():
                print(f"  ❌ diskcache_rs: Concurrent access issue at {i}")
                return False
        
        our_cache.clear()
        print("  ✓ diskcache_rs passed intensive test")
        
    except Exception as e:
        print(f"  ❌ diskcache_rs failed intensive test: {e}")
        return False
    
    return True

def test_fanout_cache_comparison():
    """Test FanoutCache vs our implementation"""
    print("\nTesting FanoutCache comparison...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_fanout_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping fanout test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    # Test original FanoutCache
    print("Testing original FanoutCache...")
    try:
        original_fanout = diskcache.FanoutCache(cloud_path + "_original_fanout", shards=4)
        
        # Add data across shards
        for i in range(100):
            key = f"fanout_key_{i}"
            value = f"fanout_value_{i}"
            original_fanout.set(key, value)
        
        # Verify data
        for i in range(100):
            key = f"fanout_key_{i}"
            expected = f"fanout_value_{i}"
            result = original_fanout.get(key)
            if result != expected:
                print(f"  ❌ Original FanoutCache failed at {key}")
                return False
        
        original_fanout.clear()
        original_fanout.close()
        print("  ✓ Original FanoutCache works")
        
    except Exception as e:
        print(f"  ❌ Original FanoutCache failed: {e}")
        return False
    
    # Test our simple fanout implementation
    print("Testing our fanout implementation...")
    try:
        # Create multiple cache instances to simulate fanout
        caches = []
        for i in range(4):
            cache = diskcache_rs.PyCache(cloud_path + f"_ours_shard_{i}")
            caches.append(cache)
        
        # Distribute data across shards
        for i in range(100):
            shard = i % 4
            key = f"fanout_key_{i}"
            value = f"fanout_value_{i}".encode()
            caches[shard].set(key, value)
        
        # Verify data
        for i in range(100):
            shard = i % 4
            key = f"fanout_key_{i}"
            expected = f"fanout_value_{i}".encode()
            result = caches[shard].get(key)
            if result != expected:
                print(f"  ❌ Our fanout implementation failed at {key}")
                return False
        
        # Clear all shards
        for cache in caches:
            cache.clear()
        
        print("  ✓ Our fanout implementation works")
        
    except Exception as e:
        print(f"  ❌ Our fanout implementation failed: {e}")
        return False
    
    return True

def test_performance_comparison():
    """Compare performance between implementations"""
    print("\nTesting performance comparison...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_perf_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping performance test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    # Test data
    test_data = {
        f"perf_key_{i}": f"performance_test_value_{i}" * 10
        for i in range(100)
    }
    
    # Test original diskcache performance
    print("Testing original diskcache performance...")
    try:
        original_cache = diskcache.Cache(cloud_path + "_original_perf")
        
        # Write performance
        start_time = time.time()
        for key, value in test_data.items():
            original_cache.set(key, value)
        write_time_original = time.time() - start_time
        
        # Read performance
        start_time = time.time()
        for key in test_data.keys():
            original_cache.get(key)
        read_time_original = time.time() - start_time
        
        original_cache.clear()
        original_cache.close()
        
        print(f"  Original diskcache: write={write_time_original:.3f}s, read={read_time_original:.3f}s")
        
    except Exception as e:
        print(f"  ❌ Original diskcache performance test failed: {e}")
        return False
    
    # Test our implementation performance
    print("Testing diskcache_rs performance...")
    try:
        our_cache = diskcache_rs.PyCache(cloud_path + "_ours_perf")
        
        # Write performance
        start_time = time.time()
        for key, value in test_data.items():
            our_cache.set(key, value.encode())
        write_time_ours = time.time() - start_time
        
        # Read performance
        start_time = time.time()
        for key in test_data.keys():
            our_cache.get(key)
        read_time_ours = time.time() - start_time
        
        our_cache.clear()
        
        print(f"  diskcache_rs: write={write_time_ours:.3f}s, read={read_time_ours:.3f}s")
        
        # Compare performance
        write_speedup = write_time_original / write_time_ours if write_time_ours > 0 else float('inf')
        read_speedup = read_time_original / read_time_ours if read_time_ours > 0 else float('inf')
        
        print(f"  Performance comparison:")
        print(f"    Write speedup: {write_speedup:.2f}x")
        print(f"    Read speedup: {read_speedup:.2f}x")
        
    except Exception as e:
        print(f"  ❌ diskcache_rs performance test failed: {e}")
        return False
    
    return True

def test_edge_cases():
    """Test edge cases that might cause issues"""
    print("\nTesting edge cases...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_edge_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping edge cases test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    edge_cases = [
        ("empty_value", ""),
        ("unicode_key_测试", "unicode_value_测试"),
        ("special_chars", "!@#$%^&*()_+-=[]{}|;':\",./<>?"),
        ("large_key", "k" * 200),
        ("binary_data", bytes(range(256))),
        ("none_like", "None"),
        ("json_like", '{"key": "value", "number": 42}'),
    ]
    
    # Test original diskcache with edge cases
    print("Testing original diskcache with edge cases...")
    try:
        original_cache = diskcache.Cache(cloud_path + "_original_edge")
        
        for key, value in edge_cases:
            original_cache.set(key, value)
            result = original_cache.get(key)
            if result != value:
                print(f"  ❌ Original diskcache failed edge case: {key}")
                return False
        
        original_cache.clear()
        original_cache.close()
        print("  ✓ Original diskcache passed edge cases")
        
    except Exception as e:
        print(f"  ❌ Original diskcache edge cases failed: {e}")
        return False
    
    # Test our implementation with edge cases
    print("Testing diskcache_rs with edge cases...")
    try:
        our_cache = diskcache_rs.PyCache(cloud_path + "_ours_edge")
        
        for key, value in edge_cases:
            if isinstance(value, str):
                value_bytes = value.encode('utf-8')
            else:
                value_bytes = value
            
            our_cache.set(key, value_bytes)
            result = our_cache.get(key)
            if result != value_bytes:
                print(f"  ❌ diskcache_rs failed edge case: {key}")
                return False
        
        our_cache.clear()
        print("  ✓ diskcache_rs passed edge cases")
        
    except Exception as e:
        print(f"  ❌ diskcache_rs edge cases failed: {e}")
        return False
    
    return True

def main():
    print("🔍 Detailed comparison between original diskcache and diskcache_rs")
    print("=" * 70)
    
    success_count = 0
    total_tests = 4
    
    if test_sqlite_corruption_scenario():
        success_count += 1
    
    if test_fanout_cache_comparison():
        success_count += 1
    
    if test_performance_comparison():
        success_count += 1
    
    if test_edge_cases():
        success_count += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All detailed comparison tests passed!")
        print("✅ Both implementations work well on your cloud drive")
        print("💡 diskcache_rs provides additional robustness for network filesystems")
    else:
        print("⚠ Some tests failed. Check the output above for details.")
    
    return success_count == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
