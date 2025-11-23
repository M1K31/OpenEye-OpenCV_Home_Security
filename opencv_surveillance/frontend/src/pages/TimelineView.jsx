// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect, useRef } from 'react';
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
  const playbackIntervalRef = useRef(null);

  // Camera filter
  const [selectedCameras, setSelectedCameras] = useState([]);
  const [availableCameras, setAvailableCameras] = useState([]);

  // Load timeline data
  useEffect(() => {
    loadTimelineData();
    loadCameras();
  }, [timeRange, selectedCameras]);

  // Playback loop - advances time and displays events
  useEffect(() => {
    if (playing) {
      playbackIntervalRef.current = setInterval(() => {
        setCurrentTime(prev => {
          const next = new Date(prev.getTime() + (playbackSpeed * 1000));
          if (next > timeRange.end) {
            setPlaying(false);
            setPlaybackMedia(null);
            return timeRange.end;
          }

          // Find events at or near current time (within 1 second window)
          const allEvents = lanes.flatMap(lane => lane.events);
          const nearbyEvents = allEvents.filter(event => {
            const eventTime = new Date(event.timestamp).getTime();
            const currentMs = next.getTime();
            return Math.abs(eventTime - currentMs) < 1000; // Within 1 second
          });

          // If we found an event, display it
          if (nearbyEvents.length > 0) {
            const event = nearbyEvents[0];
            setSelectedEvent(event);

            // Set media for display
            if (event.video_path) {
              setPlaybackMedia({
                type: 'video',
                url: `/api/recordings/${event.video_path}/download`,
                event: event
              });
            } else if (event.thumbnail_path) {
              setPlaybackMedia({
                type: 'image',
                url: `/api/snapshots/${event.thumbnail_path}`,
                event: event
              });
            }
          }

          return next;
        });
      }, 1000);
    } else {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current);
      }
    }

    return () => {
      if (playbackIntervalRef.current) {
        clearInterval(playbackIntervalRef.current);
      }
    };
  }, [playing, playbackSpeed, timeRange, lanes]);

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
        end_time: timeRange.end.toISOString()
      };

      if (selectedCameras.length > 0 && selectedCameras.length < availableCameras.length) {
        params.camera_ids = selectedCameras.join(',');
      }

      const response = await apiClient.get('/timeline/view', { params });

      setLanes(response.data.lanes || []);
    } catch (err) {
      logger.error('Error loading timeline:', err);
      setError('Failed to load timeline data. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Time axis helpers - Scrollable ruler approach
  const PIXELS_PER_INTERVAL = 150; // Fixed spacing between time marks

  const getIntervalMs = () => {
    return {
      '5m': 5 * 60 * 1000,
      '15m': 15 * 60 * 1000,
      '30m': 30 * 60 * 1000,
      '1h': 60 * 60 * 1000
    }[timeInterval];
  };

  const getTimelineWidth = () => {
    // Calculate total width of timeline based on time range and interval
    const duration = timeRange.end - timeRange.start;
    const intervalMs = getIntervalMs();
    const numIntervals = Math.ceil(duration / intervalMs);
    return numIntervals * PIXELS_PER_INTERVAL;
  };

  const getTimeAxisMarks = () => {
    const intervalMs = getIntervalMs();
    const marks = [];

    // Round start time to nearest interval
    const startMs = timeRange.start.getTime();
    const roundedStart = Math.floor(startMs / intervalMs) * intervalMs;
    let current = new Date(roundedStart);

    // Generate marks for entire time range
    while (current <= timeRange.end) {
      marks.push(new Date(current));
      current = new Date(current.getTime() + intervalMs);
    }

    return marks;
  };

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
    // Find previous event before current time
    const allEvents = lanes.flatMap(lane => lane.events);
    const previousEvents = allEvents
      .filter(e => new Date(e.timestamp) < currentTime)
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

    if (previousEvents.length > 0) {
      const prevEvent = previousEvents[0];
      setCurrentTime(new Date(prevEvent.timestamp));
      setSelectedEvent(prevEvent);
    }
  };

  const handleNextEvent = () => {
    // Find next event after current time
    const allEvents = lanes.flatMap(lane => lane.events);
    const nextEvents = allEvents
      .filter(e => new Date(e.timestamp) > currentTime)
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    if (nextEvents.length > 0) {
      const nextEvent = nextEvents[0];
      setCurrentTime(new Date(nextEvent.timestamp));
      setSelectedEvent(nextEvent);
    }
  };

  const togglePlayback = () => {
    setPlaying(!playing);
  };

  const handleSpeedChange = (speed) => {
    setPlaybackSpeed(speed);
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
                  controls
                  autoPlay={playing}
                  className="media-video"
                  onEnded={() => setPlaybackMedia(null)}
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
