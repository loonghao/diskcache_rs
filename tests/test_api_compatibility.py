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

    def test_memoize_decorator(self):
        """Test memoize decorator"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            call_count = 0

            @cache.memoize(expire=60)
            def expensive_function(x):
                nonlocal call_count
                call_count += 1
                return x * x

            # First call - should execute function
            result1 = expensive_function(5)
            assert result1 == 25
            assert call_count == 1

            # Second call with same args - should use cache
            result2 = expensive_function(5)
            assert result2 == 25
            assert call_count == 1  # Not incremented

            # Different args - should execute function
            result3 = expensive_function(10)
            assert result3 == 100
            assert call_count == 2

            # Test __cache_key__ attribute
            key = expensive_function.__cache_key__(5)
            assert isinstance(key, str)
            assert "memoize" in key

            # Test __wrapped__ attribute
            assert expensive_function.__wrapped__(5) == 25

            cache.close()

    def test_memoize_typed(self):
        """Test memoize with typed=True"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            call_count = 0

            @cache.memoize(typed=True)
            def typed_function(x):
                nonlocal call_count
                call_count += 1
                return x

            # Different types should be cached separately
            typed_function(3)
            assert call_count == 1

            typed_function(3.0)
            assert call_count == 2  # Different type, new call

            typed_function(3)
            assert call_count == 2  # Same type, cached

            cache.close()

    def test_memoize_ignore(self):
        """Test memoize with ignore parameter"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            call_count = 0

            @cache.memoize(ignore={"debug"})
            def function_with_debug(x, debug=False):
                nonlocal call_count
                call_count += 1
                return x * 2

            # Calls with different debug values should use same cache
            result1 = function_with_debug(5, debug=True)
            assert result1 == 10
            assert call_count == 1

            result2 = function_with_debug(5, debug=False)
            assert result2 == 10
            assert call_count == 1  # Cached, debug ignored

            cache.close()

    def test_transact(self):
        """Test transaction context manager"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Atomic increment of two keys
            with cache.transact():
                cache["total"] = cache.get("total", 0) + 123.4
                cache["count"] = cache.get("count", 0) + 1

            assert cache["total"] == 123.4
            assert cache["count"] == 1

            # Atomic calculation
            with cache.transact():
                average = cache["total"] / cache["count"]

            assert average == 123.4

            cache.close()

    def test_nested_transact(self):
        """Test nested transactions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            with cache.transact():
                cache["x"] = 1
                with cache.transact():
                    cache["y"] = 2
                    with cache.transact():
                        cache["z"] = 3

            assert cache["x"] == 1
            assert cache["y"] == 2
            assert cache["z"] == 3

            cache.close()

    def test_iterkeys(self):
        """Test iterkeys method"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Add items with numeric keys
            for key in [4, 1, 3, 0, 2]:
                cache[str(key)] = key

            # Forward iteration
            keys = list(cache.iterkeys())
            assert keys == ["0", "1", "2", "3", "4"]

            # Reverse iteration
            keys_reversed = list(cache.iterkeys(reverse=True))
            assert keys_reversed == ["4", "3", "2", "1", "0"]

            cache.close()

    def test_reversed(self):
        """Test __reversed__ method"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            for key in ["a", "b", "c"]:
                cache[key] = key

            # Reverse iteration using reversed()
            keys = list(reversed(cache))
            assert keys == ["c", "b", "a"]

            cache.close()

    def test_peekitem(self):
        """Test peekitem method"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            for num, letter in enumerate("abc"):
                cache[letter] = num

            # Peek at last item
            key, value = cache.peekitem()
            assert key == "c"
            assert value == 2

            # Peek at first item
            key, value = cache.peekitem(last=False)
            assert key == "a"
            assert value == 0

            # Test with empty cache
            cache.clear()
            try:
                cache.peekitem()
                assert False, "Should raise KeyError"
            except KeyError as e:
                assert "empty" in str(e)

            cache.close()

    def test_directory_property(self):
        """Test directory property"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)
            assert cache.directory == Path(tmpdir)
            cache.close()

    def test_timeout_property(self):
        """Test timeout property"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir, timeout=30.0)
            assert cache.timeout == 30.0
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

    def test_memoize_decorator(self):
        """Test memoize decorator for FanoutCache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            call_count = 0

            @cache.memoize(expire=60)
            def expensive_function(x):
                nonlocal call_count
                call_count += 1
                return x * x

            # First call - should execute function
            result1 = expensive_function(5)
            assert result1 == 25
            assert call_count == 1

            # Second call with same args - should use cache
            result2 = expensive_function(5)
            assert result2 == 25
            assert call_count == 1  # Not incremented

            # Different args - should execute function
            result3 = expensive_function(10)
            assert result3 == 100
            assert call_count == 2

            # Test __cache_key__ attribute
            key = expensive_function.__cache_key__(5)
            assert isinstance(key, str)
            assert "memoize" in key

            # Test __wrapped__ attribute
            assert expensive_function.__wrapped__(5) == 25

            cache.close()

    def test_transact(self):
        """Test transaction context manager for FanoutCache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Atomic increment of two keys
            with cache.transact():
                cache["total"] = cache.get("total", 0) + 123.4
                cache["count"] = cache.get("count", 0) + 1

            assert cache["total"] == 123.4
            assert cache["count"] == 1

            cache.close()

    def test_iterkeys(self):
        """Test iterkeys method for FanoutCache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            # Add items
            for key in ["d", "a", "c", "b"]:
                cache[key] = key

            # Forward iteration (should be sorted)
            keys = list(cache.iterkeys())
            assert keys == ["a", "b", "c", "d"]

            # Reverse iteration
            keys_reversed = list(cache.iterkeys(reverse=True))
            assert keys_reversed == ["d", "c", "b", "a"]

            cache.close()

    def test_reversed(self):
        """Test __reversed__ method for FanoutCache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            for key in ["a", "b", "c"]:
                cache[key] = key

            # Reverse iteration using reversed()
            keys = list(reversed(cache))
            assert keys == ["c", "b", "a"]

            cache.close()

    def test_peekitem(self):
        """Test peekitem method for FanoutCache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=4)

            for num, letter in enumerate("abc"):
                cache[letter] = num

            # Peek at last item
            key, value = cache.peekitem()
            assert key == "c"
            assert value == 2

            # Peek at first item
            key, value = cache.peekitem(last=False)
            assert key == "a"
            assert value == 0

            cache.close()
