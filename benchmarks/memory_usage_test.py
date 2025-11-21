#!/usr/bin/env python3
"""
Memory usage and efficiency test for diskcache_rs
"""

import psutil
import os
import time
import tempfile
import gc
from typing import Dict, List, Tuple

try:
    from diskcache_rs import Cache as RustCache
except ImportError:
    print("❌ diskcache_rs not available!")
    exit(1)

try:
    import diskcache
    DISKCACHE_AVAILABLE = True
except ImportError:
    DISKCACHE_AVAILABLE = False
    print("⚠️  python-diskcache not available, skipping baseline comparisons")


class MemoryTester:
    def __init__(self):
        self.process = psutil.Process(os.getpid())

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage in MB"""
        memory_info = self.process.memory_info()
        return {
            "rss": memory_info.rss / 1024 / 1024,  # Resident Set Size
            "vms": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
        }

    def measure_memory_growth(self, cache, data_size: int, entry_count: int) -> Dict[str, float]:
        """Measure memory growth as cache is populated"""
        gc.collect()  # Clean up before measurement
        initial_memory = self.get_memory_usage()

        # Generate test data
        test_data = b'x' * data_size

        # Populate cache and measure memory at intervals
        memory_samples = []
        sample_interval = max(1, entry_count // 10)  # 10 samples

        for i in range(entry_count):
            key = f"memory_test_key_{i:06d}"
            cache.set(key, test_data)

            if i % sample_interval == 0:
                current_memory = self.get_memory_usage()
                memory_samples.append({
                    "entries": i + 1,
                    "rss": current_memory["rss"],
                    "vms": current_memory["vms"],
                })

        final_memory = self.get_memory_usage()

        return {
            "initial_rss": initial_memory["rss"],
            "final_rss": final_memory["rss"],
            "rss_growth": final_memory["rss"] - initial_memory["rss"],
            "initial_vms": initial_memory["vms"],
            "final_vms": final_memory["vms"],
            "vms_growth": final_memory["vms"] - initial_memory["vms"],
            "samples": memory_samples,
            "memory_per_entry": (final_memory["rss"] - initial_memory["rss"]) / entry_count,
        }

    def test_memory_efficiency(self, cache, data_sizes: List[Tuple[int, str]], entry_count: int):
        """Test memory efficiency across different data sizes"""
        print(f"\n🧠 Memory Efficiency Test ({entry_count} entries)")
        print("=" * 70)

        for data_size, size_name in data_sizes:
            print(f"\n📊 Testing {size_name} entries...")

            # Clear cache before each test
            cache.clear()
            gc.collect()

            memory_stats = self.measure_memory_growth(cache, data_size, entry_count)

            print(f"Initial memory: {memory_stats['initial_rss']:.1f} MB RSS")
            print(f"Final memory:   {memory_stats['final_rss']:.1f} MB RSS")
            print(f"Memory growth:  {memory_stats['rss_growth']:.1f} MB")
            print(f"Memory/entry:   {memory_stats['memory_per_entry']*1024:.1f} KB")

            # Calculate theoretical minimum memory usage
            theoretical_min = (data_size * entry_count) / 1024 / 1024
            overhead_ratio = memory_stats['rss_growth'] / theoretical_min if theoretical_min > 0 else 0
            print(f"Theoretical min: {theoretical_min:.1f} MB")
            print(f"Overhead ratio:  {overhead_ratio:.2f}x")

    def test_memory_leak(self, cache, iterations: int = 5):
        """Test for memory leaks by repeatedly adding and removing data"""
        print(f"\n🔍 Memory Leak Test ({iterations} iterations)")
        print("=" * 70)

        test_data = b'x' * 1024  # 1KB test data
        entry_count = 1000

        memory_history = []

        for iteration in range(iterations):
            gc.collect()
            initial_memory = self.get_memory_usage()

            # Add entries
            for i in range(entry_count):
                key = f"leak_test_{iteration}_{i:06d}"
                cache.set(key, test_data)

            mid_memory = self.get_memory_usage()

            # Remove entries
            for i in range(entry_count):
                key = f"leak_test_{iteration}_{i:06d}"
                cache.delete(key)

            gc.collect()
            final_memory = self.get_memory_usage()

            memory_history.append({
                "iteration": iteration + 1,
                "initial": initial_memory["rss"],
                "peak": mid_memory["rss"],
                "final": final_memory["rss"],
                "growth": final_memory["rss"] - initial_memory["rss"],
            })

            print(f"Iteration {iteration + 1}: "
                  f"{initial_memory['rss']:.1f} → {mid_memory['rss']:.1f} → {final_memory['rss']:.1f} MB "
                  f"(growth: {final_memory['rss'] - initial_memory['rss']:+.1f} MB)")

        # Analyze leak pattern
        total_growth = sum(m["growth"] for m in memory_history)
        avg_growth = total_growth / iterations

        print(f"\nTotal memory growth: {total_growth:.1f} MB")
        print(f"Average growth/iteration: {avg_growth:.1f} MB")

        if avg_growth > 1.0:  # More than 1MB growth per iteration
            print("⚠️  Potential memory leak detected!")
        else:
            print("✅ No significant memory leak detected")

    def test_concurrent_memory_usage(self, cache_factory, thread_count: int = 4):
        """Test memory usage under concurrent access"""
        print(f"\n🚀 Concurrent Memory Usage Test ({thread_count} threads)")
        print("=" * 70)

        import threading
        import queue

        gc.collect()
        initial_memory = self.get_memory_usage()

        test_data = b'x' * 1024
        entries_per_thread = 500

        def worker_thread(thread_id: int, result_queue: queue.Queue):
            cache = cache_factory()
            for i in range(entries_per_thread):
                key = f"concurrent_{thread_id}_{i:06d}"
                cache.set(key, test_data)
            result_queue.put(f"Thread {thread_id} completed")

        # Start threads
        result_queue = queue.Queue()
        threads = []

        for i in range(thread_count):
            thread = threading.Thread(target=worker_thread, args=(i, result_queue))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        gc.collect()
        final_memory = self.get_memory_usage()

        total_entries = thread_count * entries_per_thread
        memory_growth = final_memory["rss"] - initial_memory["rss"]

        print(f"Initial memory: {initial_memory['rss']:.1f} MB")
        print(f"Final memory:   {final_memory['rss']:.1f} MB")
        print(f"Memory growth:  {memory_growth:.1f} MB")
        print(f"Total entries:  {total_entries}")
        print(f"Memory/entry:   {memory_growth * 1024 / total_entries:.1f} KB")


def main():
    """Main test execution"""
    import argparse

    parser = argparse.ArgumentParser(description="Memory usage test for diskcache_rs")
    parser.add_argument("--entries", type=int, default=1000, help="Number of entries for tests")
    parser.add_argument("--leak-iterations", type=int, default=5, help="Iterations for leak test")

    args = parser.parse_args()

    print("🧠 diskcache_rs Memory Usage Test Suite")
    print("=" * 70)

    tester = MemoryTester()

    # Test data sizes
    data_sizes = [
        (100, "100B"),
        (1024, "1KB"),
        (4096, "4KB"),
        (16384, "16KB"),
    ]

    # Test with diskcache_rs
    with tempfile.TemporaryDirectory() as temp_dir:
        cache = RustCache(temp_dir)

        # Memory efficiency test
        tester.test_memory_efficiency(cache, data_sizes, args.entries)

        # Memory leak test
        tester.test_memory_leak(cache, args.leak_iterations)

        # Concurrent memory test
        def create_cache():
            return RustCache(tempfile.mkdtemp())

        tester.test_concurrent_memory_usage(create_cache)

    print("\n" + "=" * 70)
    print("✅ Memory usage test completed!")


if __name__ == "__main__":
    main()
