"""
Core module that provides access to the Rust implementation
"""

def get_rust_cache():
    """Get the Rust PyCache class"""
    # This will be set by the test script
    import sys

    # Look for the compiled module in sys.modules
    for name, module in sys.modules.items():
        if hasattr(module, 'PyCache') and 'diskcache_rs' in name and not name.startswith('diskcache_rs.'):
            return module.PyCache

    raise ImportError("Could not find the compiled diskcache_rs module with PyCache")

__all__ = ["get_rust_cache"]
