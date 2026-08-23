// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState } from 'react';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import './DeleteClusterModal.css';

/**
 * Delete Cluster Confirmation Modal
 * Allows user to confirm cluster deletion and optionally delete faces permanently
 */
const DeleteClusterModal = ({ cluster, onConfirm, onCancel }) => {
  const [deleteFaces, setDeleteFaces] = useState(false);

  const handleConfirm = () => {
    onConfirm(deleteFaces);
  };

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onCancel);


  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <h2 className="modal-title">Delete Cluster?</h2>
          <button className="modal-close" onClick={onCancel} aria-label="Close">
            ×
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {cluster && (
            <>
              <div className="cluster-info">
                <p><strong>Cluster:</strong> {cluster.label || `Cluster #${cluster.id}`}</p>
                <p><strong>Faces:</strong> {cluster.face_count}</p>
              </div>

              <div className="warning-message">
                <p>⚠️ This action will delete the cluster grouping.</p>
              </div>

              <div className="deletion-options">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={deleteFaces}
                    onChange={(e) => setDeleteFaces(e.target.checked)}
                  />
                  <span className="checkbox-text">
                    <strong>Also permanently delete {cluster.face_count} face detection event{cluster.face_count !== 1 ? 's' : ''}</strong>
                  </span>
                </label>

                {deleteFaces ? (
                  <div className="deletion-explanation danger">
                    <p><strong>⚠️ PERMANENT DELETION</strong></p>
                    <p>All {cluster.face_count} face detection events will be permanently removed from the database.</p>
                    <p className="warning-text">This action cannot be undone!</p>
                  </div>
                ) : (
                  <div className="deletion-explanation safe">
                    <p><strong>✓ Soft Delete</strong></p>
                    <p>The cluster will be deleted, but the {cluster.face_count} face detection events will remain as "Unknown" faces.</p>
                    <p>These faces can be re-clustered later.</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onCancel}>
            Cancel
          </button>
          <button
            className={`btn ${deleteFaces ? 'btn-danger' : 'btn-primary'}`}
            onClick={handleConfirm}
          >
            {deleteFaces ? '🗑️ Delete Permanently' : 'Delete Cluster'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteClusterModal;
