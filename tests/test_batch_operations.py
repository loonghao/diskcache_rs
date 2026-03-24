"""
Tests for batched cache writes and overwrite persistence behavior.
"""

import shutil
import tempfile
from pathlib import Path

from diskcache_rs import Cache


class TestBatchOperations:
    """Tests for batched write behavior."""

    def test_set_many_round_trip(self, temp_cache_dir):
        """`set_many()` should store and return multiple values correctly."""
        cache = Cache(temp_cache_dir)

        stored = cache.set_many(
            {
                "alpha": "one",
                "beta": {"nested": 2},
                "gamma": b"bytes-value",
            }
        )

        assert stored == 3
        assert cache.get("alpha") == "one"
        assert cache.get("beta") == {"nested": 2}
        assert cache.get("gamma") == b"bytes-value"

    def test_set_many_tracks_expire_and_tag(self, temp_cache_dir):
        """`set_many()` should keep expire and tag metadata consistent."""
        cache = Cache(temp_cache_dir)

        stored = cache.set_many(
            [("key1", "value1"), ("key2", "value2")],
            expire=60,
            tag="batch",
        )

        assert stored == 2

        value, expire_time, tag = cache.get("key1", expire_time=True, tag=True)
        assert value == "value1"
        assert expire_time is not None
        assert tag == "batch"

    def test_set_many_restores_memory_only_entries_after_reopen(self):
        """Memory-only batch entries should still participate in `len`, `in`, and `get` after reopen."""
        with tempfile.TemporaryDirectory(prefix="diskcache_rs_batch_reopen_") as cache_dir:
            cache = Cache(cache_dir, disk_write_threshold=4096)
            stored = cache.set_many(
                {
                    "alpha": b"a" * 64,
                    "beta": b"b" * 96,
                    "gamma": b"c" * 128,
                }
            )
            assert stored == 3
            assert cache.stats()["count"] == 3
            cache.close()

            reopened = Cache(cache_dir, disk_write_threshold=4096)
            try:
                assert len(reopened) == 3
                assert "alpha" in reopened
                assert reopened.get("alpha") == b"a" * 64
                assert reopened.get("beta") == b"b" * 96
                assert reopened.get("gamma") == b"c" * 128
            finally:
                reopened.close()


    def test_overwrite_large_value_with_small_value_removes_stale_disk_file(self):
        """Overwriting a disk-backed value with a memory-backed value should not leave stale files."""
        with tempfile.TemporaryDirectory(prefix="diskcache_rs_overwrite_") as cache_dir:
            cache = Cache(cache_dir)
            large_value = b"a" * 4096
            small_value = b"b" * 128

            cache.set("same-key", large_value)
            cache.vacuum()

            data_dir = Path(cache_dir) / "data"
            assert len(list(data_dir.glob("*.dat"))) == 1

            cache.set("same-key", small_value)
            cache.close()

            assert list(data_dir.glob("*.dat")) == []

            reopened = Cache(cache_dir)
            try:
                assert reopened.get("same-key") == small_value
            finally:
                reopened.close()

    def test_set_many_overwrite_removes_stale_disk_file(self):
        """Batch overwrite should clean up old disk files when the new value stays in memory."""
        with tempfile.TemporaryDirectory(prefix="diskcache_rs_batch_overwrite_") as cache_dir:
            cache = Cache(cache_dir)
            cache.set("same-key", b"a" * 4096)
            cache.vacuum()

            data_dir = Path(cache_dir) / "data"
            assert len(list(data_dir.glob("*.dat"))) == 1

            stored = cache.set_many({"same-key": b"b" * 128})
            assert stored == 1
            cache.close()

            assert list(data_dir.glob("*.dat")) == []

            reopened = Cache(cache_dir)
            try:
                assert reopened.get("same-key") == b"b" * 128
            finally:
                reopened.close()

    def test_overwrite_keeps_stats_count_stable(self, temp_cache_dir):
        """Overwriting existing keys should not inflate the tracked entry count."""
        cache = Cache(temp_cache_dir)

        cache.set("same-key", "first")
        assert cache.stats()["count"] == 1

        cache.set("same-key", "second")
        assert cache.stats()["count"] == 1
        assert len(cache) == 1

        stored = cache.set_many({"same-key": "third", "other-key": "value"})
        assert stored == 2
        assert cache.get("same-key") == "third"
        assert cache.get("other-key") == "value"
        assert cache.stats()["count"] == 2
        assert len(cache) == 2

    def test_close_releases_background_writer_handles(self):

        """Closing the cache should allow the directory to be deleted immediately on Windows."""
        cache_dir = Path(tempfile.mkdtemp(prefix="diskcache_rs_cleanup_"))

        cache = Cache(str(cache_dir), disk_write_threshold=0)
        for index in range(20):
            cache.set(f"key-{index}", b"x" * 4096)
        cache.close()

        shutil.rmtree(cache_dir)
        assert not cache_dir.exists()
