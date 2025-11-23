// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Audio Modal Component (v3.10.0)
 *
 * Modal wrapper for Two-Way Audio functionality
 * Displays TwoWayAudio component in a modal dialog
 */

import React from 'react';
import TwoWayAudio from './TwoWayAudio';
import './AudioModal.css';

const AudioModal = ({ isOpen, onClose, cameraId, cameraName }) => {
  if (!isOpen) return null;

  // Handle click outside modal to close
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Handle escape key
  React.useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  return (
    <div className="audio-modal-backdrop" onClick={handleBackdropClick}>
      <div className="audio-modal-container">
        <div className="audio-modal-header">
          <h2 className="audio-modal-title">
            🎤 Two-Way Audio
          </h2>
          <p className="audio-modal-subtitle">
            {cameraName || cameraId}
          </p>
          <button
            className="audio-modal-close"
            onClick={onClose}
            aria-label="Close audio modal"
          >
            ✕
          </button>
        </div>

        <div className="audio-modal-content">
          <TwoWayAudio cameraId={cameraId} />
        </div>

        <div className="audio-modal-footer">
          <p className="audio-modal-note">
            💡 <strong>Tip:</strong> Allow microphone access when prompted for two-way communication
          </p>
        </div>
      </div>
    </div>
  );
};

export default AudioModal;
