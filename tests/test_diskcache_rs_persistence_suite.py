"""Comprehensive test suite for diskcache_rs persistence.

This test suite validates that diskcache_rs correctly persists data to disk
and can reload it after the cache is closed and reopened.

Run with: uv run python test_diskcache_rs_persistence_suite.py
"""
import tempfile
from pathlib import Path
from diskcache_rs import DiskCache


def test_basic_persistence():
    """Test 1: Basic set/get persistence after close/reopen."""
    print("\n" + "=" * 70)
    print("Test 1: Basic Persistence")
    print("=" * 70)

    tmpdir = tempfile.mkdtemp()
    print(f"Cache directory: {tmpdir}")

    # Write data
    cache1 = DiskCache(tmpdir)
    cache1.set('key1', 'value1', expire=3600)
    print(f"✓ Set key1='value1' with expire=3600")
    print(f"  Immediate get: {cache1.get('key1')}")
    cache1.close()
    print(f"✓ Closed cache")

    # Read data after reopen
    cache2 = DiskCache(tmpdir)
    result = cache2.get('key1')
    print(f"  After reopen get: {result}")
    cache2.close()

    # Verify
    if result == 'value1':
        print("✅ PASS: Data persisted correctly")
        return True
    else:
        print(f"❌ FAIL: Expected 'value1', got {result}")
        return False


def test_dict_persistence():
    """Test 2: Dictionary data persistence."""
    print("\n" + "=" * 70)
    print("Test 2: Dictionary Data Persistence")
    print("=" * 70)

    tmpdir = tempfile.mkdtemp()
    print(f"Cache directory: {tmpdir}")

    test_data = {'name': 'test', 'value': 123, 'nested': {'a': 1, 'b': 2}}

    # Write dict
    cache1 = DiskCache(tmpdir)
    cache1.set('dict_key', test_data, expire=3600)
    print(f"✓ Set dict_key={test_data}")
    cache1.close()

    # Read dict after reopen
    cache2 = DiskCache(tmpdir)
    result = cache2.get('dict_key')
    print(f"  After reopen get: {result}")
    cache2.close()

    # Verify
    if result == test_data:
        print("✅ PASS: Dictionary persisted correctly")
        return True
    else:
        print(f"❌ FAIL: Expected {test_data}, got {result}")
        return False


def test_multiple_keys_persistence():
    """Test 3: Multiple keys persistence."""
    print("\n" + "=" * 70)
    print("Test 3: Multiple Keys Persistence")
    print("=" * 70)

    tmpdir = tempfile.mkdtemp()
    print(f"Cache directory: {tmpdir}")

    test_data = {
        'key1': 'value1',
        'key2': {'data': 'value2'},
        'key3': [1, 2, 3],
        'key4': 42,
    }

    # Write multiple keys
    cache1 = DiskCache(tmpdir)
    for key, value in test_data.items():
        cache1.set(key, value, expire=3600)
    print(f"✓ Set {len(test_data)} keys")
    print(f"  Keys before close: {sorted(cache1.keys())}")
    cache1.close()

    # Read all keys after reopen
    cache2 = DiskCache(tmpdir)
    print(f"  Keys after reopen: {sorted(cache2.keys())}")

    all_match = True
    for key, expected_value in test_data.items():
        actual_value = cache2.get(key)
        if actual_value != expected_value:
            print(f"  ❌ {key}: expected {expected_value}, got {actual_value}")
            all_match = False
        else:
            print(f"  ✓ {key}: {actual_value}")

    cache2.close()

    if all_match:
        print("✅ PASS: All keys persisted correctly")
        return True
    else:
        print("❌ FAIL: Some keys did not persist")
        return False


def test_no_expire_persistence():
    """Test 4: Persistence without expire parameter."""
    print("\n" + "=" * 70)
    print("Test 4: Persistence Without Expire Parameter")
    print("=" * 70)

    tmpdir = tempfile.mkdtemp()
    print(f"Cache directory: {tmpdir}")

    # Write without expire
    cache1 = DiskCache(tmpdir)
    cache1.set('no_expire_key', 'no_expire_value')
    print(f"✓ Set no_expire_key='no_expire_value' (no expire param)")
    cache1.close()

    # Read after reopen
    cache2 = DiskCache(tmpdir)
    result = cache2.get('no_expire_key')
    print(f"  After reopen get: {result}")
    cache2.close()

    # Verify
    if result == 'no_expire_value':
        print("✅ PASS: Data without expire persisted correctly")
        return True
    else:
        print(f"❌ FAIL: Expected 'no_expire_value', got {result}")
        return False


def test_file_creation():
    """Test 5: Verify cache files are created on disk."""
    print("\n" + "=" * 70)
    print("Test 5: File Creation Verification")
    print("=" * 70)

    tmpdir = tempfile.mkdtemp()
    print(f"Cache directory: {tmpdir}")

    # Create cache and add data
    cache = DiskCache(tmpdir)
    cache.set('test', 'value', expire=3600)
    cache.close()

    # Check files
    cache_path = Path(tmpdir)
    all_files = list(cache_path.rglob('*'))

    print(f"\nFiles in cache directory:")
    has_files = False
    for item in all_files:
        if item.is_file():
            size = item.stat().st_size
            print(f"  📄 {item.relative_to(cache_path)} ({size:,} bytes)")
            has_files = True
        else:
            print(f"  📁 {item.relative_to(cache_path)}/")

    if has_files:
        print("✅ PASS: Cache files created on disk")
        return True
    else:
        print("❌ FAIL: No cache files found")
        return False


def main():
    """Run all tests and report results."""
    print("\n" + "=" * 70)
    print("DISKCACHE_RS PERSISTENCE TEST SUITE")
    print("=" * 70)
    print("\nThis test suite validates that diskcache_rs correctly persists")
    print("data to disk and can reload it after close/reopen cycles.")

    tests = [
        test_basic_persistence,
        test_dict_persistence,
        test_multiple_keys_persistence,
        test_no_expire_persistence,
        test_file_creation,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"\n❌ EXCEPTION in {test_func.__name__}: {e}")
            results.append((test_func.__name__, False))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! diskcache_rs persistence is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. diskcache_rs has persistence issues.")
        return 1


if __name__ == '__main__':
    exit(main())
