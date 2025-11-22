"""
Example demonstrating support for special characters in cache keys

This example shows how diskcache_rs now supports keys containing
special characters like :, /, \\, . and more.
"""

import tempfile
from diskcache_rs import Cache


def main():
    # Create a temporary cache directory
    with tempfile.TemporaryDirectory() as tmpdir:
        cache = Cache(tmpdir)

        print("=" * 60)
        print("diskcache_rs - Special Characters in Keys Support")
        print("=" * 60)
        print()

        # Example 1: URL as cache key
        print("1. Using URLs as cache keys:")
        url = "https://api.example.com/v1/users/123?include=profile"
        response_data = {
            "user_id": 123,
            "name": "John Doe",
            "email": "john@example.com"
        }
        cache.set(url, response_data)
        print(f"   Key: {url}")
        print(f"   Value: {cache.get(url)}")
        print()

        # Example 2: Namespace with colons
        print("2. Using namespace notation with colons:")
        key = "app:config:database:host"
        value = "localhost:5432"
        cache.set(key, value)
        print(f"   Key: {key}")
        print(f"   Value: {cache.get(key)}")
        print()

        # Example 3: File paths as keys
        print("3. Using file paths as keys:")
        windows_path = "C:\\Users\\Admin\\Documents\\file.txt"
        unix_path = "/home/user/documents/file.txt"
        cache.set(windows_path, "Windows file content")
        cache.set(unix_path, "Unix file content")
        print(f"   Windows path: {windows_path}")
        print(f"   Value: {cache.get(windows_path)}")
        print(f"   Unix path: {unix_path}")
        print(f"   Value: {cache.get(unix_path)}")
        print()

        # Example 4: Dot notation (config keys)
        print("4. Using dot notation for configuration:")
        config_keys = {
            "app.name": "MyApp",
            "app.version": "1.0.0",
            "database.host": "localhost",
            "database.port": 5432,
        }
        for key, value in config_keys.items():
            cache.set(key, value)
            print(f"   {key} = {cache.get(key)}")
        print()

        # Example 5: Mixed special characters
        print("5. Complex keys with multiple special characters:")
        complex_keys = [
            "user@domain.com:session:2024-01-01",
            "file://server/share/path/to/file.txt",
            "redis://localhost:6379/0",
        ]
        for i, key in enumerate(complex_keys):
            cache.set(key, f"value_{i}")
            print(f"   Key: {key}")
            print(f"   Value: {cache.get(key)}")
        print()

        # Example 6: Auto-deserialization
        print("6. Auto-deserialization support:")

        # Store Python objects (automatically pickled)
        cache.set("python_dict", {"nested": {"data": [1, 2, 3]}})
        print(f"   Python dict: {cache.get('python_dict')}")

        # Store JSON data (automatically detected and parsed)
        import json
        json_bytes = json.dumps({"type": "json", "value": 42}).encode('utf-8')
        cache._cache.set("json_data", json_bytes, expire_time=None, tags=[])
        print(f"   JSON data: {cache.get('json_data')}")

        # Store plain text (automatically decoded)
        text_bytes = "Hello, World!".encode('utf-8')
        cache._cache.set("text_data", text_bytes, expire_time=None, tags=[])
        print(f"   Text data: {cache.get('text_data')}")
        print()

        print("=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)


if __name__ == "__main__":
    main()
