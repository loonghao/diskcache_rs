use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use dashmap::DashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

/// Ultra-fast storage backend optimized for small data
/// - All data stored in memory for maximum speed
/// - Optional async disk backup for persistence
/// - Minimal overhead design
pub struct UltraFastStorage {
    directory: PathBuf,
    // Memory-only cache for ultra-fast access
    cache: Arc<DashMap<String, Vec<u8>>>,
    // Optional: async backup to disk
    #[allow(dead_code)] // May be used in future features
    enable_backup: bool,
}

impl UltraFastStorage {
    pub fn new<P: AsRef<Path>>(directory: P, enable_backup: bool) -> CacheResult<Self> {
        let directory = directory.as_ref().to_path_buf();
        std::fs::create_dir_all(&directory).map_err(CacheError::Io)?;

        Ok(Self {
            directory,
            cache: Arc::new(DashMap::new()),
            enable_backup,
        })
    }
}

impl StorageBackend for UltraFastStorage {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>> {
        if let Some(data) = self.cache.get(key) {
            let entry = CacheEntry::new_inline(key.to_string(), data.clone(), vec![], None);
            Ok(Some(entry))
        } else {
            Ok(None)
        }
    }

    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()> {
        // Extract data from entry
        let data = match &entry.storage {
            crate::serialization::StorageMode::Inline(data) => data.clone(),
            crate::serialization::StorageMode::File(filename) => {
                // For ultra-fast storage, we don't support file mode
                // Convert to inline
                std::fs::read(self.directory.join(filename)).map_err(CacheError::Io)?
            }
        };

        // Store in memory immediately
        self.cache.insert(key.to_string(), data);

        Ok(())
    }

    fn delete(&self, key: &str) -> CacheResult<bool> {
        Ok(self.cache.remove(key).is_some())
    }

    fn exists(&self, key: &str) -> CacheResult<bool> {
        Ok(self.cache.contains_key(key))
    }

    fn keys(&self) -> CacheResult<Vec<String>> {
        Ok(self.cache.iter().map(|entry| entry.key().clone()).collect())
    }

    fn clear(&self) -> CacheResult<()> {
        self.cache.clear();
        Ok(())
    }

    fn vacuum(&self) -> CacheResult<()> {
        // No-op for memory-only storage
        Ok(())
    }

    fn generate_filename(&self, key: &str) -> String {
        format!("{}.data", blake3::hash(key.as_bytes()).to_hex())
    }

    fn write_data_file(&self, filename: &str, data: &[u8]) -> CacheResult<()> {
        let file_path = self.directory.join(filename);
        std::fs::write(&file_path, data).map_err(CacheError::Io)
    }

    fn read_data_file(&self, filename: &str) -> CacheResult<Vec<u8>> {
        let file_path = self.directory.join(filename);
        std::fs::read(&file_path).map_err(CacheError::Io)
    }
}
