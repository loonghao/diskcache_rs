# AGENTS.md — DiskCache RS

> Navigation map, not a reference manual. Follow the links; don't read
> everything upfront.

diskcache_rs is a high-performance disk cache in Rust with Python bindings,
API-compatible with `python-diskcache` while adding better performance and
network-filesystem support.

---

## Repository Contract

**This repository has a `justfile`; run everything through `vx just`.**

| Task | Command |
|------|---------|
| Install dev environment | `vx just install` |
| Build | `vx just build` |
| Release build | `vx just build-release` |
| Test | `vx just test` |
| Test with coverage | `vx just test-cov` |
| Generate type stubs | `vx just stubs` |
| Format | `vx just format` |
| Lint | `vx just lint` |
| Format + lint + test | `vx just check` |
| Full dev loop | `vx just dev` |
| Benchmarks | `vx just bench` |

**Repository layout**

| Path | Role |
|------|------|
| `src/` | Rust crate sources |
| `python/diskcache_rs/` | Python package and type stubs |
| `tests/` | Rust and Python test suites |
| `benchmarks/` | Criterion benchmarks |
| `examples/` | Usage examples |
| `scripts/` | Build and release helpers |
| `justfile` | Canonical task entrypoint |
| `API_COMPATIBILITY.md` | python-diskcache compatibility matrix |

**Release flow** — `release-please` on `main` drives `CHANGELOG.md` and the version in
`Cargo.toml` / `pyproject.toml` from Conventional Commit subjects; `vx just
release` / `release-abi3` build wheels and PyPI publishing runs in CI.
Never edit `CHANGELOG.md` or a version string by hand.

**Prohibitions**

- Do not bypass the justfile — no direct `cargo`/`maturin`/`pytest` invocations.
- Do not edit `CHANGELOG.md` or version strings manually.
- Do not add a second agent contract file at the repository root; `AGENTS.md` is the single source.
- Do not break `python-diskcache` API compatibility without recording it in `API_COMPATIBILITY.md`.

---

## Agent Contract Files

`AGENTS.md` is the **only** agent contract file at the repository root. It is the
native instruction file for Codex, OpenCode, Cursor, GitHub Copilot, Windsurf,
Cline, Roo Code, Kiro, Trae, and Augment, and Claude Code falls back to it when
no `CLAUDE.md` exists — so do not add `CLAUDE.md`, `GEMINI.md`, `CURSOR.md`, or
any other vendor-specific variant.

**Gemini CLI exception:** Gemini CLI defaults its context file to `GEMINI.md`. To
make it read `AGENTS.md`, set `context.fileName` once in `~/.gemini/settings.json`:

```json
{
  "context": {
    "fileName": ["AGENTS.md", "GEMINI.md"]
  }
}
```
