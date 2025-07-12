"""
Python-compatible cache interface for diskcache_rs
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union

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
            disk_min_file_size: Minimum file size for disk storage (not used)
            **kwargs: Additional arguments (max_size, max_entries, etc.)
        """
        if directory is None:
            directory = os.path.join(os.getcwd(), "cache")

        self.directory = Path(directory)
        self.timeout = timeout

        # Extract Rust cache parameters
        max_size = kwargs.get(
            "size_limit", kwargs.get("max_size", 1024 * 1024 * 1024)
        )  # 1GB default
        max_entries = kwargs.get("count_limit", kwargs.get("max_entries", 100_000))

        # Create the underlying Rust cache
        _RustCache = _get_rust_cache()
        self._cache = _RustCache(
            str(self.directory), max_size=max_size, max_entries=max_entries
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

            # Deserialize the value
            value = pickle.loads(serialized_value)

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

    def close(self) -> None:
        """Close cache (no-op for Rust implementation)"""
        pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


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
