"""
Tests for full python-diskcache API compatibility.

This module tests all the methods that were added to achieve ~99% API
compatibility with python-diskcache, including:
- Cache: check, cull, evict, push/pull/peek, read, reset,
         create_tag_index, drop_tag_index, disk, values, items
- FanoutCache: check, cull, evict, push/pull/peek, read, reset,
               cache, deque, index, keys, values, items, exists, vacuum, disk
- Deque: full deque API
- Index: full index API
"""

import io

import pytest


@pytest.fixture
def cache_dir(tmp_path):
    """Create a temporary cache directory."""
    d = tmp_path / "test_cache"
    d.mkdir()
    return str(d)


@pytest.fixture
def cache(cache_dir):
    """Create a Cache instance."""
    from diskcache_rs import Cache

    c = Cache(cache_dir)
    yield c
    c.close()


@pytest.fixture
def fanout_cache(tmp_path):
    """Create a FanoutCache instance."""
    from diskcache_rs import FanoutCache

    d = tmp_path / "test_fanout"
    d.mkdir()
    c = FanoutCache(str(d), shards=4)
    yield c
    c.close()


# ============================================================
# Cache class tests
# ============================================================


class TestCacheCheck:
    """Tests for Cache.check()"""

    def test_check_empty_cache(self, cache):
        warnings = cache.check()
        assert isinstance(warnings, list)
        assert len(warnings) == 0

    def test_check_with_data(self, cache):
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        warnings = cache.check()
        assert isinstance(warnings, list)
        assert len(warnings) == 0

    def test_check_fix_mode(self, cache):
        cache.set("key1", "value1")
        warnings = cache.check(fix=True)
        assert isinstance(warnings, list)


class TestCacheTagOperations:
    """Tests for Cache.create_tag_index() and drop_tag_index()"""

    def test_create_tag_index_noop(self, cache):
        # Should not raise
        cache.create_tag_index()

    def test_drop_tag_index_noop(self, cache):
        # Should not raise
        cache.drop_tag_index()

    def test_create_then_drop_tag_index(self, cache):
        cache.create_tag_index()
        cache.drop_tag_index()


class TestCacheCull:
    """Tests for Cache.cull()"""

    def test_cull_empty_cache(self, cache):
        count = cache.cull()
        assert isinstance(count, int)
        assert count >= 0

    def test_cull_with_data(self, cache):
        for i in range(10):
            cache.set(f"key{i}", f"value{i}")
        count = cache.cull()
        assert isinstance(count, int)


class TestCacheEvict:
    """Tests for Cache.evict()"""

    def test_evict_tag(self, cache):
        cache.set("key1", "value1", tag="group1")
        cache.set("key2", "value2", tag="group1")
        count = cache.evict("group1")
        assert isinstance(count, int)


class TestCacheQueueOperations:
    """Tests for Cache.push(), pull(), peek()"""

    def test_push_and_pull(self, cache):
        key1 = cache.push("first")
        key2 = cache.push("second")
        assert key1 == 0
        assert key2 == 1

        result = cache.pull()
        assert result[0] == 0
        assert result[1] == "first"

        result = cache.pull()
        assert result[0] == 1
        assert result[1] == "second"

    def test_push_front(self, cache):
        cache.push("first")
        key = cache.push("zero", side="front")
        assert key == -1

    def test_pull_empty_queue(self, cache):
        result = cache.pull()
        assert result == (None, None)

    def test_pull_with_default(self, cache):
        result = cache.pull(default=("default_key", "default_val"))
        assert result == ("default_key", "default_val")

    def test_peek_without_removing(self, cache):
        cache.push("first")
        cache.push("second")

        # Peek should not remove the item
        result1 = cache.peek()
        result2 = cache.peek()
        assert result1 == result2
        assert result1[1] == "first"

    def test_peek_back(self, cache):
        cache.push("first")
        cache.push("second")

        result = cache.peek(side="back")
        assert result[1] == "second"

    def test_push_invalid_side(self, cache):
        with pytest.raises(ValueError):
            cache.push("value", side="invalid")

    def test_pull_invalid_side(self, cache):
        with pytest.raises(ValueError):
            cache.pull(side="invalid")

    def test_peek_invalid_side(self, cache):
        with pytest.raises(ValueError):
            cache.peek(side="invalid")

    def test_push_with_prefix(self, cache):
        key1 = cache.push("task1", prefix="tasks")
        key2 = cache.push("task2", prefix="tasks")
        assert key1 == 0
        assert key2 == 1

        result = cache.pull(prefix="tasks")
        assert result[1] == "task1"

    def test_push_with_expire(self, cache):
        cache.push("temporary", expire=3600)
        result = cache.peek()
        assert result[1] == "temporary"


class TestCacheRead:
    """Tests for Cache.read()"""

    def test_read_returns_bytesio(self, cache):
        cache.set("key", b"hello world")
        result = cache.read("key")
        assert isinstance(result, io.BytesIO)

    def test_read_content(self, cache):
        cache.set("key", b"hello world")
        result = cache.read("key")
        data = result.read()
        assert isinstance(data, bytes)

    def test_read_missing_key(self, cache):
        with pytest.raises(KeyError):
            cache.read("nonexistent")


class TestCacheReset:
    """Tests for Cache.reset()"""

    def test_reset_read_default(self, cache):
        value = cache.reset("size_limit")
        assert value == 1073741824  # 1GB default

    def test_reset_set_value(self, cache):
        result = cache.reset("size_limit", 2**20)
        assert result == 2**20

    def test_reset_unknown_key(self, cache):
        value = cache.reset("unknown_setting")
        assert value is None


class TestCacheDiskProperty:
    """Tests for Cache.disk property"""

    def test_disk_exists(self, cache):
        disk = cache.disk
        assert disk is not None

    def test_disk_store(self, cache):
        disk = cache.disk
        data = disk.store("hello")
        assert isinstance(data, bytes)

    def test_disk_fetch(self, cache):
        disk = cache.disk
        data = disk.store("hello")
        result = disk.fetch(0, "", data)
        assert result == "hello"


class TestCacheValuesItems:
    """Tests for Cache.values() and items()"""

    def test_values_empty(self, cache):
        assert cache.values() == []

    def test_values_with_data(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        vals = cache.values()
        assert len(vals) == 2
        assert set(vals) == {1, 2}

    def test_items_empty(self, cache):
        assert cache.items() == []

    def test_items_with_data(self, cache):
        cache.set("a", 1)
        cache.set("b", 2)
        items = cache.items()
        assert len(items) == 2
        items_dict = dict(items)
        assert items_dict["a"] == 1
        assert items_dict["b"] == 2


# ============================================================
# FanoutCache class tests
# ============================================================


class TestFanoutCacheCheck:
    """Tests for FanoutCache.check()"""

    def test_check_empty(self, fanout_cache):
        warnings = fanout_cache.check()
        assert isinstance(warnings, list)

    def test_check_with_data(self, fanout_cache):
        fanout_cache.set("key1", "value1")
        warnings = fanout_cache.check()
        assert isinstance(warnings, list)


class TestFanoutCacheTagOperations:
    def test_create_tag_index(self, fanout_cache):
        fanout_cache.create_tag_index()  # Should not raise

    def test_drop_tag_index(self, fanout_cache):
        fanout_cache.drop_tag_index()  # Should not raise


class TestFanoutCacheCull:
    def test_cull(self, fanout_cache):
        for i in range(10):
            fanout_cache.set(f"key{i}", f"value{i}")
        count = fanout_cache.cull()
        assert isinstance(count, int)


class TestFanoutCacheEvict:
    def test_evict(self, fanout_cache):
        fanout_cache.set("key1", "value1", tag="group1")
        count = fanout_cache.evict("group1")
        assert isinstance(count, int)


class TestFanoutCacheRead:
    def test_read(self, fanout_cache):
        fanout_cache.set("key", b"hello")
        result = fanout_cache.read("key")
        assert isinstance(result, io.BytesIO)

    def test_read_missing_key(self, fanout_cache):
        with pytest.raises(KeyError):
            fanout_cache.read("nonexistent")


class TestFanoutCacheReset:
    def test_reset_read_default(self, fanout_cache):
        value = fanout_cache.reset("size_limit")
        assert value == 1073741824

    def test_reset_set_value(self, fanout_cache):
        result = fanout_cache.reset("size_limit", 2**20)
        assert result == 2**20


class TestFanoutCacheQueueOperations:
    def test_push_and_pull(self, fanout_cache):
        key1 = fanout_cache.push("first")
        key2 = fanout_cache.push("second")
        assert key1 == 0
        assert key2 == 1

        result = fanout_cache.pull()
        assert result[1] == "first"

    def test_peek(self, fanout_cache):
        fanout_cache.push("item")
        result = fanout_cache.peek()
        assert result[1] == "item"
        # Still there after peek
        result2 = fanout_cache.peek()
        assert result2[1] == "item"


class TestFanoutCacheSubCaches:
    """Tests for FanoutCache.cache(), deque(), index()"""

    def test_cache_method(self, fanout_cache):
        from diskcache_rs import Cache

        sub = fanout_cache.cache("subcache")
        assert isinstance(sub, Cache)
        sub.set("key", "value")
        assert sub.get("key") == "value"
        sub.close()

    def test_deque_method(self, fanout_cache):
        from diskcache_rs.cache import Deque

        dq = fanout_cache.deque("mydeque")
        assert isinstance(dq, Deque)
        dq.append("item")
        assert len(dq) > 0
        dq.close()

    def test_index_method(self, fanout_cache):
        from diskcache_rs.cache import Index

        idx = fanout_cache.index("myindex")
        assert isinstance(idx, Index)
        idx["key"] = "value"
        assert idx["key"] == "value"
        idx.close()


class TestFanoutCacheKeysValuesItems:
    def test_keys(self, fanout_cache):
        fanout_cache.set("a", 1)
        fanout_cache.set("b", 2)
        keys = fanout_cache.keys()
        assert len(keys) == 2
        assert set(keys) == {"a", "b"}

    def test_values(self, fanout_cache):
        fanout_cache.set("a", 1)
        fanout_cache.set("b", 2)
        vals = fanout_cache.values()
        assert len(vals) == 2
        assert set(vals) == {1, 2}

    def test_items(self, fanout_cache):
        fanout_cache.set("a", 1)
        fanout_cache.set("b", 2)
        items = fanout_cache.items()
        assert len(items) == 2
        items_dict = dict(items)
        assert items_dict["a"] == 1
        assert items_dict["b"] == 2


class TestFanoutCacheExists:
    def test_exists(self, fanout_cache):
        fanout_cache.set("key", "value")
        assert fanout_cache.exists("key") is True
        assert fanout_cache.exists("nonexistent") is False


class TestFanoutCacheVacuum:
    def test_vacuum(self, fanout_cache):
        fanout_cache.set("key", "value")
        # Should not raise
        fanout_cache.vacuum()


class TestFanoutCacheDiskProperty:
    def test_disk_exists(self, fanout_cache):
        disk = fanout_cache.disk
        assert disk is not None


# ============================================================
# Deque class tests
# ============================================================


class TestDeque:
    @pytest.fixture
    def deque(self, tmp_path):
        from diskcache_rs.cache import Deque

        d = tmp_path / "test_deque"
        d.mkdir()
        dq = Deque(directory=str(d))
        yield dq
        dq.close()

    def test_append_and_popleft(self, deque):
        deque.append("a")
        deque.append("b")
        assert deque.popleft() == "a"
        assert deque.popleft() == "b"

    def test_appendleft_and_pop(self, deque):
        deque.appendleft("a")
        deque.appendleft("b")
        assert deque.pop() == "a"
        assert deque.pop() == "b"

    def test_len(self, deque):
        assert len(deque) == 0
        deque.append("a")
        assert len(deque) >= 1

    def test_bool(self, deque):
        assert not deque
        deque.append("a")
        assert deque

    def test_peek(self, deque):
        deque.append("a")
        assert deque.peek() == "a"
        # Item should still be there
        assert len(deque) >= 1

    def test_peekleft(self, deque):
        deque.append("a")
        deque.append("b")
        assert deque.peekleft() == "a"

    def test_pop_empty(self, deque):
        with pytest.raises(IndexError):
            deque.pop()

    def test_popleft_empty(self, deque):
        with pytest.raises(IndexError):
            deque.popleft()

    def test_clear(self, deque):
        deque.append("a")
        deque.append("b")
        deque.clear()
        assert len(deque) == 0

    def test_extend(self, deque):
        deque.extend(["a", "b", "c"])
        assert deque.popleft() == "a"

    def test_extendleft(self, deque):
        deque.extendleft(["a", "b", "c"])
        # extendleft adds one by one to the left, so order is reversed
        assert deque.pop() == "a"

    def test_init_with_iterable(self, tmp_path):
        from diskcache_rs.cache import Deque

        d = tmp_path / "deque_init"
        d.mkdir()
        dq = Deque(["a", "b", "c"], directory=str(d))
        assert len(dq) >= 3
        dq.close()

    def test_maxlen(self, tmp_path):
        from diskcache_rs.cache import Deque

        d = tmp_path / "deque_maxlen"
        d.mkdir()
        dq = Deque(directory=str(d), maxlen=2)
        assert dq.maxlen == 2
        dq.append("a")
        dq.append("b")
        dq.append("c")  # Should evict oldest
        assert len(dq) <= 2
        dq.close()

    def test_context_manager(self, tmp_path):
        from diskcache_rs.cache import Deque

        d = tmp_path / "deque_ctx"
        d.mkdir()
        with Deque(directory=str(d)) as dq:
            dq.append("a")
            assert len(dq) >= 1


# ============================================================
# Index class tests
# ============================================================


class TestIndex:
    @pytest.fixture
    def index(self, tmp_path):
        from diskcache_rs.cache import Index

        d = tmp_path / "test_index"
        d.mkdir()
        idx = Index(directory=str(d))
        yield idx
        idx.close()

    def test_set_and_get(self, index):
        index["key"] = "value"
        assert index["key"] == "value"

    def test_contains(self, index):
        index["key"] = "value"
        assert "key" in index
        assert "nonexistent" not in index

    def test_delete(self, index):
        index["key"] = "value"
        del index["key"]
        assert "key" not in index

    def test_len(self, index):
        assert len(index) == 0
        index["key"] = "value"
        assert len(index) == 1

    def test_bool(self, index):
        assert not index
        index["key"] = "value"
        assert index

    def test_get_with_default(self, index):
        assert index.get("nonexistent", "default") == "default"

    def test_pop(self, index):
        index["key"] = "value"
        result = index.pop("key")
        assert result == "value"
        assert "key" not in index

    def test_pop_default(self, index):
        result = index.pop("nonexistent", "default")
        assert result == "default"

    def test_setdefault(self, index):
        result = index.setdefault("key", "default")
        assert result == "default"
        assert index["key"] == "default"

        # Existing key should not be overwritten
        result = index.setdefault("key", "new_default")
        assert result == "default"

    def test_keys(self, index):
        index["a"] = 1
        index["b"] = 2
        keys = index.keys()
        assert set(keys) == {"a", "b"}

    def test_values(self, index):
        index["a"] = 1
        index["b"] = 2
        vals = index.values()
        assert set(vals) == {1, 2}

    def test_items(self, index):
        index["a"] = 1
        index["b"] = 2
        items = dict(index.items())
        assert items == {"a": 1, "b": 2}

    def test_update(self, index):
        index.update({"a": 1, "b": 2})
        assert index["a"] == 1
        assert index["b"] == 2

    def test_update_kwargs(self, index):
        index.update(a=1, b=2)
        assert index["a"] == 1
        assert index["b"] == 2

    def test_clear(self, index):
        index["a"] = 1
        index["b"] = 2
        index.clear()
        assert len(index) == 0

    def test_peekitem(self, index):
        index["a"] = 1
        index["b"] = 2
        key, value = index.peekitem()
        assert key in {"a", "b"}

    def test_iter(self, index):
        index["a"] = 1
        index["b"] = 2
        keys = list(index)
        assert set(keys) == {"a", "b"}

    def test_context_manager(self, tmp_path):
        from diskcache_rs.cache import Index

        d = tmp_path / "index_ctx"
        d.mkdir()
        with Index(directory=str(d)) as idx:
            idx["key"] = "value"
            assert idx["key"] == "value"

    def test_init_with_dict(self, tmp_path):
        from diskcache_rs.cache import Index

        d = tmp_path / "index_dict_init"
        d.mkdir()
        idx = Index({"a": 1, "b": 2}, directory=str(d))
        assert idx["a"] == 1
        assert idx["b"] == 2
        idx.close()
