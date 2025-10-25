/**
 * Notification Provider Service
 * Manages in-app configuration of notification channels (email, SMS, push, etc.)
 */

import apiClient from '../api/apiClient';

const notificationService = {
  /**
   * Get all available provider templates
   * @returns {Promise<{templates: Array}>}
   */
  async getTemplates() {
    const response = await apiClient.get('/notification-providers/templates');
    return response.data;
  },

  /**
   * List all notification providers for current user
   * @returns {Promise<{providers: Array, total: number}>}
   */
  async listProviders() {
    const response = await apiClient.get('/notification-providers/');
    return response.data;
  },

  /**
   * Get a specific notification provider
   * @param {number} providerId - Provider ID
   * @returns {Promise<Object>}
   */
  async getProvider(providerId) {
    const response = await apiClient.get(`/notification-providers/${providerId}`);
    return response.data;
  },

  /**
   * Create a new notification provider
   * @param {Object} providerData - Provider configuration
   * @param {string} providerData.provider_type - Type (email, sms, push, etc.)
   * @param {string} providerData.provider_name - User-friendly name
   * @param {boolean} providerData.enabled - Enable provider
   * @param {Object} providerData.config - Provider-specific configuration
   * @returns {Promise<Object>}
   */
  async createProvider(providerData) {
    const response = await apiClient.post('/notification-providers/', providerData);
    return response.data;
  },

  /**
   * Update an existing notification provider
   * @param {number} providerId - Provider ID
   * @param {Object} updates - Fields to update
   * @returns {Promise<Object>}
   */
  async updateProvider(providerId, updates) {
    const response = await apiClient.put(`/notification-providers/${providerId}`, updates);
    return response.data;
  },

  /**
   * Delete a notification provider
   * @param {number} providerId - Provider ID
   * @returns {Promise<Object>}
   */
  async deleteProvider(providerId) {
    const response = await apiClient.delete(`/notification-providers/${providerId}`);
    return response.data;
  },

  /**
   * Test a notification provider
   * @param {number} providerId - Provider ID
   * @param {Object} testData - Test configuration
   * @param {string} testData.recipient - Test recipient
   * @param {string} testData.subject - Test subject (optional)
   * @param {string} testData.message - Test message (optional)
   * @returns {Promise<{success: boolean, message: string, error?: string, delivery_time?: number}>}
   */
  async testProvider(providerId, testData) {
    const response = await apiClient.post(`/notification-providers/${providerId}/test`, testData);
    return response.data;
  },

  /**
   * Get provider icon/emoji by type
   * @param {string} providerType - Provider type
   * @returns {string} Emoji icon
   */
  getProviderIcon(providerType) {
    const icons = {
      email: '📧',
      sms: '📱',
      push: '🔔',
      telegram: '✈️',
      discord: '💬',
      webhook: '🔗'
    };
    return icons[providerType] || '🔔';
  },

  /**
   * Get provider display name
   * @param {string} providerType - Provider type
   * @returns {string} Display name
   */
  getProviderDisplayName(providerType) {
    const names = {
      email: 'Email (SMTP)',
      sms: 'SMS (Twilio)',
      push: 'Push Notifications (FCM)',
      telegram: 'Telegram Bot',
      discord: 'Discord Webhook',
      webhook: 'Custom Webhook'
    };
    return names[providerType] || providerType;
  },

  /**
   * Format test status for display
   * @param {string} status - Test status
   * @returns {Object} {text: string, color: string, icon: string}
   */
  formatTestStatus(status) {
    const formats = {
      success: { text: 'Working', color: '#28a745', icon: '✅' },
      failed: { text: 'Failed', color: '#dc3545', icon: '❌' },
      not_tested: { text: 'Not Tested', color: '#6c757d', icon: '⏺️' }
    };
    return formats[status] || formats.not_tested;
  }
};

export default notificationService;
