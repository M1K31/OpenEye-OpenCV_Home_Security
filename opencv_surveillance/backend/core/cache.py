# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Simple In-Memory Cache for Query Results
Reduces database load for frequently accessed, rarely changing data
"""

import time
from typing import Any, Optional, Callable
from functools import wraps
import logging
from threading import Lock

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a single cache entry with TTL"""

    def __init__(self, value: Any, ttl_seconds: int):
        self.value = value
        self.expires_at = time.time() + ttl_seconds
        self.created_at = time.time()
        self.hit_count = 0

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return time.time() > self.expires_at

    def age_seconds(self) -> float:
        """Get age of cache entry in seconds"""
        return time.time() - self.created_at


class SimpleCache:
    """
    Thread-safe in-memory cache with TTL support

    Features:
    - Time-to-live (TTL) expiration
    - Manual invalidation
    - Hit/miss statistics
    - Thread-safe operations
    - Automatic cleanup of expired entries
    """

    def __init__(self, default_ttl: int = 300):
        """
        Initialize cache

        Args:
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._lock = Lock()
        self._default_ttl = default_ttl

        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired():
                # Expired entry - remove it
                del self._cache[key]
                self._evictions += 1
                self._misses += 1
                logger.debug(f"Cache miss (expired): {key}")
                return None

            # Valid entry - increment hit count
            entry.hit_count += 1
            self._hits += 1
            logger.debug(f"Cache hit: {key} (age: {entry.age_seconds():.1f}s, hits: {entry.hit_count})")
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl if ttl is not None else self._default_ttl

        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")

    def invalidate(self, key: str):
        """
        Manually invalidate a cache entry

        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._evictions += 1
                logger.debug(f"Cache invalidated: {key}")

    def invalidate_pattern(self, pattern: str):
        """
        Invalidate all cache keys matching a pattern

        Args:
            pattern: String pattern to match (simple substring match)
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
                self._evictions += 1

            if keys_to_delete:
                logger.debug(f"Cache invalidated (pattern '{pattern}'): {len(keys_to_delete)} entries")

    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._evictions += count
            logger.info(f"Cache cleared: {count} entries")

    def cleanup_expired(self):
        """Remove all expired entries (manual cleanup)"""
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]

            for key in expired_keys:
                del self._cache[key]
                self._evictions += 1

            if expired_keys:
                logger.debug(f"Cache cleanup: removed {len(expired_keys)} expired entries")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "entries": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "total_requests": total_requests,
                "hit_rate_percent": round(hit_rate, 2)
            }


# Global cache instance
_cache_instance: Optional[SimpleCache] = None
_cache_lock = Lock()


def get_cache() -> SimpleCache:
    """Get or create global cache instance (thread-safe singleton)"""
    global _cache_instance

    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = SimpleCache(default_ttl=300)  # 5 minutes default
                logger.info("Cache system initialized (TTL: 300s)")

    return _cache_instance


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results

    Args:
        ttl: Time-to-live in seconds (default: 300)
        key_prefix: Prefix for cache key (default: function name)

    Example:
        @cached(ttl=600, key_prefix="settings")
        def get_system_settings(db):
            return db.query(SystemSettings).all()
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key from function name and arguments
            prefix = key_prefix or func.__name__
            # Simple key generation - you may want to improve this
            key = f"{prefix}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            result = cache.get(key)
            if result is not None:
                return result

            # Cache miss - call function and cache result
            result = func(*args, **kwargs)
            cache.set(key, result, ttl=ttl)

            return result

        # Add cache invalidation method to wrapped function
        def invalidate_cache(*args, **kwargs):
            cache = get_cache()
            prefix = key_prefix or func.__name__
            key = f"{prefix}:{str(args)}:{str(kwargs)}"
            cache.invalidate(key)

        wrapper.invalidate = invalidate_cache
        return wrapper

    return decorator
