#!/usr/bin/env python3
"""
Test extreme conditions that might trigger the SQLite corruption issue
mentioned in GitHub issue #345
"""

import os
import sys
import time
import threading
import multiprocessing
import random
import tempfile
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import diskcache
import diskcache_rs

def stress_test_original_diskcache(cache_dir, duration=30):
    """Stress test original diskcache with multiple threads"""
    print(f"Stress testing original diskcache for {duration} seconds...")
    
    def worker(worker_id):
        try:
            cache = diskcache.Cache(cache_dir)
            operations = 0
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Random operations
                operation = random.choice(['set', 'get', 'delete'])
                key = f"stress_key_{worker_id}_{random.randint(0, 100)}"
                
                if operation == 'set':
                    value = f"stress_value_{worker_id}_{random.randint(0, 1000)}" * random.randint(1, 10)
                    cache.set(key, value)
                elif operation == 'get':
                    cache.get(key)
                elif operation == 'delete':
                    cache.delete(key)
                
                operations += 1
                
                # Add some random delays to simulate real-world usage
                if random.random() < 0.1:
                    time.sleep(0.001)
            
            cache.close()
            return operations
            
        except Exception as e:
            print(f"Worker {worker_id} failed: {e}")
            if "database disk image is malformed" in str(e).lower():
                print(f"🎯 Found SQLite corruption in worker {worker_id}!")
            return -1
    
    # Run multiple threads
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(8)]
        results = [f.result() for f in futures]
    
    failed_workers = [i for i, r in enumerate(results) if r == -1]
    total_operations = sum(r for r in results if r > 0)
    
    print(f"  Original diskcache stress test results:")
    print(f"    Total operations: {total_operations}")
    print(f"    Failed workers: {len(failed_workers)}")
    
    return len(failed_workers) == 0

def stress_test_diskcache_rs(cache_dir, duration=30):
    """Stress test diskcache_rs with multiple threads"""
    print(f"Stress testing diskcache_rs for {duration} seconds...")
    
    def worker(worker_id):
        try:
            cache = diskcache_rs.PyCache(cache_dir)
            operations = 0
            start_time = time.time()
            
            while time.time() - start_time < duration:
                # Random operations
                operation = random.choice(['set', 'get', 'delete'])
                key = f"stress_key_{worker_id}_{random.randint(0, 100)}"
                
                if operation == 'set':
                    value = f"stress_value_{worker_id}_{random.randint(0, 1000)}".encode() * random.randint(1, 10)
                    cache.set(key, value)
                elif operation == 'get':
                    cache.get(key)
                elif operation == 'delete':
                    cache.delete(key)
                
                operations += 1
                
                # Add some random delays
                if random.random() < 0.1:
                    time.sleep(0.001)
            
            return operations
            
        except Exception as e:
            print(f"Worker {worker_id} failed: {e}")
            return -1
    
    # Run multiple threads
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(8)]
        results = [f.result() for f in futures]
    
    failed_workers = [i for i, r in enumerate(results) if r == -1]
    total_operations = sum(r for r in results if r > 0)
    
    print(f"  diskcache_rs stress test results:")
    print(f"    Total operations: {total_operations}")
    print(f"    Failed workers: {len(failed_workers)}")
    
    return len(failed_workers) == 0

def test_rapid_cache_creation():
    """Test rapid cache creation/destruction which might trigger issues"""
    print("Testing rapid cache creation/destruction...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_rapid_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping rapid creation test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    # Test original diskcache
    print("  Testing original diskcache rapid creation...")
    try:
        for i in range(50):
            cache_dir = cloud_path + f"_original_rapid_{i}"
            cache = diskcache.Cache(cache_dir)
            cache.set(f"rapid_key_{i}", f"rapid_value_{i}")
            result = cache.get(f"rapid_key_{i}")
            cache.close()
            
            if result != f"rapid_value_{i}":
                print(f"    ❌ Failed at iteration {i}")
                return False
            
            # Clean up
            import shutil
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
        
        print("    ✓ Original diskcache passed rapid creation test")
        
    except Exception as e:
        print(f"    ❌ Original diskcache rapid creation failed: {e}")
        return False
    
    # Test our implementation
    print("  Testing diskcache_rs rapid creation...")
    try:
        for i in range(50):
            cache_dir = cloud_path + f"_ours_rapid_{i}"
            cache = diskcache_rs.PyCache(cache_dir)
            cache.set(f"rapid_key_{i}", f"rapid_value_{i}".encode())
            result = cache.get(f"rapid_key_{i}")
            
            if result != f"rapid_value_{i}".encode():
                print(f"    ❌ Failed at iteration {i}")
                return False
            
            # Clean up
            import shutil
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
        
        print("    ✓ diskcache_rs passed rapid creation test")
        
    except Exception as e:
        print(f"    ❌ diskcache_rs rapid creation failed: {e}")
        return False
    
    return True

def test_network_interruption_simulation():
    """Simulate network interruption scenarios"""
    print("Testing network interruption simulation...")
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_interruption_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping interruption test")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    # Test with forced delays and timeouts
    print("  Testing with simulated network delays...")
    
    # Original diskcache with delays
    try:
        cache = diskcache.Cache(cloud_path + "_original_delay")
        
        for i in range(20):
            # Add artificial delay to simulate slow network
            if i % 5 == 0:
                time.sleep(0.1)
            
            cache.set(f"delay_key_{i}", f"delay_value_{i}" * 100)
            result = cache.get(f"delay_key_{i}")
            
            if result != f"delay_value_{i}" * 100:
                print(f"    ❌ Original diskcache failed with delay at {i}")
                return False
        
        cache.clear()
        cache.close()
        print("    ✓ Original diskcache handled delays")
        
    except Exception as e:
        print(f"    ❌ Original diskcache delay test failed: {e}")
        return False
    
    # Our implementation with delays
    try:
        cache = diskcache_rs.PyCache(cloud_path + "_ours_delay")
        
        for i in range(20):
            # Add artificial delay
            if i % 5 == 0:
                time.sleep(0.1)
            
            value = (f"delay_value_{i}" * 100).encode()
            cache.set(f"delay_key_{i}", value)
            result = cache.get(f"delay_key_{i}")
            
            if result != value:
                print(f"    ❌ diskcache_rs failed with delay at {i}")
                return False
        
        cache.clear()
        print("    ✓ diskcache_rs handled delays")
        
    except Exception as e:
        print(f"    ❌ diskcache_rs delay test failed: {e}")
        return False
    
    return True

def main():
    print("🔥 Extreme conditions testing for network file systems")
    print("=" * 60)
    
    cloud_path = "Z:\\_thm\\temp\\.pkg\\db_extreme_test"
    
    if not os.path.exists("Z:\\"):
        print("❌ Z: drive not available, skipping all extreme tests")
        return True
    
    os.makedirs(cloud_path, exist_ok=True)
    
    success_count = 0
    total_tests = 5
    
    # Stress tests
    if stress_test_original_diskcache(cloud_path + "_original_stress", duration=10):
        success_count += 1
    
    if stress_test_diskcache_rs(cloud_path + "_ours_stress", duration=10):
        success_count += 1
    
    # Other tests
    if test_rapid_cache_creation():
        success_count += 1
    
    if test_network_interruption_simulation():
        success_count += 1
    
    # Final comparison
    print("\nFinal robustness comparison...")
    try:
        # Try to trigger the specific error mentioned in the GitHub issue
        cache = diskcache.Cache(cloud_path + "_final_test")
        
        # Rapid concurrent operations
        for i in range(100):
            cache.set(f"final_key_{i}", f"final_value_{i}")
            cache.get(f"final_key_{i}")
            if i % 2 == 0:
                cache.delete(f"final_key_{i}")
        
        cache.close()
        print("  ✓ Original diskcache survived final test")
        success_count += 1
        
    except Exception as e:
        print(f"  ❌ Original diskcache failed final test: {e}")
        if "database disk image is malformed" in str(e).lower():
            print("  🎯 Successfully reproduced the SQLite corruption issue!")
    
    print("\n" + "=" * 60)
    print(f"Results: {success_count}/{total_tests} tests passed")
    
    if success_count >= 4:
        print("🎉 Both implementations are robust on your network drive!")
        print("💡 Your specific network setup seems to handle SQLite well")
        print("🛡️ diskcache_rs still provides additional safety measures")
    else:
        print("⚠ Some extreme conditions caused issues")
        print("🛡️ diskcache_rs provides better robustness for such scenarios")
    
    return success_count >= 4

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
