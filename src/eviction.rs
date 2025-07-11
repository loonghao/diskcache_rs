
use crate::serialization::CacheEntry;
use std::collections::{BTreeMap, HashMap};
use std::sync::Arc;
use parking_lot::RwLock;

/// Eviction policy trait
pub trait EvictionPolicy: Send + Sync {
    fn on_access(&self, key: &str, entry: &CacheEntry);
    fn on_insert(&self, key: &str, entry: &CacheEntry);
    fn on_remove(&self, key: &str);
    fn select_victims(&self, count: usize) -> Vec<String>;
    fn clear(&self);
}

/// Least Recently Used (LRU) eviction policy
pub struct LruEviction {
    access_order: Arc<RwLock<BTreeMap<u64, String>>>,
    key_to_time: Arc<RwLock<HashMap<String, u64>>>,
    counter: Arc<RwLock<u64>>,
}

impl LruEviction {
    pub fn new() -> Self {
        Self {
            access_order: Arc::new(RwLock::new(BTreeMap::new())),
            key_to_time: Arc::new(RwLock::new(HashMap::new())),
            counter: Arc::new(RwLock::new(0)),
        }
    }
    
    fn get_next_counter(&self) -> u64 {
        let mut counter = self.counter.write();
        *counter += 1;
        *counter
    }
}

impl EvictionPolicy for LruEviction {
    fn on_access(&self, key: &str, _entry: &CacheEntry) {
        let new_time = self.get_next_counter();
        
        // Remove old entry if exists
        if let Some(old_time) = self.key_to_time.read().get(key) {
            self.access_order.write().remove(old_time);
        }
        
        // Insert new entry
        self.access_order.write().insert(new_time, key.to_string());
        self.key_to_time.write().insert(key.to_string(), new_time);
    }
    
    fn on_insert(&self, key: &str, entry: &CacheEntry) {
        self.on_access(key, entry);
    }
    
    fn on_remove(&self, key: &str) {
        if let Some(time) = self.key_to_time.write().remove(key) {
            self.access_order.write().remove(&time);
        }
    }
    
    fn select_victims(&self, count: usize) -> Vec<String> {
        let access_order = self.access_order.read();
        access_order
            .iter()
            .take(count)
            .map(|(_, key)| key.clone())
            .collect()
    }
    
    fn clear(&self) {
        self.access_order.write().clear();
        self.key_to_time.write().clear();
        *self.counter.write() = 0;
    }
}

/// Least Frequently Used (LFU) eviction policy
pub struct LfuEviction {
    frequency_order: Arc<RwLock<BTreeMap<u64, Vec<String>>>>,
    key_to_frequency: Arc<RwLock<HashMap<String, u64>>>,
}

impl LfuEviction {
    pub fn new() -> Self {
        Self {
            frequency_order: Arc::new(RwLock::new(BTreeMap::new())),
            key_to_frequency: Arc::new(RwLock::new(HashMap::new())),
        }
    }
}

impl EvictionPolicy for LfuEviction {
    fn on_access(&self, key: &str, entry: &CacheEntry) {
        let mut frequency_order = self.frequency_order.write();
        let mut key_to_frequency = self.key_to_frequency.write();
        
        // Get current frequency
        let old_freq = key_to_frequency.get(key).copied().unwrap_or(0);
        let new_freq = entry.access_count;
        
        // Remove from old frequency bucket
        if old_freq > 0 {
            if let Some(bucket) = frequency_order.get_mut(&old_freq) {
                bucket.retain(|k| k != key);
                if bucket.is_empty() {
                    frequency_order.remove(&old_freq);
                }
            }
        }
        
        // Add to new frequency bucket
        frequency_order
            .entry(new_freq)
            .or_insert_with(Vec::new)
            .push(key.to_string());
        
        key_to_frequency.insert(key.to_string(), new_freq);
    }
    
    fn on_insert(&self, key: &str, entry: &CacheEntry) {
        self.on_access(key, entry);
    }
    
    fn on_remove(&self, key: &str) {
        let mut frequency_order = self.frequency_order.write();
        let mut key_to_frequency = self.key_to_frequency.write();
        
        if let Some(freq) = key_to_frequency.remove(key) {
            if let Some(bucket) = frequency_order.get_mut(&freq) {
                bucket.retain(|k| k != key);
                if bucket.is_empty() {
                    frequency_order.remove(&freq);
                }
            }
        }
    }
    
    fn select_victims(&self, count: usize) -> Vec<String> {
        let frequency_order = self.frequency_order.read();
        let mut victims = Vec::new();
        
        for (_, keys) in frequency_order.iter() {
            for key in keys {
                if victims.len() >= count {
                    break;
                }
                victims.push(key.clone());
            }
            if victims.len() >= count {
                break;
            }
        }
        
        victims
    }
    
    fn clear(&self) {
        self.frequency_order.write().clear();
        self.key_to_frequency.write().clear();
    }
}

/// Time-based eviction policy (TTL)
pub struct TtlEviction {
    expiry_times: Arc<RwLock<BTreeMap<u64, Vec<String>>>>,
    key_to_expiry: Arc<RwLock<HashMap<String, u64>>>,
}

impl TtlEviction {
    pub fn new() -> Self {
        Self {
            expiry_times: Arc::new(RwLock::new(BTreeMap::new())),
            key_to_expiry: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    pub fn get_expired_keys(&self) -> Vec<String> {
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let expiry_times = self.expiry_times.read();
        let mut expired = Vec::new();
        
        for (&expiry_time, keys) in expiry_times.iter() {
            if expiry_time <= now {
                expired.extend(keys.iter().cloned());
            } else {
                break;
            }
        }
        
        expired
    }
}

impl EvictionPolicy for TtlEviction {
    fn on_access(&self, _key: &str, _entry: &CacheEntry) {
        // TTL doesn't change on access
    }
    
    fn on_insert(&self, key: &str, entry: &CacheEntry) {
        if let Some(expire_time) = entry.expire_time {
            let mut expiry_times = self.expiry_times.write();
            let mut key_to_expiry = self.key_to_expiry.write();
            
            // Remove old expiry if exists
            if let Some(old_expiry) = key_to_expiry.get(key) {
                if let Some(bucket) = expiry_times.get_mut(old_expiry) {
                    bucket.retain(|k| k != key);
                    if bucket.is_empty() {
                        expiry_times.remove(old_expiry);
                    }
                }
            }
            
            // Add new expiry
            expiry_times
                .entry(expire_time)
                .or_insert_with(Vec::new)
                .push(key.to_string());
            
            key_to_expiry.insert(key.to_string(), expire_time);
        }
    }
    
    fn on_remove(&self, key: &str) {
        let mut expiry_times = self.expiry_times.write();
        let mut key_to_expiry = self.key_to_expiry.write();
        
        if let Some(expiry) = key_to_expiry.remove(key) {
            if let Some(bucket) = expiry_times.get_mut(&expiry) {
                bucket.retain(|k| k != key);
                if bucket.is_empty() {
                    expiry_times.remove(&expiry);
                }
            }
        }
    }
    
    fn select_victims(&self, count: usize) -> Vec<String> {
        self.get_expired_keys().into_iter().take(count).collect()
    }
    
    fn clear(&self) {
        self.expiry_times.write().clear();
        self.key_to_expiry.write().clear();
    }
}

/// Combined eviction policy that uses multiple strategies
pub struct CombinedEviction {
    lru: LruEviction,
    lfu: LfuEviction,
    ttl: TtlEviction,
    primary_strategy: EvictionStrategy,
}

#[derive(Debug, Clone, Copy)]
pub enum EvictionStrategy {
    Lru,
    Lfu,
    Ttl,
    LruTtl,
    LfuTtl,
}

impl CombinedEviction {
    pub fn new(strategy: EvictionStrategy) -> Self {
        Self {
            lru: LruEviction::new(),
            lfu: LfuEviction::new(),
            ttl: TtlEviction::new(),
            primary_strategy: strategy,
        }
    }
}

impl EvictionPolicy for CombinedEviction {
    fn on_access(&self, key: &str, entry: &CacheEntry) {
        match self.primary_strategy {
            EvictionStrategy::Lru | EvictionStrategy::LruTtl => {
                self.lru.on_access(key, entry);
            }
            EvictionStrategy::Lfu | EvictionStrategy::LfuTtl => {
                self.lfu.on_access(key, entry);
            }
            EvictionStrategy::Ttl => {}
        }
        
        if matches!(
            self.primary_strategy,
            EvictionStrategy::LruTtl | EvictionStrategy::LfuTtl | EvictionStrategy::Ttl
        ) {
            self.ttl.on_access(key, entry);
        }
    }
    
    fn on_insert(&self, key: &str, entry: &CacheEntry) {
        self.on_access(key, entry);
    }
    
    fn on_remove(&self, key: &str) {
        self.lru.on_remove(key);
        self.lfu.on_remove(key);
        self.ttl.on_remove(key);
    }
    
    fn select_victims(&self, count: usize) -> Vec<String> {
        // First, get expired keys
        let mut victims = self.ttl.get_expired_keys();
        
        if victims.len() >= count {
            return victims.into_iter().take(count).collect();
        }
        
        // If we need more victims, use the primary strategy
        let remaining = count - victims.len();
        let additional_victims = match self.primary_strategy {
            EvictionStrategy::Lru | EvictionStrategy::LruTtl => {
                self.lru.select_victims(remaining)
            }
            EvictionStrategy::Lfu | EvictionStrategy::LfuTtl => {
                self.lfu.select_victims(remaining)
            }
            EvictionStrategy::Ttl => Vec::new(),
        };
        
        victims.extend(additional_victims);
        victims.into_iter().take(count).collect()
    }
    
    fn clear(&self) {
        self.lru.clear();
        self.lfu.clear();
        self.ttl.clear();
    }
}
