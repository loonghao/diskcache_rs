"""Compare batch write throughput across diskcache_rs and python-diskcache."""

from __future__ import annotations

import statistics
import tempfile
import time

import diskcache
from diskcache_rs import Cache, rust_pickle_dumps
from diskcache_rs._diskcache_rs import PyCache

PAYLOAD = {f"key-{index}": b"x" * 1024 for index in range(500)}
SERIALIZED_PAYLOAD = {key: rust_pickle_dumps(value) for key, value in PAYLOAD.items()}
ROUNDS = 5


def benchmark_diskcache_rs_loop() -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_rs_loop_") as cache_dir:
        cache = Cache(cache_dir)
        start = time.perf_counter()
        for key, value in PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_diskcache_rs_batch() -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_rs_batch_") as cache_dir:
        cache = Cache(cache_dir)
        start = time.perf_counter()
        cache.set_many(PAYLOAD)
        cache.close()
        return time.perf_counter() - start


def benchmark_diskcache_loop() -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_py_loop_") as cache_dir:
        cache = diskcache.Cache(cache_dir)
        start = time.perf_counter()
        for key, value in PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_pycache_loop() -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_pycache_loop_") as cache_dir:
        cache = PyCache(cache_dir)
        start = time.perf_counter()
        for key, value in SERIALIZED_PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_pycache_batch() -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_pycache_batch_") as cache_dir:
        cache = PyCache(cache_dir)
        start = time.perf_counter()
        cache.set_many(list(SERIALIZED_PAYLOAD.items()))
        cache.close()
        return time.perf_counter() - start


def main() -> None:
    rs_loop = [benchmark_diskcache_rs_loop() for _ in range(ROUNDS)]
    rs_batch = [benchmark_diskcache_rs_batch() for _ in range(ROUNDS)]
    py_loop = [benchmark_diskcache_loop() for _ in range(ROUNDS)]
    pycache_loop = [benchmark_pycache_loop() for _ in range(ROUNDS)]
    pycache_batch = [benchmark_pycache_batch() for _ in range(ROUNDS)]

    rs_loop_avg = statistics.mean(rs_loop)
    rs_batch_avg = statistics.mean(rs_batch)
    py_loop_avg = statistics.mean(py_loop)
    pycache_loop_avg = statistics.mean(pycache_loop)
    pycache_batch_avg = statistics.mean(pycache_batch)

    print(f"rs_loop_avg={rs_loop_avg:.6f}")
    print(f"rs_batch_avg={rs_batch_avg:.6f}")
    print(f"py_loop_avg={py_loop_avg:.6f}")
    print(f"pycache_loop_avg={pycache_loop_avg:.6f}")
    print(f"pycache_batch_avg={pycache_batch_avg:.6f}")
    print(f"high_level_batch_speedup_vs_rs_loop={rs_loop_avg / rs_batch_avg:.2f}")
    print(f"low_level_batch_speedup_vs_pycache_loop={pycache_loop_avg / pycache_batch_avg:.2f}")
    print(f"batch_speedup_vs_diskcache_loop={py_loop_avg / rs_batch_avg:.2f}")


if __name__ == "__main__":
    main()
