use crate::error::CacheResult;
use crate::serialization::CacheEntry;

// Only the optimized storage backend
pub mod optimized_backend;

pub use optimized_backend::OptimizedStorage;

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

    /// Downcast to Any for accessing concrete type methods
    fn as_any(&self) -> &dyn std::any::Any;
}
