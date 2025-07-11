"""
DiskCache RS - A high-performance disk cache implementation in Rust with Python bindings

This module provides a Python interface compatible with python-diskcache,
but implemented in Rust for better performance and network filesystem support.
"""

try:
    # Import the Rust implementation directly
    from diskcache_rs import Cache as _RustCache, FanoutCache as _RustFanoutCache

    # Export them as the main classes
    Cache = _RustCache
    FanoutCache = _RustFanoutCache

except ImportError:
    # Fallback to Python wrapper if Rust module not available
    from .cache import Cache, FanoutCache

__version__ = "0.1.0"
__all__ = ["Cache", "FanoutCache"]

# For backward compatibility
DiskCache = Cache
