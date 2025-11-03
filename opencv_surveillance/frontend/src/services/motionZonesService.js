/**
 * Motion Zones API Service
 * Handles all API calls for motion detection zone management
 */

import apiClient from '../api/apiClient';

const motionZonesService = {
  /**
   * Get all zones for a camera
   * @param {string} cameraId - Camera identifier
   * @param {boolean} includeInactive - Include inactive zones
   * @returns {Promise} Response with zones array
   */
  async getZones(cameraId, includeInactive = false) {
    const response = await apiClient.get(`/cameras/${cameraId}/zones`, {
      params: { include_inactive: includeInactive }
    });
    return response.data;
  },

  /**
   * Create a new motion zone
   * @param {string} cameraId - Camera identifier
   * @param {object} zoneData - Zone configuration
   * @returns {Promise} Created zone
   */
  async createZone(cameraId, zoneData) {
    const response = await apiClient.post(`/cameras/${cameraId}/zones`, {
      ...zoneData,
      camera_id: cameraId
    });
    return response.data;
  },

  /**
   * Get a specific zone
   * @param {string} cameraId - Camera identifier
   * @param {number} zoneId - Zone identifier
   * @returns {Promise} Zone data
   */
  async getZone(cameraId, zoneId) {
    const response = await apiClient.get(`/cameras/${cameraId}/zones/${zoneId}`);
    return response.data;
  },

  /**
   * Update an existing zone
   * @param {string} cameraId - Camera identifier
   * @param {number} zoneId - Zone identifier
   * @param {object} updates - Fields to update
   * @returns {Promise} Updated zone
   */
  async updateZone(cameraId, zoneId, updates) {
    const response = await apiClient.put(`/cameras/${cameraId}/zones/${zoneId}`, updates);
    return response.data;
  },

  /**
   * Delete a zone
   * @param {string} cameraId - Camera identifier
   * @param {number} zoneId - Zone identifier
   * @returns {Promise} Success/failure
   */
  async deleteZone(cameraId, zoneId) {
    await apiClient.delete(`/cameras/${cameraId}/zones/${zoneId}`);
    return true;
  },

  /**
   * Toggle zone active status
   * @param {string} cameraId - Camera identifier
   * @param {number} zoneId - Zone identifier
   * @returns {Promise} Updated zone
   */
  async toggleZone(cameraId, zoneId) {
    const response = await apiClient.post(`/cameras/${cameraId}/zones/${zoneId}/toggle`);
    return response.data;
  }
};

export default motionZonesService;
