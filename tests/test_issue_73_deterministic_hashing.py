"""
Tests for issue #73: Randomized hashing causes cache misses across Python process restarts.

This test suite verifies that the FanoutCache and FastFanoutCache use deterministic
hashing for shard assignment, ensuring cache persistence across process restarts.
"""

import hashlib
import os
import subprocess
import sys
import tempfile

import pytest

from diskcache_rs import Cache, FanoutCache
from diskcache_rs.fast_cache import FastFanoutCache


class TestDeterministicShardAssignment:
    """Test that shard assignment is deterministic across calls and processes."""

    def test_fanout_cache_shard_consistency(self):
        """Test that _get_shard returns the same shard for the same key every time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=8)

            # Verify that the same key always maps to the same shard
            for key in ["test_key", "another_key", "hello", "world", "foo", "bar"]:
                shard1 = cache._get_shard(key)
                shard2 = cache._get_shard(key)
                assert shard1 is shard2, (
                    f"Shard assignment for key '{key}' is not consistent"
                )

            cache.close()

    def test_fast_fanout_cache_shard_consistency(self):
        """Test that FastFanoutCache._get_shard is deterministic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FastFanoutCache(tmpdir, shards=8)

            for key in ["test_key", "another_key", "hello", "world"]:
                shard1 = cache._get_shard(key)
                shard2 = cache._get_shard(key)
                assert shard1 is shard2, (
                    f"Shard assignment for key '{key}' is not consistent"
                )

            cache.close()

    def test_fanout_cache_shard_does_not_use_builtin_hash(self):
        """Verify that _get_shard does NOT use Python's built-in hash().

        Python's hash() is randomized per process (PYTHONHASHSEED), so if
        we were using it, different processes would get different shard indices.
        We verify this by computing the expected shard index from a deterministic
        hash (BLAKE2b) and comparing.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FanoutCache(tmpdir, shards=16)

            for key in ["key1", "key2", "key3", "test", "cache_key_123"]:
                # Compute expected shard using BLAKE2b (same as implementation)
                h = hashlib.blake2b(key.encode(), digest_size=8).digest()
                expected_index = int.from_bytes(h, byteorder="little") % 16

                # Get actual shard and determine its index
                shard = cache._get_shard(key)
                actual_index = cache._caches.index(shard)

                assert actual_index == expected_index, (
                    f"Key '{key}': expected shard {expected_index}, got {actual_index}"
                )

            cache.close()

    def test_fast_fanout_cache_shard_does_not_use_builtin_hash(self):
        """Same test for FastFanoutCache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = FastFanoutCache(tmpdir, shards=16)

            for key in ["key1", "key2", "key3", "test", "cache_key_123"]:
                h = hashlib.blake2b(key.encode(), digest_size=8).digest()
                expected_index = int.from_bytes(h, byteorder="little") % 16

                shard = cache._get_shard(key)
                actual_index = cache._caches.index(shard)

                assert actual_index == expected_index, (
                    f"Key '{key}': expected shard {expected_index}, got {actual_index}"
                )

            cache.close()


class TestCrossPersistenceFanoutCache:
    """Test that FanoutCache data persists across cache instance recreations."""

    def test_fanout_cache_persistence_same_process(self):
        """Test that FanoutCache keys are retrievable after close and reopen."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_data = {
                "key1": "value1",
                "key2": "value2",
                "key3": "value3",
                "key_with_special_chars": "special!@#$%",
                "numeric_key_42": 12345,
            }

            # Write data
            cache = FanoutCache(tmpdir, shards=8)
            for key, value in test_data.items():
                cache.set(key, value)
            cache.close()

            # Read data with a new instance
            cache2 = FanoutCache(tmpdir, shards=8)
            for key, expected_value in test_data.items():
                actual = cache2.get(key)
                assert actual == expected_value, (
                    f"Key '{key}': expected {expected_value!r}, got {actual!r}"
                )
            cache2.close()

    def test_fanout_cache_persistence_many_keys(self):
        """Test persistence with many keys to exercise multiple shards."""
        with tempfile.TemporaryDirectory() as tmpdir:
            num_keys = 200
            keys = [f"key_{i}" for i in range(num_keys)]
            values = [f"value_{i}" for i in range(num_keys)]

            # Write phase
            cache = FanoutCache(tmpdir, shards=16)
            for k, v in zip(keys, values):
                cache.set(k, v)
            cache.close()

            # Read phase (new instance)
            cache2 = FanoutCache(tmpdir, shards=16)
            found = 0
            for k, expected_v in zip(keys, values):
                actual = cache2.get(k)
                if actual == expected_v:
                    found += 1
                else:
                    # This should not happen with deterministic hashing
                    pass

            assert found == num_keys, (
                f"Only found {found}/{num_keys} keys after reopen. "
                "Shard assignment may not be deterministic."
            )
            cache2.close()


class TestCrossProcessPersistence:
    """Test that cache data persists across separate Python process invocations.

    This is the core test for issue #73 - verifying that randomized hashing
    does NOT cause cache misses across process restarts.
    """

    def test_fanout_cache_cross_process(self):
        """Test FanoutCache persistence across separate Python processes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Script to write data
            write_script = f'''
import sys
sys.path.insert(0, ".")
from diskcache_rs import FanoutCache

cache = FanoutCache({tmpdir!r}, shards=8)
for i in range(50):
    cache.set(f"cross_proc_key_{{i}}", f"cross_proc_value_{{i}}")
cache.close()
print("WRITE_OK")
'''
            # Script to read data
            read_script = f'''
import sys
sys.path.insert(0, ".")
from diskcache_rs import FanoutCache

cache = FanoutCache({tmpdir!r}, shards=8)
found = 0
for i in range(50):
    val = cache.get(f"cross_proc_key_{{i}}")
    if val == f"cross_proc_value_{{i}}":
        found += 1
cache.close()
print(f"FOUND:{{found}}/50")
'''
            # Run write script
            write_result = subprocess.run(
                [sys.executable, "-c", write_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert write_result.returncode == 0, (
                f"Write script failed: {write_result.stderr}"
            )
            assert "WRITE_OK" in write_result.stdout

            # Run read script (separate process)
            read_result = subprocess.run(
                [sys.executable, "-c", read_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert read_result.returncode == 0, (
                f"Read script failed: {read_result.stderr}"
            )

            # Parse result
            output = read_result.stdout.strip()
            assert "FOUND:50/50" in output, (
                f"Cross-process cache read failed. Got: {output}. "
                "This indicates non-deterministic hashing (issue #73)."
            )

    def test_fanout_cache_cross_process_with_random_pythonhashseed(self):
        """Test persistence even when PYTHONHASHSEED differs between processes.

        This explicitly sets different PYTHONHASHSEED values to prove that
        our deterministic hashing is independent of Python's hash randomization.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            write_script = f'''
import sys
sys.path.insert(0, ".")
from diskcache_rs import FanoutCache

cache = FanoutCache({tmpdir!r}, shards=8)
for i in range(30):
    cache.set(f"hashseed_key_{{i}}", f"hashseed_value_{{i}}")
cache.close()
print("WRITE_OK")
'''
            read_script = f'''
import sys
sys.path.insert(0, ".")
from diskcache_rs import FanoutCache

cache = FanoutCache({tmpdir!r}, shards=8)
found = 0
for i in range(30):
    val = cache.get(f"hashseed_key_{{i}}")
    if val == f"hashseed_value_{{i}}":
        found += 1
cache.close()
print(f"FOUND:{{found}}/30")
'''
            # Write with PYTHONHASHSEED=12345
            env_write = os.environ.copy()
            env_write["PYTHONHASHSEED"] = "12345"
            write_result = subprocess.run(
                [sys.executable, "-c", write_script],
                capture_output=True,
                text=True,
                timeout=30,
                env=env_write,
            )
            assert write_result.returncode == 0, (
                f"Write script failed: {write_result.stderr}"
            )

            # Read with PYTHONHASHSEED=99999 (different!)
            env_read = os.environ.copy()
            env_read["PYTHONHASHSEED"] = "99999"
            read_result = subprocess.run(
                [sys.executable, "-c", read_script],
                capture_output=True,
                text=True,
                timeout=30,
                env=env_read,
            )
            assert read_result.returncode == 0, (
                f"Read script failed: {read_result.stderr}"
            )

            output = read_result.stdout.strip()
            assert "FOUND:30/30" in output, (
                f"Cross-process read with different PYTHONHASHSEED failed. Got: {output}. "
                "The shard assignment is still dependent on PYTHONHASHSEED."
            )


class TestShardDistribution:
    """Test that the deterministic hash provides reasonable distribution."""

    def test_shard_distribution_is_reasonable(self):
        """Verify that keys are distributed across shards, not all in one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            num_shards = 8
            cache = FanoutCache(tmpdir, shards=num_shards)

            shard_counts = [0] * num_shards
            for i in range(1000):
                key = f"distribution_test_key_{i}"
                shard = cache._get_shard(key)
                shard_idx = cache._caches.index(shard)
                shard_counts[shard_idx] += 1

            cache.close()

            # Each shard should have at least some keys
            # With 1000 keys and 8 shards, expected ~125 per shard
            for i, count in enumerate(shard_counts):
                assert count > 0, f"Shard {i} has no keys - distribution is broken"
                # Allow generous range but ensure no extreme skew
                assert count < 500, (
                    f"Shard {i} has {count}/1000 keys - distribution is heavily skewed"
                )

    def test_same_keys_always_same_shard(self):
        """Verify the same key set always produces the same shard assignment."""
        with tempfile.TemporaryDirectory() as tmpdir1, \
             tempfile.TemporaryDirectory() as tmpdir2:

            cache1 = FanoutCache(tmpdir1, shards=8)
            cache2 = FanoutCache(tmpdir2, shards=8)

            for i in range(100):
                key = f"consistency_key_{i}"
                idx1 = cache1._caches.index(cache1._get_shard(key))
                idx2 = cache2._caches.index(cache2._get_shard(key))
                assert idx1 == idx2, (
                    f"Key '{key}' maps to shard {idx1} in cache1 but {idx2} in cache2"
                )

            cache1.close()
            cache2.close()


class TestIssue73Reproduction:
    """Reproduce the exact scenario from issue #73."""

    def test_original_issue_scenario(self):
        """Reproduce the issue scenario: write in one session, read in another."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate writing in one "session"
            cache = FanoutCache(tmpdir, shards=16)
            keys = [str((i % 50, i % 4)) for i in range(100)]
            for key in keys:
                cache.set(key, [1, 2, 3])
            cache.close()

            # Simulate reading in another "session"
            cache2 = FanoutCache(tmpdir, shards=16)
            found = sum(1 for key in keys if cache2.get(key) is not None)
            cache2.close()

            assert found == len(keys), (
                f"Found {found}/{len(keys)} keys after reopen. "
                "This is the exact issue #73 scenario."
            )

    def test_string_tuple_keys(self):
        """Test with the exact key format from the issue report."""
        import random

        with tempfile.TemporaryDirectory() as tmpdir:
            random.seed(42)  # Deterministic for test reproducibility
            keys = [str((random.randint(1, 50), random.randint(0, 3)))
                    for _ in range(200)]
            # Deduplicate
            keys = list(set(keys))

            # Write
            cache = FanoutCache(tmpdir, shards=16)
            for key in keys:
                cache.set(key, [1, 2, 3] * 10)
            cache.close()

            # Read with new instance
            cache2 = FanoutCache(tmpdir, shards=16)
            found = sum(1 for key in keys if cache2.get(key) is not None)
            cache2.close()

            assert found == len(keys), (
                f"Found {found}/{len(keys)} keys. "
                "String tuple keys should be fully persistent."
            )
