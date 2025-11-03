/**
 * API Response Cache Service
 *
 * Provides in-memory caching for API responses to reduce redundant network requests
 * and improve perceived performance.
 *
 * Features:
 * - TTL-based expiration
 * - Cache invalidation by key or pattern
 * - Request deduplication (prevents multiple simultaneous requests for same resource)
 */

class ApiCache {
  constructor() {
    this.cache = new Map();
    this.pendingRequests = new Map();
    this.defaultTTL = 30000; // 30 seconds default
  }

  /**
   * Generate cache key from URL and params
   */
  getCacheKey(url, params = {}) {
    const paramStr = Object.keys(params).length > 0
      ? JSON.stringify(params)
      : '';
    return `${url}${paramStr}`;
  }

  /**
   * Get cached response if valid
   */
  get(key) {
    const cached = this.cache.get(key);

    if (!cached) {
      return null;
    }

    // Check if expired
    if (Date.now() > cached.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return cached.data;
  }

  /**
   * Store response in cache
   */
  set(key, data, ttl = this.defaultTTL) {
    this.cache.set(key, {
      data,
      expiresAt: Date.now() + ttl,
      cachedAt: Date.now()
    });
  }

  /**
   * Invalidate cache entry by key
   */
  invalidate(key) {
    this.cache.delete(key);
    this.pendingRequests.delete(key);
  }

  /**
   * Invalidate multiple cache entries by pattern
   * Example: invalidatePattern('/api/cameras') invalidates all camera-related caches
   */
  invalidatePattern(pattern) {
    const keys = Array.from(this.cache.keys());
    keys.forEach(key => {
      if (key.includes(pattern)) {
        this.cache.delete(key);
      }
    });

    const pendingKeys = Array.from(this.pendingRequests.keys());
    pendingKeys.forEach(key => {
      if (key.includes(pattern)) {
        this.pendingRequests.delete(key);
      }
    });
  }

  /**
   * Clear all cache entries
   */
  clear() {
    this.cache.clear();
    this.pendingRequests.clear();
  }

  /**
   * Execute API request with caching and deduplication
   *
   * @param {string} key - Cache key
   * @param {Function} requestFn - Function that returns a Promise (the actual API call)
   * @param {number} ttl - Time to live in milliseconds
   * @returns {Promise} - Cached or fresh data
   */
  async fetch(key, requestFn, ttl = this.defaultTTL) {
    // Check cache first
    const cached = this.get(key);
    if (cached !== null) {
      return cached;
    }

    // Check if request is already in flight
    if (this.pendingRequests.has(key)) {
      return this.pendingRequests.get(key);
    }

    // Execute request and cache result
    const requestPromise = requestFn()
      .then(data => {
        this.set(key, data, ttl);
        this.pendingRequests.delete(key);
        return data;
      })
      .catch(error => {
        this.pendingRequests.delete(key);
        throw error;
      });

    // Store pending request to prevent duplicates
    this.pendingRequests.set(key, requestPromise);

    return requestPromise;
  }

  /**
   * Get cache statistics
   */
  getStats() {
    const now = Date.now();
    let validEntries = 0;
    let expiredEntries = 0;

    this.cache.forEach((value) => {
      if (now > value.expiresAt) {
        expiredEntries++;
      } else {
        validEntries++;
      }
    });

    return {
      totalEntries: this.cache.size,
      validEntries,
      expiredEntries,
      pendingRequests: this.pendingRequests.size
    };
  }

  /**
   * Clean up expired entries
   */
  cleanup() {
    const now = Date.now();
    const keys = Array.from(this.cache.keys());

    keys.forEach(key => {
      const cached = this.cache.get(key);
      if (cached && now > cached.expiresAt) {
        this.cache.delete(key);
      }
    });
  }
}

// Create singleton instance
const apiCache = new ApiCache();

// Run cleanup every 5 minutes
setInterval(() => {
  apiCache.cleanup();
}, 5 * 60 * 1000);

// Cache TTL presets (in milliseconds)
export const CacheTTL = {
  SHORT: 10000,      // 10 seconds - for frequently changing data
  MEDIUM: 30000,     // 30 seconds - default
  LONG: 60000,       // 1 minute - for relatively static data
  VERY_LONG: 300000, // 5 minutes - for very static data (settings, etc.)
};

export default apiCache;
