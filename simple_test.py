#!/usr/bin/env python3

import diskcache_rs
import tempfile

print("Testing diskcache_rs...")

try:
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Creating cache in: {temp_dir}")
        cache = diskcache_rs.PyCache(temp_dir)
        print("Cache created successfully!")
        
        # Test basic set/get
        cache.set("hello", b"world")
        result = cache.get("hello")
        print(f"Set 'hello' -> b'world', got: {result}")
        
        if result == b"world":
            print("✓ Basic test passed!")
        else:
            print("✗ Basic test failed!")
            
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
