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

from diskcache_rs import Cache


def example_basic_operations():
    """Basic cache operations"""
    print("=== Basic Operations ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create cache
        cache = Cache(temp_dir, max_size=10 * 1024 * 1024, max_entries=1000)

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
        print(f"string_key exists: {'string_key' in cache}")
        print(f"nonexistent_key exists: {'nonexistent_key' in cache}")

        # Get statistics
        stats = cache.stats()
        print(f"Cache stats: {stats}")

        # Delete
        del cache["string_key"]
        print(f"After deletion, string_key exists: {'string_key' in cache}")


def example_performance():
    """Performance demonstration"""
    print("\n=== Performance Example ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)

        # Measure write performance
        start_time = time.perf_counter()
        for i in range(1000):
            key = f"perf_key_{i}"
            value = f"performance_value_{i}".encode()
            cache.set(key, value)
        write_time = time.perf_counter() - start_time

        # Measure read performance
        start_time = time.perf_counter()
        for i in range(1000):
            key = f"perf_key_{i}"
            cache.get(key)
        read_time = time.perf_counter() - start_time

        print(
            f"Write 1000 items: {write_time:.3f} seconds ({1000 / write_time:.1f} ops/sec)"
        )
        print(
            f"Read 1000 items: {read_time:.3f} seconds ({1000 / read_time:.1f} ops/sec)"
        )

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
        cache = Cache(cloud_path)

        print(f"Created cache on cloud drive: {cloud_path}")

        # Test operations
        cache.set("cloud_key", b"This is stored on the cloud!")
        result = cache.get("cloud_key")
        print(f"Retrieved from cloud: {result}")

        # Test persistence
        cache2 = Cache(cloud_path)
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
        cache1 = Cache(temp_dir)
        cache2 = Cache(temp_dir)
        cache3 = Cache(temp_dir)

        # Each cache writes different data
        cache1.set("cache1_key", b"Data from cache 1")
        cache2.set("cache2_key", b"Data from cache 2")
        cache3.set("cache3_key", b"Data from cache 3")

        # Each cache can read all data
        print(f"Cache 1 reads cache1_key: {cache1.get('cache1_key')}")
        print(f"Cache 1 reads cache2_key: {cache1.get('cache2_key')}")
        print(f"Cache 1 reads cache3_key: {cache1.get('cache3_key')}")

        print("Concurrent access works correctly!")


def example_error_handling():
    """Example of error handling"""
    print("\n=== Error Handling Example ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)

        # Getting non-existent key
        result = cache.get("nonexistent")
        print(f"Non-existent key returns: {result}")

        # Deleting non-existent key
        try:
            del cache["nonexistent"]
            print("Deleting non-existent key succeeded")
        except KeyError:
            print("Deleting non-existent key raised KeyError (expected)")

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
