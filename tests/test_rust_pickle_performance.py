"""
Performance and behavior tests for the diskcache_rs pickle helpers.
"""

import importlib
import pickle
import tempfile
import time
from typing import Optional

import pytest

import diskcache_rs.rust_pickle as rust_pickle
from diskcache_rs import Cache, rust_pickle_dumps, rust_pickle_loads


BRIDGE_ENV = "DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE"


def reload_rust_pickle(
    monkeypatch: pytest.MonkeyPatch, enabled: Optional[bool] = None
):
    """Reload the module after changing the bridge toggle."""
    if enabled is None:
        monkeypatch.delenv(BRIDGE_ENV, raising=False)
    elif enabled:
        monkeypatch.setenv(BRIDGE_ENV, "1")
    else:
        monkeypatch.setenv(BRIDGE_ENV, "0")

    return importlib.reload(rust_pickle)


class TestRustPicklePerformance:
    """Test pickle helper behavior and performance."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_rust_pickle_functions(self):
        """Test direct bridge functions and module helpers produce correct values."""
        test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}

        if rust_pickle_dumps is not None:
            pickled = rust_pickle_dumps(test_data)
            unpickled = rust_pickle_loads(pickled)
            assert unpickled == test_data

        module_pickled = rust_pickle.dumps(test_data)
        module_unpickled = rust_pickle.loads(module_pickled)
        assert module_unpickled == test_data

    def test_rust_pickle_availability(self):
        """Test that Rust pickle bridge symbols are available."""
        assert rust_pickle.is_rust_available()
        assert rust_pickle_dumps is not None
        assert rust_pickle_loads is not None

    def test_module_defaults_to_cpython_fast_path(self, monkeypatch):
        """The default helper path should avoid the bridge to minimize overhead."""
        module = reload_rust_pickle(monkeypatch, enabled=None)
        original_dumps = module.pickle.dumps
        original_loads = module.pickle.loads
        observed = {"dumps": 0, "loads": 0}

        def spy_dumps(obj, protocol=pickle.HIGHEST_PROTOCOL):
            observed["dumps"] += 1
            return original_dumps(obj, protocol=protocol)

        def spy_loads(data):
            observed["loads"] += 1
            return original_loads(data)

        def fail_bridge(*_args, **_kwargs):
            raise AssertionError("bridge path should be disabled by default")

        monkeypatch.setattr(module.pickle, "dumps", spy_dumps)
        monkeypatch.setattr(module.pickle, "loads", spy_loads)
        monkeypatch.setattr(
            module,
            "rust_pickle_dumps",
            fail_bridge,
            raising=False,
        )
        monkeypatch.setattr(
            module,
            "rust_pickle_loads",
            fail_bridge,
            raising=False,
        )

        payload = module.dumps({"alpha": 1})
        result = module.loads(payload)

        assert result == {"alpha": 1}
        assert observed == {"dumps": 1, "loads": 1}
        assert module.is_rust_bridge_enabled() is False

    def test_module_can_opt_in_to_rust_bridge(self, monkeypatch):
        """The bridge remains available behind an explicit environment toggle."""
        module = reload_rust_pickle(monkeypatch, enabled=True)
        called = {"dumps": 0, "loads": 0}

        def bridge_dumps(obj):
            called["dumps"] += 1
            return pickle.dumps(obj)

        def bridge_loads(data):
            called["loads"] += 1
            return pickle.loads(data)

        monkeypatch.setattr(module, "rust_pickle_dumps", bridge_dumps, raising=False)
        monkeypatch.setattr(module, "rust_pickle_loads", bridge_loads, raising=False)

        payload = module.dumps({"beta": 2})
        result = module.loads(payload)

        assert result == {"beta": 2}
        assert called == {"dumps": 1, "loads": 1}
        assert module.is_rust_bridge_enabled() is True

    def test_bridge_falls_back_to_cpython_when_bridge_errors(self, monkeypatch):
        """Bridge failures should fall back to standard pickle for correctness."""
        module = reload_rust_pickle(monkeypatch, enabled=True)
        original_dumps = module.pickle.dumps
        original_loads = module.pickle.loads
        observed = {"dumps": 0, "loads": 0}

        def fallback_dumps(obj, protocol=pickle.HIGHEST_PROTOCOL):
            observed["dumps"] += 1
            return original_dumps(obj, protocol=protocol)

        def fallback_loads(data):
            observed["loads"] += 1
            return original_loads(data)

        def boom(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(module, "rust_pickle_dumps", boom, raising=False)
        monkeypatch.setattr(module, "rust_pickle_loads", boom, raising=False)
        monkeypatch.setattr(module.pickle, "dumps", fallback_dumps)
        monkeypatch.setattr(module.pickle, "loads", fallback_loads)

        payload = module.dumps({"gamma": 3})
        result = module.loads(payload)

        assert result == {"gamma": 3}
        assert observed == {"dumps": 1, "loads": 1}

    def test_pickle_compatibility(self, monkeypatch):
        """Test compatibility between helper output and standard pickle."""
        module = reload_rust_pickle(monkeypatch, enabled=None)
        test_cases = [
            "simple string",
            42,
            3.14159,
            [1, 2, 3, "four", 5.0],
            {"nested": {"data": True}, "count": 100},
            (1, "two", 3.0),
            {1, 2, 3, 4, 5},
            b"binary data",
            None,
            True,
            False,
        ]

        for test_data in test_cases:
            helper_pickled = module.dumps(test_data)
            assert pickle.loads(helper_pickled) == test_data

            standard_pickled = pickle.dumps(test_data)
            assert module.loads(standard_pickled) == test_data

    @pytest.mark.benchmark
    def test_pickle_path_performance_comparison(self, monkeypatch):
        """Compare standard pickle, default helper path, and direct bridge path."""
        module = reload_rust_pickle(monkeypatch, enabled=None)
        test_data = {
            "string": "hello world" * 100,
            "numbers": list(range(1000)),
            "nested": {"deep": {"structure": {"with": list(range(100))}}},
            "binary": b"binary data" * 100,
        }
        num_operations = 100

        start_time = time.perf_counter()
        for _ in range(num_operations):
            payload = pickle.dumps(test_data)
            _ = pickle.loads(payload)
        standard_time = time.perf_counter() - start_time

        start_time = time.perf_counter()
        for _ in range(num_operations):
            payload = module.dumps(test_data)
            _ = module.loads(payload)
        helper_time = time.perf_counter() - start_time

        print("\nPickle path comparison (%s operations):" % num_operations)
        print("Standard pickle: %.3fs" % standard_time)
        print("Default helper path: %.3fs" % helper_time)

        if rust_pickle_dumps is not None:
            start_time = time.perf_counter()
            for _ in range(num_operations):
                payload = rust_pickle_dumps(test_data)
                _ = rust_pickle_loads(payload)
            bridge_time = time.perf_counter() - start_time
            print("Direct Rust bridge: %.3fs" % bridge_time)

        assert helper_time >= 0
        assert standard_time >= 0

    @pytest.mark.benchmark
    def test_cache_performance_with_default_pickle_path(
        self, monkeypatch, temp_cache_dir
    ):
        """Cache operations should use the default low-overhead pickle path."""
        reload_rust_pickle(monkeypatch, enabled=None)
        cache = Cache(temp_cache_dir)

        test_data = {
            "key": "value",
            "number": 42,
            "list": list(range(100)),
            "nested": {"data": {"structure": True}},
        }
        num_operations = 500

        print("\nCache performance test (%s operations):" % num_operations)

        start_time = time.perf_counter()
        for i in range(num_operations):
            cache.set("key_%s" % i, test_data)
        set_time = time.perf_counter() - start_time

        start_time = time.perf_counter()
        for i in range(num_operations):
            retrieved = cache.get("key_%s" % i)
            assert retrieved == test_data
        get_time = time.perf_counter() - start_time

        total_time = set_time + get_time
        set_ops_per_sec = num_operations / set_time if set_time > 0 else float("inf")
        get_ops_per_sec = num_operations / get_time if get_time > 0 else float("inf")
        total_ops_per_sec = (
            (2 * num_operations) / total_time if total_time > 0 else float("inf")
        )

        print("Set operations: %.3fs (%.1f ops/sec)" % (set_time, set_ops_per_sec))
        print("Get operations: %.3fs (%.1f ops/sec)" % (get_time, get_ops_per_sec))
        print("Total: %.3fs (%.1f ops/sec)" % (total_time, total_ops_per_sec))

        assert set_time < 10.0
        assert get_time < 1.0

    def test_large_object_handling(self, monkeypatch):
        """Test handling of large objects."""
        module = reload_rust_pickle(monkeypatch, enabled=None)
        large_data = {
            "large_string": "x" * 100000,
            "large_list": list(range(10000)),
            "nested_structure": {
                "key_%s" % i: {"data": list(range(100))} for i in range(100)
            },
        }

        start_time = time.time()
        pickled = module.dumps(large_data)
        unpickled = module.loads(pickled)
        helper_time = time.time() - start_time

        start_time = time.time()
        pickled_std = pickle.dumps(large_data)
        unpickled_std = pickle.loads(pickled_std)
        std_time = time.time() - start_time

        assert unpickled == large_data
        assert unpickled_std == large_data

        print("\nLarge object handling:")
        print("Default helper path: %.3fs" % helper_time)
        print("Standard pickle: %.3fs" % std_time)

        assert helper_time < 5.0
        assert std_time < 5.0

    def test_error_handling(self, monkeypatch):
        """Test error handling in pickle helpers."""
        module = reload_rust_pickle(monkeypatch, enabled=None)

        with pytest.raises((pickle.PickleError, ValueError, TypeError)):
            module.loads(b"invalid pickle data")

        pickled = module.dumps(None)
        unpickled = module.loads(pickled)
        assert unpickled is None

    def test_protocol_compatibility(self, monkeypatch):
        """Test pickle protocol compatibility."""
        module = reload_rust_pickle(monkeypatch, enabled=None)
        test_data = {"test": "data", "number": 123}

        for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
            std_pickled = pickle.dumps(test_data, protocol=protocol)
            assert module.loads(std_pickled) == test_data

            helper_pickled = module.dumps(test_data)
            assert pickle.loads(helper_pickled) == test_data

    def test_cache_integration(self, monkeypatch, temp_cache_dir):
        """Test that Cache integrates with the default helper path."""
        reload_rust_pickle(monkeypatch, enabled=None)
        cache = Cache(temp_cache_dir)

        test_data = {
            "unicode": "test_data 🚀",
            "nested": {
                "list": [1, 2, {"inner": True}],
                "tuple": (1, 2, 3),
                "set": {1, 2, 3},
            },
            "binary": b"\x00\x01\x02\x03",
            "none": None,
            "bool": True,
        }

        cache.set("complex_key", test_data, expire=60)
        retrieved = cache.get("complex_key")

        assert retrieved["unicode"] == test_data["unicode"]
        assert retrieved["nested"]["list"] == test_data["nested"]["list"]
        assert retrieved["nested"]["tuple"] == test_data["nested"]["tuple"]
        assert retrieved["binary"] == test_data["binary"]
        assert retrieved["none"] == test_data["none"]
        assert retrieved["bool"] == test_data["bool"]
