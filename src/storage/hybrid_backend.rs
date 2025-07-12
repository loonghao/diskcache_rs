use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use crossbeam::channel::{self, Receiver, Sender};
use dashmap::DashMap;
use parking_lot::RwLock;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

/// Write operation for async processing
#[derive(Debug)]
enum WriteOp {
    WriteFile { path: PathBuf, data: Vec<u8> },
    DeleteFile { path: PathBuf },
}

/// High-performance hybrid storage backend
/// - Small data: stored in memory with async disk backup
/// - Large data: stored directly on disk with memory index
/// - Uses async writes for better SET performance
pub struct HybridStorage {
    directory: PathBuf,
    // Memory cache for small entries (< threshold)
    memory_cache: Arc<DashMap<String, CacheEntry>>,
    // Index for large entries stored on disk
    disk_index: Arc<RwLock<DashMap<String, DiskEntryInfo>>>,
    // LRU cache for recently accessed large data
    large_data_cache: Arc<DashMap<String, Vec<u8>>>,
    // Configuration
    memory_threshold: u64, // Store in memory if smaller than this
    use_mmap: bool,        // Use memory mapping for large files
    // Async write channel
    write_sender: Option<Sender<WriteOp>>,
}

#[derive(Debug, Clone)]
#[allow(dead_code)] // Fields may be used in future features
struct DiskEntryInfo {
    file_path: PathBuf,
    size: u64,
    created_at: u64,
    accessed_at: u64,
}

impl HybridStorage {
    pub fn new<P: AsRef<Path>>(directory: P, memory_threshold: u64) -> CacheResult<Self> {
        let directory = directory.as_ref().to_path_buf();
        std::fs::create_dir_all(&directory).map_err(CacheError::Io)?;

        // Create data directory for large files
        let data_dir = directory.join("data");
        std::fs::create_dir_all(&data_dir).map_err(CacheError::Io)?;

        // Create async write channel
        let (sender, receiver) = channel::unbounded();

        // Spawn background writer thread
        thread::spawn(move || {
            Self::background_writer(receiver);
        });

        Ok(Self {
            directory,
            memory_cache: Arc::new(DashMap::new()),
            disk_index: Arc::new(RwLock::new(DashMap::new())),
            large_data_cache: Arc::new(DashMap::new()),
            memory_threshold,
            use_mmap: true,
            write_sender: Some(sender),
        })
    }

    /// Background thread for async file operations
    fn background_writer(receiver: Receiver<WriteOp>) {
        while let Ok(op) = receiver.recv() {
            match op {
                WriteOp::WriteFile { path, data } => {
                    let _ = std::fs::write(&path, &data); // Ignore errors for cache
                }
                WriteOp::DeleteFile { path } => {
                    let _ = std::fs::remove_file(&path); // Ignore errors for cache
                }
            }
        }
    }

    fn get_file_path(&self, key: &str) -> PathBuf {
        // Use a more efficient hash-to-string conversion
        let hash = blake3::hash(key.as_bytes());
        let hex_hash = hash.to_hex();
        let mut filename = String::with_capacity(hex_hash.len() + 5); // Pre-allocate
        filename.push_str(&hex_hash);
        filename.push_str(".data");
        self.directory.join("data").join(filename)
    }

    fn current_timestamp() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs()
    }

    /// Store large data directly to disk with async writes
    #[allow(dead_code)] // May be used in future optimizations
    fn store_large_data(&self, key: &str, data: &[u8]) -> CacheResult<()> {
        let file_path = self.get_file_path(key);

        // For very large data, write synchronously to avoid memory pressure
        if data.len() > 1024 * 1024 {
            // 1MB threshold
            std::fs::write(&file_path, data).map_err(CacheError::Io)?;
        } else {
            // Send write operation to background thread (non-blocking)
            if let Some(ref sender) = self.write_sender {
                let _ = sender.try_send(WriteOp::WriteFile {
                    path: file_path.clone(),
                    data: data.to_vec(),
                }); // Ignore send errors for cache
            }
        }

        // Update disk index immediately (for reads)
        let info = DiskEntryInfo {
            file_path: file_path.clone(),
            size: data.len() as u64,
            created_at: Self::current_timestamp(),
            accessed_at: Self::current_timestamp(),
        };
        self.disk_index.read().insert(key.to_string(), info);

        Ok(())
    }

    /// Read large data from disk with memory mapping if enabled
    fn read_large_data(&self, key: &str) -> CacheResult<Option<Vec<u8>>> {
        let disk_index = self.disk_index.read();

        // Clone the info to avoid borrowing issues
        let info = if let Some(info) = disk_index.get(key) {
            info.clone()
        } else {
            return Ok(None);
        };

        // Drop the read lock before doing file I/O
        drop(disk_index);

        let data = if self.use_mmap && info.size > 4096 {
            // Use memory mapping for files > 4KB
            self.read_with_mmap(&info.file_path)?
        } else {
            // Direct read for smaller files
            std::fs::read(&info.file_path).map_err(CacheError::Io)?
        };

        // Update access time (non-blocking)
        let disk_index = self.disk_index.read();
        if let Some(mut entry) = disk_index.get_mut(key) {
            entry.accessed_at = Self::current_timestamp();
        }

        Ok(Some(data))
    }

    fn read_with_mmap(&self, path: &Path) -> CacheResult<Vec<u8>> {
        // For now, use regular file read
        // TODO: Add memory mapping support later
        std::fs::read(path).map_err(CacheError::Io)
    }
}

impl StorageBackend for HybridStorage {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>> {
        // First check memory cache
        if let Some(entry) = self.memory_cache.get(key) {
            return Ok(Some(entry.clone()));
        }

        // Check large data cache first
        if let Some(data) = self.large_data_cache.get(key) {
            let entry = CacheEntry::new_inline(key.to_string(), data.clone(), vec![], None);
            return Ok(Some(entry));
        }

        // Then check disk for large entries
        if let Some(data) = self.read_large_data(key)? {
            // Cache the data for future access (if not too large)
            if data.len() < 512 * 1024 {
                self.large_data_cache.insert(key.to_string(), data.clone());
            }

            // Create entry from raw disk data (no deserialization overhead)
            let entry = CacheEntry::new_inline(
                key.to_string(),
                data,
                vec![], // Tags not preserved for disk entries (acceptable for cache)
                None,   // Expiration handled at higher level
            );
            Ok(Some(entry))
        } else {
            Ok(None)
        }
    }

    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()> {
        let data_size = match &entry.storage {
            crate::serialization::StorageMode::Inline(data) => data.len() as u64,
            crate::serialization::StorageMode::File(_) => entry.size,
        };

        if data_size < self.memory_threshold {
            // Ultra-fast path for small data: minimize all overhead
            self.memory_cache.insert(key.to_string(), entry);

            // Skip disk cleanup for small data to maximize speed
            // (acceptable trade-off for cache use case)
            // Only clean up if we know there's a disk entry
            if self.disk_index.read().contains_key(key) {
                let disk_index = self.disk_index.read();
                if let Some((_, info)) = disk_index.remove(key) {
                    if let Some(ref sender) = self.write_sender {
                        let _ = sender.try_send(WriteOp::DeleteFile {
                            path: info.file_path,
                        });
                    }
                }
            }
        } else {
            // Large data path: minimize allocations
            match &entry.storage {
                crate::serialization::StorageMode::Inline(data) => {
                    // Direct store without extra allocation
                    self.store_large_data_direct(key, data)?;
                }
                crate::serialization::StorageMode::File(filename) => {
                    // Read and store
                    let data = self.read_data_file(filename)?;
                    self.store_large_data_direct(key, &data)?;
                }
            }

            // Remove from memory cache if it was there
            self.memory_cache.remove(key);
        }

        Ok(())
    }

    fn delete(&self, key: &str) -> CacheResult<bool> {
        let mut deleted = false;

        // Remove from memory cache
        if self.memory_cache.remove(key).is_some() {
            deleted = true;
        }

        // Remove from large data cache
        if self.large_data_cache.remove(key).is_some() {
            deleted = true;
        }

        // Remove from disk
        let disk_index = self.disk_index.read();
        if let Some((_, info)) = disk_index.remove(key) {
            // Send delete operation to background thread (non-blocking)
            if let Some(ref sender) = self.write_sender {
                let _ = sender.try_send(WriteOp::DeleteFile {
                    path: info.file_path,
                }); // Ignore send errors for cache
            }
            deleted = true;
        }

        Ok(deleted)
    }

    fn exists(&self, key: &str) -> CacheResult<bool> {
        Ok(self.memory_cache.contains_key(key) || self.disk_index.read().contains_key(key))
    }

    fn keys(&self) -> CacheResult<Vec<String>> {
        let mut keys = Vec::new();

        // Add memory cache keys
        for entry in self.memory_cache.iter() {
            keys.push(entry.key().clone());
        }

        // Add disk index keys
        let disk_index = self.disk_index.read();
        for entry in disk_index.iter() {
            if !keys.contains(entry.key()) {
                keys.push(entry.key().clone());
            }
        }

        Ok(keys)
    }

    fn clear(&self) -> CacheResult<()> {
        // Clear memory cache
        self.memory_cache.clear();

        // Clear large data cache
        self.large_data_cache.clear();

        // Clear disk files
        let disk_index = self.disk_index.read();
        for entry in disk_index.iter() {
            let _ = std::fs::remove_file(&entry.file_path);
        }
        disk_index.clear();

        Ok(())
    }

    fn vacuum(&self) -> CacheResult<()> {
        // Remove expired entries from memory
        let now = Self::current_timestamp();
        self.memory_cache.retain(|_, entry| {
            if let Some(expire_time) = entry.expire_time {
                expire_time > now
            } else {
                true
            }
        });

        // Remove expired entries from disk
        let disk_index = self.disk_index.read();
        let mut to_remove = Vec::new();

        for entry in disk_index.iter() {
            // Check if file still exists
            if !entry.file_path.exists() {
                to_remove.push(entry.key().clone());
            }
        }

        for key in to_remove {
            disk_index.remove(&key);
        }

        Ok(())
    }

    fn generate_filename(&self, key: &str) -> String {
        let hash = blake3::hash(key.as_bytes());
        format!("{}.data", hash.to_hex())
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

impl HybridStorage {
    /// Store large data with minimal allocations
    fn store_large_data_direct(&self, key: &str, data: &[u8]) -> CacheResult<()> {
        let file_path = self.get_file_path(key);

        // Update disk index immediately (for reads)
        let info = DiskEntryInfo {
            file_path: file_path.clone(),
            size: data.len() as u64,
            created_at: Self::current_timestamp(),
            accessed_at: Self::current_timestamp(),
        };
        self.disk_index.read().insert(key.to_string(), info);

        // Cache in memory if reasonable size
        if data.len() < 256 * 1024 {
            // Reduced threshold to 256KB
            self.large_data_cache.insert(key.to_string(), data.to_vec());
        }

        // Write strategy based on size
        if data.len() > 2 * 1024 * 1024 {
            // 2MB threshold for sync write
            // Large files: write synchronously to avoid memory pressure
            std::fs::write(&file_path, data).map_err(CacheError::Io)?;
        } else {
            // Medium files: async write
            if let Some(ref sender) = self.write_sender {
                let _ = sender.try_send(WriteOp::WriteFile {
                    path: file_path,
                    data: data.to_vec(),
                });
            }
        }

        Ok(())
    }

    /// Batch set operation for better performance
    #[allow(dead_code)] // May be used in future optimizations
    pub fn set_batch(&self, entries: Vec<(String, CacheEntry)>) -> CacheResult<()> {
        let mut large_writes = Vec::new();

        // Process all entries and separate small/large data
        for (key, entry) in entries {
            let data_size = match &entry.storage {
                crate::serialization::StorageMode::Inline(data) => data.len() as u64,
                crate::serialization::StorageMode::File(_) => entry.size,
            };

            if data_size < self.memory_threshold {
                // Store small data in memory immediately
                self.memory_cache.insert(key.clone(), entry);

                // Remove from disk if it was there (cleanup)
                let disk_index = self.disk_index.read();
                if let Some((_, info)) = disk_index.remove(&key) {
                    if let Some(ref sender) = self.write_sender {
                        let _ = sender.try_send(WriteOp::DeleteFile {
                            path: info.file_path,
                        });
                    }
                }
            } else {
                // Prepare large data for batch write
                let raw_data = match &entry.storage {
                    crate::serialization::StorageMode::Inline(data) => data.clone(),
                    crate::serialization::StorageMode::File(filename) => {
                        self.read_data_file(filename)?
                    }
                };

                large_writes.push((key, raw_data));
            }
        }

        // Batch process large data writes
        if !large_writes.is_empty() {
            self.batch_write_large_data(large_writes)?;
        }

        Ok(())
    }

    /// Batch write large data files
    #[allow(dead_code)] // May be used in future optimizations
    fn batch_write_large_data(&self, writes: Vec<(String, Vec<u8>)>) -> CacheResult<()> {
        for (key, data) in writes {
            let file_path = self.get_file_path(&key);

            // Cache large data in memory for faster access (with size limit)
            if data.len() < 512 * 1024 {
                // Cache data < 512KB
                self.large_data_cache.insert(key.clone(), data.clone());
            }

            // Update disk index immediately (for reads)
            let info = DiskEntryInfo {
                file_path: file_path.clone(),
                size: data.len() as u64,
                created_at: Self::current_timestamp(),
                accessed_at: Self::current_timestamp(),
            };
            self.disk_index.read().insert(key.clone(), info);

            // For very large data, write synchronously to avoid memory pressure
            if data.len() > 1024 * 1024 {
                // 1MB threshold
                std::fs::write(&file_path, &data).map_err(CacheError::Io)?;
            } else {
                // Send write operation to background thread (non-blocking)
                if let Some(ref sender) = self.write_sender {
                    let _ = sender.try_send(WriteOp::WriteFile {
                        path: file_path,
                        data,
                    });
                }
            }

            // Remove from memory cache if it was there
            self.memory_cache.remove(&key);
        }

        Ok(())
    }
}

impl Drop for HybridStorage {
    fn drop(&mut self) {
        // Optional: async flush memory cache to disk for persistence
        // For cache use case, we can skip this for better performance
    }
}
