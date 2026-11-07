// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { activateOnKey } from '../utils/a11y';
import { logger } from '../utils/logger';
import { formatTimestampShort } from '../utils/dateUtils';
import apiClient, { isAuthenticated } from '../api/apiClient';
import PipVideoPlayer from '../components/PipVideoPlayer';
import CameraSettingsModal from '../components/CameraSettingsModal';
import PTZControl from '../components/PTZControl';
import EventDetailModal from '../components/EventDetailModal';
import Button from '../components/universal/Button';
import { useCachedApi, useCachedApiMultiple } from '../hooks/useCachedApi';
import { CacheTTL } from '../services/apiCache';
import LoadingSkeleton, { SkeletonCameraCard, SkeletonEventTimeline } from '../components/LoadingSkeleton';
import AudioModal from '../components/AudioModal';
import './LiveDashboard.css';
import { describeApiError } from '../utils/apiError';

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
  screenshotFeedback,
  onRefresh,
  isRefreshing,
  streamNonce,
  refreshResult,
  onAudioClick,
  isStreamUnavailable,
  onStreamError,
  isQuickPtzOpen,
  onQuickPtzToggle,
  onOpenPtzModal,
  onQuickPtzMove,
  onQuickPtzHome
}) => {
  const isLive = Boolean(camera.is_active && camera.is_running && !isStreamUnavailable);

  return (
    <div key={camera.camera_id} className="camera-card">
      {/*
        Gate the stream on is_running and stream health, not is_active alone.
        When a camera disconnects or its MJPEG stream drops, transition cleanly
        to the Unavailable card until the camera becomes available again.
      */}
      <div className="camera-header">
        <h3>{camera.name || camera.camera_id}</h3>
        <button
          type="button"
          className={`status-badge status-badge--action ${isLive ? 'active' : 'inactive'}`}
          onClick={() => onRefresh && onRefresh(camera)}
          disabled={isRefreshing}
          title={`Reconnect ${camera.name || camera.camera_id} — refreshes only this camera`}
          aria-label={`Reconnect ${camera.name || camera.camera_id}`}
        >
          {isRefreshing
            ? '⏳ Reconnecting…'
            : !camera.is_active ? 'Disabled'
            : isLive ? 'Live' : 'Unavailable'}
        </button>
      </div>
      <div className="camera-feed">
        {isLive ? (
          <img
            // key + nonce force a remount so the browser drops the stalled
            // multipart response; changing the attribute alone would not.
            key={`${camera.camera_id}-${streamNonce || 0}`}
            src={`/api/cameras/${camera.camera_id}/stream${streamNonce ? `?t=${streamNonce}` : ''}`}
            alt={`${camera.name} feed`}
            className="feed-image"
            onError={() => {
              if (onStreamError) onStreamError(camera.camera_id);
            }}
          />
        ) : (
          <div className="feed-offline">
            <span>📡</span>
            <p>{!camera.is_active ? 'Camera Disabled' : 'Camera Unavailable'}</p>
            {camera.is_active && (
              <small>
                Stream is currently unavailable and will resume automatically when
                the camera is reachable again, or click Unavailable above to reconnect now.
              </small>
            )}
          </div>
        )}

        {/* Direct Manual PTZ HUD Overlay on the Main Dashboard card */}
        {isQuickPtzOpen && (
          <div className="dashboard-ptz-hud" onClick={(e) => e.stopPropagation()}>
            <div className="dashboard-ptz-hud-header">
              <span>🎮 Manual PTZ</span>
              <div className="dashboard-ptz-hud-actions">
                <button
                  type="button"
                  className="dashboard-ptz-studio-btn"
                  onClick={() => onOpenPtzModal && onOpenPtzModal(camera)}
                  title="Open full PTZ Studio with Presets, Patrols & Live Reticle"
                >
                  🎛️ Full PTZ…
                </button>
                <button
                  type="button"
                  className="dashboard-ptz-close-btn"
                  onClick={() => onQuickPtzToggle && onQuickPtzToggle(camera.camera_id)}
                  title="Hide on-card PTZ controls"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="dashboard-ptz-controls-row">
              <div className="dashboard-ptz-pad">
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, -1.0, 1.0, 0)} title="Pan Left + Tilt Up">↖</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 0, 1.0, 0)} title="Tilt Up">↑</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 1.0, 1.0, 0)} title="Pan Right + Tilt Up">↗</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, -1.0, 0, 0)} title="Pan Left">←</button>
                <button type="button" className="home-btn" onClick={() => onQuickPtzHome(camera.camera_id)} title="Home Position">🏠</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 1.0, 0, 0)} title="Pan Right">→</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, -1.0, -1.0, 0)} title="Pan Left + Tilt Down">↙</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 0, -1.0, 0)} title="Tilt Down">↓</button>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 1.0, -1.0, 0)} title="Pan Right + Tilt Down">↘</button>
              </div>
              <div className="dashboard-ptz-zoom">
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 0, 0, 0.5)} title="Zoom In">＋</button>
                <span>Zoom</span>
                <button type="button" onClick={() => onQuickPtzMove(camera.camera_id, 0, 0, -0.5)} title="Zoom Out">－</button>
              </div>
            </div>
          </div>
        )}

        {/* Result of the last reconnect for THIS camera. Without it a correctly
            failing reconnect is indistinguishable from a button that does
            nothing — which is exactly how it was reported. */}
        {refreshResult && (
          <div
            className={`reconnect-result ${refreshResult.ok ? 'ok' : 'failed'}`}
            role="status"
            aria-live="polite"
          >
            {refreshResult.ok ? '✅ ' : '⚠️ '}{refreshResult.message}
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
          variant={isQuickPtzOpen ? 'primary' : 'secondary'}
          size="small"
          onClick={() => onQuickPtzToggle && onQuickPtzToggle(camera.camera_id)}
          title="Toggle manual Pan / Tilt / Zoom controls on this camera feed"
          aria-label={`Pan, Tilt, and Zoom ${camera.name || camera.camera_id}`}
          disabled={!camera.is_active}
          icon="🎮"
        >
          PTZ
        </Button>
        <Button
          variant="secondary"
          size="small"
          onClick={() => onAudioClick(camera)}
          title="Two-way audio"
          aria-label={`Start two-way audio with ${camera.name || camera.camera_id}`}
          disabled={!camera.is_running}
          icon="🎤"
        >
          Audio
        </Button>
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
  // systemStatus removed - now shown in MainLayout header only
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

  // camera_id currently reconnecting, so its badge can show progress. A sleeping
  // phone takes seconds to come back and the control must not look inert.
  const [refreshingCamera, setRefreshingCamera] = useState(null);

  // Outcome of the last reconnect: { camera_id, ok, message }. Shown on the card
  // so a failure explains itself instead of looking like a dead button.
  const [refreshResult, setRefreshResult] = useState(null);

  // Camera whose two-way audio modal is open, or null.
  const [audioCamera, setAudioCamera] = useState(null);

  // Direct PTZ controls on the Main Dashboard & Fullscreen: per-card inline HUD + full PTZ modal
  const [quickPtzOpen, setQuickPtzOpen] = useState({});
  const [showFullscreenPtz, setShowFullscreenPtz] = useState(true);
  const [showFullscreenReticle, setShowFullscreenReticle] = useState(false);
  const [ptzModalCamera, setPtzModalCamera] = useState(null);
  const ptzBusyRef = useRef({});
  const ptzPendingRef = useRef({});

  const handleQuickPtzToggle = useCallback((cameraId) => {
    setQuickPtzOpen((prev) => ({ ...prev, [cameraId]: !prev[cameraId] }));
  }, []);

  const handleQuickPtzMove = useCallback(async (cameraId, panDelta, tiltDelta, zoomDelta = 0) => {
    if (ptzBusyRef.current[cameraId]) {
      ptzPendingRef.current[cameraId] = { panDelta, tiltDelta, zoomDelta };
      return;
    }
    ptzBusyRef.current[cameraId] = true;
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/move/relative`, {
        pan_delta: panDelta * 0.85,
        tilt_delta: tiltDelta * 0.85,
        zoom_delta: zoomDelta * 0.85,
        speed: 0.85,
      });
    } catch (err) {
      logger.error('Quick PTZ move failed:', err);
      setRefreshResult({
        camera_id: cameraId,
        ok: false,
        message: describeApiError(err, 'PTZ move failed.'),
      });
    } finally {
      ptzBusyRef.current[cameraId] = false;
      const next = ptzPendingRef.current[cameraId];
      if (next) {
        delete ptzPendingRef.current[cameraId];
        handleQuickPtzMove(cameraId, next.panDelta, next.tiltDelta, next.zoomDelta);
      }
    }
  }, []);

  const handleQuickPtzHome = useCallback(async (cameraId) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/home`, null, {
        params: { speed: 0.85 },
      });
    } catch (err) {
      logger.error('Quick PTZ home failed:', err);
      setRefreshResult({
        camera_id: cameraId,
        ok: false,
        message: describeApiError(err, 'PTZ Home failed.'),
      });
    }
  }, []);

  // Per-camera cache-buster for the MJPEG <img>. Reconnecting server-side is not
  // enough on its own: the browser holds an open multipart response and will keep
  // painting the stalled one unless the src changes.
  const [streamNonce, setStreamNonce] = useState({});

  // Tracks cameras whose MJPEG <img> encountered a stream/network error so the
  // card switches immediately to the Unavailable state until the camera recovers.
  const [streamUnavailable, setStreamUnavailable] = useState({});

  const handleStreamError = useCallback((cameraId) => {
    setStreamUnavailable((prev) => (
      prev[cameraId] ? prev : { ...prev, [cameraId]: true }
    ));
  }, []);

  // Poll camera status silently in the background while any active camera is
  // unavailable. Do NOT call refetchCameras() on every tick because useCachedApi's
  // refetch sets camerasLoading=true, which would unmount running <CameraCard>
  // components and sever live MJPEG streams (ERR_INCOMPLETE_CHUNKED_ENCODING).
  useEffect(() => {
    if (!isAuthenticated()) return undefined;
    const hasUnavailable = cameras.some(
      (c) => c.is_active && (!c.is_running || streamUnavailable[c.camera_id])
    );
    if (!hasUnavailable) return undefined;

    const timer = setInterval(async () => {
      try {
        const res = await apiClient.get('/cameras/');
        const list = res.data?.cameras || [];
        let statusChanged = false;
        list.forEach((cam) => {
          const prevCam = cameras.find((c) => c.camera_id === cam.camera_id);
          if (prevCam && Boolean(prevCam.is_running) !== Boolean(cam.is_running)) {
            statusChanged = true;
          }
          if (cam.is_active && cam.is_running && streamUnavailable[cam.camera_id]) {
            setStreamUnavailable((prev) => {
              const next = { ...prev };
              delete next[cam.camera_id];
              return next;
            });
            setStreamNonce((prev) => ({ ...prev, [cam.camera_id]: Date.now() }));
          }
        });
        if (statusChanged) {
          await refetchCameras();
        }
      } catch (e) {
        // Keep Unavailable card displayed while backend/camera is unreachable
      }
    }, 8000);

    return () => clearInterval(timer);
  }, [cameras, streamUnavailable, refetchCameras]);

  const handleRefreshCamera = useCallback(async (camera) => {
    const id = camera.camera_id;
    setRefreshingCamera(id);
    setRefreshResult(null);
    try {
      const res = await apiClient.post(`/cameras/${id}/reconnect`);
      const connected = !!res.data?.connected;

      setRefreshResult({
        camera_id: id,
        ok: connected,
        message: res.data?.message
          || (connected ? 'Reconnected.' : 'Camera did not come back.'),
      });

      await refetchCameras();
      if (connected) {
        setStreamUnavailable((prev) => {
          const next = { ...prev };
          delete next[id];
          return next;
        });
        setStreamNonce((prev) => ({ ...prev, [id]: Date.now() }));
      }
    } catch (err) {
      setRefreshResult({
        camera_id: id,
        ok: false,
        message: describeApiError(err, 'Reconnect failed.'),
      });
    } finally {
      setRefreshingCamera(null);
    }
  }, [refetchCameras]);

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
      // Video recordings (highest priority - most useful for review)
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
        priority: 1, // Highest priority
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
        priority: 2, // Medium priority
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
        priority: 3, // Lower priority (often duplicates motion)
      }))
    ];

    // Sort by timestamp (most recent first)
    allEvents.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    // Deduplicate events: remove events from same camera within 5 seconds of each other
    // Keep the highest priority event (recordings > motion snapshots > face detections)
    const DEDUP_WINDOW_MS = 5000; // 5 seconds
    const deduplicatedEvents = [];

    for (const event of allEvents) {
      const eventTime = new Date(event.timestamp).getTime();

      // Check if there's already a similar event in the deduplicated list
      const isDuplicate = deduplicatedEvents.some(existing => {
        // Must be same camera
        if (existing.camera_id !== event.camera_id) return false;

        // Check time window
        const existingTime = new Date(existing.timestamp).getTime();
        const timeDiff = Math.abs(eventTime - existingTime);

        if (timeDiff <= DEDUP_WINDOW_MS) {
          // Within time window - this is a potential duplicate
          // Keep if existing has higher priority (lower number)
          return existing.priority <= event.priority;
        }

        return false;
      });

      if (!isDuplicate) {
        deduplicatedEvents.push(event);
      }
    }

    // Take top 15 after deduplication
    return deduplicatedEvents.slice(0, 15);
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

  // Handle ESC and Arrow keys inside Fullscreen Camera Viewer
  useEffect(() => {
    const handleFullscreenKeys = (e) => {
      if (!fullscreenCamera) return;
      const camId = fullscreenCamera.camera_id;
      if (e.key === 'Escape') {
        closeFullscreen();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        handleQuickPtzMove(camId, 0, 1.0, 0);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        handleQuickPtzMove(camId, 0, -1.0, 0);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handleQuickPtzMove(camId, -1.0, 0, 0);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleQuickPtzMove(camId, 1.0, 0, 0);
      } else if (e.key === 'Home') {
        e.preventDefault();
        handleQuickPtzHome(camId);
      }
    };

    if (fullscreenCamera) {
      document.addEventListener('keydown', handleFullscreenKeys);
      return () => document.removeEventListener('keydown', handleFullscreenKeys);
    }
  }, [fullscreenCamera, handleQuickPtzMove, handleQuickPtzHome]);

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
        message: describeApiError(error, 'Failed to capture screenshot')
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

          {camerasLoading && cameras.length === 0 ? (
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
                  onRefresh={handleRefreshCamera}
                  isRefreshing={refreshingCamera === camera.camera_id}
                  streamNonce={streamNonce[camera.camera_id]}
                  refreshResult={
                    refreshResult?.camera_id === camera.camera_id ? refreshResult : null
                  }
                  onAudioClick={setAudioCamera}
                  isStreamUnavailable={!!streamUnavailable[camera.camera_id]}
                  onStreamError={handleStreamError}
                  isQuickPtzOpen={!!quickPtzOpen[camera.camera_id]}
                  onQuickPtzToggle={handleQuickPtzToggle}
                  onOpenPtzModal={setPtzModalCamera}
                  onQuickPtzMove={handleQuickPtzMove}
                  onQuickPtzHome={handleQuickPtzHome}
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
                    onKeyDown={activateOnKey(() => handleEventClick(event))}
                    role="button"
                    tabIndex={0}
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

      {/* Fullscreen Camera Viewer with Integrated Interactive PTZ HUD */}
      {fullscreenCamera && (
        <div className="fullscreen-overlay" onClick={closeFullscreen}>
          <div className="fullscreen-container" onClick={(e) => e.stopPropagation()}>
            <div className="fullscreen-header">
              <div className="fullscreen-title">
                <span className="fullscreen-icon">⛶</span>
                <span>{fullscreenCamera.name || fullscreenCamera.camera_id}</span>
                <span style={{ fontSize: '12px', opacity: 0.75, marginLeft: '10px', fontWeight: 400 }}>
                  (Arrow keys ↑↓←→ or PTZ pad to steer)
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Button
                  variant={showFullscreenPtz ? 'primary' : 'secondary'}
                  size="small"
                  onClick={() => setShowFullscreenPtz((v) => !v)}
                  icon="🎮"
                  title="Toggle on-screen Pan/Tilt/Zoom controls in Fullscreen"
                >
                  {showFullscreenPtz ? 'Hide PTZ Pad' : 'Show PTZ Pad'}
                </Button>
                <Button
                  variant={showFullscreenReticle ? 'primary' : 'secondary'}
                  size="small"
                  onClick={() => setShowFullscreenReticle((v) => !v)}
                  icon="🎯"
                  title="Toggle center crosshair reticle"
                >
                  Reticle
                </Button>
                <Button
                  variant="secondary"
                  size="small"
                  onClick={() => handleScreenshot(fullscreenCamera)}
                  icon="📸"
                  title="Capture Screenshot"
                >
                  Screenshot
                </Button>
                <button className="fullscreen-close" onClick={closeFullscreen} title="Exit Fullscreen (ESC)">
                  ×
                </button>
              </div>
            </div>

            <div className="fullscreen-content" style={{ position: 'relative' }}>
              {fullscreenCamera.is_active && fullscreenCamera.is_running && !streamUnavailable[fullscreenCamera.camera_id] ? (
                <>
                  <img
                    key={`${fullscreenCamera.camera_id}-${streamNonce[fullscreenCamera.camera_id] || 0}`}
                    src={`/api/cameras/${fullscreenCamera.camera_id}/stream${streamNonce[fullscreenCamera.camera_id] ? `?t=${streamNonce[fullscreenCamera.camera_id]}` : ''}`}
                    alt={`${fullscreenCamera.name} fullscreen feed`}
                    className="fullscreen-feed"
                    onError={() => handleStreamError(fullscreenCamera.camera_id)}
                  />
                  {showFullscreenReticle && (
                    <div className="ptz-reticle" aria-hidden="true">
                      <div className="ptz-reticle-h" />
                      <div className="ptz-reticle-v" />
                      <div className="ptz-reticle-ring" />
                    </div>
                  )}
                  {/* On-video translucent edge directional buttons in Fullscreen */}
                  {showFullscreenPtz && (
                    <div className="ptz-video-hud">
                      <button
                        type="button"
                        className="ptz-hud-edge up"
                        onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, 1.0, 0)}
                        title="Tilt Up (ArrowUp)"
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        className="ptz-hud-edge down"
                        onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, -1.0, 0)}
                        title="Tilt Down (ArrowDown)"
                      >
                        ▼
                      </button>
                      <button
                        type="button"
                        className="ptz-hud-edge left"
                        onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, -1.0, 0, 0)}
                        title="Pan Left (ArrowLeft)"
                      >
                        ◀
                      </button>
                      <button
                        type="button"
                        className="ptz-hud-edge right"
                        onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 1.0, 0, 0)}
                        title="Pan Right (ArrowRight)"
                      >
                        ▶
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div className="fullscreen-offline">
                  <span>📡</span>
                  <p>{!fullscreenCamera.is_active ? 'Camera Disabled' : 'Camera Unavailable'}</p>
                </div>
              )}

              {/* Floating Fullscreen PTZ D-Pad + Zoom Overlay */}
              {showFullscreenPtz && (
                <div
                  className="dashboard-ptz-hud"
                  style={{ bottom: '18px', right: '18px', zIndex: 20 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="dashboard-ptz-hud-header">
                    <span>🎮 Fullscreen PTZ</span>
                    <div className="dashboard-ptz-hud-actions">
                      <button
                        type="button"
                        className="dashboard-ptz-studio-btn"
                        onClick={() => {
                          const cam = fullscreenCamera;
                          setFullscreenCamera(null);
                          setPtzModalCamera(cam);
                        }}
                        title="Open Full PTZ Studio with Presets & Patrols"
                      >
                        🎛️ Presets / Studio…
                      </button>
                      <button
                        type="button"
                        className="dashboard-ptz-close-btn"
                        onClick={() => setShowFullscreenPtz(false)}
                        title="Hide Fullscreen PTZ Pad"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                  <div className="dashboard-ptz-controls-row">
                    <div className="dashboard-ptz-pad">
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, -1.0, 1.0, 0)} title="Pan Left + Tilt Up">↖</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, 1.0, 0)} title="Tilt Up (ArrowUp)">↑</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 1.0, 1.0, 0)} title="Pan Right + Tilt Up">↗</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, -1.0, 0, 0)} title="Pan Left (ArrowLeft)">←</button>
                      <button type="button" className="home-btn" onClick={() => handleQuickPtzHome(fullscreenCamera.camera_id)} title="Home Position (Home)">🏠</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 1.0, 0, 0)} title="Pan Right (ArrowRight)">→</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, -1.0, -1.0, 0)} title="Pan Left + Tilt Down">↙</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, -1.0, 0)} title="Tilt Down (ArrowDown)">↓</button>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 1.0, -1.0, 0)} title="Pan Right + Tilt Down">↘</button>
                    </div>
                    <div className="dashboard-ptz-zoom">
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, 0, 0.5)} title="Zoom In">＋</button>
                      <span>Zoom</span>
                      <button type="button" onClick={() => handleQuickPtzMove(fullscreenCamera.camera_id, 0, 0, -0.5)} title="Zoom Out">－</button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="fullscreen-footer">
              <div className="fullscreen-status">
                <span className={`fullscreen-status-badge ${fullscreenCamera.is_active && fullscreenCamera.is_running && !streamUnavailable[fullscreenCamera.camera_id] ? 'active' : 'inactive'}`}>
                  {fullscreenCamera.is_active && fullscreenCamera.is_running && !streamUnavailable[fullscreenCamera.camera_id] ? '🔴 Live' : '⚫ Unavailable'}
                </span>
                <Button
                  variant="secondary"
                  size="small"
                  onClick={() => setShowFullscreenPtz((v) => !v)}
                  icon="🕹️"
                  title="Show or hide the interactive PTZ D-pad in Fullscreen"
                >
                  {showFullscreenPtz ? 'Hide PTZ Pad' : 'Show PTZ Pad'}
                </Button>
                <Button
                  variant="secondary"
                  size="small"
                  onClick={() => {
                    const cam = fullscreenCamera;
                    setFullscreenCamera(null);
                    setPtzModalCamera(cam);
                  }}
                  icon="🎛️"
                  title="Open Full PTZ Control Studio with Presets, Patrols & Live Viewer"
                >
                  Full PTZ Studio
                </Button>
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

      {/* Direct PTZ Control Modal with Integrated Live Camera Viewer */}
      {ptzModalCamera && (
        <div
          className="dashboard-ptz-modal-overlay"
          onClick={() => setPtzModalCamera(null)}
        >
          <div
            className="dashboard-ptz-modal-container"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="dashboard-ptz-modal-close"
              onClick={() => setPtzModalCamera(null)}
              title="Close PTZ Studio"
            >
              ✕ Close
            </button>
            <PTZControl
              cameraId={ptzModalCamera.camera_id}
              cameraName={ptzModalCamera.name || ptzModalCamera.camera_id}
              showViewerByDefault={true}
            />
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

      {/* Two-way audio. Previously reachable in one click only from the dead
          DashboardPage; this restores that shortcut on the dashboard people
          actually use. */}
      {audioCamera && (
        <AudioModal
          isOpen={true}
          onClose={() => setAudioCamera(null)}
          cameraId={audioCamera.camera_id}
          cameraName={audioCamera.name || audioCamera.camera_id}
        />
      )}
    </div>
  );
};

export default LiveDashboard;
