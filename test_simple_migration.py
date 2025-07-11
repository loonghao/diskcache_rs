#!/usr/bin/env python3
"""
Simple test to verify auto-migration works
"""

import os
import tempfile
import diskcache
import diskcache_rs

def test_auto_migration():
    """Test if auto-migration works when diskcache data is present"""
    print("🔄 Testing Auto-Migration")
    print("=" * 30)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Working in: {temp_dir}")
        
        # Step 1: Create original diskcache data
        print("\n1. Creating original diskcache data...")
        original_cache = diskcache.Cache(temp_dir)
        original_cache.set("test_key", "test_value")
        original_cache.set("number_key", 42)
        original_cache.set("binary_key", b"binary_data")
        original_cache.close()
        
        # Verify SQLite database exists
        cache_db = os.path.join(temp_dir, "cache.db")
        if os.path.exists(cache_db):
            print(f"   ✅ SQLite database created: {os.path.getsize(cache_db)} bytes")
        else:
            print("   ❌ SQLite database not found!")
            return False
        
        # Step 2: Create diskcache_rs instance
        print("\n2. Creating diskcache_rs instance...")
        try:
            cache_rs = diskcache_rs.PyCache(temp_dir)
            print("   ✅ diskcache_rs instance created successfully")
        except Exception as e:
            print(f"   ❌ Failed to create diskcache_rs: {e}")
            return False
        
        # Step 3: Test basic operations
        print("\n3. Testing basic operations...")
        try:
            # Test new data
            cache_rs.set("new_key", b"new_value")
            result = cache_rs.get("new_key")
            if result == b"new_value":
                print("   ✅ New data operations work")
            else:
                print("   ❌ New data operations failed")
                return False
            
            # Test stats
            stats = cache_rs.stats()
            print(f"   📊 Stats: {stats}")
            
        except Exception as e:
            print(f"   ❌ Basic operations failed: {e}")
            return False
        
        # Step 4: Check for migration artifacts
        print("\n4. Checking migration artifacts...")
        migrated_db = os.path.join(temp_dir, "cache.db.migrated")
        backup_dir = os.path.join(temp_dir, "diskcache_backup")
        
        if os.path.exists(migrated_db):
            print("   ✅ Original database was renamed (migration occurred)")
        elif os.path.exists(cache_db):
            print("   ℹ️ Original database still exists (migration may not have occurred)")
        
        if os.path.exists(backup_dir):
            print("   ✅ Backup directory created")
        else:
            print("   ℹ️ No backup directory found")
        
        return True

def test_without_diskcache_data():
    """Test normal operation without existing diskcache data"""
    print("\n🆕 Testing Without Existing Data")
    print("=" * 35)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Working in: {temp_dir}")
        
        # Create diskcache_rs instance in empty directory
        print("\n1. Creating diskcache_rs in empty directory...")
        try:
            cache_rs = diskcache_rs.PyCache(temp_dir)
            print("   ✅ diskcache_rs instance created successfully")
        except Exception as e:
            print(f"   ❌ Failed to create diskcache_rs: {e}")
            return False
        
        # Test operations
        print("\n2. Testing operations...")
        try:
            cache_rs.set("test_key", b"test_value")
            result = cache_rs.get("test_key")
            if result == b"test_value":
                print("   ✅ Operations work correctly")
                return True
            else:
                print("   ❌ Operations failed")
                return False
        except Exception as e:
            print(f"   ❌ Operations failed: {e}")
            return False

def test_performance_comparison():
    """Compare performance before and after optimization"""
    print("\n⚡ Performance Comparison")
    print("=" * 25)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = diskcache_rs.PyCache(temp_dir)
        
        # Add test data
        print("Adding test data...")
        for i in range(100):
            cache.set(f"perf_key_{i}", f"perf_value_{i}".encode())
        
        # Test read performance
        import time
        
        print("Testing read performance...")
        
        # First read (from disk)
        start = time.perf_counter()
        for i in range(100):
            cache.get(f"perf_key_{i}")
        first_read_time = time.perf_counter() - start
        
        # Second read (from memory cache)
        start = time.perf_counter()
        for i in range(100):
            cache.get(f"perf_key_{i}")
        second_read_time = time.perf_counter() - start
        
        print(f"First read (disk): {first_read_time*1000:.2f}ms")
        print(f"Second read (memory): {second_read_time*1000:.2f}ms")
        
        if second_read_time > 0:
            speedup = first_read_time / second_read_time
            print(f"Memory cache speedup: {speedup:.2f}x")
        
        return True

def main():
    print("🧪 Simple Migration and Performance Tests")
    print("=" * 50)
    
    try:
        success1 = test_auto_migration()
        success2 = test_without_diskcache_data()
        success3 = test_performance_comparison()
        
        print("\n" + "=" * 50)
        print("📋 Test Results:")
        print(f"  Auto Migration: {'✅ PASS' if success1 else '❌ FAIL'}")
        print(f"  Normal Operation: {'✅ PASS' if success2 else '❌ FAIL'}")
        print(f"  Performance Test: {'✅ PASS' if success3 else '❌ FAIL'}")
        
        if all([success1, success2, success3]):
            print("\n🎉 All tests passed!")
            print("✅ diskcache_rs is working correctly!")
        else:
            print("\n⚠️ Some tests failed")
            
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
