// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Face History API Service
 * Provides methods for viewing and managing face detection history
 */

import apiClient from '../api/apiClient';

const faceHistoryService = {
  /**
   * Get face detection history with optional filters
   * @param {Object} params - Query parameters
   * @param {string} params.camera_id - Filter by camera ID
   * @param {string} params.person_name - Filter by person name
   * @param {number} params.hours - Number of hours to look back (default: 24)
   * @param {number} params.page - Page number (default: 1)
   * @param {number} params.page_size - Items per page (default: 50)
   * @returns {Promise<Object>} Paginated detection history
   */
  async getDetectionHistory(params = {}) {
    const response = await apiClient.get('/faces/history', { params });
    return response.data;
  },

  /**
   * Get detection history for a specific person
   * @param {string} personName - Name of the person
   * @param {number} limit - Maximum results (default: 100)
   * @returns {Promise<Array>} List of face detection events
   */
  async getPersonHistory(personName, limit = 100) {
    const response = await apiClient.get(`/faces/history/person/${encodeURIComponent(personName)}`, {
      params: { limit },
    });
    return response.data;
  },

  /**
   * Reassign a face detection to a different person
   * @param {number} faceId - Face detection event ID
   * @param {string} newPersonName - New person name to assign
   * @returns {Promise<Object>} Reassignment result
   */
  async reassignFace(faceId, newPersonName) {
    const response = await apiClient.post(`/faces/history/${faceId}/reassign`, {
      new_person_name: newPersonName,
    });
    return response.data;
  },

  /**
   * Bulk reassign multiple face detections
   * @param {number[]} faceIds - Array of face detection event IDs
   * @param {string} newPersonName - New person name to assign
   * @returns {Promise<Object>} Bulk reassignment result
   */
  async bulkReassignFaces(faceIds, newPersonName) {
    const response = await apiClient.post('/faces/history/bulk-reassign', {
      face_ids: faceIds,
      new_person_name: newPersonName,
    });
    return response.data;
  },

  /**
   * Get face detection statistics
   * @param {Object} params - Query parameters
   * @param {string} params.camera_id - Filter by camera ID
   * @param {number} params.days - Number of days (default: 7)
   * @returns {Promise<Object>} Statistics
   */
  async getStatistics(params = {}) {
    const response = await apiClient.get('/faces/history/statistics', { params });
    return response.data;
  },

  /**
   * Get detection timeline grouped by hour
   * @param {Object} params - Query parameters
   * @param {string} params.camera_id - Filter by camera ID
   * @param {number} params.hours - Number of hours (default: 24)
   * @returns {Promise<Object>} Timeline data
   */
  async getTimeline(params = {}) {
    const response = await apiClient.get('/faces/history/timeline', { params });
    return response.data;
  },
};

export default faceHistoryService;
