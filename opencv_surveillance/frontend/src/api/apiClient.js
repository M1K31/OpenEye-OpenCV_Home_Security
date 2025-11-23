// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import axios from 'axios';
import { API_CONFIG, RETRY_CONFIG, PUBLIC_ENDPOINTS } from '../config';

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
const isRetryableError = (error) => {
  if (!error.response) {
    // Network errors (no response) are retryable
    return true;
  }

  const status = error.response.status;

  // Retry on server errors (5xx) and rate limiting (429)
  if (status >= 500 || status === 429) {
    return true;
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
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;

    // Handle 401 Unauthorized
    if (response?.status === 401) {
      const hadToken = localStorage.getItem('access_token');

      // Only redirect if we had a token (meaning it expired)
      // Don't redirect if we never had a token (user not logged in yet)
      if (hadToken && !isPublicEndpoint(config.url)) {
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
