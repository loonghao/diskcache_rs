use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use crate::storage::StorageBackend;
use rusqlite::{Connection, Row};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

/// Migrates data from python-diskcache format to diskcache_rs format
pub struct DiskCacheMigrator {
    source_dir: PathBuf,
    target_storage: Box<dyn StorageBackend>,
}

impl DiskCacheMigrator {
    pub fn new(source_dir: PathBuf, target_storage: Box<dyn StorageBackend>) -> Self {
        Self {
            source_dir,
            target_storage,
        }
    }

    /// Check if the directory contains a python-diskcache database
    pub fn has_diskcache_data(&self) -> bool {
        let cache_db = self.source_dir.join("cache.db");
        cache_db.exists() && cache_db.is_file()
    }

    /// Migrate all data from python-diskcache to our format
    pub fn migrate(&mut self) -> CacheResult<MigrationStats> {
        if !self.has_diskcache_data() {
            return Err(CacheError::InvalidConfig(
                "No python-diskcache data found".to_string(),
            ));
        }

        let cache_db = self.source_dir.join("cache.db");
        let conn = Connection::open(&cache_db)
            .map_err(|e| CacheError::Unknown(format!("Failed to open SQLite database: {}", e)))?;

        let mut stats = MigrationStats::default();

        // First, get the schema to understand the table structure
        let tables = self.get_tables(&conn)?;
        tracing::info!("Found tables: {:?}", tables);

        // Migrate cache entries
        if tables.contains(&"cache".to_string()) {
            stats.entries_migrated += self.migrate_cache_table(&conn)?;
        }

        // Migrate settings if they exist
        if tables.contains(&"settings".to_string()) {
            self.migrate_settings_table(&conn)?;
        }

        stats.success = true;
        Ok(stats)
    }

    /// Get list of tables in the database
    fn get_tables(&self, conn: &Connection) -> CacheResult<Vec<String>> {
        let mut stmt = conn
            .prepare(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            )
            .map_err(|e| CacheError::Unknown(format!("Failed to prepare statement: {}", e)))?;

        let table_iter = stmt
            .query_map([], |row| row.get::<_, String>(0))
            .map_err(|e| CacheError::Unknown(format!("Failed to query tables: {}", e)))?;

        let mut tables = Vec::new();
        for table in table_iter {
            tables
                .push(table.map_err(|e| {
                    CacheError::Unknown(format!("Failed to get table name: {}", e))
                })?);
        }

        Ok(tables)
    }

    /// Migrate the main cache table
    fn migrate_cache_table(&mut self, conn: &Connection) -> CacheResult<u64> {
        // First, check the schema of the cache table
        let columns = self.get_table_columns(conn, "cache")?;
        tracing::info!("Cache table columns: {:?}", columns);

        // Prepare query based on available columns
        let query = if columns.contains(&"tag".to_string()) {
            "SELECT key, raw, expire_time, access_time, access_count, tag FROM cache"
        } else {
            "SELECT key, raw, expire_time, access_time, access_count, NULL as tag FROM cache"
        };

        let mut stmt = conn
            .prepare(query)
            .map_err(|e| CacheError::Unknown(format!("Failed to prepare cache query: {}", e)))?;

        let cache_iter = stmt
            .query_map([], |row| self.parse_cache_row(row))
            .map_err(|e| CacheError::Unknown(format!("Failed to query cache: {}", e)))?;

        let mut count = 0;
        for entry_result in cache_iter {
            match entry_result {
                Ok((key, entry)) => {
                    if let Err(e) = self.target_storage.set(&key, entry) {
                        tracing::warn!("Failed to migrate entry {}: {}", key, e);
                    } else {
                        count += 1;
                    }
                }
                Err(e) => {
                    tracing::warn!("Failed to parse cache entry: {}", e);
                }
            }
        }

        Ok(count)
    }

    /// Get columns of a table
    fn get_table_columns(&self, conn: &Connection, table_name: &str) -> CacheResult<Vec<String>> {
        let query = format!("PRAGMA table_info({})", table_name);
        let mut stmt = conn
            .prepare(&query)
            .map_err(|e| CacheError::Unknown(format!("Failed to prepare pragma: {}", e)))?;

        let column_iter = stmt
            .query_map([], |row| {
                row.get::<_, String>(1) // Column name is at index 1
            })
            .map_err(|e| CacheError::Unknown(format!("Failed to query columns: {}", e)))?;

        let mut columns = Vec::new();
        for column in column_iter {
            columns.push(
                column.map_err(|e| CacheError::Unknown(format!("Failed to get column: {}", e)))?,
            );
        }

        Ok(columns)
    }

    /// Parse a cache table row into our format
    fn parse_cache_row(&self, row: &Row) -> rusqlite::Result<(String, CacheEntry)> {
        let key: String = row.get(0)?;
        let raw_data: Vec<u8> = row.get(1)?;
        let expire_time: Option<f64> = row.get(2)?;
        let access_time: Option<f64> = row.get(3)?;
        let access_count: Option<i64> = row.get(4)?;
        let tag: Option<String> = row.get(5)?;

        // Convert timestamps
        let expire_time_u64 = expire_time.map(|t| t as u64);
        let access_time_u64 = access_time.map(|t| t as u64).unwrap_or_else(|| {
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_secs()
        });

        // Create tags vector
        let tags = if let Some(tag_str) = tag {
            if tag_str.is_empty() {
                vec![]
            } else {
                vec![tag_str]
            }
        } else {
            vec![]
        };

        // Create cache entry
        let mut entry = CacheEntry::new(key.clone(), raw_data, tags, expire_time_u64);

        // Update access information
        entry.accessed_at = access_time_u64;
        entry.access_count = access_count.unwrap_or(1) as u64;

        Ok((key, entry))
    }

    /// Migrate settings table (if exists)
    fn migrate_settings_table(&self, conn: &Connection) -> CacheResult<()> {
        let mut stmt = conn
            .prepare("SELECT key, value FROM settings")
            .map_err(|e| CacheError::Unknown(format!("Failed to prepare settings query: {}", e)))?;

        let settings_iter = stmt
            .query_map([], |row| {
                let key: String = row.get(0)?;
                let value: String = row.get(1)?;
                Ok((key, value))
            })
            .map_err(|e| CacheError::Unknown(format!("Failed to query settings: {}", e)))?;

        for (key, value) in settings_iter.flatten() {
            tracing::info!("Found setting: {} = {}", key, value);
            // TODO: Apply relevant settings to our cache configuration
        }

        Ok(())
    }

    /// Create a backup of the original diskcache data
    pub fn create_backup(&self) -> CacheResult<PathBuf> {
        let backup_dir = self.source_dir.join("diskcache_backup");
        std::fs::create_dir_all(&backup_dir).map_err(CacheError::Io)?;

        let cache_db = self.source_dir.join("cache.db");
        let backup_db = backup_dir.join("cache.db");

        std::fs::copy(&cache_db, &backup_db).map_err(CacheError::Io)?;

        tracing::info!("Created backup at: {:?}", backup_dir);
        Ok(backup_dir)
    }
}

/// Statistics from migration process
#[derive(Debug, Default)]
pub struct MigrationStats {
    pub entries_migrated: u64,
    pub entries_failed: u64,
    pub settings_migrated: u64,
    pub success: bool,
    pub backup_created: bool,
}

impl MigrationStats {
    pub fn total_entries(&self) -> u64 {
        self.entries_migrated + self.entries_failed
    }

    pub fn success_rate(&self) -> f64 {
        let total = self.total_entries();
        if total == 0 {
            1.0
        } else {
            self.entries_migrated as f64 / total as f64
        }
    }
}

/// Check if a directory contains python-diskcache data
pub fn detect_diskcache_format(dir: &Path) -> bool {
    let cache_db = dir.join("cache.db");
    cache_db.exists() && cache_db.is_file()
}

/// Auto-migrate if diskcache data is detected
#[allow(dead_code)]
pub fn auto_migrate_if_needed(
    cache_dir: &Path,
    _storage: &mut dyn StorageBackend,
) -> CacheResult<Option<MigrationStats>> {
    if detect_diskcache_format(cache_dir) {
        tracing::info!("Detected python-diskcache data, starting migration...");

        // Create a temporary storage wrapper
        // Note: This is a simplified approach. In practice, you might want to
        // create a proper wrapper or use a different approach.

        tracing::warn!("Auto-migration detected but not implemented in this context");
        tracing::warn!("Please use the migration API explicitly");

        Ok(None)
    } else {
        Ok(None)
    }
}
