// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Face Clustering API Service
 * Provides methods for managing face clusters
 */

import apiClient from '../api/apiClient';

const clusteringService = {
  /**
   * Trigger face clustering algorithm
   * @param {Object} params - Clustering parameters
   * @param {number} params.eps - DBSCAN distance threshold (default: 0.5)
   * @param {number} params.min_samples - Minimum faces per cluster (default: 2)
   * @param {boolean} params.recalculate - Force recalculation (default: false)
   * @returns {Promise<Object>} Clustering results
   */
  async clusterFaces(params = {}) {
    const response = await apiClient.post('/clusters/cluster', {
      eps: params.eps || 0.5,
      min_samples: params.min_samples || 2,
      recalculate: params.recalculate || false,
    });
    return response.data;
  },

  /**
   * Get all face clusters (paginated)
   * @param {number} page - Page number, 1-indexed (default: 1)
   * @param {number} pageSize - Items per page (default: 50, max: 1000)
   * @returns {Promise<Object>} List of clusters
   */
  async getClusters(page = 1, pageSize = 50) {
    const response = await apiClient.get('/clusters/', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * Get specific cluster by ID
   * @param {number} clusterId - Cluster ID
   * @returns {Promise<Object>} Cluster details
   */
  async getCluster(clusterId) {
    const response = await apiClient.get(`/clusters/${clusterId}`);
    return response.data;
  },

  /**
   * Get faces in a specific cluster (paginated)
   * @param {number} clusterId - Cluster ID
   * @param {number} skip - Records to skip (default: 0)
   * @param {number} limit - Max records (default: 50)
   * @returns {Promise<Object>} List of faces in cluster
   */
  async getClusterFaces(clusterId, skip = 0, limit = 50) {
    const response = await apiClient.get(`/clusters/${clusterId}/faces`, {
      params: { skip, limit },
    });
    return response.data;
  },

  /**
   * Assign a name to a cluster (identify the person)
   * @param {number} clusterId - Cluster ID
   * @param {string} personName - Person's name
   * @returns {Promise<Object>} Assignment result
   */
  async assignNameToCluster(clusterId, personName) {
    const response = await apiClient.post(`/clusters/${clusterId}/assign-name`, {
      person_name: personName,
    });
    return response.data;
  },

  /**
   * Merge multiple clusters into one
   * @param {number[]} clusterIds - Array of cluster IDs to merge
   * @param {string|null} newName - Optional name for merged cluster
   * @returns {Promise<Object>} Merge result
   */
  async mergeClusters(clusterIds, newName = null) {
    const response = await apiClient.post('/clusters/merge', {
      cluster_ids: clusterIds,
      new_name: newName,
    });
    return response.data;
  },

  /**
   * Delete a cluster
   * @param {number} clusterId - Cluster ID
   * @param {boolean} reassignUnknown - Set faces back to "Unknown" (default: true)
   * @param {boolean} deleteFaces - Permanently delete face detection events (default: false)
   * @returns {Promise<Object>} Deletion result
   */
  async deleteCluster(clusterId, reassignUnknown = true, deleteFaces = false) {
    const response = await apiClient.delete(`/clusters/${clusterId}`, {
      data: {
        reassign_unknown: reassignUnknown,
        delete_faces: deleteFaces
      },
    });
    return response.data;
  },

  /**
   * Get clustering statistics
   * @returns {Promise<Object>} System-wide clustering stats
   */
  async getStatistics() {
    const response = await apiClient.get('/clusters/statistics/summary');
    return response.data;
  },

  /**
   * Get clustering scheduler status
   * @returns {Promise<Object>} Scheduler status and statistics
   */
  async getSchedulerStatus() {
    const response = await apiClient.get('/clusters/scheduler/status');
    return response.data;
  },

  /**
   * Manually trigger clustering (bypasses interval check)
   * @returns {Promise<Object>} Clustering results
   */
  async triggerManualClustering() {
    const response = await apiClient.post('/clusters/scheduler/trigger');
    return response.data;
  },

  /**
   * Update clustering scheduler settings
   * @param {Object} settings - Scheduler settings
   * @param {boolean} settings.auto_enabled - Enable/disable auto-clustering
   * @param {number} settings.interval_minutes - Minutes between clustering runs
   * @param {number} settings.min_faces_threshold - Minimum faces to trigger clustering
   * @returns {Promise<Object>} Updated settings
   */
  async updateSchedulerSettings(settings) {
    const response = await apiClient.post('/clusters/scheduler/settings', null, {
      params: settings,
    });
    return response.data;
  },

  // =====================================================
  // Face Review Workflow Methods (v3.11.5)
  // =====================================================

  /**
   * Review a single face's association with a cluster
   * @param {number} clusterId - Current cluster ID
   * @param {number} faceId - Face detection event ID
   * @param {string} action - 'confirm' or 'reject'
   * @param {string|null} reassignTo - For rejections: person name to reassign to
   * @returns {Promise<Object>} Review result
   */
  async reviewFace(clusterId, faceId, action, reassignTo = null) {
    const response = await apiClient.post(`/clusters/${clusterId}/faces/${faceId}/review`, {
      action,
      reassign_to: reassignTo,
    });
    return response.data;
  },

  /**
   * Bulk review multiple faces in a cluster
   * @param {number} clusterId - Cluster ID
   * @param {number[]} faceIds - Array of face IDs to review
   * @param {string} action - 'confirm' or 'reject'
   * @param {string|null} reassignTo - For rejections: person name to reassign all to
   * @returns {Promise<Object>} Bulk review result
   */
  async bulkReviewFaces(clusterId, faceIds, action, reassignTo = null) {
    const response = await apiClient.post(`/clusters/${clusterId}/faces/bulk-review`, {
      face_ids: faceIds,
      action,
      reassign_to: reassignTo,
    });
    return response.data;
  },

  /**
   * Clean up clusters with 0 faces
   * @returns {Promise<Object>} Cleanup result with deleted count
   */
  async cleanupEmptyClusters() {
    const response = await apiClient.delete('/clusters/cleanup-empty');
    return response.data;
  },
};

export default clusteringService;
