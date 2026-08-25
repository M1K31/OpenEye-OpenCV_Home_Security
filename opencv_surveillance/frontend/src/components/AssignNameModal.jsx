// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import { logger } from '../utils/logger';
import clusteringService from '../services/clusteringService';
import apiClient from '../api/apiClient';
import './Modal.css';
import { describeApiError } from '../utils/apiError';

/**
 * Assign Name Modal
 * Interface for assigning a person name to a face cluster
 * Supports both selecting existing people and creating new ones
 */
const AssignNameModal = ({ clusterId, onClose, onSuccess }) => {
  const [personName, setPersonName] = useState('');
  const [selectedPerson, setSelectedPerson] = useState(''); // '' = create new
  const [existingPeople, setExistingPeople] = useState([]);
  const [loadingPeople, setLoadingPeople] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch existing people on mount
  useEffect(() => {
    const fetchPeople = async () => {
      try {
        const response = await apiClient.get('/faces/people');
        const people = response.data?.data || response.data?.people || [];
        setExistingPeople(people.map(p => p.name));
      } catch (err) {
        logger.error('Failed to load existing people:', err);
        // Continue without existing people - user can still create new
      } finally {
        setLoadingPeople(false);
      }
    };
    fetchPeople();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();

    // Determine the final name to use
    const finalName = selectedPerson === '__create_new__' ? personName.trim() : selectedPerson;

    if (!finalName) {
      setError('Please select a person or enter a new name');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const result = await clusteringService.assignNameToCluster(
        clusterId,
        finalName
      );

      // Show success message
      alert(`✅ ${result.message}\n${result.faces_updated} faces updated`);

      // Call success callback
      onSuccess();
    } catch (err) {
      logger.error('Error assigning name:', err);
      setError(describeApiError(err, 'Failed to assign name. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectChange = (value) => {
    setSelectedPerson(value);
    if (value !== '__create_new__') {
      setPersonName(''); // Clear text input when selecting existing person
    }
  };

  const isValid = selectedPerson === '__create_new__' ? personName.trim().length > 0 : selectedPerson.length > 0;

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onClose);


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">👤 Assign Name to Cluster</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <p className="modal-description">
              Assign this cluster to an existing person or create a new profile.
              This will update all {clusterId ? `faces in cluster #${clusterId}` : 'selected faces'}.
            </p>

            {/* Person Selection */}
            <div className="form-group">
              <label htmlFor="person-select">Select Person</label>
              {loadingPeople ? (
                <div className="loading-text">Loading people...</div>
              ) : (
                <select
                  id="person-select"
                  className="form-input"
                  value={selectedPerson}
                  onChange={(e) => handleSelectChange(e.target.value)}
                  disabled={loading}
                >
                  <option value="">-- Select a person --</option>
                  {existingPeople.length > 0 && (
                    <optgroup label="Existing People">
                      {existingPeople.map(name => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </optgroup>
                  )}
                  <optgroup label="New">
                    <option value="__create_new__">+ Create New Person</option>
                  </optgroup>
                </select>
              )}
            </div>

            {/* New Person Name Input - shown when "Create New" is selected */}
            {selectedPerson === '__create_new__' && (
              <div className="form-group">
                <label htmlFor="person-name">New Person Name</label>
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
                <p className="form-hint">
                  This will create a new person profile with photos from this cluster.
                </p>
              </div>
            )}

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
              disabled={loading || !isValid}
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
