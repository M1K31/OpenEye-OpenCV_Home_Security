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
   * @param {number} skip - Records to skip (default: 0)
   * @param {number} limit - Max records (default: 100)
   * @returns {Promise<Object>} List of clusters
   */
  async getClusters(skip = 0, limit = 100) {
    const response = await apiClient.get('/clusters/', {
      params: { skip, limit },
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
   * @returns {Promise<Object>} Deletion result
   */
  async deleteCluster(clusterId, reassignUnknown = true) {
    const response = await apiClient.delete(`/clusters/${clusterId}`, {
      data: { reassign_unknown: reassignUnknown },
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
};

export default clusteringService;
