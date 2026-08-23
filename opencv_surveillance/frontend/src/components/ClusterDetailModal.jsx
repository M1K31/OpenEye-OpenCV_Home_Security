// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { activateOnKey } from '../utils/a11y';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import { logger } from '../utils/logger';
import clusteringService from '../services/clusteringService';
import apiClient from '../api/apiClient';
import './Modal.css';
import './ClusterDetailModal.css';

/**
 * Cluster Detail Modal
 * Shows all faces in a cluster with pagination and review workflow
 */
const ClusterDetailModal = ({ clusterId, onClose, onAssignName, onClusterUpdated }) => {
  const [cluster, setCluster] = useState(null);
  const [faces, setFaces] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const ITEMS_PER_PAGE = 12;

  // Face review state
  const [reviewMode, setReviewMode] = useState(false);
  const [selectedFaces, setSelectedFaces] = useState(new Set());
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewMessage, setReviewMessage] = useState(null);
  const [showReassignInput, setShowReassignInput] = useState(false);
  const [reassignName, setReassignName] = useState('');
  const [reassignMode, setReassignMode] = useState('existing'); // 'existing' or 'new'
  const [existingPeople, setExistingPeople] = useState([]);

  useEffect(() => {
    loadClusterData();
    loadExistingPeople();
  }, [clusterId]);

  // Load existing people for reassignment dropdown
  const loadExistingPeople = async () => {
    try {
      const response = await apiClient.get('/faces/people');
      setExistingPeople(response.data?.items || []);
    } catch (err) {
      logger.error('Error loading people:', err);
      // Non-critical error, dropdown will just be empty
    }
  };

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
      logger.error('Error loading cluster:', err);
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
      logger.error('Error loading more faces:', err);
    } finally {
      setLoading(false);
    }
  };

  // Toggle face selection
  const toggleFaceSelection = (faceId) => {
    setSelectedFaces(prev => {
      const newSet = new Set(prev);
      if (newSet.has(faceId)) {
        newSet.delete(faceId);
      } else {
        newSet.add(faceId);
      }
      return newSet;
    });
  };

  // Select/deselect all faces
  const toggleSelectAll = () => {
    if (selectedFaces.size === faces.length) {
      setSelectedFaces(new Set());
    } else {
      setSelectedFaces(new Set(faces.map(f => f.id)));
    }
  };

  // Confirm a single face
  const handleConfirmFace = async (faceId) => {
    try {
      setReviewLoading(true);
      const result = await clusteringService.reviewFace(clusterId, faceId, 'confirm');
      setReviewMessage({ type: 'success', text: result.message });
      setTimeout(() => setReviewMessage(null), 3000);
    } catch (err) {
      logger.error('Error confirming face:', err);
      setReviewMessage({ type: 'error', text: 'Failed to confirm face' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Reject a single face
  const handleRejectFace = async (faceId, reassignTo = null) => {
    try {
      setReviewLoading(true);
      const result = await clusteringService.reviewFace(clusterId, faceId, 'reject', reassignTo);

      // Remove the rejected face from local state
      setFaces(prev => prev.filter(f => f.id !== faceId));
      setSelectedFaces(prev => {
        const newSet = new Set(prev);
        newSet.delete(faceId);
        return newSet;
      });

      // Update cluster face count
      if (cluster) {
        setCluster(prev => ({
          ...prev,
          face_count: prev.face_count - 1
        }));
      }

      setReviewMessage({ type: 'success', text: result.message });
      setTimeout(() => setReviewMessage(null), 3000);

      // Notify parent of update
      if (onClusterUpdated) onClusterUpdated();
    } catch (err) {
      logger.error('Error rejecting face:', err);
      setReviewMessage({ type: 'error', text: 'Failed to reject face' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Bulk confirm selected faces
  const handleBulkConfirm = async () => {
    if (selectedFaces.size === 0) return;

    try {
      setReviewLoading(true);
      const result = await clusteringService.bulkReviewFaces(
        clusterId,
        Array.from(selectedFaces),
        'confirm'
      );

      setReviewMessage({ type: 'success', text: `Confirmed ${result.faces_confirmed} faces` });
      setSelectedFaces(new Set());
      setTimeout(() => setReviewMessage(null), 3000);
    } catch (err) {
      logger.error('Error bulk confirming faces:', err);
      setReviewMessage({ type: 'error', text: 'Failed to confirm faces' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Bulk reject selected faces
  const handleBulkReject = async (reassignTo = null) => {
    if (selectedFaces.size === 0) return;

    try {
      setReviewLoading(true);
      const faceIds = Array.from(selectedFaces);
      const result = await clusteringService.bulkReviewFaces(
        clusterId,
        faceIds,
        'reject',
        reassignTo
      );

      // Remove rejected faces from local state
      setFaces(prev => prev.filter(f => !selectedFaces.has(f.id)));

      // Update cluster face count
      if (cluster) {
        setCluster(prev => ({
          ...prev,
          face_count: prev.face_count - faceIds.length
        }));
      }

      setReviewMessage({ type: 'success', text: result.message });
      setSelectedFaces(new Set());
      setShowReassignInput(false);
      setReassignName('');
      setTimeout(() => setReviewMessage(null), 3000);

      // Notify parent of update
      if (onClusterUpdated) onClusterUpdated();
    } catch (err) {
      logger.error('Error bulk rejecting faces:', err);
      setReviewMessage({ type: 'error', text: 'Failed to reject faces' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Submit reassignment
  const handleReassignSubmit = () => {
    if (selectedFaces.size > 0) {
      handleBulkReject(reassignName.trim() || null);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  const getImageUrl = (snapshotPath) => {
    if (!snapshotPath) return '/placeholder-face.png';
    if (snapshotPath.startsWith('http')) return snapshotPath;
    if (snapshotPath.startsWith('/')) return snapshotPath;
    // Just prepend / - path is already stored as data/snapshots/... in the database
    return `/${snapshotPath}`;
  };

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onClose);


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-large cluster-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">
            {cluster?.is_identified ? (
              <>✓ {cluster.label}</>
            ) : (
              <>Cluster #{clusterId}</>
            )}
          </h2>
          <button className="modal-close" onClick={onClose}>×</button>
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
              {/* Review Message */}
              {reviewMessage && (
                <div className={`review-message review-message-${reviewMessage.type}`}>
                  {reviewMessage.type === 'success' ? '✓' : '⚠'} {reviewMessage.text}
                </div>
              )}

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

                  <div className="cluster-actions">
                    {!cluster.is_identified && (
                      <button
                        className="btn btn-primary"
                        onClick={onAssignName}
                      >
                        👤 Assign Name
                      </button>
                    )}
                    <button
                      className={`btn ${reviewMode ? 'btn-secondary' : 'btn-outline'}`}
                      onClick={() => {
                        setReviewMode(!reviewMode);
                        setSelectedFaces(new Set());
                        setShowReassignInput(false);
                      }}
                    >
                      {reviewMode ? '✕ Exit Review' : '🔍 Review Faces'}
                    </button>
                  </div>
                </div>
              )}

              {/* Bulk Actions Bar (shown in review mode) */}
              {reviewMode && faces.length > 0 && (
                <div className="bulk-actions-bar">
                  <div className="selection-info">
                    <label className="select-all-label">
                      <input
                        type="checkbox"
                        checked={selectedFaces.size === faces.length && faces.length > 0}
                        onChange={toggleSelectAll}
                      />
                      Select All ({selectedFaces.size}/{faces.length})
                    </label>
                  </div>

                  {selectedFaces.size > 0 && (
                    <div className="bulk-buttons">
                      <button
                        className="btn btn-confirm"
                        onClick={handleBulkConfirm}
                        disabled={reviewLoading}
                      >
                        ✓ Confirm Selected ({selectedFaces.size})
                      </button>
                      <button
                        className="btn btn-reject"
                        onClick={() => setShowReassignInput(true)}
                        disabled={reviewLoading}
                      >
                        ✕ Reject Selected ({selectedFaces.size})
                      </button>
                    </div>
                  )}

                  {/* Reassignment Input */}
                  {showReassignInput && (
                    <div className="reassign-input-container">
                      <div className="reassign-mode-toggle">
                        <label className={`mode-option ${reassignMode === 'existing' ? 'active' : ''}`}>
                          <input
                            type="radio"
                            name="reassignMode"
                            value="existing"
                            checked={reassignMode === 'existing'}
                            onChange={() => {
                              setReassignMode('existing');
                              setReassignName('');
                            }}
                          />
                          Existing Person
                        </label>
                        <label className={`mode-option ${reassignMode === 'new' ? 'active' : ''}`}>
                          <input
                            type="radio"
                            name="reassignMode"
                            value="new"
                            checked={reassignMode === 'new'}
                            onChange={() => {
                              setReassignMode('new');
                              setReassignName('');
                            }}
                          />
                          Create New
                        </label>
                      </div>

                      {reassignMode === 'existing' ? (
                        <select
                          value={reassignName}
                          onChange={(e) => setReassignName(e.target.value)}
                          className="reassign-select"
                        >
                          <option value="">-- Select a person --</option>
                          {existingPeople.map((person) => (
                            <option key={person.name} value={person.name}>
                              {person.name} ({person.photo_count} photos)
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          placeholder="Enter new person name"
                          value={reassignName}
                          onChange={(e) => setReassignName(e.target.value)}
                          className="reassign-input"
                        />
                      )}

                      <div className="reassign-actions">
                        <button
                          className="btn btn-primary"
                          onClick={handleReassignSubmit}
                          disabled={reviewLoading || (reassignMode === 'new' && !reassignName.trim())}
                        >
                          {reviewLoading ? 'Processing...' : 'Confirm Rejection'}
                        </button>
                        <button
                          className="btn btn-outline"
                          onClick={() => {
                            setShowReassignInput(false);
                            setReassignName('');
                            setReassignMode('existing');
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Faces Grid */}
              <div className="faces-grid">
                {faces.map((face, index) => (
                  <div
                    key={`${face.id}-${index}`}
                    className={`face-item ${reviewMode ? 'review-mode' : ''} ${selectedFaces.has(face.id) ? 'selected' : ''}`}
                  >
                    {/* Selection checkbox in review mode */}
                    {reviewMode && (
                      <div className="face-select">
                        <input
                          type="checkbox"
                          checked={selectedFaces.has(face.id)}
                          onChange={() => toggleFaceSelection(face.id)}
                        />
                      </div>
                    )}

                    <div
                      className="face-image-container"
                      onClick={reviewMode ? () => toggleFaceSelection(face.id) : undefined}
                      // Only interactive while reviewing. Outside review mode there is no
                      // click handler, so it must not be focusable either — a tab stop that
                      // does nothing is its own accessibility problem.
                      onKeyDown={reviewMode ? activateOnKey(() => toggleFaceSelection(face.id)) : undefined}
                      role={reviewMode ? 'button' : undefined}
                      tabIndex={reviewMode ? 0 : undefined}
                    >
                      <img
                        src={getImageUrl(face.snapshot_path)}
                        alt={`Face detection ${face.id}`}
                        loading="lazy"
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

                    {/* Individual review buttons (shown on hover) */}
                    {reviewMode && (
                      <div className="face-review-buttons">
                        <button
                          className="btn-icon btn-confirm-icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleConfirmFace(face.id);
                          }}
                          disabled={reviewLoading}
                          title="Confirm this face"
                        >
                          ✓
                        </button>
                        <button
                          className="btn-icon btn-reject-icon"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRejectFace(face.id);
                          }}
                          disabled={reviewLoading}
                          title="Reject this face"
                        >
                          ✕
                        </button>
                      </div>
                    )}
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
