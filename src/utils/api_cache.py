"""API response caching to reduce redundant calls and avoid rate limits."""

import time
import hashlib
import json
from typing import Any, Optional, Callable
from functools import wraps

# In-memory cache with TTL
_cache: dict[str, tuple[float, Any]] = {}


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from function arguments."""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl_seconds: int = 300):
    """Decorator to cache API responses with TTL.

    Args:
        ttl_seconds: Time to live in seconds (default 5 minutes)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__module__}.{func.__name__}:{cache_key(*args, **kwargs)}"

            # Check cache
            if key in _cache:
                cached_at, cached_value = _cache[key]
                if time.time() - cached_at < ttl_seconds:
                    return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)
            _cache[key] = (time.time(), result)

            # Clean old entries (every 100 calls)
            if len(_cache) > 100:
                cleanup_cache(ttl_seconds)

            return result
        return wrapper
    return decorator


def cleanup_cache(max_age: int = 600):
    """Remove expired cache entries."""
    now = time.time()
    expired = [k for k, (cached_at, _) in _cache.items() if now - cached_at > max_age]
    for k in expired:
        del _cache[k]


def clear_cache():
    """Clear all cached entries."""
    _cache.clear()
