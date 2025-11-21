use crate::error::{CacheError, CacheResult};
use serde::{Deserialize, Serialize};

/// Optimized serialization using MessagePack with LZ4 compression
pub struct OptimizedSerializer;

impl OptimizedSerializer {
    /// Encode data using MessagePack with smart compression
    #[allow(dead_code)]
    pub fn encode_data<T: Serialize>(value: &T) -> CacheResult<Vec<u8>> {
        // Use MessagePack for optimal performance
        let msgpack_bytes =
            rmp_serde::to_vec(value).map_err(|e| CacheError::Serialization(e.to_string()))?;

        if msgpack_bytes.len() > 1024 {
            // Only compress if data is large enough and compression provides benefit
            let compressed_bytes = lz4_flex::compress_prepend_size(&msgpack_bytes);
            if compressed_bytes.len() < msgpack_bytes.len() * 9 / 10 {
                Ok(compressed_bytes)
            } else {
                Ok(msgpack_bytes)
            }
        } else {
            Ok(msgpack_bytes)
        }
    }

    /// Decode data with automatic compression detection
    #[allow(dead_code)]
    pub fn decode_data<T: for<'de> Deserialize<'de>>(data: &[u8]) -> CacheResult<T> {
        // Try LZ4 decompression first if data is large enough
        let msgpack_bytes = if data.len() > 4 {
            match lz4_flex::decompress_size_prepended(data) {
                Ok(decompressed) => decompressed,
                Err(_) => data.to_vec(), // Not compressed, use as-is
            }
        } else {
            data.to_vec()
        };

        rmp_serde::from_slice(&msgpack_bytes)
            .map_err(|e| CacheError::Deserialization(e.to_string()))
    }
}

/// Storage mode for cache entries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum StorageMode {
    /// Data stored inline in the entry (for small data)
    Inline(Vec<u8>),
    /// Data stored in a separate file (for large data)
    File(String), // filename
}

/// Metadata for cached entries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheEntry {
    pub key: String,
    pub storage: StorageMode,
    pub created_at: u64,
    pub accessed_at: u64,
    pub access_count: u64,
    pub size: u64,
    pub tags: Vec<String>,
    pub expire_time: Option<u64>,
}

impl CacheEntry {
    /// Create a new cache entry with inline storage
    pub fn new_inline(
        key: String,
        data: Vec<u8>,
        tags: Vec<String>,
        expire_time: Option<u64>,
    ) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        let size = data.len() as u64;

        Self {
            key,
            storage: StorageMode::Inline(data),
            created_at: now,
            accessed_at: now,
            access_count: 0,
            size,
            tags,
            expire_time,
        }
    }

    /// Create a new cache entry with file storage
    pub fn new_file(
        key: String,
        filename: String,
        size: u64,
        tags: Vec<String>,
        expire_time: Option<u64>,
    ) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            key,
            storage: StorageMode::File(filename),
            created_at: now,
            accessed_at: now,
            access_count: 0,
            size,
            tags,
            expire_time,
        }
    }

    /// Create entry based on data size and threshold (backward compatibility)
    pub fn new(key: String, data: Vec<u8>, tags: Vec<String>, expire_time: Option<u64>) -> Self {
        Self::new_inline(key, data, tags, expire_time)
    }

    /// Get the data from the entry, regardless of storage mode
    pub fn get_data(&self) -> Option<&[u8]> {
        match &self.storage {
            StorageMode::Inline(data) => Some(data),
            StorageMode::File(_) => None, // Caller needs to read from file
        }
    }

    /// Get the filename if stored as file
    pub fn get_filename(&self) -> Option<&str> {
        match &self.storage {
            StorageMode::Inline(_) => None,
            StorageMode::File(filename) => Some(filename),
        }
    }

    /// Check if data is stored inline
    pub fn is_inline(&self) -> bool {
        matches!(self.storage, StorageMode::Inline(_))
    }

    pub fn update_access(&mut self) {
        self.accessed_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        self.access_count += 1;
    }

    pub fn is_expired(&self) -> bool {
        if let Some(expire_time) = self.expire_time {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs();
            now > expire_time
        } else {
            false
        }
    }
}
