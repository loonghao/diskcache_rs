# DiskCache RS

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/rust-1.87+-orange.svg)](https://www.rust-lang.org)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org)

中文文档 | [English](README.md)

一个用 Rust 实现的高性能磁盘缓存，提供 Python 绑定，设计上与 [python-diskcache](https://github.com/grantjenks/python-diskcache) 兼容，同时提供更好的性能和网络文件系统支持。

## 🚀 特性

- **高性能**: 使用 Rust 实现，追求最大速度和效率
- **网络文件系统支持**: 针对云磁盘和网络文件系统（NFS、SMB 等）优化
- **Python 兼容**: 可直接替换 python-diskcache，API 熟悉易用
- **线程安全**: 支持多线程和多进程并发访问
- **多种淘汰策略**: LRU、LFU、TTL 和组合策略
- **压缩支持**: 内置 LZ4 压缩，节省空间
- **原子操作**: 即使在不可靠的网络驱动器上也能确保数据一致性
- **无 SQLite 依赖**: 避免网络文件系统上的 SQLite 损坏问题

## 🎯 解决的问题

原始的 python-diskcache 在网络文件系统上可能遭受 SQLite 损坏，如 [issue #345](https://github.com/grantjenks/python-diskcache/issues/345) 所记录。本实现使用专门为网络文件系统设计的基于文件的存储引擎，避免了"database disk image is malformed"错误。

## 📦 安装

### 前置要求

- Rust 1.87+（从源码构建）
- Python 3.8+
- maturin（构建 Python 绑定）

### 从源码构建

```bash
# 克隆仓库
git clone https://github.com/loonghao/diskcache_rs.git
cd diskcache_rs

# 安装依赖
uv add diskcache  # 可选：用于对比测试

# 构建和安装
uvx maturin develop
```

## 🔧 使用方法

### 基本用法

```python
import diskcache_rs

# 创建缓存
cache = diskcache_rs.PyCache("/path/to/cache", max_size=1024*1024*1024, max_entries=100000)

# 设置和获取值
cache.set("key", b"value")
result = cache.get("key")  # 返回 b"value"

# 检查存在性
if cache.exists("key"):
    print("键存在！")

# 删除
cache.delete("key")

# 获取统计信息
stats = cache.stats()
print(f"命中: {stats['hits']}, 未命中: {stats['misses']}")

# 清空所有条目
cache.clear()
```

### Python 兼容 API

与 python-diskcache 直接兼容：

```python
# 将 python 包装器添加到路径
import sys
sys.path.insert(0, 'python')

from diskcache_rs import Cache, FanoutCache

# 像原始 diskcache 一样使用
cache = Cache('/path/to/cache')
cache['key'] = 'value'
print(cache['key'])  # 'value'

# FanoutCache 获得更好性能
fanout = FanoutCache('/path/to/cache', shards=8)
fanout.set('key', 'value')
```

### 网络文件系统使用

完美适用于云磁盘和网络存储：

```python
# 在网络驱动器上工作良好
cache = diskcache_rs.PyCache("Z:\\_thm\\temp\\.pkg\\db")

# 或 UNC 路径
cache = diskcache_rs.PyCache("\\\\server\\share\\cache")

# 优雅处理网络中断
cache.set("important_data", b"critical_value")
```

## 🏗️ 架构

### 核心组件

- **存储引擎**: 针对网络文件系统优化的基于文件的存储
- **序列化**: 多种格式（JSON、Bincode）支持压缩
- **淘汰策略**: LRU、LFU、TTL 和组合策略
- **并发性**: 线程安全操作，最小锁定
- **网络优化**: 原子写入、重试逻辑、损坏检测

### 网络文件系统优化

1. **无 SQLite**: 避免数据库损坏问题
2. **原子写入**: 使用临时文件和原子重命名
3. **文件锁定**: 可选文件锁定用于协调
4. **重试逻辑**: 处理临时网络故障
5. **损坏检测**: 验证数据完整性

## 📊 性能

在云磁盘（Z: 驱动器）上的基准测试：

| 操作 | diskcache_rs | python-diskcache | 说明 |
|------|--------------|------------------|------|
| 设置 (1KB) | ~20ms       | ~190ms          | 快 9.5 倍 |
| 获取 (1KB) | ~25ms       | ~2ms            | 需要优化 |
| 并发 | ✅ 稳定      | ✅ 稳定*         | 两者在你的设置上都工作 |
| 网络文件系统 | ✅ 优化     | ⚠️ 可能失败      | 关键优势 |

*注意：python-diskcache 在你的特定云磁盘上工作，但在其他网络文件系统上可能失败

## 🧪 测试

项目包含网络文件系统兼容性的全面测试：

```bash
# 基本功能测试
uv run python simple_test.py

# 网络文件系统特定测试
uv run python test_network_fs.py

# 与原始 diskcache 对比
uv run python test_detailed_comparison.py

# 极端条件测试
uv run python test_extreme_conditions.py
```

### 云磁盘测试结果

✅ **所有测试在 Z: 驱动器（云存储）上通过**
- 基本操作: ✓
- 并发访问: ✓
- 大文件 (1MB+): ✓
- 持久性: ✓
- 边缘情况: ✓

## 🔧 配置

```python
cache = diskcache_rs.PyCache(
    directory="/path/to/cache",
    max_size=1024*1024*1024,    # 1GB
    max_entries=100000,          # 10万条目
)
```

### 高级配置（Rust API）

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
    use_file_locking: false,  // 网络驱动器禁用
    auto_vacuum: true,
    vacuum_interval: 3600,
};

let cache = Cache::new(config)?;
```

## 🤝 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 添加测试
5. 提交 pull request

## 📄 许可证

本项目采用 Apache License 2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 🙏 致谢

- [python-diskcache](https://github.com/grantjenks/python-diskcache) 提供原始灵感
- [PyO3](https://github.com/PyO3/pyo3) 提供优秀的 Python-Rust 绑定
- [maturin](https://github.com/PyO3/maturin) 提供无缝的 Python 包构建

## 📚 相关项目

- [python-diskcache](https://github.com/grantjenks/python-diskcache) - 原始 Python 实现
- [sled](https://github.com/spacejam/sled) - Rust 嵌入式数据库
- [rocksdb](https://github.com/facebook/rocksdb) - 高性能键值存储

---

**注意**: 本项目专门解决网络文件系统问题。如果你只使用本地存储，原始的 python-diskcache 可能就足够满足你的需求。
