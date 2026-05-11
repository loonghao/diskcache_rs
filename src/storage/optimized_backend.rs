use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use bytes::{Bytes, BytesMut};
use dashmap::DashMap;
use memmap2::Mmap;
use parking_lot::{Mutex, RwLock};

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::{BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::mpsc;
use std::sync::Arc;
use std::time::Duration;
use std::time::{SystemTime, UNIX_EPOCH};

const INDEX_TABLE_SQL: &str = "CREATE TABLE IF NOT EXISTS cache_index (key TEXT PRIMARY KEY, value BLOB NOT NULL, generation INTEGER NOT NULL DEFAULT 0)";

/// High-performance optimized storage backend with multiple performance enhancements:
/// - Memory-mapped files for large data
/// - Zero-copy operations using Bytes
/// - Async I/O with batching
/// - Object pooling for buffer reuse
/// - Adaptive compression
/// - Fine-grained locking
/// - Persistent index using SQLite for cross-process coordination
pub struct OptimizedStorage {
    directory: PathBuf,

    // Multi-tier storage
    hot_cache: Arc<DashMap<String, HotEntry>>, // Frequently accessed inline data
    warm_cache: Arc<DashMap<String, MmapEntry>>, // Memory-mapped files
    cold_index: Arc<RwLock<DashMap<String, FileInfo>>>, // File metadata (in-memory cache)

    index_db: Arc<Mutex<Connection>>,

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
    pub hot_cache_size: usize,  // Max entries in hot cache
    pub warm_cache_size: usize, // Max memory-mapped files
    #[allow(dead_code)]
    pub mmap_threshold: usize, // Size threshold for memory mapping
    pub batch_size: usize,      // Write batch size
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

#[derive(Debug, Clone)]
struct HotEntry {
    data: Bytes,
    generation: i64,
}

#[allow(dead_code)]
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

enum IndexEntry {
    Inline(HotEntry),
    File(FileInfo),
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
    sender: Mutex<Option<mpsc::Sender<WriteOp>>>,
    worker: Mutex<Option<std::thread::JoinHandle<()>>>,
}

#[derive(Debug)]
enum WriteOp {
    Write { path: PathBuf, data: Bytes },
    Delete { path: PathBuf },
    Sync { done: mpsc::SyncSender<()> },
    Shutdown { done: mpsc::SyncSender<()> },
}

impl WriteBatcher {
    fn new(_directory: PathBuf, batch_size: usize) -> Self {
        let (sender, receiver) = mpsc::channel();

        let worker = std::thread::spawn(move || {
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
                        Self::flush_batch(&mut batch, &mut writer_map);
                        let _ = std::fs::remove_file(&path);
                    }
                    WriteOp::Sync { done } => {
                        Self::flush_batch(&mut batch, &mut writer_map);
                        for writer in writer_map.values_mut() {
                            let _ = writer.flush();
                        }
                        let _ = done.send(());
                    }
                    WriteOp::Shutdown { done } => {
                        Self::flush_batch(&mut batch, &mut writer_map);
                        for writer in writer_map.values_mut() {
                            let _ = writer.flush();
                        }
                        let _ = done.send(());
                        break;
                    }
                }
            }

            Self::flush_batch(&mut batch, &mut writer_map);
        });

        Self {
            sender: Mutex::new(Some(sender)),
            worker: Mutex::new(Some(worker)),
        }
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
        if let Some(sender) = self.sender.lock().as_ref() {
            let _ = sender.send(WriteOp::Write { path, data });
        }
    }

    fn delete_async(&self, path: PathBuf) {
        if let Some(sender) = self.sender.lock().as_ref() {
            let _ = sender.send(WriteOp::Delete { path });
        }
    }

    fn sync(&self) {
        let (done_tx, done_rx) = mpsc::sync_channel(0);
        if let Some(sender) = self.sender.lock().as_ref() {
            let _ = sender.send(WriteOp::Sync { done: done_tx });
            let _ = done_rx.recv();
        }
    }

    fn shutdown(&self) {
        let sender = self.sender.lock().take();
        if let Some(sender) = sender {
            let (done_tx, done_rx) = mpsc::sync_channel(0);
            let _ = sender.send(WriteOp::Shutdown { done: done_tx });
            let _ = done_rx.recv();
        }

        if let Some(worker) = self.worker.lock().take() {
            let _ = worker.join();
        }
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

    #[allow(dead_code)]
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

        let index_db_path = directory.join("index.sqlite3");
        let index_db = Self::open_index_connection_at(&index_db_path)?;
        Self::initialize_index_connection(&index_db, config.use_file_locking)?;

        let write_batcher = Arc::new(WriteBatcher::new(data_dir.clone(), config.batch_size));

        let mut storage = Self {
            directory,
            hot_cache: Arc::new(DashMap::with_capacity(config.hot_cache_size)),
            warm_cache: Arc::new(DashMap::with_capacity(config.warm_cache_size)),
            cold_index: Arc::new(RwLock::new(DashMap::new())),
            index_db: Arc::new(Mutex::new(index_db)),
            buffer_pool: Arc::new(BufferPool::new()),
            write_batcher,
            config,
            stats: Arc::new(StorageStats::default()),
        };

        // Load existing index from SQLite
        storage.rebuild_index_from_disk()?;

        Ok(storage)
    }

    fn sqlite_error(context: &str, error: rusqlite::Error) -> CacheError {
        CacheError::Io(std::io::Error::other(format!("{}: {}", context, error)))
    }

    fn initialize_index_connection(conn: &Connection, nfs_safe: bool) -> CacheResult<()> {
        if nfs_safe {
            conn.pragma_update(None, "journal_mode", "DELETE")
                .map_err(|e| Self::sqlite_error("Failed to enable SQLite rollback journal", e))?;
            conn.pragma_update(None, "synchronous", "FULL")
                .map_err(|e| {
                    Self::sqlite_error("Failed to configure SQLite full synchronous mode", e)
                })?;
            conn.pragma_update(None, "mmap_size", 0)
                .map_err(|e| Self::sqlite_error("Failed to disable SQLite mmap", e))?;
        } else {
            conn.pragma_update(None, "journal_mode", "WAL")
                .map_err(|e| Self::sqlite_error("Failed to enable SQLite WAL", e))?;
            conn.pragma_update(None, "synchronous", "NORMAL")
                .map_err(|e| {
                    Self::sqlite_error("Failed to configure SQLite normal synchronous mode", e)
                })?;
        }
        conn.execute(INDEX_TABLE_SQL, [])
            .map_err(|e| Self::sqlite_error("Failed to create SQLite index table", e))?;
        Self::ensure_generation_column(conn)?;
        Ok(())
    }

    fn ensure_generation_column(conn: &Connection) -> CacheResult<()> {
        let mut stmt = conn
            .prepare("PRAGMA table_info(cache_index)")
            .map_err(|e| Self::sqlite_error("Failed to inspect SQLite index schema", e))?;
        let columns = stmt
            .query_map([], |row| row.get::<_, String>(1))
            .map_err(|e| Self::sqlite_error("Failed to query SQLite index schema", e))?;

        for column in columns {
            if column.map_err(|e| Self::sqlite_error("Failed to read SQLite index schema", e))?
                == "generation"
            {
                return Ok(());
            }
        }

        conn.execute(
            "ALTER TABLE cache_index ADD COLUMN generation INTEGER NOT NULL DEFAULT 0",
            [],
        )
        .map_err(|e| Self::sqlite_error("Failed to add SQLite generation column", e))?;
        Ok(())
    }

    fn open_index_connection_at(path: &Path) -> CacheResult<Connection> {
        let conn = Connection::open(path)
            .map_err(|e| Self::sqlite_error("Failed to open SQLite index", e))?;
        conn.busy_timeout(Duration::from_secs(60))
            .map_err(|e| Self::sqlite_error("Failed to set SQLite busy timeout", e))?;
        Ok(conn)
    }

    /// Rebuild the cold index by loading from SQLite database
    fn rebuild_index_from_disk(&mut self) -> CacheResult<()> {
        let conn = self.index_db.lock();
        let mut stmt = conn
            .prepare("SELECT key, value, generation FROM cache_index")
            .map_err(|e| Self::sqlite_error("Failed to query SQLite index", e))?;
        let rows = stmt
            .query_map([], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, Vec<u8>>(1)?,
                    row.get::<_, i64>(2)?,
                ))
            })
            .map_err(|e| Self::sqlite_error("Failed to iterate SQLite index", e))?;

        let index = self.cold_index.write();
        let mut loaded_count = 0;
        let mut skipped_count = 0;

        for row in rows {
            let (key, value_bytes, generation) =
                row.map_err(|e| Self::sqlite_error("Failed to read SQLite index row", e))?;
            let (file_info, decoded_len): (FileInfo, usize) =
                bincode::decode_from_slice(value_bytes.as_slice(), bincode::config::standard())
                    .map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to deserialize FileInfo: {}",
                            e
                        )))
                    })?;

            if file_info.path.to_string_lossy().starts_with("memory://") {
                if value_bytes.len() > decoded_len {
                    self.hot_cache.insert(
                        key,
                        HotEntry {
                            data: Bytes::copy_from_slice(&value_bytes[decoded_len..]),
                            generation,
                        },
                    );
                    loaded_count += 1;
                } else {
                    skipped_count += 1;
                }
                continue;
            }

            if file_info.path.exists() {
                index.insert(key, file_info);
                loaded_count += 1;
            } else {
                skipped_count += 1;
            }
        }

        tracing::debug!(
            "Loaded {} entries from SQLite index, skipped {} missing files",
            loaded_count,
            skipped_count
        );

        Ok(())
    }

    /// Close background resources and flush in-memory data.
    pub fn close_db(&self) {
        self.write_batcher.shutdown();

        if let Err(e) = self.flush_memory_caches() {
            tracing::error!("Failed to flush memory caches during close: {}", e);
        }
    }

    /// Flush in-flight file writes. Cache entries are already persisted when set.
    fn flush_memory_caches(&self) -> CacheResult<()> {
        Ok(())
    }

    /// Persist the cold index to SQLite.
    fn persist_index(&self) -> CacheResult<()> {
        let index = self.cold_index.read();
        let file_infos: Vec<(String, FileInfo)> = index
            .iter()
            .map(|entry| (entry.key().clone(), entry.value().clone()))
            .collect();
        drop(index);
        self.persist_file_infos(&file_infos)
    }

    fn encode_inline_entry(key: &str, data: &[u8]) -> CacheResult<Vec<u8>> {
        let file_info = FileInfo {
            path: PathBuf::from(format!("memory://{}", key)),
            size: data.len() as u64,
            created_at: Self::get_current_timestamp(),
            compressed: false,
        };
        let mut value_bytes = bincode::encode_to_vec(&file_info, bincode::config::standard())
            .map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to serialize FileInfo: {}",
                    e
                )))
            })?;
        value_bytes.extend_from_slice(data);
        Ok(value_bytes)
    }

    fn persist_inline_entries(&self, entries: &[(String, Bytes)]) -> CacheResult<()> {
        if entries.is_empty() {
            return Ok(());
        }

        let mut conn = self.index_db.lock();
        let tx = conn
            .transaction()
            .map_err(|e| Self::sqlite_error("Failed to begin SQLite transaction", e))?;
        {
            let mut stmt = tx
                .prepare("INSERT OR REPLACE INTO cache_index (key, value, generation) VALUES (?1, ?2, ?3)")
                .map_err(|e| Self::sqlite_error("Failed to prepare inline SQLite entry", e))?;
            for (key, data) in entries {
                let generation = Self::new_generation();
                let value_bytes = Self::encode_inline_entry(key, data)?;
                stmt.execute(params![key.as_str(), value_bytes, generation])
                    .map_err(|e| Self::sqlite_error("Failed to persist inline SQLite entry", e))?;
                self.hot_cache.insert(
                    key.clone(),
                    HotEntry {
                        data: data.clone(),
                        generation,
                    },
                );
            }
        }
        tx.commit()
            .map_err(|e| Self::sqlite_error("Failed to commit SQLite transaction", e))?;
        Ok(())
    }

    fn decode_index_entry(value_bytes: &[u8], generation: i64) -> CacheResult<IndexEntry> {
        let (file_info, decoded_len): (FileInfo, usize) =
            bincode::decode_from_slice(value_bytes, bincode::config::standard()).map_err(|e| {
                CacheError::Io(std::io::Error::other(format!(
                    "Failed to deserialize FileInfo: {}",
                    e
                )))
            })?;

        if file_info.path.to_string_lossy().starts_with("memory://") {
            if value_bytes.len() <= decoded_len {
                return Err(CacheError::Io(std::io::Error::other(
                    "Inline SQLite entry is missing data bytes",
                )));
            }
            Ok(IndexEntry::Inline(HotEntry {
                data: Bytes::copy_from_slice(&value_bytes[decoded_len..]),
                generation,
            }))
        } else {
            Ok(IndexEntry::File(file_info))
        }
    }

    fn read_index_generation(&self, key: &str) -> CacheResult<Option<i64>> {
        let conn = self.index_db.lock();
        conn.query_row(
            "SELECT generation FROM cache_index WHERE key = ?1",
            params![key],
            |row| row.get(0),
        )
        .optional()
        .map_err(|e| Self::sqlite_error("Failed to read SQLite index generation", e))
    }

    fn read_index_entry(&self, key: &str) -> CacheResult<Option<IndexEntry>> {
        let conn = self.index_db.lock();
        let row: Option<(Vec<u8>, i64)> = conn
            .query_row(
                "SELECT value, generation FROM cache_index WHERE key = ?1",
                params![key],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()
            .map_err(|e| Self::sqlite_error("Failed to read SQLite index entry", e))?;
        drop(conn);

        row.map(|(value_bytes, generation)| Self::decode_index_entry(&value_bytes, generation))
            .transpose()
    }

    fn read_file_entry(&self, key: &str, file_info: FileInfo) -> CacheResult<Option<CacheEntry>> {
        match std::fs::read(&file_info.path) {
            Ok(raw_data) => {
                self.stats.record_cold_hit();
                let data = self.decompress_if_needed(&raw_data, file_info.compressed)?;
                self.stats.record_read(data.len() as u64);
                Ok(Some(CacheEntry::new_inline(
                    key.to_string(),
                    data.to_vec(),
                    vec![],
                    None,
                )))
            }
            Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
                self.hot_cache.remove(key);
                self.warm_cache.remove(key);
                self.cold_index.write().remove(key);
                self.stats.record_miss();
                Ok(None)
            }
            Err(err) => Err(CacheError::Io(err)),
        }
    }

    fn get_current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }

    fn new_generation() -> i64 {
        let duration = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default();
        duration
            .as_secs()
            .saturating_mul(1_000_000_000)
            .saturating_add(u64::from(duration.subsec_nanos())) as i64
    }

    fn build_file_path(&self, key: &str) -> PathBuf {
        let hash = blake3::hash(key.as_bytes());
        let hex_hash = hash.to_hex();
        self.directory
            .join("data")
            .join(format!("{}.dat", &hex_hash[..16]))
    }

    fn remove_existing_persisted_entry(&self, key: &str) -> CacheResult<bool> {
        let mut removed_file = false;
        if let Some((_, file_info)) = self.cold_index.write().remove(key) {
            if !file_info.path.to_string_lossy().starts_with("memory://") {
                self.write_batcher.sync();
                match std::fs::remove_file(&file_info.path) {
                    Ok(_) => removed_file = true,
                    Err(err) if err.kind() == std::io::ErrorKind::NotFound => {}
                    Err(err) => return Err(CacheError::Io(err)),
                }
            }
        }

        let conn = self.index_db.lock();
        conn.execute("DELETE FROM cache_index WHERE key = ?1", params![key])
            .map_err(|e| Self::sqlite_error("Failed to remove SQLite index entry", e))?;
        Ok(removed_file)
    }

    fn persist_file_infos(&self, file_infos: &[(String, FileInfo)]) -> CacheResult<()> {
        if file_infos.is_empty() {
            return Ok(());
        }

        let mut conn = self.index_db.lock();
        let tx = conn
            .transaction()
            .map_err(|e| Self::sqlite_error("Failed to begin SQLite transaction", e))?;

        {
            let mut stmt = tx
                .prepare("INSERT OR REPLACE INTO cache_index (key, value, generation) VALUES (?1, ?2, ?3)")
                .map_err(|e| Self::sqlite_error("Failed to prepare SQLite file info", e))?;
            for (key, file_info) in file_infos {
                let value_bytes = bincode::encode_to_vec(file_info, bincode::config::standard())
                    .map_err(|e| {
                        CacheError::Io(std::io::Error::other(format!(
                            "Failed to serialize FileInfo: {}",
                            e
                        )))
                    })?;
                stmt.execute(params![key.as_str(), value_bytes, Self::new_generation()])
                    .map_err(|e| Self::sqlite_error("Failed to persist SQLite file info", e))?;
            }
        }

        tx.commit()
            .map_err(|e| Self::sqlite_error("Failed to commit SQLite transaction", e))?;
        Ok(())
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
        if let Some(entry) = self.hot_cache.get(key) {
            match self.read_index_generation(key)? {
                Some(generation) if generation == entry.generation => {
                    self.stats.record_hot_hit();
                    self.stats.record_read(entry.data.len() as u64);
                    return Ok(Some(CacheEntry::new_inline(
                        key.to_string(),
                        entry.data.to_vec(),
                        vec![],
                        None,
                    )));
                }
                _ => {
                    drop(entry);
                    self.hot_cache.remove(key);
                }
            }
        }

        match self.read_index_entry(key)? {
            Some(IndexEntry::Inline(entry)) => {
                self.stats.record_hot_hit();
                self.stats.record_read(entry.data.len() as u64);
                self.hot_cache.insert(key.to_string(), entry.clone());
                Ok(Some(CacheEntry::new_inline(
                    key.to_string(),
                    entry.data.to_vec(),
                    vec![],
                    None,
                )))
            }
            Some(IndexEntry::File(file_info)) => {
                self.cold_index
                    .write()
                    .insert(key.to_string(), file_info.clone());
                self.read_file_entry(key, file_info)
            }
            None => {
                self.hot_cache.remove(key);
                self.warm_cache.remove(key);
                self.cold_index.write().remove(key);
                self.stats.record_miss();
                Ok(None)
            }
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

    fn set_batch(&self, entries: Vec<(String, Vec<u8>)>) -> CacheResult<()> {
        if entries.is_empty() {
            return Ok(());
        }

        let mut file_infos = Vec::new();
        let mut inline_entries = Vec::new();
        let mut has_async_file_writes = false;

        for (key, data) in entries {
            let data_size = data.len();
            self.stats.record_write(data_size as u64);

            self.hot_cache.remove(&key);
            self.warm_cache.remove(&key);
            self.remove_existing_persisted_entry(&key)?;

            if data_size < self.config.disk_write_threshold {
                inline_entries.push((key, Bytes::from(data)));
                continue;
            }

            let (compressed_data, is_compressed) = self.compress_if_beneficial(&data);
            let file_path = self.build_file_path(&key);
            let file_info = FileInfo {
                path: file_path.clone(),
                size: compressed_data.len() as u64,
                created_at: Self::get_current_timestamp(),
                compressed: is_compressed,
            };

            self.cold_index
                .write()
                .insert(key.clone(), file_info.clone());

            if self.config.use_file_locking {
                self.write_with_lock(&file_path, &compressed_data)?;
            } else if self.config.sync_writes || data_size > 1024 * 1024 {
                std::fs::write(&file_path, &compressed_data).map_err(CacheError::Io)?;
            } else {
                self.write_batcher.write_async(file_path, compressed_data);
                has_async_file_writes = true;
            }

            file_infos.push((key, file_info));
        }

        self.cleanup_hot_cache();
        self.persist_inline_entries(&inline_entries)?;
        if has_async_file_writes {
            self.write_batcher.sync();
        }
        self.persist_file_infos(&file_infos)?;

        Ok(())
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

        let mut delete_sqlite_entry = !found;
        let mut removed_cold_entry = false;
        if let Some((_, file_info)) = self.cold_index.write().remove(key) {
            removed_cold_entry = true;
            found = true;
            delete_sqlite_entry =
                file_info.compressed || file_info.size as usize >= self.config.disk_write_threshold;
            self.write_batcher.delete_async(file_info.path);
        }

        if found && !removed_cold_entry {
            delete_sqlite_entry = true;
        }

        if !delete_sqlite_entry {
            return Ok(found);
        }

        let conn = self.index_db.lock();
        let deleted = conn
            .execute("DELETE FROM cache_index WHERE key = ?1", params![key])
            .map_err(|e| Self::sqlite_error("Failed to delete SQLite index entry", e))?;

        Ok(found || deleted > 0)
    }

    fn exists(&self, key: &str) -> CacheResult<bool> {
        let conn = self.index_db.lock();
        let exists: Option<i32> = conn
            .query_row(
                "SELECT 1 FROM cache_index WHERE key = ?1 LIMIT 1",
                params![key],
                |row| row.get(0),
            )
            .optional()
            .map_err(|e| Self::sqlite_error("Failed to check SQLite index entry", e))?;
        Ok(exists.is_some())
    }

    fn keys(&self) -> CacheResult<Vec<String>> {
        let conn = self.index_db.lock();
        let mut stmt = conn
            .prepare("SELECT key FROM cache_index")
            .map_err(|e| Self::sqlite_error("Failed to query SQLite index keys", e))?;
        let rows = stmt
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|e| Self::sqlite_error("Failed to iterate SQLite index keys", e))?;
        let mut keys = Vec::new();
        for row in rows {
            keys.push(row.map_err(|e| Self::sqlite_error("Failed to read SQLite key", e))?);
        }

        Ok(keys)
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

        let conn = self.index_db.lock();
        conn.execute("DELETE FROM cache_index", [])
            .map_err(|e| Self::sqlite_error("Failed to clear SQLite index", e))?;

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
        self.remove_existing_persisted_entry(key)?;

        if data_size < self.config.disk_write_threshold {
            let bytes = Bytes::copy_from_slice(data);
            self.persist_inline_entries(&[(key.to_string(), bytes)])?;
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
                // Async write for better performance, then wait before publishing metadata.
                self.write_batcher.write_async(file_path, compressed_data);
                self.write_batcher.sync();
            }

            self.persist_file_infos(&[(key.to_string(), file_info)])?;
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
        self.write_batcher.shutdown();
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
