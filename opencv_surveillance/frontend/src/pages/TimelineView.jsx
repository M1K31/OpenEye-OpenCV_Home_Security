// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { activateOnKey } from '../utils/a11y';
import { logger } from '../utils/logger';
import apiClient from '../api/apiClient';
import { Button } from '../components/universal';
import './TimelineView.css';

/**
 * Timeline Playback View
 *
 * Multi-camera timeline interface with synchronized playback
 * Features:
 * - Horizontal time axis with zoom controls
 * - Multiple camera lanes
 * - Event markers (motion, face, recording)
 * - Scrubber for seeking
 * - Synchronized playback across cameras
 * 
 * Performance optimizations (v3.10.1):
 * - Memoized calculations to prevent expensive re-renders
 * - Debounced data loading
 * - Simplified playback state machine to prevent race conditions
 * - Limited initial data load
 */
const TimelineView = () => {
  // Time range state
  const [timeRange, setTimeRange] = useState({
    start: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24 hours
    end: new Date()
  });

  // Timeline data
  const [lanes, setLanes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Playback state
  const [currentTime, setCurrentTime] = useState(new Date());
  const [playing, setPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1.0);
  const [currentEventIndex, setCurrentEventIndex] = useState(-1); // Track current event by index for reliable sequencing

  // UI state
  const [timeInterval, setTimeInterval] = useState('1h'); // '5m', '15m', '30m', '1h'
  const [use24Hour, setUse24Hour] = useState(false); // Toggle between 12hr and 24hr format
  const [hoveredEvent, setHoveredEvent] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [playbackMedia, setPlaybackMedia] = useState(null); // Currently playing video/snapshot

  // Scrollable timeline state
  const [scrollOffset, setScrollOffset] = useState(0); // Horizontal scroll offset in pixels
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartX, setDragStartX] = useState(0);
  const [dragStartOffset, setDragStartOffset] = useState(0);

  // Refs
  const timelineRef = useRef(null);
  const timelineCanvasRef = useRef(null);
  const playbackTimeoutRef = useRef(null);
  const isPlayingRef = useRef(false); // Ref to track playing state without re-renders
  const loadTimeoutRef = useRef(null); // Debounce data loading

  // Progress tracking for sequential playback
  const [playbackProgress, setPlaybackProgress] = useState({ current: 0, total: 0 });

  // Camera filter
  const [selectedCameras, setSelectedCameras] = useState([]);
  const [availableCameras, setAvailableCameras] = useState([]);

  // Load timeline data with debouncing
  useEffect(() => {
    // Clear any pending load
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
    }

    // Debounce data loading to prevent excessive API calls
    loadTimeoutRef.current = setTimeout(() => {
      loadTimelineData();
    }, 300);

    return () => {
      if (loadTimeoutRef.current) {
        clearTimeout(loadTimeoutRef.current);
      }
    };
  }, [timeRange, selectedCameras]);

  // Load cameras once on mount
  useEffect(() => {
    loadCameras();
  }, []);

  // Keyboard shortcuts for timeline navigation
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ignore if typing in an input
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case ' ': // Space - Play/Pause
          e.preventDefault();
          togglePlayback();
          break;
        case 'ArrowLeft': // Left - Previous event
          e.preventDefault();
          handlePreviousEvent();
          break;
        case 'ArrowRight': // Right - Next event
          e.preventDefault();
          handleNextEvent();
          break;
        case 'ArrowUp': // Up - Increase speed
          e.preventDefault();
          {
            const speeds = [0.5, 1, 2, 4, 8];
            const currentIdx = speeds.indexOf(playbackSpeed);
            if (currentIdx < speeds.length - 1) {
              handleSpeedChange(speeds[currentIdx + 1]);
            }
          }
          break;
        case 'ArrowDown': // Down - Decrease speed
          e.preventDefault();
          {
            const speeds = [0.5, 1, 2, 4, 8];
            const currentIdx = speeds.indexOf(playbackSpeed);
            if (currentIdx > 0) {
              handleSpeedChange(speeds[currentIdx - 1]);
            }
          }
          break;
        case 'Escape': // Escape - Stop playback
          e.preventDefault();
          stopPlayback();
          break;
        case 'l': // L - Jump to live
        case 'L':
          e.preventDefault();
          jumpToNow();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [playbackSpeed]);

  // Memoize sorted events to prevent recalculation on every render
  const sortedEvents = useMemo(() => {
    return lanes.flatMap(lane => lane.events)
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }, [lanes]);

  // Handle video end or move to next image
  const advanceToNextEvent = useCallback(() => {
    if (!isPlayingRef.current) return;

    const nextIndex = currentEventIndex + 1;
    if (nextIndex >= sortedEvents.length) {
      // No more events - stop playback
      setPlaying(false);
      isPlayingRef.current = false;
      setPlaybackMedia(null);
      return;
    }

    const nextEvent = sortedEvents[nextIndex];
    const eventTime = new Date(nextEvent.timestamp);

    // Check if event is beyond time range
    if (eventTime > timeRange.end) {
      setPlaying(false);
      isPlayingRef.current = false;
      setPlaybackMedia(null);
      setCurrentTime(timeRange.end);
      return;
    }

    // Update state
    setCurrentEventIndex(nextIndex);
    setCurrentTime(eventTime);
    setSelectedEvent(nextEvent);
    setPlaybackProgress({ current: nextIndex + 1, total: sortedEvents.length });

    // Set media for display
    if (nextEvent.video_path && nextEvent.recording_id) {
      const thumbnailUrl = nextEvent.thumbnail_path 
        ? (nextEvent.thumbnail_path.startsWith('/') 
            ? nextEvent.thumbnail_path 
            : `/data/snapshots/${nextEvent.thumbnail_path}`)
        : null;
      setPlaybackMedia({
        type: 'video',
        url: `/api/recordings/${nextEvent.recording_id}/download`,
        thumbnailUrl: thumbnailUrl,
        event: nextEvent
      });
      // Video will call handleVideoEnded when done
    } else if (nextEvent.thumbnail_path) {
      const snapshotUrl = nextEvent.thumbnail_path.startsWith('/') 
        ? nextEvent.thumbnail_path 
        : `/data/snapshots/${nextEvent.thumbnail_path}`;
      setPlaybackMedia({
        type: 'image',
        url: snapshotUrl,
        event: nextEvent
      });
      // Schedule next event after delay
      const baseDelay = 2000; // 2 seconds per image
      const delay = baseDelay / playbackSpeed;
      playbackTimeoutRef.current = setTimeout(() => advanceToNextEvent(), delay);
    } else {
      // No media, skip to next immediately
      playbackTimeoutRef.current = setTimeout(() => advanceToNextEvent(), 100);
    }
  }, [currentEventIndex, sortedEvents, timeRange, playbackSpeed]);

  // Start playback from current event index
  const startPlayback = useCallback(() => {
    if (sortedEvents.length === 0) {
      setPlaying(false);
      isPlayingRef.current = false;
      return;
    }

    // Find starting index - either current or find first event after currentTime
    let startIndex = currentEventIndex;
    if (startIndex < 0) {
      // Find first event at or after currentTime
      startIndex = sortedEvents.findIndex(e => new Date(e.timestamp) >= currentTime);
      if (startIndex < 0) {
        // All events are before current time, start from first event
        startIndex = 0;
      }
    }

    const event = sortedEvents[startIndex];
    const eventTime = new Date(event.timestamp);

    // Update state
    setCurrentEventIndex(startIndex);
    setCurrentTime(eventTime);
    setSelectedEvent(event);
    setPlaybackProgress({ current: startIndex + 1, total: sortedEvents.length });

    // Set media for display
    if (event.video_path && event.recording_id) {
      const thumbnailUrl = event.thumbnail_path 
        ? (event.thumbnail_path.startsWith('/') 
            ? event.thumbnail_path 
            : `/data/snapshots/${event.thumbnail_path}`)
        : null;
      setPlaybackMedia({
        type: 'video',
        url: `/api/recordings/${event.recording_id}/download`,
        thumbnailUrl: thumbnailUrl,
        event: event
      });
    } else if (event.thumbnail_path) {
      const snapshotUrl = event.thumbnail_path.startsWith('/') 
        ? event.thumbnail_path 
        : `/data/snapshots/${event.thumbnail_path}`;
      setPlaybackMedia({
        type: 'image',
        url: snapshotUrl,
        event: event
      });
      // Schedule next event
      const baseDelay = 2000;
      const delay = baseDelay / playbackSpeed;
      playbackTimeoutRef.current = setTimeout(() => advanceToNextEvent(), delay);
    }
  }, [currentEventIndex, sortedEvents, currentTime, playbackSpeed, advanceToNextEvent]);

  // Update video playback speed when it changes
  useEffect(() => {
    const videoElement = document.querySelector('.media-video');
    if (videoElement) {
      videoElement.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  // Playback control - start/stop playback
  useEffect(() => {
    if (playing) {
      isPlayingRef.current = true;
      startPlayback();
    } else {
      isPlayingRef.current = false;
      // Clear any pending timeouts
      if (playbackTimeoutRef.current) {
        clearTimeout(playbackTimeoutRef.current);
        playbackTimeoutRef.current = null;
      }
      // Pause video if playing
      const videoElement = document.querySelector('.media-video');
      if (videoElement) {
        videoElement.pause();
      }
    }

    return () => {
      if (playbackTimeoutRef.current) {
        clearTimeout(playbackTimeoutRef.current);
        playbackTimeoutRef.current = null;
      }
    };
  }, [playing]);

  // Handle video element play/pause (separate from playback control)
  useEffect(() => {
    const videoElement = document.querySelector('.media-video');
    if (videoElement && playbackMedia && playbackMedia.type === 'video' && playing) {
      videoElement.playbackRate = playbackSpeed;
      videoElement.play().catch(err => {
        logger.error('Video play error:', err);
        // If video fails to play, skip to next event
        if (isPlayingRef.current) {
          setTimeout(() => advanceToNextEvent(), 500);
        }
      });
    }
  }, [playbackMedia, playing, playbackSpeed, advanceToNextEvent]);

  const loadCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      const cameras = response.data?.cameras || [];
      setAvailableCameras(cameras.map(c => c.camera_id));
      if (selectedCameras.length === 0) {
        setSelectedCameras(cameras.map(c => c.camera_id));
      }
    } catch (err) {
      logger.error('Error loading cameras:', err);
    }
  };

  const loadTimelineData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = {
        start_time: timeRange.start.toISOString(),
        end_time: timeRange.end.toISOString(),
        limit: 500  // Limit events for performance
      };

      if (selectedCameras.length > 0 && selectedCameras.length < availableCameras.length) {
        params.camera_ids = selectedCameras.join(',');
      }

      const response = await apiClient.get('/timeline/view', { params });

      setLanes(response.data.lanes || []);
      // Reset event index when new data loads
      setCurrentEventIndex(-1);
    } catch (err) {
      logger.error('Error loading timeline:', err);
      setError('Failed to load timeline data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Time axis helpers - Scrollable ruler approach
  const PIXELS_PER_INTERVAL = 150; // Fixed spacing between time marks

  // Memoize interval calculation
  const intervalMs = useMemo(() => {
    return {
      '5m': 5 * 60 * 1000,
      '15m': 15 * 60 * 1000,
      '30m': 30 * 60 * 1000,
      '1h': 60 * 60 * 1000
    }[timeInterval];
  }, [timeInterval]);

  const getIntervalMs = () => intervalMs;

  // Memoize timeline width calculation
  const timelineWidth = useMemo(() => {
    const duration = timeRange.end - timeRange.start;
    const numIntervals = Math.ceil(duration / intervalMs);
    return numIntervals * PIXELS_PER_INTERVAL;
  }, [timeRange, intervalMs]);

  const getTimelineWidth = () => timelineWidth;

  // Memoize time axis marks calculation
  const timeAxisMarks = useMemo(() => {
    const marks = [];
    const startMs = timeRange.start.getTime();
    const roundedStart = Math.floor(startMs / intervalMs) * intervalMs;
    let current = new Date(roundedStart);

    while (current <= timeRange.end) {
      marks.push(new Date(current));
      current = new Date(current.getTime() + intervalMs);
    }

    return marks;
  }, [timeRange, intervalMs]);

  const getTimeAxisMarks = () => timeAxisMarks;

  const getTimePosition = (time) => {
    // Convert time to pixel position on timeline
    const intervalMs = getIntervalMs();
    const startMs = timeRange.start.getTime();
    const roundedStart = Math.floor(startMs / intervalMs) * intervalMs;
    const offset = time - roundedStart;
    const position = (offset / intervalMs) * PIXELS_PER_INTERVAL;
    return position - scrollOffset;
  };

  const getEventPosition = (eventTime) => {
    return getTimePosition(eventTime);
  };

  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragStartX(e.clientX);
    setDragStartOffset(scrollOffset);
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;

    const deltaX = dragStartX - e.clientX; // Reversed for intuitive drag
    const newOffset = dragStartOffset + deltaX;

    // Clamp scroll offset to valid range
    const maxOffset = Math.max(0, getTimelineWidth() - (window.innerWidth - 200));
    const clampedOffset = Math.max(0, Math.min(newOffset, maxOffset));

    setScrollOffset(clampedOffset);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const handleSeek = (e) => {
    if (isDragging) return; // Don't seek while dragging

    const rect = timelineCanvasRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;

    // Convert click position to time
    const intervalMs = getIntervalMs();
    const startMs = timeRange.start.getTime();
    const roundedStart = Math.floor(startMs / intervalMs) * intervalMs;
    const clickOffset = (x + scrollOffset) / PIXELS_PER_INTERVAL * intervalMs;
    const newTime = new Date(roundedStart + clickOffset);

    setCurrentTime(newTime);
  };

  // Add mouse event listeners
  useEffect(() => {
    const handleGlobalMouseMove = (e) => handleMouseMove(e);
    const handleGlobalMouseUp = () => handleMouseUp();

    if (isDragging) {
      document.addEventListener('mousemove', handleGlobalMouseMove);
      document.addEventListener('mouseup', handleGlobalMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleGlobalMouseMove);
      document.removeEventListener('mouseup', handleGlobalMouseUp);
    };
  }, [isDragging, dragStartX, dragStartOffset, scrollOffset]);

  const handleIntervalChange = (interval) => {
    setTimeInterval(interval);
  };

  const toggleTimeFormat = () => {
    setUse24Hour(!use24Hour);
  };

  const handlePreviousEvent = () => {
    // Use sortedEvents which is already memoized
    if (sortedEvents.length === 0) return;

    // Find previous event before current time
    let prevIndex = -1;
    for (let i = sortedEvents.length - 1; i >= 0; i--) {
      if (new Date(sortedEvents[i].timestamp) < currentTime) {
        prevIndex = i;
        break;
      }
    }

    if (prevIndex >= 0) {
      const prevEvent = sortedEvents[prevIndex];
      setCurrentEventIndex(prevIndex);
      setCurrentTime(new Date(prevEvent.timestamp));
      setSelectedEvent(prevEvent);

      // Load media for the event
      if (prevEvent.video_path && prevEvent.recording_id) {
        const thumbnailUrl = prevEvent.thumbnail_path 
          ? (prevEvent.thumbnail_path.startsWith('/') 
              ? prevEvent.thumbnail_path 
              : `/data/snapshots/${prevEvent.thumbnail_path}`)
          : null;
        setPlaybackMedia({
          type: 'video',
          url: `/api/recordings/${prevEvent.recording_id}/download`,
          thumbnailUrl: thumbnailUrl,
          event: prevEvent
        });
      } else if (prevEvent.thumbnail_path) {
        const snapshotUrl = prevEvent.thumbnail_path.startsWith('/') 
          ? prevEvent.thumbnail_path 
          : `/data/snapshots/${prevEvent.thumbnail_path}`;
        setPlaybackMedia({
          type: 'image',
          url: snapshotUrl,
          event: prevEvent
        });
      }
    }
  };

  const handleNextEvent = () => {
    // Use sortedEvents which is already memoized
    if (sortedEvents.length === 0) return;

    // Find next event after current time
    let nextIndex = -1;
    for (let i = 0; i < sortedEvents.length; i++) {
      if (new Date(sortedEvents[i].timestamp) > currentTime) {
        nextIndex = i;
        break;
      }
    }

    if (nextIndex >= 0) {
      const nextEvent = sortedEvents[nextIndex];
      setCurrentEventIndex(nextIndex);
      setCurrentTime(new Date(nextEvent.timestamp));
      setSelectedEvent(nextEvent);

      // Load media for the event
      if (nextEvent.video_path && nextEvent.recording_id) {
        const thumbnailUrl = nextEvent.thumbnail_path 
          ? (nextEvent.thumbnail_path.startsWith('/') 
              ? nextEvent.thumbnail_path 
              : `/data/snapshots/${nextEvent.thumbnail_path}`)
          : null;
        setPlaybackMedia({
          type: 'video',
          url: `/api/recordings/${nextEvent.recording_id}/download`,
          thumbnailUrl: thumbnailUrl,
          event: nextEvent
        });
      } else if (nextEvent.thumbnail_path) {
        const snapshotUrl = nextEvent.thumbnail_path.startsWith('/') 
          ? nextEvent.thumbnail_path 
          : `/data/snapshots/${nextEvent.thumbnail_path}`;
        setPlaybackMedia({
          type: 'image',
          url: snapshotUrl,
          event: nextEvent
        });
      }
    }
  };

  const togglePlayback = () => {
    setPlaying(!playing);
  };

  const stopPlayback = () => {
    setPlaying(false);
    setPlaybackMedia(null);
    setSelectedEvent(null);
    setCurrentEventIndex(-1);
  };

  const handleVideoEnded = useCallback(() => {
    // When a video ends during playback, continue to next event
    if (isPlayingRef.current) {
      advanceToNextEvent();
    }
  }, [advanceToNextEvent]);

  const handleSpeedChange = (speed) => {
    setPlaybackSpeed(speed);
    // Update video playback rate if video is currently playing
    const videoElement = document.querySelector('.media-video');
    if (videoElement) {
      videoElement.playbackRate = speed;
    }
  };

  const jumpToNow = () => {
    const now = new Date();
    const duration = timeRange.end - timeRange.start;
    setTimeRange({
      start: new Date(now.getTime() - duration),
      end: now
    });
    setCurrentTime(now);
  };

  const setTimeRangePreset = (hours) => {
    const now = new Date();
    setTimeRange({
      start: new Date(now.getTime() - hours * 60 * 60 * 1000),
      end: now
    });
    setCurrentTime(now);
  };

  const getCurrentTimeRangeHours = () => {
    const duration = timeRange.end - timeRange.start;
    const hours = duration / (60 * 60 * 1000);
    return hours;
  };

  const formatTime = (date) => {
    if (use24Hour) {
      // 24-hour format: "14:30"
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${hours}:${minutes}`;
    } else {
      // 12-hour format with AM/PM: "2:30 PM"
      const hours = date.getHours();
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const ampm = hours >= 12 ? 'PM' : 'AM';
      const hour12 = hours % 12 || 12;
      return `${hour12}:${minutes} ${ampm}`;
    }
  };

  const formatDate = (date) => {
    const month = date.toLocaleDateString('en-US', { month: 'short' });
    const day = date.getDate();
    const time = formatTime(date);
    return `${month} ${day}, ${time}`;
  };

  const handleEventClick = (event) => {
    setSelectedEvent(event);
    setCurrentTime(new Date(event.timestamp));

    // If event has a recording, could navigate to playback
    if (event.video_path) {
      logger.log('Play recording:', event.video_path);
    }
  };

  const getEventColor = (eventType) => {
    switch (eventType) {
      case 'motion':
        return '#3b82f6'; // Blue
      case 'face':
        return '#10b981'; // Green
      case 'object':
        return '#f59e0b'; // Orange (v3.10.0)
      case 'recording':
        return '#ef4444'; // Red
      default:
        return '#6b7280'; // Gray
    }
  };

  const getEventIcon = (eventType, event) => {
    switch (eventType) {
      case 'motion':
        return '🏃';
      case 'face':
        return '👤';
      case 'object':
        // v3.10.0: Show specific icon based on object class
        if (event?.object_class === 'vehicle') return '🚗';
        if (event?.object_class === 'animal') return '🐾';
        if (event?.object_class === 'package') return '📦';
        return '🔍';
      case 'recording':
        return '⏺️';
      default:
        return '•';
    }
  };

  return (
    <div className="timeline-view">
      {/* Header - Clean and Simple */}
      <div className="timeline-header">
        <div className="timeline-title">
          <h1>Timeline Playback</h1>
        </div>

        <div className="timeline-settings">
          {/* Interval Controls */}
          <div className="setting-group">
            <label>Interval</label>
            <div className="button-group">
              {[
                { value: '5m', label: '5m' },
                { value: '15m', label: '15m' },
                { value: '30m', label: '30m' },
                { value: '1h', label: '1h' }
              ].map(interval => (
                <Button
                  key={interval.value}
                  variant={timeInterval === interval.value ? 'primary' : 'secondary'}
                  size="small"
                  onClick={() => handleIntervalChange(interval.value)}
                >
                  {interval.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Time Format Toggle */}
          <div className="setting-group">
            <label>Time</label>
            <div className="button-group">
              <Button
                variant={!use24Hour ? 'primary' : 'secondary'}
                size="small"
                onClick={() => setUse24Hour(false)}
              >
                12h
              </Button>
              <Button
                variant={use24Hour ? 'primary' : 'secondary'}
                size="small"
                onClick={() => setUse24Hour(true)}
              >
                24h
              </Button>
            </div>
          </div>

          <Button
            variant="secondary"
            size="small"
            onClick={loadTimelineData}
            disabled={loading}
            loading={loading}
            icon="🔄"
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Time Range Display */}
      <div className="time-range-display">
        <span className="current-time">
          📅 {formatDate(currentTime)}
        </span>
        <span className="time-range">
          Showing: {formatDate(timeRange.start)} → {formatDate(timeRange.end)}
        </span>
      </div>

      {/* Time Range Selector */}
      <div className="time-range-selector">
        <label>Time Range:</label>
        <div className="button-group">
          {[
            { hours: 1, label: 'Last Hour' },
            { hours: 6, label: 'Last 6 Hours' },
            { hours: 24, label: 'Last 24 Hours' },
            { hours: 24 * 7, label: 'Last 7 Days' },
            { hours: 24 * 30, label: 'Last 30 Days' }
          ].map(preset => (
            <Button
              key={preset.hours}
              variant={Math.abs(getCurrentTimeRangeHours() - preset.hours) < 0.1 ? 'primary' : 'secondary'}
              size="small"
              onClick={() => setTimeRangePreset(preset.hours)}
            >
              {preset.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Camera Filter */}
      {availableCameras.length > 0 && (
        <div className="camera-filter">
          <label>Cameras:</label>
          {availableCameras.map(cameraId => (
            <label key={cameraId} className="camera-checkbox">
              <input
                type="checkbox"
                checked={selectedCameras.includes(cameraId)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedCameras([...selectedCameras, cameraId]);
                  } else {
                    setSelectedCameras(selectedCameras.filter(id => id !== cameraId));
                  }
                }}
              />
              {cameraId}
            </label>
          ))}
        </div>
      )}

      {/* Timeline Canvas */}
      {error ? (
        <div className="timeline-error">
          <span>⚠️ {error}</span>
          <Button variant="primary" size="medium" onClick={loadTimelineData}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="timeline-loading">
          <div className="spinner"></div>
          <p>Loading timeline...</p>
        </div>
      ) : (
        <div
          className="timeline-canvas"
          ref={timelineCanvasRef}
          onMouseDown={handleMouseDown}
          onClick={handleSeek}
          onKeyDown={activateOnKey(handleSeek)}
          role="button"
          tabIndex={0}
          style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
        >
          {/* Scrollable Timeline Container */}
          <div
            className="timeline-scroll-container"
            style={{ width: `${getTimelineWidth()}px` }}
          >
            {/* Time Axis */}
            <div className="time-axis">
              {getTimeAxisMarks().map((mark, idx) => {
                const position = getTimePosition(mark.getTime());
                // Only render marks that are visible
                if (position < -200 || position > window.innerWidth + 200) return null;

                return (
                  <div
                    key={idx}
                    className="time-mark"
                    style={{ left: `${position}px` }}
                  >
                    <div className="time-tick"></div>
                    <div className="time-label">{formatTime(mark)}</div>
                  </div>
                );
              })}
            </div>

            {/* Event Icons on Timeline Axis */}
            <div className="timeline-events">
              {lanes.flatMap(lane => lane.events).map(event => {
                const position = getTimePosition(new Date(event.timestamp).getTime());

                // Only render if visible
                if (position < -200 || position > window.innerWidth + 200) return null;

                return (
                  <div
                    key={event.id}
                    className={`timeline-event-icon ${selectedEvent?.id === event.id ? 'selected' : ''}`}
                    style={{
                      left: `${position}px`,
                      backgroundColor: getEventColor(event.event_type)
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEventClick(event);
                    }}
                    onMouseEnter={() => setHoveredEvent(event)}
                    onMouseLeave={() => setHoveredEvent(null)}
                    title={`${event.event_type}: ${formatDate(new Date(event.timestamp))}`}
                  >
                    <span>{getEventIcon(event.event_type, event)}</span>
                  </div>
                );
              })}
            </div>

            {/* Playhead */}
            <div
              className="playhead"
              style={{ left: `${getTimePosition(currentTime.getTime())}px` }}
            >
              <div className="playhead-line"></div>
              <div className="playhead-handle"></div>
            </div>

          </div>
        </div>
      )}

      {/* Media Viewer - Always visible */}
      <div className="media-viewer-container">
        {playbackMedia || selectedEvent ? (
          <div className="media-viewer">
            <div className="media-display">
              {playbackMedia && playbackMedia.type === 'video' ? (
                <video
                  key={playbackMedia.url}
                  src={playbackMedia.url}
                  poster={playbackMedia.thumbnailUrl || undefined}
                  controls
                  className="media-video"
                  onEnded={handleVideoEnded}
                  onError={(e) => {
                    logger.error('Video playback error:', e);
                    // If video fails to load, skip to next event
                    if (isPlayingRef.current) {
                      setTimeout(() => advanceToNextEvent(), 500);
                    }
                  }}
                  onLoadedData={(e) => {
                    // Set playback speed when video loads
                    e.target.playbackRate = playbackSpeed;
                    // Explicitly play if playing state is true
                    if (isPlayingRef.current) {
                      e.target.play().catch(err => {
                        logger.error('Video play error after load:', err);
                      });
                    }
                  }}
                />
              ) : playbackMedia && playbackMedia.type === 'image' ? (
                <img
                  src={playbackMedia.url}
                  alt="Event snapshot"
                  className="media-image"
                />
              ) : selectedEvent && selectedEvent.thumbnail_path ? (
                <img
                  src={`/api/snapshots/${selectedEvent.thumbnail_path}`}
                  alt="Event snapshot"
                  className="media-image"
                  onError={(e) => e.target.style.display = 'none'}
                />
              ) : (
                <div className="media-placeholder">
                  <span>📹</span>
                  <p>Select an event or press play to view media</p>
                </div>
              )}
            </div>

            {(playbackMedia || selectedEvent) && (
              <div className="media-info">
                {(() => {
                  const event = playbackMedia ? playbackMedia.event : selectedEvent;
                  return (
                    <>
                      <div className="media-header">
                        <div className="media-title">
                          <span className="media-icon">{getEventIcon(event.event_type)}</span>
                          <span className="media-event-type">{event.event_type}</span>
                        </div>
                        <span className="media-time">{formatDate(new Date(event.timestamp))}</span>
                      </div>

                      <div className="media-details-grid">
                        <div className="detail-item">
                          <label>Camera</label>
                          <span>{event.camera_id}</span>
                        </div>

                        {event.person_name && (
                          <div className="detail-item">
                            <label>Person</label>
                            <span>👤 {event.person_name} ({(event.confidence * 100).toFixed(1)}%)</span>
                          </div>
                        )}

                        {event.duration && (
                          <div className="detail-item">
                            <label>Duration</label>
                            <span>{event.duration.toFixed(1)}s</span>
                          </div>
                        )}

                        {event.faces_detected > 0 && (
                          <div className="detail-item">
                            <label>Faces Detected</label>
                            <span>{event.faces_detected}</span>
                          </div>
                        )}

                        {event.known_faces_detected > 0 && (
                          <div className="detail-item">
                            <label>Known Faces</label>
                            <span>{event.known_faces_detected}</span>
                          </div>
                        )}
                      </div>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        ) : (
          <div className="media-viewer">
            <div className="media-placeholder">
              <span>📹</span>
              <p>Select an event or press play to view media</p>
            </div>
          </div>
        )}

        {/* Playback Controls - Bottom of Media Container */}
        <div className="playback-control-bar">
          <div className="playback-buttons">
            <Button
              variant="secondary"
              size="small"
              onClick={handlePreviousEvent}
              title="Previous event"
              disabled={loading}
              icon="⏮"
            >
              Previous
            </Button>

            <Button
              variant={playing ? 'secondary' : 'primary'}
              size="small"
              onClick={togglePlayback}
              title={playing ? 'Pause' : 'Play'}
              disabled={loading}
              icon={playing ? '⏸' : '▶'}
            >
              {playing ? 'Pause' : 'Play'}
            </Button>

            <Button
              variant="secondary"
              size="small"
              onClick={stopPlayback}
              title="Stop playback"
              disabled={loading || !playing}
              icon="⏹"
            >
              Stop
            </Button>

            <Button
              variant="secondary"
              size="small"
              onClick={handleNextEvent}
              title="Next event"
              disabled={loading}
              endIcon="⏭"
            >
              Next
            </Button>

            <Button
              variant="primary"
              size="small"
              onClick={jumpToNow}
              title="Jump to now"
              disabled={loading}
              icon="🔴"
            >
              Live
            </Button>
          </div>

          {/* Speed Control */}
          <div className="speed-selector">
            <label>Speed</label>
            <div className="button-group">
              {[0.5, 1, 2, 4, 8].map(speed => (
                <Button
                  key={speed}
                  variant={playbackSpeed === speed ? 'primary' : 'secondary'}
                  size="small"
                  onClick={() => handleSpeedChange(speed)}
                >
                  {speed}x
                </Button>
              ))}
            </div>
          </div>

          {/* Playback Progress */}
          {playing && playbackProgress.total > 0 && (
            <div className="playback-progress">
              <span className="progress-text">
                Event {playbackProgress.current} of {playbackProgress.total}
              </span>
              <div className="progress-bar">
                <div 
                  className="progress-fill"
                  style={{ width: `${(playbackProgress.current / playbackProgress.total) * 100}%` }}
                />
              </div>
            </div>
          )}
        </div>

        {/* Keyboard Shortcuts Help */}
        <div className="keyboard-shortcuts-hint">
          <span title="Space: Play/Pause | ←/→: Prev/Next | ↑/↓: Speed | L: Live | Esc: Stop">
            ⌨️ Shortcuts
          </span>
        </div>
      </div>

      {/* Camera Lanes - Now below media viewer */}
      {!error && !loading && (
        <div className="camera-section">
          <h2 className="section-title">Camera Events</h2>
          <div className="camera-lanes">
            {lanes.length === 0 ? (
              <div className="empty-timeline">
                <p>📭 No events in this time range</p>
                <Button
                  variant="primary"
                  size="small"
                  onClick={() => jumpToNow()}
                >
                  Jump to current time
                </Button>
              </div>
            ) : (
              lanes.map(lane => (
                <div key={lane.camera_id} className="camera-lane">
                  <div className="lane-header">
                    <h3>{lane.camera_name}</h3>
                    <span className="event-count">{lane.events.length} events</span>
                  </div>

                  <div className="lane-timeline">
                    {/* Recording blocks */}
                    {lane.recordings.map(rec => {
                      const startTime = new Date(rec.started_at).getTime();
                      const position = getTimePosition(startTime);
                      const intervalMs = getIntervalMs();
                      const widthPx = (rec.duration_seconds * 1000 / intervalMs) * PIXELS_PER_INTERVAL;

                      // Only render if visible
                      if (position + widthPx < -200 || position > window.innerWidth + 200) return null;

                      return (
                        <div
                          key={rec.id}
                          className="recording-block"
                          style={{
                            left: `${position}px`,
                            width: `${widthPx}px`
                          }}
                          title={`Recording: ${formatDate(new Date(rec.started_at))}`}
                        />
                      );
                    })}

                    {/* Event markers */}
                    {lane.events.map(event => {
                      const position = getTimePosition(new Date(event.timestamp).getTime());

                      // Only render if visible
                      if (position < -200 || position > window.innerWidth + 200) return null;

                      return (
                        <div
                          key={event.id}
                          className="event-marker"
                          style={{
                            left: `${position}px`,
                            backgroundColor: getEventColor(event.event_type)
                          }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEventClick(event);
                          }}
                          onMouseEnter={() => setHoveredEvent(event)}
                          onMouseLeave={() => setHoveredEvent(null)}
                          title={`${event.event_type}: ${formatDate(new Date(event.timestamp))}`}
                        >
                          <span className="event-icon">{getEventIcon(event.event_type)}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Hover Tooltip */}
      {hoveredEvent && !selectedEvent && (
        <div className="event-tooltip">
          <div><strong>{hoveredEvent.event_type}</strong></div>
          <div>{formatDate(new Date(hoveredEvent.timestamp))}</div>
          {hoveredEvent.person_name && <div>👤 {hoveredEvent.person_name}</div>}
        </div>
      )}
    </div>
  );
};

export default TimelineView;
