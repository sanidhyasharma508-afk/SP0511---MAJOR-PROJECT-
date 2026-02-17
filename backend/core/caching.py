import pickle
import json
import hashlib
from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
import asyncio
import inspect

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("caching")


class CacheBackend:
    """Abstract cache backend interface"""

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        raise NotImplementedError

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        raise NotImplementedError

    async def clear(self) -> bool:
        """Clear all cache"""
        raise NotImplementedError

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        raise NotImplementedError


class InMemoryCacheBackend(CacheBackend):
    """In-memory cache backend (for development)"""

    def __init__(self):
        self.store: Dict[str, Dict[str, Any]] = {}

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key not in self.store:
            return None

        entry = self.store[key]

        # Check expiration
        if entry.get("expires_at"):
            if datetime.utcnow() > entry["expires_at"]:
                del self.store[key]
                return None

        logger.log_event("cache_hit", level="DEBUG", key=key, backend="memory")
        return entry["value"]

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        ttl = ttl or settings.CACHE_TTL

        self.store[key] = {
            "value": value,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(seconds=ttl) if ttl else None,
        }

        logger.log_event("cache_set", level="DEBUG", key=key, backend="memory", ttl=ttl)
        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if key in self.store:
            del self.store[key]
            logger.log_event("cache_delete", level="DEBUG", key=key, backend="memory")
            return True
        return False

    async def clear(self) -> bool:
        """Clear all cache"""
        count = len(self.store)
        self.store.clear()
        logger.log_event("cache_clear", level="DEBUG", backend="memory", cleared_items=count)
        return True

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return key in self.store


class RedisCacheBackend(CacheBackend):
    """Redis cache backend (for production)"""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis = None
        self._init_in_progress = False

    async def _ensure_connection(self):
        """Ensure Redis connection is established"""
        if self.redis is None and not self._init_in_progress:
            self._init_in_progress = True
            try:
                import redis.asyncio as redis

                self.redis = await redis.from_url(self.redis_url, decode_responses=True)
                await self.redis.ping()
                logger.log_event("redis_connected", level="INFO", url=self.redis_url)
            except Exception as e:
                logger.log_error("redis_connection_failed", e, url=self.redis_url)
                self.redis = None
            finally:
                self._init_in_progress = False

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            await self._ensure_connection()
            if self.redis is None:
                return None

            value = await self.redis.get(key)

            if value:
                try:
                    # Try JSON first
                    return json.loads(value)
                except:
                    # Fall back to pickle
                    return pickle.loads(value.encode())

            logger.log_event("cache_miss", level="DEBUG", key=key, backend="redis")
            return None
        except Exception as e:
            logger.log_error("cache_get_failed", e, key=key)
            return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        try:
            await self._ensure_connection()
            if self.redis is None:
                return False

            ttl = ttl or settings.CACHE_TTL

            try:
                # Try JSON serialization
                serialized = json.dumps(value)
            except:
                # Fall back to pickle
                serialized = pickle.dumps(value).decode()

            await self.redis.setex(key, ttl, serialized)
            logger.log_event("cache_set", level="DEBUG", key=key, backend="redis", ttl=ttl)
            return True
        except Exception as e:
            logger.log_error("cache_set_failed", e, key=key)
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            await self._ensure_connection()
            if self.redis is None:
                return False

            result = await self.redis.delete(key)
            logger.log_event(
                "cache_delete", level="DEBUG", key=key, backend="redis", deleted=bool(result)
            )
            return bool(result)
        except Exception as e:
            logger.log_error("cache_delete_failed", e, key=key)
            return False

    async def clear(self) -> bool:
        """Clear all cache"""
        try:
            await self._ensure_connection()
            if self.redis is None:
                return False

            keys_deleted = await self.redis.flushdb()
            logger.log_event(
                "cache_clear", level="DEBUG", backend="redis", keys_deleted=keys_deleted
            )
            return True
        except Exception as e:
            logger.log_error("cache_clear_failed", e)
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            await self._ensure_connection()
            if self.redis is None:
                return False

            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.log_error("cache_exists_failed", e, key=key)
            return False


class CacheManager:
    """Cache manager with pluggable backend"""

    def __init__(self, backend: CacheBackend = None):
        if backend:
            self.backend = backend
        elif settings.REDIS_URL and settings.REDIS_URL != "redis://":
            self.backend = RedisCacheBackend()
        else:
            self.backend = InMemoryCacheBackend()

        logger.log_event(
            "cache_manager_initialized", level="INFO", backend=type(self.backend).__name__
        )

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not settings.ENABLE_CACHING:
            return None

        return await self.backend.get(key)

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        if not settings.ENABLE_CACHING:
            return False

        return await self.backend.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        return await self.backend.delete(key)

    async def clear(self) -> bool:
        """Clear all cache"""
        return await self.backend.clear()

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        return await self.backend.exists(key)

    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_parts = [prefix] + list(map(str, args))

        if kwargs:
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")

        key_string = ":".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()


# Global cache manager
cache_manager = CacheManager()


def cached(prefix: str = None, ttl: int = None):
    """Decorator to cache function results"""

    def decorator(func: Callable):
        cache_prefix = prefix or func.__name__

        @asyncio.coroutine if not inspect.iscoroutinefunction(func) else lambda x: x
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_manager.generate_key(cache_prefix, *args, **kwargs)

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.log_event("cache_hit", level="DEBUG", key=cache_key, function=func.__name__)
                return cached_value

            # Call function
            result = await func(*args, **kwargs)

            # Store in cache
            await cache_manager.set(cache_key, result, ttl)

            return result

        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_manager.generate_key(cache_prefix, *args, **kwargs)

            # Try to get from cache (sync)
            import asyncio

            loop = asyncio.get_event_loop()
            cached_value = loop.run_until_complete(cache_manager.get(cache_key))
            if cached_value is not None:
                logger.log_event("cache_hit", level="DEBUG", key=cache_key, function=func.__name__)
                return cached_value

            # Call function
            result = func(*args, **kwargs)

            # Store in cache (sync)
            loop.run_until_complete(cache_manager.set(cache_key, result, ttl))

            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def invalidate_cache(prefix: str):
    """Decorator to invalidate cache after function execution"""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await cache_manager.delete(cache_manager.generate_key(prefix, *args, **kwargs))
            logger.log_event("cache_invalidated", level="DEBUG", prefix=prefix)
            return result

        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            import asyncio

            loop = asyncio.get_event_loop()
            loop.run_until_complete(
                cache_manager.delete(cache_manager.generate_key(prefix, *args, **kwargs))
            )
            logger.log_event("cache_invalidated", level="DEBUG", prefix=prefix)
            return result

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
