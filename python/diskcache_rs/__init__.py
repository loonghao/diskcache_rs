"""
DiskCache RS - A high-performance disk cache implementation in Rust with Python bindings

This module provides a Python interface compatible with python-diskcache,
but implemented in Rust for better performance and network filesystem support.
"""

# Always use the Python wrapper for now
# The Python wrapper will handle importing the Rust implementation
from .cache import Cache, Deque, FanoutCache, Index
from .fast_cache import FastCache, FastFanoutCache
from .pickle_cache import PickleCache, cache_object, clear_cache, get_cached_object

# Constants, exceptions, and warnings (compatible with diskcache.core)
from .constants import (
    DEFAULT_SETTINGS,
    ENOVAL,
    EVICTION_POLICY,
    UNKNOWN,
    EmptyDirWarning,
    Timeout,
    UnknownFileWarning,
)

# Disk serialization classes (compatible with diskcache.core)
from .disk import Disk, JSONDisk

# Recipes: synchronization primitives, rate limiting, cache stampede protection
from .recipes import (
    Averager,
    BoundedSemaphore,
    Lock,
    RLock,
    barrier,
    memoize_stampede,
    throttle,
)

# Import Rust pickle functions
try:
    from ._diskcache_rs import rust_pickle_dumps, rust_pickle_loads
except ImportError:
    rust_pickle_dumps = None
    rust_pickle_loads = None

# Version is exported from Rust core module
from ._diskcache_rs import __version__

# Optional: DjangoCache (only available if Django is installed and configured)
try:
    from .djangocache import DjangoCache
except Exception:
    pass

__all__ = [
    # Core cache classes
    "Cache",
    "FanoutCache",
    "Deque",
    "Index",
    # Constants
    "DEFAULT_SETTINGS",
    "ENOVAL",
    "EVICTION_POLICY",
    "UNKNOWN",
    # Disk serialization
    "Disk",
    "JSONDisk",
    # Exceptions and warnings
    "Timeout",
    "EmptyDirWarning",
    "UnknownFileWarning",
    # Recipes: synchronization primitives
    "Lock",
    "RLock",
    "BoundedSemaphore",
    # Recipes: decorators
    "Averager",
    "barrier",
    "memoize_stampede",
    "throttle",
    # diskcache_rs extras
    "PickleCache",
    "cache_object",
    "get_cached_object",
    "clear_cache",
    "FastCache",
    "FastFanoutCache",
    "rust_pickle_dumps",
    "rust_pickle_loads",
]

# For backward compatibility
DiskCache = Cache
