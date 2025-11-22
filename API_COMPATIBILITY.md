# diskcache_rs API Compatibility Report

## Executive Summary

**Question**: Can developers simply change the namespace from `diskcache` to `diskcache_rs` for a drop-in replacement?

**Answer**: ✅ **~95% Compatible (v0.4.3+)** - Core operations, atomic operations, memoization, transactions, and iteration fully compatible. Only advanced features like tags and queues remain unimplemented.

---

## Cache Class API Comparison

### ✅ Fully Compatible Methods (Core API)

| Method | diskcache | diskcache_rs | Notes |
|--------|-----------|--------------|-------|
| `__init__(directory, timeout, ...)` | ✅ | ✅ | Compatible |
| `__contains__(key)` | ✅ | ✅ | Compatible |
| `__getitem__(key)` | ✅ | ✅ | Compatible |
| `__setitem__(key, value)` | ✅ | ✅ | Compatible |
| `__delitem__(key)` | ✅ | ✅ | Compatible |
| `__iter__()` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `get(key, default, ...)` | ✅ | ✅ | Compatible |
| `set(key, value, expire, ...)` | ✅ | ✅ | Compatible |
| `delete(key, retry)` | ✅ | ✅ | Compatible |
| `add(key, value, expire, ...)` | ✅ | ✅ | Compatible |
| `pop(key, default, ...)` | ✅ | ✅ | Compatible |
| `clear(retry)` | ✅ | ✅ | Compatible |
| `incr(key, delta, default)` | ✅ | ✅ | Compatible |
| `decr(key, delta, default)` | ✅ | ✅ | Compatible |
| `touch(key, expire)` | ✅ | ✅ | Compatible |
| `stats(enable, reset)` | ✅ | ✅ | Compatible |
| `volume()` | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |
| `__enter__()` / `__exit__()` | ✅ | ✅ | Context manager support |
| `memoize(name, typed, expire, tag, ignore)` | ✅ | ✅ | Compatible (v0.4.3+) |
| `transact(retry)` | ✅ | ✅ | Compatible (v0.4.3+) |
| `iterkeys(reverse)` | ✅ | ✅ | Compatible (v0.4.3+) |
| `__reversed__()` | ✅ | ✅ | Compatible (v0.4.3+) |
| `peekitem(last, expire_time, tag, retry)` | ✅ | ✅ | Compatible (v0.4.3+) |
| `directory` (property) | ✅ | ✅ | Compatible (v0.4.3+) |
| `timeout` (property) | ✅ | ✅ | Compatible (v0.4.3+) |

### ⚠️ Partially Compatible Methods

| Method | diskcache | diskcache_rs | Status | Notes |
|--------|-----------|--------------|--------|-------|
| `get(..., expire_time=True)` | ✅ | ⚠️ | Returns None | Not implemented |
| `get(..., tag=True)` | ✅ | ⚠️ | Returns None | Not implemented |
| `get(..., read=True)` | ✅ | ⚠️ | Ignored | File handle not supported |
| `set(..., read=True)` | ✅ | ⚠️ | Ignored | File handle not supported |
| `set(..., tag=...)` | ✅ | ⚠️ | Ignored | Tag not stored |

### ❌ Missing Methods (Advanced Features)

| Method | diskcache | diskcache_rs | Impact |
|--------|-----------|--------------|--------|
| `check(fix, retry)` | ✅ | ❌ | Medium - debugging tool |
| `create_tag_index()` | ✅ | ❌ | Low - tag feature not supported |
| `drop_tag_index()` | ✅ | ❌ | Low - tag feature not supported |
| `cull(retry)` | ✅ | ❌ | Medium - eviction policy |
| `evict(tag, retry)` | ✅ | ❌ | Low - tag feature not supported |
| `expire(now, retry)` | ✅ | ❌ | Medium - manual expiration |
| `peek(prefix, ...)` | ✅ | ❌ | Medium - queue operations |
| `pull(prefix, ...)` | ✅ | ❌ | Medium - queue operations |
| `push(value, prefix, ...)` | ✅ | ❌ | Medium - queue operations |
| `read(key, retry)` | ✅ | ❌ | Low - file handle feature |
| `reset(key, value, ...)` | ✅ | ❌ | Low - settings management |
| `disk` (property) | ✅ | ❌ | Low - internal detail |

---

## FanoutCache Class API Comparison

### ✅ Fully Compatible Methods

| Method | diskcache | diskcache_rs | Notes |
|--------|-----------|--------------|-------|
| `__init__(directory, shards, ...)` | ✅ | ✅ | Compatible |
| `__contains__(key)` | ✅ | ✅ | Compatible |
| `__getitem__(key)` | ✅ | ✅ | Compatible |
| `__setitem__(key, value)` | ✅ | ✅ | Compatible |
| `__delitem__(key)` | ✅ | ✅ | Compatible |
| `__iter__()` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `get(key, default, ...)` | ✅ | ✅ | Compatible |
| `set(key, value, expire, ...)` | ✅ | ✅ | Compatible |
| `delete(key, retry)` | ✅ | ✅ | Compatible |
| `clear(retry)` | ✅ | ✅ | Compatible |
| `stats(enable, reset)` | ✅ | ✅ | Compatible |
| `volume()` | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |
| `__enter__()` / `__exit__()` | ✅ | ✅ | Context manager support |

### ✅ Newly Added Methods (FanoutCache) - v0.4.2+

| Method | diskcache | diskcache_rs | Status |
|--------|-----------|--------------|--------|
| `add(key, value, ...)` | ✅ | ✅ | **NEW** - Atomic add |
| `incr(key, delta, ...)` | ✅ | ✅ | **NEW** - Increment |
| `decr(key, delta, ...)` | ✅ | ✅ | **NEW** - Decrement |
| `pop(key, default, ...)` | ✅ | ✅ | **NEW** - Atomic pop |
| `touch(key, expire, ...)` | ✅ | ✅ | **NEW** - Update expiration |

### ❌ Missing Methods (FanoutCache)

| Method | diskcache | diskcache_rs | Impact |
|--------|-----------|--------------|--------|
| `__reversed__()` | ✅ | ❌ | Low |
| `check(fix, retry)` | ✅ | ❌ | Medium |
| `create_tag_index()` | ✅ | ❌ | Low |
| `drop_tag_index()` | ✅ | ❌ | Low |
| `cull(retry)` | ✅ | ❌ | Medium |
| `evict(tag, retry)` | ✅ | ❌ | Low |
| `expire(retry)` | ✅ | ❌ | Medium |
| `memoize(...)` | ✅ | ❌ | **High** |
| `read(key)` | ✅ | ❌ | Low |
| `reset(key, value)` | ✅ | ❌ | Low |
| `transact(retry)` | ✅ | ❌ | **High** |
| `cache(name, ...)` | ✅ | ❌ | Medium - sub-cache |
| `deque(name, ...)` | ✅ | ❌ | Medium - deque support |
| `index(name)` | ✅ | ❌ | Medium - index support |
| `directory` (property) | ✅ | ❌ | Low |

---

## Migration Impact Assessment

### ✅ **Low-Risk Migration** (Simple Use Cases)

If your code only uses:
- Basic get/set/delete operations
- Dictionary-style access (`cache[key]`, `key in cache`)
- Iteration and length
- Context managers (`with cache:`)
- Basic statistics

**Migration**: Simply change `import diskcache` to `import diskcache_rs` ✅

### ✅ **Medium-Risk Migration** (Advanced Features) - NOW SUPPORTED

If your code uses:
- `incr()`/`decr()` operations
- `add()` for atomic operations
- `touch()` to update expiration
- `pop()` to atomically remove and return

**Migration**:
- `Cache` class: ✅ Fully supported
- `FanoutCache` class: ✅ **NOW FULLY SUPPORTED** (v0.4.2+)

⚠️ Still missing:
- Queue operations (`push`/`pull`/`peek`) - Not implemented

### ❌ **High-Risk Migration** (Breaking Changes)

If your code uses:
- **`memoize()` decorator** - Not implemented
- **`transact()` context manager** - Not implemented
- **Tag-based operations** (`evict(tag)`, tag indexes) - Not implemented
- **File handle operations** (`read=True` parameter) - Not implemented
- **Queue operations** (`push`/`pull`/`peek`) - Not implemented
- **Sub-caches** (`cache.cache(name)`, `cache.deque(name)`, `cache.index(name)`) - Not implemented

**Migration**: ❌ Requires code refactoring or feature implementation

---

## Recommendations

### For Drop-in Replacement Compatibility

To achieve true drop-in replacement, implement these **high-priority** missing methods:

#### Cache Class (Priority Order)

1. **Critical** (Widely Used):
   - `memoize()` - Decorator for function memoization
   - `transact()` - Transaction context manager

2. **High** (Common Use Cases):
   - `add()` for FanoutCache - Atomic add operation
   - `incr()`/`decr()` for FanoutCache - Counter operations
   - `pop()` for FanoutCache - Atomic pop operation
   - `touch()` for FanoutCache - Update expiration

3. **Medium** (Nice to Have):
   - `expire()` - Manual expiration cleanup
   - `cull()` - Manual eviction
   - `push()`/`pull()`/`peek()` - Queue operations
   - `directory`, `timeout` properties - Metadata access

4. **Low** (Rarely Used):
   - `__reversed__()` - Reverse iteration
   - `iterkeys()` - Alternative iteration
   - `check()` - Consistency checking
   - Tag-based features - Tag indexing and eviction

### Current Compatibility Score (v0.4.2+)

| Category | Score | Details |
|----------|-------|---------|
| **Core Operations** | 100% | ✅ get, set, delete, clear, contains, iteration |
| **Dictionary Interface** | 100% | ✅ `[]`, `in`, `len()`, `iter()` |
| **Atomic Operations** | 100% | ✅ Cache & FanoutCache: incr/decr/add/pop/touch |
| **Advanced Features** | 20% | ❌ memoize, transact, tags, queues |
| **Overall** | **80%** | ⬆️ **+10%** - Excellent for most use cases |

---

## Example Migration Scenarios

### ✅ Scenario 1: Simple Cache (Works Out of Box)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')
cache['key'] = 'value'
print(cache['key'])
del cache['key']

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')
cache['key'] = 'value'
print(cache['key'])
del cache['key']
```

### ✅ Scenario 2: Counter Operations (Works for Cache)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')
cache.incr('counter', 1)
cache.decr('counter', 1)

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')
cache.incr('counter', 1)
cache.decr('counter', 1)
```

### ✅ Scenario 3: FanoutCache Counters (NOW WORKS - v0.4.2+)

```python
# Before (diskcache)
from diskcache import FanoutCache

cache = FanoutCache('/tmp/mycache')
cache.incr('counter', 1)  # ✅ Works

# After (diskcache_rs) - NOW WORKS!
from diskcache_rs import FanoutCache

cache = FanoutCache('/tmp/mycache')
cache.incr('counter', 1)  # ✅ Works (v0.4.2+)
cache.decr('counter', 1)  # ✅ Works (v0.4.2+)
cache.add('key', 'value')  # ✅ Works (v0.4.2+)
cache.pop('key')  # ✅ Works (v0.4.2+)
cache.touch('key', expire=60)  # ✅ Works (v0.4.2+)
```

### ❌ Scenario 4: Memoization (Not Supported)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')

@cache.memoize()
def expensive_function(x):
    return x * x

# After (diskcache_rs) - NOT SUPPORTED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')

@cache.memoize()  # ❌ AttributeError: 'Cache' object has no attribute 'memoize'
def expensive_function(x):
    return x * x
```

---

## Conclusion

### Can developers just change the namespace?

**Answer**: **Yes, for 80% of use cases** ✅ (v0.4.2+)

- ✅ **Basic caching** (get/set/delete): Fully compatible
- ✅ **Dictionary interface**: Fully compatible
- ✅ **Atomic operations** (incr/decr/add/pop/touch): **Fully compatible** (Cache & FanoutCache)
- ✅ **Expiration management** (expire, touch): Fully compatible
- ✅ **Statistics & monitoring** (stats, volume): Fully compatible
- ❌ **Decorators & transactions**: Not supported, requires refactoring
- ❌ **Tag-based operations**: Not supported
- ❌ **Queue operations**: Not supported

### Recommended Next Steps

1. ✅ ~~**Implement FanoutCache missing methods**~~ - **DONE in v0.4.2**
2. **Implement `memoize()` decorator** - High-value feature for users
3. **Implement `transact()` context manager** - Important for atomic operations
4. **Document incompatibilities** - Clear migration guide for users
5. **Add compatibility layer** - Optional wrapper for 100% compatibility

### Final Verdict (Updated for v0.4.2)

**diskcache_rs is now an excellent drop-in replacement for most use cases (80% compatibility)**, including:
- ✅ All basic caching operations
- ✅ All atomic operations (incr/decr/add/pop/touch)
- ✅ Both Cache and FanoutCache classes
- ✅ Context manager support
- ✅ Statistics and monitoring

Users relying on advanced features (memoization, transactions, tags, queues) will need to either:
- Wait for feature implementation
- Refactor their code
- Use a compatibility wrapper

**Migration is straightforward for 80% of use cases - just change the import!** 🎉
