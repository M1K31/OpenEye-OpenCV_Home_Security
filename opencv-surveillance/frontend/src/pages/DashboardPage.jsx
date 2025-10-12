// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import FaceManagementPage from './FaceManagementPage';
import wsService from '../services/WebSocketService';

const DashboardPage = ({ onLogout }) => {
  const [showFaceManagement, setShowFaceManagement] = useState(false);
  const [recentDetections, setRecentDetections] = useState([]);
  const [statistics, setStatistics] = useState({});
  const [wsStatus, setWsStatus] = useState('disconnected'); // WebSocket connection status
  const [usePolling, setUsePolling] = useState(false); // Fallback to polling if WebSocket fails
  const [cameras, setCameras] = useState([]); // List of all cameras
  const [displayMode, setDisplayMode] = useState('grid'); // Display mode: grid, vertical, horizontal, cycle
  const [currentCameraIndex, setCurrentCameraIndex] = useState(0); // For cycle mode
  const [systemSettings, setSystemSettings] = useState({}); // System settings from backend
  const navigate = useNavigate();

  // Load system settings for display mode and cycle interval
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await axios.get('/api/settings');
        setSystemSettings(response.data);
        // Set display mode from settings
        if (response.data.display_mode) {
          setDisplayMode(response.data.display_mode);
        }
      } catch (error) {
        console.error('Error loading system settings:', error);
      }
    };
    loadSettings();
  }, []);

  // Cycle mode timer
  useEffect(() => {
    if (displayMode === 'cycle' && cameras.length > 1) {
      const cycleInterval = (systemSettings.cycle_interval || 5) * 1000; // Convert to milliseconds
      const timer = setInterval(() => {
        setCurrentCameraIndex((prevIndex) => (prevIndex + 1) % cameras.length);
      }, cycleInterval);
      
      return () => clearInterval(timer);
    }
  }, [displayMode, cameras.length, systemSettings.cycle_interval]);

  // Load cameras once on mount
  useEffect(() => {
    const loadCameras = async () => {
      try {
        const response = await axios.get('/api/cameras/');
        // API returns { cameras: [...], total: n }
        setCameras(response.data.cameras || []);
      } catch (error) {
        console.error('Error loading cameras:', error);
        setCameras([]); // Set empty array on error
      }
    };
    loadCameras();
  }, []);

  // Load face detection data
  useEffect(() => {
    const loadDetections = async () => {
      try {
        const response = await axios.get('/api/faces/detections');
        setRecentDetections(response.data);
      } catch (error) {
        console.error('Error loading detections:', error);
      }
    };

    const loadStats = async () => {
      try {
        const response = await axios.get('/api/faces/statistics');
        setStatistics(response.data);
      } catch (error) {
        console.error('Error loading statistics:', error);
      }
    };

    // Initial load
    loadDetections();
    loadStats();

    // WebSocket setup
    const token = localStorage.getItem('token');
    let pollingInterval = null;

    if (token) {
      // Try WebSocket connection first
      wsService.connect(token);

      // Listen for WebSocket status changes
      const unsubscribeStatus = wsService.on('status_change', ({ status }) => {
        setWsStatus(status);
        
        // If WebSocket fails after max retries, fall back to polling
        if (status === 'error' || status === 'disconnected') {
          console.log('WebSocket unavailable, using polling fallback');
          setUsePolling(true);
        } else if (status === 'connected') {
          setUsePolling(false);
        }
      });

      // Listen for statistics updates via WebSocket
      const unsubscribeStats = wsService.on('statistics_update', (message) => {
        if (message.data) {
          setStatistics(prevStats => ({
            ...prevStats,
            ...message.data
          }));
        }
      });

      // Listen for camera events
      const unsubscribeCameraEvents = wsService.on('camera_event', (message) => {
        console.log('Camera event received:', message);
        // Refresh detections on certain camera events
        if (message.event_type === 'face_detected' || message.event_type === 'face_recognized') {
          loadDetections();
        }
      });

      // Polling fallback (only if WebSocket fails)
      const startPolling = () => {
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }
        pollingInterval = setInterval(() => {
          if (usePolling || !wsService.isConnected()) {
            loadDetections();
            loadStats();
          }
        }, 5000);
      };

      // Start polling after a short delay to see if WebSocket connects
      setTimeout(() => {
        if (!wsService.isConnected()) {
          console.log('WebSocket not connected, starting polling');
          setUsePolling(true);
          startPolling();
        }
      }, 3000);

      // Cleanup
      return () => {
        unsubscribeStatus();
        unsubscribeStats();
        unsubscribeCameraEvents();
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }
        // Don't disconnect WebSocket here - it should persist across page navigation
      };
    } else {
      // No token, use polling only
      setUsePolling(true);
      pollingInterval = setInterval(() => {
        loadDetections();
        loadStats();
      }, 5000);

      return () => {
        if (pollingInterval) {
          clearInterval(pollingInterval);
        }
      };
    }
  }, [usePolling]);

  // Helper function to get grid style based on display mode
  const getGridStyle = (mode) => {
    const baseStyle = {
      marginTop: '15px',
      gap: '20px',
    };

    switch (mode) {
      case 'grid':
        return {
          ...baseStyle,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
        };
      case 'vertical':
        return {
          ...baseStyle,
          display: 'flex',
          flexDirection: 'column',
        };
      case 'horizontal':
        return {
          ...baseStyle,
          display: 'flex',
          flexDirection: 'row',
          overflowX: 'auto',
        };
      case 'cycle':
        return {
          ...baseStyle,
          display: 'flex',
          justifyContent: 'center',
        };
      default:
        return styles.cameraGrid;
    }
  };

  // Helper function to render a single camera
  const renderCamera = (camera) => {
    if (!camera) return null;
    
    return (
      <div key={camera.camera_id} style={styles.cameraCard}>
        <div style={styles.cameraHeader}>
          <h3 style={styles.cameraName}>{camera.name || camera.camera_id}</h3>
          <span style={camera.is_active ? styles.liveIndicator : styles.offlineIndicator}>
            {camera.is_active ? '🔴 LIVE' : '⚫ OFFLINE'}
          </span>
        </div>
        {camera.is_active ? (
          <img 
            src={`/api/cameras/${camera.camera_id}/stream`}
            alt={`${camera.name || camera.camera_id} stream`}
            className="video-stream" 
            style={styles.videoStream}
            onError={(e) => {
              e.target.onerror = null;
              e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="640" height="480"%3E%3Crect fill="%23333" width="640" height="480"/%3E%3Ctext fill="%23fff" font-size="20" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EStream Unavailable%3C/text%3E%3C/svg%3E';
            }}
          />
        ) : (
          <div style={styles.offlineStream}>
            <span style={styles.offlineText}>Camera Offline</span>
          </div>
        )}
      </div>
    );
  };

  if (showFaceManagement) {
    return <FaceManagementPage onBack={() => setShowFaceManagement(false)} />;
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>OpenEye Surveillance Dashboard</h1>
        <div style={styles.headerButtons}>
          {/* Connection Status Indicator */}
          <div style={styles.connectionStatus}>
            {wsStatus === 'connected' && (
              <span style={styles.statusConnected} title="Real-time updates active">
                🟢 Live
              </span>
            )}
            {wsStatus === 'connecting' && (
              <span style={styles.statusConnecting} title="Connecting to real-time updates">
                🟡 Connecting...
              </span>
            )}
            {(wsStatus === 'disconnected' || wsStatus === 'error') && usePolling && (
              <span style={styles.statusPolling} title="Using polling fallback">
                🔵 Polling
              </span>
            )}
          </div>
          <button onClick={() => navigate('/recordings')} style={styles.recordingsButton}>
            📼 Recordings
          </button>
          <button onClick={() => navigate('/settings')} style={styles.settingsButton}>
            ⚙️ Settings
          </button>
          <button onClick={onLogout} style={styles.logoutButton}>
            🚪 Logout
          </button>
        </div>
      </header>

      {/* Face Recognition Stats Banner */}
      {statistics.total_people > 0 && (
        <div style={styles.statsBanner}>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Known People:</span>
            <span style={styles.statValue}>{statistics.total_people}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Recognitions Today:</span>
            <span style={styles.statValue}>{statistics.recognitions_today || 0}</span>
          </div>
          <div style={styles.statItem}>
            <span style={styles.statLabel}>Last Recognition:</span>
            <span style={styles.statValue}>
              {statistics.last_recognition 
                ? new Date(statistics.last_recognition).toLocaleTimeString()
                : 'Never'}
            </span>
          </div>
        </div>
      )}

      {/* Video Stream */}
      <div className="video-container" style={styles.videoContainer}>
        <div style={styles.streamHeader}>
          <h2>Live Camera Feeds</h2>
          {cameras.length > 0 && (
            <div style={styles.displayModeSelector}>
              <button 
                onClick={() => setDisplayMode('grid')} 
                style={{...styles.modeButton, ...(displayMode === 'grid' ? styles.modeButtonActive : {})}}
                title="Grid View - Display all cameras in a responsive grid layout (best for 2-6 cameras)"
              >
                ▦
              </button>
              <button 
                onClick={() => setDisplayMode('vertical')} 
                style={{...styles.modeButton, ...(displayMode === 'vertical' ? styles.modeButtonActive : {})}}
                title="Vertical Stack - Stack cameras vertically, one per row (best for 1-3 cameras)"
              >
                ☰
              </button>
              <button 
                onClick={() => setDisplayMode('horizontal')} 
                style={{...styles.modeButton, ...(displayMode === 'horizontal' ? styles.modeButtonActive : {})}}
                title="Horizontal Stack - Line up cameras side-by-side with horizontal scroll (best for multiple cameras)"
              >
                ≡
              </button>
              <button 
                onClick={() => setDisplayMode('cycle')} 
                style={{...styles.modeButton, ...(displayMode === 'cycle' ? styles.modeButtonActive : {})}}
                title="Cycle Mode - Auto-rotate through cameras one at a time (interval configured in System Settings)"
              >
                🔄
              </button>
            </div>
          )}
        </div>
        
        {cameras.length === 0 ? (
          <div style={styles.noCameras}>
            <p>📹 No cameras configured yet.</p>
            <p style={styles.noCamerasSubtext}>Add your first camera to start monitoring</p>
            <button 
              onClick={() => navigate('/settings')} 
              style={styles.addCameraButton}
            >
              ➕ Add Camera
            </button>
          </div>
        ) : (
          <>
            {displayMode === 'cycle' && cameras.length > 1 && (
              <div style={styles.cycleInfo}>
                <span>Camera {currentCameraIndex + 1} of {cameras.length}</span>
                <span> • </span>
                <span>Auto-switching every {systemSettings.cycle_interval || 5}s</span>
              </div>
            )}
            <div style={getGridStyle(displayMode)}>
              {displayMode === 'cycle' 
                ? renderCamera(cameras[currentCameraIndex])
                : cameras.map(camera => renderCamera(camera))
              }
            </div>
          </>
        )}
      </div>

      {/* Recent Face Detections */}
      <div style={styles.detectionsContainer}>
        <h2>Recent Face Detections</h2>
        {Object.keys(recentDetections).length === 0 ? (
          <p style={styles.noDetections}>
            No recent face detections. Faces will appear here when detected.
          </p>
        ) : (
          <div style={styles.detectionsGrid}>
            {Object.entries(recentDetections).map(([cameraId, data]) => (
              <div key={cameraId} style={styles.cameraDetections}>
                <h3 style={styles.cameraTitle}>{cameraId}</h3>
                {data.recent_faces && data.recent_faces.length > 0 ? (
                  <div style={styles.facesList}>
                    {data.recent_faces.slice(0, 5).map((face, index) => (
                      <div 
                        key={index} 
                        style={{
                          ...styles.faceItem,
                          ...(face.name === 'Unknown' ? styles.faceUnknown : styles.faceKnown)
                        }}
                      >
                        <div style={styles.faceName}>{face.name}</div>
                        <div style={styles.faceInfo}>
                          Confidence: {(face.confidence * 100).toFixed(1)}%
                        </div>
                        <div style={styles.faceTime}>
                          {new Date(face.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={styles.noFaces}>No faces detected on this camera</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Info Section */}
      <div style={styles.infoSection}>
        <h3>Features Active:</h3>
        <ul style={styles.featuresList}>
          <li>✓ Motion Detection</li>
          <li>✓ Automatic Recording</li>
          <li>{statistics.total_people > 0 ? '✓' : '○'} Face Recognition {statistics.total_people === 0 && '(Add people to enable)'}</li>
          <li>✓ OpenCV Processing</li>
        </ul>
      </div>
    </div>
  );
};

// Styles defined ONCE outside component
const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    color: 'var(--text-primary)',
    padding: '20px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '2px solid var(--border-panel)',
  },
  title: {
    color: 'var(--text-primary)',
    fontSize: '28px',
    margin: 0,
  },
  headerButtons: {
    display: 'flex',
    gap: '15px',
    alignItems: 'center',
  },
  connectionStatus: {
    padding: '6px 12px',
    borderRadius: '6px',
    fontSize: '0.9em',
    fontWeight: '500',
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border-panel)',
  },
  statusConnected: {
    color: 'var(--color-success)',
  },
  statusConnecting: {
    color: '#ffc107',
  },
  statusPolling: {
    color: '#17a2b8',
  },
  recordingsButton: {
    backgroundColor: '#8e44ad',
    color: 'var(--text-primary)',
    padding: '12px 24px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '14px',
    transition: 'all 0.2s ease',
  },
  settingsButton: {
    backgroundColor: 'var(--text-link)',
    color: 'var(--text-primary)',
    padding: '12px 24px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '14px',
    transition: 'all 0.2s ease',
  },
  logoutButton: {
    backgroundColor: 'var(--color-error)',
    color: 'var(--text-primary)',
    padding: '12px 24px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '14px',
    transition: 'all 0.2s ease',
  },
  statsBanner: {
    display: 'flex',
    justifyContent: 'space-around',
    backgroundColor: 'var(--bg-panel)',
    padding: '15px',
    borderRadius: '8px',
    marginBottom: '20px',
    border: '1px solid var(--border-panel)',
  },
  statItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
  },
  statLabel: {
    fontSize: '0.9em',
    color: 'var(--text-secondary)',
    marginBottom: '5px',
  },
  statValue: {
    fontSize: '1.5em',
    fontWeight: 'bold',
    color: 'var(--text-primary)',
  },
  videoContainer: {
    marginBottom: '30px',
    backgroundColor: 'var(--bg-panel)',
    padding: '20px',
    borderRadius: '8px',
    border: '1px solid var(--border-panel)',
  },
  streamHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '15px',
  },
  displayModeSelector: {
    display: 'flex',
    gap: '10px',
    backgroundColor: 'var(--bg-main)',
    padding: '8px',
    borderRadius: '8px',
    border: '1px solid var(--border-panel)',
  },
  modeButton: {
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)',
    padding: '8px 16px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '18px',
    transition: 'all 0.2s ease',
  },
  modeButtonActive: {
    background: 'var(--text-link)',
    color: 'white',
    boxShadow: '0 2px 8px rgba(0, 123, 255, 0.3)',
  },
  cycleInfo: {
    textAlign: 'center',
    padding: '10px',
    backgroundColor: 'var(--bg-main)',
    borderRadius: '6px',
    color: 'var(--text-secondary)',
    marginBottom: '15px',
    border: '1px solid var(--border-panel)',
  },
  videoStream: {
    width: '100%',
    maxWidth: '800px',
    border: '2px solid var(--border-panel)',
    borderRadius: '8px',
  },
  streamInfo: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '10px',
    marginTop: '10px',
    color: 'var(--text-secondary)',
  },
  liveIndicator: {
    color: 'var(--color-error)',
    fontWeight: 'bold',
  },
  detectionsContainer: {
    backgroundColor: 'var(--bg-panel)',
    padding: '20px',
    borderRadius: '8px',
    border: '1px solid var(--border-panel)',
    marginBottom: '30px',
  },
  noDetections: {
    textAlign: 'center',
    color: 'var(--text-secondary)',
    fontStyle: 'italic',
    padding: '20px',
  },
  detectionsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '20px',
  },
  cameraDetections: {
    border: '1px solid var(--border-panel)',
    borderRadius: '8px',
    padding: '15px',
    backgroundColor: 'var(--bg-main)',
  },
  cameraTitle: {
    margin: '0 0 15px 0',
    color: 'var(--text-primary)',
    fontSize: '1.1em',
  },
  facesList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  faceItem: {
    padding: '10px',
    borderRadius: '6px',
    border: '1px solid var(--border-panel)',
  },
  faceKnown: {
    backgroundColor: 'rgba(40, 167, 69, 0.15)',
    borderColor: 'var(--color-success)',
  },
  faceUnknown: {
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    borderColor: 'var(--color-error)',
  },
  faceName: {
    fontWeight: 'bold',
    fontSize: '1.1em',
    marginBottom: '5px',
    color: 'var(--text-primary)',
  },
  faceInfo: {
    fontSize: '0.9em',
    color: 'var(--text-secondary)',
  },
  faceTime: {
    fontSize: '0.85em',
    color: 'var(--text-secondary)',
    marginTop: '5px',
  },
  noFaces: {
    textAlign: 'center',
    color: 'var(--text-secondary)',
    fontStyle: 'italic',
    padding: '10px',
  },
  infoSection: {
    backgroundColor: 'rgba(0, 123, 255, 0.15)',
    padding: '20px',
    borderRadius: '8px',
    borderLeft: '4px solid var(--text-link)',
  },
  featuresList: {
    listStyle: 'none',
    padding: 0,
    margin: '10px 0 0 0',
  },
  // Camera Grid Styles
  noCameras: {
    textAlign: 'center',
    padding: '60px 40px',
    color: 'var(--text-secondary)',
    fontSize: '1.1em',
  },
  noCamerasSubtext: {
    fontSize: '0.9em',
    color: 'var(--text-secondary)',
    marginTop: '5px',
    marginBottom: '20px',
  },
  addCameraButton: {
    backgroundColor: 'var(--text-link)',
    color: 'var(--text-primary)',
    padding: '14px 32px',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontWeight: '600',
    fontSize: '16px',
    marginTop: '10px',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
  },
  cameraGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: '20px',
    marginTop: '15px',
  },
  cameraCard: {
    backgroundColor: 'var(--bg-main)',
    border: '1px solid var(--border-panel)',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  cameraHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 15px',
    backgroundColor: 'var(--bg-panel)',
    borderBottom: '1px solid var(--border-panel)',
  },
  cameraName: {
    margin: 0,
    fontSize: '1.1em',
    color: 'var(--text-primary)',
  },
  offlineIndicator: {
    color: 'var(--text-secondary)',
    fontWeight: 'bold',
    fontSize: '0.9em',
  },
  offlineStream: {
    width: '100%',
    height: '300px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'var(--bg-main)',
    border: '2px dashed var(--border-panel)',
  },
  offlineText: {
    color: 'var(--text-secondary)',
    fontSize: '1.2em',
    fontStyle: 'italic',
  },
};

export default DashboardPage;