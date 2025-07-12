"""
DiskCache RS - A high-performance disk cache implementation in Rust with Python bindings

This module provides a Python interface compatible with python-diskcache,
but implemented in Rust for better performance and network filesystem support.
"""

# Always use the Python wrapper for now
# The Python wrapper will handle importing the Rust implementation
from .cache import Cache, FanoutCache
from .fast_cache import FastCache, FastFanoutCache
from .pickle_cache import PickleCache, cache_object, clear_cache, get_cached_object

# Import Rust pickle functions
try:
    from ._diskcache_rs import rust_pickle_dumps, rust_pickle_loads
except ImportError:
    rust_pickle_dumps = None
    rust_pickle_loads = None

__version__ = "0.1.0"
__all__ = [
    "Cache",
    "FanoutCache",
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
