#!/usr/bin/env python3
"""
Simple test to verify memory cache is working
"""

import diskcache_rs
import tempfile
import time

def test_basic_memory_cache():
    """Test basic memory cache functionality"""
    print("Testing basic memory cache functionality...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create cache
        cache = diskcache_rs.PyCache(temp_dir, max_size=1024*1024, max_entries=1000)
        
        # Set some data
        print("Setting test data...")
        cache.set("test_key", b"test_value")
        
        # First read (from disk)
        print("First read (from disk)...")
        start = time.perf_counter()
        result1 = cache.get("test_key")
        time1 = time.perf_counter() - start
        print(f"First read time: {time1*1000:.2f}ms")
        print(f"Result: {result1}")
        
        # Second read (should be from memory cache)
        print("Second read (from memory cache)...")
        start = time.perf_counter()
        result2 = cache.get("test_key")
        time2 = time.perf_counter() - start
        print(f"Second read time: {time2*1000:.2f}ms")
        print(f"Result: {result2}")
        
        # Compare times
        if time2 > 0:
            speedup = time1 / time2
            print(f"Speedup: {speedup:.2f}x")
        
        # Test stats
        stats = cache.stats()
        print(f"Cache stats: {stats}")
        
        return result1 == result2 == b"test_value"

def test_multiple_items():
    """Test with multiple items"""
    print("\nTesting with multiple items...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Add multiple items
        items = {}
        for i in range(10):
            key = f"item_{i}"
            value = f"value_{i}".encode()
            items[key] = value
            cache.set(key, value)
        
        # Read all items twice
        print("First round of reads...")
        start = time.perf_counter()
        for key in items:
            cache.get(key)
        time1 = time.perf_counter() - start
        
        print("Second round of reads...")
        start = time.perf_counter()
        for key in items:
            cache.get(key)
        time2 = time.perf_counter() - start
        
        print(f"First round: {time1*1000:.2f}ms")
        print(f"Second round: {time2*1000:.2f}ms")
        
        if time2 > 0:
            speedup = time1 / time2
            print(f"Speedup: {speedup:.2f}x")

def main():
    print("🧪 Simple Memory Cache Test")
    print("=" * 40)
    
    try:
        success1 = test_basic_memory_cache()
        test_multiple_items()
        
        if success1:
            print("\n✅ Memory cache appears to be working!")
        else:
            print("\n❌ Memory cache test failed!")
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
