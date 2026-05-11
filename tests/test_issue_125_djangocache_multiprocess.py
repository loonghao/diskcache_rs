"""Regression tests for issue #125."""

import subprocess
import sys
import tempfile


def test_djangocache_is_exported():
    import diskcache_rs

    assert hasattr(diskcache_rs, "DjangoCache")
    assert diskcache_rs.DjangoCache is not None


def test_fanout_cache_can_be_opened_by_multiple_processes():
    from diskcache_rs import FanoutCache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-125-")
    cache = FanoutCache(path, shards=1)
    try:
        assert cache.set("key", "value")

        code = """
import sys
from diskcache_rs import FanoutCache
cache = FanoutCache(sys.argv[1], shards=1)
try:
    print(cache.get("key"))
finally:
    cache.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert result.stdout.strip() == "value"
    finally:
        cache.close()


def test_cache_can_be_opened_by_multiple_processes():
    from diskcache_rs import Cache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-125-cache-")
    cache = Cache(path)
    try:
        assert cache.set("key", "value")

        code = """
import sys
from diskcache_rs import Cache
cache = Cache(sys.argv[1])
try:
    print(cache.get("key"))
finally:
    cache.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert result.stdout.strip() == "value"
    finally:
        cache.close()


def test_large_value_is_visible_to_other_process_after_set_returns():
    from diskcache_rs import Cache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-125-large-")
    cache = Cache(path)
    try:
        assert cache.set("key", b"x" * 4096)

        code = """
import sys
from diskcache_rs import Cache
cache = Cache(sys.argv[1])
try:
    value = cache.get("key")
    print(len(value) if value is not None else None)
finally:
    cache.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert result.stdout.strip() == "4096"
    finally:
        cache.close()


def test_cache_observes_other_process_overwrite():
    from diskcache_rs import Cache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-125-overwrite-")
    cache = Cache(path)
    try:
        assert cache.set("key", b"old")
        assert cache.get("key") == b"old"

        code = """
import sys
from diskcache_rs import Cache
cache = Cache(sys.argv[1])
try:
    assert cache.set("key", b"new")
finally:
    cache.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert cache.get("key") == b"new"
    finally:
        cache.close()


def test_cache_observes_other_process_delete():
    from diskcache_rs import Cache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-125-delete-")
    cache = Cache(path)
    try:
        assert cache.set("key", b"value")
        assert cache.get("key") == b"value"

        code = """
import sys
from diskcache_rs import Cache
cache = Cache(sys.argv[1])
try:
    assert cache.delete("key")
finally:
    cache.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", code, path],
            text=True,
            capture_output=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert cache.get("key") is None
    finally:
        cache.close()
