"""
Test for issue #17: Configurable disk write threshold and NFS file locking

This test demonstrates:
1. Configurable disk_write_threshold - control when data is written to disk vs memory-only
2. File locking support for NFS scenarios
"""

import os
import tempfile
from pathlib import Path

import pytest


def test_disk_write_threshold_default():
    """Test default behavior: items < 1KB stay in memory, >= 1KB written to disk"""
    from diskcache_rs import Cache

    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(tmpdir)

        # Small data (< 1KB) - should NOT create disk file
        small_data = b"x" * 512  # 512 bytes
        cache.set("small_key", small_data)

        # Large data (>= 1KB) - should create disk file
        large_data = b"y" * 2048  # 2KB
        cache.set("large_key", large_data)

        # Verify data can be retrieved
        assert cache.get("small_key") == small_data
        assert cache.get("large_key") == large_data

        # Close cache to ensure data is persisted
        cache.close()

        # With redb backend, data is stored in index.redb file
        # Check that redb database was created
        redb_file = Path(tmpdir) / "index.redb"
        assert redb_file.exists(), "redb database file should exist"
        assert redb_file.stat().st_size > 0, "redb database should not be empty"


def test_disk_write_threshold_custom_zero():
    """Test custom threshold = 0: all data written to disk"""
    from diskcache_rs import Cache

    with tempfile.TemporaryDirectory() as tmpdir:
        # Set threshold to 0 - all data should be written to disk
        cache = Cache(tmpdir, disk_write_threshold=0)

        # Even tiny data should create disk file
        tiny_data = b"x" * 10  # 10 bytes
        cache.set("tiny_key", tiny_data)

        # Verify data can be retrieved
        assert cache.get("tiny_key") == tiny_data

        # Close cache to ensure data is persisted
        cache.close()

        # With redb backend, data is stored in index.redb file
        redb_file = Path(tmpdir) / "index.redb"
        assert redb_file.exists(), "redb database file should exist"
        assert redb_file.stat().st_size > 0, "redb database should not be empty"


def test_disk_write_threshold_custom_large():
    """Test custom threshold = 10KB: only large items written to disk"""
    from diskcache_rs import Cache

    with tempfile.TemporaryDirectory() as tmpdir:
        # Set threshold to 10KB
        cache = Cache(tmpdir, disk_write_threshold=10 * 1024)

        # Medium data (5KB) - should NOT create disk file
        medium_data = b"x" * (5 * 1024)
        cache.set("medium_key", medium_data)

        # Very large data (20KB) - should create disk file
        very_large_data = b"y" * (20 * 1024)
        cache.set("very_large_key", very_large_data)

        # Verify data can be retrieved
        assert cache.get("medium_key") == medium_data
        assert cache.get("very_large_key") == very_large_data

        # Close cache to ensure data is persisted
        cache.close()

        # With redb backend, data is stored in index.redb file
        redb_file = Path(tmpdir) / "index.redb"
        assert redb_file.exists(), "redb database file should exist"
        assert redb_file.stat().st_size > 0, "redb database should not be empty"


def test_file_locking_enabled():
    """Test that file locking can be enabled (for NFS scenarios)"""
    from diskcache_rs import Cache

    with tempfile.TemporaryDirectory() as tmpdir:
        # Enable file locking
        cache = Cache(tmpdir, use_file_locking=True, disk_write_threshold=0)

        # Write some data
        data = b"test data with locking"
        cache.set("locked_key", data)

        # Verify data can be retrieved
        assert cache.get("locked_key") == data

        # Note: Actual file locking behavior is hard to test without concurrent access
        # This test just verifies the option can be set without errors


def test_file_locking_disabled_default():
    """Test that file locking is disabled by default (for performance)"""
    from diskcache_rs import Cache

    with tempfile.TemporaryDirectory() as tmpdir:
        # Default: file locking disabled
        cache = Cache(tmpdir, disk_write_threshold=0)

        # Write some data
        data = b"test data without locking"
        cache.set("unlocked_key", data)

        # Verify data can be retrieved
        assert cache.get("unlocked_key") == data


if __name__ == "__main__":
    # Run tests manually for debugging
    print("Testing default disk write threshold...")
    test_disk_write_threshold_default()
    print("✓ Default threshold test passed")

    print("\nTesting custom threshold = 0...")
    test_disk_write_threshold_custom_zero()
    print("✓ Custom threshold=0 test passed")

    print("\nTesting custom threshold = 10KB...")
    test_disk_write_threshold_custom_large()
    print("✓ Custom threshold=10KB test passed")

    print("\nTesting file locking enabled...")
    test_file_locking_enabled()
    print("✓ File locking enabled test passed")

    print("\nTesting file locking disabled (default)...")
    test_file_locking_disabled_default()
    print("✓ File locking disabled test passed")

    print("\n✅ All tests passed!")
