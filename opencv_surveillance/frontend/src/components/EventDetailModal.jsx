import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/apiClient';
import Button from './universal/Button';
import './Modal.css';
import './EventDetailModal.css';

/**
 * EventDetailModal Component
 *
 * Displays event details with image/video preview and action buttons:
 * - Save/Download
 * - Delete
 * - View in Timeline
 * - Play (for videos)
 */
const EventDetailModal = ({ event, onClose, onDelete }) => {
  const navigate = useNavigate();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  if (!event) return null;

  const isVideo = !!event.recording_id;
  const hasSnapshot = !!event.snapshot_path || event.hasSnapshot;
  const eventTime = new Date(event.timestamp).toLocaleString();

  const handleSave = async () => {
    try {
      let downloadUrl;
      let filename;

      if (isVideo) {
        // Download video recording
        downloadUrl = `/api/recordings/${event.recording_id}/download`;
        filename = `recording_${event.recording_id}_${event.camera_id}.mp4`;
      } else if (hasSnapshot) {
        // Download snapshot image
        downloadUrl = event.snapshot_path;
        filename = `snapshot_${event.id}_${event.camera_id}.jpg`;
      }

      // Trigger download
      const response = await apiClient.get(downloadUrl, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      logger.error('Failed to download:', err);
      setError('Failed to download file');
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this event? This action cannot be undone.')) {
      return;
    }

    setDeleting(true);
    setError(null);

    try {
      if (isVideo) {
        await apiClient.delete(`/recordings/${event.recording_id}`);
      } else if (hasSnapshot) {
        // Assuming there's a snapshot delete endpoint
        await apiClient.delete(`/motion-events/${event.id || event.snapshot_id}`);
      }

      if (onDelete) {
        onDelete(event);
      }

      onClose();
    } catch (err) {
      logger.error('Failed to delete:', err);
      setError(`Failed to delete event: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  const handleViewInTimeline = () => {
    // Navigate to timeline view with event timestamp
    const timestamp = new Date(event.timestamp).getTime();
    navigate(`/timeline?camera=${event.camera_id}&timestamp=${timestamp}`);
    onClose();
  };

  const handleViewRecordings = () => {
    // Navigate to recordings page
    navigate(`/recordings`);
    onClose();
  };

  const getEventTitle = () => {
    if (event.type === 'face') {
      return `Face Detected: ${event.person_name}`;
    } else if (event.type === 'motion') {
      if (event.known_faces_detected > 0) {
        return `Motion + ${event.known_faces_detected} Known Face(s)`;
      } else if (event.faces_detected > 0) {
        return `Motion + ${event.faces_detected} Unknown Face(s)`;
      }
      return 'Motion Detected';
    }
    return 'Event';
  };

  const getEventDetails = () => {
    const details = [];

    details.push({ label: 'Camera', value: event.camera_id });
    details.push({ label: 'Time', value: eventTime });

    if (event.type === 'face' && event.confidence) {
      details.push({ label: 'Confidence', value: `${Math.round(event.confidence * 100)}%` });
    }

    if (event.duration_seconds) {
      details.push({ label: 'Duration', value: `${Math.round(event.duration_seconds)}s` });
    }

    if (event.faces_detected) {
      details.push({ label: 'Faces Detected', value: event.faces_detected });
    }

    if (event.known_faces_detected) {
      details.push({ label: 'Known Faces', value: event.known_faces_detected });
    }

    return details;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal event-detail-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">{getEventTitle()}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="alert alert-error">
            <span className="alert-icon">⚠️</span>
            <div className="alert-content">{error}</div>
          </div>
        )}

        <div className="modal-body">
          {/* Event Preview */}
          <div className="event-preview">
            {isVideo ? (
              <video
                src={`/api/recordings/${event.recording_id}/download`}
                controls
                className="event-video"
                preload="metadata"
                style={{ width: '100%', maxHeight: '480px', borderRadius: '8px' }}
              >
                Your browser does not support the video tag.
              </video>
            ) : hasSnapshot ? (
              <img
                src={event.snapshot_path || `/data/snapshots/${event.camera_id}/${event.id}.jpg`}
                alt="Event snapshot"
                className="event-snapshot"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="640" height="480"%3E%3Crect fill="%23333" width="640" height="480"/%3E%3Ctext fill="%23fff" font-size="20" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3ESnapshot Unavailable%3C/text%3E%3C/svg%3E';
                }}
              />
            ) : (
              <div className="event-no-media">
                <p>No media available</p>
              </div>
            )}
          </div>

          {/* Event Details */}
          <div className="event-details-list">
            {getEventDetails().map((detail, index) => (
              <div key={index} className="event-detail-item">
                <span className="event-detail-label">{detail.label}:</span>
                <span className="event-detail-value">{detail.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <div className="event-actions">
            {/* Save/Download Button */}
            <Button
              variant="primary"
              onClick={handleSave}
              title={isVideo ? 'Download Video' : 'Download Snapshot'}
              icon="💾"
            >
              Save
            </Button>

            {/* View in Timeline Button */}
            <Button
              variant="secondary"
              onClick={handleViewInTimeline}
              title="View in timeline"
              icon="📅"
            >
              Timeline
            </Button>

            {/* View All Recordings Button (for videos) */}
            {isVideo && (
              <Button
                variant="secondary"
                onClick={handleViewRecordings}
                title="View all recordings"
                icon="📹"
              >
                Recordings
              </Button>
            )}

            {/* Delete Button */}
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
              loading={deleting}
              title="Delete event"
              icon={!deleting ? '🗑️' : undefined}
            >
              Delete
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EventDetailModal;
