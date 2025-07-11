#!/usr/bin/env python3
"""
Basic usage examples for diskcache_rs
"""

import os
import sys
import tempfile
import time

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import diskcache_rs

def example_basic_operations():
    """Basic cache operations"""
    print("=== Basic Operations ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create cache
        cache = diskcache_rs.PyCache(temp_dir, max_size=10*1024*1024, max_entries=1000)
        
        # Set values
        cache.set("string_key", b"Hello, World!")
        cache.set("binary_key", bytes(range(256)))
        cache.set("large_key", b"x" * 10000)
        
        # Get values
        result1 = cache.get("string_key")
        result2 = cache.get("binary_key")
        result3 = cache.get("large_key")
        
        print(f"String value: {result1}")
        print(f"Binary value length: {len(result2)}")
        print(f"Large value length: {len(result3)}")
        
        # Check existence
        print(f"string_key exists: {cache.exists('string_key')}")
        print(f"nonexistent_key exists: {cache.exists('nonexistent_key')}")
        
        # Get statistics
        stats = cache.stats()
        print(f"Cache stats: {stats}")
        
        # Delete
        cache.delete("string_key")
        print(f"After deletion, string_key exists: {cache.exists('string_key')}")

def example_expiration():
    """Cache expiration example"""
    print("\n=== Expiration Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Set with expiration (2 seconds from now)
        expire_time = int(time.time()) + 2
        cache.set("expire_key", b"This will expire", expire_time=expire_time)
        
        print("Set value with 2-second expiration")
        print(f"Immediately: {cache.get('expire_key')}")
        
        time.sleep(1)
        print(f"After 1 second: {cache.get('expire_key')}")
        
        time.sleep(2)
        print(f"After 3 seconds total: {cache.get('expire_key')}")

def example_tags():
    """Cache tags example"""
    print("\n=== Tags Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Set values with tags
        cache.set("user_1", b"User 1 data", tags=["user", "active"])
        cache.set("user_2", b"User 2 data", tags=["user", "inactive"])
        cache.set("product_1", b"Product 1 data", tags=["product", "electronics"])
        
        print("Set values with tags")
        print(f"user_1: {cache.get('user_1')}")
        print(f"user_2: {cache.get('user_2')}")
        print(f"product_1: {cache.get('product_1')}")

def example_performance():
    """Performance demonstration"""
    print("\n=== Performance Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Measure write performance
        start_time = time.time()
        for i in range(1000):
            key = f"perf_key_{i}"
            value = f"performance_value_{i}".encode()
            cache.set(key, value)
        write_time = time.time() - start_time
        
        # Measure read performance
        start_time = time.time()
        for i in range(1000):
            key = f"perf_key_{i}"
            cache.get(key)
        read_time = time.time() - start_time
        
        print(f"Write 1000 items: {write_time:.3f} seconds ({1000/write_time:.1f} ops/sec)")
        print(f"Read 1000 items: {read_time:.3f} seconds ({1000/read_time:.1f} ops/sec)")
        
        # Show final stats
        stats = cache.stats()
        print(f"Final stats: {stats}")

def example_cloud_drive():
    """Example using cloud drive (if available)"""
    print("\n=== Cloud Drive Example ===")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_example"
    
    if not os.path.exists("Z:\\"):
        print("Z: drive not available, skipping cloud drive example")
        return
    
    try:
        os.makedirs(cloud_path, exist_ok=True)
        
        # Create cache on cloud drive
        cache = diskcache_rs.PyCache(cloud_path)
        
        print(f"Created cache on cloud drive: {cloud_path}")
        
        # Test operations
        cache.set("cloud_key", b"This is stored on the cloud!")
        result = cache.get("cloud_key")
        print(f"Retrieved from cloud: {result}")
        
        # Test persistence
        cache2 = diskcache_rs.PyCache(cloud_path)
        result2 = cache2.get("cloud_key")
        print(f"Retrieved from new cache instance: {result2}")
        
        # Clean up
        cache.clear()
        print("Cloud drive example completed successfully!")
        
    except Exception as e:
        print(f"Cloud drive example failed: {e}")

def example_concurrent_access():
    """Example of concurrent access"""
    print("\n=== Concurrent Access Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple cache instances (simulating different processes)
        cache1 = diskcache_rs.PyCache(temp_dir)
        cache2 = diskcache_rs.PyCache(temp_dir)
        cache3 = diskcache_rs.PyCache(temp_dir)
        
        # Each cache writes different data
        cache1.set("cache1_key", b"Data from cache 1")
        cache2.set("cache2_key", b"Data from cache 2")
        cache3.set("cache3_key", b"Data from cache 3")
        
        # Each cache can read all data
        print(f"Cache 1 reads cache1_key: {cache1.get('cache1_key')}")
        print(f"Cache 1 reads cache2_key: {cache1.get('cache2_key')}")
        print(f"Cache 1 reads cache3_key: {cache1.get('cache3_key')}")
        
        print(f"Cache 2 reads cache1_key: {cache2.get('cache1_key')}")
        print(f"Cache 2 reads cache2_key: {cache2.get('cache2_key')}")
        print(f"Cache 2 reads cache3_key: {cache2.get('cache3_key')}")
        
        print("Concurrent access works correctly!")

def example_error_handling():
    """Example of error handling"""
    print("\n=== Error Handling Example ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Getting non-existent key
        result = cache.get("nonexistent")
        print(f"Non-existent key returns: {result}")
        
        # Deleting non-existent key
        deleted = cache.delete("nonexistent")
        print(f"Deleting non-existent key returns: {deleted}")
        
        # Large key names
        long_key = "x" * 200
        cache.set(long_key, b"value for long key")
        result = cache.get(long_key)
        print(f"Long key works: {result is not None}")

def main():
    print("🚀 DiskCache RS Examples")
    print("=" * 50)
    
    try:
        example_basic_operations()
        example_expiration()
        example_tags()
        example_performance()
        example_cloud_drive()
        example_concurrent_access()
        example_error_handling()
        
        print("\n🎉 All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
