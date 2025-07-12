"""
High-performance pickle replacement using Rust backend
"""

import pickle
from typing import Any

# Try to import Rust pickle functions
try:
    from ._diskcache_rs import rust_pickle_dumps, rust_pickle_loads

    RUST_PICKLE_AVAILABLE = True
except ImportError:
    RUST_PICKLE_AVAILABLE = False


def dumps(obj: Any, protocol: int = pickle.HIGHEST_PROTOCOL) -> bytes:
    """
    Serialize an object using high-performance Rust backend if available,
    otherwise fall back to standard pickle.

    Args:
        obj: Object to serialize
        protocol: Pickle protocol version (ignored for Rust implementation)

    Returns:
        Serialized bytes
    """
    if RUST_PICKLE_AVAILABLE:
        try:
            # Use Rust implementation for better performance
            return rust_pickle_dumps(obj)
        except Exception:
            # Fall back to standard pickle on error
            pass

    # Use standard Python pickle
    return pickle.dumps(obj, protocol=protocol)


def loads(data: bytes) -> Any:
    """
    Deserialize an object using high-performance Rust backend if available,
    otherwise fall back to standard pickle.

    Args:
        data: Serialized bytes

    Returns:
        Deserialized object
    """
    if RUST_PICKLE_AVAILABLE:
        try:
            # Use Rust implementation for better performance
            return rust_pickle_loads(data)
        except Exception:
            # Fall back to standard pickle on error
            pass

    # Use standard Python pickle
    return pickle.loads(data)


def is_rust_available() -> bool:
    """Check if Rust pickle implementation is available"""
    return RUST_PICKLE_AVAILABLE


# For compatibility, expose the same interface as pickle module
HIGHEST_PROTOCOL = pickle.HIGHEST_PROTOCOL
DEFAULT_PROTOCOL = pickle.DEFAULT_PROTOCOL
