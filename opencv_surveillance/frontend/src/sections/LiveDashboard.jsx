// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { logger } from '../utils/logger';
import { formatTimestampShort } from '../utils/dateUtils';
import apiClient, { isAuthenticated } from '../api/apiClient';
import PipVideoPlayer from '../components/PipVideoPlayer';
import CameraSettingsModal from '../components/CameraSettingsModal';
import EventDetailModal from '../components/EventDetailModal';
import Button from '../components/universal/Button';
import { useCachedApi, useCachedApiMultiple } from '../hooks/useCachedApi';
import { CacheTTL } from '../services/apiCache';
import LoadingSkeleton, { SkeletonCameraCard, SkeletonEventTimeline } from '../components/LoadingSkeleton';
import './LiveDashboard.css';

/**
 * Memoized Camera Card Component
 * Prevents unnecessary re-renders when parent state changes (e.g., grid size)
 */
const CameraCard = React.memo(({
  camera,
  onScreenshot,
  onPipToggle,
  onFullscreenToggle,
  onSettingsClick,
  isPipActive,
  isFullscreenActive,
  flashingCamera,
  screenshotFeedback
}) => {
  return (
    <div key={camera.camera_id} className="camera-card">
      <div className="camera-header">
        <h3>{camera.name || camera.camera_id}</h3>
        <span className={`status-badge ${camera.is_active ? 'active' : 'inactive'}`}>
          {camera.is_active ? 'Live' : 'Offline'}
        </span>
      </div>
      <div className="camera-feed">
        {camera.is_active ? (
          <img
            src={`/api/cameras/${camera.camera_id}/stream`}
            alt={`${camera.name} feed`}
            className="feed-image"
            onError={(e) => {
              e.target.onerror = null;
              e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="640" height="480"%3E%3Crect fill="%23333" width="640" height="480"/%3E%3Ctext fill="%23fff" font-size="20" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EStream Unavailable%3C/text%3E%3C/svg%3E';
            }}
          />
        ) : (
          <div className="feed-offline">
            <span>📡</span>
            <p>Camera Offline</p>
          </div>
        )}
        {flashingCamera === camera.camera_id && (
          <div className="screenshot-flash"></div>
        )}
      </div>
      <div className="camera-info">
        <span className="info-item">
          🎥 {camera.resolution || 'Unknown'}
        </span>
        <span className="info-item">
          {camera.motion_detection ? '🔍 Motion: ON' : '🔍 Motion: OFF'}
        </span>
      </div>
      <div className="camera-actions">
        <Button
          variant="secondary"
          size="small"
          onClick={() => onScreenshot(camera)}
          title="Capture Screenshot"
          disabled={!camera.is_active}
          icon="📸"
        >
          Screenshot
        </Button>
        <Button
          variant="secondary"
          size="small"
          onClick={() => onSettingsClick(camera)}
          title="Camera Settings"
          icon="⚙️"
        >
          Settings
        </Button>
        <Button
          variant={isPipActive ? 'primary' : 'secondary'}
          size="small"
          onClick={() => onPipToggle(camera)}
          title={isPipActive ? 'Close Picture-in-Picture' : 'Open Picture-in-Picture'}
          disabled={!camera.is_active}
          icon={isPipActive ? '📺' : '📺'}
        >
          {isPipActive ? 'Close PiP' : 'PiP'}
        </Button>
        <Button
          variant={isFullscreenActive ? 'primary' : 'secondary'}
          size="small"
          onClick={() => onFullscreenToggle(camera)}
          title={isFullscreenActive ? 'Exit Fullscreen' : 'View Fullscreen'}
          disabled={!camera.is_active}
          icon={isFullscreenActive ? '🔳' : '⛶'}
        >
          {isFullscreenActive ? 'Exit' : 'Fullscreen'}
        </Button>
      </div>
      {screenshotFeedback?.camera_id === camera.camera_id && (
        <div className={`screenshot-feedback ${screenshotFeedback.status}`}>
          {screenshotFeedback.status === 'success' ? '✓' : '⚠'} {screenshotFeedback.message}
        </div>
      )}
    </div>
  );
});

/**
 * LiveDashboard Section
 *
 * Main landing page with:
 * - Camera grid (real-time feeds)
 * - Global status bar
 * - Collapsible event timeline (right panel)
 * - Linked events to recordings
 */
const LiveDashboard = () => {
  const [events, setEvents] = useState([]);
  const [showTimeline, setShowTimeline] = useState(true);
  const [systemStatus, setSystemStatus] = useState('All systems nominal');
  const [selectedRecording, setSelectedRecording] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [showEventModal, setShowEventModal] = useState(false);
  const [cameraSize, setCameraSize] = useState(() => {
    // Load camera size preference from localStorage, default to 'medium'
    return localStorage.getItem('camera-feed-size') || 'medium';
  });
  const [pipCamera, setPipCamera] = useState(null);
  const [pipVideoRef, setPipVideoRef] = useState(null); // Reference to the PiP video element
  const [fullscreenCamera, setFullscreenCamera] = useState(null);
  const [screenshotFeedback, setScreenshotFeedback] = useState(null); // { camera_id, status: 'success'|'error', message }
  const [flashingCamera, setFlashingCamera] = useState(null); // camera_id for flash effect
  const [settingsCamera, setSettingsCamera] = useState(null); // Camera for settings modal

  // Check if Picture-in-Picture is supported
  const isPipSupported = document.pictureInPictureEnabled;

  // Fetch cameras with caching (10 second cache)
  const {
    data: camerasData,
    loading: camerasLoading,
    error: camerasError,
    refetch: refetchCameras
  } = useCachedApi('/cameras/', {
    ttl: CacheTTL.SHORT,
    enabled: isAuthenticated(),
    transform: (data) => data?.cameras || []
  });

  const cameras = camerasData || [];

  // Fetch events with caching (parallel requests with 10 second cache)
  // Memoize requests array to prevent infinite re-fetching
  const eventsRequests = useMemo(() => [
    {
      url: '/recordings/',
      params: { skip: 0, limit: 15 },
      ttl: CacheTTL.SHORT,
      transform: (data) => data?.recordings || (Array.isArray(data) ? data : [])
    },
    {
      url: '/motion-events/',
      params: { skip: 0, limit: 15 },
      ttl: CacheTTL.SHORT,
      transform: (data) => data?.events || []
    },
    {
      url: '/faces/history',
      params: { page: 1, page_size: 15 },
      ttl: CacheTTL.SHORT,
      transform: (data) => data?.data || []
    }
  ], []); // Empty deps - requests are static

  const {
    data: eventsData,
    loading: eventsLoading,
    refetch: refetchEvents
  } = useCachedApiMultiple(eventsRequests, { enabled: isAuthenticated() });

  // Process events data (memoized to prevent flickering)
  const processedEvents = useMemo(() => {
    if (!eventsData || eventsData.length < 3) return [];

    const [recordings, motionEvents, detections] = eventsData;

    // Merge and create unified timeline events
    const allEvents = [
      // Video recordings
      ...recordings.map(r => ({
        id: r.recording_id || r.id,  // API now returns recording_id
        recording_id: r.recording_id || r.id,
        type: 'motion',
        camera_id: r.camera_id,
        timestamp: r.started_at,
        duration_seconds: r.duration_seconds,
        faces_detected: r.faces_detected || 0,
        known_faces_detected: r.known_faces_detected || 0,
        hasRecording: true,
      })),
      // Motion snapshots (may or may not have recording)
      ...motionEvents.map(m => ({
        id: m.id,
        snapshot_id: m.id,
        snapshot_path: m.snapshot_path,
        recording_id: m.recording_id,  // May be null
        type: 'motion',
        camera_id: m.camera_id,
        timestamp: m.detected_at,
        duration_seconds: 0,
        faces_detected: m.faces_detected || 0,
        known_faces_detected: 0,
        hasRecording: !!m.recording_id,  // Has recording if recording_id exists
        hasSnapshot: true,
      })),
      // Face detections
      ...detections.map(d => ({
        id: d.id,
        recording_id: d.recording_id,
        snapshot_path: d.snapshot_path,
        type: 'face',
        camera_id: d.camera_id,
        timestamp: d.detected_at,
        person_name: d.person_name || 'Unknown',
        confidence: d.confidence || 0,
        hasSnapshot: !!d.snapshot_path,
      }))
    ];

    // Sort by timestamp (most recent first)
    allEvents.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Take top 15
    return allEvents.slice(0, 15);
  }, [eventsData]);

  // Update events state only when processed events change
  useEffect(() => {
    setEvents(processedEvents);
  }, [processedEvents]);

  // Auto-refresh events disabled to prevent flickering and camera feed reloads
  // Events will update when user manually refreshes or navigates
  // useEffect(() => {
  //   if (!isAuthenticated()) return;
  //
  //   const interval = setInterval(() => {
  //     refetchEvents();
  //   }, 10000);
  //
  //   return () => clearInterval(interval);
  // }, []); // Empty deps - refetchEvents is stable from hook

  const toggleTimeline = () => {
    setShowTimeline(!showTimeline);
  };

  const handleSizeChange = (size) => {
    setCameraSize(size);
    localStorage.setItem('camera-feed-size', size);
  };

  const handlePipToggle = async (camera) => {
    if (!isPipSupported) {
      alert('Picture-in-Picture is not supported in your browser. Try Chrome, Edge, or Safari.');
      return;
    }

    try {
      // If already in PiP mode, exit it
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setPipCamera(null);
        return;
      }

      // Check if clicking the same camera
      if (pipCamera?.camera_id === camera.camera_id) {
        setPipCamera(null);
        return;
      }

      // Set the camera for PiP (this will trigger the video element to render)
      setPipCamera(camera);

    } catch (error) {
      logger.error('Failed to toggle Picture-in-Picture:', error);
      alert('Failed to enable Picture-in-Picture. Please try again.');
    }
  };

  const closePip = async () => {
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
      }
      setPipCamera(null);
      setPipVideoRef(null);
    } catch (error) {
      logger.error('Failed to close Picture-in-Picture:', error);
    }
  };

  // Handle PiP video element ready
  const handlePipVideoReady = async (videoElement) => {
    if (!videoElement || !pipCamera) return;

    try {
      // Request Picture-in-Picture mode
      await videoElement.requestPictureInPicture();
      setPipVideoRef(videoElement);
    } catch (error) {
      logger.error('Failed to enter Picture-in-Picture:', error);
      setPipCamera(null);
    }
  };

  // Listen for PiP events
  useEffect(() => {
    const handleLeavePip = () => {
      setPipCamera(null);
      setPipVideoRef(null);
    };

    if (pipVideoRef) {
      pipVideoRef.addEventListener('leavepictureinpicture', handleLeavePip);
      return () => {
        pipVideoRef.removeEventListener('leavepictureinpicture', handleLeavePip);
      };
    }
  }, [pipVideoRef]);

  const handleFullscreenToggle = (camera) => {
    if (fullscreenCamera?.camera_id === camera.camera_id) {
      // Exit fullscreen if same camera clicked
      setFullscreenCamera(null);
    } else {
      // Enter fullscreen for this camera
      setFullscreenCamera(camera);
    }
  };

  const closeFullscreen = () => {
    setFullscreenCamera(null);
  };

  // Handle ESC key to close fullscreen
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && fullscreenCamera) {
        closeFullscreen();
      }
    };

    if (fullscreenCamera) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [fullscreenCamera]);

  // Handle manual screenshot capture
  const handleScreenshot = useCallback(async (camera) => {
    try {
      // Show flash effect
      setFlashingCamera(camera.camera_id);
      setTimeout(() => setFlashingCamera(null), 300);

      // Call API to capture snapshot (GET request returns the image file)
      const response = await apiClient.get(`/cameras/${camera.camera_id}/snapshot`, {
        responseType: 'blob' // Expect image file response
      });

      // Show success feedback
      setScreenshotFeedback({
        camera_id: camera.camera_id,
        status: 'success',
        message: 'Screenshot captured!'
      });

      // Clear feedback after 3 seconds
      setTimeout(() => setScreenshotFeedback(null), 3000);

      // Refresh events to show new snapshot
      refetchEvents();

    } catch (error) {
      logger.error('Screenshot capture failed:', error);

      // Show error feedback
      setScreenshotFeedback({
        camera_id: camera.camera_id,
        status: 'error',
        message: error.response?.data?.detail || 'Failed to capture screenshot'
      });

      // Clear feedback after 3 seconds
      setTimeout(() => setScreenshotFeedback(null), 3000);
    }
  }, [refetchEvents]);

  const handleEventClick = (event) => {
    // Show event detail modal for all events (videos and snapshots)
    setSelectedEvent(event);
    setShowEventModal(true);
  };

  const closeEventModal = () => {
    setShowEventModal(false);
    setSelectedEvent(null);
  };

  const handleEventDelete = (deletedEvent) => {
    // Remove deleted event from the events list
    setEvents(events.filter(e => e.id !== deletedEvent.id));
  };

  const formatEventTitle = (event) => {
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

  const formatEventSubtitle = (event) => {
    if (event.type === 'face') {
      return `Confidence: ${Math.round(event.confidence * 100)}%`;
    } else if (event.type === 'motion' && event.duration_seconds) {
      return `Duration: ${Math.round(event.duration_seconds)}s`;
    }
    return '';
  };

  const getEventIcon = (event) => {
    if (event.type === 'face') {
      return '👤';
    } else if (event.type === 'motion') {
      // Prioritize video recording over snapshot
      if (event.recording_id || event.hasRecording) {
        return '📹'; // Motion with video
      } else if (event.snapshot_path || event.hasSnapshot) {
        return '📷'; // Motion with snapshot only
      } else {
        return '🔍'; // Motion detection only (no media)
      }
    }
    return '❓'; // Unknown event type
  };

  return (
    <div className="live-dashboard">
      {/* Global Status Bar */}
      <div className="global-status-bar">
        <div className="status-indicator">
          <span className="status-icon">✓</span>
          <span className="status-text">{systemStatus}</span>
        </div>
        <Button
          variant="secondary"
          size="small"
          onClick={toggleTimeline}
          aria-label={showTimeline ? 'Hide Timeline' : 'Show Timeline'}
          icon={showTimeline ? '›' : '‹'}
        >
          {showTimeline ? 'Hide Events' : 'Show Events'}
        </Button>
      </div>

      <div className="dashboard-container">
        {/* Camera Grid - Main Content */}
        <div className={`camera-grid-container ${showTimeline ? 'with-timeline' : 'full-width'}`}>
          <div className="camera-grid-header">
            <h2 className="section-title">Live Cameras</h2>

            {/* Camera Size Selector */}
            <div className="camera-size-selector">
              <span className="size-label">Size:</span>
              <Button
                variant={cameraSize === 'small' ? 'primary' : 'secondary'}
                size="small"
                onClick={() => handleSizeChange('small')}
                title="Small (fits more cameras)"
              >
                Small
              </Button>
              <Button
                variant={cameraSize === 'medium' ? 'primary' : 'secondary'}
                size="small"
                onClick={() => handleSizeChange('medium')}
                title="Medium (balanced view)"
              >
                Medium
              </Button>
              <Button
                variant={cameraSize === 'large' ? 'primary' : 'secondary'}
                size="small"
                onClick={() => handleSizeChange('large')}
                title="Large (more detail)"
              >
                Large
              </Button>
              <Button
                variant={cameraSize === 'xl' ? 'primary' : 'secondary'}
                size="small"
                onClick={() => handleSizeChange('xl')}
                title="Extra Large (maximum detail)"
              >
                XL
              </Button>
            </div>
          </div>

          {camerasLoading ? (
            <div className={`camera-grid camera-grid-${cameraSize}`}>
              {Array.from({ length: 4 }).map((_, index) => (
                <SkeletonCameraCard key={index} />
              ))}
            </div>
          ) : cameras.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">📹</span>
              <p>No cameras configured</p>
              <a href="/cameras" className="btn-primary">Add Camera</a>
            </div>
          ) : (
            <div className={`camera-grid camera-grid-${cameraSize}`}>
              {cameras.map((camera) => (
                <CameraCard
                  key={camera.camera_id}
                  camera={camera}
                  onScreenshot={handleScreenshot}
                  onPipToggle={handlePipToggle}
                  onFullscreenToggle={handleFullscreenToggle}
                  onSettingsClick={setSettingsCamera}
                  isPipActive={pipCamera?.camera_id === camera.camera_id}
                  isFullscreenActive={fullscreenCamera?.camera_id === camera.camera_id}
                  flashingCamera={flashingCamera}
                  screenshotFeedback={screenshotFeedback}
                />
              ))}
            </div>
          )}
        </div>

        {/* Event Timeline - Right Panel */}
        {showTimeline && (
          <aside className="event-timeline">
            <h3 className="timeline-title">Recent Events</h3>
            <div className="timeline-list">
              {eventsLoading ? (
                <SkeletonEventTimeline count={5} />
              ) : !Array.isArray(events) || events.length === 0 ? (
                <div className="timeline-empty">
                  <span>🔔</span>
                  <p>No recent events</p>
                </div>
              ) : (
                events.map((event, index) => (
                  <div
                    key={event.id || index}
                    className={`timeline-item ${event.recording_id || event.snapshot_path || event.hasSnapshot ? 'clickable' : ''}`}
                    onClick={() => handleEventClick(event)}
                    title={
                      event.recording_id
                        ? 'Click to view recording'
                        : event.snapshot_path || event.hasSnapshot
                        ? 'Click to view snapshot'
                        : ''
                    }
                  >
                    <div className="event-icon">
                      {getEventIcon(event)}
                    </div>
                    <div className="event-details">
                      <p className="event-title">
                        {formatEventTitle(event)}
                      </p>
                      <p className="event-subtitle">
                        {formatEventSubtitle(event)}
                      </p>
                      <p className="event-camera">{event.camera_id}</p>
                      <p className="event-time">
                        {formatTimestampShort(event.timestamp)}
                      </p>
                      {event.recording_id && (
                        <span className="event-badge">📹 Recording Available</span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Event Detail Modal */}
      {showEventModal && selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          onClose={closeEventModal}
          onDelete={handleEventDelete}
        />
      )}

      {/* Native Picture-in-Picture Video Element (Hidden) */}
      {pipCamera && (
        <PipVideoPlayer
          camera={pipCamera}
          onReady={handlePipVideoReady}
          onClose={closePip}
        />
      )}

      {/* Fullscreen Camera Viewer */}
      {fullscreenCamera && (
        <div className="fullscreen-overlay" onClick={closeFullscreen}>
          <div className="fullscreen-container" onClick={(e) => e.stopPropagation()}>
            <div className="fullscreen-header">
              <div className="fullscreen-title">
                <span className="fullscreen-icon">⛶</span>
                <span>{fullscreenCamera.name || fullscreenCamera.camera_id}</span>
              </div>
              <button className="fullscreen-close" onClick={closeFullscreen} title="Exit Fullscreen (ESC)">
                ×
              </button>
            </div>

            <div className="fullscreen-content">
              {fullscreenCamera.is_active ? (
                <img
                  src={`/api/cameras/${fullscreenCamera.camera_id}/stream`}
                  alt={`${fullscreenCamera.name} fullscreen feed`}
                  className="fullscreen-feed"
                  onError={(e) => {
                    e.target.onerror = null;
                    e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080"%3E%3Crect fill="%23222" width="1920" height="1080"/%3E%3Ctext fill="%23fff" font-size="32" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EStream Unavailable%3C/text%3E%3C/svg%3E';
                  }}
                />
              ) : (
                <div className="fullscreen-offline">
                  <span>📡</span>
                  <p>Camera Offline</p>
                </div>
              )}
            </div>

            <div className="fullscreen-footer">
              <div className="fullscreen-status">
                <span className={`fullscreen-status-badge ${fullscreenCamera.is_active ? 'active' : 'inactive'}`}>
                  {fullscreenCamera.is_active ? '🔴 Live' : '⚫ Offline'}
                </span>
              </div>
              <div className="fullscreen-info">
                <span className="fullscreen-info-item">
                  🎥 {fullscreenCamera.resolution || 'Unknown'}
                </span>
                <span className="fullscreen-info-item">
                  {fullscreenCamera.motion_detection ? '🔍 Motion: ON' : '🔍 Motion: OFF'}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Camera Settings Modal */}
      {settingsCamera && (
        <CameraSettingsModal
          camera={settingsCamera}
          onClose={() => setSettingsCamera(null)}
          onUpdate={refetchCameras}
        />
      )}
    </div>
  );
};

export default LiveDashboard;
