"""
Pickle helpers for diskcache_rs.

By default we use CPython's built-in ``pickle`` fast path because the current
Rust bridge still delegates back to Python's pickle module internally. The
bridge remains available for explicit testing and benchmarking via the
``DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE`` environment variable.
"""

import os
import pickle
from typing import Any

# Try to import Rust pickle functions
try:
    from ._diskcache_rs import rust_pickle_dumps, rust_pickle_loads

    RUST_PICKLE_AVAILABLE = True
except ImportError:
    RUST_PICKLE_AVAILABLE = False

_BRIDGE_ENV = "DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}


def is_rust_available() -> bool:
    """Check if the Rust bridge functions are importable."""
    return RUST_PICKLE_AVAILABLE


def is_rust_bridge_enabled() -> bool:
    """Return ``True`` when the Rust pickle bridge is explicitly enabled."""
    if not RUST_PICKLE_AVAILABLE:
        return False

    value = os.getenv(_BRIDGE_ENV, "")
    return value.strip().lower() in _TRUTHY_VALUES


def dumps(obj: Any, protocol: int = pickle.HIGHEST_PROTOCOL) -> bytes:
    """
    Serialize an object.

    The default path uses CPython's pickle implementation directly for best
    end-to-end performance. Set ``DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE=1`` to
    benchmark or debug the Rust bridge path.
    """
    if is_rust_bridge_enabled():
        try:
            return rust_pickle_dumps(obj)
        except Exception:
            pass

    return pickle.dumps(obj, protocol=protocol)


def loads(data: bytes) -> Any:
    """
    Deserialize an object.

    The default path uses CPython's pickle implementation directly for best
    end-to-end performance. Set ``DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE=1`` to
    benchmark or debug the Rust bridge path.
    """
    if is_rust_bridge_enabled():
        try:
            return rust_pickle_loads(data)
        except Exception:
            pass

    return pickle.loads(data)


# For compatibility, expose the same interface as pickle module
HIGHEST_PROTOCOL = pickle.HIGHEST_PROTOCOL
DEFAULT_PROTOCOL = pickle.DEFAULT_PROTOCOL

