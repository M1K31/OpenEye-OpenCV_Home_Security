// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React from 'react';
import { activateOnKey } from '../utils/a11y';
import './ClusterCard.css';

/**
 * Cluster Card Component
 * Displays a single face cluster with representative image and metadata
 */
const ClusterCard = ({ cluster, selected, onSelect, onView, onAssignName, onDelete }) => {
  const {
    id,
    label,
    is_identified,
    face_count,
    avg_confidence,
    representative_snapshot_path,
    last_seen_at,
  } = cluster;

  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Get image URL
  const getImageUrl = () => {
    if (!representative_snapshot_path) {
      return '/placeholder-face.png'; // Fallback placeholder
    }
    // Construct URL based on path
    if (representative_snapshot_path.startsWith('http')) {
      return representative_snapshot_path;
    }
    // If path already starts with /, use as-is
    if (representative_snapshot_path.startsWith('/')) {
      return representative_snapshot_path;
    }
    // Otherwise, just prepend / to make it a valid URL path
    // The path is already stored as data/snapshots/... in the database
    return `/${representative_snapshot_path}`;
  };

  return (
    <div className={`cluster-card ${selected ? 'selected' : ''}`}>
      {/* Selection Checkbox */}
      <div className="cluster-selection">
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onSelect(id)}
          onClick={(e) => e.stopPropagation()}
        />
      </div>

      {/* Representative Image */}
      <div 
        className="cluster-image"
        onClick={() => onView(id)}
        onKeyDown={activateOnKey(() => onView(id))}
        role="button"
        tabIndex={0}
      >
        <img
          src={getImageUrl()}
          alt={label || `Cluster ${id}`}
          onError={(e) => {
            e.target.src = '/placeholder-face.png';
          }}
        />
        <div className="face-count-badge">
          {face_count} {face_count === 1 ? 'face' : 'faces'}
        </div>
      </div>

      {/* Cluster Info */}
      <div className="cluster-info">
        <div className="cluster-header">
          <h3 className="cluster-title">
            {is_identified ? (
              <>
                <span className="status-icon identified">✓</span>
                {label}
              </>
            ) : (
              <>
                <span className="status-icon unidentified">?</span>
                Cluster #{id}
              </>
            )}
          </h3>
        </div>

        <div className="cluster-meta">
          <div className="meta-item">
            <span className="meta-label">Confidence:</span>
            <span className="meta-value">
              {avg_confidence ? `${(avg_confidence * 100).toFixed(1)}%` : 'N/A'}
            </span>
          </div>
          <div className="meta-item">
            <span className="meta-label">Last seen:</span>
            <span className="meta-value">{formatDate(last_seen_at)}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="cluster-actions">
          {!is_identified && (
            <button
              className="btn btn-sm btn-primary"
              onClick={(e) => {
                e.stopPropagation();
                onAssignName(id);
              }}
            >
              👤 Assign Name
            </button>
          )}
          <button
            className="btn btn-sm btn-outline"
            onClick={(e) => {
              e.stopPropagation();
              onView(id);
            }}
          >
            👁️ View Faces
          </button>
          <button
            className="btn btn-sm btn-danger"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(id);
            }}
          >
            🗑️
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClusterCard;
