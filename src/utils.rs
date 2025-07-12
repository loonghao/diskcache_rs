use crate::error::{CacheError, CacheResult};
use std::time::{SystemTime, UNIX_EPOCH};

/// Get current timestamp in seconds since Unix epoch
pub fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

/// Get current timestamp in milliseconds since Unix epoch
#[allow(dead_code)]
pub fn current_timestamp_millis() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

/// Convert bytes to human readable format
#[allow(dead_code)]
pub fn format_bytes(bytes: u64) -> String {
    const UNITS: &[&str] = &["B", "KB", "MB", "GB", "TB"];
    const THRESHOLD: u64 = 1024;

    if bytes < THRESHOLD {
        return format!("{} B", bytes);
    }

    let mut size = bytes as f64;
    let mut unit_index = 0;

    while size >= THRESHOLD as f64 && unit_index < UNITS.len() - 1 {
        size /= THRESHOLD as f64;
        unit_index += 1;
    }

    format!("{:.1} {}", size, UNITS[unit_index])
}

/// Calculate hash for a key
#[allow(dead_code)]
pub fn hash_key(key: &str) -> String {
    blake3::hash(key.as_bytes()).to_hex().to_string()
}

/// Validate key format
pub fn validate_key(key: &str) -> CacheResult<()> {
    if key.is_empty() {
        return Err(CacheError::InvalidConfig("Key cannot be empty".to_string()));
    }

    if key.len() > 250 {
        return Err(CacheError::InvalidConfig(
            "Key too long (max 250 characters)".to_string(),
        ));
    }

    // Check for invalid characters that might cause filesystem issues
    let invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0'];
    if key.chars().any(|c| invalid_chars.contains(&c)) {
        return Err(CacheError::InvalidConfig(
            "Key contains invalid characters".to_string(),
        ));
    }

    Ok(())
}

/// Sanitize key for filesystem use
#[allow(dead_code)]
pub fn sanitize_key(key: &str) -> String {
    // Replace invalid characters with underscores
    let invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0'];
    key.chars()
        .map(|c| if invalid_chars.contains(&c) { '_' } else { c })
        .collect()
}

/// Check if a path is likely on a network filesystem
#[allow(dead_code)]
pub fn is_network_path(path: &std::path::Path) -> bool {
    let path_str = path.to_string_lossy();

    // Check for UNC paths on Windows
    if path_str.starts_with("\\\\") {
        return true;
    }

    // Check for common network mount points on Unix
    if path_str.starts_with("/mnt/")
        || path_str.starts_with("/net/")
        || path_str.starts_with("/nfs/")
    {
        return true;
    }

    false
}

/// Retry mechanism for operations that might fail on network filesystems
#[allow(dead_code)]
pub async fn retry_operation<F, T, E>(
    operation: F,
    max_retries: usize,
    initial_delay_ms: u64,
) -> Result<T, E>
where
    F: Fn() -> Result<T, E>,
    E: std::fmt::Debug,
{
    let mut delay = initial_delay_ms;

    for attempt in 0..=max_retries {
        match operation() {
            Ok(result) => return Ok(result),
            Err(e) => {
                if attempt == max_retries {
                    return Err(e);
                }

                tracing::warn!(
                    "Operation failed (attempt {}), retrying in {}ms: {:?}",
                    attempt + 1,
                    delay,
                    e
                );

                tokio::time::sleep(tokio::time::Duration::from_millis(delay)).await;
                delay = std::cmp::min(delay * 2, 5000); // Exponential backoff, max 5s
            }
        }
    }

    unreachable!()
}

/// File locking utilities for network filesystems
pub struct FileLock {
    #[cfg(unix)]
    file: Option<std::fs::File>,
    #[cfg(windows)]
    file: Option<std::fs::File>,
}

impl FileLock {
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self { file: None }
    }

    #[allow(dead_code)]
    pub fn try_lock(&mut self, path: &std::path::Path) -> CacheResult<bool> {
        use std::fs::OpenOptions;

        let lock_file = path.with_extension("lock");

        match OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&lock_file)
        {
            Ok(file) => {
                self.file = Some(file);
                Ok(true)
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(false),
            Err(e) => Err(CacheError::Io(e)),
        }
    }

    pub fn unlock(&mut self) -> CacheResult<()> {
        if let Some(_file) = self.file.take() {
            // File will be closed when dropped
        }
        Ok(())
    }
}

impl Drop for FileLock {
    fn drop(&mut self) {
        let _ = self.unlock();
    }
}

/// Statistics collection
#[derive(Debug, Clone, Default)]
pub struct CacheStats {
    pub hits: u64,
    pub misses: u64,
    pub sets: u64,
    pub deletes: u64,
    pub evictions: u64,
    pub errors: u64,
    pub total_size: u64,
    pub entry_count: u64,
}

impl CacheStats {
    pub fn new() -> Self {
        Default::default()
    }

    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }

    pub fn miss_rate(&self) -> f64 {
        1.0 - self.hit_rate()
    }

    pub fn average_entry_size(&self) -> f64 {
        if self.entry_count == 0 {
            0.0
        } else {
            self.total_size as f64 / self.entry_count as f64
        }
    }
}

/// Configuration validation
pub fn validate_cache_config(
    max_size: Option<u64>,
    max_entries: Option<u64>,
    directory: &std::path::Path,
) -> CacheResult<()> {
    // Check if directory exists or can be created
    if !directory.exists() {
        std::fs::create_dir_all(directory)
            .map_err(|e| CacheError::InvalidConfig(format!("Cannot create directory: {}", e)))?;
    }

    // Check if directory is writable
    let test_file = directory.join(".test_write");
    std::fs::write(&test_file, b"test")
        .map_err(|e| CacheError::InvalidConfig(format!("Directory not writable: {}", e)))?;
    std::fs::remove_file(&test_file)
        .map_err(|e| CacheError::InvalidConfig(format!("Cannot clean up test file: {}", e)))?;

    // Validate size limits
    if let Some(max_size) = max_size {
        if max_size == 0 {
            return Err(CacheError::InvalidConfig(
                "Max size cannot be zero".to_string(),
            ));
        }
    }

    if let Some(max_entries) = max_entries {
        if max_entries == 0 {
            return Err(CacheError::InvalidConfig(
                "Max entries cannot be zero".to_string(),
            ));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_bytes() {
        assert_eq!(format_bytes(0), "0 B");
        assert_eq!(format_bytes(512), "512 B");
        assert_eq!(format_bytes(1024), "1.0 KB");
        assert_eq!(format_bytes(1536), "1.5 KB");
        assert_eq!(format_bytes(1048576), "1.0 MB");
    }

    #[test]
    fn test_validate_key() {
        assert!(validate_key("valid_key").is_ok());
        assert!(validate_key("").is_err());
        assert!(validate_key("key/with/slash").is_err());
        assert!(validate_key(&"x".repeat(300)).is_err());
    }

    #[test]
    fn test_sanitize_key() {
        assert_eq!(sanitize_key("valid_key"), "valid_key");
        assert_eq!(sanitize_key("key/with\\slash"), "key_with_slash");
        assert_eq!(
            sanitize_key("key:with*special?chars"),
            "key_with_special_chars"
        );
    }

    #[test]
    fn test_cache_stats() {
        let mut stats = CacheStats::new();
        stats.hits = 80;
        stats.misses = 20;

        assert!((stats.hit_rate() - 0.8).abs() < f64::EPSILON);
        assert!((stats.miss_rate() - 0.2).abs() < f64::EPSILON);
    }
}
