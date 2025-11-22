"""Test API compatibility with python-diskcache"""

import tempfile
from pathlib import Path

import pytest

from diskcache_rs import Cache, FanoutCache


class TestCacheAPICompatibility:
    """Test Cache class API compatibility with python-diskcache"""

    def test_basic_operations(self):
        """Test basic get/set/delete operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Set and get
            cache["key1"] = "value1"
            assert cache["key1"] == "value1"

            # Contains
            assert "key1" in cache

            # Delete
            del cache["key1"]
            assert "key1" not in cache

            cache.close()

    def test_dictionary_interface(self):
        """Test dictionary-style interface"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Set multiple items
            cache["a"] = 1
            cache["b"] = 2
            cache["c"] = 3

            # Length
            assert len(cache) == 3

            # Iteration
            keys = list(cache)
            assert set(keys) == {"a", "b", "c"}

            # Clear
            count = cache.clear()
            assert count == 3
            assert len(cache) == 0

            cache.close()

    def test_atomic_operations(self):
        """Test atomic operations (add, incr, decr, pop)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Add (only if not exists)
            assert cache.add("counter", 0) is True
            assert cache.add("counter", 1) is False  # Already exists
            assert cache["counter"] == 0

            # Increment
            result = cache.incr("counter", 5)
            assert result == 5
            assert cache["counter"] == 5

            # Decrement
            result = cache.decr("counter", 2)
            assert result == 3
            assert cache["counter"] == 3

            # Pop
            value = cache.pop("counter")
            assert value == 3
            assert "counter" not in cache

            cache.close()

    def test_expiration(self):
        """Test expiration and touch"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Set with expiration
            cache.set("temp", "value", expire=1.0)
            assert cache.get("temp") == "value"

            # Touch to update expiration
            assert cache.touch("temp", expire=10.0) is True

            cache.close()

    def test_context_manager(self):
        """Test context manager support"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with Cache(tmpdir) as cache:
                cache["key"] = "value"
                assert cache["key"] == "value"

    def test_stats_and_volume(self):
        """Test statistics and volume"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            cache["key1"] = "value1"
            cache["key2"] = "value2"

            # Stats
            stats = cache.stats()
            assert isinstance(stats, dict)
            assert "hits" in stats
            assert "misses" in stats

            # Volume
            volume = cache.volume()
            assert isinstance(volume, int)
            assert volume >= 0

            cache.close()


class TestFanoutCacheAPICompatibility:
    """Test FanoutCache class API compatibility with python-diskcache"""

    def test_basic_operations(self):
        """Test basic get/set/delete operations"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Set and get
            cache["key1"] = "value1"
            assert cache["key1"] == "value1"

            # Contains
            assert "key1" in cache

            # Delete
            del cache["key1"]
            assert "key1" not in cache

            cache.close()

    def test_dictionary_interface(self):
        """Test dictionary-style interface"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Set multiple items
            cache["a"] = 1
            cache["b"] = 2
            cache["c"] = 3

            # Length
            assert len(cache) == 3

            # Iteration
            keys = list(cache)
            assert set(keys) == {"a", "b", "c"}

            # Clear
            count = cache.clear()
            assert count == 3
            assert len(cache) == 0

            cache.close()

    def test_atomic_operations(self):
        """Test atomic operations (add, incr, decr, pop) - NEW"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Add (only if not exists)
            assert cache.add("counter", 0) is True
            assert cache.add("counter", 1) is False  # Already exists
            assert cache["counter"] == 0

            # Increment
            result = cache.incr("counter", 5)
            assert result == 5
            assert cache["counter"] == 5

            # Decrement
            result = cache.decr("counter", 2)
            assert result == 3
            assert cache["counter"] == 3

            # Pop
            value = cache.pop("counter")
            assert value == 3
            assert "counter" not in cache

            cache.close()

    def test_touch(self):
        """Test touch operation - NEW"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Set with expiration
            cache.set("temp", "value", expire=1.0)
            assert cache.get("temp") == "value"

            # Touch to update expiration
            assert cache.touch("temp", expire=10.0) is True

            cache.close()

    def test_stats_and_volume(self):
        """Test statistics and volume"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            cache["key1"] = "value1"
            cache["key2"] = "value2"

            # Stats
            stats = cache.stats()
            assert isinstance(stats, dict)
            assert "hits" in stats
            assert "misses" in stats

            # Volume
            volume = cache.volume()
            assert isinstance(volume, int)
            assert volume >= 0

            cache.close()
