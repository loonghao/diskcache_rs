"""Constants, exceptions, and warnings for diskcache_rs.

Compatible with python-diskcache's constants and exception classes from
``diskcache.core``.
"""

import pickle


class _Constant(tuple):
    """Pretty display of immutable constant."""

    def __new__(cls, name):
        return tuple.__new__(cls, (name,))

    def __repr__(self):
        return "%s" % self[0]


ENOVAL = _Constant("ENOVAL")
"""Sentinel object for cache evaluation (cache miss indicator).

Used as the default value for :meth:`Cache.get` to distinguish between
a cache miss and a cached ``None`` value.
"""

UNKNOWN = _Constant("UNKNOWN")
"""Sentinel object for unknown values.

Used internally as a placeholder when the actual key or value is not yet
known.
"""


DEFAULT_SETTINGS = {
    "statistics": 0,  # False
    "tag_index": 0,  # False
    "eviction_policy": "least-recently-stored",
    "size_limit": 2**30,  # 1gb
    "cull_limit": 10,
    "sqlite_auto_vacuum": 1,  # FULL
    "sqlite_cache_size": 2**13,  # 8,192 pages
    "sqlite_journal_mode": "wal",
    "sqlite_mmap_size": 2**26,  # 64mb
    "sqlite_synchronous": 1,  # NORMAL
    "disk_min_file_size": 2**15,  # 32kb
    "disk_pickle_protocol": pickle.HIGHEST_PROTOCOL,
}
"""Default settings for Cache instances.

These mirror the default settings in python-diskcache. Note that
diskcache_rs uses a Rust backend instead of SQLite, so SQLite-specific
settings are accepted for compatibility but may not affect behavior.
"""


EVICTION_POLICY = {
    "none": {
        "init": None,
        "get": None,
        "cull": None,
    },
    "least-recently-stored": {
        "init": None,
        "get": None,
        "cull": "SELECT {fields} FROM Cache ORDER BY rowid LIMIT ?",
    },
    "least-recently-used": {
        "init": (
            "CREATE INDEX IF NOT EXISTS Cache_access_time ON"
            " Cache (access_time)"
        ),
        "get": "UPDATE Cache SET access_time = {now} WHERE rowid = {rowid}",
        "cull": (
            "SELECT {fields} FROM Cache ORDER BY access_time LIMIT ?"
        ),
    },
    "least-frequently-used": {
        "init": (
            "CREATE INDEX IF NOT EXISTS Cache_access_count ON"
            " Cache (access_count)"
        ),
        "get": (
            "UPDATE Cache SET access_count = access_count + 1"
            " WHERE rowid = {rowid}"
        ),
        "cull": (
            "SELECT {fields} FROM Cache ORDER BY access_count LIMIT ?"
        ),
    },
}
"""Eviction policy definitions.

These mirror the eviction policy SQL definitions in python-diskcache.
In diskcache_rs, eviction is handled by the Rust backend, so the SQL
statements are provided for compatibility and documentation only.
"""


class Timeout(Exception):
    """Database timeout expired.

    Raised when a cache operation exceeds the configured timeout.
    Compatible with ``diskcache.Timeout``.
    """

    pass


class EmptyDirWarning(UserWarning):
    """Warning used by :meth:`Cache.check` for empty directories.

    Compatible with ``diskcache.EmptyDirWarning``.
    """

    pass


class UnknownFileWarning(UserWarning):
    """Warning used by :meth:`Cache.check` for unknown files.

    Compatible with ``diskcache.UnknownFileWarning``.
    """

    pass
