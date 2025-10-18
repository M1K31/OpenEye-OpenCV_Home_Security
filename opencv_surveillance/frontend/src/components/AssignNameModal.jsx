// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState } from 'react';
import clusteringService from '../services/clusteringService';
import './Modal.css';

/**
 * Assign Name Modal
 * Interface for assigning a person name to a face cluster
 */
const AssignNameModal = ({ clusterId, onClose, onSuccess }) => {
  const [personName, setPersonName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!personName.trim()) {
      setError('Please enter a name');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const result = await clusteringService.assignNameToCluster(
        clusterId,
        personName.trim()
      );
      
      // Show success message
      alert(`✅ ${result.message}\n${result.faces_updated} faces updated`);
      
      // Call success callback
      onSuccess();
    } catch (err) {
      console.error('Error assigning name:', err);
      setError(err.response?.data?.detail || 'Failed to assign name. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>👤 Assign Name to Cluster</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <p className="modal-description">
              Enter the person's name to identify all faces in this cluster.
              This will update all {clusterId ? `faces in cluster #${clusterId}` : 'selected faces'}.
            </p>

            <div className="form-group">
              <label htmlFor="person-name">Person Name</label>
              <input
                type="text"
                id="person-name"
                className="form-input"
                placeholder="e.g., John Smith"
                value={personName}
                onChange={(e) => setPersonName(e.target.value)}
                autoFocus
                disabled={loading}
              />
            </div>

            {error && (
              <div className="error-message">
                ⚠️ {error}
              </div>
            )}
          </div>

          <div className="modal-footer">
            <button
              type="button"
              className="btn btn-outline"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !personName.trim()}
            >
              {loading ? '⏳ Assigning...' : '✓ Assign Name'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AssignNameModal;
