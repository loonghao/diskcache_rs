use crate::serialization::CacheEntry;
use parking_lot::RwLock;
use std::collections::{BTreeMap, HashMap};
use std::sync::Arc;

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
    #[allow(dead_code)]
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
    #[allow(dead_code)]
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

        // Remove from old frequency bucket. This must run unconditionally: a
        // key inserted with access_count == 0 lives in bucket 0, so guarding on
        // `old_freq > 0` would leave a stale copy behind and make
        // `select_victims` return the same key twice. For a brand new key the
        // lookup simply misses and this is a no-op.
        if let Some(bucket) = frequency_order.get_mut(&old_freq) {
            bucket.retain(|k| k != key);
            if bucket.is_empty() {
                frequency_order.remove(&old_freq);
            }
        }

        // Add to new frequency bucket
        frequency_order
            .entry(new_freq)
            .or_default()
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

        for keys in frequency_order.values() {
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
    #[allow(dead_code)]
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
                .or_default()
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

/// Least Recently Stored eviction policy - removes oldest stored items
/// This policy does NOT track access times, only store times (like diskcache default)
pub struct LeastRecentlyStoredEviction {
    store_order: Arc<RwLock<BTreeMap<u64, String>>>,
    key_to_time: Arc<RwLock<HashMap<String, u64>>>,
    counter: Arc<RwLock<u64>>,
}

impl LeastRecentlyStoredEviction {
    #[allow(dead_code)]
    pub fn new() -> Self {
        Self {
            store_order: Arc::new(RwLock::new(BTreeMap::new())),
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

impl EvictionPolicy for LeastRecentlyStoredEviction {
    fn on_access(&self, _key: &str, _entry: &CacheEntry) {
        // LeastRecentlyStored doesn't track access times - this is the key optimization!
    }

    fn on_insert(&self, key: &str, _entry: &CacheEntry) {
        let new_time = self.get_next_counter();

        // Remove old entry if exists
        if let Some(old_time) = self.key_to_time.read().get(key) {
            self.store_order.write().remove(old_time);
        }

        // Insert new entry with store time
        self.store_order.write().insert(new_time, key.to_string());
        self.key_to_time.write().insert(key.to_string(), new_time);
    }

    fn on_remove(&self, key: &str) {
        if let Some(time) = self.key_to_time.write().remove(key) {
            self.store_order.write().remove(&time);
        }
    }

    fn select_victims(&self, count: usize) -> Vec<String> {
        let store_order = self.store_order.read();
        store_order.values().take(count).cloned().collect()
    }

    fn clear(&self) {
        self.store_order.write().clear();
        self.key_to_time.write().clear();
    }
}

/// Combined eviction policy that uses multiple strategies
pub struct CombinedEviction {
    lru: LruEviction,
    lfu: LfuEviction,
    ttl: TtlEviction,
    least_recently_stored: LeastRecentlyStoredEviction,
    primary_strategy: EvictionStrategy,
}

#[derive(Debug, Clone, Copy)]
#[allow(dead_code)]
pub enum EvictionStrategy {
    /// No eviction policy - items are never automatically removed
    None,
    /// Least Recently Used - tracks access time, updates on every get
    Lru,
    /// Least Frequently Used - tracks access count, updates on every get
    Lfu,
    /// Time To Live - only removes expired items, no access tracking
    Ttl,
    /// Least Recently Stored - removes oldest stored items, no access tracking (like diskcache default)
    LeastRecentlyStored,
    /// Combined LRU + TTL
    LruTtl,
    /// Combined LFU + TTL
    LfuTtl,
}

impl CombinedEviction {
    #[allow(dead_code)]
    pub fn new(strategy: EvictionStrategy) -> Self {
        Self {
            lru: LruEviction::new(),
            lfu: LfuEviction::new(),
            ttl: TtlEviction::new(),
            least_recently_stored: LeastRecentlyStoredEviction::new(),
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
            EvictionStrategy::Ttl
            | EvictionStrategy::LeastRecentlyStored
            | EvictionStrategy::None => {
                // These strategies don't track access times - key performance optimization!
            }
        }

        if matches!(
            self.primary_strategy,
            EvictionStrategy::LruTtl | EvictionStrategy::LfuTtl | EvictionStrategy::Ttl
        ) {
            self.ttl.on_access(key, entry);
        }
    }

    fn on_insert(&self, key: &str, entry: &CacheEntry) {
        // For insert, we need to track in the appropriate strategy
        match self.primary_strategy {
            EvictionStrategy::Lru | EvictionStrategy::LruTtl => {
                self.lru.on_insert(key, entry);
            }
            EvictionStrategy::Lfu | EvictionStrategy::LfuTtl => {
                self.lfu.on_insert(key, entry);
            }
            EvictionStrategy::LeastRecentlyStored => {
                self.least_recently_stored.on_insert(key, entry);
            }
            EvictionStrategy::Ttl | EvictionStrategy::None => {}
        }

        if matches!(
            self.primary_strategy,
            EvictionStrategy::LruTtl | EvictionStrategy::LfuTtl | EvictionStrategy::Ttl
        ) {
            self.ttl.on_insert(key, entry);
        }
    }

    fn on_remove(&self, key: &str) {
        self.lru.on_remove(key);
        self.lfu.on_remove(key);
        self.ttl.on_remove(key);
        self.least_recently_stored.on_remove(key);
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
            EvictionStrategy::Lru | EvictionStrategy::LruTtl => self.lru.select_victims(remaining),
            EvictionStrategy::Lfu | EvictionStrategy::LfuTtl => self.lfu.select_victims(remaining),
            EvictionStrategy::LeastRecentlyStored => {
                self.least_recently_stored.select_victims(remaining)
            }
            EvictionStrategy::Ttl | EvictionStrategy::None => Vec::new(),
        };

        victims.extend(additional_victims);
        victims.into_iter().take(count).collect()
    }

    fn clear(&self) {
        self.lru.clear();
        self.lfu.clear();
        self.ttl.clear();
        self.least_recently_stored.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build a cache entry carrying an explicit access count.
    fn entry_with_access_count(key: &str, access_count: u64) -> CacheEntry {
        let mut entry = CacheEntry::new_inline(key.to_string(), b"value".to_vec(), vec![], None);
        entry.access_count = access_count;
        entry
    }

    /// A key must never appear twice in `select_victims`, even after it is
    /// promoted out of the frequency-0 bucket.
    #[test]
    fn select_victims_has_no_duplicate_keys_after_frequency_zero_promotion() {
        let policy = LfuEviction::new();

        // Insert lands the key in the frequency-0 bucket (access_count == 0).
        policy.on_insert("a", &entry_with_access_count("a", 0));
        // A later access promotes it out of bucket 0 into bucket 1.
        policy.on_access("a", &entry_with_access_count("a", 1));

        let victims = policy.select_victims(10);

        let unique: std::collections::HashSet<_> = victims.iter().collect();
        assert_eq!(
            unique.len(),
            victims.len(),
            "same key selected more than once: {victims:?}"
        );
        assert_eq!(victims, vec!["a".to_string()]);
    }

    /// Victims are ordered by ascending frequency, with the least frequently
    /// used keys evicted first.
    #[test]
    fn select_victims_orders_by_ascending_frequency() {
        let policy = LfuEviction::new();

        policy.on_insert("low", &entry_with_access_count("low", 0));
        policy.on_insert("mid", &entry_with_access_count("mid", 3));
        policy.on_insert("high", &entry_with_access_count("high", 7));

        let victims = policy.select_victims(10);

        assert_eq!(
            victims,
            vec!["low".to_string(), "mid".to_string(), "high".to_string()],
            "expected victims ordered by ascending frequency"
        );
    }

    /// Promotion must move a key between buckets, not copy it, so the number of
    /// selectable victims still matches the number of tracked keys.
    #[test]
    fn select_victims_count_after_promotion_matches_tracked_keys() {
        let policy = LfuEviction::new();

        for key in ["a", "b", "c"] {
            policy.on_insert(key, &entry_with_access_count(key, 0));
        }
        // Promote "a" and "b" out of the frequency-0 bucket.
        policy.on_access("a", &entry_with_access_count("a", 1));
        policy.on_access("b", &entry_with_access_count("b", 2));

        // Three keys are tracked, so three distinct victims must be available.
        let victims = policy.select_victims(3);
        assert_eq!(
            victims.len(),
            3,
            "expected 3 distinct victims, got {victims:?}"
        );

        let unique: std::collections::HashSet<_> = victims.iter().collect();
        assert_eq!(unique.len(), 3, "duplicate victims returned: {victims:?}");
    }

    /// `select_victims` never returns more keys than requested.
    #[test]
    fn select_victims_respects_requested_count() {
        let policy = LfuEviction::new();

        for key in ["a", "b", "c", "d"] {
            policy.on_insert(key, &entry_with_access_count(key, 0));
        }

        assert_eq!(policy.select_victims(0).len(), 0);
        assert_eq!(policy.select_victims(2).len(), 2);
        assert_eq!(policy.select_victims(10).len(), 4);
    }

    /// A repeated access at an unchanged frequency must not duplicate the key.
    #[test]
    fn repeated_access_at_same_frequency_does_not_duplicate_key() {
        let policy = LfuEviction::new();

        policy.on_insert("a", &entry_with_access_count("a", 2));
        policy.on_access("a", &entry_with_access_count("a", 2));
        policy.on_access("a", &entry_with_access_count("a", 2));

        let victims = policy.select_victims(10);
        assert_eq!(
            victims,
            vec!["a".to_string()],
            "repeated access must not duplicate the key in its bucket"
        );
    }
}
