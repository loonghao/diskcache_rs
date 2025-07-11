use crate::error::{CacheError, CacheResult};
use crate::serialization::CacheEntry;
use parking_lot::RwLock;
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::Arc;


/// Storage backend trait
pub trait StorageBackend: Send + Sync {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>>;
    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()>;
    fn delete(&self, key: &str) -> CacheResult<bool>;
    fn exists(&self, key: &str) -> CacheResult<bool>;
    fn keys(&self) -> CacheResult<Vec<String>>;
    fn clear(&self) -> CacheResult<()>;
    fn size(&self) -> CacheResult<u64>;
    fn vacuum(&self) -> CacheResult<()>;
}

/// File-based storage backend optimized for network file systems
pub struct FileStorage {
    directory: PathBuf,
    index: Arc<RwLock<HashMap<String, FileEntry>>>,
    use_atomic_writes: bool,
    use_file_locking: bool,
}

#[derive(Debug, Clone)]
struct FileEntry {
    file_path: PathBuf,
    size: u64,
    created_at: u64,
    accessed_at: u64,
}

impl FileStorage {
    pub fn new<P: AsRef<Path>>(
        directory: P,
        use_atomic_writes: bool,
        use_file_locking: bool,
    ) -> CacheResult<Self> {
        let directory = directory.as_ref().to_path_buf();
        
        // Create directory if it doesn't exist
        std::fs::create_dir_all(&directory)
            .map_err(|e| CacheError::Io(e))?;
        
        // Check if this is a network file system
        let is_network_fs = Self::detect_network_filesystem(&directory)?;
        
        if is_network_fs {
            tracing::warn!("Network file system detected. Using optimized settings.");
        }
        
        let mut storage = Self {
            directory,
            index: Arc::new(RwLock::new(HashMap::new())),
            use_atomic_writes: use_atomic_writes && !is_network_fs,
            use_file_locking: use_file_locking && !is_network_fs,
        };
        
        // Load existing index
        storage.rebuild_index()?;
        
        Ok(storage)
    }
    
    fn detect_network_filesystem(path: &Path) -> CacheResult<bool> {
        // Simple heuristic to detect network file systems
        // This is platform-specific and could be improved
        
        #[cfg(unix)]
        {
            use std::ffi::CString;
            use std::mem;
            use std::os::unix::ffi::OsStrExt;
            
            let path_cstr = CString::new(path.as_os_str().as_bytes())
                .map_err(|_| CacheError::NetworkFileSystem("Invalid path".to_string()))?;
            
            unsafe {
                let mut statfs: libc::statfs = mem::zeroed();
                if libc::statfs(path_cstr.as_ptr(), &mut statfs) == 0 {
                    // Check for common network filesystem types
                    match statfs.f_type {
                        0x6969 => return Ok(true), // NFS
                        0x517B => return Ok(true), // SMB
                        0x564C => return Ok(true), // NCP
                        _ => {}
                    }
                }
            }
        }
        
        #[cfg(windows)]
        {
            use std::ffi::OsStr;
            use std::os::windows::ffi::OsStrExt;
            
            let wide_path: Vec<u16> = OsStr::new(path)
                .encode_wide()
                .chain(std::iter::once(0))
                .collect();
            
            unsafe {
                let drive_type = winapi::um::fileapi::GetDriveTypeW(wide_path.as_ptr());
                if drive_type == winapi::um::winbase::DRIVE_REMOTE {
                    return Ok(true);
                }
            }
        }
        
        Ok(false)
    }
    
    fn rebuild_index(&mut self) -> CacheResult<()> {
        let mut index = self.index.write();
        index.clear();
        
        let entries = std::fs::read_dir(&self.directory)
            .map_err(|e| CacheError::Io(e))?;
        
        for entry in entries {
            let entry = entry.map_err(|e| CacheError::Io(e))?;
            let path = entry.path();
            
            if path.is_file() && path.extension().map_or(false, |ext| ext == "cache") {
                if let Some(stem) = path.file_stem() {
                    if let Some(key) = stem.to_str() {
                        let metadata = entry.metadata().map_err(|e| CacheError::Io(e))?;
                        
                        let file_entry = FileEntry {
                            file_path: path.clone(),
                            size: metadata.len(),
                            created_at: metadata
                                .created()
                                .unwrap_or_else(|_| std::time::SystemTime::now())
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap()
                                .as_secs(),
                            accessed_at: metadata
                                .accessed()
                                .unwrap_or_else(|_| std::time::SystemTime::now())
                                .duration_since(std::time::UNIX_EPOCH)
                                .unwrap()
                                .as_secs(),
                        };
                        
                        index.insert(key.to_string(), file_entry);
                    }
                }
            }
        }
        
        Ok(())
    }
    
    fn get_file_path(&self, key: &str) -> PathBuf {
        // Use a hash of the key to avoid filesystem limitations
        let hash = blake3::hash(key.as_bytes());
        let filename = format!("{}.cache", hash.to_hex());
        self.directory.join(filename)
    }
    
    fn write_file_atomic(&self, path: &Path, data: &[u8]) -> CacheResult<()> {
        if self.use_atomic_writes {
            // Write to temporary file first, then rename
            let temp_path = path.with_extension("tmp");
            
            {
                let mut file = OpenOptions::new()
                    .write(true)
                    .create(true)
                    .truncate(true)
                    .open(&temp_path)
                    .map_err(|e| CacheError::Io(e))?;
                
                file.write_all(data).map_err(|e| CacheError::Io(e))?;
                file.sync_all().map_err(|e| CacheError::Io(e))?;
            }
            
            std::fs::rename(&temp_path, path).map_err(|e| CacheError::Io(e))?;
        } else {
            // Direct write for network file systems
            let mut file = OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .open(path)
                .map_err(|e| CacheError::Io(e))?;
            
            file.write_all(data).map_err(|e| CacheError::Io(e))?;
            file.sync_all().map_err(|e| CacheError::Io(e))?;
        }
        
        Ok(())
    }
}

impl StorageBackend for FileStorage {
    fn get(&self, key: &str) -> CacheResult<Option<CacheEntry>> {
        let file_path = self.get_file_path(key);
        
        if !file_path.exists() {
            return Ok(None);
        }
        
        let mut file = File::open(&file_path).map_err(|e| CacheError::Io(e))?;
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer).map_err(|e| CacheError::Io(e))?;
        
        let entry: CacheEntry = bincode::deserialize(&buffer)
            .map_err(|e| CacheError::Deserialization(format!("Storage deserialization error: {:?}", e)))?;
        
        // Check if expired
        if entry.is_expired() {
            self.delete(key)?;
            return Ok(None);
        }
        
        Ok(Some(entry))
    }
    
    fn set(&self, key: &str, entry: CacheEntry) -> CacheResult<()> {
        let file_path = self.get_file_path(key);
        
        let data = bincode::serialize(&entry)
            .map_err(|e| CacheError::Serialization(format!("Storage serialization error: {:?}", e)))?;
        
        self.write_file_atomic(&file_path, &data)?;
        
        // Update index
        let file_entry = FileEntry {
            file_path: file_path.clone(),
            size: data.len() as u64,
            created_at: entry.created_at,
            accessed_at: entry.accessed_at,
        };
        
        self.index.write().insert(key.to_string(), file_entry);
        
        Ok(())
    }
    
    fn delete(&self, key: &str) -> CacheResult<bool> {
        let file_path = self.get_file_path(key);
        
        if file_path.exists() {
            std::fs::remove_file(&file_path).map_err(|e| CacheError::Io(e))?;
            self.index.write().remove(key);
            Ok(true)
        } else {
            Ok(false)
        }
    }
    
    fn exists(&self, key: &str) -> CacheResult<bool> {
        Ok(self.index.read().contains_key(key))
    }
    
    fn keys(&self) -> CacheResult<Vec<String>> {
        Ok(self.index.read().keys().cloned().collect())
    }
    
    fn clear(&self) -> CacheResult<()> {
        let keys: Vec<String> = self.keys()?;
        for key in keys {
            self.delete(&key)?;
        }
        Ok(())
    }
    
    fn size(&self) -> CacheResult<u64> {
        Ok(self.index.read().values().map(|entry| entry.size).sum())
    }
    
    fn vacuum(&self) -> CacheResult<()> {
        // For file storage, vacuum means removing expired entries
        let keys: Vec<String> = self.keys()?;
        for key in keys {
            if let Ok(Some(entry)) = self.get(&key) {
                if entry.is_expired() {
                    self.delete(&key)?;
                }
            }
        }
        Ok(())
    }
}
