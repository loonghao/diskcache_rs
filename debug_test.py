#!/usr/bin/env python3

import tempfile
import os


def test_cache():
    # Test with the exact same import order as the failing test
    import diskcache
    from diskcache_rs import Cache

    print(f"diskcache module: {diskcache}")
    print(f"diskcache.Cache: {diskcache.Cache}")
    print(f"diskcache_rs.Cache: {Cache}")

    with tempfile.TemporaryDirectory() as temp_dir:
        rs_cache = Cache(temp_dir)
        dc_cache = diskcache.Cache(temp_dir + "_dc")

        print(f"rs_cache type: {type(rs_cache)}")
        print(f"dc_cache type: {type(dc_cache)}")
        print(f"rs_cache has exists: {hasattr(rs_cache, 'exists')}")
        print(f"dc_cache has exists: {hasattr(dc_cache, 'exists')}")

        nonexistent_key = "this_key_does_not_exist"

        # Test the exact same operations as in the failing test
        rs_result = rs_cache.get(nonexistent_key)
        dc_result = dc_cache.get(nonexistent_key)
        print(f"rs_cache get result: {rs_result}")
        print(f"dc_cache get result: {dc_result}")

        # This is the line that fails in the test
        try:
            result = nonexistent_key not in rs_cache
            print(f"rs_cache 'not in' result: {result}")
        except Exception as e:
            print(f"Error in rs_cache 'not in': {e}")
            import traceback

            traceback.print_exc()

        try:
            result = not dc_cache.exists(nonexistent_key)
            print(f"dc_cache exists result: {result}")
        except Exception as e:
            print(f"Error in dc_cache exists: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_cache()
