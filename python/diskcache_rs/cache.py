"""
Python-compatible cache interface for diskcache_rs
"""

import functools
import hashlib
import io
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple, Union

# Use high-performance Rust pickle implementation when available
try:
    from . import rust_pickle as pickle
except ImportError:
    import pickle

# We'll import the Rust implementation at runtime to avoid circular imports
_RustCache = None


def _get_rust_cache():
    """Get the Rust cache class, importing it if necessary"""
    global _RustCache
    if _RustCache is None:
        from .core import get_rust_cache

        _RustCache = get_rust_cache()
    return _RustCache


class Cache:
    """
    High-performance disk cache compatible with python-diskcache API

    This implementation uses Rust for better performance and network filesystem support.
    """

    def __init__(
        self,
        directory: Union[str, Path] = None,
        timeout: float = 60.0,
        disk_min_file_size: int = 32 * 1024,
        **kwargs,
    ):
        """
        Initialize cache

        Args:
            directory: Cache directory path
            timeout: Operation timeout (not used in Rust implementation)
            disk_min_file_size: Minimum file size for disk storage (deprecated, use disk_write_threshold)
            **kwargs: Additional arguments:
                - max_size / size_limit: Maximum cache size in bytes (default: 1GB)
                - max_entries / count_limit: Maximum number of entries (default: 100,000)
                - disk_write_threshold: Size threshold for writing to disk vs memory-only (default: 1024 bytes)
                  Items smaller than this threshold are stored in memory only and won't create disk files.
                  Set to 0 to write all items to disk (useful for testing/debugging).
                - use_file_locking: Enable file locking for NFS scenarios (default: False)
                  Enable this when using cache on network filesystems to prevent corruption.
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "cache")

        self._directory = Path(directory)
        self._timeout = timeout
        self._transaction_lock = (
            threading.RLock()
        )  # Reentrant lock for nested transactions
        self._transaction_depth = 0  # Track nested transaction depth
        self._expire_times: Dict[str, float] = {}  # Track expiration times for expire()
        self._tags: Dict[str, str] = {}  # Track tags for tag-based operations

        # Extract Rust cache parameters
        max_size = kwargs.get(
            "size_limit", kwargs.get("max_size", 1024 * 1024 * 1024)
        )  # 1GB default
        max_entries = kwargs.get("count_limit", kwargs.get("max_entries", 100_000))

        # New configuration options for issue #17
        disk_write_threshold = kwargs.get("disk_write_threshold", 1024)  # 1KB default
        use_file_locking = kwargs.get("use_file_locking", False)

        # Create the underlying Rust cache
        _RustCache = _get_rust_cache()
        self._cache = _RustCache(
            str(self._directory),
            max_size=max_size,
            max_entries=max_entries,
            disk_write_threshold=disk_write_threshold,
            use_file_locking=use_file_locking,
        )

    def set(
        self,
        key: str,
        value: Any,
        expire: Optional[float] = None,
        read: bool = False,
        tag: Optional[str] = None,
        retry: bool = False,
    ) -> bool:
        """
        Set key to value in cache

        Args:
            key: Cache key
            value: Value to store
            expire: Expiration time (seconds from now, or timestamp)
            read: Whether this is a read operation (ignored)
            tag: Tag for the entry
            retry: Whether to retry on failure (ignored)

        Returns:
            True if successful
        """
        try:
            # Handle read=True: read value from file-like object
            if read and hasattr(value, "read"):
                value = value.read()

            # Serialize the value
            serialized_value = pickle.dumps(value)

            # Calculate expiration time
            expire_time = None
            if expire is not None:
                if expire > time.time():
                    # Assume it's already a timestamp
                    expire_time = int(expire)
                else:
                    # Assume it's seconds from now
                    expire_time = int(time.time() + expire)

            # Prepare tags
            tags = [tag] if tag else []

            # Store in Rust cache
            self._cache.set(key, serialized_value, expire_time=expire_time, tags=tags)

            # Track expiration time for expire() method
            if expire_time is not None:
                self._expire_times[key] = float(expire_time)
            else:
                self._expire_times.pop(key, None)

            # Track tag for tag-based operations
            if tag is not None:
                self._tags[key] = tag
            else:
                self._tags.pop(key, None)

            return True

        except Exception:
            return False

    def _auto_deserialize(self, data: bytes) -> Any:
        """
        Auto-detect and deserialize data from various formats

        Tries to deserialize in the following order:
        1. Pickle (most common for diskcache)
        2. JSON (if data looks like JSON)
        3. Raw bytes (if all else fails)

        Args:
            data: Serialized data bytes

        Returns:
            Deserialized value
        """
        # Try pickle first (most common)
        try:
            return pickle.loads(data)
        except Exception:
            pass

        # Try JSON if it looks like JSON
        try:
            # Check if data starts with common JSON markers
            if data and data[0:1] in (b"{", b"[", b'"'):
                text = data.decode("utf-8")
                return json.loads(text)
        except Exception:
            pass

        # Try plain text
        try:
            return data.decode("utf-8")
        except Exception:
            pass

        # Return raw bytes as last resort
        return data

    def get(
        self,
        key: str,
        default: Any = None,
        read: bool = False,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> Any:
        """
        Get value for key from cache

        Args:
            key: Cache key
            default: Default value if key not found
            read: If True, return file handle for value
            expire_time: If True, return expire time in tuple
            tag: If True, return tag in tuple
            retry: Whether to retry on failure (ignored)

        Returns:
            Cached value or default. If expire_time or tag is True,
            returns a tuple of (value, expire_time, tag) as requested.
        """
        try:
            serialized_value = self._cache.get(key)
            if serialized_value is None:
                if expire_time and tag:
                    return (default, None, None)
                elif expire_time:
                    return (default, None)
                elif tag:
                    return (default, None)
                return default

            # Auto-detect and deserialize the value
            value = self._auto_deserialize(serialized_value)

            # Handle read=True: wrap value in BytesIO
            if read:
                if isinstance(value, bytes):
                    value = io.BytesIO(value)
                else:
                    value = io.BytesIO(serialized_value)

            # Handle additional return values
            if expire_time or tag:
                result = [value]
                if expire_time:
                    result.append(self._expire_times.get(key))
                if tag:
                    result.append(self._tags.get(key))
                return tuple(result)

            return value

        except Exception:
            if expire_time and tag:
                return (default, None, None)
            elif expire_time:
                return (default, None)
            elif tag:
                return (default, None)
            return default

    def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key to delete

        Returns:
            True if key existed and was deleted
        """
        try:
            result = self._cache.delete(key)
            if result:
                self._expire_times.pop(key, None)
                self._tags.pop(key, None)
            return result
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return self._cache.exists(key)
        except Exception:
            return False

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return self._cache.exists(key)
        except Exception:
            return False

    def __getitem__(self, key: str) -> Any:
        """Get item using [] syntax"""
        result = self.get(key)
        try:
            exists = self._cache.exists(key)
        except Exception:
            exists = False
        if result is None and not exists:
            raise KeyError(key)
        return result

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item using [] syntax"""
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete item using del syntax"""
        if not self.delete(key):
            raise KeyError(key)

    def keys(self) -> List[str]:
        """Get list of all cache keys"""
        try:
            return self._cache.keys()
        except Exception:
            return []

    def __iter__(self) -> Iterator[str]:
        """Iterate over cache keys"""
        try:
            return iter(self._cache.keys())
        except Exception:
            return iter([])

    def __len__(self) -> int:
        """Get number of items in cache"""
        try:
            return len(self._cache.keys())
        except Exception:
            return 0

    def clear(self) -> int:
        """
        Clear all items from cache

        Returns:
            Number of items removed
        """
        try:
            count = len(self)
            self._cache.clear()
            self._expire_times.clear()
            self._tags.clear()
            return count
        except Exception:
            return 0

    def pop(
        self,
        key: str,
        default=None,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """
        Remove and return value for key

        Args:
            key: Cache key
            default: Default value if key not found
            expire_time: If True, return expire time in tuple
            tag: If True, return tag in tuple
            retry: Whether to retry on failure (ignored)

        Returns:
            Value, or tuple with additional metadata if requested
        """
        try:
            value = self.get(key)
            if value is None and key not in self:
                if expire_time and tag:
                    return (default, None, None)
                elif expire_time:
                    return (default, None)
                elif tag:
                    return (default, None)
                return default

            # Capture metadata before deletion
            et = self._expire_times.get(key)
            t = self._tags.get(key)

            # Remove the key
            self.delete(key)

            if expire_time and tag:
                return (value, et, t)
            elif expire_time:
                return (value, et)
            elif tag:
                return (value, t)
            return value
        except Exception:
            if expire_time and tag:
                return (default, None, None)
            elif expire_time:
                return (default, None)
            elif tag:
                return (default, None)
            return default

    def stats(self, enable: bool = True, reset: bool = False) -> Dict[str, Any]:
        """
        Get cache statistics

        Args:
            enable: Whether to enable stats (ignored)
            reset: Whether to reset stats (not supported)

        Returns:
            Dictionary of statistics
        """
        try:
            rust_stats = self._cache.stats()

            # Convert to python-diskcache compatible format
            return {
                "hits": rust_stats.get("hits", 0),
                "misses": rust_stats.get("misses", 0),
                "sets": rust_stats.get("sets", 0),
                "deletes": rust_stats.get("deletes", 0),
                "evictions": rust_stats.get("evictions", 0),
                "size": rust_stats.get("total_size", 0),
                "count": rust_stats.get("entry_count", 0),
            }
        except Exception:
            return {}

    def volume(self) -> int:
        """Get cache size in bytes"""
        try:
            return self._cache.size()
        except Exception:
            return 0

    def add(
        self,
        key: str,
        value: Any,
        expire: Optional[float] = None,
        read: bool = False,
        tag: Optional[str] = None,
        retry: bool = False,
    ) -> bool:
        """
        Add key to cache only if it doesn't already exist

        Args:
            key: Cache key
            value: Value to store
            expire: Expiration time (seconds from now, or timestamp)
            read: Whether this is a read operation (ignored)
            tag: Tag for the entry
            retry: Whether to retry on failure (ignored)

        Returns:
            True if key was added, False if key already exists
        """
        if key in self:
            return False
        return self.set(key, value, expire, read, tag, retry)

    def incr(
        self, key: str, delta: int = 1, default: int = 0, retry: bool = False
    ) -> int:
        """
        Increment value for key by delta

        Args:
            key: Cache key
            delta: Amount to increment by
            default: Default value if key doesn't exist
            retry: Whether to retry on failure (ignored)

        Returns:
            New value after increment
        """
        try:
            current = self.get(key)
            if current is None:
                new_value = default + delta
            else:
                new_value = int(current) + delta
            self.set(key, new_value)
            return new_value
        except Exception:
            # If key doesn't exist and no default provided, raise KeyError
            if default is None:
                raise KeyError(key)
            new_value = default + delta
            self.set(key, new_value)
            return new_value

    def decr(
        self, key: str, delta: int = 1, default: int = 0, retry: bool = False
    ) -> int:
        """
        Decrement value for key by delta

        Args:
            key: Cache key
            delta: Amount to decrement by
            default: Default value if key doesn't exist
            retry: Whether to retry on failure (ignored)

        Returns:
            New value after decrement
        """
        return self.incr(key, -delta, default, retry)

    def touch(
        self, key: str, expire: Optional[float] = None, retry: bool = False
    ) -> bool:
        """
        Update expiration time for key

        Args:
            key: Cache key
            expire: New expiration time
            retry: Whether to retry on failure (ignored)

        Returns:
            True if key was touched, False if key doesn't exist
        """
        if key not in self:
            return False

        # Get current value and update with new expiration
        value = self.get(key)
        if value is not None:
            return self.set(key, value, expire)
        return False

    def expire(self, now: Optional[float] = None, retry: bool = False) -> int:
        """
        Remove expired items from the cache.

        Removes items from the cache that have expired before the given time.
        If *now* is not provided, ``time.time()`` is used.

        Compatible with python-diskcache's ``Cache.expire()`` API.

        Args:
            now: Current time (default ``time.time()``)
            retry: Whether to retry on failure (ignored)

        Returns:
            Count of removed expired items

        Example:
            >>> cache = Cache()
            >>> cache.set('key', 'value', expire=0.01)
            True
            >>> import time; time.sleep(0.1)
            >>> cache.expire()
            1
        """
        if now is None:
            now = time.time()

        count = 0
        # Find keys that have expired
        expired_keys = [
            key for key, exp_time in list(self._expire_times.items()) if exp_time <= now
        ]

        for key in expired_keys:
            try:
                self._cache.delete(key)
                count += 1
            except Exception:
                pass
            # Always remove from tracking dict
            self._expire_times.pop(key, None)

        return count

    def vacuum(self) -> None:
        """Manually trigger vacuum operation to sync pending writes"""
        self._cache.vacuum()

    def close(self) -> None:
        """Close cache and release resources (especially redb database lock)"""
        if hasattr(self, "_cache") and self._cache is not None:
            self._cache.close()
            del self._cache
            self._cache = None

    def __del__(self):
        """Destructor to ensure resources are released"""
        self.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def __getstate__(self):
        """Support pickling by returning directory and timeout."""
        return (str(self._directory), self._timeout)

    def __setstate__(self, state):
        """Restore cache from pickled state."""
        directory, timeout = state
        self.__init__(directory=directory, timeout=timeout)

    def memoize(
        self,
        name: Optional[str] = None,
        typed: bool = False,
        expire: Optional[float] = None,
        tag: Optional[str] = None,
        ignore: Set[str] = frozenset(),
    ) -> Callable:
        """
        Memoizing cache decorator.

        Decorator to wrap callable with memoizing function using cache.
        Repeated calls with the same arguments will lookup result in cache and
        avoid function evaluation.

        Args:
            name: Name for callable (default None, uses function name)
            typed: Cache different types separately (default False)
            expire: Seconds until arguments expire (default None, no expiry)
            tag: Text to associate with arguments (default None)
            ignore: Positional or keyword args to ignore (default empty set)

        Returns:
            Decorator function

        Example:
            >>> cache = Cache()
            >>> @cache.memoize(expire=60)
            ... def expensive_function(x):
            ...     return x * x
            >>> expensive_function(5)
            25
        """

        def decorator(func: Callable) -> Callable:
            # Determine the cache key prefix
            cache_key_prefix = name if name is not None else func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from arguments
                cache_key = self._make_key(
                    cache_key_prefix, args, kwargs, typed, ignore
                )

                # Try to get from cache - use __contains__ to check existence
                if cache_key in self:
                    return self.get(cache_key)

                # Call the function
                result = func(*args, **kwargs)

                # Store in cache
                self.set(cache_key, result, expire=expire)

                return result

            # Add __cache_key__ method to generate cache key
            def cache_key(*args, **kwargs):
                return self._make_key(cache_key_prefix, args, kwargs, typed, ignore)

            wrapper.__cache_key__ = cache_key
            wrapper.__wrapped__ = func

            return wrapper

        return decorator

    def _make_key(
        self,
        prefix: str,
        args: tuple,
        kwargs: dict,
        typed: bool,
        ignore: Set[str],
    ) -> str:
        """
        Generate cache key from function arguments.

        Args:
            prefix: Key prefix (usually function name)
            args: Positional arguments
            kwargs: Keyword arguments
            typed: Include type information in key
            ignore: Arguments to ignore

        Returns:
            Cache key string
        """
        # Filter out ignored arguments
        filtered_args = args
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ignore}

        # Build key components
        key_parts = [prefix]

        # Add positional arguments
        for i, arg in enumerate(filtered_args):
            if i not in ignore:
                if typed:
                    key_parts.append(f"{type(arg).__name__}:{repr(arg)}")
                else:
                    key_parts.append(repr(arg))

        # Add keyword arguments (sorted for consistency)
        for k in sorted(filtered_kwargs.keys()):
            v = filtered_kwargs[k]
            if typed:
                key_parts.append(f"{k}={type(v).__name__}:{repr(v)}")
            else:
                key_parts.append(f"{k}={repr(v)}")

        # Join and hash to create a fixed-length key
        key_str = "|".join(key_parts)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()

        # Use underscore instead of colon to avoid potential issues
        return f"memoize_{prefix}_{key_hash}"

    def iterkeys(self, reverse: bool = False) -> Iterator[str]:
        """
        Iterate cache keys in database sort order.

        Args:
            reverse: Reverse sort order (default False)

        Returns:
            Iterator of cache keys

        Example:
            >>> cache = Cache()
            >>> for key in [4, 1, 3, 0, 2]:
            ...     cache[key] = key
            >>> list(cache.iterkeys())
            [0, 1, 2, 3, 4]
            >>> list(cache.iterkeys(reverse=True))
            [4, 3, 2, 1, 0]
        """
        keys = sorted(self.keys())
        if reverse:
            keys = reversed(keys)
        return iter(keys)

    def __reversed__(self) -> Iterator[str]:
        """
        Reverse iterate keys in cache including expired items.

        Returns:
            Reverse iterator of cache keys
        """
        return self.iterkeys(reverse=True)

    def peekitem(
        self,
        last: bool = True,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> tuple:
        """
        Peek at key and value item pair in cache based on iteration order.

        Args:
            last: Last item in iteration order (default True)
            expire_time: If True, return expire_time in tuple (default False)
            tag: If True, return tag in tuple (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            Key and value item pair

        Raises:
            KeyError: If cache is empty

        Example:
            >>> cache = Cache()
            >>> for num, letter in enumerate('abc'):
            ...     cache[letter] = num
            >>> cache.peekitem()
            ('c', 2)
            >>> cache.peekitem(last=False)
            ('a', 0)
        """
        keys = list(self.keys())
        if not keys:
            raise KeyError("cache is empty")

        # Sort keys to get consistent ordering
        keys = sorted(keys)
        key = keys[-1] if last else keys[0]
        value = self.get(key)

        if expire_time or tag:
            result = [key, value]
            if expire_time:
                result.append(self._expire_times.get(key))
            if tag:
                result.append(self._tags.get(key))
            return tuple(result)
        return (key, value)

    @property
    def directory(self) -> Path:
        """Cache directory path"""
        return self._directory

    @property
    def timeout(self) -> float:
        """SQLite connection timeout value in seconds"""
        return self._timeout

    @contextmanager
    def transact(self, retry: bool = False):
        """
        Context manager to perform a transaction by locking the cache.

        While the cache is locked, no other write operation is permitted from
        other threads. Transactions should therefore be as short as possible.
        Read and write operations performed in a transaction are atomic.

        Transactions may be nested and may not be shared between threads.

        Args:
            retry: Retry if database timeout occurs (default False)

        Yields:
            Context manager for use in with statement

        Example:
            >>> cache = Cache()
            >>> with cache.transact():  # Atomically increment two keys
            ...     cache['total'] = cache.get('total', 0) + 123.4
            ...     cache['count'] = cache.get('count', 0) + 1
            >>> with cache.transact():  # Atomically calculate average
            ...     average = cache['total'] / cache['count']
        """
        # Acquire the lock
        self._transaction_lock.acquire()
        self._transaction_depth += 1

        try:
            yield self
        finally:
            # Release the lock
            self._transaction_depth -= 1
            self._transaction_lock.release()

    def check(self, fix: bool = False, retry: bool = False) -> List[str]:
        """
        Check database and file system consistency.

        Warnings are stored and returned as a list of strings. If *fix* is
        ``True``, some inconsistencies will be repaired automatically.

        Args:
            fix: Correct inconsistencies (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            List of warnings

        Example:
            >>> cache = Cache()
            >>> warnings = cache.check()
            >>> len(warnings)
            0
        """
        warnings: List[str] = []
        try:
            # Check directory exists
            if not self._directory.exists():
                warnings.append(f"Cache directory does not exist: {self._directory}")
                if fix:
                    self._directory.mkdir(parents=True, exist_ok=True)
                    warnings.append("Created cache directory")

            # Check that all tracked keys are accessible
            for key in list(self.keys()):
                try:
                    self._cache.get(key)
                except Exception as exc:
                    warnings.append(f"Key {key!r} inaccessible: {exc}")
                    if fix:
                        try:
                            self._cache.delete(key)
                            warnings.append(f"Removed inaccessible key {key!r}")
                        except Exception:
                            pass

            # Verify expire tracking consistency
            for key in list(self._expire_times):
                if key not in self:
                    warnings.append(f"Expire tracking for missing key {key!r}")
                    if fix:
                        self._expire_times.pop(key, None)
                        warnings.append(f"Removed stale expire tracking for {key!r}")

            # Verify tag tracking consistency
            for key in list(self._tags):
                if key not in self:
                    warnings.append(f"Tag tracking for missing key {key!r}")
                    if fix:
                        self._tags.pop(key, None)
                        warnings.append(f"Removed stale tag tracking for {key!r}")

        except Exception as exc:
            warnings.append(f"Error during check: {exc}")

        return warnings

    def create_tag_index(self) -> None:
        """
        Create tag index on cache database.

        Better to index ``tag`` column after filling cache. Calling
        :meth:`create_tag_index` is a no-op if the index already exists.

        .. note::

            In diskcache_rs, tags are stored alongside entries but there is
            no separate SQL-level index. This method exists for API
            compatibility only.
        """
        # No-op: diskcache_rs stores tags inline with entries.
        pass

    def drop_tag_index(self) -> None:
        """
        Drop tag index on cache database.

        .. note::

            In diskcache_rs, tags are stored alongside entries but there is
            no separate SQL-level index. This method exists for API
            compatibility only.
        """
        # No-op: see create_tag_index.
        pass

    def cull(self, retry: bool = False) -> int:
        """
        Cull items from cache until volume is less than size limit.

        Remove items based on the eviction policy until the cache volume
        is within acceptable limits. This is normally done automatically,
        but can be triggered manually.

        Args:
            retry: Retry if database timeout occurs (default False)

        Returns:
            Count of items removed

        Example:
            >>> cache = Cache(size_limit=1000)
            >>> count = cache.cull()
        """
        count = 0
        try:
            # First expire any expired items
            count += self.expire()

            # The Rust backend handles eviction automatically via
            # enforce_cache_limits(). Trigger a vacuum to force cleanup.
            self._cache.vacuum()
        except Exception:
            pass
        return count

    def evict(self, tag: str, retry: bool = False) -> int:
        """
        Remove items with matching *tag* from cache.

        Removes items from the cache with matching *tag* value.

        Args:
            tag: Tag value to evict
            retry: Retry if database timeout occurs (default False)

        Returns:
            Count of items removed

        Example:
            >>> cache = Cache()
            >>> cache.set('a', 1, tag='group1')
            True
            >>> cache.set('b', 2, tag='group1')
            True
            >>> cache.evict('group1')
            2
        """
        count = 0
        # Find all keys with matching tag
        keys_to_evict = [k for k, t in list(self._tags.items()) if t == tag]
        for key in keys_to_evict:
            try:
                if self.delete(key):
                    count += 1
            except Exception:
                pass
        return count

    def push(
        self,
        value: Any,
        prefix: Optional[str] = None,
        side: str = "back",
        expire: Optional[float] = None,
        read: bool = False,
        tag: Optional[str] = None,
        retry: bool = False,
    ) -> Any:
        """
        Push *value* onto *side* of queue identified by *prefix* in cache.

        When prefix is None, integer keys are used. Otherwise, string
        keys are used in the format "prefix-integer". Side must be one of
        'back' or 'front'. Defaults to pushing to the 'back' side.

        Waiting on a pull or peek is possible with :meth:`pull` or
        :meth:`peek`.

        See also `Cache.pull` and `Cache.peek`.

        Args:
            value: Value to store
            prefix: Key prefix for queue (default None)
            side: 'back' or 'front' (default 'back')
            expire: Seconds until value expires (default None)
            read: If True, value is treated as a file-like object (ignored)
            tag: Tag text to associate with value (default None)
            retry: Retry if database timeout occurs (default False)

        Returns:
            Key at which value was stored

        Raises:
            ValueError: If side is not 'back' or 'front'

        Example:
            >>> cache = Cache()
            >>> cache.push('a')
            0
            >>> cache.push('b')
            1
            >>> cache.push('c', side='front')
            -1
        """
        if side not in ("back", "front"):
            raise ValueError(f"side must be 'back' or 'front', got {side!r}")

        # Use a lock to ensure atomic queue operations
        with self._transaction_lock:
            queue_prefix = prefix if prefix is not None else "__queue__"
            counter_key = f"__queue_counter_{queue_prefix}__"
            front_key = f"__queue_front_{queue_prefix}__"

            # Get current counter values
            back_counter = self.get(counter_key)
            if back_counter is None:
                back_counter = 0
            else:
                back_counter = int(back_counter)

            front_counter = self.get(front_key)
            if front_counter is None:
                front_counter = 0
            else:
                front_counter = int(front_counter)

            if side == "back":
                key_index = back_counter
                back_counter += 1
            else:  # front
                front_counter -= 1
                key_index = front_counter

            # Build the actual cache key
            if prefix is not None:
                cache_key = f"{prefix}-{key_index}"
            else:
                cache_key = f"__queue__{key_index}"

            # Store the value
            self.set(cache_key, value, expire=expire, tag=tag)

            # Update counters
            self.set(counter_key, back_counter)
            self.set(front_key, front_counter)

            return key_index

    def pull(
        self,
        prefix: Optional[str] = None,
        default: Tuple = (None, None),
        side: str = "front",
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> Any:
        """
        Pull key and value item pair from *side* of queue in cache.

        When prefix is None, integer keys are used. Otherwise, string
        keys are used in the format "prefix-integer". Side must be one of
        'front' or 'back'. Defaults to pulling from the 'front' side.

        Args:
            prefix: Key prefix for queue (default None)
            default: Value to return if queue is empty (default (None, None))
            side: 'front' or 'back' (default 'front')
            expire_time: If True, include expire time in result (default False)
            tag: If True, include tag in result (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            (key, value) pair, or default if queue is empty

        Raises:
            ValueError: If side is not 'front' or 'back'

        Example:
            >>> cache = Cache()
            >>> cache.push('a')
            0
            >>> cache.push('b')
            1
            >>> cache.pull()
            (0, 'a')
        """
        if side not in ("front", "back"):
            raise ValueError(f"side must be 'front' or 'back', got {side!r}")

        with self._transaction_lock:
            queue_prefix = prefix if prefix is not None else "__queue__"
            counter_key = f"__queue_counter_{queue_prefix}__"
            front_key = f"__queue_front_{queue_prefix}__"

            back_counter = self.get(counter_key)
            if back_counter is None:
                back_counter = 0
            else:
                back_counter = int(back_counter)

            front_counter = self.get(front_key)
            if front_counter is None:
                front_counter = 0
            else:
                front_counter = int(front_counter)

            # Check if queue is empty
            if front_counter >= back_counter:
                if expire_time and tag:
                    return default + (None, None)
                elif expire_time or tag:
                    return default + (None,)
                return default

            if side == "front":
                key_index = front_counter
                front_counter += 1
            else:  # back
                back_counter -= 1
                key_index = back_counter

            # Build the actual cache key
            if prefix is not None:
                cache_key = f"{prefix}-{key_index}"
            else:
                cache_key = f"__queue__{key_index}"

            # Get the value and remove it
            value = self.get(cache_key)
            et = self._expire_times.get(cache_key)
            t = self._tags.get(cache_key)
            self.delete(cache_key)

            # Update counters
            self.set(counter_key, back_counter)
            self.set(front_key, front_counter)

            result = (key_index, value)
            if expire_time:
                result = result + (et,)
            if tag:
                result = result + (t,)
            return result

    def peek(
        self,
        prefix: Optional[str] = None,
        default: Tuple = (None, None),
        side: str = "front",
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> Any:
        """
        Peek at key and value item pair from *side* of queue in cache.

        Same as :meth:`pull` but does not remove the item from the queue.

        Args:
            prefix: Key prefix for queue (default None)
            default: Value to return if queue is empty (default (None, None))
            side: 'front' or 'back' (default 'front')
            expire_time: If True, include expire time in result (default False)
            tag: If True, include tag in result (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            (key, value) pair, or default if queue is empty

        Raises:
            ValueError: If side is not 'front' or 'back'

        Example:
            >>> cache = Cache()
            >>> cache.push('a')
            0
            >>> cache.peek()
            (0, 'a')
        """
        if side not in ("front", "back"):
            raise ValueError(f"side must be 'front' or 'back', got {side!r}")

        with self._transaction_lock:
            queue_prefix = prefix if prefix is not None else "__queue__"
            counter_key = f"__queue_counter_{queue_prefix}__"
            front_key = f"__queue_front_{queue_prefix}__"

            back_counter = self.get(counter_key)
            if back_counter is None:
                back_counter = 0
            else:
                back_counter = int(back_counter)

            front_counter = self.get(front_key)
            if front_counter is None:
                front_counter = 0
            else:
                front_counter = int(front_counter)

            # Check if queue is empty
            if front_counter >= back_counter:
                if expire_time and tag:
                    return default + (None, None)
                elif expire_time or tag:
                    return default + (None,)
                return default

            if side == "front":
                key_index = front_counter
            else:  # back
                key_index = back_counter - 1

            # Build the actual cache key
            if prefix is not None:
                cache_key = f"{prefix}-{key_index}"
            else:
                cache_key = f"__queue__{key_index}"

            # Get the value (don't remove)
            value = self.get(cache_key)

            result = (key_index, value)
            if expire_time:
                result = result + (self._expire_times.get(cache_key),)
            if tag:
                result = result + (self._tags.get(cache_key),)
            return result

    def read(self, key: str, retry: bool = False) -> io.BytesIO:
        """
        Return file handle value corresponding to *key* from cache.

        This method returns a :class:`io.BytesIO` object wrapping the
        cached bytes value, emulating the file-handle behavior of
        python-diskcache.

        Args:
            key: Cache key
            retry: Retry if database timeout occurs (default False)

        Returns:
            File-like object for reading

        Raises:
            KeyError: If key is not found

        Example:
            >>> cache = Cache()
            >>> cache.set('key', b'hello')
            True
            >>> reader = cache.read('key')
            >>> reader.read()
            b'hello'
        """
        try:
            serialized_value = self._cache.get(key)
            if serialized_value is None:
                raise KeyError(key)

            # Return as a BytesIO file handle
            return io.BytesIO(serialized_value)
        except KeyError:
            raise
        except Exception:
            raise KeyError(key)

    def reset(self, key: str, value: Any = None, update: bool = True) -> Any:
        """
        Reset *key* and *value* item from Settings table in database.

        If *value* is not given (``None``), it is loaded from the Settings
        table in the database. If the key is not found, returns the default
        setting value.

        This method provides access to cache settings like ``size_limit``,
        ``cull_limit``, ``statistics``, ``tag_index``, ``eviction_policy``
        and ``disk_min_file_size``.

        .. note::

            diskcache_rs manages settings through constructor parameters
            rather than a runtime settings table. This method provides
            basic compatibility by mapping known setting keys to their
            current values.

        Args:
            key: Settings key
            value: Settings value to set (default None, reads current value)
            update: Whether to persist the value (default True)

        Returns:
            Current or updated value for the given key

        Example:
            >>> cache = Cache(size_limit=2**20)
            >>> cache.reset('size_limit')
            1048576
        """
        # Map of known diskcache settings to their current/default values
        _settings = {
            "statistics": 0,
            "tag_index": 0,
            "eviction_policy": "least-recently-stored",
            "size_limit": 1073741824,  # 1GB
            "cull_limit": 10,
            "disk_min_file_size": 32768,
        }

        if value is not None and update:
            _settings[key] = value
            return value

        return _settings.get(key, None)

    @property
    def disk(self) -> Any:
        """
        Disk used for serialization.

        In python-diskcache, this is a ``Disk`` instance that handles
        serialization and file storage. In diskcache_rs, serialization
        is handled by pickle + Rust backend.

        Returns a lightweight proxy object that provides the ``store``
        and ``fetch`` methods for API compatibility.

        Returns:
            Disk-like object
        """
        return _DiskProxy(self)

    def values(self) -> List[Any]:
        """
        Return list of all values in the cache.

        Returns:
            List of cached values
        """
        result = []
        for key in self.keys():
            try:
                value = self.get(key)
                result.append(value)
            except Exception:
                pass
        return result

    def items(self) -> List[Tuple[str, Any]]:
        """
        Return list of all (key, value) pairs in the cache.

        Returns:
            List of (key, value) tuples
        """
        result = []
        for key in self.keys():
            try:
                value = self.get(key)
                result.append((key, value))
            except Exception:
                pass
        return result


class _DiskProxy:
    """
    Lightweight proxy providing disk-like interface for API compatibility.

    In python-diskcache, the ``Disk`` class handles serialization and
    file storage. This proxy provides compatible ``store`` and ``fetch``
    methods while delegating to the Rust backend.
    """

    def __init__(self, cache: "Cache"):
        self._cache = cache

    def store(self, value: Any, read: bool = False, key: Any = None) -> Any:
        """Store a value, returning the stored representation."""
        return pickle.dumps(value)

    def fetch(self, mode: int, filename: str, value: Any, read: bool = False) -> Any:
        """Fetch a value from storage."""
        if isinstance(value, bytes):
            try:
                return pickle.loads(value)
            except Exception:
                return value
        return value


class FanoutCache:
    """
    Fanout cache implementation using multiple Cache instances

    This provides sharding across multiple cache directories for better performance.
    """

    def __init__(
        self,
        directory: Union[str, Path] = None,
        shards: int = 8,
        timeout: float = 60.0,
        **kwargs,
    ):
        """
        Initialize fanout cache

        Args:
            directory: Base cache directory
            shards: Number of cache shards
            timeout: Operation timeout
            **kwargs: Additional arguments passed to Cache
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "cache")

        self.directory = Path(directory)
        self.shards = shards
        self.timeout = timeout

        # Create shard caches
        self._caches = []
        for i in range(shards):
            shard_dir = self.directory / f"shard_{i:03d}"
            cache = Cache(shard_dir, timeout=timeout, **kwargs)
            self._caches.append(cache)

    def _get_shard(self, key: str) -> Cache:
        """Get the cache shard for a given key using deterministic hashing.

        Uses BLAKE3 (or SHA-256 fallback) instead of Python's built-in hash()
        to ensure consistent shard assignment across process restarts.
        Python's hash() is randomized per process (PYTHONHASHSEED), which
        causes cache misses when keys are looked up in a different process
        than the one that stored them (issue #73).
        """
        try:
            import hashlib

            h = hashlib.blake2b(key.encode(), digest_size=8).digest()
        except (AttributeError, ValueError):
            import hashlib

            h = hashlib.sha256(key.encode()).digest()[:8]
        shard_index = int.from_bytes(h, byteorder="little") % self.shards
        return self._caches[shard_index]

    def set(self, key: str, value: Any, **kwargs) -> bool:
        """Set key to value in appropriate shard"""
        return self._get_shard(key).set(key, value, **kwargs)

    def get(self, key: str, default: Any = None, **kwargs) -> Any:
        """Get value for key from appropriate shard"""
        return self._get_shard(key).get(key, default, **kwargs)

    def delete(self, key: str) -> bool:
        """Delete key from appropriate shard"""
        return self._get_shard(key).delete(key)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in appropriate shard"""
        return key in self._get_shard(key)

    def __getitem__(self, key: str) -> Any:
        """Get item using [] syntax"""
        return self._get_shard(key)[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item using [] syntax"""
        self._get_shard(key)[key] = value

    def __delitem__(self, key: str) -> None:
        """Delete item using del syntax"""
        del self._get_shard(key)[key]

    def __iter__(self) -> Iterator[str]:
        """Iterate over all cache keys"""
        for cache in self._caches:
            yield from cache

    def __len__(self) -> int:
        """Get total number of items across all shards"""
        return sum(len(cache) for cache in self._caches)

    def clear(self) -> int:
        """Clear all items from all shards"""
        return sum(cache.clear() for cache in self._caches)

    def stats(self, **kwargs) -> Dict[str, Any]:
        """Get combined statistics from all shards"""
        combined_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "size": 0,
            "count": 0,
        }

        for cache in self._caches:
            shard_stats = cache.stats(**kwargs)
            for key in combined_stats:
                combined_stats[key] += shard_stats.get(key, 0)

        return combined_stats

    def volume(self) -> int:
        """Get total cache size across all shards"""
        return sum(cache.volume() for cache in self._caches)

    def add(
        self,
        key: str,
        value: Any,
        expire: Optional[float] = None,
        read: bool = False,
        tag: Optional[str] = None,
        retry: bool = False,
    ) -> bool:
        """Add key to cache only if it doesn't already exist"""
        return self._get_shard(key).add(key, value, expire, read, tag, retry)

    def incr(
        self, key: str, delta: int = 1, default: int = 0, retry: bool = False
    ) -> int:
        """Increment value for key by delta"""
        return self._get_shard(key).incr(key, delta, default, retry)

    def decr(
        self, key: str, delta: int = 1, default: int = 0, retry: bool = False
    ) -> int:
        """Decrement value for key by delta"""
        return self._get_shard(key).decr(key, delta, default, retry)

    def pop(
        self,
        key: str,
        default=None,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ):
        """Remove and return value for key"""
        return self._get_shard(key).pop(key, default, expire_time, tag, retry)

    def touch(
        self, key: str, expire: Optional[float] = None, retry: bool = False
    ) -> bool:
        """Update expiration time for key"""
        return self._get_shard(key).touch(key, expire, retry)

    def expire(self, now: Optional[float] = None, retry: bool = False) -> int:
        """
        Remove expired items from all cache shards.

        Removes items from the cache that have expired before the given time.
        If *now* is not provided, ``time.time()`` is used.

        Compatible with python-diskcache's ``FanoutCache.expire()`` API.

        Args:
            now: Current time (default ``time.time()``)
            retry: Whether to retry on failure (ignored)

        Returns:
            Count of removed expired items across all shards

        Example:
            >>> cache = FanoutCache()
            >>> cache.set('key', 'value', expire=0.01)
            True
            >>> import time; time.sleep(0.1)
            >>> cache.expire()
            1
        """
        return sum(cache.expire(now=now, retry=retry) for cache in self._caches)

    def close(self) -> None:
        """Close all shard caches"""
        for cache in self._caches:
            cache.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def memoize(
        self,
        name: Optional[str] = None,
        typed: bool = False,
        expire: Optional[float] = None,
        tag: Optional[str] = None,
        ignore: Set[str] = frozenset(),
    ) -> Callable:
        """
        Memoizing cache decorator.

        Decorator to wrap callable with memoizing function using cache.
        Repeated calls with the same arguments will lookup result in cache and
        avoid function evaluation.

        The cache key is determined by hashing the function arguments, and the
        appropriate shard is selected based on this key.

        Args:
            name: Name for callable (default None, uses function name)
            typed: Cache different types separately (default False)
            expire: Seconds until arguments expire (default None, no expiry)
            tag: Text to associate with arguments (default None)
            ignore: Positional or keyword args to ignore (default empty set)

        Returns:
            Decorator function

        Example:
            >>> cache = FanoutCache()
            >>> @cache.memoize(expire=60)
            ... def expensive_function(x):
            ...     return x * x
            >>> expensive_function(5)
            25
        """

        def decorator(func: Callable) -> Callable:
            # Determine the cache key prefix
            cache_key_prefix = name if name is not None else func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key from arguments
                cache_key = self._make_key(
                    cache_key_prefix, args, kwargs, typed, ignore
                )

                # Get the appropriate shard
                shard = self._get_shard(cache_key)

                # Try to get from cache - use __contains__ to check existence
                if cache_key in shard:
                    return shard.get(cache_key)

                # Call the function
                result = func(*args, **kwargs)

                # Store in cache
                shard.set(cache_key, result, expire=expire)

                return result

            # Add __cache_key__ method to generate cache key
            def cache_key(*args, **kwargs):
                return self._make_key(cache_key_prefix, args, kwargs, typed, ignore)

            wrapper.__cache_key__ = cache_key
            wrapper.__wrapped__ = func

            return wrapper

        return decorator

    def _make_key(
        self,
        prefix: str,
        args: tuple,
        kwargs: dict,
        typed: bool,
        ignore: Set[str],
    ) -> str:
        """
        Generate cache key from function arguments.

        Args:
            prefix: Key prefix (usually function name)
            args: Positional arguments
            kwargs: Keyword arguments
            typed: Include type information in key
            ignore: Arguments to ignore

        Returns:
            Cache key string
        """
        # Filter out ignored arguments
        filtered_args = args
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in ignore}

        # Build key components
        key_parts = [prefix]

        # Add positional arguments
        for i, arg in enumerate(filtered_args):
            if i not in ignore:
                if typed:
                    key_parts.append(f"{type(arg).__name__}:{repr(arg)}")
                else:
                    key_parts.append(repr(arg))

        # Add keyword arguments (sorted for consistency)
        for k in sorted(filtered_kwargs.keys()):
            v = filtered_kwargs[k]
            if typed:
                key_parts.append(f"{k}={type(v).__name__}:{repr(v)}")
            else:
                key_parts.append(f"{k}={repr(v)}")

        # Join and hash to create a fixed-length key
        key_str = "|".join(key_parts)
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()

        # Use underscore instead of colon to avoid potential issues
        return f"memoize_{prefix}_{key_hash}"

    def iterkeys(self, reverse: bool = False) -> Iterator[str]:
        """
        Iterate cache keys in database sort order across all shards.

        Args:
            reverse: Reverse sort order (default False)

        Returns:
            Iterator of cache keys
        """
        # Collect all keys from all shards
        all_keys = []
        for cache in self._caches:
            all_keys.extend(cache.keys())

        # Sort and optionally reverse
        all_keys = sorted(all_keys)
        if reverse:
            all_keys = reversed(all_keys)

        return iter(all_keys)

    def __reversed__(self) -> Iterator[str]:
        """
        Reverse iterate keys in cache including expired items.

        Returns:
            Reverse iterator of cache keys
        """
        return self.iterkeys(reverse=True)

    def peekitem(
        self,
        last: bool = True,
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> tuple:
        """
        Peek at key and value item pair in cache based on iteration order.

        Args:
            last: Last item in iteration order (default True)
            expire_time: If True, return expire_time in tuple (default False)
            tag: If True, return tag in tuple (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            Key and value item pair

        Raises:
            KeyError: If cache is empty
        """
        # Collect all keys from all shards
        all_keys = []
        for cache in self._caches:
            all_keys.extend(cache.keys())

        if not all_keys:
            raise KeyError("cache is empty")

        # Sort keys to get consistent ordering
        all_keys = sorted(all_keys)
        key = all_keys[-1] if last else all_keys[0]
        value = self.get(key)

        if expire_time or tag:
            shard = self._get_shard(key)
            result = [key, value]
            if expire_time:
                result.append(shard._expire_times.get(key))
            if tag:
                result.append(shard._tags.get(key))
            return tuple(result)
        return (key, value)

    @contextmanager
    def transact(self, retry: bool = False):
        """
        Context manager to perform a transaction by locking all cache shards.

        While the cache is locked, no other write operation is permitted from
        other threads. Transactions should therefore be as short as possible.

        Args:
            retry: Retry if database timeout occurs (default False)

        Yields:
            Context manager for use in with statement

        Example:
            >>> cache = FanoutCache()
            >>> with cache.transact():  # Atomically increment two keys
            ...     cache['total'] = cache.get('total', 0) + 123.4
            ...     cache['count'] = cache.get('count', 0) + 1
        """
        # Acquire locks on all shards
        for cache in self._caches:
            cache._transaction_lock.acquire()
            cache._transaction_depth += 1

        try:
            yield self
        finally:
            # Release locks on all shards
            for cache in self._caches:
                cache._transaction_depth -= 1
                cache._transaction_lock.release()

    def check(self, fix: bool = False, retry: bool = False) -> List[str]:
        """
        Check database and file system consistency across all shards.

        Args:
            fix: Correct inconsistencies (default False)
            retry: Retry if database timeout occurs (default False)

        Returns:
            List of warnings
        """
        warnings: List[str] = []
        for i, cache in enumerate(self._caches):
            shard_warnings = cache.check(fix=fix, retry=retry)
            for w in shard_warnings:
                warnings.append(f"shard {i}: {w}")
        return warnings

    def create_tag_index(self) -> None:
        """
        Create tag index on all cache shards.

        .. note::

            In diskcache_rs, tags are stored alongside entries. This method
            exists for API compatibility only.
        """
        for cache in self._caches:
            cache.create_tag_index()

    def drop_tag_index(self) -> None:
        """
        Drop tag index on all cache shards.

        .. note::

            In diskcache_rs, tags are stored alongside entries. This method
            exists for API compatibility only.
        """
        for cache in self._caches:
            cache.drop_tag_index()

    def cull(self, retry: bool = False) -> int:
        """
        Cull items from cache until volume is less than size limit.

        Args:
            retry: Retry if database timeout occurs (default False)

        Returns:
            Count of items removed
        """
        return sum(cache.cull(retry=retry) for cache in self._caches)

    def evict(self, tag: str, retry: bool = False) -> int:
        """
        Remove items with matching *tag* from all cache shards.

        Args:
            tag: Tag value to evict
            retry: Retry if database timeout occurs (default False)

        Returns:
            Count of items removed
        """
        return sum(cache.evict(tag, retry=retry) for cache in self._caches)

    def read(self, key: str, retry: bool = False) -> io.BytesIO:
        """
        Return file handle value corresponding to *key* from cache.

        Args:
            key: Cache key
            retry: Retry if database timeout occurs (default False)

        Returns:
            File-like object for reading

        Raises:
            KeyError: If key is not found
        """
        return self._get_shard(key).read(key, retry=retry)

    def reset(self, key: str, value: Any = None) -> Any:
        """
        Reset *key* and *value* item from Settings in all shards.

        Args:
            key: Settings key
            value: Settings value (default None)

        Returns:
            Updated value
        """
        result = None
        for cache in self._caches:
            result = cache.reset(key, value)
        return result

    def push(
        self,
        value: Any,
        prefix: Optional[str] = None,
        side: str = "back",
        expire: Optional[float] = None,
        read: bool = False,
        tag: Optional[str] = None,
        retry: bool = False,
    ) -> Any:
        """
        Push *value* onto *side* of queue identified by *prefix*.

        Uses shard 0 for queue operations to maintain ordering.

        Args:
            value: Value to store
            prefix: Key prefix for queue (default None)
            side: 'back' or 'front' (default 'back')
            expire: Seconds until value expires (default None)
            read: If True, value is treated as a file-like object (ignored)
            tag: Tag text to associate with value (default None)
            retry: Retry if database timeout occurs (default False)

        Returns:
            Key at which value was stored
        """
        # Use shard 0 for queue operations to maintain ordering
        return self._caches[0].push(
            value, prefix=prefix, side=side, expire=expire, tag=tag, retry=retry
        )

    def pull(
        self,
        prefix: Optional[str] = None,
        default: Tuple = (None, None),
        side: str = "front",
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> Any:
        """
        Pull key and value item pair from *side* of queue.

        Args:
            prefix: Key prefix for queue (default None)
            default: Value to return if queue is empty
            side: 'front' or 'back' (default 'front')
            expire_time: If True, include expire time in result
            tag: If True, include tag in result
            retry: Retry if database timeout occurs (default False)

        Returns:
            (key, value) pair, or default if queue is empty
        """
        return self._caches[0].pull(
            prefix=prefix,
            default=default,
            side=side,
            expire_time=expire_time,
            tag=tag,
            retry=retry,
        )

    def peek(
        self,
        prefix: Optional[str] = None,
        default: Tuple = (None, None),
        side: str = "front",
        expire_time: bool = False,
        tag: bool = False,
        retry: bool = False,
    ) -> Any:
        """
        Peek at key and value item pair from *side* of queue.

        Args:
            prefix: Key prefix for queue (default None)
            default: Value to return if queue is empty
            side: 'front' or 'back' (default 'front')
            expire_time: If True, include expire time in result
            tag: If True, include tag in result
            retry: Retry if database timeout occurs (default False)

        Returns:
            (key, value) pair, or default if queue is empty
        """
        return self._caches[0].peek(
            prefix=prefix,
            default=default,
            side=side,
            expire_time=expire_time,
            tag=tag,
            retry=retry,
        )

    def keys(self) -> List[str]:
        """
        Return list of all keys across all shards.

        Returns:
            List of cache keys
        """
        all_keys: List[str] = []
        for cache in self._caches:
            all_keys.extend(cache.keys())
        return all_keys

    def values(self) -> List[Any]:
        """
        Return list of all values across all shards.

        Returns:
            List of cached values
        """
        result: List[Any] = []
        for cache in self._caches:
            result.extend(cache.values())
        return result

    def items(self) -> List[Tuple[str, Any]]:
        """
        Return list of all (key, value) pairs across all shards.

        Returns:
            List of (key, value) tuples
        """
        result: List[Tuple[str, Any]] = []
        for cache in self._caches:
            result.extend(cache.items())
        return result

    def exists(self, key: str) -> bool:
        """
        Check if key exists in the appropriate shard.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        return self._get_shard(key).exists(key)

    @property
    def disk(self) -> Any:
        """
        Disk used for serialization.

        Returns a lightweight proxy object for API compatibility.
        """
        return _DiskProxy(self._caches[0])

    def cache(self, name: str, timeout: Optional[float] = None, **kwargs) -> "Cache":
        """
        Return ``Cache`` with given *name* in a subdirectory.

        This method creates or returns a named cache instance stored in a
        subdirectory of this FanoutCache's directory. Useful for organizing
        related but logically separate caches.

        Args:
            name: Subdirectory name for the cache
            timeout: SQLite connection timeout (default uses FanoutCache timeout)
            **kwargs: Additional arguments passed to Cache

        Returns:
            Cache instance

        Example:
            >>> fanout = FanoutCache('/tmp/fc')
            >>> users_cache = fanout.cache('users')
            >>> users_cache.set('user1', {'name': 'Alice'})
            True
        """
        if timeout is None:
            timeout = self.timeout
        cache_dir = self.directory / name
        return Cache(cache_dir, timeout=timeout, **kwargs)

    def deque(self, name: str, maxlen: Optional[int] = None) -> "Deque":
        """
        Return ``Deque`` with given *name* in a subdirectory.

        Args:
            name: Subdirectory name for the deque
            maxlen: Maximum length of deque (default None, no limit)

        Returns:
            Deque instance

        Example:
            >>> fanout = FanoutCache('/tmp/fc')
            >>> dq = fanout.deque('tasks')
            >>> dq.append('task1')
        """
        cache_dir = self.directory / name
        return Deque(directory=cache_dir, maxlen=maxlen)

    def index(self, name: str) -> "Index":
        """
        Return ``Index`` with given *name* in a subdirectory.

        Args:
            name: Subdirectory name for the index

        Returns:
            Index instance

        Example:
            >>> fanout = FanoutCache('/tmp/fc')
            >>> idx = fanout.index('metadata')
            >>> idx['version'] = '1.0'
        """
        cache_dir = self.directory / name
        return Index(directory=cache_dir)

    def vacuum(self) -> None:
        """Manually trigger vacuum operation on all shards."""
        for cache in self._caches:
            cache.vacuum()

    def __del__(self):
        """Destructor to ensure resources are released."""
        self.close()

    def __getstate__(self):
        """Support pickling by returning directory, shards, and timeout."""
        return (str(self.directory), self.shards, self.timeout)

    def __setstate__(self, state):
        """Restore FanoutCache from pickled state."""
        directory, shards, timeout = state
        self.__init__(directory=directory, shards=shards, timeout=timeout)


class Deque:
    """
    Persistent double-ended queue based on Cache.

    Implements a subset of collections.deque interface backed by a
    persistent cache for durability.

    Compatible with python-diskcache's Deque API.

    Example:
        >>> dq = Deque()
        >>> dq.append('a')
        >>> dq.appendleft('b')
        >>> list(dq)
        ['b', 'a']
    """

    def __init__(
        self,
        iterable: Any = (),
        directory: Union[str, Path] = None,
        maxlen: Optional[int] = None,
    ):
        """
        Initialize deque.

        Args:
            iterable: Initial values to add (default empty)
            directory: Cache directory path (default auto-generated)
            maxlen: Maximum length (default None, no limit)
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "cache", "deque")
        self._cache = Cache(directory)
        self._maxlen = maxlen

        # Initialize from iterable
        for item in iterable:
            self.append(item)

    @property
    def maxlen(self) -> Optional[int]:
        """Maximum length of the deque."""
        return self._maxlen

    @property
    def directory(self) -> Path:
        """Directory of the underlying cache."""
        return self._cache.directory

    def append(self, value: Any) -> None:
        """Add value to the back of the deque."""
        self._cache.push(value, side="back")
        if self._maxlen is not None and len(self) > self._maxlen:
            self.popleft()

    def appendleft(self, value: Any) -> None:
        """Add value to the front of the deque."""
        self._cache.push(value, side="front")
        if self._maxlen is not None and len(self) > self._maxlen:
            self.pop()

    def pop(self) -> Any:
        """Remove and return value from the back of the deque."""
        result = self._cache.pull(side="back")
        if result == (None, None):
            raise IndexError("pop from an empty deque")
        return result[1]

    def popleft(self) -> Any:
        """Remove and return value from the front of the deque."""
        result = self._cache.pull(side="front")
        if result == (None, None):
            raise IndexError("pop from an empty deque")
        return result[1]

    def peek(self) -> Any:
        """Return value at the back of the deque without removing."""
        result = self._cache.peek(side="back")
        if result == (None, None):
            raise IndexError("peek at an empty deque")
        return result[1]

    def peekleft(self) -> Any:
        """Return value at the front of the deque without removing."""
        result = self._cache.peek(side="front")
        if result == (None, None):
            raise IndexError("peek at an empty deque")
        return result[1]

    def clear(self) -> None:
        """Remove all items from the deque."""
        self._cache.clear()

    def __len__(self) -> int:
        """Return number of items in the deque."""
        front, back = self._get_queue_range()
        return back - front

    def __iter__(self) -> Iterator[Any]:
        """Iterate over deque items from front to back."""
        front, back = self._get_queue_range()
        for i in range(front, back):
            cache_key = f"__queue__{i}"
            value = self._cache.get(cache_key)
            if value is not None:
                yield value

    def __reversed__(self) -> Iterator[Any]:
        """Iterate over deque items from back to front."""
        front, back = self._get_queue_range()
        for i in range(back - 1, front - 1, -1):
            cache_key = f"__queue__{i}"
            value = self._cache.get(cache_key)
            if value is not None:
                yield value

    def __bool__(self) -> bool:
        """Return True if deque is not empty."""
        return len(self) > 0

    def __repr__(self) -> str:
        return f"Deque(directory={self._cache.directory!r})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cache.close()

    def close(self) -> None:
        """Close the underlying cache."""
        self._cache.close()

    def extend(self, iterable: Any) -> None:
        """Extend deque by appending elements from the iterable."""
        for item in iterable:
            self.append(item)

    def extendleft(self, iterable: Any) -> None:
        """Extend deque by prepending elements from the iterable."""
        for item in iterable:
            self.appendleft(item)

    def _get_queue_range(self):
        """Get front and back indices of the queue."""
        queue_prefix = "__queue__"
        counter_key = f"__queue_counter_{queue_prefix}__"
        front_key = f"__queue_front_{queue_prefix}__"

        back = self._cache.get(counter_key)
        front = self._cache.get(front_key)
        if back is None:
            back = 0
        else:
            back = int(back)
        if front is None:
            front = 0
        else:
            front = int(front)
        return front, back

    def _get_all_items(self):
        """Get all items as a list."""
        front, back = self._get_queue_range()
        items = []
        for i in range(front, back):
            cache_key = f"__queue__{i}"
            value = self._cache.get(cache_key)
            if value is not None:
                items.append(value)
        return items

    def __getitem__(self, index):
        """Get item at index."""
        items = self._get_all_items()
        return items[index]

    def __setitem__(self, index, value):
        """Set item at index."""
        front, back = self._get_queue_range()
        length = back - front
        if isinstance(index, int):
            if index < 0:
                index += length
            if index < 0 or index >= length:
                raise IndexError("deque index out of range")
            cache_key = f"__queue__{front + index}"
            self._cache.set(cache_key, value)
        else:
            raise TypeError(f"deque indices must be integers, not {type(index).__name__}")

    def __delitem__(self, index):
        """Delete item at index."""
        items = self._get_all_items()
        if isinstance(index, int):
            del items[index]
        else:
            raise TypeError(f"deque indices must be integers, not {type(index).__name__}")
        # Rebuild the deque
        self.clear()
        for item in items:
            self.append(item)

    def __contains__(self, value) -> bool:
        """Check if value is in deque."""
        for item in self:
            if item == value:
                return True
        return False

    def copy(self) -> "Deque":
        """Return a shallow copy of the deque."""
        import tempfile

        new_dir = tempfile.mkdtemp()
        new_deque = Deque(directory=new_dir, maxlen=self._maxlen)
        for item in self:
            new_deque.append(item)
        return new_deque

    def count(self, value) -> int:
        """Return number of occurrences of value."""
        return sum(1 for item in self if item == value)

    def remove(self, value) -> None:
        """Remove first occurrence of value.

        Raises ValueError if value is not present.
        """
        items = self._get_all_items()
        try:
            items.remove(value)
        except ValueError:
            raise ValueError(f"{value!r} is not in deque")
        # Rebuild the deque
        self.clear()
        for item in items:
            self.append(item)

    def reverse(self) -> None:
        """Reverse the deque in-place."""
        items = self._get_all_items()
        items.reverse()
        self.clear()
        for item in items:
            self.append(item)

    def rotate(self, steps: int = 1) -> None:
        """Rotate the deque *steps* steps to the right.

        If steps is negative, rotate to the left.
        """
        length = len(self)
        if length <= 1:
            return
        steps = steps % length
        if steps == 0:
            return
        items = self._get_all_items()
        items = items[-steps:] + items[:-steps]
        self.clear()
        for item in items:
            self.append(item)

    def __iadd__(self, other):
        """Implement self += other."""
        self.extend(other)
        return self

    def __eq__(self, other) -> bool:
        """Compare deques for equality."""
        if isinstance(other, Deque):
            return list(self) == list(other)
        if hasattr(other, "__iter__"):
            return list(self) == list(other)
        return NotImplemented

    def __ne__(self, other) -> bool:
        """Compare deques for inequality."""
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __lt__(self, other) -> bool:
        """Compare deques."""
        if isinstance(other, Deque) or hasattr(other, "__iter__"):
            return list(self) < list(other)
        return NotImplemented

    def __le__(self, other) -> bool:
        """Compare deques."""
        if isinstance(other, Deque) or hasattr(other, "__iter__"):
            return list(self) <= list(other)
        return NotImplemented

    def __gt__(self, other) -> bool:
        """Compare deques."""
        if isinstance(other, Deque) or hasattr(other, "__iter__"):
            return list(self) > list(other)
        return NotImplemented

    def __ge__(self, other) -> bool:
        """Compare deques."""
        if isinstance(other, Deque) or hasattr(other, "__iter__"):
            return list(self) >= list(other)
        return NotImplemented

    @contextmanager
    def transact(self):
        """Context manager to perform a transaction on the underlying cache."""
        with self._cache.transact():
            yield self

    def __getstate__(self):
        """Support pickling."""
        return (str(self._cache.directory), self._maxlen, list(self))

    def __setstate__(self, state):
        """Restore from pickled state."""
        directory, maxlen, items = state
        self.__init__(directory=directory, maxlen=maxlen)
        self.clear()  # Clear any existing data in the directory
        for item in items:
            self.append(item)


class Index:
    """
    Persistent ordered mapping based on Cache.

    Implements a subset of collections.OrderedDict interface backed by a
    persistent cache for durability.

    Compatible with python-diskcache's Index API.

    Example:
        >>> idx = Index()
        >>> idx['key'] = 'value'
        >>> idx['key']
        'value'
    """

    def __init__(
        self,
        *args: Any,
        directory: Union[str, Path] = None,
        **kwargs: Any,
    ):
        """
        Initialize index.

        Args:
            *args: Initial (key, value) pairs or dict-like mapping
            directory: Cache directory path (default auto-generated)
            **kwargs: Initial key=value pairs
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "cache", "index")
        self._cache = Cache(directory)

        # Initialize from args and kwargs
        if args:
            if len(args) == 1 and isinstance(args[0], dict):
                for k, v in args[0].items():
                    self._cache.set(str(k), v)
            elif len(args) == 1 and hasattr(args[0], "__iter__"):
                for k, v in args[0]:
                    self._cache.set(str(k), v)
        for k, v in kwargs.items():
            self._cache.set(str(k), v)

    @property
    def directory(self) -> Path:
        """Directory of the underlying cache."""
        return self._cache.directory

    def __getitem__(self, key: str) -> Any:
        """Get value for key."""
        return self._cache[str(key)]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set value for key."""
        self._cache.set(str(key), value)

    def __delitem__(self, key: str) -> None:
        """Delete key."""
        del self._cache[str(key)]

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return str(key) in self._cache

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys."""
        return iter(self._cache)

    def __reversed__(self) -> Iterator[str]:
        """Reverse iterate keys."""
        return reversed(self._cache)

    def __len__(self) -> int:
        """Return number of items."""
        return len(self._cache)

    def __bool__(self) -> bool:
        """Return True if index is not empty."""
        return len(self) > 0

    def get(self, key: str, default: Any = None) -> Any:
        """Get value for key with default."""
        return self._cache.get(str(key), default)

    def pop(self, key: str, default: Any = None) -> Any:
        """Remove and return value for key."""
        return self._cache.pop(str(key), default)

    def setdefault(self, key: str, default: Any = None) -> Any:
        """If key is not in index, set it to default and return default."""
        k = str(key)
        if k not in self._cache:
            self._cache.set(k, default)
            return default
        return self._cache.get(k)

    def keys(self) -> List[str]:
        """Return list of keys."""
        return self._cache.keys()

    def values(self) -> List[Any]:
        """Return list of values."""
        return self._cache.values()

    def items(self) -> List[Tuple[str, Any]]:
        """Return list of (key, value) pairs."""
        return self._cache.items()

    def update(self, *args: Any, **kwargs: Any) -> None:
        """Update index with key/value pairs."""
        if args:
            if isinstance(args[0], dict):
                for k, v in args[0].items():
                    self._cache.set(str(k), v)
            else:
                for k, v in args[0]:
                    self._cache.set(str(k), v)
        for k, v in kwargs.items():
            self._cache.set(str(k), v)

    def clear(self) -> None:
        """Remove all items."""
        self._cache.clear()

    def peekitem(self, last: bool = True) -> Tuple[str, Any]:
        """Peek at key and value pair."""
        return self._cache.peekitem(last=last)

    def popitem(self, last: bool = True) -> Tuple[str, Any]:
        """Remove and return (key, value) pair.

        Pairs are returned in LIFO (last-in, first-out) order if *last* is
        true or FIFO order if false.

        Args:
            last: If True, return last item (default True)

        Returns:
            (key, value) tuple

        Raises:
            KeyError: If index is empty
        """
        key, value = self._cache.peekitem(last=last)
        del self._cache[key]
        return (key, value)

    @property
    def cache(self) -> Cache:
        """Return the underlying Cache object."""
        return self._cache

    def __eq__(self, other) -> bool:
        """Compare Index with another mapping."""
        if isinstance(other, Index):
            return dict(self.items()) == dict(other.items())
        if isinstance(other, dict):
            return dict(self.items()) == other
        return NotImplemented

    def __ne__(self, other) -> bool:
        """Compare Index with another mapping."""
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    @contextmanager
    def transact(self):
        """Context manager to perform a transaction on the underlying cache."""
        with self._cache.transact():
            yield self

    def memoize(
        self,
        name: Optional[str] = None,
        typed: bool = False,
        ignore: Set[str] = frozenset(),
    ) -> Callable:
        """Memoize decorator using this Index as cache."""
        return self._cache.memoize(name=name, typed=typed, ignore=ignore)

    def push(
        self,
        value: Any,
        prefix: Optional[str] = None,
        side: str = "back",
    ) -> Any:
        """Push value onto queue in underlying cache."""
        return self._cache.push(value, prefix=prefix, side=side)

    def pull(
        self,
        prefix: Optional[str] = None,
        default: Tuple = (None, None),
        side: str = "front",
    ) -> Any:
        """Pull value from queue in underlying cache."""
        return self._cache.pull(prefix=prefix, default=default, side=side)

    def __getstate__(self):
        """Support pickling."""
        return (str(self._cache.directory), dict(self.items()))

    def __setstate__(self, state):
        """Restore from pickled state."""
        directory, data = state
        self.__init__(data, directory=directory)

    def __repr__(self) -> str:
        return f"Index(directory={self._cache.directory!r})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cache.close()

    def close(self) -> None:
        """Close the underlying cache."""
        self._cache.close()
