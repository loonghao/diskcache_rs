"""Disk serialization classes for diskcache_rs.

Compatible with python-diskcache's ``Disk`` and ``JSONDisk`` classes from
``diskcache.core``.

In python-diskcache, these classes handle the serialization and
deserialization of cache keys and values to/from SQLite and the filesystem.
In diskcache_rs, the Rust backend handles storage directly, so these classes
provide a compatible interface primarily for code that references
``diskcache.Disk`` or ``diskcache.JSONDisk`` directly.
"""

import io
import json
import os
import pickle
import zlib
from pathlib import Path
from typing import Any, Optional, Tuple, Union

from .constants import UNKNOWN


# Mode constants matching python-diskcache
MODE_NONE = 0
MODE_RAW = 1
MODE_BINARY = 2
MODE_TEXT = 3
MODE_PICKLE = 4


class Disk:
    """Cache key and value serialization for SQLite database and target directory.

    Provides methods to convert Python objects to/from the storage format
    used by the cache backend. This is a compatibility layer — in diskcache_rs,
    the Rust backend handles storage directly.

    :param str directory: directory path for cache files
    :param int min_file_size: minimum size for file-based storage
    :param int pickle_protocol: pickle protocol version
    """

    def __init__(
        self,
        directory,
        min_file_size=0,
        pickle_protocol=pickle.HIGHEST_PROTOCOL,
    ):
        self._directory = Path(directory) if directory else Path(".")
        self._min_file_size = min_file_size
        self._pickle_protocol = pickle_protocol

    @property
    def directory(self):
        """Cache directory path."""
        return self._directory

    def hash(self, key):
        """Return hash of *key* for use in filename.

        :param key: key to hash
        :return: hash value
        """
        return hash(key)

    def put(self, key):
        """Convert *key* to fields ``(key, raw)`` for SQLite database.

        :param key: key to convert
        :return: tuple of ``(key_bytes, raw_flag)``
        """
        if isinstance(key, bytes):
            return key, True
        return pickle.dumps(key, self._pickle_protocol), False

    def get(self, key, raw):
        """Convert fields ``(key, raw)`` from SQLite to key.

        :param key: database key
        :param bool raw: True if key is raw bytes
        :return: Python key object
        """
        if raw:
            return key
        return pickle.loads(key)

    def store(self, value, read=False, key=UNKNOWN):
        """Convert *value* to fields ``(size, mode, filename, db_value)``
        for SQLite database.

        :param value: value to convert
        :param bool read: True if value is file-like object
        :param key: associated key (optional)
        :return: tuple of ``(size, mode, filename, db_value)``
        """
        if isinstance(value, bytes):
            if len(value) < self._min_file_size:
                return len(value), MODE_RAW, None, value
            # For large values, would write to file in original diskcache
            return len(value), MODE_RAW, None, value

        if isinstance(value, str):
            data = value.encode("utf-8")
            return len(data), MODE_TEXT, None, data

        if isinstance(value, int) and not isinstance(value, bool):
            return 0, MODE_NONE, None, value

        if isinstance(value, float):
            return 0, MODE_NONE, None, value

        if read and hasattr(value, "read"):
            data = value.read()
            return len(data), MODE_BINARY, None, data

        # Default: pickle the value
        data = pickle.dumps(value, self._pickle_protocol)
        return len(data), MODE_PICKLE, None, data

    def fetch(self, mode, filename, value, read=False):
        """Convert fields ``(mode, filename, value)`` from SQLite to value.

        :param int mode: storage mode
        :param str filename: filename (if stored on disk)
        :param value: database value
        :param bool read: True to return file-like object
        :return: Python value
        """
        if mode == MODE_RAW:
            data = bytes(value) if not isinstance(value, bytes) else value
            if read:
                return io.BytesIO(data)
            return data

        if mode == MODE_BINARY:
            if read:
                return io.BytesIO(value)
            return value

        if mode == MODE_TEXT:
            if isinstance(value, bytes):
                return value.decode("utf-8")
            return str(value)

        if mode == MODE_PICKLE:
            if isinstance(value, bytes):
                return pickle.loads(value)
            return value

        # MODE_NONE — value is stored directly
        return value

    def filename(self, key=UNKNOWN, value=UNKNOWN):
        """Return filename and full_path pair for file storage.

        :param key: associated key
        :param value: associated value
        :return: tuple of ``(filename, full_path)``
        """
        hex_name = "%016x" % abs(hash((key, value)))
        sub_dir = hex_name[:2]
        name = hex_name[2:] + ".val"
        directory = self._directory / sub_dir
        directory.mkdir(parents=True, exist_ok=True)
        full_path = str(directory / name)
        filename = os.path.join(sub_dir, name)
        return filename, full_path

    def remove(self, filename):
        """Remove file at *filename* from directory.

        :param str filename: relative filename to remove
        """
        full_path = self._directory / filename
        try:
            full_path.unlink()
        except FileNotFoundError:
            pass

    def __repr__(self):
        return "Disk(directory={!r})".format(str(self._directory))


class JSONDisk(Disk):
    """Cache key and value serialization using JSON with optional compression.

    Inherits from :class:`Disk` and overrides serialization to use JSON
    format with optional zlib compression. Useful when cache values need to be
    human-readable or interoperable with non-Python systems.

    :param str directory: directory path for cache files
    :param int compress_level: zlib compression level (0-9, default 1)
    :param kwargs: additional arguments passed to :class:`Disk`
    """

    def __init__(self, directory, compress_level=1, **kwargs):
        self._compress_level = compress_level
        super().__init__(directory, **kwargs)

    def put(self, key):
        """Convert *key* to fields ``(key, raw)`` using JSON serialization.

        :param key: key to convert
        :return: tuple of ``(key_bytes, raw_flag)``
        """
        data = json.dumps(key).encode("utf-8")
        return zlib.compress(data, self._compress_level), True

    def get(self, key, raw):
        """Convert fields ``(key, raw)`` from JSON to key.

        :param key: database key (compressed JSON bytes)
        :param bool raw: True if key is raw bytes
        :return: Python key object
        """
        data = zlib.decompress(key)
        return json.loads(data.decode("utf-8"))

    def store(self, value, read=False, key=UNKNOWN):
        """Convert *value* to fields using JSON serialization.

        :param value: value to convert
        :param bool read: True if value is file-like object
        :param key: associated key (optional)
        :return: tuple of ``(size, mode, filename, db_value)``
        """
        if read and hasattr(value, "read"):
            value = value.read()
            if isinstance(value, bytes):
                value = value.decode("utf-8")

        data = json.dumps(value).encode("utf-8")
        compressed = zlib.compress(data, self._compress_level)
        return len(compressed), MODE_RAW, None, compressed

    def fetch(self, mode, filename, value, read=False):
        """Convert fields from JSON storage to value.

        :param int mode: storage mode
        :param str filename: filename (if stored on disk)
        :param value: database value (compressed JSON bytes)
        :param bool read: True to return file-like object
        :return: Python value
        """
        data = zlib.decompress(value)
        return json.loads(data.decode("utf-8"))

    def __repr__(self):
        return "JSONDisk(directory={!r}, compress_level={})".format(
            str(self._directory), self._compress_level
        )
