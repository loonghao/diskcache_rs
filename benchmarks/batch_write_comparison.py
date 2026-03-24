"""Compare batch-write throughput across high-level and low-level cache APIs."""

from __future__ import annotations

import statistics
import tempfile
import time
from collections.abc import Callable

import diskcache
from diskcache_rs import Cache, rust_pickle_dumps
from diskcache_rs._diskcache_rs import PyCache

PAYLOAD_COUNT = 500
PAYLOAD_SIZE = 1024
PREFILL_COUNT = 10_000
ROUNDS = 5

PAYLOAD = {f"key-{index}": b"x" * PAYLOAD_SIZE for index in range(PAYLOAD_COUNT)}
SERIALIZED_PAYLOAD = {key: rust_pickle_dumps(value) for key, value in PAYLOAD.items()}
PREFILL_PAYLOAD = {
    f"prefill-{index}": b"p" * 128 for index in range(PREFILL_COUNT)
}
SERIALIZED_PREFILL_PAYLOAD = {
    key: rust_pickle_dumps(value) for key, value in PREFILL_PAYLOAD.items()
}


BenchmarkFn = Callable[[], float]


def benchmark_diskcache_rs_loop(prefill: bool = False) -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_rs_loop_") as cache_dir:
        cache = Cache(cache_dir)
        if prefill:
            cache.set_many(PREFILL_PAYLOAD)

        start = time.perf_counter()
        for key, value in PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_diskcache_rs_batch(prefill: bool = False) -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_rs_batch_") as cache_dir:
        cache = Cache(cache_dir)
        if prefill:
            cache.set_many(PREFILL_PAYLOAD)

        start = time.perf_counter()
        cache.set_many(PAYLOAD)
        cache.close()
        return time.perf_counter() - start


def benchmark_diskcache_loop(prefill: bool = False) -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_py_loop_") as cache_dir:
        cache = diskcache.Cache(cache_dir)
        if prefill:
            for key, value in PREFILL_PAYLOAD.items():
                cache.set(key, value)

        start = time.perf_counter()
        for key, value in PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_pycache_loop(prefill: bool = False) -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_pycache_loop_") as cache_dir:
        cache = PyCache(cache_dir)
        if prefill:
            cache.set_many(list(SERIALIZED_PREFILL_PAYLOAD.items()))

        start = time.perf_counter()
        for key, value in SERIALIZED_PAYLOAD.items():
            cache.set(key, value)
        cache.close()
        return time.perf_counter() - start


def benchmark_pycache_batch(prefill: bool = False) -> float:
    with tempfile.TemporaryDirectory(prefix="diskcache_pycache_batch_") as cache_dir:
        cache = PyCache(cache_dir)
        if prefill:
            cache.set_many(list(SERIALIZED_PREFILL_PAYLOAD.items()))

        start = time.perf_counter()
        cache.set_many(list(SERIALIZED_PAYLOAD.items()))
        cache.close()
        return time.perf_counter() - start


def run_rounds(benchmark: BenchmarkFn) -> list[float]:
    return [benchmark() for _ in range(ROUNDS)]


def average_duration(samples: list[float]) -> float:
    return statistics.mean(samples)


def print_metric(name: str, samples: list[float]) -> None:
    avg = average_duration(samples)
    print(f"{name}_avg={avg:.6f}")
    print(f"{name}_ops_per_sec={PAYLOAD_COUNT / avg:.1f}")


def print_scenario_results(name: str, samples: dict[str, list[float]]) -> None:
    print(f"scenario={name}")
    for metric_name, metric_samples in samples.items():
        print_metric(f"{name}_{metric_name}", metric_samples)

    rs_loop_avg = average_duration(samples["rs_loop"])
    rs_batch_avg = average_duration(samples["rs_batch"])
    py_loop_avg = average_duration(samples["py_loop"])
    pycache_loop_avg = average_duration(samples["pycache_loop"])
    pycache_batch_avg = average_duration(samples["pycache_batch"])

    print(f"{name}_high_level_batch_speedup_vs_rs_loop={rs_loop_avg / rs_batch_avg:.2f}")
    print(
        f"{name}_low_level_batch_speedup_vs_pycache_loop={pycache_loop_avg / pycache_batch_avg:.2f}"
    )
    print(f"{name}_batch_speedup_vs_diskcache_loop={py_loop_avg / rs_batch_avg:.2f}")
    print()


def main() -> None:
    print(
        f"payload_count={PAYLOAD_COUNT} payload_size={PAYLOAD_SIZE} prefill_count={PREFILL_COUNT} rounds={ROUNDS}"
    )
    print()

    fresh_samples = {
        "rs_loop": run_rounds(lambda: benchmark_diskcache_rs_loop(prefill=False)),
        "rs_batch": run_rounds(lambda: benchmark_diskcache_rs_batch(prefill=False)),
        "py_loop": run_rounds(lambda: benchmark_diskcache_loop(prefill=False)),
        "pycache_loop": run_rounds(lambda: benchmark_pycache_loop(prefill=False)),
        "pycache_batch": run_rounds(lambda: benchmark_pycache_batch(prefill=False)),
    }
    print_scenario_results("fresh", fresh_samples)

    prefilled_samples = {
        "rs_loop": run_rounds(lambda: benchmark_diskcache_rs_loop(prefill=True)),
        "rs_batch": run_rounds(lambda: benchmark_diskcache_rs_batch(prefill=True)),
        "py_loop": run_rounds(lambda: benchmark_diskcache_loop(prefill=True)),
        "pycache_loop": run_rounds(lambda: benchmark_pycache_loop(prefill=True)),
        "pycache_batch": run_rounds(lambda: benchmark_pycache_batch(prefill=True)),
    }
    print_scenario_results("prefilled", prefilled_samples)

    print("analysis_hint=high_level Cache.set_many is still bounded by Python-side pickle serialization")
    print("analysis_hint=low_level PyCache.set_many better isolates Rust storage batching gains")
    print(
        "analysis_hint=prefilled scenarios highlight the cost of per-write cache limit bookkeeping when the cache is already large"
    )


if __name__ == "__main__":
    main()
