"""
Core module that provides access to the Rust implementation
"""

def get_rust_cache():
    """Get the Rust Cache class"""
    try:
        # Import the compiled Rust module directly
        import diskcache_rs as _rust_module
        return _rust_module.Cache
    except ImportError as e:
        raise ImportError(f"Could not import the compiled diskcache_rs module: {e}")

def get_rust_fanout_cache():
    """Get the Rust FanoutCache class"""
    try:
        # Import the compiled Rust module directly
        import diskcache_rs as _rust_module
        return _rust_module.FanoutCache
    except ImportError as e:
        raise ImportError(f"Could not import the compiled diskcache_rs module: {e}")

__all__ = ["get_rust_cache", "get_rust_fanout_cache"]
