"""Redis-based caching utilities."""

import json
import logging
from typing import Any, Optional, Callable
from functools import wraps
import redis
from src.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages Redis caching for API responses."""

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize cache manager.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or settings.redis_url
        try:
            self.redis = redis.from_url(self.redis_url, decode_responses=True)
            self.redis.ping()
            logger.info("Connected to Redis for caching")
        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}, caching disabled")
            self.redis = None

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        if not self.redis:
            return None

        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: int = 900) -> bool:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default 15 min)

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        try:
            self.redis.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {str(e)}")
            return False

    def cached(self, ttl: int = 900, key_prefix: str = ""):
        """Decorator for caching function results.

        Args:
            ttl: Time to live in seconds
            key_prefix: Prefix for cache key

        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key from function name and args
                key_parts = [key_prefix, func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(filter(None, key_parts))

                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # Call function and cache result
                logger.debug(f"Cache miss for {cache_key}")
                result = await func(*args, **kwargs)

                if result is not None:
                    self.set(cache_key, result, ttl)

                return result

            return wrapper
        return decorator


# Global cache instance
cache = CacheManager()
