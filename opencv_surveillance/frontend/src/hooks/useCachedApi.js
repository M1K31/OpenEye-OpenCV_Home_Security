/**
 * Custom Hook for Cached API Calls
 *
 * Provides automatic caching, loading states, and error handling for API calls
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import apiClient from '../api/apiClient';
import apiCache, { CacheTTL } from '../services/apiCache';

/**
 * Hook for making cached API calls
 *
 * @param {string} url - API endpoint URL
 * @param {Object} options - Configuration options
 * @param {Object} options.params - Query parameters
 * @param {number} options.ttl - Cache TTL in milliseconds
 * @param {boolean} options.enabled - Whether to auto-fetch on mount (default: true)
 * @param {Array} options.dependencies - Dependencies to trigger refetch
 * @param {Function} options.transform - Transform function for response data
 * @returns {Object} - { data, loading, error, refetch, invalidate }
 */
export function useCachedApi(url, options = {}) {
  const {
    params = {},
    ttl = CacheTTL.MEDIUM,
    enabled = true,
    dependencies = [],
    transform = (data) => data,
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  // Generate cache key
  const cacheKey = apiCache.getCacheKey(url, params);

  // Fetch data function
  const fetchData = useCallback(async (skipCache = false) => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Skip cache if requested
      if (skipCache) {
        apiCache.invalidate(cacheKey);
      }

      // Fetch with caching
      const response = await apiCache.fetch(
        cacheKey,
        async () => {
          const res = await apiClient.get(url, { params });
          return res.data;
        },
        ttl
      );

      if (mountedRef.current) {
        setData(transform(response));
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        setLoading(false);
      }
    }
  }, [url, cacheKey, ttl, enabled]); // Removed 'transform' to prevent infinite loops

  // Auto-fetch on mount and when dependencies change
  useEffect(() => {
    fetchData();
  }, [fetchData, ...dependencies]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Refetch function (bypasses cache)
  const refetch = useCallback(() => {
    return fetchData(true);
  }, [fetchData]);

  // Invalidate cache for this request
  const invalidate = useCallback(() => {
    apiCache.invalidate(cacheKey);
  }, [cacheKey]);

  return {
    data,
    loading,
    error,
    refetch,
    invalidate
  };
}

/**
 * Hook for making multiple parallel cached API calls
 *
 * @param {Array} requests - Array of request configs: [{ url, params, ttl }, ...]
 * @param {Object} options - Configuration options
 * @returns {Object} - { data, loading, error, refetch }
 */
export function useCachedApiMultiple(requests, options = {}) {
  const { enabled = true } = options;
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);

  const fetchAll = useCallback(async (skipCache = false) => {
    if (!enabled || requests.length === 0) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Fetch all requests in parallel
      const promises = requests.map(async (req) => {
        const { url, params = {}, ttl = CacheTTL.MEDIUM, transform = (d) => d } = req;
        const cacheKey = apiCache.getCacheKey(url, params);

        if (skipCache) {
          apiCache.invalidate(cacheKey);
        }

        const response = await apiCache.fetch(
          cacheKey,
          async () => {
            const res = await apiClient.get(url, { params });
            return res.data;
          },
          ttl
        );

        return transform(response);
      });

      const results = await Promise.all(promises);

      if (mountedRef.current) {
        setData(results);
        setLoading(false);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err);
        setLoading(false);
      }
    }
  }, [requests, enabled]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refetch = useCallback(() => {
    return fetchAll(true);
  }, [fetchAll]);

  return {
    data,
    loading,
    error,
    refetch
  };
}

export default useCachedApi;
