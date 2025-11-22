"""
Python-compatible cache interface for diskcache_rs
"""

import functools
import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Union

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
        self._transaction_lock = threading.RLock()  # Reentrant lock for nested transactions
        self._transaction_depth = 0  # Track nested transaction depth

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
            if data and data[0:1] in (b'{', b'[', b'"'):
                text = data.decode('utf-8')
                return json.loads(text)
        except Exception:
            pass

        # Try plain text
        try:
            return data.decode('utf-8')
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
            read: Whether this is a read operation (ignored)
            expire_time: Whether to return expire time (not supported)
            tag: Whether to return tag (not supported)
            retry: Whether to retry on failure (ignored)

        Returns:
            Cached value or default
        """
        try:
            serialized_value = self._cache.get(key)
            if serialized_value is None:
                return default

            # Auto-detect and deserialize the value
            value = self._auto_deserialize(serialized_value)

            # Handle additional return values
            if expire_time or tag:
                result = [value]
                if expire_time:
                    result.append(None)  # Expire time not supported yet
                if tag:
                    result.append(None)  # Tag not supported yet
                return tuple(result)

            return value

        except Exception:
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
            return self._cache.delete(key)
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
            expire_time: Whether to return expire time (not supported)
            tag: Whether to return tag (not supported)
            retry: Whether to retry on failure (ignored)

        Returns:
            Value, or tuple with additional metadata if requested
        """
        try:
            value = self.get(key)
            if value is None:
                if expire_time or tag:
                    return (default, None, None)
                return default

            # Remove the key
            del self[key]

            if expire_time or tag:
                # Return tuple format: (value, expire_time, tag)
                return (value, None, None)
            return value
        except Exception:
            if expire_time or tag:
                return (default, None, None)
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
            # Return tuple format: (key, value, expire_time, tag)
            return (key, value, None, None)
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
        """Get the cache shard for a given key"""
        # Simple hash-based sharding
        shard_index = hash(key) % self.shards
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
            # Return tuple format: (key, value, expire_time, tag)
            return (key, value, None, None)
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
