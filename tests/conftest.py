"""
Pytest configuration and fixtures for diskcache_rs tests
"""

import pytest
import tempfile
import os
import shutil
from pathlib import Path

import diskcache_rs


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache testing"""
    temp_dir = tempfile.mkdtemp(prefix="diskcache_rs_test_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance for testing"""
    return diskcache_rs.PyCache(
        temp_cache_dir,
        max_size=1024 * 1024,  # 1MB
        max_entries=1000
    )


@pytest.fixture
def large_cache(temp_cache_dir):
    """Create a larger cache instance for performance testing"""
    return diskcache_rs.PyCache(
        temp_cache_dir,
        max_size=100 * 1024 * 1024,  # 100MB
        max_entries=10000
    )


@pytest.fixture
def cloud_cache_dir():
    """Create cache directory on cloud drive if available"""
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_test"
    
    if os.path.exists("Z:\\"):
        os.makedirs(cloud_path, exist_ok=True)
        yield cloud_path
        # Cleanup
        if os.path.exists(cloud_path):
            shutil.rmtree(cloud_path)
    else:
        pytest.skip("Cloud drive Z: not available")


@pytest.fixture
def cloud_cache(cloud_cache_dir):
    """Create a cache instance on cloud drive"""
    return diskcache_rs.PyCache(
        cloud_cache_dir,
        max_size=10 * 1024 * 1024,  # 10MB
        max_entries=1000
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
