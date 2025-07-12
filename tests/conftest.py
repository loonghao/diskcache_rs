"""
Pytest configuration and fixtures for diskcache_rs tests
"""

import gc
import os
import platform
import shutil
import tempfile
import time

import pytest


def force_cleanup_directory(directory):
    """Force cleanup of directory, handling Windows file locks"""
    if not os.path.exists(directory):
        return

    # Force garbage collection to release any file handles
    gc.collect()

    # On Windows, wait a bit for file handles to be released
    if platform.system() == "Windows":
        time.sleep(0.1)

    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            shutil.rmtree(directory)
            break
        except (OSError, PermissionError) as e:
            if attempt == max_attempts - 1:
                # Last attempt failed, log the error but don't fail the test
                print(f"Warning: Could not clean up {directory}: {e}")
                break

            # Wait and try again
            time.sleep(0.2 * (attempt + 1))
            gc.collect()


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup fixture that runs after each test"""
    yield

    # Force garbage collection to release file handles
    gc.collect()

    # On Windows, give a bit more time for file handles to be released
    if platform.system() == "Windows":
        time.sleep(0.05)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing"""
    temp_dir = tempfile.mkdtemp(prefix="diskcache_rs_test_")
    yield temp_dir
    # Cleanup with retry logic for Windows
    force_cleanup_directory(temp_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance for testing"""
    from diskcache_rs import Cache

    return Cache(
        temp_cache_dir,
        max_size=1024 * 1024,  # 1MB
        max_entries=1000,
    )


@pytest.fixture
def large_cache(temp_cache_dir):
    """Create a larger cache instance for performance testing"""
    from diskcache_rs import Cache

    return Cache(
        temp_cache_dir,
        max_size=100 * 1024 * 1024,  # 100MB
        max_entries=10000,
    )


@pytest.fixture
def cloud_cache_dir():
    """Create cache directory on cloud drive if available"""
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_test"

    if os.path.exists("Z:\\"):
        os.makedirs(cloud_path, exist_ok=True)
        yield cloud_path
        # Cleanup with retry logic
        force_cleanup_directory(cloud_path)
    else:
        pytest.skip("Cloud drive Z: not available")


@pytest.fixture
def cloud_cache(cloud_cache_dir):
    """Create a cache instance on cloud drive"""
    from diskcache_rs import Cache

    return Cache(
        cloud_cache_dir,
        max_size=10 * 1024 * 1024,  # 10MB
        max_entries=1000,
    )


@pytest.fixture
def sample_data():
    """Sample test data"""
    return {
        "small": b"Hello, World!",
        "medium": b"x" * 1024,  # 1KB
        "large": b"x" * (10 * 1024),  # 10KB
        "json_like": b'{"key": "value", "number": 42}',
        "binary": bytes(range(256)),
    }


@pytest.fixture(scope="session")
def benchmark_data():
    """Data for benchmark tests"""
    return {
        "keys": [f"benchmark_key_{i}" for i in range(1000)],
        "values": [f"benchmark_value_{i}".encode() * 10 for i in range(1000)],
        "large_value": b"x" * (100 * 1024),  # 100KB
    }
