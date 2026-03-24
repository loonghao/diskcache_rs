"""Tests for newly added python-diskcache compatibility APIs.

Covers:
- Constants: ENOVAL, UNKNOWN, DEFAULT_SETTINGS, EVICTION_POLICY
- Exceptions/warnings: Timeout, EmptyDirWarning, UnknownFileWarning
- Disk and JSONDisk serialization classes
- Recipes: Lock, RLock, BoundedSemaphore, Averager, barrier, throttle, memoize_stampede
"""

import os
import tempfile
import threading
import time

import pytest


@pytest.fixture
def cache_dir():
    """Create a temporary directory for cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def cache(cache_dir):
    """Create a Cache instance."""
    from diskcache_rs import Cache

    c = Cache(cache_dir)
    yield c
    c.close()


# ============================================================
# Constants tests
# ============================================================


class TestConstants:
    """Test module-level constants."""

    def test_enoval_is_importable(self):
        from diskcache_rs import ENOVAL

        assert ENOVAL is not None

    def test_enoval_repr(self):
        from diskcache_rs import ENOVAL

        assert repr(ENOVAL) == "ENOVAL"

    def test_enoval_is_singleton(self):
        from diskcache_rs import ENOVAL
        from diskcache_rs.constants import ENOVAL as ENOVAL2

        assert ENOVAL is ENOVAL2

    def test_enoval_is_tuple(self):
        from diskcache_rs import ENOVAL

        assert isinstance(ENOVAL, tuple)

    def test_unknown_is_importable(self):
        from diskcache_rs import UNKNOWN

        assert UNKNOWN is not None

    def test_unknown_repr(self):
        from diskcache_rs import UNKNOWN

        assert repr(UNKNOWN) == "UNKNOWN"

    def test_enoval_not_equal_unknown(self):
        from diskcache_rs import ENOVAL, UNKNOWN

        assert ENOVAL != UNKNOWN

    def test_default_settings_is_dict(self):
        from diskcache_rs import DEFAULT_SETTINGS

        assert isinstance(DEFAULT_SETTINGS, dict)

    def test_default_settings_keys(self):
        from diskcache_rs import DEFAULT_SETTINGS

        assert "size_limit" in DEFAULT_SETTINGS
        assert "eviction_policy" in DEFAULT_SETTINGS
        assert "statistics" in DEFAULT_SETTINGS
        assert "tag_index" in DEFAULT_SETTINGS

    def test_default_settings_size_limit(self):
        from diskcache_rs import DEFAULT_SETTINGS

        assert DEFAULT_SETTINGS["size_limit"] == 2**30  # 1GB

    def test_eviction_policy_is_dict(self):
        from diskcache_rs import EVICTION_POLICY

        assert isinstance(EVICTION_POLICY, dict)

    def test_eviction_policy_keys(self):
        from diskcache_rs import EVICTION_POLICY

        assert "none" in EVICTION_POLICY
        assert "least-recently-stored" in EVICTION_POLICY
        assert "least-recently-used" in EVICTION_POLICY
        assert "least-frequently-used" in EVICTION_POLICY


# ============================================================
# Exceptions and warnings tests
# ============================================================


class TestExceptionsAndWarnings:
    """Test Timeout, EmptyDirWarning, UnknownFileWarning."""

    def test_timeout_is_exception(self):
        from diskcache_rs import Timeout

        assert issubclass(Timeout, Exception)

    def test_timeout_can_be_raised(self):
        from diskcache_rs import Timeout

        with pytest.raises(Timeout):
            raise Timeout("operation timed out")

    def test_timeout_message(self):
        from diskcache_rs import Timeout

        try:
            raise Timeout("db timeout")
        except Timeout as exc:
            assert str(exc) == "db timeout"

    def test_empty_dir_warning(self):
        from diskcache_rs import EmptyDirWarning

        assert issubclass(EmptyDirWarning, UserWarning)

    def test_unknown_file_warning(self):
        from diskcache_rs import UnknownFileWarning

        assert issubclass(UnknownFileWarning, UserWarning)

    def test_warnings_can_be_issued(self):
        import warnings

        from diskcache_rs import EmptyDirWarning, UnknownFileWarning

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn("test", EmptyDirWarning)
            warnings.warn("test", UnknownFileWarning)
            assert len(w) == 2
            assert issubclass(w[0].category, EmptyDirWarning)
            assert issubclass(w[1].category, UnknownFileWarning)


# ============================================================
# Disk and JSONDisk tests
# ============================================================


class TestDisk:
    """Test Disk serialization class."""

    def test_disk_importable(self):
        from diskcache_rs import Disk

        assert Disk is not None

    def test_disk_init(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        assert d.directory is not None

    def test_disk_store_bytes(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        size, mode, filename, data = d.store(b"hello")
        assert size == 5
        assert isinstance(data, bytes)

    def test_disk_store_string(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        size, mode, filename, data = d.store("hello")
        assert size > 0

    def test_disk_store_int(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        size, mode, filename, value = d.store(42)
        assert value == 42

    def test_disk_store_and_fetch_roundtrip(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        original = {"key": "value", "num": 42}
        size, mode, filename, data = d.store(original)
        result = d.fetch(mode, filename, data)
        assert result == original

    def test_disk_put_and_get(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        key_data, raw = d.put("test_key")
        result = d.get(key_data, raw)
        assert result == "test_key"

    def test_disk_hash(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        h = d.hash("key")
        assert isinstance(h, int)

    def test_disk_repr(self, cache_dir):
        from diskcache_rs import Disk

        d = Disk(cache_dir)
        assert "Disk" in repr(d)


class TestJSONDisk:
    """Test JSONDisk serialization class."""

    def test_jsondisk_importable(self):
        from diskcache_rs import JSONDisk

        assert JSONDisk is not None

    def test_jsondisk_init(self, cache_dir):
        from diskcache_rs import JSONDisk

        d = JSONDisk(cache_dir)
        assert d.directory is not None

    def test_jsondisk_store_and_fetch_roundtrip(self, cache_dir):
        from diskcache_rs import JSONDisk

        d = JSONDisk(cache_dir)
        original = {"key": "value", "num": 42}
        size, mode, filename, data = d.store(original)
        result = d.fetch(mode, filename, data)
        assert result == original

    def test_jsondisk_put_and_get(self, cache_dir):
        from diskcache_rs import JSONDisk

        d = JSONDisk(cache_dir)
        key_data, raw = d.put("test_key")
        result = d.get(key_data, raw)
        assert result == "test_key"

    def test_jsondisk_is_disk_subclass(self):
        from diskcache_rs import Disk, JSONDisk

        assert issubclass(JSONDisk, Disk)

    def test_jsondisk_repr(self, cache_dir):
        from diskcache_rs import JSONDisk

        d = JSONDisk(cache_dir, compress_level=5)
        r = repr(d)
        assert "JSONDisk" in r
        assert "5" in r


# ============================================================
# Lock tests
# ============================================================


class TestLock:
    """Test Lock recipe."""

    def test_lock_importable(self):
        from diskcache_rs import Lock

        assert Lock is not None

    def test_lock_acquire_release(self, cache):
        from diskcache_rs import Lock

        lock = Lock(cache, "test-lock")
        lock.acquire()
        assert lock.locked()
        lock.release()
        assert not lock.locked()

    def test_lock_context_manager(self, cache):
        from diskcache_rs import Lock

        lock = Lock(cache, "test-lock")
        with lock:
            assert lock.locked()
        assert not lock.locked()

    def test_lock_blocks_second_acquire(self, cache):
        from diskcache_rs import Lock

        lock = Lock(cache, "test-lock")
        lock.acquire()

        acquired = threading.Event()

        def try_acquire():
            lock2 = Lock(cache, "test-lock")
            lock2.acquire()
            acquired.set()
            lock2.release()

        t = threading.Thread(target=try_acquire)
        t.start()
        # Give thread a moment
        time.sleep(0.05)
        assert not acquired.is_set()  # Should be blocked
        lock.release()
        t.join(timeout=2)
        assert acquired.is_set()


# ============================================================
# RLock tests
# ============================================================


class TestRLock:
    """Test RLock recipe."""

    def test_rlock_importable(self):
        from diskcache_rs import RLock

        assert RLock is not None

    def test_rlock_reentrant(self, cache):
        from diskcache_rs import RLock

        rlock = RLock(cache, "test-rlock")
        rlock.acquire()
        rlock.acquire()  # Should not block
        rlock.release()
        rlock.release()

    def test_rlock_context_manager(self, cache):
        from diskcache_rs import RLock

        rlock = RLock(cache, "test-rlock")
        rlock.acquire()
        with rlock:  # Reentrant
            pass
        rlock.release()

    def test_rlock_release_unacquired(self, cache):
        from diskcache_rs import RLock

        rlock = RLock(cache, "test-rlock-release")
        with pytest.raises(AssertionError, match="cannot release"):
            rlock.release()


# ============================================================
# BoundedSemaphore tests
# ============================================================


class TestBoundedSemaphore:
    """Test BoundedSemaphore recipe."""

    def test_semaphore_importable(self):
        from diskcache_rs import BoundedSemaphore

        assert BoundedSemaphore is not None

    def test_semaphore_acquire_release(self, cache):
        from diskcache_rs import BoundedSemaphore

        sem = BoundedSemaphore(cache, "test-sem", value=2)
        sem.acquire()
        sem.acquire()
        sem.release()
        sem.release()

    def test_semaphore_context_manager(self, cache):
        from diskcache_rs import BoundedSemaphore

        sem = BoundedSemaphore(cache, "test-sem", value=1)
        with sem:
            pass  # Should not block

    def test_semaphore_release_unacquired(self, cache):
        from diskcache_rs import BoundedSemaphore

        sem = BoundedSemaphore(cache, "test-sem-release", value=1)
        with pytest.raises(AssertionError, match="cannot release"):
            sem.release()


# ============================================================
# Averager tests
# ============================================================


class TestAverager:
    """Test Averager recipe."""

    def test_averager_importable(self):
        from diskcache_rs import Averager

        assert Averager is not None

    def test_averager_basic(self, cache):
        from diskcache_rs import Averager

        ave = Averager(cache, "test-avg")
        ave.add(0.080)
        ave.add(0.120)
        result = ave.get()
        assert result is not None
        assert abs(result - 0.1) < 1e-9

    def test_averager_empty(self, cache):
        from diskcache_rs import Averager

        ave = Averager(cache, "test-avg-empty")
        assert ave.get() is None

    def test_averager_pop(self, cache):
        from diskcache_rs import Averager

        ave = Averager(cache, "test-avg-pop")
        ave.add(0.080)
        ave.add(0.120)
        ave.add(0.160)
        result = ave.pop()
        assert result is not None
        assert abs(result - 0.12) < 1e-9
        assert ave.get() is None  # Key was deleted


# ============================================================
# throttle decorator tests
# ============================================================


class TestThrottle:
    """Test throttle decorator recipe."""

    def test_throttle_importable(self):
        from diskcache_rs import throttle

        assert throttle is not None

    def test_throttle_basic(self, cache):
        from diskcache_rs import throttle

        call_count = 0

        @throttle(cache, 10, 1)  # 10 calls per second
        def increment():
            nonlocal call_count
            call_count += 1

        # Call a few times
        for _ in range(3):
            increment()

        assert call_count == 3


# ============================================================
# barrier decorator tests
# ============================================================


class TestBarrier:
    """Test barrier decorator recipe."""

    def test_barrier_importable(self):
        from diskcache_rs import barrier

        assert barrier is not None

    def test_barrier_basic(self, cache):
        from diskcache_rs import Lock, barrier

        results = []

        @barrier(cache, Lock)
        def work(n):
            results.append(n)
            return n

        assert work(1) == 1
        assert work(2) == 2
        assert results == [1, 2]


# ============================================================
# memoize_stampede decorator tests
# ============================================================


class TestMemoizeStampede:
    """Test memoize_stampede decorator recipe."""

    def test_memoize_stampede_importable(self):
        from diskcache_rs import memoize_stampede

        assert memoize_stampede is not None

    def test_memoize_stampede_basic(self, cache):
        from diskcache_rs import memoize_stampede

        call_count = 0

        @memoize_stampede(cache, expire=60)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(5) == 10
        assert call_count == 1
        assert compute(5) == 10
        assert call_count == 1  # Cached

    def test_memoize_stampede_has_cache_key(self, cache):
        from diskcache_rs import memoize_stampede

        @memoize_stampede(cache, expire=60)
        def func(x):
            return x

        assert hasattr(func, "__cache_key__")
        key = func.__cache_key__(42)
        assert isinstance(key, tuple)


# ============================================================
# Full import compatibility tests
# ============================================================


class TestFullImportCompatibility:
    """Test that all python-diskcache exports are importable from diskcache_rs."""

    def test_all_core_exports(self):
        from diskcache_rs import (
            ENOVAL,
            EVICTION_POLICY,
            UNKNOWN,
            Cache,
            Deque,
            Disk,
            FanoutCache,
            Index,
            JSONDisk,
        )

    def test_all_recipe_exports(self):
        from diskcache_rs import (
            Averager,
            BoundedSemaphore,
            Lock,
            RLock,
            barrier,
            memoize_stampede,
            throttle,
        )

    def test_all_exception_exports(self):
        from diskcache_rs import (
            EmptyDirWarning,
            Timeout,
            UnknownFileWarning,
        )

    def test_all_constant_exports(self):
        from diskcache_rs import DEFAULT_SETTINGS, ENOVAL, EVICTION_POLICY, UNKNOWN

    def test_all_in_module_all(self):
        import diskcache_rs

        all_exports = diskcache_rs.__all__

        # python-diskcache core exports
        expected = [
            "Cache",
            "FanoutCache",
            "Deque",
            "Index",
            "Disk",
            "JSONDisk",
            "ENOVAL",
            "UNKNOWN",
            "DEFAULT_SETTINGS",
            "EVICTION_POLICY",
            "Timeout",
            "EmptyDirWarning",
            "UnknownFileWarning",
            "Lock",
            "RLock",
            "BoundedSemaphore",
            "Averager",
            "barrier",
            "memoize_stampede",
            "throttle",
        ]

        for name in expected:
            assert name in all_exports, f"{name} missing from __all__"


# ============================================================
# Recipes utility function tests
# ============================================================


class TestRecipeUtilities:
    """Test full_name and args_to_key helper functions."""

    def test_full_name(self):
        from diskcache_rs.recipes import full_name

        def my_func():
            pass

        name = full_name(my_func)
        assert "my_func" in name

    def test_args_to_key_basic(self):
        from diskcache_rs.recipes import args_to_key

        key = args_to_key(("func",), (1, 2), {"a": 3}, False)
        assert key == ("func", 1, 2, "a", 3)

    def test_args_to_key_typed(self):
        from diskcache_rs.recipes import args_to_key

        key = args_to_key(("func",), (1,), {}, True)
        assert key == ("func", 1, int)

    def test_args_to_key_empty(self):
        from diskcache_rs.recipes import args_to_key

        key = args_to_key(("func",), (), {}, False)
        assert key == ("func",)
