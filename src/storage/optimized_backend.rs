use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use bytes::{Bytes, BytesMut};
use dashmap::DashMap;
use memmap2::{Mmap, MmapOptions};
use parking_lot::RwLock;
use redb::{Database, ReadableDatabase, ReadableTable, TableDefinition};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

// Define redb table for cache index
const INDEX_TABLE: TableDefinition<&str, &[u8]> = TableDefinition::new("cache_index");

/// High-performance optimized storage backend with multiple performance enhancements:
/// - Memory-mapped files for large data
/// - Zero-copy operations using Bytes
/// - Async I/O with batching
/// - Object pooling for buffer reuse
/// - Adaptive compression
/// - Fine-grained locking
/// - Persistent index using redb for ACID guarantees
pub struct OptimizedStorage {
    directory: PathBuf,

    // Multi-tier storage
    hot_cache: Arc<DashMap<String, Bytes>>, // Frequently accessed data
    warm_cache: Arc<DashMap<String, MmapEntry>>, // Memory-mapped files
    cold_index: Arc<RwLock<DashMap<String, FileInfo>>>, // File metadata (in-memory cache)

    // Persistent index database (Option to allow explicit closing)
    index_db: Arc<RwLock<Option<Database>>>, // redb database for persistent index

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

#[derive(Debug, Clone, Serialize, Deserialize, bincode::Encode, bincode::Decode)]
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

        // Initialize redb database for persistent index
        let index_db_path = directory.join("index.redb");

        // Use create if file doesn't exist, otherwise open
        let index_db = if index_db_path.exists() {
            Database::open(&index_db_path).map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to open redb database: {}",
                    e
                )))
            })?
        } else {
            Database::create(&index_db_path).map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to create redb database: {}",
                    e
                )))
            })?
        };

        let write_batcher = Arc::new(WriteBatcher::new(data_dir.clone(), config.batch_size));

        let mut storage = Self {
            directory,
            hot_cache: Arc::new(DashMap::with_capacity(config.hot_cache_size)),
            warm_cache: Arc::new(DashMap::with_capacity(config.warm_cache_size)),
            cold_index: Arc::new(RwLock::new(DashMap::new())),
            index_db: Arc::new(RwLock::new(Some(index_db))),
            buffer_pool: Arc::new(BufferPool::new()),
            write_batcher,
            config,
            stats: Arc::new(StorageStats::default()),
        };

        // Load existing index from redb
        storage.rebuild_index_from_disk()?;

        Ok(storage)
    }

    /// Rebuild the cold index by loading from redb database
    fn rebuild_index_from_disk(&mut self) -> CacheResult<()> {
        let db_guard = self.index_db.read();
        let db = match db_guard.as_ref() {
            Some(db) => db,
            None => return Ok(()), // Database is closed
        };

        let read_txn = db.begin_read().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to begin redb read transaction: {}",
                e
            )))
        })?;

        // Try to open the table (it might not exist on first run)
        let table = match read_txn.open_table(INDEX_TABLE) {
            Ok(table) => table,
            Err(_) => {
                // Table doesn't exist yet, this is a new database
                return Ok(());
            }
        };

        let index = self.cold_index.write();
        let mut loaded_count = 0;
        let mut skipped_count = 0;

        // Iterate over all entries in the redb table
        let iter = table.iter().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to iterate redb table: {}",
                e
            )))
        })?;

        for entry in iter {
            let (key, value) = entry.map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to read redb entry: {}",
                    e
                )))
            })?;

            // Deserialize FileInfo from bytes
            let file_info: FileInfo =
                bincode::decode_from_slice(value.value(), bincode::config::standard())
                    .map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to deserialize FileInfo: {}",
                            e
                        )))
                    })?
                    .0;

            // Verify file still exists before adding to index
            if file_info.path.exists() {
                index.insert(key.value().to_string(), file_info);
                loaded_count += 1;
            } else {
                skipped_count += 1;
            }
        }

        tracing::debug!(
            "Loaded {} entries from redb index, skipped {} missing files",
            loaded_count,
            skipped_count
        );

        Ok(())
    }

    /// Close the redb database explicitly
    /// This releases the file lock and allows other processes to open the database
    pub fn close_db(&self) {
        // Flush all in-memory data to disk before closing
        if let Err(e) = self.flush_memory_caches() {
            tracing::error!("Failed to flush memory caches during close: {}", e);
        }

        let mut db_guard = self.index_db.write();
        *db_guard = None;
        tracing::debug!("Closed redb database");
    }

    /// Flush all in-memory caches (hot_cache and warm_cache) to disk
    /// This ensures data persistence when closing the cache
    fn flush_memory_caches(&self) -> CacheResult<()> {
        let db_guard = self.index_db.read();
        let db = match db_guard.as_ref() {
            Some(db) => db,
            None => return Ok(()), // Database already closed
        };

        // Collect all entries from hot_cache and warm_cache
        let mut entries_to_persist = Vec::new();

        // Collect from hot_cache
        for entry in self.hot_cache.iter() {
            let key = entry.key().clone();
            let data = entry.value().clone();
            entries_to_persist.push((key, data));
        }

        // Collect from warm_cache (convert MmapEntry to Bytes)
        for entry in self.warm_cache.iter() {
            let key = entry.key().clone();
            let mmap_entry = entry.value();
            let data = Bytes::copy_from_slice(&mmap_entry.mmap[..mmap_entry.size]);
            entries_to_persist.push((key, data));
        }

        if entries_to_persist.is_empty() {
            return Ok(());
        }

        tracing::debug!(
            "Flushing {} entries from memory caches to disk",
            entries_to_persist.len()
        );

        // Write all entries to redb in a single transaction
        let write_txn = db.begin_write().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to begin redb write transaction: {}",
                e
            )))
        })?;

        {
            let mut table = write_txn.open_table(INDEX_TABLE).map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to open redb table: {}",
                    e
                )))
            })?;

            for (key, data) in entries_to_persist {
                // Create a FileInfo for in-memory data
                // We'll store the data inline in the FileInfo structure
                let file_info = FileInfo {
                    path: PathBuf::from(format!("memory://{}", key)),
                    size: data.len() as u64,
                    created_at: Self::get_current_timestamp(),
                    compressed: false,
                };

                // Serialize FileInfo + data together
                let mut value_bytes =
                    bincode::encode_to_vec(&file_info, bincode::config::standard()).map_err(
                        |e| {
                            CacheError::Io(std::io::Error::other(format!(
                                "Failed to serialize FileInfo: {}",
                                e
                            )))
                        },
                    )?;

                // Append the actual data after FileInfo
                value_bytes.extend_from_slice(&data);

                table
                    .insert(key.as_str(), value_bytes.as_slice())
                    .map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to insert into redb: {}",
                            e
                        )))
                    })?;
            }
        }

        write_txn.commit().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to commit redb transaction: {}",
                e
            )))
        })?;

        tracing::debug!("Successfully flushed memory caches to disk");
        Ok(())
    }

    /// Persist the cold index to redb database with ACID guarantees
    fn persist_index(&self) -> CacheResult<()> {
        let db_guard = self.index_db.read();
        let db = match db_guard.as_ref() {
            Some(db) => db,
            None => return Ok(()), // Database is closed
        };

        let write_txn = db.begin_write().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to begin redb write transaction: {}",
                e
            )))
        })?;

        {
            let mut table = write_txn.open_table(INDEX_TABLE).map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to open redb table: {}",
                    e
                )))
            })?;

            let index = self.cold_index.read();

            // Write all entries to redb
            for entry in index.iter() {
                let key = entry.key().as_str();
                let file_info = entry.value();

                // Serialize FileInfo to bytes
                let value_bytes = bincode::encode_to_vec(file_info, bincode::config::standard())
                    .map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to serialize FileInfo: {}",
                            e
                        )))
                    })?;

                table.insert(key, value_bytes.as_slice()).map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to insert into redb: {}",
                        e
                    )))
                })?;
            }
        }

        // Commit transaction (ACID guarantee)
        write_txn.commit().map_err(|e| {
            CacheError::Io(std::io::Error::other(format!(
                "Failed to commit redb transaction: {}",
                e
            )))
        })?;

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
            // Level 4: Check redb for persisted memory data
            let db_guard = self.index_db.read();
            if let Some(db) = db_guard.as_ref() {
                if let Ok(read_txn) = db.begin_read() {
                    if let Ok(table) = read_txn.open_table(INDEX_TABLE) {
                        if let Ok(Some(value)) = table.get(key) {
                            let value_bytes = value.value();

                            // Try to deserialize FileInfo
                            if let Ok((file_info, _)) = bincode::decode_from_slice::<FileInfo, _>(
                                value_bytes,
                                bincode::config::standard(),
                            ) {
                                // Check if this is memory-persisted data (path starts with "memory://")
                                if file_info.path.to_string_lossy().starts_with("memory://") {
                                    // Calculate FileInfo size to extract the actual data
                                    let file_info_size = bincode::encode_to_vec(
                                        &file_info,
                                        bincode::config::standard(),
                                    )
                                    .map(|v| v.len())
                                    .unwrap_or(0);

                                    if value_bytes.len() > file_info_size {
                                        let data = &value_bytes[file_info_size..];
                                        self.stats.record_read(data.len() as u64);

                                        // Restore to hot cache
                                        self.hot_cache
                                            .insert(key.to_string(), Bytes::copy_from_slice(data));

                                        let entry = CacheEntry::new_inline(
                                            key.to_string(),
                                            data.to_vec(),
                                            vec![],
                                            None,
                                        );
                                        return Ok(Some(entry));
                                    }
                                }
                            }
                        }
                    }
                }
            }

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

            // Remove from redb index
            let db_guard = self.index_db.read();
            if let Some(db) = db_guard.as_ref() {
                let write_txn = db.begin_write().map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to begin redb write transaction: {}",
                        e
                    )))
                })?;

                {
                    let mut table = write_txn.open_table(INDEX_TABLE).map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to open redb table: {}",
                            e
                        )))
                    })?;

                    table.remove(key).map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to remove from redb: {}",
                            e
                        )))
                    })?;
                }

                write_txn.commit().map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to commit redb transaction: {}",
                        e
                    )))
                })?;
            }
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

        // Clear redb index
        let db_guard = self.index_db.read();
        if let Some(db) = db_guard.as_ref() {
            let write_txn = db.begin_write().map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to begin redb write transaction: {}",
                    e
                )))
            })?;

            {
                // Delete the table to clear all entries
                write_txn.delete_table(INDEX_TABLE).map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to delete redb table: {}",
                        e
                    )))
                })?;
            }

            write_txn.commit().map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to commit redb transaction: {}",
                    e
                )))
            })?;
        }

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

    fn as_any(&self) -> &dyn std::any::Any {
        self
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
            self.cold_index
                .write()
                .insert(key.to_string(), file_info.clone());

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

            // Persist to redb immediately (ACID guarantee, fast with redb)
            let db_guard = self.index_db.read();
            if let Some(db) = db_guard.as_ref() {
                let write_txn = db.begin_write().map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to begin redb write transaction: {}",
                        e
                    )))
                })?;

                {
                    let mut table = write_txn.open_table(INDEX_TABLE).map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to open redb table: {}",
                            e
                        )))
                    })?;

                    let value_bytes =
                        bincode::encode_to_vec(&file_info, bincode::config::standard()).map_err(
                            |e| {
                                CacheError::Io(std::io::Error::other(format!(
                                    "Failed to serialize FileInfo: {}",
                                    e
                                )))
                            },
                        )?;

                    table.insert(key, value_bytes.as_slice()).map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to insert into redb: {}",
                            e
                        )))
                    })?;
                }

                write_txn.commit().map_err(|e| {
                    CacheError::Io(std::io::Error::other(format!(
                        "Failed to commit redb transaction: {}",
                        e
                    )))
                })?;
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
            CacheError::Io(std::io::Error::other(format!(
                "Failed to acquire file lock: {}",
                e
            )))
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

impl Drop for OptimizedStorage {
    fn drop(&mut self) {
        // Ensure index is persisted when storage is dropped
        let _ = self.persist_index();
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
