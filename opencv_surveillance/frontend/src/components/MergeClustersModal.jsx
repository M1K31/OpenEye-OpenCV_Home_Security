// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import clusteringService from '../services/clusteringService';
import './Modal.css';
import { describeApiError } from '../utils/apiError';

/**
 * Merge Clusters Modal
 * Interface for combining multiple face clusters
 */
const MergeClustersModal = ({ clusterIds, onClose, onSuccess }) => {
  const [clusters, setClusters] = useState([]);
  const [newName, setNewName] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingClusters, setLoadingClusters] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadClusters();
  }, [clusterIds]);

  const loadClusters = async () => {
    try {
      setLoadingClusters(true);
      const clusterPromises = clusterIds.map(id => 
        clusteringService.getCluster(id).catch(() => null)
      );
      const clustersData = await Promise.all(clusterPromises);
      setClusters(clustersData.filter(c => c !== null));
    } catch (err) {
      console.error('Error loading clusters:', err);
      setError('Failed to load cluster details');
    } finally {
      setLoadingClusters(false);
    }
  };

  const handleMerge = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await clusteringService.mergeClusters(
        clusterIds,
        newName.trim() || null
      );
      
      // Show success message
      alert(`✅ ${result.message}\n${result.faces_moved} faces merged`);
      
      // Call success callback
      onSuccess();
    } catch (err) {
      console.error('Error merging clusters:', err);
      setError(describeApiError(err, 'Failed to merge clusters. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const totalFaces = clusters.reduce((sum, c) => sum + (c?.face_count || 0), 0);

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onClose);


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-medium" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">🔗 Merge Face Clusters</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {loadingClusters ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading cluster details...</p>
            </div>
          ) : (
            <>
              <p className="modal-description">
                You are about to merge {clusters.length} clusters containing {totalFaces} faces total.
                All faces will be combined into one cluster.
              </p>

              {/* Clusters Preview */}
              <div className="merge-clusters-preview">
                {clusters.map((cluster, index) => (
                  <div key={cluster.id} className="merge-cluster-item">
                    <div className="merge-cluster-icon">
                      {cluster.is_identified ? '✓' : '?'}
                    </div>
                    <div className="merge-cluster-info">
                      <div className="merge-cluster-title">
                        {cluster.is_identified ? cluster.label : `Cluster #${cluster.id}`}
                      </div>
                      <div className="merge-cluster-meta">
                        {cluster.face_count} {cluster.face_count === 1 ? 'face' : 'faces'}
                      </div>
                    </div>
                    {index < clusters.length - 1 && (
                      <div className="merge-arrow">→</div>
                    )}
                  </div>
                ))}
              </div>

              {/* Optional Name Input */}
              <div className="form-group">
                <label htmlFor="merge-name">
                  Person Name (Optional)
                  <span className="label-hint">Leave empty to keep unidentified</span>
                </label>
                <input
                  type="text"
                  id="merge-name"
                  className="form-input"
                  placeholder="e.g., John Smith"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  disabled={loading}
                />
              </div>

              {error && (
                <div className="error-message">
                  ⚠️ {error}
                </div>
              )}

              <div className="warning-message">
                <span className="warning-icon">⚠️</span>
                <div>
                  <strong>Warning:</strong> This action cannot be undone.
                  The source clusters will be deleted and all faces will be moved to a single cluster.
                </div>
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button
            className="btn btn-outline"
            onClick={onClose}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            className="btn btn-primary"
            onClick={handleMerge}
            disabled={loading || loadingClusters}
          >
            {loading ? '⏳ Merging...' : '✓ Merge Clusters'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MergeClustersModal;
