//! Tests for storage backends

use super::*;
use crate::serialization::CacheEntry;
use tempfile::TempDir;

/// Helper function to create a test cache entry
fn create_test_entry(key: &str, data: &[u8]) -> CacheEntry {
    CacheEntry::new_inline(key.to_string(), data.to_vec(), vec![], None)
}

#[cfg(test)]
mod ultra_fast_storage_tests {
    use super::*;
    use crate::storage::ultra_fast_backend::UltraFastStorage;

    #[test]
    fn test_ultra_fast_basic_operations() {
        let temp_dir = TempDir::new().unwrap();
        let storage = UltraFastStorage::new(temp_dir.path(), false).unwrap();

        let entry = create_test_entry("test_key", b"test_value");

        // Test set and get
        storage.set("test_key", entry.clone()).unwrap();
        let retrieved = storage.get("test_key").unwrap();
        assert!(retrieved.is_some());

        let retrieved_entry = retrieved.unwrap();
        assert_eq!(retrieved_entry.key, "test_key");

        // Test exists
        assert!(storage.exists("test_key").unwrap());
        assert!(!storage.exists("nonexistent").unwrap());

        // Test delete
        assert!(storage.delete("test_key").unwrap());
        assert!(!storage.exists("test_key").unwrap());
    }

    #[test]
    fn test_ultra_fast_keys() {
        let temp_dir = TempDir::new().unwrap();
        let storage = UltraFastStorage::new(temp_dir.path(), false).unwrap();

        // Add multiple entries
        for i in 0..5 {
            let entry = create_test_entry(&format!("key_{}", i), b"test_value");
            storage.set(&format!("key_{}", i), entry).unwrap();
        }

        let keys = storage.keys().unwrap();
        assert_eq!(keys.len(), 5);

        // Check all keys are present
        for i in 0..5 {
            assert!(keys.contains(&format!("key_{}", i)));
        }
    }

    #[test]
    fn test_ultra_fast_clear() {
        let temp_dir = TempDir::new().unwrap();
        let storage = UltraFastStorage::new(temp_dir.path(), false).unwrap();

        // Add entries
        for i in 0..3 {
            let entry = create_test_entry(&format!("key_{}", i), b"test_value");
            storage.set(&format!("key_{}", i), entry).unwrap();
        }

        assert_eq!(storage.keys().unwrap().len(), 3);

        // Clear all
        storage.clear().unwrap();
        assert_eq!(storage.keys().unwrap().len(), 0);
    }
}

#[cfg(test)]
mod hybrid_storage_tests {
    use super::*;
    use crate::storage::hybrid_backend::HybridStorage;

    #[test]
    fn test_hybrid_small_data() {
        let temp_dir = TempDir::new().unwrap();
        let storage = HybridStorage::new(temp_dir.path(), 1024).unwrap(); // 1KB threshold

        let small_data = vec![0u8; 512]; // 512 bytes - should go to memory
        let entry = create_test_entry("small_key", &small_data);

        storage.set("small_key", entry).unwrap();
        let retrieved = storage.get("small_key").unwrap();
        assert!(retrieved.is_some());

        let retrieved_entry = retrieved.unwrap();
        assert_eq!(retrieved_entry.key, "small_key");
    }

    #[test]
    fn test_hybrid_large_data() {
        let temp_dir = TempDir::new().unwrap();
        let storage = HybridStorage::new(temp_dir.path(), 1024).unwrap(); // 1KB threshold

        let large_data = vec![0u8; 2048]; // 2KB - should go to disk
        let entry = create_test_entry("large_key", &large_data);

        storage.set("large_key", entry).unwrap();
        let retrieved = storage.get("large_key").unwrap();
        assert!(retrieved.is_some());

        let retrieved_entry = retrieved.unwrap();
        assert_eq!(retrieved_entry.key, "large_key");
    }

    #[test]
    fn test_hybrid_mixed_operations() {
        let temp_dir = TempDir::new().unwrap();
        let storage = HybridStorage::new(temp_dir.path(), 1024).unwrap();

        // Add small and large data
        let small_entry = create_test_entry("small", &vec![0u8; 512]);
        let large_entry = create_test_entry("large", &vec![0u8; 2048]);

        storage.set("small", small_entry).unwrap();
        storage.set("large", large_entry).unwrap();

        // Both should be retrievable
        assert!(storage.get("small").unwrap().is_some());
        assert!(storage.get("large").unwrap().is_some());

        // Test keys
        let keys = storage.keys().unwrap();
        assert_eq!(keys.len(), 2);
        assert!(keys.contains(&"small".to_string()));
        assert!(keys.contains(&"large".to_string()));

        // Test delete
        assert!(storage.delete("small").unwrap());
        assert!(storage.delete("large").unwrap());
        assert_eq!(storage.keys().unwrap().len(), 0);
    }
}

#[cfg(test)]
mod file_storage_tests {
    use super::*;
    use crate::storage::FileStorage;

    #[test]
    fn test_file_storage_basic() {
        let temp_dir = TempDir::new().unwrap();
        let storage = FileStorage::new(temp_dir.path(), true, false, false).unwrap();

        let entry = create_test_entry("test_key", b"test_value");

        storage.set("test_key", entry).unwrap();
        let retrieved = storage.get("test_key").unwrap();
        assert!(retrieved.is_some());

        assert!(storage.exists("test_key").unwrap());
        assert!(storage.delete("test_key").unwrap());
        assert!(!storage.exists("test_key").unwrap());
    }

    #[test]
    fn test_file_storage_persistence() {
        let temp_dir = TempDir::new().unwrap();
        let entry = create_test_entry("persist_key", b"persist_value");

        // Create storage, add entry, and drop it
        {
            let storage = FileStorage::new(temp_dir.path(), true, false, false).unwrap();
            storage.set("persist_key", entry).unwrap();
        }

        // Create new storage instance and check if data persists
        {
            let storage = FileStorage::new(temp_dir.path(), true, false, false).unwrap();
            let retrieved = storage.get("persist_key").unwrap();
            assert!(retrieved.is_some());
        }
    }
}

#[cfg(test)]
mod storage_backend_tests {
    use super::*;

    fn test_storage_backend<T: StorageBackend>(storage: T) {
        let entry = create_test_entry("test_key", b"test_value");

        // Test basic operations
        storage.set("test_key", entry.clone()).unwrap();
        assert!(storage.exists("test_key").unwrap());

        let retrieved = storage.get("test_key").unwrap();
        assert!(retrieved.is_some());

        // Test keys
        let keys = storage.keys().unwrap();
        assert!(keys.contains(&"test_key".to_string()));

        // Test delete
        assert!(storage.delete("test_key").unwrap());
        assert!(!storage.exists("test_key").unwrap());

        // Test vacuum (should not fail)
        storage.vacuum().unwrap();
    }

    #[test]
    fn test_all_storage_backends() {
        let temp_dir = TempDir::new().unwrap();

        // Test UltraFastStorage
        let ultra_fast = UltraFastStorage::new(temp_dir.path().join("ultra_fast"), false).unwrap();
        test_storage_backend(ultra_fast);

        // Test HybridStorage
        let hybrid = HybridStorage::new(temp_dir.path().join("hybrid"), 1024).unwrap();
        test_storage_backend(hybrid);

        // Test FileStorage
        let file_storage =
            FileStorage::new(temp_dir.path().join("file"), true, false, false).unwrap();
        test_storage_backend(file_storage);
    }
}

#[cfg(test)]
mod performance_tests {
    use super::*;
    use std::time::Instant;

    #[test]
    fn test_ultra_fast_performance() {
        let temp_dir = TempDir::new().unwrap();
        let storage = UltraFastStorage::new(temp_dir.path(), false).unwrap();

        let data = vec![0u8; 1024]; // 1KB data
        let iterations = 1000;

        let start = Instant::now();
        for i in 0..iterations {
            let entry = create_test_entry(&format!("key_{}", i), &data);
            storage.set(&format!("key_{}", i), entry).unwrap();
        }
        let duration = start.elapsed();

        println!(
            "UltraFast SET: {} ops in {:?} ({:.1} ops/s)",
            iterations,
            duration,
            iterations as f64 / duration.as_secs_f64()
        );

        // Should be very fast (> 10k ops/s)
        let ops_per_sec = iterations as f64 / duration.as_secs_f64();
        assert!(
            ops_per_sec > 10000.0,
            "UltraFast storage should be > 10k ops/s, got {:.1}",
            ops_per_sec
        );
    }
}
