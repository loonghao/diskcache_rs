use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;

// Import high-performance storage backends
pub mod hybrid_backend;
pub mod ultra_fast_backend;

#[cfg(test)]
mod tests;

use bincode::{deserialize, serialize};
pub use hybrid_backend::HybridStorage;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::Arc;
pub use ultra_fast_backend::UltraFastStorage;

/// Storage backend trait
pub trait StorageBackend: Send + Sync {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>>;
    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()>;
    fn delete(&self, key: &str) -> CacheResult<bool>;
    fn exists(&self, key: &str) -> CacheResult<bool>;
    fn keys(&self) -> CacheResult<Vec<String>>;
    fn clear(&self) -> CacheResult<()>;
    fn vacuum(&self) -> CacheResult<()>;
    fn generate_filename(&self, key: &str) -> String;
    fn write_data_file(&self, filename: &str, data: &[u8]) -> CacheResult<()>;
    fn read_data_file(&self, filename: &str) -> CacheResult<Vec<u8>>;
}

/// File entry metadata
#[derive(Debug, Clone)]
#[allow(dead_code)] // Fields may be used in future features
pub struct FileEntry {
    pub size: u64,
    pub created_at: u64,
    pub accessed_at: u64,
}

/// File-based storage backend
pub struct FileStorage {
    directory: PathBuf,
    index: Arc<RwLock<HashMap<String, FileEntry>>>,
    use_atomic_writes: bool,
    #[allow(dead_code)]
    use_file_locking: bool,
    use_fsync: bool,
}

impl FileStorage {
    pub fn new<P: AsRef<Path>>(
        directory: P,
        use_atomic_writes: bool,
        use_file_locking: bool,
        use_fsync: bool,
    ) -> CacheResult<Self> {
        let directory = directory.as_ref().to_path_buf();
        std::fs::create_dir_all(&directory).map_err(CacheError::Io)?;

        // Check if this is a network filesystem
        let is_network_fs = false; // Simplified for now

        let mut storage = Self {
            directory,
            index: Arc::new(RwLock::new(HashMap::new())),
            use_atomic_writes: use_atomic_writes && !is_network_fs,
            use_file_locking: use_file_locking && !is_network_fs,
            use_fsync: use_fsync && !is_network_fs,
        };

        // Load existing index
        storage.load_index()?;

        Ok(storage)
    }

    fn get_file_path(&self, key: &str) -> PathBuf {
        // Use a hash of the key to avoid filesystem limitations
        let hash = blake3::hash(key.as_bytes());
        let filename = format!("{}.cache", hash.to_hex());
        self.directory.join(filename)
    }

    fn get_data_file_path(&self, filename: &str) -> PathBuf {
        self.directory.join("data").join(filename)
    }

    fn load_index(&mut self) -> CacheResult<()> {
        // Simplified index loading
        Ok(())
    }

    fn write_file_atomic(&self, path: &Path, data: &[u8]) -> CacheResult<()> {
        use std::fs::File;
        use std::io::Write;

        if self.use_atomic_writes {
            // Atomic write using temporary file
            let temp_path = path.with_extension("tmp");
            {
                let mut file = File::create(&temp_path).map_err(CacheError::Io)?;
                file.write_all(data).map_err(CacheError::Io)?;
                if self.use_fsync {
                    file.sync_all().map_err(CacheError::Io)?;
                }
            }
            std::fs::rename(&temp_path, path).map_err(CacheError::Io)?;
        } else {
            // Direct write
            let mut file = File::create(path).map_err(CacheError::Io)?;
            file.write_all(data).map_err(CacheError::Io)?;
            if self.use_fsync {
                file.sync_all().map_err(CacheError::Io)?;
            }
        }
        Ok(())
    }
}

impl StorageBackend for FileStorage {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>> {
        let file_path = self.get_file_path(key);

        if !file_path.exists() {
            return Ok(None);
        }

        let mut file = File::open(&file_path).map_err(CacheError::Io)?;
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer).map_err(CacheError::Io)?;

        let entry: CacheEntry = deserialize(&buffer).map_err(|e| {
            CacheError::Deserialization(format!("Storage deserialization error: {:?}", e))
        })?;

        // Check if expired
        if entry.is_expired() {
            self.delete(key)?;
            return Ok(None);
        }

        Ok(Some(entry))
    }

    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()> {
        let file_path = self.get_file_path(key);

        let data = serialize(&entry).map_err(|e| {
            CacheError::Serialization(format!("Storage serialization error: {:?}", e))
        })?;

        self.write_file_atomic(&file_path, &data)?;

        // Update index
        let file_entry = FileEntry {
            size: data.len() as u64,
            created_at: entry.created_at,
            accessed_at: entry.accessed_at,
        };

        self.index.write().insert(key.to_string(), file_entry);

        Ok(())
    }

    fn delete(&self, key: &str) -> CacheResult<bool> {
        let file_path = self.get_file_path(key);

        if file_path.exists() {
            std::fs::remove_file(&file_path).map_err(CacheError::Io)?;
            self.index.write().remove(key);
            Ok(true)
        } else {
            Ok(false)
        }
    }

    fn exists(&self, key: &str) -> CacheResult<bool> {
        Ok(self.index.read().contains_key(key))
    }

    fn keys(&self) -> CacheResult<Vec<String>> {
        Ok(self.index.read().keys().cloned().collect())
    }

    fn clear(&self) -> CacheResult<()> {
        let keys: Vec<String> = self.keys()?;
        for key in keys {
            self.delete(&key)?;
        }
        Ok(())
    }

    fn vacuum(&self) -> CacheResult<()> {
        // For file storage, vacuum means removing expired entries
        let keys: Vec<String> = self.keys()?;
        for key in keys {
            if let Ok(Some(entry)) = self.get(&key) {
                if entry.is_expired() {
                    self.delete(&key)?;
                }
            }
        }
        Ok(())
    }

    fn generate_filename(&self, key: &str) -> String {
        let hash = blake3::hash(key.as_bytes());
        format!("{}.data", hash.to_hex())
    }

    fn write_data_file(&self, filename: &str, data: &[u8]) -> CacheResult<()> {
        let data_dir = self.directory.join("data");
        std::fs::create_dir_all(&data_dir).map_err(CacheError::Io)?;

        let file_path = data_dir.join(filename);
        self.write_file_atomic(&file_path, data)
    }

    fn read_data_file(&self, filename: &str) -> CacheResult<Vec<u8>> {
        let file_path = self.get_data_file_path(filename);

        if !file_path.exists() {
            return Err(CacheError::Io(std::io::Error::new(
                std::io::ErrorKind::NotFound,
                "Data file not found",
            )));
        }

        let mut file = File::open(&file_path).map_err(CacheError::Io)?;
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer).map_err(CacheError::Io)?;
        Ok(buffer)
    }
}
