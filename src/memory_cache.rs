use crate::serialization::CacheEntry;
use lru::LruCache;
use parking_lot::RwLock;
use std::num::NonZeroUsize;
use std::sync::Arc;

/// In-memory cache layer for frequently accessed items
pub struct MemoryCache {
    cache: Arc<RwLock<LruCache<String, CacheEntry>>>,
    max_memory_size: u64,
    current_memory_size: Arc<RwLock<u64>>,
}

impl MemoryCache {
    /// Create a new memory cache with specified capacity
    pub fn new(max_entries: usize, max_memory_size: u64) -> Self {
        let capacity = NonZeroUsize::new(max_entries).unwrap_or(NonZeroUsize::new(1000).unwrap());

        Self {
            cache: Arc::new(RwLock::new(LruCache::new(capacity))),
            max_memory_size,
            current_memory_size: Arc::new(RwLock::new(0)),
        }
    }

    /// Get an entry from memory cache
    pub fn get(&self, key: &str) -> Option<CacheEntry> {
        let mut cache = self.cache.write();
        cache.get(key).cloned()
    }

    /// Put an entry into memory cache
    pub fn put(&self, key: String, entry: CacheEntry) {
        let entry_size = entry.size;

        // Check if we have space
        if entry_size > self.max_memory_size {
            return; // Entry too large for memory cache
        }

        let mut cache = self.cache.write();
        let mut current_size = self.current_memory_size.write();

        // Remove old entry if exists and update size
        if let Some(old_entry) = cache.peek(&key) {
            *current_size = current_size.saturating_sub(old_entry.size);
        }

        // Make space if needed
        while *current_size + entry_size > self.max_memory_size && !cache.is_empty() {
            if let Some((_, removed_entry)) = cache.pop_lru() {
                *current_size = current_size.saturating_sub(removed_entry.size);
            } else {
                break;
            }
        }

        // Insert new entry
        cache.put(key, entry);
        *current_size += entry_size;
    }

    /// Remove an entry from memory cache
    pub fn remove(&self, key: &str) -> Option<CacheEntry> {
        let mut cache = self.cache.write();
        if let Some(entry) = cache.pop(key) {
            let mut current_size = self.current_memory_size.write();
            *current_size = current_size.saturating_sub(entry.size);
            Some(entry)
        } else {
            None
        }
    }

    /// Clear all entries from memory cache
    pub fn clear(&self) {
        let mut cache = self.cache.write();
        cache.clear();
        *self.current_memory_size.write() = 0;
    }

    /// Check if key exists in memory cache
    #[allow(dead_code)]
    pub fn contains(&self, key: &str) -> bool {
        let cache = self.cache.read();
        cache.contains(key)
    }

    /// Get memory cache statistics
    pub fn stats(&self) -> MemoryCacheStats {
        let cache = self.cache.read();
        let current_size = *self.current_memory_size.read();

        MemoryCacheStats {
            entries: cache.len(),
            memory_used: current_size,
            memory_limit: self.max_memory_size,
            hit_rate: 0.0, // TODO: Track hit rate
        }
    }

    /// Get all keys in memory cache
    #[allow(dead_code)]
    pub fn keys(&self) -> Vec<String> {
        let cache = self.cache.read();
        cache.iter().map(|(k, _)| k.clone()).collect()
    }

    /// Promote a key to most recently used
    #[allow(dead_code)]
    pub fn touch(&self, key: &str) {
        let mut cache = self.cache.write();
        if cache.contains(key) {
            // Get and put back to update LRU order
            if let Some(entry) = cache.get(key).cloned() {
                cache.put(key.to_string(), entry);
            }
        }
    }
}

/// Memory cache statistics
#[derive(Debug, Clone)]
pub struct MemoryCacheStats {
    pub entries: usize,
    pub memory_used: u64,
    pub memory_limit: u64,
    pub hit_rate: f64,
}

impl MemoryCacheStats {
    pub fn memory_usage_percent(&self) -> f64 {
        if self.memory_limit == 0 {
            0.0
        } else {
            (self.memory_used as f64 / self.memory_limit as f64) * 100.0
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::serialization::CacheEntry;

    #[test]
    fn test_memory_cache_basic() {
        let cache = MemoryCache::new(100, 1024 * 1024); // 1MB

        let entry =
            CacheEntry::new_inline("test_key".to_string(), b"test_value".to_vec(), vec![], None);

        // Test put and get
        cache.put("test_key".to_string(), entry.clone());
        let retrieved = cache.get("test_key");
        assert!(retrieved.is_some());
        // Compare the storage data instead of the deprecated data field
        let retrieved_entry = retrieved.unwrap();
        match (&retrieved_entry.storage, &entry.storage) {
            (
                crate::serialization::StorageMode::Inline(data1),
                crate::serialization::StorageMode::Inline(data2),
            ) => {
                assert_eq!(data1, data2);
            }
            _ => panic!("Storage modes don't match"),
        }

        // Test contains
        assert!(cache.contains("test_key"));
        assert!(!cache.contains("nonexistent"));

        // Test remove
        let removed = cache.remove("test_key");
        assert!(removed.is_some());
        assert!(!cache.contains("test_key"));
    }

    #[test]
    fn test_memory_cache_lru_eviction() {
        let cache = MemoryCache::new(2, 1024); // Small cache

        let entry1 = CacheEntry::new_inline("key1".to_string(), b"value1".to_vec(), vec![], None);
        let entry2 = CacheEntry::new_inline("key2".to_string(), b"value2".to_vec(), vec![], None);
        let entry3 = CacheEntry::new_inline("key3".to_string(), b"value3".to_vec(), vec![], None);

        cache.put("key1".to_string(), entry1);
        cache.put("key2".to_string(), entry2);
        cache.put("key3".to_string(), entry3); // Should evict key1

        assert!(!cache.contains("key1"));
        assert!(cache.contains("key2"));
        assert!(cache.contains("key3"));
    }

    #[test]
    fn test_memory_cache_size_limit() {
        let cache = MemoryCache::new(100, 50); // 50 bytes limit

        let large_entry = CacheEntry::new_inline(
            "large".to_string(),
            vec![0u8; 100], // 100 bytes
            vec![],
            None,
        );

        // Should not store entry larger than limit
        cache.put("large".to_string(), large_entry);
        assert!(!cache.contains("large"));

        let small_entry = CacheEntry::new_inline(
            "small".to_string(),
            vec![0u8; 20], // 20 bytes
            vec![],
            None,
        );

        cache.put("small".to_string(), small_entry);
        assert!(cache.contains("small"));
    }
}
