// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Two-Factor Authentication Service
 * Handles all 2FA-related API calls
 */

import apiClient from '../api/apiClient';

const twoFactorService = {
  /**
   * Get current user's 2FA status
   * @returns {Promise} Status object with enabled flag and enrollment date
   */
  async getStatus() {
    const response = await apiClient.get('/auth/2fa/status');
    return response.data;
  },

  /**
   * Enable 2FA for current user
   * Generates TOTP secret, QR code, and backup codes
   * @returns {Promise} Object with secret, qr_code, and backup_codes
   */
  async enable() {
    const response = await apiClient.post('/auth/2fa/enable');
    return response.data;
  },

  /**
   * Verify TOTP token and activate 2FA
   * @param {string} token - 6-digit TOTP token from authenticator app
   * @returns {Promise} Verification result
   */
  async verify(token) {
    const response = await apiClient.post('/auth/2fa/verify', { token });
    return response.data;
  },

  /**
   * Disable 2FA for current user
   * @param {string} password - User's password for confirmation
   * @returns {Promise} Disable result
   */
  async disable(password) {
    const response = await apiClient.post('/auth/2fa/disable', { password });
    return response.data;
  },

  /**
   * Login with 2FA
   * @param {string} username - Username
   * @param {string} password - Password
   * @param {string} totpToken - 6-digit TOTP token (optional)
   * @param {string} backupCode - Backup recovery code (optional, alternative to TOTP)
   * @returns {Promise} Login response with access token or requires_2fa flag
   */
  async login(username, password, totpToken = null, backupCode = null) {
    try {
      // If no 2FA token provided, try standard login first
      if (!totpToken && !backupCode) {
        const payload = new URLSearchParams({
          username,
          password,
        });

        const response = await apiClient.post('/token', payload, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        });

        return response.data;
      } else {
        // User has provided 2FA token - use dedicated 2FA endpoint
        const response = await apiClient.post('/auth/login-2fa', {
          username,
          password,
          totp_token: totpToken,
          backup_code: backupCode,
        });

        return response.data;
      }
    } catch (error) {
      // Check if 403 with X-Requires-2FA header
      if (error.response?.status === 403 && error.response?.headers['x-requires-2fa']) {
        return { requires_2fa: true };
      }
      throw error;
    }
  },
};

export default twoFactorService;
