use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use bytes::{Bytes, BytesMut};
use dashmap::DashMap;
use memmap2::{Mmap, MmapOptions};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

/// High-performance optimized storage backend with multiple performance enhancements:
/// - Memory-mapped files for large data
/// - Zero-copy operations using Bytes
/// - Async I/O with batching
/// - Object pooling for buffer reuse
/// - Adaptive compression
/// - Fine-grained locking
pub struct OptimizedStorage {
    directory: PathBuf,

    // Multi-tier storage
    hot_cache: Arc<DashMap<String, Bytes>>, // Frequently accessed data
    warm_cache: Arc<DashMap<String, MmapEntry>>, // Memory-mapped files
    cold_index: Arc<RwLock<DashMap<String, FileInfo>>>, // File metadata

    // Performance optimizations
    #[allow(dead_code)]
    buffer_pool: Arc<BufferPool>,
    write_batcher: Arc<WriteBatcher>,

    // Configuration
    config: StorageConfig,

    // Statistics
    stats: Arc<StorageStats>,
}

#[derive(Clone)]
pub struct StorageConfig {
    pub hot_cache_size: usize,        // Max entries in hot cache
    pub warm_cache_size: usize,       // Max memory-mapped files
    pub mmap_threshold: usize,        // Size threshold for memory mapping
    pub batch_size: usize,            // Write batch size
    pub compression_threshold: usize, // Size threshold for compression
    pub use_compression: bool,
    pub sync_writes: bool,
    pub disk_write_threshold: usize, // Size threshold for writing to disk (vs memory-only)
    pub use_file_locking: bool,      // Enable file locking for NFS scenarios
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self {
            hot_cache_size: 10_000,
            warm_cache_size: 1_000,
            mmap_threshold: 64 * 1024, // 64KB
            batch_size: 100,
            compression_threshold: 1024, // 1KB
            use_compression: true,
            sync_writes: false,
            disk_write_threshold: 1024, // 1KB - data smaller than this stays in memory only
            use_file_locking: false,    // Disabled by default for performance
        }
    }
}

#[derive(Debug)]
struct MmapEntry {
    mmap: Mmap,
    size: usize,
    last_accessed: AtomicU64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct FileInfo {
    path: PathBuf,
    #[allow(dead_code)]
    size: u64,
    #[allow(dead_code)]
    created_at: u64,
    compressed: bool,
}

/// Buffer pool for reusing allocations
#[allow(dead_code)]
struct BufferPool {
    small_buffers: Arc<RwLock<VecDeque<BytesMut>>>, // < 4KB
    medium_buffers: Arc<RwLock<VecDeque<BytesMut>>>, // 4KB - 64KB
    large_buffers: Arc<RwLock<VecDeque<BytesMut>>>, // > 64KB
}

#[allow(dead_code)]
impl BufferPool {
    fn new() -> Self {
        Self {
            small_buffers: Arc::new(RwLock::new(VecDeque::with_capacity(100))),
            medium_buffers: Arc::new(RwLock::new(VecDeque::with_capacity(50))),
            large_buffers: Arc::new(RwLock::new(VecDeque::with_capacity(10))),
        }
    }

    fn get_buffer(&self, size: usize) -> BytesMut {
        let pool = if size < 4096 {
            &self.small_buffers
        } else if size < 65536 {
            &self.medium_buffers
        } else {
            &self.large_buffers
        };

        if let Some(mut buf) = pool.write().pop_front() {
            buf.clear();
            if buf.capacity() >= size {
                return buf;
            }
        }

        BytesMut::with_capacity(size.max(4096))
    }

    fn return_buffer(&self, buf: BytesMut) {
        if buf.capacity() == 0 {
            return;
        }

        let pool = if buf.capacity() < 4096 {
            &self.small_buffers
        } else if buf.capacity() < 65536 {
            &self.medium_buffers
        } else {
            &self.large_buffers
        };

        let mut pool_guard = pool.write();
        if pool_guard.len() < 20 {
            // Limit pool size
            pool_guard.push_back(buf);
        }
    }
}

/// Batched write operations for better I/O performance
struct WriteBatcher {
    sender: mpsc::Sender<WriteOp>,
}

#[derive(Debug)]
enum WriteOp {
    Write { path: PathBuf, data: Bytes },
    Delete { path: PathBuf },
    Sync { done: mpsc::SyncSender<()> },
}

impl WriteBatcher {
    fn new(_directory: PathBuf, batch_size: usize) -> Self {
        let (sender, receiver) = mpsc::channel();

        std::thread::spawn(move || {
            let mut batch = Vec::with_capacity(batch_size);
            let mut writer_map: std::collections::HashMap<PathBuf, BufWriter<File>> =
                std::collections::HashMap::new();

            while let Ok(op) = receiver.recv() {
                match op {
                    WriteOp::Write { path, data } => {
                        batch.push((path, data));
                        if batch.len() >= batch_size {
                            Self::flush_batch(&mut batch, &mut writer_map);
                        }
                    }
                    WriteOp::Delete { path } => {
                        let _ = std::fs::remove_file(&path);
                    }
                    WriteOp::Sync { done } => {
                        Self::flush_batch(&mut batch, &mut writer_map);
                        for writer in writer_map.values_mut() {
                            let _ = writer.flush();
                        }
                        // Signal completion
                        let _ = done.send(());
                    }
                }
            }

            // Final flush
            Self::flush_batch(&mut batch, &mut writer_map);
        });

        Self { sender }
    }

    fn flush_batch(
        batch: &mut Vec<(PathBuf, Bytes)>,
        _writer_map: &mut std::collections::HashMap<PathBuf, BufWriter<File>>,
    ) {
        for (path, data) in batch.drain(..) {
            if let Ok(file) = OpenOptions::new()
                .create(true)
                .write(true)
                .truncate(true)
                .open(&path)
            {
                let mut writer = BufWriter::new(file);
                let _ = writer.write_all(&data);
                let _ = writer.flush();
            }
        }
    }

    fn write_async(&self, path: PathBuf, data: Bytes) {
        let _ = self.sender.send(WriteOp::Write { path, data });
    }

    fn delete_async(&self, path: PathBuf) {
        let _ = self.sender.send(WriteOp::Delete { path });
    }

    fn sync(&self) {
        let (done_tx, done_rx) = mpsc::sync_channel(0); // Rendezvous channel for immediate sync
        let _ = self.sender.send(WriteOp::Sync { done: done_tx });
        // Wait for sync to complete
        let _ = done_rx.recv();
    }
}

/// Performance statistics
#[derive(Default)]
struct StorageStats {
    hot_hits: AtomicU64,
    warm_hits: AtomicU64,
    cold_hits: AtomicU64,
    misses: AtomicU64,
    writes: AtomicU64,
    bytes_written: AtomicU64,
    bytes_read: AtomicU64,
}

impl StorageStats {
    fn record_hot_hit(&self) {
        self.hot_hits.fetch_add(1, Ordering::Relaxed);
    }

    fn record_warm_hit(&self) {
        self.warm_hits.fetch_add(1, Ordering::Relaxed);
    }

    fn record_cold_hit(&self) {
        self.cold_hits.fetch_add(1, Ordering::Relaxed);
    }

    fn record_miss(&self) {
        self.misses.fetch_add(1, Ordering::Relaxed);
    }

    fn record_write(&self, bytes: u64) {
        self.writes.fetch_add(1, Ordering::Relaxed);
        self.bytes_written.fetch_add(bytes, Ordering::Relaxed);
    }

    fn record_read(&self, bytes: u64) {
        self.bytes_read.fetch_add(bytes, Ordering::Relaxed);
    }
}

impl OptimizedStorage {
    pub fn new<P: AsRef<Path>>(directory: P) -> CacheResult<Self> {
        Self::with_config(directory, StorageConfig::default())
    }

    pub fn with_config<P: AsRef<Path>>(directory: P, config: StorageConfig) -> CacheResult<Self> {
        let directory = directory.as_ref().to_path_buf();
        std::fs::create_dir_all(&directory).map_err(CacheError::Io)?;

        let data_dir = directory.join("data");
        std::fs::create_dir_all(&data_dir).map_err(CacheError::Io)?;

        let write_batcher = Arc::new(WriteBatcher::new(data_dir.clone(), config.batch_size));

        let mut storage = Self {
            directory,
            hot_cache: Arc::new(DashMap::with_capacity(config.hot_cache_size)),
            warm_cache: Arc::new(DashMap::with_capacity(config.warm_cache_size)),
            cold_index: Arc::new(RwLock::new(DashMap::new())),
            buffer_pool: Arc::new(BufferPool::new()),
            write_batcher,
            config,
            stats: Arc::new(StorageStats::default()),
        };

        // Scan existing files to rebuild the cold index
        storage.rebuild_index_from_disk()?;

        Ok(storage)
    }

    /// Rebuild the cold index by scanning existing files on disk
    fn rebuild_index_from_disk(&mut self) -> CacheResult<()> {
        // Try to load index from persistent index file first
        let index_path = self.directory.join("index.json");
        if index_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&index_path) {
                if let Ok(persisted_index) =
                    serde_json::from_str::<std::collections::HashMap<String, FileInfo>>(&content)
                {
                    let mut index = self.cold_index.write();
                    for (key, file_info) in persisted_index {
                        // Verify file still exists
                        if file_info.path.exists() {
                            index.insert(key, file_info);
                        }
                    }
                    return Ok(());
                }
            }
        }

        // Fallback: scan data directory (less efficient, but works for recovery)
        let data_dir = self.directory.join("data");
        if !data_dir.exists() {
            return Ok(());
        }

        // Note: Without the index file, we can't recover the original keys
        // because we use blake3 hash for filenames. This is a known limitation.
        // Users should call vacuum() periodically to persist the index.

        Ok(())
    }

    /// Persist the cold index to disk for recovery after restart
    fn persist_index(&self) -> CacheResult<()> {
        let index_path = self.directory.join("index.json");
        let index = self.cold_index.read();

        // Convert DashMap to HashMap for serialization
        let index_map: std::collections::HashMap<String, FileInfo> = index
            .iter()
            .map(|entry| (entry.key().clone(), entry.value().clone()))
            .collect();

        let json = serde_json::to_string_pretty(&index_map).map_err(|e| {
            CacheError::Io(std::io::Error::new(
                std::io::ErrorKind::Other,
                format!("Failed to serialize index: {}", e),
            ))
        })?;

        std::fs::write(&index_path, json).map_err(CacheError::Io)?;
        Ok(())
    }

    fn get_current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }

    fn build_file_path(&self, key: &str) -> PathBuf {
        let hash = blake3::hash(key.as_bytes());
        let hex_hash = hash.to_hex();
        self.directory
            .join("data")
            .join(format!("{}.dat", &hex_hash[..16]))
    }

    /// Compress data if it provides significant space savings
    fn compress_if_beneficial(&self, data: &[u8]) -> (Bytes, bool) {
        if !self.config.use_compression || data.len() < self.config.compression_threshold {
            return (Bytes::copy_from_slice(data), false);
        }

        // Use LZ4 for fast compression
        match lz4_flex::compress_prepend_size(data) {
            compressed if compressed.len() < data.len() * 9 / 10 => (Bytes::from(compressed), true),
            _ => (Bytes::copy_from_slice(data), false),
        }
    }

    /// Decompress data if it was previously compressed
    fn decompress_if_needed(&self, data: &[u8], is_compressed: bool) -> CacheResult<Bytes> {
        if !is_compressed {
            return Ok(Bytes::copy_from_slice(data));
        }

        match lz4_flex::decompress_size_prepended(data) {
            Ok(decompressed) => Ok(Bytes::from(decompressed)),
            Err(e) => Err(CacheError::Deserialization(format!(
                "Decompression failed: {}",
                e
            ))),
        }
    }

    /// Remove least recently used entries from hot cache when it's full
    fn cleanup_hot_cache(&self) {
        if self.hot_cache.len() > self.config.hot_cache_size {
            // Simple eviction: remove 10% of entries
            let entries_to_remove = self.config.hot_cache_size / 10;
            let mut removed_count = 0;

            self.hot_cache.retain(|_, _| {
                if removed_count < entries_to_remove {
                    removed_count += 1;
                    false
                } else {
                    true
                }
            });
        }
    }

    /// Remove old entries from warm cache based on access time
    fn cleanup_warm_cache(&self) {
        if self.warm_cache.len() > self.config.warm_cache_size {
            let current_time = Self::get_current_timestamp();
            let mut keys_to_remove = Vec::new();

            // Find entries that haven't been accessed in 5 minutes
            for entry in self.warm_cache.iter() {
                let last_accessed = entry.value().last_accessed.load(Ordering::Relaxed);
                if current_time - last_accessed > 300 {
                    // 5 minutes
                    keys_to_remove.push(entry.key().clone());
                }
            }

            // Remove up to 10% of cache entries
            let max_removals = self.config.warm_cache_size / 10;
            for key in keys_to_remove.into_iter().take(max_removals) {
                self.warm_cache.remove(&key);
            }
        }
    }
}

impl StorageBackend for OptimizedStorage {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>> {
        // Level 1: Hot cache (fastest)
        if let Some(data) = self.hot_cache.get(key) {
            self.stats.record_hot_hit();
            self.stats.record_read(data.len() as u64);
            let entry = CacheEntry::new_inline(key.to_string(), data.to_vec(), vec![], None);
            return Ok(Some(entry));
        }

        // Level 2: Warm cache (memory-mapped files)
        if let Some(mmap_entry) = self.warm_cache.get(key) {
            self.stats.record_warm_hit();
            mmap_entry
                .last_accessed
                .store(Self::get_current_timestamp(), Ordering::Relaxed);

            let data = &mmap_entry.mmap[..mmap_entry.size];
            self.stats.record_read(data.len() as u64);

            // Promote to hot cache if small enough
            if data.len() < 4096 {
                self.hot_cache
                    .insert(key.to_string(), Bytes::copy_from_slice(data));
            }

            let entry = CacheEntry::new_inline(key.to_string(), data.to_vec(), vec![], None);
            return Ok(Some(entry));
        }

        // Level 3: Cold storage (disk files)
        if let Some(file_info) = self.cold_index.read().get(key) {
            let file_info = file_info.clone();
            drop(self.cold_index.read()); // Release read lock early

            match std::fs::read(&file_info.path) {
                Ok(raw_data) => {
                    self.stats.record_cold_hit();

                    let data = self.decompress_if_needed(&raw_data, file_info.compressed)?;
                    self.stats.record_read(data.len() as u64);

                    // Decide on caching strategy based on size
                    if data.len() < 4096 {
                        // Small data: promote to hot cache
                        self.hot_cache.insert(key.to_string(), data.clone());
                        self.cleanup_hot_cache();
                    } else if data.len() < self.config.mmap_threshold {
                        // Medium data: create memory-mapped file
                        if let Ok(file) = std::fs::File::open(&file_info.path) {
                            if let Ok(mmap) = unsafe { MmapOptions::new().map(&file) } {
                                let mmap_entry = MmapEntry {
                                    mmap,
                                    size: raw_data.len(),
                                    last_accessed: AtomicU64::new(Self::get_current_timestamp()),
                                };
                                self.warm_cache.insert(key.to_string(), mmap_entry);
                                self.cleanup_warm_cache();
                            }
                        }
                    }

                    let entry =
                        CacheEntry::new_inline(key.to_string(), data.to_vec(), vec![], None);
                    Ok(Some(entry))
                }
                Err(_) => {
                    // File not found or read error, remove from index
                    self.cold_index.write().remove(key);
                    self.stats.record_miss();
                    Ok(None)
                }
            }
        } else {
            self.stats.record_miss();
            Ok(None)
        }
    }

    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()> {
        let data = match &entry.storage {
            crate::serialization::StorageMode::Inline(data) => data,
            crate::serialization::StorageMode::File(filename) => {
                // Read file data
                let file_path = self.directory.join("data").join(filename);
                return match std::fs::read(&file_path) {
                    Ok(file_data) => self.set_data(key, &file_data),
                    Err(e) => Err(CacheError::Io(e)),
                };
            }
        };

        self.set_data(key, data)
    }

    fn delete(&self, key: &str) -> CacheResult<bool> {
        let mut found = false;

        // Remove from all cache levels
        if self.hot_cache.remove(key).is_some() {
            found = true;
        }

        if self.warm_cache.remove(key).is_some() {
            found = true;
        }

        if let Some((_, file_info)) = self.cold_index.write().remove(key) {
            found = true;
            // Delete file asynchronously
            self.write_batcher.delete_async(file_info.path);
        }

        Ok(found)
    }

    fn exists(&self, key: &str) -> CacheResult<bool> {
        Ok(self.hot_cache.contains_key(key)
            || self.warm_cache.contains_key(key)
            || self.cold_index.read().contains_key(key))
    }

    fn keys(&self) -> CacheResult<Vec<String>> {
        let mut keys = std::collections::HashSet::new();

        // Collect from all levels
        for entry in self.hot_cache.iter() {
            keys.insert(entry.key().clone());
        }

        for entry in self.warm_cache.iter() {
            keys.insert(entry.key().clone());
        }

        for entry in self.cold_index.read().iter() {
            keys.insert(entry.key().clone());
        }

        Ok(keys.into_iter().collect())
    }

    fn clear(&self) -> CacheResult<()> {
        self.hot_cache.clear();
        self.warm_cache.clear();

        // Clear cold storage
        let cold_index = self.cold_index.read();
        for entry in cold_index.iter() {
            let file_path = &entry.value().path;
            self.write_batcher.delete_async(file_path.clone());
        }
        drop(cold_index);

        self.cold_index.write().clear();

        // Force sync to ensure all deletes are processed
        self.write_batcher.sync();

        Ok(())
    }

    fn vacuum(&self) -> CacheResult<()> {
        // Force cleanup of old entries
        self.cleanup_hot_cache();
        self.cleanup_warm_cache();

        // Sync pending writes
        self.write_batcher.sync();

        // Persist index to disk for recovery after restart
        self.persist_index()?;

        Ok(())
    }

    fn generate_filename(&self, key: &str) -> String {
        let hash = blake3::hash(key.as_bytes());
        format!("{}.dat", &hash.to_hex()[..16])
    }

    fn write_data_file(&self, filename: &str, data: &[u8]) -> CacheResult<()> {
        let file_path = self.directory.join("data").join(filename);
        std::fs::write(&file_path, data).map_err(CacheError::Io)
    }

    fn read_data_file(&self, filename: &str) -> CacheResult<Vec<u8>> {
        let file_path = self.directory.join("data").join(filename);
        std::fs::read(&file_path).map_err(CacheError::Io)
    }
}

impl OptimizedStorage {
    /// Set data with optimized storage strategy
    fn set_data(&self, key: &str, data: &[u8]) -> CacheResult<()> {
        let data_size = data.len();
        self.stats.record_write(data_size as u64);

        // Remove from all cache levels first
        self.hot_cache.remove(key);
        self.warm_cache.remove(key);

        if data_size < self.config.disk_write_threshold {
            // Small data: store in hot cache only (below disk_write_threshold)
            self.hot_cache
                .insert(key.to_string(), Bytes::copy_from_slice(data));
            self.cleanup_hot_cache();
        } else {
            // Large data: compress and store to disk (>= disk_write_threshold)
            let (compressed_data, is_compressed) = self.compress_if_beneficial(data);
            let file_path = self.build_file_path(key);

            // Store file info in cold index
            let file_info = FileInfo {
                path: file_path.clone(),
                size: compressed_data.len() as u64,
                created_at: Self::get_current_timestamp(),
                compressed: is_compressed,
            };
            self.cold_index.write().insert(key.to_string(), file_info);

            // Write to disk with optional file locking
            if self.config.use_file_locking {
                // Use file locking for NFS scenarios
                self.write_with_lock(&file_path, &compressed_data)?;
            } else if self.config.sync_writes || data_size > 1024 * 1024 {
                // Large files or sync mode: write immediately
                std::fs::write(&file_path, &compressed_data).map_err(CacheError::Io)?;
            } else {
                // Async write for better performance
                self.write_batcher.write_async(file_path, compressed_data);
            }
        }

        Ok(())
    }

    /// Write data to file with exclusive lock (for NFS scenarios)
    fn write_with_lock(&self, file_path: &Path, data: &[u8]) -> CacheResult<()> {
        use fs4::fs_std::FileExt;

        // Create parent directory if it doesn't exist
        if let Some(parent) = file_path.parent() {
            std::fs::create_dir_all(parent).map_err(CacheError::Io)?;
        }

        // Open file for writing (create if doesn't exist)
        let file = OpenOptions::new()
            .write(true)
            .create(true)
            .truncate(true)
            .open(file_path)
            .map_err(CacheError::Io)?;

        // Acquire exclusive lock (blocks until lock is available)
        file.lock_exclusive().map_err(|e| {
            CacheError::Io(std::io::Error::new(
                std::io::ErrorKind::Other,
                format!("Failed to acquire file lock: {}", e),
            ))
        })?;

        // Write data using buffered writer for better performance
        let mut writer = BufWriter::new(&file);
        writer.write_all(data).map_err(CacheError::Io)?;
        writer.flush().map_err(CacheError::Io)?;

        // Sync to disk to ensure data is written
        file.sync_all().map_err(CacheError::Io)?;

        // Lock is automatically released when file is dropped
        Ok(())
    }

    /// Get performance statistics
    #[allow(dead_code)]
    pub fn stats(&self) -> StorageStatistics {
        StorageStatistics {
            hot_hits: self.stats.hot_hits.load(Ordering::Relaxed),
            warm_hits: self.stats.warm_hits.load(Ordering::Relaxed),
            cold_hits: self.stats.cold_hits.load(Ordering::Relaxed),
            misses: self.stats.misses.load(Ordering::Relaxed),
            writes: self.stats.writes.load(Ordering::Relaxed),
            bytes_written: self.stats.bytes_written.load(Ordering::Relaxed),
            bytes_read: self.stats.bytes_read.load(Ordering::Relaxed),
            hot_cache_size: self.hot_cache.len(),
            warm_cache_size: self.warm_cache.len(),
            cold_index_size: self.cold_index.read().len(),
        }
    }

    /// Batch set operation for better performance
    #[allow(dead_code)]
    pub fn set_batch(&self, entries: Vec<(String, Vec<u8>)>) -> CacheResult<()> {
        for (key, data) in entries {
            self.set_data(&key, &data)?;
        }
        Ok(())
    }
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct StorageStatistics {
    pub hot_hits: u64,
    pub warm_hits: u64,
    pub cold_hits: u64,
    pub misses: u64,
    pub writes: u64,
    pub bytes_written: u64,
    pub bytes_read: u64,
    pub hot_cache_size: usize,
    pub warm_cache_size: usize,
    pub cold_index_size: usize,
}
