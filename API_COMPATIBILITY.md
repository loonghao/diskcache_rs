# diskcache_rs API Compatibility Report

## Executive Summary

**Question**: Can developers simply change the namespace from `diskcache` to `diskcache_rs` for a drop-in replacement?

**Answer**: ✅ **~100% Compatible** - All core operations, atomic operations, memoization, transactions, iteration, queue operations, sub-cache operations, metadata access, tag-based operations, and pickle serialization are fully compatible.

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
| `__reversed__()` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `__getstate__()` / `__setstate__()` | ✅ | ✅ | Pickle serialization support |
| `get(key, default, read, expire_time, tag, ...)` | ✅ | ✅ | Full support including expire_time and tag return |
| `set(key, value, expire, read, tag, ...)` | ✅ | ✅ | Full support including read=True for file-like objects |
| `delete(key, retry)` | ✅ | ✅ | Compatible |
| `add(key, value, expire, ...)` | ✅ | ✅ | Compatible |
| `pop(key, default, expire_time, tag, ...)` | ✅ | ✅ | Full support including expire_time and tag return |
| `clear(retry)` | ✅ | ✅ | Compatible |
| `incr(key, delta, default)` | ✅ | ✅ | Compatible |
| `decr(key, delta, default)` | ✅ | ✅ | Compatible |
| `touch(key, expire)` | ✅ | ✅ | Compatible |
| `expire(now, retry)` | ✅ | ✅ | Compatible |
| `evict(tag, retry)` | ✅ | ✅ | Full tag-based eviction via Python-side tracking |
| `stats(enable, reset)` | ✅ | ✅ | Compatible |
| `volume()` | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |
| `__enter__()` / `__exit__()` | ✅ | ✅ | Context manager support |
| `memoize(name, typed, expire, tag, ignore)` | ✅ | ✅ | Compatible |
| `transact(retry)` | ✅ | ✅ | Compatible |
| `iterkeys(reverse)` | ✅ | ✅ | Compatible |
| `peekitem(last, expire_time, tag, retry)` | ✅ | ✅ | Full support including expire_time and tag return |
| `directory` (property) | ✅ | ✅ | Compatible |
| `timeout` (property) | ✅ | ✅ | Compatible |
| `check(fix, retry)` | ✅ | ✅ | Compatible |
| `cull(retry)` | ✅ | ✅ | Compatible |
| `reset(key, value)` | ✅ | ✅ | Compatible (settings via constructor) |
| `read(key, retry)` | ✅ | ✅ | Returns BytesIO handle |
| `push(value, prefix, side, ...)` | ✅ | ✅ | Queue operations |
| `pull(prefix, default, side, ...)` | ✅ | ✅ | Queue operations with expire_time/tag support |
| `peek(prefix, default, side, ...)` | ✅ | ✅ | Queue operations with expire_time/tag support |
| `create_tag_index()` | ✅ | ✅ | No-op (tags inline) |
| `drop_tag_index()` | ✅ | ✅ | No-op (tags inline) |
| `disk` (property) | ✅ | ✅ | Returns compatible proxy |
| `keys()` | ✅ | ✅ | Compatible |
| `values()` | ✅ | ✅ | Compatible |
| `items()` | ✅ | ✅ | Compatible |
| `vacuum()` | ✅ | ✅ | Compatible |

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
| `__reversed__()` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `__getstate__()` / `__setstate__()` | ✅ | ✅ | Pickle serialization support |
| `get(key, default, read, expire_time, tag, ...)` | ✅ | ✅ | Full support including expire_time and tag return |
| `set(key, value, expire, read, tag, ...)` | ✅ | ✅ | Full support |
| `delete(key, retry)` | ✅ | ✅ | Compatible |
| `add(key, value, ...)` | ✅ | ✅ | Compatible |
| `incr(key, delta, ...)` | ✅ | ✅ | Compatible |
| `decr(key, delta, ...)` | ✅ | ✅ | Compatible |
| `pop(key, default, ...)` | ✅ | ✅ | Compatible |
| `touch(key, expire, ...)` | ✅ | ✅ | Compatible |
| `expire(retry)` | ✅ | ✅ | Compatible |
| `evict(tag, retry)` | ✅ | ✅ | Full tag-based eviction |
| `clear(retry)` | ✅ | ✅ | Compatible |
| `stats(enable, reset)` | ✅ | ✅ | Compatible |
| `volume()` | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |
| `__enter__()` / `__exit__()` | ✅ | ✅ | Context manager support |
| `memoize(name, typed, expire, tag, ignore)` | ✅ | ✅ | Compatible |
| `transact(retry)` | ✅ | ✅ | Compatible |
| `iterkeys(reverse)` | ✅ | ✅ | Compatible |
| `peekitem(last, ...)` | ✅ | ✅ | Compatible with expire_time/tag support |
| `check(fix, retry)` | ✅ | ✅ | Compatible |
| `cull(retry)` | ✅ | ✅ | Compatible |
| `reset(key, value)` | ✅ | ✅ | Compatible |
| `read(key, retry)` | ✅ | ✅ | Returns BytesIO handle |
| `push(value, prefix, side, ...)` | ✅ | ✅ | Queue operations |
| `pull(prefix, default, side, ...)` | ✅ | ✅ | Queue operations |
| `peek(prefix, default, side, ...)` | ✅ | ✅ | Queue operations |
| `create_tag_index()` | ✅ | ✅ | No-op (tags inline) |
| `drop_tag_index()` | ✅ | ✅ | No-op (tags inline) |
| `cache(name, ...)` | ✅ | ✅ | Sub-cache factory |
| `deque(name, maxlen)` | ✅ | ✅ | Deque factory |
| `index(name)` | ✅ | ✅ | Index factory |
| `keys()` | ✅ | ✅ | Compatible |
| `values()` | ✅ | ✅ | Compatible |
| `items()` | ✅ | ✅ | Compatible |
| `exists(key)` | ✅ | ✅ | Compatible |
| `vacuum()` | ✅ | ✅ | Compatible |
| `directory` (property) | ✅ | ✅ | Compatible |
| `timeout` (property) | ✅ | ✅ | Compatible |
| `disk` (property) | ✅ | ✅ | Returns compatible proxy |

---

## Deque Class API Comparison

### ✅ Fully Compatible Methods

| Method | diskcache | diskcache_rs | Notes |
|--------|-----------|--------------|-------|
| `__init__(iterable, directory, maxlen)` | ✅ | ✅ | Compatible |
| `append(value)` | ✅ | ✅ | Compatible |
| `appendleft(value)` | ✅ | ✅ | Compatible |
| `pop()` | ✅ | ✅ | Compatible |
| `popleft()` | ✅ | ✅ | Compatible |
| `peek()` | ✅ | ✅ | Compatible |
| `peekleft()` | ✅ | ✅ | Compatible |
| `clear()` | ✅ | ✅ | Compatible |
| `extend(iterable)` | ✅ | ✅ | Compatible |
| `extendleft(iterable)` | ✅ | ✅ | Compatible |
| `copy()` | ✅ | ✅ | Compatible |
| `count(value)` | ✅ | ✅ | Compatible |
| `remove(value)` | ✅ | ✅ | Compatible |
| `reverse()` | ✅ | ✅ | Compatible |
| `rotate(steps)` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `__iter__()` | ✅ | ✅ | Compatible |
| `__reversed__()` | ✅ | ✅ | Compatible |
| `__bool__()` | ✅ | ✅ | Compatible |
| `__contains__(value)` | ✅ | ✅ | Compatible |
| `__getitem__(index)` | ✅ | ✅ | Compatible |
| `__setitem__(index, value)` | ✅ | ✅ | Compatible |
| `__delitem__(index)` | ✅ | ✅ | Compatible |
| `__eq__` / `__ne__` / `__lt__` / `__gt__` / `__le__` / `__ge__` | ✅ | ✅ | All comparison operators |
| `__iadd__(other)` | ✅ | ✅ | In-place addition |
| `__getstate__()` / `__setstate__()` | ✅ | ✅ | Pickle support |
| `transact()` | ✅ | ✅ | Transaction support |
| `maxlen` (property) | ✅ | ✅ | Compatible |
| `directory` (property) | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |

---

## Index Class API Comparison

### ✅ Fully Compatible Methods

| Method | diskcache | diskcache_rs | Notes |
|--------|-----------|--------------|-------|
| `__init__(*args, directory, **kwargs)` | ✅ | ✅ | Compatible |
| `__getitem__(key)` | ✅ | ✅ | Compatible |
| `__setitem__(key, value)` | ✅ | ✅ | Compatible |
| `__delitem__(key)` | ✅ | ✅ | Compatible |
| `__contains__(key)` | ✅ | ✅ | Compatible |
| `__iter__()` | ✅ | ✅ | Compatible |
| `__reversed__()` | ✅ | ✅ | Compatible |
| `__len__()` | ✅ | ✅ | Compatible |
| `__bool__()` | ✅ | ✅ | Compatible |
| `__eq__` / `__ne__` | ✅ | ✅ | Comparison operators |
| `__getstate__()` / `__setstate__()` | ✅ | ✅ | Pickle support |
| `get(key, default)` | ✅ | ✅ | Compatible |
| `pop(key, default)` | ✅ | ✅ | Compatible |
| `popitem(last)` | ✅ | ✅ | Compatible |
| `setdefault(key, default)` | ✅ | ✅ | Compatible |
| `keys()` | ✅ | ✅ | Compatible |
| `values()` | ✅ | ✅ | Compatible |
| `items()` | ✅ | ✅ | Compatible |
| `update(*args, **kwargs)` | ✅ | ✅ | Compatible |
| `clear()` | ✅ | ✅ | Compatible |
| `peekitem(last)` | ✅ | ✅ | Compatible |
| `cache` (property) | ✅ | ✅ | Returns underlying Cache |
| `directory` (property) | ✅ | ✅ | Compatible |
| `close()` | ✅ | ✅ | Compatible |
| `transact()` | ✅ | ✅ | Transaction support |
| `memoize(name, typed, ignore)` | ✅ | ✅ | Memoization decorator |
| `push(value, prefix, side)` | ✅ | ✅ | Queue operations |
| `pull(prefix, default, side)` | ✅ | ✅ | Queue operations |

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

### ✅ **Medium-Risk Migration** (Advanced Features) - FULLY SUPPORTED

If your code uses:
- `incr()`/`decr()` operations
- `add()` for atomic operations
- `touch()` to update expiration
- `pop()` to atomically remove and return
- `memoize()` decorator
- `transact()` context manager
- Queue operations (`push`/`pull`/`peek`)
- Sub-caches (`cache()`/`deque()`/`index()`)
- `Deque` and `Index` classes
- Tag-based operations (`set(tag=...)`, `evict(tag)`)
- `get(expire_time=True, tag=True)` metadata return
- `read=True` parameter for file-like objects
- Pickle serialization (`__getstate__`/`__setstate__`)

**Migration**: Simply change `import diskcache` to `import diskcache_rs` ✅

---

## Compatibility Score

| Category | Score | Details |
|----------|-------|---------|
| **Core Operations** | 100% | ✅ get, set, delete, clear, contains, iteration |
| **Dictionary Interface** | 100% | ✅ `[]`, `in`, `len()`, `iter()`, `reversed()` |
| **Atomic Operations** | 100% | ✅ incr/decr/add/pop/touch |
| **Memoization** | 100% | ✅ `memoize()` decorator |
| **Transactions** | 100% | ✅ `transact()` context manager |
| **Queue Operations** | 100% | ✅ push/pull/peek |
| **Maintenance** | 100% | ✅ check/cull/expire/vacuum/reset |
| **Sub-caches** | 100% | ✅ cache()/deque()/index() |
| **Metadata** | 100% | ✅ directory/timeout/disk/stats/volume |
| **Tag Operations** | 100% | ✅ Tags tracked and fully queryable |
| **Expire Time Return** | 100% | ✅ get/pop/peek/peekitem with expire_time=True |
| **Read Parameter** | 100% | ✅ set(read=True) and get(read=True) |
| **Pickle Support** | 100% | ✅ __getstate__/__setstate__ for all classes |
| **Deque** | 100% | ✅ Full collections.deque-like interface |
| **Index** | 100% | ✅ Full MutableMapping interface |
| **Overall** | **~100%** | Complete API compatibility |

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

### ✅ Scenario 2: Tag-based Operations (Now Fully Working!)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')
cache.set('user:1', {'name': 'Alice'}, tag='users')
cache.set('user:2', {'name': 'Bob'}, tag='users')
cache.set('session:1', 'abc123', tag='sessions')

# Get with tag
value, tag = cache.get('user:1', tag=True)

# Evict all users
cache.evict('users')

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')
cache.set('user:1', {'name': 'Alice'}, tag='users')
cache.set('user:2', {'name': 'Bob'}, tag='users')
cache.set('session:1', 'abc123', tag='sessions')

value, tag = cache.get('user:1', tag=True)
cache.evict('users')
```

### ✅ Scenario 3: Memoization (Works!)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')

@cache.memoize(expire=60)
def expensive_function(x):
    return x * x

expensive_function(5)  # 25

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')

@cache.memoize(expire=60)
def expensive_function(x):
    return x * x

expensive_function(5)  # 25
```

### ✅ Scenario 4: Transactions (Works!)

```python
# Before (diskcache)
from diskcache import Cache

cache = Cache('/tmp/mycache')
with cache.transact():
    cache['total'] = cache.get('total', 0) + 123.4
    cache['count'] = cache.get('count', 0) + 1

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Cache

cache = Cache('/tmp/mycache')
with cache.transact():
    cache['total'] = cache.get('total', 0) + 123.4
    cache['count'] = cache.get('count', 0) + 1
```

### ✅ Scenario 5: FanoutCache with Sub-caches (Works!)

```python
# Before (diskcache)
from diskcache import FanoutCache

fc = FanoutCache('/tmp/mycache')
users = fc.cache('users')
tasks = fc.deque('tasks')
meta = fc.index('metadata')

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import FanoutCache

fc = FanoutCache('/tmp/mycache')
users = fc.cache('users')
tasks = fc.deque('tasks')
meta = fc.index('metadata')
```

### ✅ Scenario 6: Deque with Full Collections Interface (Works!)

```python
# Before (diskcache)
from diskcache import Deque

dq = Deque(directory='/tmp/mydeque')
dq.extend([1, 2, 3, 4, 5])
dq.rotate(2)
print(dq[0])  # 4
dq.reverse()
dq.remove(3)
print(dq.count(1))

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Deque

dq = Deque(directory='/tmp/mydeque')
dq.extend([1, 2, 3, 4, 5])
dq.rotate(2)
print(dq[0])  # 4
dq.reverse()
dq.remove(3)
print(dq.count(1))
```

### ✅ Scenario 7: Index with Full Mapping Interface (Works!)

```python
# Before (diskcache)
from diskcache import Index

idx = Index(directory='/tmp/myindex')
idx['a'] = 1
idx['b'] = 2
key, value = idx.popitem()
idx == {'a': 1}

# After (diskcache_rs) - NO CHANGES NEEDED
from diskcache_rs import Index

idx = Index(directory='/tmp/myindex')
idx['a'] = 1
idx['b'] = 2
key, value = idx.popitem()
idx == {'a': 1}
```

---

---

## Recipes API Comparison

### ✅ Fully Compatible Synchronization Primitives

| Class/Function | diskcache | diskcache_rs | Notes |
|----------------|-----------|--------------|-------|
| `Lock(cache, key, expire, tag)` | ✅ | ✅ | Cross-process spin lock |
| `Lock.acquire()` | ✅ | ✅ | Spin-lock algorithm |
| `Lock.release()` | ✅ | ✅ | Delete-key based |
| `Lock.locked()` | ✅ | ✅ | Check if acquired |
| `Lock` context manager | ✅ | ✅ | `with lock:` |
| `RLock(cache, key, expire, tag)` | ✅ | ✅ | Re-entrant lock |
| `RLock.acquire()` | ✅ | ✅ | PID+TID based ownership |
| `RLock.release()` | ✅ | ✅ | Decrements count |
| `RLock` context manager | ✅ | ✅ | `with rlock:` |
| `BoundedSemaphore(cache, key, value, ...)` | ✅ | ✅ | Bounded semaphore |
| `BoundedSemaphore.acquire()` | ✅ | ✅ | Spin-lock decrement |
| `BoundedSemaphore.release()` | ✅ | ✅ | Increment with assertion |
| `BoundedSemaphore` context manager | ✅ | ✅ | `with sem:` |

### ✅ Fully Compatible Recipes and Decorators

| Class/Function | diskcache | diskcache_rs | Notes |
|----------------|-----------|--------------|-------|
| `Averager(cache, key, expire, tag)` | ✅ | ✅ | Running average |
| `Averager.add(value)` | ✅ | ✅ | Add value to average |
| `Averager.get()` | ✅ | ✅ | Get current average |
| `Averager.pop()` | ✅ | ✅ | Get average and delete |
| `throttle(cache, count, seconds, ...)` | ✅ | ✅ | Rate limiting decorator |
| `barrier(cache, lock_factory, ...)` | ✅ | ✅ | Barrier decorator |
| `memoize_stampede(cache, expire, ...)` | ✅ | ✅ | Stampede-protected memoize |

---

## Constants and Exceptions API Comparison

### ✅ Fully Compatible Constants

| Constant | diskcache | diskcache_rs | Notes |
|----------|-----------|--------------|-------|
| `ENOVAL` | ✅ | ✅ | Cache miss sentinel |
| `UNKNOWN` | ✅ | ✅ | Unknown value sentinel |
| `DEFAULT_SETTINGS` | ✅ | ✅ | Default cache settings dict |
| `EVICTION_POLICY` | ✅ | ✅ | Eviction policy definitions |

### ✅ Fully Compatible Exceptions and Warnings

| Class | diskcache | diskcache_rs | Notes |
|-------|-----------|--------------|-------|
| `Timeout` | ✅ | ✅ | Database timeout exception |
| `EmptyDirWarning` | ✅ | ✅ | Empty directory warning |
| `UnknownFileWarning` | ✅ | ✅ | Unknown file warning |

---

## Disk Serialization API Comparison

### ✅ Fully Compatible Disk Classes

| Class | diskcache | diskcache_rs | Notes |
|-------|-----------|--------------|-------|
| `Disk(directory, min_file_size, ...)` | ✅ | ✅ | Pickle-based serialization |
| `Disk.store(value, read, key)` | ✅ | ✅ | Serialize value |
| `Disk.fetch(mode, filename, value, read)` | ✅ | ✅ | Deserialize value |
| `Disk.put(key)` | ✅ | ✅ | Serialize key |
| `Disk.get(key, raw)` | ✅ | ✅ | Deserialize key |
| `Disk.hash(key)` | ✅ | ✅ | Hash key |
| `Disk.filename(key, value)` | ✅ | ✅ | Generate filename |
| `Disk.remove(filename)` | ✅ | ✅ | Remove file |
| `JSONDisk(directory, compress_level)` | ✅ | ✅ | JSON+zlib serialization |

### ⚠️ Not Applicable

| Feature | Notes |
|---------|-------|
| `DjangoCache` | Django integration - only available when Django is installed |

---

## Conclusion

### Can developers just change the namespace?

**Answer**: **Yes, for ~100% of use cases** ✅

- ✅ **Basic caching** (get/set/delete): Fully compatible
- ✅ **Dictionary interface**: Fully compatible
- ✅ **Atomic operations** (incr/decr/add/pop/touch): Fully compatible
- ✅ **Memoization** (`memoize()` decorator): Fully compatible
- ✅ **Transactions** (`transact()` context manager): Fully compatible
- ✅ **Queue operations** (push/pull/peek): Fully compatible
- ✅ **Sub-caches** (cache/deque/index): Fully compatible
- ✅ **Deque and Index** classes: Fully compatible with all methods
- ✅ **Maintenance** (check/cull/expire/vacuum/reset): Fully compatible
- ✅ **Metadata** (directory/timeout/disk/stats/volume): Fully compatible
- ✅ **Tag operations** (set with tag, get with tag, evict by tag): Fully compatible
- ✅ **Expire time return** (get/pop/peek with expire_time): Fully compatible
- ✅ **Read parameter** (set/get with read=True): Fully compatible
- ✅ **Pickle serialization** (__getstate__/__setstate__): Fully compatible
- ✅ **Synchronization** (Lock/RLock/BoundedSemaphore): Fully compatible
- ✅ **Recipes** (Averager/throttle/barrier/memoize_stampede): Fully compatible
- ✅ **Constants** (ENOVAL/UNKNOWN/DEFAULT_SETTINGS/EVICTION_POLICY): Fully compatible
- ✅ **Exceptions** (Timeout/EmptyDirWarning/UnknownFileWarning): Fully compatible
- ✅ **Disk classes** (Disk/JSONDisk): Fully compatible

**Migration is straightforward for all use cases - just change the import!** 🎉
