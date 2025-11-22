"""
Test support for special characters in cache keys
"""

import json
import pickle
import tempfile
from pathlib import Path

import pytest

from diskcache_rs import Cache


class TestSpecialCharKeys:
    """Test cache with special characters in keys"""

    def test_key_with_colon(self):
        """Test keys containing colon character"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with colon in key
            key = "namespace:user:123"
            value = {"user_id": 123, "name": "test"}

            cache.set(key, value)
            result = cache.get(key)

            assert result == value
            assert key in cache

    def test_key_with_slash(self):
        """Test keys containing forward slash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with slash in key
            key = "path/to/resource"
            value = "resource_data"

            cache.set(key, value)
            result = cache.get(key)

            assert result == value
            assert key in cache

    def test_key_with_backslash(self):
        """Test keys containing backslash"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with backslash in key (Windows path style)
            key = "C:\\Users\\test\\file.txt"
            value = "file_content"

            cache.set(key, value)
            result = cache.get(key)

            assert result == value
            assert key in cache

    def test_key_with_dot(self):
        """Test keys containing dot character"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with dot in key
            key = "config.database.host"
            value = "localhost"

            cache.set(key, value)
            result = cache.get(key)

            assert result == value
            assert key in cache

    def test_key_with_multiple_special_chars(self):
        """Test keys with multiple special characters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with multiple special characters
            test_keys = [
                "http://example.com/path?query=1",
                "user@domain.com:password",
                "file://C:\\path\\to\\file",
                "key:with:many:colons",
                "path/with/many/slashes",
                "mixed:path/with\\all",
                "config.app.settings",  # dot notation
                "file.name.with.dots.txt",  # multiple dots
            ]

            for i, key in enumerate(test_keys):
                value = f"value_{i}"
                cache.set(key, value)
                result = cache.get(key)
                assert result == value, f"Failed for key: {key}"
                assert key in cache

    def test_url_as_key(self):
        """Test using URLs as cache keys"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Test with full URL
            url = "https://api.example.com/v1/users/123?include=profile&format=json"
            response_data = {
                "user_id": 123,
                "name": "John Doe",
                "email": "john@example.com"
            }

            cache.set(url, response_data)
            result = cache.get(url)

            assert result == response_data
            assert url in cache


class TestAutoDeserialization:
    """Test automatic deserialization of different formats"""

    def test_pickle_deserialization(self):
        """Test automatic pickle deserialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Store complex Python object
            value = {"list": [1, 2, 3], "dict": {"nested": True}, "tuple": (1, 2)}
            cache.set("test_key", value)
            result = cache.get("test_key")

            assert result == value

    def test_json_deserialization(self):
        """Test automatic JSON deserialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Manually store JSON data
            json_data = {"key": "value", "number": 42}
            json_bytes = json.dumps(json_data).encode('utf-8')

            # Use internal Rust cache to store raw JSON
            cache._cache.set("json_key", json_bytes, expire_time=None, tags=[])

            # Should auto-deserialize JSON
            result = cache.get("json_key")
            assert result == json_data

    def test_text_deserialization(self):
        """Test automatic text deserialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Store plain text
            text = "Hello, World!"
            text_bytes = text.encode('utf-8')

            # Use internal Rust cache to store raw text
            cache._cache.set("text_key", text_bytes, expire_time=None, tags=[])

            # Should auto-deserialize to text
            result = cache.get("text_key")
            assert result == text

    def test_mixed_formats(self):
        """Test cache with mixed serialization formats"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = Cache(tmpdir)

            # Store different formats
            cache.set("pickle_key", {"type": "pickle"})
            cache._cache.set("json_key", b'{"type": "json"}', expire_time=None, tags=[])
            cache._cache.set("text_key", b"plain text", expire_time=None, tags=[])

            # All should deserialize correctly
            assert cache.get("pickle_key") == {"type": "pickle"}
            assert cache.get("json_key") == {"type": "json"}
            assert cache.get("text_key") == "plain text"
