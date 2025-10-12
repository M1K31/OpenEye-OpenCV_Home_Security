// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import apiClient, { isAuthenticated } from '../api/apiClient';
import './LiveDashboard.css';

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
  const [cameras, setCameras] = useState([]);
  const [events, setEvents] = useState([]);
  const [showTimeline, setShowTimeline] = useState(true);
  const [systemStatus, setSystemStatus] = useState('All systems nominal');
  const [selectedRecording, setSelectedRecording] = useState(null);

  useEffect(() => {
    if (isAuthenticated()) {
      fetchCameras();
      fetchRecentEvents();
      
      // Refresh events every 10 seconds
      const interval = setInterval(fetchRecentEvents, 10000);
      return () => clearInterval(interval);
    }
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      // API returns {cameras: [...], total: number}
      const cameraData = response.data?.cameras || [];
      setCameras(cameraData);
    } catch (error) {
      console.error('Error fetching cameras:', error);
      setCameras([]);
    }
  };

  const fetchRecentEvents = async () => {
    try {
      // Fetch both recordings (motion events) and face detections
      const [recordingsRes, detectionsRes] = await Promise.all([
        apiClient.get('/recordings/?limit=15'),
        apiClient.get('/history/detections?limit=15').catch(() => ({ data: { detections: [] } }))
      ]);

      // Recordings from API - handle wrapped response
      const recordings = recordingsRes.data?.recordings || 
        (Array.isArray(recordingsRes.data) ? recordingsRes.data : []);

      // Face detections from API - handle wrapped response
      const detections = detectionsRes.data?.detections || [];

      // Merge and create unified timeline events
      const allEvents = [
        ...recordings.map(r => ({
          id: r.id || r.recording_id,
          recording_id: r.recording_id,
          type: 'motion',
          camera_id: r.camera_id,
          timestamp: r.started_at,
          duration_seconds: r.duration_seconds,
          faces_detected: r.faces_detected || 0,
          known_faces_detected: r.known_faces_detected || 0,
        })),
        ...detections.map(d => ({
          id: d.id,
          recording_id: d.recording_id,
          type: 'face',
          camera_id: d.camera_id,
          timestamp: d.detected_at,
          person_name: d.person_name || 'Unknown',
          confidence: d.confidence || 0,
        }))
      ];

      // Sort by timestamp (most recent first)
      allEvents.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      // Take top 15
      setEvents(allEvents.slice(0, 15));
    } catch (error) {
      console.error('Error fetching events:', error);
      setEvents([]);
    }
  };

  const toggleTimeline = () => {
    setShowTimeline(!showTimeline);
  };

  const handleEventClick = (event) => {
    if (event.recording_id) {
      // Open recording in new tab or navigate to recordings page
      // For now, navigate to recordings page with the recording highlighted
      window.location.href = `/recordings#${event.recording_id}`;
    }
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

  return (
    <div className="live-dashboard">
      {/* Global Status Bar */}
      <div className="global-status-bar">
        <div className="status-indicator">
          <span className="status-icon">✓</span>
          <span className="status-text">{systemStatus}</span>
        </div>
        <button 
          className="timeline-toggle"
          onClick={toggleTimeline}
          aria-label={showTimeline ? 'Hide Timeline' : 'Show Timeline'}
        >
          {showTimeline ? '› Hide Events' : '‹ Show Events'}
        </button>
      </div>

      <div className="dashboard-container">
        {/* Camera Grid - Main Content */}
        <div className={`camera-grid-container ${showTimeline ? 'with-timeline' : 'full-width'}`}>
          <h2 className="section-title">Live Cameras</h2>
          
          {cameras.length === 0 ? (
            <div className="empty-state">
              <span className="empty-icon">📹</span>
              <p>No cameras configured</p>
              <a href="/cameras" className="btn-primary">Add Camera</a>
            </div>
          ) : (
            <div className="camera-grid">
              {cameras.map((camera) => (
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
                  </div>
                  <div className="camera-info">
                    <span className="info-item">
                      🎥 {camera.resolution || 'Unknown'}
                    </span>
                    <span className="info-item">
                      {camera.motion_detection ? '🔍 Motion: ON' : '🔍 Motion: OFF'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Event Timeline - Right Panel */}
        {showTimeline && (
          <aside className="event-timeline">
            <h3 className="timeline-title">Recent Events</h3>
            <div className="timeline-list">
              {!Array.isArray(events) || events.length === 0 ? (
                <div className="timeline-empty">
                  <span>🔔</span>
                  <p>No recent events</p>
                </div>
              ) : (
                events.map((event, index) => (
                  <div 
                    key={event.id || index} 
                    className={`timeline-item ${event.recording_id ? 'clickable' : ''}`}
                    onClick={() => handleEventClick(event)}
                    title={event.recording_id ? 'Click to view recording' : ''}
                  >
                    <div className="event-icon">
                      {event.type === 'face' ? '�' : '�'}
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
                        {new Date(event.timestamp).toLocaleString()}
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
    </div>
  );
};

export default LiveDashboard;
