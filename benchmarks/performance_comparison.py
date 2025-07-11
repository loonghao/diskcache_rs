#!/usr/bin/env python3
"""
Performance comparison between diskcache_rs and python-diskcache
"""

import os
import sys
import time
import tempfile
import statistics
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import diskcache
import diskcache_rs

def benchmark_operation(operation_func, iterations=1000, warmup=100):
    """Benchmark an operation with warmup and multiple runs"""
    
    # Warmup
    for _ in range(warmup):
        operation_func()
    
    # Actual benchmark
    times = []
    for _ in range(iterations):
        start_time = time.perf_counter()
        operation_func()
        end_time = time.perf_counter()
        times.append(end_time - start_time)
    
    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'min': min(times),
        'max': max(times),
        'std': statistics.stdev(times) if len(times) > 1 else 0,
        'total': sum(times),
        'ops_per_sec': iterations / sum(times)
    }

def benchmark_set_operations(cache_dir, implementation='diskcache'):
    """Benchmark set operations"""
    
    if implementation == 'diskcache':
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.PyCache(cache_dir)
    
    test_data = b"benchmark_value_" + b"x" * 100  # ~115 bytes
    counter = 0
    
    def set_operation():
        nonlocal counter
        key = f"benchmark_key_{counter}"
        if implementation == 'diskcache':
            cache.set(key, test_data)
        else:
            cache.set(key, test_data)
        counter += 1
    
    result = benchmark_operation(set_operation, iterations=1000, warmup=100)
    
    if hasattr(cache, 'close'):
        cache.close()
    
    return result

def benchmark_get_operations(cache_dir, implementation='diskcache'):
    """Benchmark get operations"""
    
    if implementation == 'diskcache':
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.PyCache(cache_dir)
    
    # Pre-populate cache
    test_data = b"benchmark_value_" + b"x" * 100
    keys = []
    for i in range(1000):
        key = f"get_benchmark_key_{i}"
        keys.append(key)
        if implementation == 'diskcache':
            cache.set(key, test_data)
        else:
            cache.set(key, test_data)
    
    counter = 0
    
    def get_operation():
        nonlocal counter
        key = keys[counter % len(keys)]
        cache.get(key)
        counter += 1
    
    result = benchmark_operation(get_operation, iterations=1000, warmup=100)
    
    if hasattr(cache, 'close'):
        cache.close()
    
    return result

def benchmark_mixed_operations(cache_dir, implementation='diskcache'):
    """Benchmark mixed read/write operations"""
    
    if implementation == 'diskcache':
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.PyCache(cache_dir)
    
    test_data = b"mixed_benchmark_value_" + b"x" * 100
    counter = 0
    
    def mixed_operation():
        nonlocal counter
        key = f"mixed_key_{counter % 100}"  # Reuse keys to test updates
        
        if counter % 3 == 0:  # 33% writes
            if implementation == 'diskcache':
                cache.set(key, test_data + str(counter).encode())
            else:
                cache.set(key, test_data + str(counter).encode())
        else:  # 67% reads
            cache.get(key)
        
        counter += 1
    
    result = benchmark_operation(mixed_operation, iterations=1000, warmup=100)
    
    if hasattr(cache, 'close'):
        cache.close()
    
    return result

def benchmark_large_values(cache_dir, implementation='diskcache'):
    """Benchmark operations with large values"""
    
    if implementation == 'diskcache':
        cache = diskcache.Cache(cache_dir)
    else:
        cache = diskcache_rs.PyCache(cache_dir)
    
    # 10KB value
    large_data = b"x" * (10 * 1024)
    counter = 0
    
    def large_set_operation():
        nonlocal counter
        key = f"large_key_{counter}"
        if implementation == 'diskcache':
            cache.set(key, large_data)
        else:
            cache.set(key, large_data)
        counter += 1
    
    result = benchmark_operation(large_set_operation, iterations=100, warmup=10)
    
    if hasattr(cache, 'close'):
        cache.close()
    
    return result

def run_benchmarks(test_dir):
    """Run all benchmarks"""
    
    print("🏃 Running Performance Benchmarks")
    print("=" * 60)
    
    benchmarks = [
        ("Set Operations (Small Values)", benchmark_set_operations),
        ("Get Operations (Small Values)", benchmark_get_operations),
        ("Mixed Operations (Read/Write)", benchmark_mixed_operations),
        ("Set Operations (Large Values)", benchmark_large_values),
    ]
    
    results = {}
    
    for benchmark_name, benchmark_func in benchmarks:
        print(f"\n📊 {benchmark_name}")
        print("-" * 40)
        
        # Test original diskcache
        diskcache_dir = os.path.join(test_dir, "diskcache_bench")
        os.makedirs(diskcache_dir, exist_ok=True)
        
        print("Testing python-diskcache...")
        diskcache_result = benchmark_func(diskcache_dir, 'diskcache')
        
        # Test our implementation
        diskcache_rs_dir = os.path.join(test_dir, "diskcache_rs_bench")
        os.makedirs(diskcache_rs_dir, exist_ok=True)
        
        print("Testing diskcache_rs...")
        diskcache_rs_result = benchmark_func(diskcache_rs_dir, 'diskcache_rs')
        
        # Store results
        results[benchmark_name] = {
            'diskcache': diskcache_result,
            'diskcache_rs': diskcache_rs_result
        }
        
        # Print comparison
        print(f"\nResults:")
        print(f"  python-diskcache:")
        print(f"    Mean time: {diskcache_result['mean']*1000:.2f}ms")
        print(f"    Ops/sec: {diskcache_result['ops_per_sec']:.1f}")
        print(f"  diskcache_rs:")
        print(f"    Mean time: {diskcache_rs_result['mean']*1000:.2f}ms")
        print(f"    Ops/sec: {diskcache_rs_result['ops_per_sec']:.1f}")
        
        # Calculate speedup
        speedup = diskcache_result['ops_per_sec'] / diskcache_rs_result['ops_per_sec']
        if speedup > 1:
            print(f"  📈 python-diskcache is {speedup:.2f}x faster")
        else:
            print(f"  📈 diskcache_rs is {1/speedup:.2f}x faster")
        
        # Clean up
        import shutil
        if os.path.exists(diskcache_dir):
            shutil.rmtree(diskcache_dir)
        if os.path.exists(diskcache_rs_dir):
            shutil.rmtree(diskcache_rs_dir)
    
    return results

def print_summary(results):
    """Print benchmark summary"""
    
    print("\n" + "=" * 60)
    print("📋 BENCHMARK SUMMARY")
    print("=" * 60)
    
    print(f"{'Benchmark':<30} {'python-diskcache':<15} {'diskcache_rs':<15} {'Winner':<10}")
    print("-" * 75)
    
    for benchmark_name, result in results.items():
        dc_ops = result['diskcache']['ops_per_sec']
        rs_ops = result['diskcache_rs']['ops_per_sec']
        
        if dc_ops > rs_ops:
            winner = f"diskcache ({dc_ops/rs_ops:.1f}x)"
        else:
            winner = f"diskcache_rs ({rs_ops/dc_ops:.1f}x)"
        
        print(f"{benchmark_name[:29]:<30} {dc_ops:>10.1f} ops/s {rs_ops:>10.1f} ops/s {winner:<10}")
    
    print("\n💡 Notes:")
    print("- python-diskcache is more optimized for read operations")
    print("- diskcache_rs provides better network filesystem support")
    print("- Performance varies based on storage type and network conditions")

def main():
    """Main benchmark runner"""
    
    # Use cloud drive if available, otherwise temp directory
    if os.path.exists("Z:\\"):
        test_dir = "Z:\\_thm\\temp\\.pkg\\db_benchmark"
        print(f"🌩️ Using cloud drive for benchmarks: {test_dir}")
    else:
        test_dir = tempfile.mkdtemp(prefix="diskcache_benchmark_")
        print(f"💾 Using local storage for benchmarks: {test_dir}")
    
    try:
        os.makedirs(test_dir, exist_ok=True)
        
        results = run_benchmarks(test_dir)
        print_summary(results)
        
        print(f"\n🎉 Benchmarks completed!")
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up if using temp directory
        if not test_dir.startswith("Z:"):
            import shutil
            if os.path.exists(test_dir):
                shutil.rmtree(test_dir)

if __name__ == "__main__":
    main()
