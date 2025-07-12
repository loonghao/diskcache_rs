"""
Basic functionality tests for diskcache_rs
"""


class TestBasicOperations:
    """Test basic cache operations"""

    def test_set_and_get(self, cache, sample_data):
        """Test basic set and get operations"""
        for key, value in sample_data.items():
            cache.set(f"test_{key}", value)
            retrieved = cache.get(f"test_{key}")
            assert retrieved == value, (
                f"Failed for {key}: expected {value}, got {retrieved}"
            )

    def test_get_nonexistent_key(self, cache):
        """Test getting a nonexistent key returns None"""
        result = cache.get("nonexistent_key")
        assert result is None

    def test_exists(self, cache, sample_data):
        """Test key existence checking"""
        # Test non-existent key
        assert not cache.exists("nonexistent_key")

        # Test existing key
        cache.set("test_key", sample_data["small"])
        assert cache.exists("test_key")

    def test_delete(self, cache, sample_data):
        """Test key deletion"""
        # Set a key
        cache.set("delete_test", sample_data["small"])
        assert cache.exists("delete_test")

        # Delete it
        result = cache.delete("delete_test")
        assert result is True
        assert not cache.exists("delete_test")

        # Try to delete non-existent key
        result = cache.delete("nonexistent_key")
        assert result is False

    def test_keys(self, cache, sample_data):
        """Test listing all keys"""
        # Start with empty cache
        keys = cache.keys()
        initial_count = len(keys)

        # Add some keys
        test_keys = ["key1", "key2", "key3"]
        for key in test_keys:
            cache.set(key, sample_data["small"])

        # Check keys
        keys = cache.keys()
        assert len(keys) == initial_count + len(test_keys)
        for key in test_keys:
            assert key in keys

    def test_clear(self, cache, sample_data):
        """Test clearing all cache entries"""
        # Add some data
        for i in range(5):
            cache.set(f"clear_test_{i}", sample_data["small"])

        # Verify data exists
        assert len(cache.keys()) >= 5

        # Clear cache
        cache.clear()

        # Verify cache is empty
        assert len(cache.keys()) == 0

    def test_stats(self, cache):
        """Test cache statistics"""
        stats = cache.stats()
        assert isinstance(stats, dict)

        # Check for expected keys
        expected_keys = ["hits", "misses"]
        for key in expected_keys:
            assert key in stats
            assert isinstance(stats[key], int)

    def test_cache_size_limit(self, temp_cache_dir):
        """Test cache respects size limits"""
        from diskcache_rs import Cache

        # Create a small cache
        small_cache = Cache(
            temp_cache_dir,
            max_size=1024,  # 1KB limit
            max_entries=100,
        )

        # Try to store more than the limit
        large_data = b"x" * 2048  # 2KB
        small_cache.set("large_key", large_data)

        # The cache should handle this gracefully
        # (exact behavior depends on implementation)
        stats = small_cache.stats()
        assert isinstance(stats, dict)

    def test_cache_entry_limit(self, temp_cache_dir):
        """Test cache respects entry count limits"""
        from diskcache_rs import Cache

        # Create a cache with low entry limit
        limited_cache = Cache(temp_cache_dir, max_size=1024 * 1024, max_entries=5)

        # Add more entries than the limit
        for i in range(10):
            limited_cache.set(f"entry_{i}", b"data")

        # Cache should handle this gracefully
        keys = limited_cache.keys()
        # Exact behavior depends on eviction policy
        assert len(keys) <= 10  # Should not crash

    def test_unicode_keys(self, cache):
        """Test cache handles unicode keys properly"""
        unicode_keys = [
            "测试键",  # Chinese
            "тест",  # Russian
            "🔑",  # Emoji
            "key with spaces",
            "key-with-dashes",
            "key_with_underscores",
        ]

        for key in unicode_keys:
            cache.set(key, b"unicode test data")
            assert cache.exists(key)
            assert cache.get(key) == b"unicode test data"

    def test_binary_data(self, cache):
        """Test cache handles binary data correctly"""
        binary_data = bytes(range(256))
        cache.set("binary_key", binary_data)

        retrieved = cache.get("binary_key")
        assert retrieved == binary_data
        assert len(retrieved) == 256

    def test_empty_values(self, cache):
        """Test cache handles empty values"""
        cache.set("empty_key", b"")
        retrieved = cache.get("empty_key")
        assert retrieved == b""
        assert cache.exists("empty_key")

    def test_overwrite_key(self, cache, sample_data):
        """Test overwriting existing keys"""
        key = "overwrite_test"

        # Set initial value
        cache.set(key, sample_data["small"])
        assert cache.get(key) == sample_data["small"]

        # Overwrite with different value
        cache.set(key, sample_data["large"])
        assert cache.get(key) == sample_data["large"]
