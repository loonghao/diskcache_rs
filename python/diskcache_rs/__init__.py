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

# Version is managed by maturin and synced from Cargo.toml
try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    # Python 3.7 fallback
    from importlib_metadata import version, PackageNotFoundError  # type: ignore

try:
    __version__ = version("diskcache_rs")
except PackageNotFoundError:
    # Development mode fallback - read from Cargo.toml
    import re
    from pathlib import Path

    cargo_toml = Path(__file__).parent.parent.parent / "Cargo.toml"
    if cargo_toml.exists():
        content = cargo_toml.read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
        if match:
            __version__ = match.group(1) + "-dev"
        else:
            __version__ = "0.0.0-dev"
    else:
        __version__ = "0.0.0-dev"
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
