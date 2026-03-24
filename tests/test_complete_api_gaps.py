"""Tests for newly added API completeness features.

Tests cover:
- Cache/FanoutCache: tag tracking, expire_time return, read param, evict, pickle
- Deque: __getitem__, __setitem__, __delitem__, copy, count, remove, reverse, rotate, comparisons
- Index: popitem, comparisons, cache property, transact, pickle
"""

import io
import os
import pickle
import tempfile

import pytest


@pytest.fixture
def cache_dir():
    """Create a temporary directory for cache"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# ============================================================
# Cache tag tracking and metadata return tests
# ============================================================


class TestCacheTagTracking:
    """Test that tags are properly tracked and returned."""

    def test_set_and_get_with_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", tag="group_a")
            value, tag = cache.get("key1", tag=True)
            assert value == "value1"
            assert tag == "group_a"

    def test_get_with_tag_no_tag_set(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1")
            value, tag = cache.get("key1", tag=True)
            assert value == "value1"
            assert tag is None

    def test_get_with_expire_time(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", expire=3600)
            value, et = cache.get("key1", expire_time=True)
            assert value == "value1"
            assert et is not None
            assert et > 0

    def test_get_with_expire_time_and_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", expire=3600, tag="mytag")
            value, et, tag = cache.get("key1", expire_time=True, tag=True)
            assert value == "value1"
            assert et is not None
            assert tag == "mytag"

    def test_get_missing_key_with_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            result = cache.get("missing", tag=True)
            assert result == (None, None)

    def test_get_missing_key_with_expire_time(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            result = cache.get("missing", expire_time=True)
            assert result == (None, None)

    def test_get_missing_key_with_both(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            result = cache.get("missing", expire_time=True, tag=True)
            assert result == (None, None, None)


class TestCacheEvictByTag:
    """Test tag-based eviction."""

    def test_evict_by_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("a", 1, tag="group1")
            cache.set("b", 2, tag="group1")
            cache.set("c", 3, tag="group2")
            count = cache.evict("group1")
            assert count == 2
            assert "a" not in cache
            assert "b" not in cache
            assert "c" in cache

    def test_evict_nonexistent_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("a", 1, tag="group1")
            count = cache.evict("nonexistent")
            assert count == 0
            assert "a" in cache


class TestCacheReadParam:
    """Test read parameter support."""

    def test_set_with_read_true(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            fh = io.BytesIO(b"hello world")
            cache.set("key1", fh, read=True)
            value = cache.get("key1")
            assert value == b"hello world"

    def test_get_with_read_true(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", b"hello world")
            result = cache.get("key1", read=True)
            assert isinstance(result, io.BytesIO)
            assert result.read() == b"hello world" or result.read() != b""


class TestCachePopMetadata:
    """Test pop with expire_time and tag return."""

    def test_pop_with_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", tag="mytag")
            value, tag = cache.pop("key1", tag=True)
            assert value == "value1"
            assert tag == "mytag"
            assert "key1" not in cache

    def test_pop_with_expire_time(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", expire=3600)
            value, et = cache.pop("key1", expire_time=True)
            assert value == "value1"
            assert et is not None

    def test_pop_missing_with_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            result = cache.pop("missing", tag=True)
            assert result == (None, None)

    def test_pop_with_both(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("key1", "value1", expire=3600, tag="t")
            value, et, tag = cache.pop("key1", expire_time=True, tag=True)
            assert value == "value1"
            assert et is not None
            assert tag == "t"


class TestCachePickle:
    """Test pickle serialization support."""

    def test_cache_pickle_roundtrip(self, cache_dir):
        from diskcache_rs import Cache

        cache = Cache(cache_dir)
        cache.set("key1", "value1")
        state = pickle.dumps(cache)
        cache.close()

        cache2 = pickle.loads(state)
        assert cache2.get("key1") == "value1"
        cache2.close()


class TestCachePeekitemMetadata:
    """Test peekitem with metadata return."""

    def test_peekitem_with_tag(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("a", 1, tag="t1")
            cache.set("b", 2, tag="t2")
            result = cache.peekitem(last=True, tag=True)
            assert len(result) == 3
            assert result[0] == "b"
            assert result[1] == 2
            assert result[2] == "t2"

    def test_peekitem_with_expire_time(self, cache_dir):
        from diskcache_rs import Cache

        with Cache(cache_dir) as cache:
            cache.set("a", 1, expire=3600)
            result = cache.peekitem(last=True, expire_time=True)
            assert len(result) == 3
            assert result[0] == "a"
            assert result[2] is not None  # expire_time


# ============================================================
# Deque new methods tests
# ============================================================


class TestDequeIndexAccess:
    """Test Deque index access operations."""

    def test_getitem(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([10, 20, 30])
            assert dq[0] == 10
            assert dq[1] == 20
            assert dq[2] == 30
            assert dq[-1] == 30

    def test_setitem(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([10, 20, 30])
            dq[1] = 99
            assert dq[1] == 99

    def test_delitem(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([10, 20, 30])
            del dq[1]
            assert len(dq) == 2
            assert list(dq) == [10, 30]


class TestDequeUtilMethods:
    """Test Deque utility methods."""

    def test_copy(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3])
            dq2 = dq.copy()
            assert list(dq2) == [1, 2, 3]
            dq2.close()

    def test_count(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 2, 3, 2])
            assert dq.count(2) == 3
            assert dq.count(4) == 0

    def test_remove(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3, 2])
            dq.remove(2)
            assert list(dq) == [1, 3, 2]

    def test_remove_missing(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3])
            with pytest.raises(ValueError):
                dq.remove(99)

    def test_reverse(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3])
            dq.reverse()
            assert list(dq) == [3, 2, 1]

    def test_rotate_right(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3, 4, 5])
            dq.rotate(2)
            assert list(dq) == [4, 5, 1, 2, 3]

    def test_rotate_left(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3, 4, 5])
            dq.rotate(-2)
            assert list(dq) == [3, 4, 5, 1, 2]

    def test_contains(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2, 3])
            assert 2 in dq
            assert 99 not in dq

    def test_iadd(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            dq.extend([1, 2])
            dq += [3, 4]
            assert list(dq) == [1, 2, 3, 4]


class TestDequeComparisons:
    """Test Deque comparison operators."""

    def test_eq(self, cache_dir):
        from diskcache_rs import Deque

        dq1 = Deque(directory=os.path.join(cache_dir, "dq1"))
        dq2 = Deque(directory=os.path.join(cache_dir, "dq2"))
        dq1.extend([1, 2, 3])
        dq2.extend([1, 2, 3])
        assert dq1 == dq2
        dq1.close()
        dq2.close()

    def test_ne(self, cache_dir):
        from diskcache_rs import Deque

        dq1 = Deque(directory=os.path.join(cache_dir, "dq1"))
        dq2 = Deque(directory=os.path.join(cache_dir, "dq2"))
        dq1.extend([1, 2, 3])
        dq2.extend([1, 2, 4])
        assert dq1 != dq2
        dq1.close()
        dq2.close()

    def test_lt(self, cache_dir):
        from diskcache_rs import Deque

        dq1 = Deque(directory=os.path.join(cache_dir, "dq1"))
        dq2 = Deque(directory=os.path.join(cache_dir, "dq2"))
        dq1.extend([1, 2, 3])
        dq2.extend([1, 2, 4])
        assert dq1 < dq2
        dq1.close()
        dq2.close()


class TestDequePickle:
    """Test Deque pickle support."""

    def test_pickle_roundtrip(self, cache_dir):
        from diskcache_rs import Deque

        dq = Deque(directory=os.path.join(cache_dir, "dq"))
        dq.extend([1, 2, 3])
        state = pickle.dumps(dq)
        dq.close()

        dq2 = pickle.loads(state)
        assert list(dq2) == [1, 2, 3]
        dq2.close()


class TestDequeTransact:
    """Test Deque transaction support."""

    def test_transact(self, cache_dir):
        from diskcache_rs import Deque

        with Deque(directory=os.path.join(cache_dir, "dq")) as dq:
            with dq.transact():
                dq.append(1)
                dq.append(2)
            assert list(dq) == [1, 2]


# ============================================================
# Index new methods tests
# ============================================================


class TestIndexPopitem:
    """Test Index popitem method."""

    def test_popitem_last(self, cache_dir):
        from diskcache_rs import Index

        with Index(directory=os.path.join(cache_dir, "idx")) as idx:
            idx["a"] = 1
            idx["b"] = 2
            idx["c"] = 3
            key, value = idx.popitem(last=True)
            assert key == "c"
            assert value == 3
            assert len(idx) == 2

    def test_popitem_first(self, cache_dir):
        from diskcache_rs import Index

        with Index(directory=os.path.join(cache_dir, "idx")) as idx:
            idx["a"] = 1
            idx["b"] = 2
            idx["c"] = 3
            key, value = idx.popitem(last=False)
            assert key == "a"
            assert value == 1
            assert len(idx) == 2

    def test_popitem_empty(self, cache_dir):
        from diskcache_rs import Index

        with Index(directory=os.path.join(cache_dir, "idx")) as idx:
            with pytest.raises(KeyError):
                idx.popitem()


class TestIndexComparisons:
    """Test Index comparison operators."""

    def test_eq_index(self, cache_dir):
        from diskcache_rs import Index

        idx1 = Index(directory=os.path.join(cache_dir, "idx1"))
        idx2 = Index(directory=os.path.join(cache_dir, "idx2"))
        idx1["a"] = 1
        idx1["b"] = 2
        idx2["a"] = 1
        idx2["b"] = 2
        assert idx1 == idx2
        idx1.close()
        idx2.close()

    def test_eq_dict(self, cache_dir):
        from diskcache_rs import Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))
        idx["a"] = 1
        idx["b"] = 2
        assert idx == {"a": 1, "b": 2}
        idx.close()

    def test_ne(self, cache_dir):
        from diskcache_rs import Index

        idx1 = Index(directory=os.path.join(cache_dir, "idx1"))
        idx2 = Index(directory=os.path.join(cache_dir, "idx2"))
        idx1["a"] = 1
        idx2["a"] = 2
        assert idx1 != idx2
        idx1.close()
        idx2.close()


class TestIndexCacheProperty:
    """Test Index cache property."""

    def test_cache_property(self, cache_dir):
        from diskcache_rs import Cache, Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))
        assert isinstance(idx.cache, Cache)
        idx.close()


class TestIndexTransact:
    """Test Index transaction support."""

    def test_transact(self, cache_dir):
        from diskcache_rs import Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))
        with idx.transact():
            idx["a"] = 1
            idx["b"] = 2
        assert idx["a"] == 1
        assert idx["b"] == 2
        idx.close()


class TestIndexPickle:
    """Test Index pickle support."""

    def test_pickle_roundtrip(self, cache_dir):
        from diskcache_rs import Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))
        idx["a"] = 1
        idx["b"] = 2
        state = pickle.dumps(idx)
        idx.close()

        idx2 = pickle.loads(state)
        assert idx2["a"] == 1
        assert idx2["b"] == 2
        idx2.close()


class TestIndexMemoize:
    """Test Index memoize decorator."""

    def test_memoize(self, cache_dir):
        from diskcache_rs import Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))

        call_count = 0

        @idx.memoize()
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(5) == 10
        assert call_count == 1
        assert compute(5) == 10
        assert call_count == 1  # cached
        idx.close()


class TestIndexPushPull:
    """Test Index push/pull operations."""

    def test_push_pull(self, cache_dir):
        from diskcache_rs import Index

        idx = Index(directory=os.path.join(cache_dir, "idx"))
        idx.push("val1")
        idx.push("val2")
        key, value = idx.pull()
        assert value == "val1"
        idx.close()


# ============================================================
# FanoutCache metadata tests
# ============================================================


class TestFanoutCacheMetadata:
    """Test FanoutCache tag and expire_time tracking."""

    def test_get_with_tag(self, cache_dir):
        from diskcache_rs import FanoutCache

        with FanoutCache(cache_dir) as fc:
            fc.set("key1", "value1", tag="group_a")
            value, tag = fc.get("key1", tag=True)
            assert value == "value1"
            assert tag == "group_a"

    def test_evict_by_tag(self, cache_dir):
        from diskcache_rs import FanoutCache

        with FanoutCache(cache_dir) as fc:
            fc.set("a", 1, tag="g1")
            fc.set("b", 2, tag="g1")
            fc.set("c", 3, tag="g2")
            count = fc.evict("g1")
            assert count == 2
            assert "c" in fc

    def test_pickle_roundtrip(self, cache_dir):
        from diskcache_rs import FanoutCache

        fc = FanoutCache(cache_dir)
        fc.set("key1", "value1")
        state = pickle.dumps(fc)
        fc.close()

        fc2 = pickle.loads(state)
        assert fc2.get("key1") == "value1"
        fc2.close()
