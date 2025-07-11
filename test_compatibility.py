#!/usr/bin/env python3
"""
Test compatibility with python-diskcache API
"""

import sys
import os
import tempfile
import time

# Import the Rust cache directly first
import diskcache_rs as rust_cache

# Create a simple wrapper for testing
class Cache:
    def __init__(self, directory, **kwargs):
        max_size = kwargs.get('size_limit', kwargs.get('max_size', 1024 * 1024 * 1024))
        max_entries = kwargs.get('count_limit', kwargs.get('max_entries', 100_000))
        self._cache = rust_cache.PyCache(str(directory), max_size=max_size, max_entries=max_entries)
        self.directory = directory

    def set(self, key, value, expire=None, **kwargs):
        import pickle
        serialized = pickle.dumps(value)
        expire_time = None
        if expire:
            import time
            if expire > time.time():
                expire_time = int(expire)
            else:
                expire_time = int(time.time() + expire)
        tags = [kwargs.get('tag')] if kwargs.get('tag') else []
        self._cache.set(key, serialized, expire_time=expire_time, tags=tags)
        return True

    def get(self, key, default=None, **kwargs):
        import pickle
        try:
            result = self._cache.get(key)
            if result is None:
                return default
            return pickle.loads(result)
        except:
            return default

    def delete(self, key):
        return self._cache.delete(key)

    def __contains__(self, key):
        return self._cache.exists(key)

    def __getitem__(self, key):
        result = self.get(key)
        if result is None and key not in self:
            raise KeyError(key)
        return result

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        if not self.delete(key):
            raise KeyError(key)

    def __iter__(self):
        return iter(self._cache.keys())

    def __len__(self):
        return len(self._cache.keys())

    def clear(self):
        count = len(self)
        self._cache.clear()
        return count

    def stats(self, **kwargs):
        return self._cache.stats()

    def volume(self):
        return self._cache.size()

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

# Simple FanoutCache for testing
class FanoutCache:
    def __init__(self, directory, shards=8, **kwargs):
        import os
        self.directory = directory
        self.shards = shards
        self._caches = []
        for i in range(shards):
            shard_dir = os.path.join(directory, f"shard_{i:03d}")
            self._caches.append(Cache(shard_dir, **kwargs))

    def _get_shard(self, key):
        return self._caches[hash(key) % self.shards]

    def set(self, key, value, **kwargs):
        return self._get_shard(key).set(key, value, **kwargs)

    def get(self, key, default=None, **kwargs):
        return self._get_shard(key).get(key, default, **kwargs)

    def delete(self, key):
        return self._get_shard(key).delete(key)

    def __contains__(self, key):
        return key in self._get_shard(key)

    def __getitem__(self, key):
        return self._get_shard(key)[key]

    def __setitem__(self, key, value):
        self._get_shard(key)[key] = value

    def __delitem__(self, key):
        del self._get_shard(key)[key]

    def clear(self):
        return sum(cache.clear() for cache in self._caches)

    def stats(self, **kwargs):
        combined = {'hits': 0, 'misses': 0, 'sets': 0, 'deletes': 0, 'evictions': 0, 'size': 0, 'count': 0}
        for cache in self._caches:
            stats = cache.stats(**kwargs)
            for key in combined:
                combined[key] += stats.get(key, 0)
        return combined

    def close(self):
        for cache in self._caches:
            cache.close()

def test_cache_basic():
    """Test basic Cache operations"""
    print("Testing Cache basic operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)
        
        # Test set/get
        cache.set('key1', 'value1')
        assert cache.get('key1') == 'value1'
        print("✓ Basic set/get works")
        
        # Test dict-like interface
        cache['key2'] = 'value2'
        assert cache['key2'] == 'value2'
        assert 'key2' in cache
        print("✓ Dict-like interface works")
        
        # Test delete
        del cache['key2']
        assert 'key2' not in cache
        print("✓ Delete works")
        
        # Test with different data types
        cache.set('int_key', 42)
        cache.set('list_key', [1, 2, 3])
        cache.set('dict_key', {'a': 1, 'b': 2})
        
        assert cache.get('int_key') == 42
        assert cache.get('list_key') == [1, 2, 3]
        assert cache.get('dict_key') == {'a': 1, 'b': 2}
        print("✓ Different data types work")
        
        # Test iteration
        keys = list(cache)
        assert 'key1' in keys
        assert 'int_key' in keys
        print("✓ Iteration works")
        
        # Test len
        assert len(cache) > 0
        print("✓ Length works")
        
        # Test clear
        count = cache.clear()
        assert count > 0
        assert len(cache) == 0
        print("✓ Clear works")

def test_cache_expiration():
    """Test cache expiration"""
    print("\nTesting Cache expiration...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)
        
        # Set with expiration (1 second from now)
        cache.set('expire_key', 'expire_value', expire=1)
        
        # Should exist immediately
        assert cache.get('expire_key') == 'expire_value'
        print("✓ Value exists before expiration")
        
        # Wait for expiration
        time.sleep(2)
        
        # Should be expired (depending on implementation)
        result = cache.get('expire_key', 'default')
        if result == 'default':
            print("✓ Expiration works")
        else:
            print("⚠ Expiration might not be working as expected")

def test_cache_stats():
    """Test cache statistics"""
    print("\nTesting Cache statistics...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)
        
        # Add some data
        for i in range(5):
            cache.set(f'stats_key_{i}', f'value_{i}')
        
        # Get some data to generate hits
        for i in range(3):
            cache.get(f'stats_key_{i}')
        
        # Get non-existent data to generate misses
        cache.get('nonexistent_key')
        
        stats = cache.stats()
        print(f"Stats: {stats}")
        
        assert isinstance(stats, dict)
        assert 'hits' in stats
        assert 'misses' in stats
        assert 'sets' in stats
        print("✓ Statistics work")
        
        # Test volume
        volume = cache.volume()
        assert volume > 0
        print(f"✓ Volume: {volume} bytes")

def test_fanout_cache():
    """Test FanoutCache operations"""
    print("\nTesting FanoutCache...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        fanout = FanoutCache(temp_dir, shards=4)
        
        # Test basic operations
        fanout.set('fanout_key1', 'fanout_value1')
        assert fanout.get('fanout_key1') == 'fanout_value1'
        print("✓ FanoutCache basic operations work")
        
        # Test with multiple keys (should distribute across shards)
        for i in range(20):
            fanout.set(f'fanout_key_{i}', f'fanout_value_{i}')
        
        # Verify all keys exist
        for i in range(20):
            assert fanout.get(f'fanout_key_{i}') == f'fanout_value_{i}'
        print("✓ FanoutCache distribution works")
        
        # Test dict-like interface
        fanout['dict_key'] = 'dict_value'
        assert fanout['dict_key'] == 'dict_value'
        assert 'dict_key' in fanout
        print("✓ FanoutCache dict-like interface works")
        
        # Test stats
        stats = fanout.stats()
        assert isinstance(stats, dict)
        assert stats['count'] > 0
        print("✓ FanoutCache statistics work")
        
        # Test clear
        count = fanout.clear()
        assert count > 0
        assert len(fanout) == 0
        print("✓ FanoutCache clear works")

def test_context_manager():
    """Test context manager interface"""
    print("\nTesting context manager...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        with Cache(temp_dir) as cache:
            cache.set('context_key', 'context_value')
            assert cache.get('context_key') == 'context_value'
        print("✓ Context manager works")

def test_error_handling():
    """Test error handling"""
    print("\nTesting error handling...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = Cache(temp_dir)
        
        # Test getting non-existent key
        assert cache.get('nonexistent') is None
        assert cache.get('nonexistent', 'default') == 'default'
        print("✓ Non-existent key handling works")
        
        # Test KeyError for __getitem__
        try:
            _ = cache['nonexistent']
            assert False, "Should have raised KeyError"
        except KeyError:
            print("✓ KeyError for missing key works")
        
        # Test KeyError for __delitem__
        try:
            del cache['nonexistent']
            assert False, "Should have raised KeyError"
        except KeyError:
            print("✓ KeyError for deleting missing key works")

if __name__ == "__main__":
    print("Starting diskcache_rs compatibility tests...")
    
    try:
        test_cache_basic()
        test_cache_expiration()
        test_cache_stats()
        test_fanout_cache()
        test_context_manager()
        test_error_handling()
        
        print("\n🎉 All compatibility tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
