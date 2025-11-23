# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for the cache module
"""

import pytest
import time
from backend.core.cache import CacheEntry, SimpleCache, get_cache, cached


class TestCacheEntry:
    """Test CacheEntry class"""

    def test_cache_entry_creation(self):
        """Test creating a cache entry"""
        entry = CacheEntry("test_value", ttl_seconds=60)
        assert entry.value == "test_value"
        assert entry.hit_count == 0
        assert not entry.is_expired()

    def test_cache_entry_expiration(self):
        """Test cache entry expiration"""
        entry = CacheEntry("test_value", ttl_seconds=1)
        assert not entry.is_expired()

        # Wait for expiration
        time.sleep(1.1)
        assert entry.is_expired()

    def test_cache_entry_age(self):
        """Test cache entry age calculation"""
        entry = CacheEntry("test_value", ttl_seconds=60)
        time.sleep(0.1)
        age = entry.age_seconds()
        assert age >= 0.1
        assert age < 1.0


class TestSimpleCache:
    """Test SimpleCache class"""

    @pytest.fixture
    def cache(self):
        """Create a fresh cache instance for each test"""
        return SimpleCache(default_ttl=300)

    def test_cache_initialization(self, cache):
        """Test cache is initialized correctly"""
        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0

    def test_cache_set_and_get(self, cache):
        """Test basic set and get operations"""
        cache.set("key1", "value1")
        result = cache.get("key1")
        assert result == "value1"

        stats = cache.get_stats()
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 0

    def test_cache_miss(self, cache):
        """Test cache miss for non-existent key"""
        result = cache.get("nonexistent")
        assert result is None

        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0

    def test_cache_with_custom_ttl(self, cache):
        """Test setting cache entry with custom TTL"""
        cache.set("key1", "value1", ttl=1)

        # Should be available immediately
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired and return None
        result = cache.get("key1")
        assert result is None

        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_cache_invalidate(self, cache):
        """Test manual cache invalidation"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.invalidate("key1")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_cache_invalidate_pattern(self, cache):
        """Test pattern-based cache invalidation"""
        cache.set("user:1:profile", "data1")
        cache.set("user:2:profile", "data2")
        cache.set("user:1:settings", "data3")
        cache.set("system:config", "data4")

        # Invalidate all user:1 entries
        cache.invalidate_pattern("user:1")

        assert cache.get("user:1:profile") is None
        assert cache.get("user:1:settings") is None
        assert cache.get("user:2:profile") == "data2"
        assert cache.get("system:config") == "data4"

        stats = cache.get_stats()
        assert stats["evictions"] == 2

    def test_cache_clear(self, cache):
        """Test clearing all cache entries"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

        stats = cache.get_stats()
        assert stats["entries"] == 0
        assert stats["evictions"] == 3

    def test_cache_cleanup_expired(self, cache):
        """Test manual cleanup of expired entries"""
        # Set some entries with different TTLs
        cache.set("key1", "value1", ttl=10)  # Long TTL
        cache.set("key2", "value2", ttl=1)   # Short TTL
        cache.set("key3", "value3", ttl=1)   # Short TTL

        # Wait for short TTL entries to expire
        time.sleep(1.1)

        # Run cleanup
        cache.cleanup_expired()

        # Long TTL entry should still exist
        assert cache.get("key1") == "value1"

        # Short TTL entries should be gone
        stats = cache.get_stats()
        assert stats["entries"] == 1
        assert stats["evictions"] == 2

    def test_cache_hit_count(self, cache):
        """Test that hit count increments correctly"""
        cache.set("key1", "value1")

        # Access the entry multiple times
        for _ in range(5):
            cache.get("key1")

        stats = cache.get_stats()
        assert stats["hits"] == 5

    def test_cache_statistics(self, cache):
        """Test cache statistics calculation"""
        # 3 sets, 3 hits, 2 misses
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.get("key1")  # hit
        cache.get("key2")  # hit
        cache.get("key3")  # hit
        cache.get("nonexistent1")  # miss
        cache.get("nonexistent2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 2
        assert stats["total_requests"] == 5
        assert stats["hit_rate_percent"] == 60.0

    def test_cache_thread_safety(self, cache):
        """Test that cache operations are thread-safe"""
        import threading

        def set_values():
            for i in range(100):
                cache.set(f"key{i}", f"value{i}")

        def get_values():
            for i in range(100):
                cache.get(f"key{i}")

        # Run concurrent operations
        threads = [
            threading.Thread(target=set_values),
            threading.Thread(target=get_values),
            threading.Thread(target=set_values),
            threading.Thread(target=get_values)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Cache should still be consistent
        stats = cache.get_stats()
        assert stats["entries"] <= 100  # Some entries might have been overwritten


class TestCacheDecorator:
    """Test the @cached decorator"""

    def test_cached_decorator_basic(self):
        """Test basic decorator functionality"""
        call_count = 0

        @cached(ttl=60)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # First call - should execute function
        result1 = expensive_function(2, 3)
        assert result1 == 5
        assert call_count == 1

        # Second call with same args - should use cache
        result2 = expensive_function(2, 3)
        assert result2 == 5
        assert call_count == 1  # Function not called again

        # Call with different args - should execute function
        result3 = expensive_function(5, 7)
        assert result3 == 12
        assert call_count == 2

    def test_cached_decorator_with_ttl(self):
        """Test decorator with TTL expiration"""
        call_count = 0

        @cached(ttl=1)
        def get_data():
            nonlocal call_count
            call_count += 1
            return "data"

        # First call
        result1 = get_data()
        assert result1 == "data"
        assert call_count == 1

        # Second call within TTL
        result2 = get_data()
        assert result2 == "data"
        assert call_count == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Third call after TTL - should execute function again
        result3 = get_data()
        assert result3 == "data"
        assert call_count == 2

    def test_cached_decorator_with_key_prefix(self):
        """Test decorator with custom key prefix"""
        @cached(ttl=60, key_prefix="custom")
        def get_user(user_id):
            return f"user_{user_id}"

        result1 = get_user(1)
        result2 = get_user(1)

        assert result1 == result2 == "user_1"

    def test_cached_decorator_invalidation(self):
        """Test manual cache invalidation through decorator"""
        call_count = 0

        @cached(ttl=60)
        def get_settings():
            nonlocal call_count
            call_count += 1
            return {"theme": "dark"}

        # First call
        result1 = get_settings()
        assert call_count == 1

        # Second call - uses cache
        result2 = get_settings()
        assert call_count == 1

        # Invalidate cache
        get_settings.invalidate()

        # Third call - executes function again
        result3 = get_settings()
        assert call_count == 2

    def test_cached_decorator_with_kwargs(self):
        """Test decorator with keyword arguments"""
        @cached(ttl=60)
        def calculate(a, b, operation="add"):
            if operation == "add":
                return a + b
            elif operation == "multiply":
                return a * b

        result1 = calculate(2, 3, operation="add")
        result2 = calculate(2, 3, operation="multiply")

        assert result1 == 5
        assert result2 == 6


class TestGlobalCacheInstance:
    """Test global cache instance management"""

    def test_get_cache_singleton(self):
        """Test that get_cache returns the same instance"""
        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

    def test_get_cache_initialization(self):
        """Test that global cache is properly initialized"""
        cache = get_cache()

        assert isinstance(cache, SimpleCache)
        stats = cache.get_stats()
        assert "entries" in stats
        assert "hits" in stats
        assert "misses" in stats
