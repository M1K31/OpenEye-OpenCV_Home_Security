// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import axios from 'axios';

/**
 * Centralized API Client with Authentication Handling
 *
 * Features:
 * - Automatic token injection
 * - 401 error handling
 * - Public endpoint bypass
 * - No 401 spam on unauthenticated requests
 * - Automatic retry with exponential backoff
 */

// Create axios instance
const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Retry configuration
 */
const RETRY_CONFIG = {
  maxRetries: 3,
  initialDelay: 1000, // 1 second
  maxDelay: 10000, // 10 seconds
  backoffMultiplier: 2, // Exponential backoff
};

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

// Public endpoints that don't require authentication
const PUBLIC_ENDPOINTS = [
  '/token',
  '/setup/status',
  '/setup/initialize',
];

/**
 * Check if an endpoint is public (no auth required)
 */
const isPublicEndpoint = (url) => {
  return PUBLIC_ENDPOINTS.some(endpoint => url?.includes(endpoint));
};

/**
 * Request Interceptor
 * - Adds Authorization header if token exists
 * - Skips auth for public endpoints
 * - Prevents 401 spam by only adding token when available
 */
apiClient.interceptors.request.use(
  (config) => {
    // Skip auth for public endpoints
    if (isPublicEndpoint(config.url)) {
      return config;
    }

    // Only add auth header if token exists
    const token = localStorage.getItem('token');
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
 * Response Interceptor
 * - Handles 401 errors gracefully
 * - Only redirects to login if token existed (i.e., it expired)
 * - Prevents redirect loops
 * - Implements automatic retry with exponential backoff
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error;

    // Handle 401 Unauthorized
    if (response?.status === 401) {
      const hadToken = localStorage.getItem('token');

      // Only redirect if we had a token (meaning it expired)
      // Don't redirect if we never had a token (user not logged in yet)
      if (hadToken && !isPublicEndpoint(config.url)) {
        console.warn('Token expired or invalid, redirecting to login');
        localStorage.removeItem('token');

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

        console.warn(retryMessage, {
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
        console.error('Max retries reached for request:', {
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
 * Helper: Check if user is authenticated
 */
export const isAuthenticated = () => {
  return !!localStorage.getItem('token');
};

/**
 * Helper: Get current token
 */
export const getToken = () => {
  return localStorage.getItem('token');
};

/**
 * Helper: Set authentication token
 */
export const setToken = (token) => {
  if (token) {
    localStorage.setItem('token', token);
  } else {
    localStorage.removeItem('token');
  }
};

/**
 * Helper: Clear authentication
 */
export const clearAuth = () => {
  localStorage.removeItem('token');
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
