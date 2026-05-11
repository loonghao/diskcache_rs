"""Django cache backend for diskcache_rs."""

from typing import Any, Dict, Iterable, Optional

from .cache import Cache

try:
    from django.core.cache.backends.base import DEFAULT_TIMEOUT, BaseCache
except ImportError:  # pragma: no cover - exercised when Django is not installed
    DEFAULT_TIMEOUT = object()

    class DjangoCache:  # type: ignore[no-redef]
        """Placeholder that reports the missing optional Django dependency."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError(
                "DjangoCache requires Django. Install Django to use "
                "'diskcache_rs.DjangoCache' as a Django cache backend."
            )

else:

    class DjangoCache(BaseCache):
        """Django cache backend backed by diskcache_rs.Cache."""

        def __init__(self, location: str, params: Dict[str, Any]) -> None:
            super().__init__(params)
            options = dict(params.get("OPTIONS", {}))
            self._cache = Cache(location, **options)

        def add(
            self,
            key: str,
            value: Any,
            timeout: Any = DEFAULT_TIMEOUT,
            version: Optional[int] = None,
        ) -> bool:
            key = self.make_and_validate_key(key, version=version)
            if self._cache.get(key, default=None) is not None:
                return False
            return self.set(key, value, timeout=timeout, version=None)

        def get(
            self,
            key: str,
            default: Any = None,
            version: Optional[int] = None,
        ) -> Any:
            key = self.make_and_validate_key(key, version=version)
            return self._cache.get(key, default=default)

        def set(
            self,
            key: str,
            value: Any,
            timeout: Any = DEFAULT_TIMEOUT,
            version: Optional[int] = None,
        ) -> bool:
            key = self.make_and_validate_key(key, version=version)
            expire = self.get_backend_timeout(timeout)
            return self._cache.set(key, value, expire=expire)

        def touch(
            self,
            key: str,
            timeout: Any = DEFAULT_TIMEOUT,
            version: Optional[int] = None,
        ) -> bool:
            key = self.make_and_validate_key(key, version=version)
            expire = self.get_backend_timeout(timeout)
            return self._cache.touch(key, expire=expire)

        def delete(self, key: str, version: Optional[int] = None) -> bool:
            key = self.make_and_validate_key(key, version=version)
            return self._cache.delete(key)

        def clear(self) -> bool:
            self._cache.clear()
            return True

        def get_many(
            self,
            keys: Iterable[str],
            version: Optional[int] = None,
        ) -> Dict[str, Any]:
            values = {}
            for key in keys:
                value = self.get(key, version=version)
                if value is not None:
                    values[key] = value
            return values

        def set_many(
            self,
            data: Dict[str, Any],
            timeout: Any = DEFAULT_TIMEOUT,
            version: Optional[int] = None,
        ) -> list:
            failed = []
            for key, value in data.items():
                if not self.set(key, value, timeout=timeout, version=version):
                    failed.append(key)
            return failed

        def delete_many(
            self,
            keys: Iterable[str],
            version: Optional[int] = None,
        ) -> None:
            for key in keys:
                self.delete(key, version=version)

        def has_key(self, key: str, version: Optional[int] = None) -> bool:
            key = self.make_and_validate_key(key, version=version)
            return key in self._cache

        def close(self, **kwargs: Any) -> None:
            self._cache.close()
