use crate::error::{CacheError, CacheResult};
use bincode::{deserialize, serialize};
use serde::{Deserialize, Serialize};

/// Serialization format options
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SerializationFormat {
    Json,
    Bincode,
    MessagePack,
}

/// Compression options
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompressionType {
    None,
    Lz4,
    Zstd,
}

/// Serializer enum for different formats
#[derive(Debug)]
#[allow(dead_code)]
pub enum Serializer {
    Json(JsonSerializer),
    Bincode(BincodeSerializer),
}

impl Serializer {
    #[allow(dead_code)]
    pub fn serialize<T: Serialize>(&self, value: &T) -> CacheResult<Vec<u8>> {
        match self {
            Serializer::Json(s) => s.serialize(value),
            Serializer::Bincode(s) => s.serialize(value),
        }
    }

    #[allow(dead_code)]
    pub fn deserialize<T: for<'de> Deserialize<'de>>(&self, data: &[u8]) -> CacheResult<T> {
        match self {
            Serializer::Json(s) => s.deserialize(data),
            Serializer::Bincode(s) => s.deserialize(data),
        }
    }
}

/// Internal serializer trait for different formats
#[allow(dead_code)]
trait SerializerImpl: Send + Sync {
    fn serialize<T: Serialize>(&self, value: &T) -> CacheResult<Vec<u8>>;
    fn deserialize<T: for<'de> Deserialize<'de>>(&self, data: &[u8]) -> CacheResult<T>;
}

/// JSON serializer
#[derive(Debug)]
pub struct JsonSerializer {
    compression: CompressionType,
}

impl JsonSerializer {
    pub fn new(compression: CompressionType) -> Self {
        Self { compression }
    }
}

impl SerializerImpl for JsonSerializer {
    fn serialize<T: Serialize>(&self, value: &T) -> CacheResult<Vec<u8>> {
        let json_data =
            serde_json::to_vec(value).map_err(|e| CacheError::Serialization(e.to_string()))?;

        match self.compression {
            CompressionType::None => Ok(json_data),
            CompressionType::Lz4 => {
                let compressed = lz4_flex::compress_prepend_size(&json_data);
                Ok(compressed)
            }
            CompressionType::Zstd => {
                // For now, fallback to no compression for Zstd
                Ok(json_data)
            }
        }
    }

    fn deserialize<T: for<'de> Deserialize<'de>>(&self, data: &[u8]) -> CacheResult<T> {
        let json_data = match self.compression {
            CompressionType::None => data.to_vec(),
            CompressionType::Lz4 => lz4_flex::decompress_size_prepended(data)
                .map_err(|e| CacheError::Deserialization(e.to_string()))?,
            CompressionType::Zstd => data.to_vec(),
        };

        serde_json::from_slice(&json_data).map_err(|e| CacheError::Deserialization(e.to_string()))
    }
}

/// Bincode serializer
#[derive(Debug)]
pub struct BincodeSerializer {
    compression: CompressionType,
}

impl BincodeSerializer {
    pub fn new(compression: CompressionType) -> Self {
        Self { compression }
    }
}

impl SerializerImpl for BincodeSerializer {
    fn serialize<T: Serialize>(&self, value: &T) -> CacheResult<Vec<u8>> {
        let bincode_data = serialize(value).map_err(|e| {
            CacheError::Serialization(format!("Bincode serialization error: {:?}", e))
        })?;

        match self.compression {
            CompressionType::None => Ok(bincode_data),
            CompressionType::Lz4 => {
                let compressed = lz4_flex::compress_prepend_size(&bincode_data);
                Ok(compressed)
            }
            CompressionType::Zstd => Ok(bincode_data),
        }
    }

    fn deserialize<T: for<'de> Deserialize<'de>>(&self, data: &[u8]) -> CacheResult<T> {
        let bincode_data = match self.compression {
            CompressionType::None => data.to_vec(),
            CompressionType::Lz4 => lz4_flex::decompress_size_prepended(data)
                .map_err(|e| CacheError::Deserialization(e.to_string()))?,
            CompressionType::Zstd => data.to_vec(),
        };

        deserialize(&bincode_data).map_err(|e| {
            CacheError::Deserialization(format!("Bincode deserialization error: {:?}", e))
        })
    }
}

/// Factory for creating serializers
pub fn create_serializer(format: SerializationFormat, compression: CompressionType) -> Serializer {
    match format {
        SerializationFormat::Json => Serializer::Json(JsonSerializer::new(compression)),
        SerializationFormat::Bincode => Serializer::Bincode(BincodeSerializer::new(compression)),
        SerializationFormat::MessagePack => {
            // Fallback to JSON for now
            Serializer::Json(JsonSerializer::new(compression))
        }
    }
}

/// Metadata for cached entries
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CacheEntry {
    pub key: String,
    pub data: Vec<u8>,
    pub created_at: u64,
    pub accessed_at: u64,
    pub access_count: u64,
    pub size: u64,
    pub tags: Vec<String>,
    pub expire_time: Option<u64>,
}

impl CacheEntry {
    pub fn new(key: String, data: Vec<u8>, tags: Vec<String>, expire_time: Option<u64>) -> Self {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        Self {
            key,
            size: data.len() as u64,
            data,
            created_at: now,
            accessed_at: now,
            access_count: 1,
            tags,
            expire_time,
        }
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
