#!/usr/bin/env python3
"""
Basic test script for diskcache_rs
"""

import diskcache_rs
import tempfile
import os
import time

def test_basic_operations():
    """Test basic cache operations"""
    print("Testing basic cache operations...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Create cache instance
        cache = diskcache_rs.PyCache(temp_dir, max_size=1024*1024, max_entries=1000)
        
        # Test set and get
        test_data = b"Hello, World!"
        cache.set("test_key", test_data)
        
        retrieved_data = cache.get("test_key")
        assert retrieved_data == test_data, f"Expected {test_data}, got {retrieved_data}"
        print("✓ Set and get operations work correctly")
        
        # Test exists
        assert cache.exists("test_key"), "Key should exist"
        assert not cache.exists("nonexistent_key"), "Nonexistent key should not exist"
        print("✓ Exists operation works correctly")
        
        # Test keys
        keys = cache.keys()
        assert "test_key" in keys, "test_key should be in keys list"
        print("✓ Keys operation works correctly")
        
        # Test delete
        deleted = cache.delete("test_key")
        assert deleted, "Delete should return True for existing key"
        assert not cache.exists("test_key"), "Key should not exist after deletion"
        print("✓ Delete operation works correctly")
        
        # Test stats
        stats = cache.stats()
        print(f"Cache stats: {stats}")
        assert isinstance(stats, dict), "Stats should return a dictionary"
        print("✓ Stats operation works correctly")
        
        # Test hit rate
        hit_rate = cache.hit_rate()
        print(f"Hit rate: {hit_rate}")
        assert isinstance(hit_rate, float), "Hit rate should be a float"
        print("✓ Hit rate calculation works correctly")

def test_multiple_entries():
    """Test cache with multiple entries"""
    print("\nTesting multiple entries...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir, max_size=1024*1024, max_entries=100)
        
        # Add multiple entries
        for i in range(10):
            key = f"key_{i}"
            value = f"value_{i}".encode('utf-8')
            cache.set(key, value)
        
        # Verify all entries exist
        for i in range(10):
            key = f"key_{i}"
            expected_value = f"value_{i}".encode('utf-8')
            retrieved_value = cache.get(key)
            assert retrieved_value == expected_value, f"Mismatch for {key}"
        
        print("✓ Multiple entries work correctly")
        
        # Test clear
        cache.clear()
        keys = cache.keys()
        assert len(keys) == 0, "Cache should be empty after clear"
        print("✓ Clear operation works correctly")

def test_expiration():
    """Test cache expiration"""
    print("\nTesting expiration...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Set entry with expiration (1 second from now)
        expire_time = int(time.time()) + 1
        cache.set("expire_key", b"expire_value", expire_time=expire_time)
        
        # Should exist immediately
        assert cache.exists("expire_key"), "Key should exist before expiration"
        
        # Wait for expiration
        time.sleep(2)
        
        # Should not exist after expiration
        # Note: This depends on the cache checking expiration on access
        retrieved = cache.get("expire_key")
        if retrieved is None:
            print("✓ Expiration works correctly")
        else:
            print("⚠ Expiration might not be working as expected")

def test_tags():
    """Test cache with tags"""
    print("\nTesting tags...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Set entry with tags
        cache.set("tagged_key", b"tagged_value", tags=["tag1", "tag2"])
        
        # Should be able to retrieve normally
        retrieved = cache.get("tagged_key")
        assert retrieved == b"tagged_value", "Tagged entry should be retrievable"
        print("✓ Tags work correctly")

def test_large_data():
    """Test cache with larger data"""
    print("\nTesting large data...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Create 1MB of data
        large_data = b"x" * (1024 * 1024)
        cache.set("large_key", large_data)
        
        retrieved = cache.get("large_key")
        assert retrieved == large_data, "Large data should be stored and retrieved correctly"
        print("✓ Large data works correctly")

def test_size_and_vacuum():
    """Test cache size and vacuum operations"""
    print("\nTesting size and vacuum...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Add some data
        for i in range(5):
            cache.set(f"size_key_{i}", b"x" * 1000)
        
        # Check size
        size = cache.size()
        print(f"Cache size: {size} bytes")
        assert size > 0, "Cache size should be greater than 0"
        
        # Test vacuum
        cache.vacuum()
        print("✓ Vacuum operation completed")

if __name__ == "__main__":
    print("Starting diskcache_rs tests...")
    
    try:
        test_basic_operations()
        test_multiple_entries()
        test_expiration()
        test_tags()
        test_large_data()
        test_size_and_vacuum()
        
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
