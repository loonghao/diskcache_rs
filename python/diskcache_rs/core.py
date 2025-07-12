"""
Core module that provides access to the Rust implementation
"""


def get_rust_cache():
    """Get the Rust PyCache class"""
    try:
        # Import the compiled Rust module directly (avoid circular import)
        from diskcache_rs import _diskcache_rs

        # Ensure we get the PyCache class that returns dict from stats()
        if hasattr(_diskcache_rs, "PyCache"):
            return _diskcache_rs.PyCache
        else:
            raise ImportError("PyCache class not found in _diskcache_rs module")

    except ImportError as e:
        raise ImportError(
            f"Could not import the compiled diskcache_rs module: {e}"
        ) from e
    except AttributeError as e:
        raise ImportError(
            f"PyCache class not available in _diskcache_rs module: {e}"
        ) from e


def get_rust_fanout_cache():
    """Get the Rust FanoutCache class"""
    try:
        # Import the compiled Rust module directly (avoid circular import)
        from diskcache_rs import _diskcache_rs

        return _diskcache_rs.FanoutCache
    except ImportError as e:
        raise ImportError(
            f"Could not import the compiled diskcache_rs module: {e}"
        ) from e


__all__ = ["get_rust_cache", "get_rust_fanout_cache"]
