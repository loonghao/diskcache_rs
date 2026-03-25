#!/usr/bin/env python3
"""Compare CPython pickle, diskcache_rs default pickle helpers, and the direct bridge path."""

import os
import pickle
import time

os.environ.pop("DISKCACHE_RS_USE_RUST_PICKLE_BRIDGE", None)

import diskcache_rs.rust_pickle as rust_pickle
from diskcache_rs import rust_pickle_dumps, rust_pickle_loads


def benchmark(label, dumps_fn, loads_fn, payload, iterations=200):
    start = time.perf_counter()
    for _ in range(iterations):
        encoded = dumps_fn(payload)
        _ = loads_fn(encoded)
    elapsed = time.perf_counter() - start
    ops_per_sec = iterations / elapsed if elapsed > 0 else float("inf")
    return {"label": label, "elapsed": elapsed, "ops_per_sec": ops_per_sec}


def print_results(results):
    print("\nPickle path comparison")
    print("=" * 72)
    print(f"{'Path':<24} {'Time':>12} {'Ops/sec':>16} {'Relative'}")
    print("-" * 72)

    baseline = results[0]["elapsed"]
    for result in results:
        relative = result["elapsed"] / baseline if baseline > 0 else 1.0
        print(
            f"{result['label']:<24} {result['elapsed']:>10.4f}s {result['ops_per_sec']:>14.1f} {relative:>8.2f}x"
        )


def main():
    payload = {
        "text": "diskcache_rs" * 100,
        "numbers": list(range(500)),
        "nested": {"alpha": list(range(50)), "beta": {"ok": True}},
        "binary": b"abc123" * 200,
    }

    results = [
        benchmark("CPython pickle", pickle.dumps, pickle.loads, payload),
        benchmark("default helper path", rust_pickle.dumps, rust_pickle.loads, payload),
    ]

    if rust_pickle_dumps is not None and rust_pickle_loads is not None:
        results.append(
            benchmark("direct Rust bridge", rust_pickle_dumps, rust_pickle_loads, payload)
        )

    print_results(results)

    if len(results) > 2:
        helper = results[1]
        bridge = results[2]
        if helper["elapsed"] > 0 and bridge["elapsed"] > 0:
            if helper["elapsed"] < bridge["elapsed"]:
                print(
                    f"\nDefault helper path is {bridge['elapsed'] / helper['elapsed']:.2f}x faster than the direct bridge."
                )
            else:
                print(
                    f"\nDirect bridge is {helper['elapsed'] / bridge['elapsed']:.2f}x faster than the default helper path."
                )


if __name__ == "__main__":
    main()
