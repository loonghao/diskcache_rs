# AGENTS.md — diskcache_rs

> High-performance disk cache implemented in Rust with PyO3 Python bindings,
> built and shipped with maturin as the `diskcache_rs` PyPI package — a
> drop-in, faster alternative to the pure-Python `diskcache`.
> Navigation map for AI agents, not a reference manual. Follow the links; do
> not read everything up front.

## Build & test

This repo has a justfile — use it. Run `just --list` for the live recipe list.

```bash
vx just dev           # install + build + stubs: full dev environment setup
vx just build         # uvx maturin develop (debug extension module)
vx just build-release # uvx maturin develop --release
vx just test          # uv run python -m pytest tests/ -v
vx just test-cov      # pytest with HTML coverage for diskcache_rs
vx just check         # format + lint + test (the local CI equivalent)
vx just lint          # cargo clippy -- -D warnings, then uv run ruff check .
vx just format        # cargo fmt --all, then uv run ruff format .
vx just fix           # clippy --fix + ruff check --fix
```

Release-oriented recipes:

```bash
vx just release       # uvx maturin build --release
vx just release-abi3  # uvx maturin build --release --features abi3 (Python 3.8+)
vx just publish       # release, then uvx maturin publish (needs PyPI auth)
vx just sync-version  # scripts/sync_version.py: Cargo.toml <-> pyproject.toml
vx just stubs         # regenerate .pyi stubs with pyo3-stubgen
vx just verify-stubs  # confirm .pyi files land inside the built wheel
vx just bench         # pytest -k benchmark
vx just bench-pickle  # benchmarks/pickle_bridge_comparison.py
vx just audit         # cargo audit
```

Requires Rust 1.87+, Python 3.8+, and `uv` / `maturin`.

## Repo layout

| Path | Role |
|---|---|
| `src/cache.rs` | Core cache implementation and the PyO3 class surface |
| `src/storage.rs`, `src/storage/optimized_backend.rs` | SQLite-backed persistent storage (`rusqlite`, bundled) |
| `src/memory_cache.rs`, `src/eviction.rs` | In-memory tier and eviction policy |
| `src/serialization.rs` | Serializers: `serde_json`, `bincode`, `rmp-serde`, `postcard`, `lz4_flex` |
| `src/pickle_cache.rs` | Pickle-compatible values via the Rust pickle bridge |
| `src/migration.rs` | Import/migration path from the pure-Python `diskcache` |
| `src/error.rs`, `src/utils.rs` | Error types and helpers (`blake3`, `dashmap`, `parking_lot`) |
| `python/diskcache_rs/` | Python package wrapper: `cache.py`, `core.py`, `disk.py`, `fast_cache.py`, `pickle_cache.py`, `djangocache.py`, `recipes.py`, `constants.py`, plus `.pyi` stubs |
| `tests/` | Pytest suite — API-compatibility, persistence, network filesystem, NFS-safe SQLite, Django cache, performance |
| `benchmarks/` | Standalone performance and profiling scripts (not part of `just test`) |
| `examples/` | `basic_usage.py`, `special_chars_keys_example.py` |
| `scripts/` | `sync_version.py`, `generate_stubs.py`, `test-docker-network.sh` |
| `API_COMPATIBILITY.md` | Behavioural delta against upstream `diskcache` — read before changing public API |
| `Dockerfile.test`, `docker-compose.test.yml` | Containerised network-filesystem tests |

## Release

- release-please drives versioning from Conventional Commits on `main`
  (`release-please-config.json`). `.release-please-manifest.json` is the single
  source of version truth.
- `feat:` → minor, `fix:` → patch, `chore:`/`docs:`/`ci:` → **no release**.
- Use `chore:`/`docs:` for config and doc work so release-please does not cut a
  valueless version.
- Merging the release PR triggers `.github/workflows/release.yml`, which calls
  `build.yml` and `build-abi3.yml` to produce both wheel flavours, then
  publishes to PyPI and creates the GitHub release.
- `Cargo.toml` and `pyproject.toml` must carry the same version —
  `just sync-version` is the supported way to reconcile them.

## Do / Don't

- **Do** keep the two wheels working: any new PyO3 surface must build under
  both the default and the `abi3` (`abi3-py38`) feature.
- **Do** regenerate stubs (`just stubs`) and confirm them in the wheel
  (`just verify-stubs`) after changing the Rust API.
- **Do** check `API_COMPATIBILITY.md` before changing anything the pure-Python
  `diskcache` also exposes.
- **Don't** edit `python/diskcache_rs/*.pyi` by hand — they are generated.
- **Don't** hardcode an exact version in tests (`assert __version__ == "X.Y.Z"`)
  — release-please bumps will break it. Use `>=` or read package metadata.
  `tests/test_version_and_disk_threshold.py` already depends on this.
- **Don't** add `CLAUDE.md` / `GEMINI.md` / `CURSOR.md` / `ANTHROPIC.md` /
  `OPENAI.md` / `COPILOT.md` / `CODEBUDDY.md` / `.cursorrules` / `.clinerules` /
  `.windsurfrules` at the root. This file is the only agent contract file.
- **Don't** commit build artifacts to the repo root (`target/`, `dist/`,
  `htmlcov/`, `coverage.json`, `*.so`, `*.pyd`).
