// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Authentication Service (v3.8.0)
 * Handles token management with automatic refresh token rotation
 *
 * Features:
 * - Automatic token refresh 5 minutes before expiry
 * - Refresh token rotation for security
 * - Transparent 401 handling with token refresh
 * - Logout from single device or all devices
 */

import axios from 'axios';
import { logger } from '../utils/logger';

class AuthService {
  constructor() {
    this.refreshPromise = null;
    this.refreshTimer = null;
    this.tokenRefreshCallbacks = []; // Callbacks to notify on token refresh
    this.setupInterceptors();

    // Start refresh timer if token exists
    if (this.getToken()) {
      this.startTokenRefreshTimer();
      // Re-issue the media cookie for a session that is already signed in.
      // setToken() (which writes the cookie) only runs on login/refresh/logout, so
      // without this an existing session — including every user upgrading to the
      // build that started requiring auth on media — would hold a valid token in
      // localStorage but no cookie, and every <img>/<video> request would 401 until
      // they happened to re-login or the token refreshed.
      this.setMediaCookie(this.getToken());
    }
  }

  /**
   * Setup axios interceptors for automatic token refresh
   */
  setupInterceptors() {
    // Request interceptor - Add token to requests
    axios.interceptors.request.use(
      (config) => {
        const token = this.getToken();
        if (token && !config.headers.Authorization) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor - Handle 401 errors with automatic refresh
    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // If 401 and not already retried, attempt automatic token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Skip refresh for token refresh endpoint itself to avoid infinite loop
          if (originalRequest.url && originalRequest.url.includes('/token/refresh')) {
            this.handleAuthFailure();
            return Promise.reject(error);
          }

          try {
            // Attempt automatic token refresh using refresh token
            const newToken = await this.refreshToken();

            if (newToken) {
              // Retry original request with new token
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return axios(originalRequest);
            }
          } catch (refreshError) {
            // Token refresh failed, redirect to login
            logger.error('Token refresh failed:', refreshError);
            this.handleAuthFailure();
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Get current access token from localStorage
   */
  getToken() {
    return localStorage.getItem('access_token');
  }

  /**
   * Set access token in localStorage
   */
  setToken(token) {
    if (token) {
      localStorage.setItem('access_token', token);
      this.storeTokenTimestamp();
      this.setMediaCookie(token);
    } else {
      localStorage.removeItem('access_token');
      localStorage.removeItem('token_timestamp');
      localStorage.removeItem('token_expires_at');
      this.setMediaCookie(null);
    }
  }

  /**
   * Mirror the access token into a cookie so the browser can authenticate MEDIA.
   *
   * Live camera feeds are <img src="/api/cameras/../stream"> and recordings are
   * <video src="/api/recordings/../download">. A plain tag cannot attach an
   * Authorization header, so those endpoints accept the same JWT from this cookie
   * (see backend get_current_user_media). Without it, securing media would simply
   * break playback.
   *
   * SameSite=Strict keeps it from riding along on cross-site requests (CSRF), and
   * the cookie is cleared on logout together with the stored token.
   */
  setMediaCookie(token) {
    try {
      const secure = window.location.protocol === 'https:' ? '; Secure' : '';
      if (token) {
        document.cookie = `access_token=${token}; Path=/; SameSite=Strict${secure}`;
      } else {
        document.cookie = `access_token=; Path=/; Max-Age=0; SameSite=Strict${secure}`;
      }
    } catch (e) {
      // Non-fatal: JSON APIs still work via the Authorization header.
      logger.warn('Could not set media auth cookie:', e);
    }
  }

  /**
   * Get refresh token from localStorage
   */
  getRefreshToken() {
    return localStorage.getItem('refresh_token');
  }

  /**
   * Set refresh token in localStorage
   */
  setRefreshToken(token) {
    if (token) {
      localStorage.setItem('refresh_token', token);
    } else {
      localStorage.removeItem('refresh_token');
    }
  }

  /**
   * Store timestamp when token was created/refreshed
   */
  storeTokenTimestamp() {
    localStorage.setItem('token_timestamp', Date.now().toString());
  }

  /**
   * Store token expiration time
   */
  storeTokenExpiration(expiresIn) {
    // expiresIn is in seconds, convert to timestamp
    const expiresAt = Date.now() + (expiresIn * 1000);
    localStorage.setItem('token_expires_at', expiresAt.toString());
  }

  /**
   * Check if token is expired based on JWT exp claim
   */
  isTokenExpired() {
    const token = this.getToken();
    if (!token) return true;

    try {
      // Decode JWT token (payload is the second part)
      const payload = JSON.parse(atob(token.split('.')[1]));
      const expirationTime = payload.exp * 1000; // Convert to milliseconds
      const currentTime = Date.now();

      // Token is expired if current time is past expiration
      return currentTime >= expirationTime;
    } catch (error) {
      logger.error('Error decoding token:', error);
      return true; // Assume expired if can't decode
    }
  }

  /**
   * Get time remaining until token expires (in seconds)
   */
  getTokenTimeRemaining() {
    const token = this.getToken();
    if (!token) return 0;

    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      const expirationTime = payload.exp * 1000;
      const currentTime = Date.now();
      const remaining = Math.max(0, Math.floor((expirationTime - currentTime) / 1000));
      return remaining;
    } catch (error) {
      return 0;
    }
  }

  /**
   * Refresh access token using refresh token
   *
   * v3.8.0: Uses refresh token rotation for security
   * Each refresh generates a new refresh token and revokes the old one
   */
  async refreshToken() {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    const refreshToken = this.getRefreshToken();

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    this.refreshPromise = (async () => {
      try {
        const response = await axios.post('/api/token/refresh', {
          refresh_token: refreshToken
        });

        if (response.data.access_token && response.data.refresh_token) {
          // Store new tokens
          const newToken = response.data.access_token;
          this.setToken(newToken);
          this.setRefreshToken(response.data.refresh_token);
          this.storeTokenExpiration(response.data.expires_in);

          // Restart refresh timer with new expiration
          this.startTokenRefreshTimer();

          // Notify listeners of token refresh (e.g., WebSocket reconnection)
          this.notifyTokenRefresh(newToken);

          return newToken;
        } else {
          throw new Error('Invalid response from token refresh');
        }
      } catch (error) {
        logger.error('Token refresh failed:', error);
        // Clear tokens on refresh failure
        this.setToken(null);
        this.setRefreshToken(null);
        throw error;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  /**
   * Subscribe to token refresh events
   *
   * Use this to get notified when the access token is refreshed,
   * so you can update WebSocket connections or other long-lived resources.
   *
   * @param {Function} callback - Called with new token as parameter
   * @returns {Function} Unsubscribe function
   *
   * @example
   * const unsubscribe = authService.onTokenRefresh((newToken) => {
   *   logger.log('Token refreshed, reconnecting WebSocket...');
   *   wsService.disconnect();
   *   wsService.connect(newToken);
   * });
   */
  onTokenRefresh(callback) {
    this.tokenRefreshCallbacks.push(callback);

    // Return unsubscribe function
    return () => {
      this.tokenRefreshCallbacks = this.tokenRefreshCallbacks.filter(cb => cb !== callback);
    };
  }

  /**
   * Notify all subscribers that token has been refreshed
   *
   * @private
   * @param {string} newToken - The new access token
   */
  notifyTokenRefresh(newToken) {
    logger.log(`Notifying ${this.tokenRefreshCallbacks.length} token refresh listeners`);

    this.tokenRefreshCallbacks.forEach(callback => {
      try {
        callback(newToken);
      } catch (error) {
        logger.error('Error in token refresh callback:', error);
      }
    });
  }

  /**
   * Start automatic token refresh timer
   *
   * Refreshes token 5 minutes before it expires
   */
  startTokenRefreshTimer() {
    // Clear existing timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    const expiresAt = localStorage.getItem('token_expires_at');

    if (!expiresAt) {
      return;
    }

    const expirationTime = parseInt(expiresAt);
    const currentTime = Date.now();
    const timeUntilExpiry = expirationTime - currentTime;

    // Refresh 5 minutes (300 seconds) before expiry
    const refreshTime = timeUntilExpiry - (5 * 60 * 1000);

    if (refreshTime > 0) {
      logger.log(`Token will auto-refresh in ${Math.floor(refreshTime / 1000)} seconds`);

      this.refreshTimer = setTimeout(async () => {
        try {
          logger.log('Auto-refreshing token...');
          await this.refreshToken();
          logger.log('Token auto-refreshed successfully');
        } catch (error) {
          logger.error('Auto token refresh failed:', error);
          this.handleAuthFailure();
        }
      }, refreshTime);
    } else if (timeUntilExpiry > 0) {
      // Token expires soon (less than 5 minutes), refresh immediately
      logger.log('Token expires soon, refreshing immediately...');
      this.refreshToken().catch((error) => {
        logger.error('Immediate token refresh failed:', error);
        this.handleAuthFailure();
      });
    }
  }


  /**
   * Handle authentication failure
   */
  handleAuthFailure() {
    // Clear refresh timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    // Clear all tokens
    this.setToken(null);
    this.setRefreshToken(null);
    localStorage.removeItem('username');

    // Redirect to login
    window.location.href = '/login';
  }

  /**
   * Login with credentials (v3.8.0)
   *
   * Now stores both access token and refresh token
   */
  async login(username, password) {
    try {
      // Use URLSearchParams for OAuth2 password flow (application/x-www-form-urlencoded)
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);

      const response = await axios.post('/api/token', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      });

      if (response.data.access_token && response.data.refresh_token) {
        // Store both tokens
        this.setToken(response.data.access_token);
        this.setRefreshToken(response.data.refresh_token);
        this.storeTokenExpiration(response.data.expires_in);
        localStorage.setItem('username', username);

        // Start automatic refresh timer
        this.startTokenRefreshTimer();

        return response.data;
      } else {
        throw new Error('No tokens received');
      }
    } catch (error) {
      logger.error('Login failed:', error);
      throw error;
    }
  }

  /**
   * Logout (v3.8.0)
   *
   * Revokes refresh token on server before clearing local storage
   */
  async logout() {
    const refreshToken = this.getRefreshToken();

    // Stop refresh timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    // Revoke refresh token on server if available
    if (refreshToken) {
      try {
        await axios.post('/api/token/revoke', {
          refresh_token: refreshToken
        });
      } catch (error) {
        logger.error('Token revocation failed:', error);
        // Continue with local logout even if server revocation fails
      }
    }

    // Clear all local tokens
    this.setToken(null);
    this.setRefreshToken(null);
    localStorage.removeItem('username');
  }

  /**
   * Logout from all devices (v3.8.0)
   *
   * Revokes all refresh tokens for the current user
   */
  async logoutAll() {
    // Stop refresh timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    try {
      await axios.post('/api/token/revoke-all');
    } catch (error) {
      logger.error('Revoke all tokens failed:', error);
      // Continue with local logout even if server revocation fails
    }

    // Clear all local tokens
    this.setToken(null);
    this.setRefreshToken(null);
    localStorage.removeItem('username');
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated() {
    const token = this.getToken();
    return token && !this.isTokenExpired();
  }
}

// Export singleton instance
export default new AuthService();
