"""Regression coverage for NFS-safe SQLite settings inspired by python-diskcache issue #345."""

import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def test_use_file_locking_uses_sqlite_rollback_journal():
    from diskcache_rs import Cache

    path = Path(tempfile.mkdtemp(prefix="diskcache-rs-issue-345-"))
    cache = Cache(str(path), use_file_locking=True)
    try:
        assert cache.set("key", b"value")
    finally:
        cache.close()

    conn = sqlite3.connect(path / "index.sqlite3")
    try:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()

    assert journal_mode.lower() == "delete"
    assert not (path / "index.sqlite3-wal").exists()
    assert not (path / "index.sqlite3-shm").exists()


def test_use_file_locking_multi_process_open_still_works():
    from diskcache_rs import Cache

    path = tempfile.mkdtemp(prefix="diskcache-rs-issue-345-mp-")
    cache = Cache(path, use_file_locking=True)
    try:
        assert cache.set("key", b"value")

        code = """
import sys
from diskcache_rs import Cache
cache = Cache(sys.argv[1], use_file_locking=True)
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
        assert result.stdout.strip() == "b'value'"
    finally:
        cache.close()
