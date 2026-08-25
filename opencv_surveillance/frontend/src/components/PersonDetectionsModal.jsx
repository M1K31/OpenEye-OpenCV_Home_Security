// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { activateOnKey } from '../utils/a11y';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import { useDialogA11y } from '../hooks/useDialogA11y';
import { logger } from '../utils/logger';
import faceHistoryService from '../services/faceHistoryService';
import apiClient from '../api/apiClient';
import './PersonDetectionsModal.css';
import { describeApiError } from '../utils/apiError';

/**
 * Person Detections Modal
 * Shows detection history for a specific person with review capability
 * Uses static buttons for better performance
 */
const PersonDetectionsModal = ({ personName, allPeople, onClose, onUpdate }) => {
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reviewMode, setReviewMode] = useState(false);
  const [selectedFaces, setSelectedFaces] = useState(new Set());
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewMessage, setReviewMessage] = useState(null);

  // Action states
  const [showReassign, setShowReassign] = useState(false);
  const [showCreatePerson, setShowCreatePerson] = useState(false);
  const [reassignTarget, setReassignTarget] = useState('');
  const [newPersonName, setNewPersonName] = useState('');

  useEffect(() => {
    loadDetections();
  }, [personName]);

  const loadDetections = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await faceHistoryService.getPersonHistory(personName, 100);
      setDetections(data || []);
    } catch (err) {
      logger.error('Error loading detections:', err);
      setError('Failed to load detection history');
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
    if (snapshotPath.startsWith('http')) return snapshotPath;
    if (snapshotPath.startsWith('/')) return snapshotPath;
    return `/${snapshotPath}`;
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

  // Select/deselect all
  const toggleSelectAll = () => {
    if (selectedFaces.size === detections.length) {
      setSelectedFaces(new Set());
    } else {
      setSelectedFaces(new Set(detections.map(d => d.id)));
    }
  };

  // Mark selected as Unknown
  const handleMarkUnknown = async () => {
    if (selectedFaces.size === 0) return;

    try {
      setReviewLoading(true);
      const faceIds = Array.from(selectedFaces);
      const result = await faceHistoryService.bulkReassignFaces(faceIds, 'Unknown');

      // Remove from local state
      setDetections(prev => prev.filter(d => !selectedFaces.has(d.id)));
      setSelectedFaces(new Set());

      setReviewMessage({ type: 'success', text: `Marked ${result.reassigned_count} face(s) as Unknown` });
      setTimeout(() => setReviewMessage(null), 3000);

      if (onUpdate) onUpdate();
    } catch (err) {
      logger.error('Error marking as unknown:', err);
      setReviewMessage({ type: 'error', text: 'Failed to mark faces as Unknown' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Reassign to existing person
  const handleReassign = async () => {
    if (selectedFaces.size === 0 || !reassignTarget) return;

    try {
      setReviewLoading(true);
      const faceIds = Array.from(selectedFaces);
      const result = await faceHistoryService.bulkReassignFaces(faceIds, reassignTarget);

      // Remove from local state
      setDetections(prev => prev.filter(d => !selectedFaces.has(d.id)));
      setSelectedFaces(new Set());
      setShowReassign(false);
      setReassignTarget('');

      setReviewMessage({ type: 'success', text: result.message });
      setTimeout(() => setReviewMessage(null), 3000);

      if (onUpdate) onUpdate();
    } catch (err) {
      logger.error('Error reassigning faces:', err);
      setReviewMessage({ type: 'error', text: 'Failed to reassign faces' });
    } finally {
      setReviewLoading(false);
    }
  };

  // Create new person and assign faces
  const handleCreateAndAssign = async () => {
    if (selectedFaces.size === 0 || !newPersonName.trim()) return;

    const trimmedName = newPersonName.trim();
    const faceIds = Array.from(selectedFaces);

    try {
      setReviewLoading(true);

      // First create the person
      try {
        await apiClient.post('/faces/people', { name: trimmedName });
      } catch (createErr) {
        // If person already exists, that's OK - continue with reassignment
        if (createErr.response?.status !== 409) {
          throw createErr;
        }
      }

      // Then reassign the faces
      const result = await faceHistoryService.bulkReassignFaces(faceIds, trimmedName);

      // Remove from local state
      setDetections(prev => prev.filter(d => !selectedFaces.has(d.id)));
      setSelectedFaces(new Set());
      setShowCreatePerson(false);
      setNewPersonName('');

      setReviewMessage({ type: 'success', text: `Created "${trimmedName}" and assigned ${result.reassigned_count} face(s)` });
      setTimeout(() => setReviewMessage(null), 3000);

      if (onUpdate) onUpdate();
    } catch (err) {
      logger.error('Error creating person:', err);
      // More specific error messages
      const errorMsg = describeApiError(err, 'Failed to create person and assign faces');
      setReviewMessage({ type: 'error', text: errorMsg });
    } finally {
      setReviewLoading(false);
    }
  };

  // Other people for reassignment (excluding current person)
  const otherPeople = (allPeople || []).filter(p => p.name !== personName);

  // Reset action states when selection changes
  const resetActions = () => {
    setShowReassign(false);
    setShowCreatePerson(false);
    setReassignTarget('');
    setNewPersonName('');
  };

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onClose);

  const { dialogRef, dialogProps } = useDialogA11y(true, 'person-detections-title');


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={dialogRef} {...dialogProps} className="modal modal-large person-detections-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 id="person-detections-title" className="modal-title">
            Detections for {personName}
          </h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Review Message */}
          {reviewMessage && (
            <div className={`review-message review-message-${reviewMessage.type}`}>
              {reviewMessage.type === 'success' ? '✓' : '⚠'} {reviewMessage.text}
            </div>
          )}

          {error ? (
            <div className="error-state">
              <p>⚠️ {error}</p>
              <button className="btn btn-primary" onClick={loadDetections}>
                Try Again
              </button>
            </div>
          ) : loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading detections...</p>
            </div>
          ) : detections.length === 0 ? (
            <div className="empty-state">
              <p>No detections found for {personName}</p>
            </div>
          ) : (
            <>
              {/* Info Bar */}
              <div className="info-bar">
                <span>{detections.length} detection(s) found</span>
                <button
                  className={`btn ${reviewMode ? 'btn-secondary' : 'btn-outline'}`}
                  onClick={() => {
                    setReviewMode(!reviewMode);
                    setSelectedFaces(new Set());
                    resetActions();
                  }}
                >
                  {reviewMode ? '✕ Exit Review' : '🔍 Review Detections'}
                </button>
              </div>

              {/* Bulk Actions Bar (shown in review mode with selections) */}
              {reviewMode && (
                <div className="bulk-actions-bar">
                  <div className="selection-info">
                    <label className="select-all-label">
                      <input
                        type="checkbox"
                        checked={selectedFaces.size === detections.length && detections.length > 0}
                        onChange={toggleSelectAll}
                      />
                      Select All ({selectedFaces.size}/{detections.length})
                    </label>
                  </div>

                  {selectedFaces.size > 0 && !showReassign && !showCreatePerson && (
                    <div className="bulk-buttons">
                      <button
                        className="btn btn-unknown"
                        onClick={handleMarkUnknown}
                        disabled={reviewLoading}
                      >
                        ✕ Mark as Unknown ({selectedFaces.size})
                      </button>
                      <button
                        className="btn btn-add-person"
                        onClick={() => { resetActions(); setShowCreatePerson(true); }}
                        disabled={reviewLoading}
                      >
                        + Create New Person
                      </button>
                      {otherPeople.length > 0 && (
                        <button
                          className="btn btn-reassign"
                          onClick={() => { resetActions(); setShowReassign(true); }}
                          disabled={reviewLoading}
                        >
                          ↗ Reassign to Existing
                        </button>
                      )}
                    </div>
                  )}

                  {/* Create Person Input */}
                  {showCreatePerson && (
                    <div className="create-person-container">
                      <input
                        type="text"
                        placeholder="Enter new person name..."
                        value={newPersonName}
                        onChange={(e) => setNewPersonName(e.target.value)}
                        className="create-person-input"
                        autoFocus
                      />
                      <button
                        className="btn btn-add-person"
                        onClick={handleCreateAndAssign}
                        disabled={reviewLoading || !newPersonName.trim()}
                      >
                        {reviewLoading ? 'Creating...' : `Create & Assign (${selectedFaces.size})`}
                      </button>
                      <button
                        className="btn btn-reassign"
                        onClick={() => setShowCreatePerson(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  )}

                  {/* Reassign Select */}
                  {showReassign && (
                    <div className="reassign-input-container">
                      <select
                        value={reassignTarget}
                        onChange={(e) => setReassignTarget(e.target.value)}
                        className="reassign-select"
                      >
                        <option value="">-- Select Person --</option>
                        {otherPeople.map(p => (
                          <option key={p.name} value={p.name}>{p.name}</option>
                        ))}
                      </select>
                      <button
                        className="btn btn-add-person"
                        onClick={handleReassign}
                        disabled={reviewLoading || !reassignTarget}
                      >
                        {reviewLoading ? 'Reassigning...' : `Reassign (${selectedFaces.size})`}
                      </button>
                      <button
                        className="btn btn-reassign"
                        onClick={() => setShowReassign(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Detections Grid */}
              <div className="detections-grid">
                {detections.map((detection) => (
                  <div
                    key={detection.id}
                    className={`detection-item ${reviewMode ? 'review-mode' : ''} ${selectedFaces.has(detection.id) ? 'selected' : ''}`}
                    onClick={reviewMode ? () => toggleFaceSelection(detection.id) : undefined}
                    // Only interactive while reviewing; see ClusterDetailModal for the same rule.
                    onKeyDown={reviewMode ? activateOnKey(() => toggleFaceSelection(detection.id)) : undefined}
                    role={reviewMode ? 'button' : undefined}
                    tabIndex={reviewMode ? 0 : undefined}
                  >
                    {/* Selection checkbox in review mode */}
                    {reviewMode && (
                      <div className="face-select" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selectedFaces.has(detection.id)}
                          onChange={() => toggleFaceSelection(detection.id)}
                        />
                      </div>
                    )}

                    <div className="detection-image-container">
                      <img
                        src={getImageUrl(detection.snapshot_path)}
                        alt={`Detection ${detection.id}`}
                        loading="lazy"
                        onError={(e) => {
                          e.target.src = '/placeholder-face.png';
                        }}
                      />
                      <div className="detection-confidence">
                        {(detection.confidence * 100).toFixed(0)}%
                      </div>
                    </div>

                    <div className="detection-meta">
                      <div className="detection-camera">📷 {detection.camera_id}</div>
                      <div className="detection-time">{formatDate(detection.detected_at)}</div>
                    </div>
                  </div>
                ))}
              </div>
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

export default PersonDetectionsModal;
