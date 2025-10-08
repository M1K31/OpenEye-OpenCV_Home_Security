// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import FaceManagementPage from './FaceManagementPage';

const DashboardPage = ({ onLogout }) => {
  const [showFaceManagement, setShowFaceManagement] = useState(false);
  const [recentDetections, setRecentDetections] = useState([]);
  const [statistics, setStatistics] = useState({});
  const streamUrl = "/api/cameras/mock_cam_1/stream";
  const navigate = useNavigate();

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

    // Refresh every 5 seconds
    const interval = setInterval(() => {
      loadDetections();
      loadStats();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  if (showFaceManagement) {
    return <FaceManagementPage onBack={() => setShowFaceManagement(false)} />;
  }

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>OpenEye Surveillance Dashboard</h1>
        <div style={styles.headerButtons}>
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
        <h2>Live Camera Feed</h2>
        <img 
          src={streamUrl} 
          alt="Live camera stream" 
          className="video-stream" 
          style={styles.videoStream}
        />
        <div style={styles.streamInfo}>
          <span style={styles.liveIndicator}>🔴 LIVE</span>
          <span>Mock Camera 1</span>
        </div>
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
    gap: '10px',
  },
  settingsButton: {
    backgroundColor: 'var(--text-link)',
    color: '#FFFFFF',
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
    color: '#FFFFFF',
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
    color: '#999',
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
    color: '#999',
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
    color: '#999',
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
    color: '#999',
  },
  faceTime: {
    fontSize: '0.85em',
    color: '#999',
    marginTop: '5px',
  },
  noFaces: {
    textAlign: 'center',
    color: '#999',
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
};

export default DashboardPage;