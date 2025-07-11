#!/usr/bin/env python3
"""
Test diskcache_rs on network file systems (cloud drives)
This specifically tests the Z: drive scenario you mentioned.
"""

import os
import sys
import time
import tempfile
import traceback
from pathlib import Path

# Import our Rust cache
import diskcache_rs

def test_network_path_detection():
    """Test if we can detect network file systems"""
    print("Testing network path detection...")
    
    # Test various paths
    test_paths = [
        "Z:\\_thm\\temp\\.pkg\\db",  # Your cloud drive path
        "\\\\server\\share",         # UNC path
        "/mnt/nfs",                  # NFS mount
        "C:\\temp",                  # Local path
        "/tmp",                      # Local path
    ]
    
    for path in test_paths:
        if os.path.exists(os.path.dirname(path)) or path.startswith("Z:"):
            print(f"Path: {path}")
            # We'll implement detection in Rust, for now just note the path type
            if path.startswith("\\\\") or path.startswith("Z:") or path.startswith("/mnt"):
                print(f"  -> Detected as network path")
            else:
                print(f"  -> Detected as local path")

def test_cloud_drive_cache():
    """Test cache on your specific cloud drive path"""
    print("\nTesting cache on cloud drive...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db"
    
    # Check if the cloud drive is available
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping cloud drive test")
        return False
    
    try:
        # Ensure the directory exists
        os.makedirs(cloud_path, exist_ok=True)
        
        print(f"Creating cache in: {cloud_path}")
        cache = diskcache_rs.PyCache(cloud_path, max_size=10*1024*1024, max_entries=1000)
        
        # Test basic operations
        print("Testing basic operations on cloud drive...")
        
        # Set some test data
        test_data = {
            "simple": b"Hello, Cloud!",
            "json_data": '{"test": "data", "number": 42}'.encode(),
            "binary": bytes(range(256)),
            "large": b"x" * 10000,  # 10KB
        }
        
        # Store data
        for key, value in test_data.items():
            print(f"  Setting {key}...")
            cache.set(key, value)
            
            # Immediately verify
            retrieved = cache.get(key)
            if retrieved == value:
                print(f"  ✓ {key} stored and retrieved successfully")
            else:
                print(f"  ❌ {key} failed: expected {len(value)} bytes, got {len(retrieved) if retrieved else 0}")
                return False
        
        # Test persistence by creating a new cache instance
        print("Testing persistence...")
        cache2 = diskcache_rs.PyCache(cloud_path)
        
        for key, expected_value in test_data.items():
            retrieved = cache2.get(key)
            if retrieved == expected_value:
                print(f"  ✓ {key} persisted correctly")
            else:
                print(f"  ❌ {key} persistence failed")
                return False
        
        # Test stats
        stats = cache.stats()
        print(f"Cache stats: {stats}")
        
        # Test size
        size = cache.size()
        print(f"Cache size: {size} bytes")
        
        # Clean up
        cache.clear()
        print("✓ Cloud drive cache test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Cloud drive cache test failed: {e}")
        traceback.print_exc()
        return False

def test_concurrent_access():
    """Test concurrent access on network file system"""
    print("\nTesting concurrent access...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_concurrent"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping concurrent test")
        return False
    
    try:
        os.makedirs(cloud_path, exist_ok=True)
        
        # Create multiple cache instances (simulating multiple processes)
        caches = []
        for i in range(3):
            cache = diskcache_rs.PyCache(cloud_path)
            caches.append(cache)
        
        # Each cache writes different data
        for i, cache in enumerate(caches):
            for j in range(5):
                key = f"cache_{i}_key_{j}"
                value = f"value_from_cache_{i}_{j}".encode()
                cache.set(key, value)
                print(f"  Cache {i} set {key}")
        
        # Verify all caches can read all data
        print("Verifying cross-cache reads...")
        for i, cache in enumerate(caches):
            for cache_idx in range(3):
                for j in range(5):
                    key = f"cache_{cache_idx}_key_{j}"
                    expected = f"value_from_cache_{cache_idx}_{j}".encode()
                    retrieved = cache.get(key)
                    if retrieved == expected:
                        print(f"  ✓ Cache {i} read {key} correctly")
                    else:
                        print(f"  ❌ Cache {i} failed to read {key}")
                        return False
        
        # Clean up
        caches[0].clear()
        print("✓ Concurrent access test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Concurrent access test failed: {e}")
        traceback.print_exc()
        return False

def test_large_files():
    """Test with larger files on network drive"""
    print("\nTesting large files on network drive...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_large"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping large files test")
        return False
    
    try:
        os.makedirs(cloud_path, exist_ok=True)
        cache = diskcache_rs.PyCache(cloud_path, max_size=50*1024*1024)  # 50MB
        
        # Test with different sized files
        sizes = [1024, 10*1024, 100*1024, 1024*1024]  # 1KB, 10KB, 100KB, 1MB
        
        for size in sizes:
            print(f"  Testing {size} byte file...")
            key = f"large_file_{size}"
            data = b"x" * size
            
            start_time = time.time()
            cache.set(key, data)
            set_time = time.time() - start_time
            
            start_time = time.time()
            retrieved = cache.get(key)
            get_time = time.time() - start_time
            
            if retrieved == data:
                print(f"    ✓ {size} bytes: set={set_time:.3f}s, get={get_time:.3f}s")
            else:
                print(f"    ❌ {size} bytes failed")
                return False
        
        # Clean up
        cache.clear()
        print("✓ Large files test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Large files test failed: {e}")
        traceback.print_exc()
        return False

def compare_with_original_diskcache():
    """Compare with original python-diskcache on network drive"""
    print("\nComparing with original diskcache...")
    
    try:
        import diskcache
        print("Original diskcache available for comparison")
        
        cloud_path = "Z:\\_thm\\temp\\.pkg\\db_compare"
        
        if not os.path.exists("Z:\\"):
            print("❌ Z: drive not available, skipping comparison")
            return False
        
        os.makedirs(cloud_path, exist_ok=True)
        
        # Test original diskcache
        print("Testing original diskcache...")
        try:
            original_cache = diskcache.Cache(cloud_path + "_original")
            original_cache.set("test_key", "test_value")
            result = original_cache.get("test_key")
            if result == "test_value":
                print("  ✓ Original diskcache works on this network drive")
                original_works = True
            else:
                print("  ❌ Original diskcache failed")
                original_works = False
            original_cache.clear()
        except Exception as e:
            print(f"  ❌ Original diskcache failed: {e}")
            original_works = False
        
        # Test our implementation
        print("Testing diskcache_rs...")
        try:
            our_cache = diskcache_rs.PyCache(cloud_path + "_ours")
            our_cache.set("test_key", b"test_value")
            result = our_cache.get("test_key")
            if result == b"test_value":
                print("  ✓ diskcache_rs works on this network drive")
                ours_works = True
            else:
                print("  ❌ diskcache_rs failed")
                ours_works = False
            our_cache.clear()
        except Exception as e:
            print(f"  ❌ diskcache_rs failed: {e}")
            ours_works = False
        
        if ours_works and not original_works:
            print("🎉 diskcache_rs works where original diskcache fails!")
        elif ours_works and original_works:
            print("✓ Both implementations work on this network drive")
        elif not ours_works and original_works:
            print("⚠ Original diskcache works but ours doesn't")
        else:
            print("❌ Both implementations fail on this network drive")
        
        return ours_works
        
    except ImportError:
        print("Original diskcache not available for comparison")
        return True

def main():
    print("🚀 Testing diskcache_rs on network file systems")
    print("=" * 60)
    
    test_network_path_detection()
    
    success_count = 0
    total_tests = 4
    
    if test_cloud_drive_cache():
        success_count += 1
    
    if test_concurrent_access():
        success_count += 1
    
    if test_large_files():
        success_count += 1
    
    if compare_with_original_diskcache():
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All network file system tests passed!")
        print("✅ diskcache_rs is compatible with your cloud drive!")
    else:
        print("⚠ Some tests failed. Check the output above for details.")
    
    return success_count == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
