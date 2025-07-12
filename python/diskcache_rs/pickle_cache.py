"""
High-performance pickle cache with expiration support
"""

import pickle
from typing import Any, Dict, List, Optional

from ._diskcache_rs import PickleCache as _PickleCache


class PickleCache:
    """
    High-performance disk cache for pickled Python objects with expiration support.

    This cache uses Rust for high-performance operations and supports:
    - Automatic expiration of cached items
    - LRU eviction when size limits are reached
    - Efficient pickle serialization/deserialization
    - Thread-safe operations

    Example:
        >>> cache = PickleCache("/tmp/pickle_cache", max_size=100*1024*1024)  # 100MB limit
        >>> cache.set("key", {"data": "value"}, ttl_seconds=3600)  # Expire in 1 hour
        >>> data = cache.get("key")
        >>> print(data)  # {"data": "value"}
    """

    def __init__(
        self,
        directory: str,
        max_size: Optional[int] = None,
        default_ttl_seconds: Optional[int] = None,
    ):
        """
        Initialize the pickle cache.

        Args:
            directory: Directory to store cache files
            max_size: Maximum cache size in bytes (None for unlimited)
            default_ttl_seconds: Default TTL for entries in seconds (None for no expiration)
        """
        self._cache = _PickleCache(directory, max_size, default_ttl_seconds)

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store a Python object in the cache.

        Args:
            key: Cache key
            value: Python object to cache (must be picklable)
            ttl_seconds: Time to live in seconds (overrides default TTL)

        Raises:
            PickleError: If the object cannot be pickled
            IOError: If there's an error writing to disk
        """
        try:
            pickled_data = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
            self._cache.set_pickle(key, pickled_data, ttl_seconds)
        except Exception as e:
            raise RuntimeError(f"Failed to cache object: {e}") from e

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a Python object from the cache.

        Args:
            key: Cache key
            default: Default value to return if key is not found or expired

        Returns:
            The cached object or default value

        Raises:
            PickleError: If the cached data cannot be unpickled
        """
        try:
            pickled_data = self._cache.get_pickle(key)
            if pickled_data is not None:
                return pickle.loads(pickled_data)
            return default
        except Exception:
            # If unpickling fails, remove the corrupted entry
            try:
                self._cache.delete_pickle(key)
            except Exception:
                pass
            return default

    def delete(self, key: str) -> bool:
        """
        Delete an entry from the cache.

        Args:
            key: Cache key to delete

        Returns:
            True if the key was found and deleted, False otherwise
        """
        return self._cache.delete_pickle(key)

    def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache and is not expired.

        Args:
            key: Cache key to check

        Returns:
            True if the key exists and is not expired, False otherwise
        """
        return self._cache.exists_pickle(key)

    def keys(self) -> List[str]:
        """
        Get all non-expired keys in the cache.

        Returns:
            List of cache keys
        """
        return self._cache.keys_pickle()

    def clear(self) -> None:
        """
        Clear all entries from the cache.
        """
        self._cache.clear_pickle()

    def stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - entries: Number of entries in cache
            - size_bytes: Total size in bytes
            - max_size_bytes: Maximum size limit (if set)
            - size_ratio: Size usage percentage (if max_size is set)
        """
        return self._cache.stats_pickle()

    def expire(self, key: str, ttl_seconds: int) -> bool:
        """
        Set or update the TTL for an existing key.

        Args:
            key: Cache key
            ttl_seconds: New TTL in seconds

        Returns:
            True if the key was found and TTL was set, False otherwise
        """
        return self._cache.expire_pickle(key, ttl_seconds)

    def ttl(self, key: str) -> Optional[int]:
        """
        Get the remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, None if key doesn't exist or has no expiration,
            0 if the key is expired
        """
        return self._cache.ttl_pickle(key)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (supports 'in' operator)"""
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

    def __iter__(self):
        """Iterate over cache keys"""
        return iter(self.keys())

    # Context manager support
    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # No cleanup needed as Rust handles file operations
        pass


# Convenience functions for quick caching
def cache_object(
    directory: str,
    key: str,
    value: Any,
    ttl_seconds: Optional[int] = None,
    max_size: Optional[int] = None,
) -> None:
    """
    Convenience function to cache a single object.

    Args:
        directory: Cache directory
        key: Cache key
        value: Object to cache
        ttl_seconds: TTL in seconds
        max_size: Maximum cache size in bytes
    """
    cache = PickleCache(directory, max_size=max_size)
    cache.set(key, value, ttl_seconds)


def get_cached_object(
    directory: str,
    key: str,
    default: Any = None,
) -> Any:
    """
    Convenience function to retrieve a cached object.

    Args:
        directory: Cache directory
        key: Cache key
        default: Default value if not found

    Returns:
        Cached object or default value
    """
    cache = PickleCache(directory)
    return cache.get(key, default)


def clear_cache(directory: str) -> None:
    """
    Convenience function to clear a cache directory.

    Args:
        directory: Cache directory to clear
    """
    cache = PickleCache(directory)
    cache.clear()
