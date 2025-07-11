use crate::error::CacheResult;
use crate::eviction::{CombinedEviction, EvictionPolicy, EvictionStrategy};
use crate::serialization::{CacheEntry, CompressionType, SerializationFormat, create_serializer};
use crate::storage::{FileStorage, StorageBackend};
use crate::utils::{CacheStats, validate_cache_config, validate_key, current_timestamp};
use crate::memory_cache::MemoryCache;
use crate::migration::{detect_diskcache_format, DiskCacheMigrator};
use parking_lot::RwLock;
use pyo3::prelude::*;
use std::path::PathBuf;
use std::sync::Arc;
use std::collections::HashMap;

/// Cache configuration
#[derive(Debug, Clone)]
pub struct CacheConfig {
    pub directory: PathBuf,
    pub max_size: Option<u64>,
    pub max_entries: Option<u64>,
    pub eviction_strategy: EvictionStrategy,
    pub serialization_format: SerializationFormat,
    pub compression: CompressionType,
    pub use_atomic_writes: bool,
    pub use_file_locking: bool,
    pub auto_vacuum: bool,
    pub vacuum_interval: u64, // seconds
    pub memory_cache_size: u64, // bytes
    pub memory_cache_entries: usize,
    pub auto_migrate: bool,
}

impl Default for CacheConfig {
    fn default() -> Self {
        Self {
            directory: PathBuf::from("./cache"),
            max_size: Some(1024 * 1024 * 1024), // 1GB
            max_entries: Some(100_000),
            eviction_strategy: EvictionStrategy::LruTtl,
            serialization_format: SerializationFormat::Bincode,
            compression: CompressionType::Lz4,
            use_atomic_writes: true,
            use_file_locking: true,
            auto_vacuum: true,
            vacuum_interval: 3600, // 1 hour
            memory_cache_size: 64 * 1024 * 1024, // 64MB
            memory_cache_entries: 10000,
            auto_migrate: true,
        }
    }
}

/// High-performance disk cache implementation
pub struct Cache {
    config: CacheConfig,
    storage: Box<dyn StorageBackend>,
    eviction: Box<dyn EvictionPolicy>,
    serializer: crate::serialization::Serializer,
    stats: Arc<RwLock<CacheStats>>,
    last_vacuum: Arc<RwLock<u64>>,
    memory_cache: Option<MemoryCache>,
}

impl Cache {
    /// Create a new cache with the given configuration
    pub fn new(config: CacheConfig) -> CacheResult<Self> {
        // Validate configuration
        validate_cache_config(
            config.max_size,
            config.max_entries,
            &config.directory,
        )?;
        
        // Create storage backend
        let storage = Box::new(FileStorage::new(
            &config.directory,
            config.use_atomic_writes,
            config.use_file_locking,
        )?);
        
        // Create eviction policy
        let eviction = Box::new(CombinedEviction::new(config.eviction_strategy));
        
        // Create serializer
        let serializer = create_serializer(config.serialization_format, config.compression);

        // Create memory cache if enabled
        let memory_cache = if config.memory_cache_size > 0 && config.memory_cache_entries > 0 {
            Some(MemoryCache::new(config.memory_cache_entries, config.memory_cache_size))
        } else {
            None
        };

        let mut cache = Self {
            config,
            storage,
            eviction,
            serializer,
            stats: Arc::new(RwLock::new(CacheStats::new())),
            last_vacuum: Arc::new(RwLock::new(current_timestamp())),
            memory_cache,
        };

        // Auto-migrate if needed
        if cache.config.auto_migrate {
            cache.auto_migrate_diskcache_data()?;
        }

        Ok(cache)
    }
    
    /// Create a cache with default configuration in the specified directory
    pub fn with_directory<P: Into<PathBuf>>(directory: P) -> CacheResult<Self> {
        let mut config = CacheConfig::default();
        config.directory = directory.into();
        Self::new(config)
    }
    
    /// Get a value from the cache
    pub fn get(&self, key: &str) -> CacheResult<Option<Vec<u8>>> {
        validate_key(key)?;

        // Try memory cache first
        if let Some(ref memory_cache) = self.memory_cache {
            if let Some(mut entry) = memory_cache.get(key) {
                // Update access statistics
                entry.update_access();
                self.eviction.on_access(key, &entry);

                // Update memory cache with new access info
                memory_cache.put(key.to_string(), entry.clone());

                // Update stats
                self.stats.write().hits += 1;

                return Ok(Some(entry.data));
            }
        }

        // Try disk storage
        match self.storage.get(key)? {
            Some(mut entry) => {
                // Update access statistics
                entry.update_access();
                self.eviction.on_access(key, &entry);

                // Update storage with new access info
                self.storage.set(key, entry.clone())?;

                // Store in memory cache for future access
                if let Some(ref memory_cache) = self.memory_cache {
                    memory_cache.put(key.to_string(), entry.clone());
                }

                // Update stats
                self.stats.write().hits += 1;

                Ok(Some(entry.data))
            }
            None => {
                self.stats.write().misses += 1;
                Ok(None)
            }
        }
    }
    
    /// Set a value in the cache
    pub fn set(
        &self,
        key: &str,
        value: &[u8],
        expire_time: Option<u64>,
        tags: Vec<String>,
    ) -> CacheResult<()> {
        validate_key(key)?;
        
        // Check if we need to evict entries
        self.maybe_evict()?;
        
        // Create cache entry
        let entry = CacheEntry::new(
            key.to_string(),
            value.to_vec(),
            tags,
            expire_time,
        );
        
        // Store the entry
        self.storage.set(key, entry.clone())?;
        self.eviction.on_insert(key, &entry);

        // Store in memory cache
        if let Some(ref memory_cache) = self.memory_cache {
            memory_cache.put(key.to_string(), entry.clone());
        }

        // Update stats
        let mut stats = self.stats.write();
        stats.sets += 1;
        stats.total_size += entry.size;
        stats.entry_count += 1;
        
        Ok(())
    }
    
    /// Delete a value from the cache
    pub fn delete(&self, key: &str) -> CacheResult<bool> {
        validate_key(key)?;
        
        let existed = self.storage.delete(key)?;
        if existed {
            self.eviction.on_remove(key);

            // Remove from memory cache
            if let Some(ref memory_cache) = self.memory_cache {
                memory_cache.remove(key);
            }

            let mut stats = self.stats.write();
            stats.deletes += 1;
            stats.entry_count = stats.entry_count.saturating_sub(1);
        }
        
        Ok(existed)
    }
    
    /// Check if a key exists in the cache
    pub fn exists(&self, key: &str) -> CacheResult<bool> {
        validate_key(key)?;
        self.storage.exists(key)
    }
    
    /// Get all keys in the cache
    pub fn keys(&self) -> CacheResult<Vec<String>> {
        self.storage.keys()
    }
    
    /// Clear all entries from the cache
    pub fn clear(&self) -> CacheResult<()> {
        self.storage.clear()?;
        self.eviction.clear();

        // Clear memory cache
        if let Some(ref memory_cache) = self.memory_cache {
            memory_cache.clear();
        }

        let mut stats = self.stats.write();
        *stats = CacheStats::new();

        Ok(())
    }
    
    /// Get cache statistics
    pub fn stats(&self) -> CacheStats {
        self.stats.read().clone()
    }
    
    /// Get current cache size in bytes
    pub fn size(&self) -> CacheResult<u64> {
        self.storage.size()
    }
    
    /// Manually trigger vacuum operation
    pub fn vacuum(&self) -> CacheResult<()> {
        self.storage.vacuum()?;
        *self.last_vacuum.write() = current_timestamp();
        Ok(())
    }
    
    /// Check if eviction is needed and perform it
    fn maybe_evict(&self) -> CacheResult<()> {
        let current_size = self.size()?;
        let current_entries = self.keys()?.len() as u64;
        
        let mut evict_count = 0;
        
        // Check size limit
        if let Some(max_size) = self.config.max_size {
            if current_size > max_size {
                // Evict 10% of entries or enough to get under limit
                evict_count = std::cmp::max(
                    evict_count,
                    (current_entries / 10).max(1),
                );
            }
        }
        
        // Check entry count limit
        if let Some(max_entries) = self.config.max_entries {
            if current_entries > max_entries {
                evict_count = std::cmp::max(
                    evict_count,
                    current_entries - max_entries + (max_entries / 10),
                );
            }
        }
        
        // Perform eviction
        if evict_count > 0 {
            let victims = self.eviction.select_victims(evict_count as usize);
            for key in victims {
                self.storage.delete(&key)?;
                self.eviction.on_remove(&key);
                self.stats.write().evictions += 1;
            }
        }
        
        // Auto vacuum if needed
        if self.config.auto_vacuum {
            let last_vacuum = *self.last_vacuum.read();
            let now = current_timestamp();
            if now - last_vacuum > self.config.vacuum_interval {
                self.vacuum()?;
            }
        }
        
        Ok(())
    }

    /// Auto-migrate from python-diskcache if detected
    fn auto_migrate_diskcache_data(&mut self) -> CacheResult<()> {
        if detect_diskcache_format(&self.config.directory) {
            tracing::info!("Detected python-diskcache data, starting auto-migration...");

            // Create a backup first
            let backup_dir = self.config.directory.join("diskcache_backup");
            if !backup_dir.exists() {
                let cache_db = self.config.directory.join("cache.db");
                let backup_db = backup_dir.join("cache.db");
                std::fs::create_dir_all(&backup_dir)?;
                std::fs::copy(&cache_db, &backup_db)?;
                tracing::info!("Created backup at: {:?}", backup_dir);
            }

            // Perform migration
            let mut migrator = DiskCacheMigrator::new(
                self.config.directory.clone(),
                Box::new(FileStorage::new(
                    &self.config.directory,
                    self.config.use_atomic_writes,
                    self.config.use_file_locking,
                )?),
            );

            match migrator.migrate() {
                Ok(stats) => {
                    tracing::info!("Migration completed: {:?}", stats);
                    if stats.success {
                        // Rename the original database to avoid future migrations
                        let cache_db = self.config.directory.join("cache.db");
                        let migrated_db = self.config.directory.join("cache.db.migrated");
                        if cache_db.exists() && !migrated_db.exists() {
                            std::fs::rename(&cache_db, &migrated_db)?;
                        }
                    }
                }
                Err(e) => {
                    tracing::warn!("Migration failed: {}", e);
                    // Continue without migration
                }
            }
        }

        Ok(())
    }

    /// Get memory cache statistics
    pub fn memory_stats(&self) -> Option<crate::memory_cache::MemoryCacheStats> {
        self.memory_cache.as_ref().map(|mc| mc.stats())
    }

    /// Manually migrate from python-diskcache
    pub fn migrate_from_diskcache(&mut self) -> CacheResult<crate::migration::MigrationStats> {
        let mut migrator = DiskCacheMigrator::new(
            self.config.directory.clone(),
            Box::new(FileStorage::new(
                &self.config.directory,
                self.config.use_atomic_writes,
                self.config.use_file_locking,
            )?),
        );

        migrator.migrate()
    }
}

/// Python wrapper for the Cache
#[pyclass]
pub struct PyCache {
    cache: Cache,
}

#[pymethods]
impl PyCache {
    #[new]
    #[pyo3(signature = (directory, max_size=None, max_entries=None))]
    fn new(
        directory: String,
        max_size: Option<u64>,
        max_entries: Option<u64>,
    ) -> PyResult<Self> {
        let mut config = CacheConfig::default();
        config.directory = PathBuf::from(directory);
        config.max_size = max_size;
        config.max_entries = max_entries;
        
        let cache = Cache::new(config)?;
        Ok(Self { cache })
    }
    
    fn get(&self, key: &str) -> PyResult<Option<Vec<u8>>> {
        Ok(self.cache.get(key)?)
    }
    
    #[pyo3(signature = (key, value, expire_time=None, tags=None))]
    fn set(
        &self,
        key: &str,
        value: &[u8],
        expire_time: Option<u64>,
        tags: Option<Vec<String>>,
    ) -> PyResult<()> {
        let tags = tags.unwrap_or_default();
        Ok(self.cache.set(key, value, expire_time, tags)?)
    }
    
    fn delete(&self, key: &str) -> PyResult<bool> {
        Ok(self.cache.delete(key)?)
    }
    
    fn exists(&self, key: &str) -> PyResult<bool> {
        Ok(self.cache.exists(key)?)
    }
    
    fn keys(&self) -> PyResult<Vec<String>> {
        Ok(self.cache.keys()?)
    }
    
    fn clear(&self) -> PyResult<()> {
        Ok(self.cache.clear()?)
    }
    
    fn size(&self) -> PyResult<u64> {
        Ok(self.cache.size()?)
    }
    
    fn vacuum(&self) -> PyResult<()> {
        Ok(self.cache.vacuum()?)
    }
    
    fn stats(&self) -> PyResult<HashMap<String, u64>> {
        let stats = self.cache.stats();
        let mut result = HashMap::new();
        result.insert("hits".to_string(), stats.hits);
        result.insert("misses".to_string(), stats.misses);
        result.insert("sets".to_string(), stats.sets);
        result.insert("deletes".to_string(), stats.deletes);
        result.insert("evictions".to_string(), stats.evictions);
        result.insert("errors".to_string(), stats.errors);
        result.insert("total_size".to_string(), stats.total_size);
        result.insert("entry_count".to_string(), stats.entry_count);
        Ok(result)
    }
    
    fn hit_rate(&self) -> PyResult<f64> {
        Ok(self.cache.stats().hit_rate())
    }
}
