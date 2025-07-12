"""
Compatibility tests with python-diskcache
"""

import os
import shutil
import tempfile

import pytest


class TestCompatibility:
    """Test compatibility with python-diskcache API"""

    @pytest.fixture
    def diskcache_available(self):
        """Check if original diskcache is available"""
        try:
            import diskcache  # noqa: F401

            return True
        except ImportError:
            pytest.skip(
                "Original diskcache not available for compatibility testing. Install with: uv add diskcache"
            )

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for both caches"""
        rs_dir = tempfile.mkdtemp(prefix="diskcache_rs_compat_")
        dc_dir = tempfile.mkdtemp(prefix="diskcache_compat_")

        yield rs_dir, dc_dir

        # Cleanup with retry for Windows file locking issues
        import time

        for dir_path in [rs_dir, dc_dir]:
            if os.path.exists(dir_path):
                for attempt in range(3):
                    try:
                        shutil.rmtree(dir_path)
                        break
                    except (PermissionError, OSError):
                        if attempt < 2:
                            time.sleep(0.5)  # Wait and retry
                        else:
                            # Final attempt - ignore errors
                            try:
                                shutil.rmtree(dir_path, ignore_errors=True)
                            except Exception:
                                pass

    def test_basic_api_compatibility(self, diskcache_available, temp_dirs, sample_data):
        """Test that basic API is compatible"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        # Create both caches
        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        # Test same operations on both
        test_key = "compatibility_test"
        test_value = sample_data["medium"]

        # Set operations
        rs_cache.set(test_key, test_value)
        dc_cache.set(test_key, test_value)

        # Get operations
        rs_result = rs_cache.get(test_key)
        dc_result = dc_cache.get(test_key)

        assert rs_result == dc_result == test_value

        # Exists operations (diskcache uses __contains__)
        assert rs_cache.exists(test_key) == (test_key in dc_cache) is True

        # Delete operations
        rs_delete_result = rs_cache.delete(test_key)
        dc_delete_result = dc_cache.delete(test_key)

        assert rs_delete_result == dc_delete_result is True
        assert rs_cache.exists(test_key) == (test_key in dc_cache) is False

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_keys_compatibility(self, diskcache_available, temp_dirs, sample_data):
        """Test keys() method compatibility"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        # Add same keys to both caches
        test_keys = ["key1", "key2", "key3"]
        for key in test_keys:
            rs_cache.set(key, sample_data["small"])
            dc_cache.set(key, sample_data["small"])

        # Get keys from both (diskcache uses iterkeys())
        rs_keys = set(rs_cache.keys())
        dc_keys = set(dc_cache.iterkeys())

        # Should contain at least our test keys
        for key in test_keys:
            assert key in rs_keys
            assert key in dc_keys

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_clear_compatibility(self, diskcache_available, temp_dirs, sample_data):
        """Test clear() method compatibility"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        # Add data to both caches
        for i in range(5):
            key = f"clear_test_{i}"
            rs_cache.set(key, sample_data["small"])
            dc_cache.set(key, sample_data["small"])

        # Verify data exists
        assert len(list(rs_cache)) >= 5  # Use iteration instead of keys()
        assert len(list(dc_cache.iterkeys())) >= 5

        # Clear both caches
        rs_cache.clear()
        dc_cache.clear()

        # Both should be empty
        assert len(list(rs_cache)) == 0  # Use iteration instead of keys()
        assert len(list(dc_cache.iterkeys())) == 0

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_stats_compatibility(self, diskcache_available, temp_dirs):
        """Test stats() method compatibility"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        # Get stats from both
        rs_stats = rs_cache.stats()
        dc_stats = dc_cache.stats()

        # diskcache_rs returns dict, original diskcache returns tuple
        assert isinstance(rs_stats, dict)
        assert isinstance(dc_stats, tuple)

        # Basic compatibility check
        assert len(rs_stats) > 0
        assert len(dc_stats) == 2  # (hits, misses)

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_nonexistent_key_behavior(self, diskcache_available, temp_dirs):
        """Test behavior with nonexistent keys"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        nonexistent_key = "this_key_does_not_exist"

        # Get nonexistent key
        rs_result = rs_cache.get(nonexistent_key)
        dc_result = dc_cache.get(nonexistent_key)

        # Both should return None
        assert rs_result is None
        assert dc_result is None

        # Exists check (use __contains__ for compatibility)
        assert nonexistent_key not in rs_cache
        assert nonexistent_key not in dc_cache

        # Delete nonexistent key
        rs_delete = rs_cache.delete(nonexistent_key)
        dc_delete = dc_cache.delete(nonexistent_key)

        # Both should return False
        assert not rs_delete
        assert not dc_delete

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_data_type_compatibility(self, diskcache_available, temp_dirs, sample_data):
        """Test compatibility with different data types"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        # Test different data types
        test_cases = [
            ("binary", sample_data["binary"]),
            ("small", sample_data["small"]),
            ("large", sample_data["large"]),
            ("json_like", sample_data["json_like"]),
        ]

        for test_name, test_data in test_cases:
            key = f"datatype_test_{test_name}"

            # Store in both caches
            rs_cache.set(key, test_data)
            dc_cache.set(key, test_data)

            # Retrieve from both
            rs_retrieved = rs_cache.get(key)
            dc_retrieved = dc_cache.get(key)

            # Should be identical
            assert rs_retrieved == dc_retrieved == test_data

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_unicode_key_compatibility(self, diskcache_available, temp_dirs):
        """Test unicode key handling compatibility"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        unicode_keys = [
            "测试键",  # Chinese
            "тест",  # Russian
            "key with spaces",
            "key-with-dashes",
        ]

        test_value = b"unicode key test"

        for key in unicode_keys:
            # Store in both caches
            rs_cache.set(key, test_value)
            dc_cache.set(key, test_value)

            # Retrieve from both
            rs_result = rs_cache.get(key)
            dc_result = dc_cache.get(key)

            # Should be identical
            assert rs_result == dc_result == test_value

            # Exists check (use __contains__ for compatibility)
            assert (key in rs_cache) == (key in dc_cache) is True

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()

    def test_overwrite_behavior_compatibility(
        self, diskcache_available, temp_dirs, sample_data
    ):
        """Test key overwrite behavior compatibility"""
        import diskcache
        from diskcache_rs import Cache

        rs_dir, dc_dir = temp_dirs

        rs_cache = Cache(rs_dir)
        dc_cache = diskcache.Cache(dc_dir)

        key = "overwrite_test"

        # Set initial value
        rs_cache.set(key, sample_data["small"])
        dc_cache.set(key, sample_data["small"])

        # Verify initial value
        assert rs_cache.get(key) == dc_cache.get(key) == sample_data["small"]

        # Overwrite with different value
        rs_cache.set(key, sample_data["large"])
        dc_cache.set(key, sample_data["large"])

        # Verify overwritten value
        assert rs_cache.get(key) == dc_cache.get(key) == sample_data["large"]

        # Close caches to release file handles
        rs_cache.close()
        dc_cache.close()
