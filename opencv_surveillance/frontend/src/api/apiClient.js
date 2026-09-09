// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import axios from 'axios';
import { API_CONFIG, RETRY_CONFIG, PUBLIC_ENDPOINTS } from '../config';
import { logger } from '../utils/logger';

/**
 * Centralized API Client with Authentication Handling (v3.8.0)
 *
 * Features:
 * - Automatic token injection
 * - 401 error handling with refresh token support
 * - Public endpoint bypass
 * - No 401 spam on unauthenticated requests
 * - Automatic retry with exponential backoff
 *
 * Note: The main axios interceptors are set up in authService.js
 * This file provides an alternative client with retry logic
 * Configuration is centralized in config.js
 */

// Create axios instance with centralized configuration
const apiClient = axios.create({
  baseURL: API_CONFIG.baseURL,
  timeout: API_CONFIG.timeout,
  headers: API_CONFIG.defaultHeaders,
});

/**
 * Check if error is retryable
 */
// Methods with no side effects, so replaying one cannot create anything.
//
// A POST that reached the server and succeeded before the connection dropped is
// indistinguishable, from here, from one that never arrived — and replaying it
// creates a second camera, automation rule or exported clip. That was happening
// for every method, because the old check looked only at the failure and never
// at the request.
//
// PUT and DELETE are idempotent by HTTP contract and are still excluded. A
// replayed DELETE whose first attempt succeeded returns 404, so the user is
// shown "not found" for work that was in fact done. Not retrying costs a little
// resilience; retrying costs correctness of what the user is told.
const REPLAYABLE_METHODS = new Set(['get', 'head', 'options']);

const isReplayable = (config) =>
  REPLAYABLE_METHODS.has(String(config?.method || 'get').toLowerCase());

const isRetryableError = (error) => {
  const { config, response } = error;

  // No config means the failure happened before a request was built — in the
  // request interceptor. There is nothing to replay.
  if (!config) {
    return false;
  }

  if (!response) {
    // A network error is ambiguous: the server may have processed the request
    // and lost the response. Only safe methods may be replayed.
    return isReplayable(config);
  }

  const status = response.status;

  // 429 is the one unambiguous case: the server rejected the request without
  // acting on it, so replaying any method is safe.
  if (status === 429) {
    return true;
  }

  // 5xx is ambiguous in the same way as a network error — a 500 can be raised
  // after the write committed — so the same restriction applies.
  if (status >= 500) {
    return isReplayable(config);
  }

  // Don't retry on client errors (4xx except 429)
  return false;
};

/**
 * Calculate retry delay with exponential backoff and jitter
 */
const getRetryDelay = (retryCount) => {
  const delay = Math.min(
    RETRY_CONFIG.initialDelay * Math.pow(RETRY_CONFIG.backoffMultiplier, retryCount),
    RETRY_CONFIG.maxDelay
  );

  // Add jitter (±25%) to prevent thundering herd
  const jitter = delay * 0.25 * (Math.random() * 2 - 1);
  return Math.floor(delay + jitter);
};

/**
 * Sleep function for retry delays
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Check if an endpoint is public (no auth required)
 */
const isPublicEndpoint = (url) => {
  return PUBLIC_ENDPOINTS.some(endpoint => url?.includes(endpoint));
};

/**
 * Request Interceptor (v3.8.0)
 * - Adds Authorization header if token exists
 * - Skips auth for public endpoints
 * - Prevents 401 spam by only adding token when available
 * - Uses access_token (updated for refresh token system)
 */
apiClient.interceptors.request.use(
  (config) => {
    // Skip auth for public endpoints
    if (isPublicEndpoint(config.url)) {
      return config;
    }

    // Only add auth header if token exists (v3.8.0: using access_token)
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Response Interceptor (v3.8.0)
 * - Handles 401 errors gracefully
 * - Delegates token refresh to authService.js (via global axios interceptors)
 * - Only redirects to login if token existed (i.e., it expired)
 * - Prevents redirect loops
 * - Implements automatic retry with exponential backoff
 *
 * Note: The main 401 handling with automatic token refresh is done
 * in authService.js. This interceptor provides fallback behavior.
 */
/**
 * Mark server timestamps as UTC.
 *
 * The backend stores every instant in UTC, but SQLite has no timezone type, so
 * what arrives over the wire is "2026-08-19T23:44:09" with nothing to say which
 * zone that is. JavaScript reads an ISO string WITHOUT an offset as local time
 * and one ending in Z as UTC, so leaving it bare makes the browser render a UTC
 * instant as though it were already local — every timestamp shifted by the
 * viewer's offset, and correct only in London.
 *
 * Appending Z here rather than at 60-odd `new Date(...)` call sites, or on every
 * field of every response schema, because there is one rule and it belongs in
 * one place. Anything that is already marked, or is not an ISO instant, is left
 * alone.
 */
const BARE_ISO_INSTANT = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?$/;

const markUtc = (value) => {
  if (typeof value === 'string') {
    return BARE_ISO_INSTANT.test(value) ? `${value.replace(' ', 'T')}Z` : value;
  }
  if (Array.isArray(value)) return value.map(markUtc);
  if (value && typeof value === 'object') {
    const out = {};
    for (const key of Object.keys(value)) out[key] = markUtc(value[key]);
    return out;
  }
  return value;
};

apiClient.interceptors.response.use(
  (response) => {
    if (response?.data) response.data = markUtc(response.data);
    return response;
  },
  async (error) => {
    const { config, response } = error;

    // Handle 401 Unauthorized
    if (response?.status === 401) {
      const hadToken = localStorage.getItem('access_token');

      // Only redirect if we had a token (meaning it expired)
      // Don't redirect if we never had a token (user not logged in yet)
      if (hadToken && !isPublicEndpoint(config?.url)) {
        logger.warn('Token expired or invalid after refresh attempt');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');

        // Only redirect if not already on login page
        if (!window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
      }
    }

    // Retry logic for retryable errors
    // isRetryableError returns false when config is absent, so it is safe to
    // dereference here. It was previously dereferenced first, and an error
    // raised in the request interceptor has no config — so `config.__retryCount`
    // threw a TypeError that replaced the real error with a misleading one.
    if (isRetryableError(error)) {
      // Initialize retry count if not set
      config.__retryCount = config.__retryCount || 0;

      // Check if we should retry
      if (config.__retryCount < RETRY_CONFIG.maxRetries) {
        config.__retryCount += 1;

        const delay = getRetryDelay(config.__retryCount);
        const retryMessage = `Retrying request (${config.__retryCount}/${RETRY_CONFIG.maxRetries}) after ${delay}ms...`;

        logger.warn(retryMessage, {
          url: config.url,
          method: config.method,
          error: error.message,
          status: response?.status,
        });

        // Wait before retrying
        await sleep(delay);

        // Retry the request
        return apiClient(config);
      } else {
        logger.error('Max retries reached for request:', {
          url: config.url,
          method: config.method,
          retries: config.__retryCount,
        });
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Helper: Check if user is authenticated (v3.8.0)
 */
export const isAuthenticated = () => {
  return !!localStorage.getItem('access_token');
};

/**
 * Helper: Get current access token (v3.8.0)
 */
export const getToken = () => {
  return localStorage.getItem('access_token');
};

/**
 * Helper: Set authentication token (v3.8.0)
 */
export const setToken = (token) => {
  if (token) {
    localStorage.setItem('access_token', token);
  } else {
    localStorage.removeItem('access_token');
  }
};

/**
 * Helper: Clear authentication (v3.8.0)
 * Clears both access and refresh tokens
 */
export const clearAuth = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('token_expires_at');
};

/**
 * Helper: Validate token with backend
 */
export const validateToken = async () => {
  try {
    const response = await apiClient.get('/users/me');
    return { valid: true, user: response.data };
  } catch (error) {
    return { valid: false, error: error.message };
  }
};

export default apiClient;
