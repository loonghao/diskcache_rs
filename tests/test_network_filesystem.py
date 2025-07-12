"""
Network filesystem specific tests for diskcache_rs

This module contains legacy network filesystem tests.
For comprehensive cross-platform network testing, see test_cross_platform_network.py
"""

import concurrent.futures
import os
import platform
import threading
import time
from pathlib import Path

import pytest


class TestNetworkFilesystem:
    """Test cache behavior on network filesystems"""

    @pytest.mark.skipif(
        not (platform.system() == "Windows" and os.path.exists("Z:\\")),
        reason="Windows cloud drive Z: not available",
    )
    def test_cloud_drive_basic_operations(self, cloud_cache, sample_data):
        """Test basic operations on cloud drive (Windows-specific)"""
        # Test set and get
        cloud_cache.set("cloud_test", sample_data["medium"])
        retrieved = cloud_cache.get("cloud_test")
        assert retrieved == sample_data["medium"]

    @pytest.mark.skipif(
        not (platform.system() == "Windows" and os.path.exists("Z:\\")),
        reason="Windows cloud drive Z: not available",
    )
    def test_cloud_drive_persistence(self, cloud_cache_dir, sample_data):
        """Test data persistence across cache instances on cloud drive (Windows-specific)"""
        from diskcache_rs import Cache

        # Create first cache instance and store data
        cache1 = Cache(cloud_cache_dir)
        cache1.set("persistent_key", sample_data["large"])

        # Create second cache instance and retrieve data
        cache2 = Cache(cloud_cache_dir)
        retrieved = cache2.get("persistent_key")
        assert retrieved == sample_data["large"]

    @pytest.mark.skipif(
        not (platform.system() == "Windows" and os.path.exists("Z:\\")),
        reason="Windows cloud drive Z: not available",
    )
    def test_cloud_drive_concurrent_access(self, cloud_cache, sample_data):
        """Test concurrent access on cloud drive (Windows-specific)"""

        def worker(worker_id):
            """Worker function for concurrent testing"""
            results = []
            for i in range(10):
                key = f"worker_{worker_id}_key_{i}"
                value = f"worker_{worker_id}_value_{i}".encode()

                # Set value
                cloud_cache.set(key, value)

                # Get value
                retrieved = cloud_cache.get(key)
                results.append(retrieved == value)

                # Small delay to simulate real usage
                time.sleep(0.01)

            return all(results)

        # Run multiple workers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker, i) for i in range(4)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # All workers should succeed
        assert all(results)

    @pytest.mark.skipif(
        not (platform.system() == "Windows" and os.path.exists("Z:\\")),
        reason="Windows cloud drive Z: not available",
    )
    def test_cloud_drive_large_files(self, cloud_cache):
        """Test handling of large files on cloud drive (Windows-specific)"""
        # Create a 1MB file
        large_data = b"x" * (1024 * 1024)

        start_time = time.time()
        cloud_cache.set("large_file", large_data)
        set_time = time.time() - start_time

        start_time = time.time()
        retrieved = cloud_cache.get("large_file")
        get_time = time.time() - start_time

        assert retrieved == large_data
        print(f"Cloud drive large file - Set: {set_time:.2f}s, Get: {get_time:.2f}s")

    def test_unc_path_handling(self, temp_cache_dir):
        """Test UNC path handling (if available)"""
        # This test would need actual UNC paths to be meaningful
        # For now, just test that the cache can handle UNC-like paths
        # unc_like_path = temp_cache_dir.replace("\\", "\\\\")

        # This should not crash
        try:
            from diskcache_rs import Cache

            cache = Cache(temp_cache_dir)  # Use regular path for now
            cache.set("unc_test", b"test data")
            assert cache.get("unc_test") == b"test data"
        except Exception as e:
            pytest.fail(f"UNC path handling failed: {e}")

    def test_network_interruption_simulation(self, cache, sample_data):
        """Simulate network interruption scenarios"""
        # Store some data
        cache.set("interruption_test", sample_data["medium"])

        # Verify it's there
        assert cache.get("interruption_test") == sample_data["medium"]

        # In a real network filesystem, we might simulate interruption
        # For now, just test that the cache handles normal operations
        # after potential interruptions

        # Try multiple operations
        for i in range(10):
            key = f"post_interruption_{i}"
            cache.set(key, sample_data["small"])
            assert cache.get(key) == sample_data["small"]

    def test_atomic_operations(self, cache, sample_data):
        """Test that operations are atomic (important for network filesystems)"""

        def concurrent_writer(cache, key_prefix, iterations):
            """Write data concurrently"""
            for i in range(iterations):
                key = f"{key_prefix}_{i}"
                cache.set(key, sample_data["small"])

        # Start multiple writers
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=concurrent_writer, args=(cache, f"atomic_test_{i}", 20)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all data was written correctly
        keys = cache.keys()
        atomic_keys = [k for k in keys if k.startswith("atomic_test_")]

        # Should have 3 * 20 = 60 keys
        assert len(atomic_keys) == 60

        # Verify all values are correct
        for key in atomic_keys:
            assert cache.get(key) == sample_data["small"]

    @pytest.mark.skipif(
        not (platform.system() == "Windows" and os.path.exists("Z:\\")),
        reason="Windows cloud drive Z: not available",
    )
    def test_cloud_drive_error_recovery(self, cloud_cache, sample_data):
        """Test error recovery on cloud drive (Windows-specific)"""
        # Store some data
        cloud_cache.set("recovery_test", sample_data["medium"])

        # Verify it's accessible
        assert cloud_cache.get("recovery_test") == sample_data["medium"]

        # Test that cache can handle various error conditions gracefully
        # (This would need more sophisticated testing in a real scenario)

        # Try operations that might fail on network drives
        try:
            # Rapid successive operations
            for i in range(100):
                key = f"rapid_{i}"
                cloud_cache.set(key, b"rapid test")
                retrieved = cloud_cache.get(key)
                assert retrieved == b"rapid test"
        except Exception as e:
            pytest.fail(f"Rapid operations failed: {e}")

    def test_path_normalization(self, temp_cache_dir):
        """Test that different path formats work correctly"""
        from diskcache_rs import Cache

        # Test different path separators
        paths_to_test = [
            temp_cache_dir,
            temp_cache_dir.replace("\\", "/"),  # Forward slashes
            str(Path(temp_cache_dir)),  # Pathlib normalization
        ]

        for path in paths_to_test:
            try:
                cache = Cache(path)
                cache.set("path_test", b"test data")
                assert cache.get("path_test") == b"test data"
            except Exception as e:
                pytest.fail(f"Path normalization failed for {path}: {e}")
