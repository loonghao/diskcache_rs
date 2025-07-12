"""
Fast cache implementation using Rust pickle backend
"""

import time
from typing import Any, Dict, Iterator, List, Optional

from .pickle_cache import PickleCache


class FastCache:
    """
    High-performance cache using Rust pickle backend.

    This is a drop-in replacement for the standard Cache class that uses
    the high-performance Rust pickle implementation for better performance.

    Note: This implementation prioritizes API compatibility over raw performance.
    For maximum performance, use the original Cache class which now includes
    Rust pickle optimizations.

    Example:
        >>> cache = FastCache("/tmp/cache", max_size=100*1024*1024)
        >>> cache.set("key", {"data": "value"}, expire=3600)
        >>> data = cache.get("key")
    """

    def __init__(
        self,
        directory: str,
        max_size: Optional[int] = None,
        max_entries: Optional[int] = None,
        default_ttl_seconds: Optional[int] = None,
    ):
        """
        Initialize the fast cache.

        Args:
            directory: Directory to store cache files
            max_size: Maximum cache size in bytes
            max_entries: Maximum number of entries (ignored, use max_size)
            default_ttl_seconds: Default TTL for entries in seconds
        """
        self.directory = directory
        self._cache = PickleCache(directory, max_size, default_ttl_seconds)

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
            tag: Tag for the entry (ignored for now)
            retry: Whether to retry on failure (ignored)

        Returns:
            True if successful
        """
        try:
            # Calculate TTL
            ttl_seconds = None
            if expire is not None:
                if expire > time.time():
                    # Assume it's already a timestamp
                    ttl_seconds = int(expire - time.time())
                else:
                    # Assume it's seconds from now
                    ttl_seconds = int(expire)

            # Store using Rust pickle cache
            self._cache.set(key, value, ttl_seconds)
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
            expire_time: Whether to return expire time
            tag: Whether to return tag (ignored)
            retry: Whether to retry on failure (ignored)

        Returns:
            Cached value or default, optionally with expire time
        """
        try:
            value = self._cache.get(key, default)

            # Handle additional return values
            if expire_time or tag:
                result = [value]
                if expire_time:
                    # Get TTL and convert to timestamp
                    ttl = self._cache.ttl(key)
                    if ttl is not None:
                        expire_timestamp = time.time() + ttl
                        result.append(expire_timestamp)
                    else:
                        result.append(None)
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
            True if key was found and deleted
        """
        return self._cache.delete(key)

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        return self._cache.exists(key)

    def keys(self) -> List[str]:
        """Get list of all cache keys"""
        return self._cache.keys()

    def clear(self) -> None:
        """Clear all entries from the cache"""
        self._cache.clear()

    def stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return self._cache.stats()

    def expire(self, key: str, ttl_seconds: int) -> bool:
        """Set TTL for an existing key"""
        return self._cache.expire(key, ttl_seconds)

    def ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL for a key"""
        return self._cache.ttl(key)

    # Dictionary-like interface
    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache"""
        return self.exists(key)

    def __getitem__(self, key: str) -> Any:
        """Get item using [] syntax"""
        result = self.get(key)
        if result is None and not self.exists(key):
            raise KeyError(key)
        return result

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item using [] syntax"""
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        """Delete item using del syntax"""
        if not self.delete(key):
            raise KeyError(key)

    def __len__(self) -> int:
        """Get number of entries in cache"""
        return len(self.keys())

    def __iter__(self) -> Iterator[str]:
        """Iterate over cache keys"""
        return iter(self.keys())

    # Additional methods for compatibility
    def add(self, key: str, value: Any, expire: Optional[float] = None) -> bool:
        """Add key to cache only if it doesn't exist"""
        if self.exists(key):
            return False
        return self.set(key, value, expire)

    def touch(self, key: str, expire: Optional[float] = None) -> bool:
        """Update the expiration time for a key"""
        if not self.exists(key):
            return False

        if expire is not None:
            if expire > time.time():
                ttl_seconds = int(expire - time.time())
            else:
                ttl_seconds = int(expire)
            return self.expire(key, ttl_seconds)

        return True

    def pop(self, key: str, default: Any = None) -> Any:
        """Remove and return value for key"""
        value = self.get(key, default)
        if self.exists(key):
            self.delete(key)
        return value

    def incr(self, key: str, delta: int = 1) -> int:
        """Increment integer value"""
        try:
            current = self.get(key, 0)
            if not isinstance(current, (int, float)):
                raise ValueError("Value is not a number")
            new_value = current + delta
            self.set(key, new_value)
            return new_value
        except Exception:
            raise ValueError("Cannot increment non-numeric value")

    def decr(self, key: str, delta: int = 1) -> int:
        """Decrement integer value"""
        return self.incr(key, -delta)

    def volume(self) -> int:
        """Get cache volume (total size in bytes)"""
        stats = self.stats()
        return stats.get("size_bytes", 0)

    def close(self) -> None:
        """Close the cache (no-op for compatibility)"""
        pass

    # Context manager support
    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class FastFanoutCache:
    """
    Fast fanout cache using multiple FastCache shards for better concurrency.
    """

    def __init__(
        self,
        directory: str,
        shards: int = 8,
        max_size: Optional[int] = None,
        max_entries: Optional[int] = None,
        default_ttl_seconds: Optional[int] = None,
    ):
        """
        Initialize the fast fanout cache.

        Args:
            directory: Base directory for cache shards
            shards: Number of cache shards
            max_size: Maximum total cache size in bytes
            max_entries: Maximum number of entries (ignored)
            default_ttl_seconds: Default TTL for entries
        """
        self.directory = directory
        self.shards = shards

        # Calculate per-shard size limit
        shard_max_size = None
        if max_size is not None:
            shard_max_size = max_size // shards

        # Create cache shards
        self._caches = []
        for i in range(shards):
            shard_dir = f"{directory}/shard_{i:03d}"
            cache = FastCache(shard_dir, shard_max_size, None, default_ttl_seconds)
            self._caches.append(cache)

    def _get_shard(self, key: str) -> FastCache:
        """Get the cache shard for a given key"""
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

    def exists(self, key: str) -> bool:
        """Check if key exists in any shard"""
        return self._get_shard(key).exists(key)

    def keys(self) -> List[str]:
        """Get all keys from all shards"""
        all_keys = []
        for cache in self._caches:
            all_keys.extend(cache.keys())
        return all_keys

    def clear(self) -> None:
        """Clear all shards"""
        for cache in self._caches:
            cache.clear()

    def stats(self) -> Dict[str, int]:
        """Get combined statistics from all shards"""
        combined_stats = {"entries": 0, "size_bytes": 0}

        for cache in self._caches:
            shard_stats = cache.stats()
            combined_stats["entries"] += shard_stats.get("entries", 0)
            combined_stats["size_bytes"] += shard_stats.get("size_bytes", 0)

        return combined_stats

    # Delegate other methods to appropriate shard
    def __contains__(self, key: str) -> bool:
        return self.exists(key)

    def __getitem__(self, key: str) -> Any:
        return self._get_shard(key)[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._get_shard(key)[key] = value

    def __delitem__(self, key: str) -> None:
        del self._get_shard(key)[key]

    def __len__(self) -> int:
        return sum(len(cache) for cache in self._caches)

    def __iter__(self) -> Iterator[str]:
        for cache in self._caches:
            yield from cache

    def close(self) -> None:
        """Close all cache shards"""
        for cache in self._caches:
            cache.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
