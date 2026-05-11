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
