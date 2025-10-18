// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import clusteringService from '../services/clusteringService';
import './Modal.css';

/**
 * Cluster Detail Modal
 * Shows all faces in a cluster with pagination
 */
const ClusterDetailModal = ({ clusterId, onClose, onAssignName }) => {
  const [cluster, setCluster] = useState(null);
  const [faces, setFaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const ITEMS_PER_PAGE = 12;

  useEffect(() => {
    loadClusterData();
  }, [clusterId]);

  const loadClusterData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [clusterData, facesData] = await Promise.all([
        clusteringService.getCluster(clusterId),
        clusteringService.getClusterFaces(clusterId, 0, ITEMS_PER_PAGE),
      ]);
      
      setCluster(clusterData);
      setFaces(facesData.faces || []);
      setHasMore((facesData.faces?.length || 0) >= ITEMS_PER_PAGE);
      setPage(0);
    } catch (err) {
      console.error('Error loading cluster:', err);
      setError('Failed to load cluster details');
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (!hasMore || loading) return;
    
    try {
      setLoading(true);
      const skip = (page + 1) * ITEMS_PER_PAGE;
      const data = await clusteringService.getClusterFaces(clusterId, skip, ITEMS_PER_PAGE);
      
      setFaces(prev => [...prev, ...(data.faces || [])]);
      setHasMore((data.faces?.length || 0) >= ITEMS_PER_PAGE);
      setPage(prev => prev + 1);
    } catch (err) {
      console.error('Error loading more faces:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getImageUrl = (snapshotPath) => {
    if (!snapshotPath) return '/placeholder-face.png';
    return snapshotPath.startsWith('http')
      ? snapshotPath
      : `/api${snapshotPath}`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            {cluster?.is_identified ? (
              <>✓ {cluster.label}</>
            ) : (
              <>Cluster #{clusterId}</>
            )}
          </h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {error ? (
            <div className="error-state">
              <p>⚠️ {error}</p>
              <button className="btn btn-primary" onClick={loadClusterData}>
                Try Again
              </button>
            </div>
          ) : loading && faces.length === 0 ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading faces...</p>
            </div>
          ) : (
            <>
              {/* Cluster Info */}
              {cluster && (
                <div className="cluster-detail-info">
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="info-label">Total Faces:</span>
                      <span className="info-value">{cluster.face_count}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Avg Confidence:</span>
                      <span className="info-value">
                        {cluster.avg_confidence ? `${(cluster.avg_confidence * 100).toFixed(1)}%` : 'N/A'}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Last Seen:</span>
                      <span className="info-value">{formatDate(cluster.last_seen_at)}</span>
                    </div>
                    <div className="info-item">
                      <span className="info-label">Status:</span>
                      <span className={`info-value ${cluster.is_identified ? 'identified' : 'unidentified'}`}>
                        {cluster.is_identified ? '✓ Identified' : '? Unidentified'}
                      </span>
                    </div>
                  </div>
                  
                  {!cluster.is_identified && (
                    <button
                      className="btn btn-primary"
                      onClick={onAssignName}
                    >
                      👤 Assign Name
                    </button>
                  )}
                </div>
              )}

              {/* Faces Grid */}
              <div className="faces-grid">
                {faces.map((face, index) => (
                  <div key={`${face.id}-${index}`} className="face-item">
                    <div className="face-image-container">
                      <img
                        src={getImageUrl(face.snapshot_path)}
                        alt={`Face detection ${face.id}`}
                        onError={(e) => {
                          e.target.src = '/placeholder-face.png';
                        }}
                      />
                      <div className="face-confidence">
                        {(face.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="face-meta">
                      <div className="face-camera">📷 {face.camera_id}</div>
                      <div className="face-time">{formatDate(face.detected_at)}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Load More */}
              {hasMore && (
                <div className="load-more">
                  <button
                    className="btn btn-outline"
                    onClick={loadMore}
                    disabled={loading}
                  >
                    {loading ? 'Loading...' : 'Load More Faces'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClusterDetailModal;
