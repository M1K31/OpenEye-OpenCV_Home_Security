// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Authentication Service
 * Handles token management, refresh, and expiration detection
 */

import axios from 'axios';

class AuthService {
  constructor() {
    this.refreshPromise = null;
    this.setupInterceptors();
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

    // Response interceptor - Handle 401 errors
    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // If 401 and not already retried, attempt token refresh
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Check if this is a token expiration (not invalid credentials)
          if (this.isTokenExpired() || error.response.data?.detail?.includes('expired')) {
            try {
              // Show token refresh UI
              const newToken = await this.handleTokenExpiration();
              
              if (newToken) {
                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${newToken}`;
                return axios(originalRequest);
              }
            } catch (refreshError) {
              // Token refresh failed, redirect to login
              this.handleAuthFailure();
              return Promise.reject(refreshError);
            }
          } else {
            // Invalid credentials, redirect to login
            this.handleAuthFailure();
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Get current token from localStorage
   */
  getToken() {
    return localStorage.getItem('token');
  }

  /**
   * Set token in localStorage
   */
  setToken(token) {
    if (token) {
      localStorage.setItem('token', token);
      this.storeTokenTimestamp();
    } else {
      localStorage.removeItem('token');
      localStorage.removeItem('token_timestamp');
    }
  }

  /**
   * Store timestamp when token was created/refreshed
   */
  storeTokenTimestamp() {
    localStorage.setItem('token_timestamp', Date.now().toString());
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
      console.error('Error decoding token:', error);
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
   * Handle token expiration by showing refresh modal
   */
  async handleTokenExpiration() {
    // Prevent multiple simultaneous refresh attempts
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = new Promise((resolve, reject) => {
      // Create modal for token refresh
      const modal = this.createTokenRefreshModal(resolve, reject);
      document.body.appendChild(modal);
    });

    try {
      const newToken = await this.refreshPromise;
      this.refreshPromise = null;
      return newToken;
    } catch (error) {
      this.refreshPromise = null;
      throw error;
    }
  }

  /**
   * Create token refresh modal
   */
  createTokenRefreshModal(resolve, reject) {
    const modal = document.createElement('div');
    modal.id = 'token-refresh-modal';
    modal.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.8);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    `;

    const content = document.createElement('div');
    content.style.cssText = `
      background: #1a1f2e;
      padding: 30px;
      border-radius: 10px;
      max-width: 500px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
      border: 1px solid rgba(0, 255, 255, 0.3);
    `;

    content.innerHTML = `
      <h2 style="margin-top: 0; color: #00ffff; text-shadow: 0 0 10px rgba(0, 255, 255, 0.5);">Session Expired</h2>
      <p style="color: #b8c5d6; margin-bottom: 20px;">
        Your session has expired. Please log in again to continue.
      </p>
      <div style="margin-bottom: 15px;">
        <label style="display: block; margin-bottom: 5px; color: #00ffff; font-weight: bold;">
          Username:
        </label>
        <input 
          type="text" 
          id="refresh-username" 
          style="width: 100%; padding: 10px; border: 1px solid rgba(0, 255, 255, 0.3); border-radius: 5px; box-sizing: border-box; background: #0d1117; color: #e6edf3;"
          placeholder="Enter username"
        />
      </div>
      <div style="margin-bottom: 20px;">
        <label style="display: block; margin-bottom: 5px; color: #00ffff; font-weight: bold;">
          Password:
        </label>
        <input 
          type="password" 
          id="refresh-password" 
          style="width: 100%; padding: 10px; border: 1px solid rgba(0, 255, 255, 0.3); border-radius: 5px; box-sizing: border-box; background: #0d1117; color: #e6edf3;"
          placeholder="Enter password"
        />
      </div>
      <div id="refresh-error" style="color: #ff4444; margin-bottom: 15px; display: none;"></div>
      <div style="display: flex; gap: 10px; justify-content: flex-end;">
        <button 
          id="refresh-cancel-btn"
          style="padding: 10px 20px; border: 1px solid rgba(0, 255, 255, 0.3); background: transparent; color: #00ffff; border-radius: 5px; cursor: pointer; transition: all 0.3s;"
          onmouseover="this.style.background='rgba(0, 255, 255, 0.1)'"
          onmouseout="this.style.background='transparent'"
        >
          Cancel
        </button>
        <button 
          id="refresh-login-btn"
          style="padding: 10px 20px; border: none; background: linear-gradient(135deg, #00ffff, #0088ff); color: #000; font-weight: bold; border-radius: 5px; cursor: pointer; transition: all 0.3s;"
          onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 5px 15px rgba(0, 255, 255, 0.4)'"
          onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'"
        >
          Login
        </button>
      </div>
    `;

    modal.appendChild(content);

    const usernameInput = content.querySelector('#refresh-username');
    const passwordInput = content.querySelector('#refresh-password');
    const errorDiv = content.querySelector('#refresh-error');
    const cancelBtn = content.querySelector('#refresh-cancel-btn');
    const loginBtn = content.querySelector('#refresh-login-btn');

    // Auto-fill username if available
    const savedUsername = localStorage.getItem('username');
    if (savedUsername) {
      usernameInput.value = savedUsername;
      passwordInput.focus();
    } else {
      usernameInput.focus();
    }

    // Handle login
    const handleLogin = async () => {
      const username = usernameInput.value.trim();
      const password = passwordInput.value;

      if (!username || !password) {
        errorDiv.textContent = 'Please enter both username and password';
        errorDiv.style.display = 'block';
        return;
      }

      loginBtn.disabled = true;
      loginBtn.textContent = 'Logging in...';
      errorDiv.style.display = 'none';

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

        if (response.data.access_token) {
          const newToken = response.data.access_token;
          this.setToken(newToken);
          localStorage.setItem('username', username);
          
          // Remove modal
          document.body.removeChild(modal);
          
          // Resolve with new token
          resolve(newToken);
        } else {
          throw new Error('No token received');
        }
      } catch (error) {
        console.error('Token refresh failed:', error);
        errorDiv.textContent = error.response?.data?.detail || 'Login failed. Please try again.';
        errorDiv.style.display = 'block';
        loginBtn.disabled = false;
        loginBtn.textContent = 'Login';
      }
    };

    // Handle cancel
    const handleCancel = () => {
      document.body.removeChild(modal);
      reject(new Error('Token refresh cancelled'));
      this.handleAuthFailure();
    };

    loginBtn.addEventListener('click', handleLogin);
    cancelBtn.addEventListener('click', handleCancel);

    // Handle Enter key
    passwordInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        handleLogin();
      }
    });

    return modal;
  }

  /**
   * Handle authentication failure
   */
  handleAuthFailure() {
    this.setToken(null);
    localStorage.removeItem('username');
    window.location.href = '/login';
  }

  /**
   * Login with credentials
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

      if (response.data.access_token) {
        this.setToken(response.data.access_token);
        localStorage.setItem('username', username);
        return response.data;
      } else {
        throw new Error('No token received');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }

  /**
   * Logout
   */
  logout() {
    this.setToken(null);
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
