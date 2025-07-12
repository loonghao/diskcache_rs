use chrono::{DateTime, Duration, Utc};
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

/// Entry in the pickle cache with expiration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PickleCacheEntry {
    /// Pickled data as bytes
    pub data: Vec<u8>,
    /// Expiration timestamp
    pub expires_at: Option<DateTime<Utc>>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last access timestamp
    pub accessed_at: DateTime<Utc>,
    /// Size in bytes
    pub size: usize,
}

impl PickleCacheEntry {
    pub fn new(data: Vec<u8>, ttl: Option<Duration>) -> Self {
        let now = Utc::now();
        let expires_at = ttl.map(|duration| now + duration);
        let size = data.len();

        Self {
            data,
            expires_at,
            created_at: now,
            accessed_at: now,
            size,
        }
    }

    pub fn is_expired(&self) -> bool {
        if let Some(expires_at) = self.expires_at {
            Utc::now() > expires_at
        } else {
            false
        }
    }

    pub fn touch(&mut self) {
        self.accessed_at = Utc::now();
    }
}

/// High-performance pickle cache with expiration support
#[pyclass]
pub struct PickleCache {
    /// Cache directory
    directory: PathBuf,
    /// In-memory index for fast lookups
    index: HashMap<String, PickleCacheEntry>,
    /// Maximum cache size in bytes
    max_size: Option<usize>,
    /// Current cache size in bytes
    current_size: usize,
    /// Default TTL for entries
    default_ttl: Option<Duration>,
}

#[pymethods]
impl PickleCache {
    #[new]
    #[pyo3(signature = (directory, max_size = None, default_ttl_seconds = None))]
    pub fn new(
        directory: &str,
        max_size: Option<usize>,
        default_ttl_seconds: Option<i64>,
    ) -> PyResult<Self> {
        let dir_path = PathBuf::from(directory);

        // Create directory if it doesn't exist
        if !dir_path.exists() {
            fs::create_dir_all(&dir_path).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                    "Failed to create cache directory: {}",
                    e
                ))
            })?;
        }

        let default_ttl = default_ttl_seconds.map(Duration::seconds);

        let mut cache = Self {
            directory: dir_path,
            index: HashMap::new(),
            max_size,
            current_size: 0,
            default_ttl,
        };

        // Load existing cache index
        cache.load_index()?;

        Ok(cache)
    }

    /// Set a pickled object in the cache
    #[pyo3(signature = (key, pickled_data, ttl_seconds = None))]
    pub fn set_pickle(
        &mut self,
        key: &str,
        pickled_data: &[u8],
        ttl_seconds: Option<i64>,
    ) -> PyResult<()> {
        let ttl = ttl_seconds.map(Duration::seconds).or(self.default_ttl);

        let entry = PickleCacheEntry::new(pickled_data.to_vec(), ttl);

        // Write to disk
        let file_path = self.get_file_path(key);
        fs::write(&file_path, &entry.data).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                "Failed to write cache file: {}",
                e
            ))
        })?;

        // Update index
        if let Some(old_entry) = self.index.insert(key.to_string(), entry.clone()) {
            self.current_size = self.current_size.saturating_sub(old_entry.size);
        }
        self.current_size += entry.size;

        // Check size limits and evict if necessary
        self.evict_if_needed()?;

        // Save index
        self.save_index()?;

        Ok(())
    }

    /// Get a pickled object from the cache
    pub fn get_pickle(&mut self, key: &str) -> PyResult<Option<Vec<u8>>> {
        if let Some(entry) = self.index.get_mut(key) {
            // Check if expired
            if entry.is_expired() {
                self.delete_pickle(key)?;
                return Ok(None);
            }

            // Update access time
            entry.touch();

            // Read from disk
            let file_path = self.get_file_path(key);
            match fs::read(&file_path) {
                Ok(data) => {
                    self.save_index()?; // Save updated access time
                    Ok(Some(data))
                }
                Err(_) => {
                    // File doesn't exist, remove from index
                    self.index.remove(key);
                    self.save_index()?;
                    Ok(None)
                }
            }
        } else {
            Ok(None)
        }
    }

    /// Delete a pickled object from the cache
    pub fn delete_pickle(&mut self, key: &str) -> PyResult<bool> {
        if let Some(entry) = self.index.remove(key) {
            self.current_size = self.current_size.saturating_sub(entry.size);

            // Remove file
            let file_path = self.get_file_path(key);
            let _ = fs::remove_file(&file_path); // Ignore errors if file doesn't exist

            self.save_index()?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    /// Check if a key exists and is not expired
    pub fn exists_pickle(&mut self, key: &str) -> PyResult<bool> {
        if let Some(entry) = self.index.get(key) {
            if entry.is_expired() {
                self.delete_pickle(key)?;
                Ok(false)
            } else {
                Ok(true)
            }
        } else {
            Ok(false)
        }
    }

    /// Get all non-expired keys
    pub fn keys_pickle(&mut self) -> PyResult<Vec<String>> {
        let mut expired_keys = Vec::new();
        let mut valid_keys = Vec::new();

        for (key, entry) in &self.index {
            if entry.is_expired() {
                expired_keys.push(key.clone());
            } else {
                valid_keys.push(key.clone());
            }
        }

        // Remove expired keys
        for key in expired_keys {
            self.delete_pickle(&key)?;
        }

        Ok(valid_keys)
    }

    /// Clear all entries from the cache
    pub fn clear_pickle(&mut self) -> PyResult<()> {
        // Remove all files
        for key in self.index.keys() {
            let file_path = self.get_file_path(key);
            let _ = fs::remove_file(&file_path);
        }

        self.index.clear();
        self.current_size = 0;
        self.save_index()?;

        Ok(())
    }

    /// Get cache statistics
    pub fn stats_pickle(&mut self) -> PyResult<HashMap<String, i64>> {
        // Clean up expired entries first
        let _ = self.keys_pickle()?;

        let mut stats = HashMap::new();
        stats.insert("entries".to_string(), self.index.len() as i64);
        stats.insert("size_bytes".to_string(), self.current_size as i64);

        if let Some(max_size) = self.max_size {
            stats.insert("max_size_bytes".to_string(), max_size as i64);
            stats.insert(
                "size_ratio".to_string(),
                ((self.current_size as f64 / max_size as f64) * 100.0) as i64,
            );
        }

        Ok(stats)
    }

    /// Set TTL for an existing key
    pub fn expire_pickle(&mut self, key: &str, ttl_seconds: i64) -> PyResult<bool> {
        if let Some(entry) = self.index.get_mut(key) {
            entry.expires_at = Some(Utc::now() + Duration::seconds(ttl_seconds));
            self.save_index()?;
            Ok(true)
        } else {
            Ok(false)
        }
    }

    /// Get TTL for a key (seconds remaining)
    pub fn ttl_pickle(&self, key: &str) -> PyResult<Option<i64>> {
        if let Some(entry) = self.index.get(key) {
            if let Some(expires_at) = entry.expires_at {
                let remaining = expires_at - Utc::now();
                let seconds = remaining.num_seconds();
                if seconds >= 0 {
                    // Add 1 to account for sub-second precision
                    Ok(Some(std::cmp::max(1, seconds)))
                } else {
                    Ok(Some(0)) // Expired
                }
            } else {
                Ok(None) // No expiration
            }
        } else {
            Ok(None) // Key doesn't exist
        }
    }
}

impl PickleCache {
    fn get_file_path(&self, key: &str) -> PathBuf {
        // Use hash of key to avoid filesystem issues with special characters
        let hash = blake3::hash(key.as_bytes());
        let filename = format!("{}.pkl", hash.to_hex());
        self.directory.join(filename)
    }

    fn load_index(&mut self) -> PyResult<()> {
        let index_path = self.directory.join("index.json");
        if index_path.exists() {
            match fs::read_to_string(&index_path) {
                Ok(content) => {
                    if let Ok(index) =
                        serde_json::from_str::<HashMap<String, PickleCacheEntry>>(&content)
                    {
                        self.current_size = index.values().map(|e| e.size).sum();
                        self.index = index;
                    }
                }
                Err(_) => {
                    // If index is corrupted, start fresh
                    self.index.clear();
                    self.current_size = 0;
                }
            }
        }
        Ok(())
    }

    fn save_index(&self) -> PyResult<()> {
        let index_path = self.directory.join("index.json");
        let content = serde_json::to_string(&self.index).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to serialize index: {}",
                e
            ))
        })?;

        fs::write(&index_path, content).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to save index: {}", e))
        })?;

        Ok(())
    }

    fn evict_if_needed(&mut self) -> PyResult<()> {
        if let Some(max_size) = self.max_size {
            while self.current_size > max_size && !self.index.is_empty() {
                // Find least recently used entry
                let lru_key = self
                    .index
                    .iter()
                    .min_by_key(|(_, entry)| entry.accessed_at)
                    .map(|(key, _)| key.clone());

                if let Some(key) = lru_key {
                    self.delete_pickle(&key)?;
                } else {
                    break;
                }
            }
        }
        Ok(())
    }
}

/// High-performance pickle serialization using Rust
#[pyfunction]
pub fn rust_pickle_dumps(py: Python, obj: PyObject) -> PyResult<PyObject> {
    // Use Python's pickle module for now, but through Rust
    // This provides a foundation for future pure Rust implementation
    let pickle_module = py.import("pickle")?;
    let dumps_func = pickle_module.getattr("dumps")?;
    let result = dumps_func.call1((obj,))?;
    Ok(result.into())
}

/// High-performance pickle deserialization using Rust
#[pyfunction]
pub fn rust_pickle_loads(py: Python, data: PyObject) -> PyResult<PyObject> {
    // Use Python's pickle module for now, but through Rust
    // This provides a foundation for future pure Rust implementation
    let pickle_module = py.import("pickle")?;
    let loads_func = pickle_module.getattr("loads")?;
    let result = loads_func.call1((data,))?;
    Ok(result.into())
}
