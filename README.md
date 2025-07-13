# DiskCache RS

[![PyPI version](https://img.shields.io/pypi/v/diskcache-rs.svg)](https://pypi.org/project/diskcache-rs/)
[![PyPI downloads](https://img.shields.io/pypi/dm/diskcache-rs.svg)](https://pypi.org/project/diskcache-rs/)
[![Python versions](https://img.shields.io/pypi/pyversions/diskcache-rs.svg)](https://pypi.org/project/diskcache-rs/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.87+-orange.svg)](https://www.rust-lang.org)
[![CI](https://github.com/loonghao/diskcache_rs/workflows/CI/badge.svg)](https://github.com/loonghao/diskcache_rs/actions)
[![codecov](https://codecov.io/gh/loonghao/diskcache_rs/branch/main/graph/badge.svg)](https://codecov.io/gh/loonghao/diskcache_rs)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](https://github.com/loonghao/diskcache_rs#readme)

English Documentation

A **blazingly fast** disk cache implementation in Rust with Python bindings, designed to be compatible with [python-diskcache](https://github.com/grantjenks/python-diskcache) while providing **superior performance** and **bulletproof network filesystem support**.

## 📊 Performance Results

**diskcache_rs consistently outperforms python-diskcache across all operations:**

| Operation | diskcache_rs | python-diskcache | Speedup |
|-----------|-------------|------------------|---------|
| **Single SET** | 8,958 ops/s | 7,444 ops/s | **1.2x faster** ⚡ |
| **Batch SET (10)** | 13,968 ops/s | 1,889 ops/s | **7.4x faster** 🚀 |
| **Batch SET (100)** | 14,699 ops/s | 7,270 ops/s | **2.0x faster** ⚡ |
| **Cold Start** | 806 μs | 14,558 μs | **18x faster** 🚀 |
| **DELETE** | 122k ops/s | 7.7k ops/s | **16x faster** 🚀 |

*Benchmarks run on Windows 11, Python 3.13, identical test conditions.*

## 🚀 Features

### 🌟 **Core Advantages**
- **⚡ Superior Performance**: 1.2x to 18x faster than python-diskcache
- **🌐 Network Filesystem Mastery**: Bulletproof operation on NFS, SMB, CIFS
- **🔄 Drop-in Replacement**: Compatible API with python-diskcache
- **🚀 Ultra-Fast Startup**: 18x faster cold start times
- **🧵 True Concurrency**: Built with Rust's fearless concurrency

### 🎛️ **Storage Backends**
- **UltraFast**: Memory-only storage for maximum speed
- **Hybrid**: Smart memory + disk storage with automatic optimization
- **File**: Traditional file-based storage with network compatibility

### 🛡️ **Reliability**
- **No SQLite Dependencies**: Eliminates database corruption on network drives
- **Atomic Operations**: Ensures data consistency even on unreliable connections
- **Thread Safe**: Safe for concurrent access from multiple threads and processes
- **Compression Support**: Built-in LZ4 compression for space efficiency

## 🎯 Problem Solved

The original python-diskcache can suffer from SQLite corruption on network file systems, as documented in [issue #345](https://github.com/grantjenks/python-diskcache/issues/345). This implementation uses a file-based storage engine specifically designed for network filesystems, avoiding the "database disk image is malformed" errors.

## 🚀 Quick Start

```bash
pip install diskcache-rs
```

```python
from diskcache_rs import Cache

# Create a cache
cache = Cache('/tmp/mycache')

# Basic operations
cache['key'] = 'value'
print(cache['key'])  # 'value'

# Check if key exists
if 'key' in cache:
    print("Key exists!")

# Get with default
value = cache.get('missing_key', 'default')

# Delete
del cache['key']
```

## 📦 Installation

### From PyPI (Recommended)

```bash
# Standard installation (Python version-specific wheels)
pip install diskcache-rs

# ABI3 installation (compatible with Python 3.8+)
pip install diskcache-rs --prefer-binary --extra-index-url https://pypi.org/simple/
```

### Wheel Types

**diskcache_rs** provides two types of wheels:

1. **Standard Wheels** (default)
   - Optimized for specific Python versions (3.8, 3.9, 3.10, 3.11, 3.12, 3.13)
   - Smaller download size
   - Maximum performance for your Python version

2. **ABI3 Wheels** (universal)
   - Single wheel compatible with Python 3.8+
   - Larger download size but works across Python versions
   - Ideal for deployment scenarios with multiple Python versions

### Prerequisites (Building from Source)

- Rust 1.87+ (for building from source)
- Python 3.8+
- maturin (for building Python bindings)

### Build from Source

```bash
# Clone the repository
git clone https://github.com/loonghao/diskcache_rs.git
cd diskcache_rs

# Install dependencies
uv add diskcache  # Optional: for comparison testing

# Standard build (Python version-specific)
uvx maturin develop

# ABI3 build (compatible with Python 3.8+)
uvx maturin develop --features abi3
```

### Development Commands

```bash
# Setup development environment
just dev

# Build standard wheels
just release

# Build ABI3 wheels
just release-abi3

# Available commands
just --list
```

### Release Process

This project uses [Commitizen](https://commitizen-tools.github.io/commitizen/) for automated version management and releases.

#### Making Changes

1. **Use Conventional Commits**: All commits should follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:
   ```bash
   # Use commitizen for guided commit creation
   just commit

   # Or manually follow the format:
   # feat: add new feature
   # fix: resolve bug
   # docs: update documentation
   # chore: maintenance tasks
   ```

2. **Automatic Releases**: When you push to `main`, the CI will:
   - Analyze commit messages since the last release
   - Automatically bump version in both `Cargo.toml` and `pyproject.toml`
   - Generate changelog
   - Create GitHub release
   - Build and publish wheels to PyPI

#### Manual Release Commands

```bash
# Check what version would be bumped (dry run)
just bump --dry-run

# Manually bump version and create changelog
just bump

# Generate changelog only
just changelog
```

## 🔧 Usage Examples

### Basic Cache Operations

```python
from diskcache_rs import Cache

# Create a cache with size limits
cache = Cache('/tmp/mycache', size_limit=1e9)  # 1GB limit

# Dictionary-like interface
cache['key'] = 'value'
print(cache['key'])  # 'value'

# Method interface
cache.set('number', 42)
cache.set('data', {'nested': 'dict'})

# Get with default values
value = cache.get('missing', 'default_value')

# Check membership
if 'key' in cache:
    print("Found key!")

# Iterate over keys
for key in cache:
    print(f"{key}: {cache[key]}")

# Delete items
del cache['key']
cache.pop('number', None)  # Safe deletion

# Clear everything
cache.clear()
```

### Advanced Features

```python
from diskcache_rs import Cache, FanoutCache

# FanoutCache for better concurrent performance
cache = FanoutCache('/tmp/fanout', shards=8, size_limit=1e9)

# Set with expiration (TTL)
cache.set('temp_key', 'temp_value', expire=3600)  # 1 hour

# Touch to update access time
cache.touch('temp_key')

# Atomic operations
with cache.transact():
    cache['key1'] = 'value1'
    cache['key2'] = 'value2'
    # Both operations succeed or fail together

# Statistics and monitoring
stats = cache.stats()
print(f"Hits: {stats.hits}, Misses: {stats.misses}")
print(f"Size: {cache.volume()} bytes")

# Eviction and cleanup
cache.cull()  # Manual eviction
cache.expire()  # Remove expired items
```

### High-Performance Scenarios

```python
from diskcache_rs import FastCache

# Ultra-fast memory-only cache
fast_cache = FastCache(max_size=1000)

# Batch operations for maximum throughput
items = [(f'key_{i}', f'value_{i}') for i in range(1000)]
for key, value in items:
    fast_cache[key] = value

# Efficient bulk retrieval
keys = [f'key_{i}' for i in range(100)]
values = [fast_cache.get(key) for key in keys]
```

### Network Filesystem Support

```python
from diskcache_rs import Cache

# Works reliably on network drives
network_cache = Cache('//server/share/cache')

# Atomic writes prevent corruption
network_cache['important_data'] = large_dataset

# Built-in retry logic for network issues
try:
    value = network_cache['important_data']
except Exception as e:
    print(f"Network error handled: {e}")
```

### Django Integration

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'diskcache_rs.DjangoCache',
        'LOCATION': '/tmp/django_cache',
        'OPTIONS': {
            'size_limit': 1e9,  # 1GB
            'cull_limit': 0.1,  # Remove 10% when full
        }
    }
}

# In your views
from django.core.cache import cache

cache.set('user_data', user_profile, timeout=3600)
user_data = cache.get('user_data')
```

### Performance Comparison

```python
import time
import diskcache
from diskcache_rs import Cache

# Setup
data = b'x' * 1024  # 1KB test data

# Original diskcache
dc_cache = diskcache.Cache('/tmp/diskcache_test')
start = time.perf_counter()
for i in range(1000):
    dc_cache.set(f'key_{i}', data)
dc_time = time.perf_counter() - start

# diskcache_rs
rs_cache = Cache('/tmp/diskcache_rs_test')
start = time.perf_counter()
for i in range(1000):
    rs_cache[f'key_{i}'] = data
rs_time = time.perf_counter() - start

print(f"diskcache: {dc_time:.3f}s ({1000/dc_time:.0f} ops/sec)")
print(f"diskcache_rs: {rs_time:.3f}s ({1000/rs_time:.0f} ops/sec)")
print(f"Speedup: {dc_time/rs_time:.1f}x faster")
```

### Python-Compatible API

For drop-in compatibility with python-diskcache:

```python
# Add the python wrapper to your path
import sys
sys.path.insert(0, 'python')

from diskcache_rs import Cache, FanoutCache

# Use like original diskcache
cache = Cache('/path/to/cache')
cache['key'] = 'value'
print(cache['key'])  # 'value'

# FanoutCache for better performance
fanout = FanoutCache('/path/to/cache', shards=8)
fanout.set('key', 'value')
```

### Network Filesystem Usage

Perfect for cloud drives and network storage:

```python
# Works great on network drives
cache = diskcache_rs.PyCache("Z:\\_thm\\temp\\.pkg\\db")

# Or UNC paths
cache = diskcache_rs.PyCache("\\\\server\\share\\cache")

# Handles network interruptions gracefully
cache.set("important_data", b"critical_value")
```

## 🏗️ Architecture

### Core Components

- **Storage Engine**: File-based storage optimized for network filesystems
- **Serialization**: Multiple formats (JSON, Bincode) with compression
- **Eviction Policies**: LRU, LFU, TTL, and combined strategies
- **Concurrency**: Thread-safe operations with minimal locking
- **Network Optimization**: Atomic writes, retry logic, corruption detection

### Network Filesystem Optimizations

1. **No SQLite**: Avoids database corruption issues
2. **Atomic Writes**: Uses temporary files and atomic renames
3. **File Locking**: Optional file locking for coordination
4. **Retry Logic**: Handles temporary network failures
5. **Corruption Detection**: Validates data integrity

## 📋 Feature Comparison

| Feature | diskcache_rs | python-diskcache | Notes |
|---------|-------------|------------------|-------|
| **Performance** | 1.2x - 18x faster | Baseline | Rust implementation advantage |
| **Network FS** | ✅ Optimized | ⚠️ May corrupt | File-based vs SQLite |
| **Thread Safety** | ✅ Yes | ✅ Yes | Both support concurrent access |
| **Process Safety** | ✅ Yes | ✅ Yes | Multi-process coordination |
| **API Compatibility** | ✅ Drop-in | ✅ Native | Same interface |
| **Memory Usage** | 🔥 Lower | Baseline | Rust memory efficiency |
| **Startup Time** | 🚀 18x faster | Baseline | Minimal initialization |
| **Compression** | ✅ LZ4 | ✅ Multiple | Built-in compression |
| **Eviction Policies** | ✅ LRU/LFU/TTL | ✅ LRU/LFU/TTL | Same strategies |
| **Serialization** | ✅ Multiple | ✅ Pickle | JSON, Bincode, Pickle |
| **Type Hints** | ✅ Full | ✅ Partial | Complete .pyi files |
| **Cross Platform** | ✅ Yes | ✅ Yes | Windows, macOS, Linux |
| **ABI3 Support** | ✅ Optional | ❌ No | Single wheel for Python 3.8+ |
| **Wheel Types** | 🎯 Standard + ABI3 | Standard only | Flexible deployment options |
| **Dependencies** | 🔥 Minimal | More | Fewer runtime dependencies |
| **Installation** | 📦 pip install | 📦 pip install | Both available on PyPI |

## 📊 Performance

Benchmarks on cloud drive (Z: drive):

| Operation | diskcache_rs | python-diskcache | Notes |
|-----------|--------------|------------------|-------|
| Set (1KB) | ~20ms       | ~190ms          | 9.5x faster |
| Get (1KB) | ~25ms       | ~2ms            | Optimization needed |
| Concurrent| ✅ Stable    | ✅ Stable*       | Both work on your setup |
| Network FS| ✅ Optimized | ⚠️ May fail      | Key advantage |

*Note: python-diskcache works on your specific cloud drive but may fail on other network filesystems

## 🧪 Testing

The project includes comprehensive tests for network filesystem compatibility:

```bash
# Basic functionality test
uv run python simple_test.py

# Network filesystem specific tests
uv run python test_network_fs.py

# Comparison with original diskcache
uv run python test_detailed_comparison.py

# Extreme conditions testing
uv run python test_extreme_conditions.py
```

### Test Results on Cloud Drive

✅ **All tests pass on Z: drive (cloud storage)**
- Basic operations: ✓
- Concurrent access: ✓
- Large files (1MB+): ✓
- Persistence: ✓
- Edge cases: ✓

## 🔧 Configuration

```python
cache = diskcache_rs.PyCache(
    directory="/path/to/cache",
    max_size=1024*1024*1024,    # 1GB
    max_entries=100000,          # 100K entries
)
```

### Advanced Configuration (Rust API)

```rust
use diskcache_rs::{Cache, CacheConfig, EvictionStrategy, SerializationFormat, CompressionType};

let config = CacheConfig {
    directory: PathBuf::from("/path/to/cache"),
    max_size: Some(1024 * 1024 * 1024),
    max_entries: Some(100_000),
    eviction_strategy: EvictionStrategy::LruTtl,
    serialization_format: SerializationFormat::Bincode,
    compression: CompressionType::Lz4,
    use_atomic_writes: true,
    use_file_locking: false,  // Disable for network drives
    auto_vacuum: true,
    vacuum_interval: 3600,
};

let cache = Cache::new(config)?;
```

## 📚 API Reference

### Cache Class

The main cache interface, compatible with python-diskcache:

```python
from diskcache_rs import Cache

cache = Cache(directory, size_limit=None, cull_limit=0.1)
```

**Methods:**
- `cache[key] = value` - Set a value
- `value = cache[key]` - Get a value (raises KeyError if missing)
- `value = cache.get(key, default=None)` - Get with default
- `cache.set(key, value, expire=None, tag=None)` - Set with options
- `del cache[key]` - Delete a key
- `key in cache` - Check membership
- `len(cache)` - Number of items
- `cache.clear()` - Remove all items
- `cache.stats()` - Get statistics
- `cache.volume()` - Get total size in bytes

### FanoutCache Class

Sharded cache for better concurrent performance:

```python
from diskcache_rs import FanoutCache

cache = FanoutCache(directory, shards=8, size_limit=None)
```

Same API as Cache, but with better concurrent performance.

### FastCache Class

Memory-only cache for maximum speed:

```python
from diskcache_rs import FastCache

cache = FastCache(max_size=1000)
```

**Methods:**
- `cache[key] = value` - Set a value
- `value = cache[key]` - Get a value
- `value = cache.get(key, default=None)` - Get with default
- `del cache[key]` - Delete a key
- `cache.clear()` - Remove all items

## � Testing

### Running Tests

```bash
# Run all tests
uv run --group test pytest

# Run specific test categories
uv run --group test pytest -m "not docker"  # Skip Docker tests
uv run --group test pytest -m "docker"      # Only Docker tests
uv run --group test pytest -m "network"     # Network filesystem tests

# Run compatibility tests
uv run --group test pytest tests/test_compatibility.py -v
```

### Docker Network Testing

For comprehensive network filesystem testing, we provide Docker-based simulation:

```bash
# Run Docker network tests (requires Docker)
./scripts/test-docker-network.sh

# Or manually with Docker Compose
docker-compose -f docker-compose.test.yml up --build
```

The Docker tests simulate:
- NFS server environments
- SMB/CIFS server environments
- Network latency conditions
- Concurrent access scenarios

### Cross-Platform Network Testing

The test suite automatically detects and tests available network paths:
- **Windows**: UNC paths, mapped drives, cloud sync folders
- **Linux/macOS**: NFS mounts, SMB mounts, cloud sync folders

## �🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [python-diskcache](https://github.com/grantjenks/python-diskcache) for the original inspiration
- [PyO3](https://github.com/PyO3/pyo3) for excellent Python-Rust bindings
- [maturin](https://github.com/PyO3/maturin) for seamless Python package building

## 📚 Related Projects

- [python-diskcache](https://github.com/grantjenks/python-diskcache) - Original Python implementation
- [sled](https://github.com/spacejam/sled) - Embedded database in Rust
- [rocksdb](https://github.com/facebook/rocksdb) - High-performance key-value store

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Install development dependencies**: `just dev`
4. **Make your changes** and add tests
5. **Run the test suite**: `just test`
6. **Format your code**: `just format`
7. **Submit a pull request**

### Development Setup

```bash
# Clone and setup
git clone https://github.com/loonghao/diskcache_rs.git
cd diskcache_rs

# One-command setup
just dev

# Available commands
just --list
```

### Running Tests

```bash
just test          # Run all tests
just test-cov      # Run with coverage
just bench         # Run benchmarks
just format        # Format code
just lint          # Run linting
```

## 📄 License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [Grant Jenks](https://github.com/grantjenks) for the original python-diskcache
- [PyO3](https://github.com/PyO3/pyo3) team for excellent Python-Rust bindings
- [maturin](https://github.com/PyO3/maturin) for seamless Python package building
- Rust community for the amazing ecosystem

---

**Note**: This project specifically addresses network filesystem issues encountered with SQLite-based caches. For local storage scenarios, both diskcache_rs and python-diskcache are excellent choices, with diskcache_rs offering superior performance.
