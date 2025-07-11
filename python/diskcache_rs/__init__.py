"""
DiskCache RS - A high-performance disk cache implementation in Rust with Python bindings

This module provides a Python interface compatible with python-diskcache,
but implemented in Rust for better performance and network filesystem support.
"""

from .cache import Cache, FanoutCache

__version__ = "0.1.0"
__all__ = ["Cache", "FanoutCache"]

# For backward compatibility
DiskCache = Cache
