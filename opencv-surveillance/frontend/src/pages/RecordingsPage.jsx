// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { useNavigate } from 'react-router-dom';

const RecordingsPage = () => {
  const navigate = useNavigate();
  const [recordings, setRecordings] = useState([]);
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('videos'); // 'videos' or 'snapshots'
  const [selectedRecording, setSelectedRecording] = useState(null);
  const [filterCamera, setFilterCamera] = useState('all');
  const [cameras, setCameras] = useState([]);

  useEffect(() => {
    loadRecordings();
    loadSnapshots();
    loadCameras();
  }, []);

  const loadCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      // Handle both formats: direct array or { cameras: [] }
      setCameras(Array.isArray(response.data) ? response.data : (response.data.cameras || []));
    } catch (err) {
      console.error('Error loading cameras:', err);
      setCameras([]);
    }
  };

  const loadRecordings = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/recordings/');
      // Handle wrapped response or legacy array response
      const recordingsData = response.data?.recordings || 
        (Array.isArray(response.data) ? response.data : []);
      setRecordings(recordingsData);
      setError('');
    } catch (err) {
      console.error('Error loading recordings:', err);
      setError('Failed to load recordings');
      setRecordings([]);
    } finally {
      setLoading(false);
    }
  };

  const loadSnapshots = async () => {
    try {
      // Load motion events (includes events with AND without face detection)
      const response = await apiClient.get('/motion-events/?limit=100');
      // Handle wrapped response (backward compatible with v3.5.2)
      const events = response.data.events || response.data;
      const snapshotsData = Array.isArray(events) ? events : [];
      // Filter only events that have a snapshot_path
      const filtered = snapshotsData.filter(event => event.snapshot_path);
      setSnapshots(filtered);
    } catch (err) {
      console.error('Error loading snapshots:', err);
      setSnapshots([]);
    }
  };

  const deleteRecording = async (recordingId) => {
    if (!window.confirm('Are you sure you want to delete this recording?')) {
      return;
    }
    
    try {
      await apiClient.delete(`/recordings/${recordingId}`);
      loadRecordings();
    } catch (err) {
      console.error('Error deleting recording:', err);
      alert('Failed to delete recording');
    }
  };

  const deleteSnapshot = async (eventId) => {
    if (!window.confirm('Are you sure you want to delete this motion event snapshot?')) {
      return;
    }
    
    try {
      await apiClient.delete(`/motion-events/${eventId}`);
      loadSnapshots();
    } catch (err) {
      console.error('Error deleting snapshot:', err);
      alert('Failed to delete snapshot');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  /**
   * Convert file system path to web URL
   * Maps absolute paths to mounted static file endpoints
   */
  const convertPathToUrl = (filePath) => {
    if (!filePath) return '';
    
    // If already a properly formatted web URL, return as-is
    if (filePath.startsWith('http://') || filePath.startsWith('https://')) {
      return filePath;
    }
    
    // If it's already a relative web path (starts with /data/ or /legacy/), return as-is
    if (filePath.startsWith('/data/') || filePath.startsWith('/legacy/') || filePath.startsWith('/recordings/') || filePath.startsWith('/faces/')) {
      return filePath;
    }

    // Extract just the filename from the full path
    const filename = filePath.split('/').pop();
    
    // Check if this is a legacy snapshot (in data/snapshots directory)
    if (filePath.includes('data/snapshots') || filePath.includes('data\\snapshots')) {
      return `/legacy/snapshots/${filename}`;
    }
    
    // Default to custom snapshots path (for absolute paths like /Volumes/...)
    return `/data/snapshots/${filename}`;
  };

  const filteredRecordings = filterCamera === 'all' 
    ? recordings 
    : recordings.filter(r => r.camera_id === filterCamera);

  const filteredSnapshots = filterCamera === 'all'
    ? snapshots
    : snapshots.filter(s => s.camera_id === filterCamera);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <button onClick={() => navigate('/dashboard')} style={styles.backButton}>
          ← Back to Dashboard
        </button>
        <h1 style={styles.title}>📼 Recordings & Snapshots</h1>
      </header>

      {/* Tab Selector */}
      <div style={styles.tabContainer}>
        <button
          onClick={() => setActiveTab('videos')}
          style={{
            ...styles.tab,
            ...(activeTab === 'videos' ? styles.activeTab : {})
          }}
        >
          🎥 Videos ({filteredRecordings.length})
        </button>
        <button
          onClick={() => setActiveTab('snapshots')}
          style={{
            ...styles.tab,
            ...(activeTab === 'snapshots' ? styles.activeTab : {})
          }}
        >
          📷 Snapshots ({filteredSnapshots.length})
        </button>
      </div>

      {/* Camera Filter */}
      <div style={styles.filterContainer}>
        <label style={styles.filterLabel}>Filter by Camera:</label>
        <select
          value={filterCamera}
          onChange={(e) => setFilterCamera(e.target.value)}
          style={styles.filterSelect}
        >
          <option value="all">All Cameras</option>
          {cameras.map(camera => (
            <option key={camera.camera_id} value={camera.camera_id}>
              {camera.name || camera.camera_id}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div style={styles.loading}>Loading...</div>
      ) : error ? (
        <div style={styles.error}>{error}</div>
      ) : (
        <div style={styles.content}>
          {activeTab === 'videos' ? (
            <div style={styles.recordingsGrid}>
              {filteredRecordings.length === 0 ? (
                <div style={styles.empty}>
                  <p>📹 No video recordings found.</p>
                  <p style={styles.emptyHint}>
                    Recordings will appear here when motion is detected and recording is enabled.
                  </p>
                </div>
              ) : (
                filteredRecordings.map((recording) => (
                  <div key={recording.id} style={styles.recordingCard}>
                    <div style={styles.recordingThumbnail}>
                      <video
                        src={`/api/recordings/${recording.id}/download`}
                        controls
                        style={styles.videoPreview}
                        preload="metadata"
                      />
                    </div>
                    <div style={styles.recordingInfo}>
                      <h3 style={styles.recordingTitle}>
                        {recording.camera_id}
                      </h3>
                      <p style={styles.recordingMeta}>
                        📅 {formatDate(recording.started_at)}
                      </p>
                      <p style={styles.recordingMeta}>
                        ⏱️ {recording.duration_seconds ? recording.duration_seconds.toFixed(1) : '0.0'}s
                      </p>
                      <p style={styles.recordingMeta}>
                        💾 {recording.file_size_bytes ? formatFileSize(recording.file_size_bytes) : 'N/A'}
                      </p>
                      {recording.faces_detected > 0 && (
                        <p style={styles.recordingMeta}>
                          👤 {recording.faces_detected} face{recording.faces_detected > 1 ? 's' : ''} detected
                        </p>
                      )}
                    </div>
                    <div style={styles.recordingActions}>
                      <a
                        href={`/api/recordings/${recording.id}/download`}
                        download
                        style={styles.downloadButton}
                      >
                        ⬇️ Download
                      </a>
                      <button
                        onClick={() => deleteRecording(recording.id)}
                        style={styles.deleteButton}
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          ) : (
            <div style={styles.snapshotsGrid}>
              {filteredSnapshots.length === 0 ? (
                <div style={styles.empty}>
                  <p>📷 No snapshots found.</p>
                  <p style={styles.emptyHint}>
                    Snapshots are captured during motion events and face detection.
                  </p>
                </div>
              ) : (
                filteredSnapshots.map((snapshot) => (
                  <div key={snapshot.id} style={styles.snapshotCard}>
                    <img
                      src={convertPathToUrl(snapshot.snapshot_path)}
                      alt={snapshot.camera_id}
                      style={styles.snapshotImage}
                      onClick={() => setSelectedRecording(snapshot)}
                      onError={(e) => {
                        console.error('Failed to load snapshot:', snapshot.snapshot_path);
                        e.target.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="100" height="100"%3E%3Ctext x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999"%3E❌%3C/text%3E%3C/svg%3E';
                      }}
                    />
                    <div style={styles.snapshotInfo}>
                      <p style={styles.snapshotCamera}>{snapshot.camera_id}</p>
                      <p style={styles.snapshotDate}>{formatDate(snapshot.detected_at)}</p>
                      {snapshot.faces_detected > 0 && (
                        <p style={styles.snapshotSize}>
                          👤 {snapshot.faces_detected} face{snapshot.faces_detected > 1 ? 's' : ''}
                        </p>
                      )}
                    </div>
                    <div style={styles.snapshotActions}>
                      <a
                        href={convertPathToUrl(snapshot.snapshot_path)}
                        download
                        style={styles.downloadButtonSmall}
                      >
                        ⬇️
                      </a>
                      <button
                        onClick={() => deleteSnapshot(snapshot.id)}
                        style={styles.deleteButtonSmall}
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Image Modal */}
      {selectedRecording && selectedRecording.snapshot_path && (
        <div style={styles.modal} onClick={() => setSelectedRecording(null)}>
          <div style={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setSelectedRecording(null)}
              style={styles.modalClose}
            >
              ✕
            </button>
            <img
              src={convertPathToUrl(selectedRecording.snapshot_path)}
              alt={selectedRecording.camera_id}
              style={styles.modalImage}
              onError={(e) => {
                console.error('Failed to load modal snapshot:', selectedRecording.snapshot_path);
                e.target.alt = '❌ Image failed to load';
              }}
            />
            <div style={styles.modalInfo}>
              <h3>{selectedRecording.camera_id}</h3>
              <p>{formatDate(selectedRecording.detected_at)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles = {
  container: {
    minHeight: '100vh',
    backgroundColor: 'var(--background)',
    color: 'var(--text)',
    padding: '20px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    marginBottom: '30px',
  },
  backButton: {
    padding: '10px 20px',
    backgroundColor: 'var(--primary)',
    color: 'var(--text)',
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '16px',
  },
  title: {
    margin: 0,
    fontSize: '32px',
    fontWeight: 'bold',
  },
  tabContainer: {
    display: 'flex',
    gap: '10px',
    marginBottom: '20px',
    borderBottom: '2px solid var(--border)',
  },
  tab: {
    padding: '12px 24px',
    backgroundColor: 'transparent',
    color: 'var(--text)',
    border: 'none',
    borderBottom: '3px solid transparent',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: '500',
    transition: 'all 0.3s ease',
  },
  activeTab: {
    borderBottomColor: 'var(--primary)',
    color: 'var(--primary)',
  },
  filterContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '20px',
    padding: '15px',
    backgroundColor: 'var(--card-background)',
    borderRadius: '8px',
  },
  filterLabel: {
    fontSize: '16px',
    fontWeight: '500',
  },
  filterSelect: {
    padding: '8px 12px',
    backgroundColor: 'var(--input-background)',
    color: 'var(--text)',
    border: '1px solid var(--border)',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  content: {
    marginTop: '20px',
  },
  loading: {
    textAlign: 'center',
    fontSize: '18px',
    padding: '40px',
  },
  error: {
    textAlign: 'center',
    color: '#ff4444',
    fontSize: '18px',
    padding: '40px',
  },
  empty: {
    textAlign: 'center',
    padding: '60px 20px',
  },
  emptyHint: {
    fontSize: '14px',
    opacity: 0.7,
    marginTop: '10px',
  },
  recordingsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
    gap: '20px',
  },
  recordingCard: {
    backgroundColor: 'var(--card-background)',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
  },
  recordingThumbnail: {
    width: '100%',
    aspectRatio: '16/9',
    backgroundColor: '#000',
  },
  videoPreview: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  recordingInfo: {
    padding: '15px',
  },
  recordingTitle: {
    margin: '0 0 10px 0',
    fontSize: '18px',
    fontWeight: 'bold',
  },
  recordingMeta: {
    margin: '5px 0',
    fontSize: '14px',
    opacity: 0.8,
  },
  recordingActions: {
    display: 'flex',
    gap: '10px',
    padding: '15px',
    borderTop: '1px solid var(--border)',
  },
  downloadButton: {
    flex: 1,
    padding: '10px',
    backgroundColor: 'var(--success)',
    color: '#fff',
    textDecoration: 'none',
    textAlign: 'center',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '500',
  },
  deleteButton: {
    flex: 1,
    padding: '10px',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
  },
  snapshotsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: '15px',
  },
  snapshotCard: {
    backgroundColor: 'var(--card-background)',
    borderRadius: '12px',
    overflow: 'hidden',
    boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
    cursor: 'pointer',
    transition: 'transform 0.2s ease',
  },
  snapshotImage: {
    width: '100%',
    aspectRatio: '4/3',
    objectFit: 'cover',
  },
  snapshotInfo: {
    padding: '10px',
  },
  snapshotCamera: {
    margin: '0 0 5px 0',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  snapshotDate: {
    margin: '0 0 5px 0',
    fontSize: '12px',
    opacity: 0.8,
  },
  snapshotSize: {
    margin: 0,
    fontSize: '12px',
    opacity: 0.6,
  },
  snapshotActions: {
    display: 'flex',
    gap: '5px',
    padding: '10px',
    borderTop: '1px solid var(--border)',
  },
  downloadButtonSmall: {
    flex: 1,
    padding: '8px',
    backgroundColor: 'var(--success)',
    color: '#fff',
    textDecoration: 'none',
    textAlign: 'center',
    borderRadius: '6px',
    fontSize: '14px',
  },
  deleteButtonSmall: {
    flex: 1,
    padding: '8px',
    backgroundColor: 'var(--danger)',
    color: '#fff',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  modal: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.9)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  modalContent: {
    position: 'relative',
    maxWidth: '90vw',
    maxHeight: '90vh',
    backgroundColor: 'var(--card-background)',
    borderRadius: '12px',
    padding: '20px',
  },
  modalClose: {
    position: 'absolute',
    top: '10px',
    right: '10px',
    backgroundColor: 'rgba(0,0,0,0.5)',
    color: '#fff',
    border: 'none',
    borderRadius: '50%',
    width: '40px',
    height: '40px',
    fontSize: '24px',
    cursor: 'pointer',
  },
  modalImage: {
    maxWidth: '100%',
    maxHeight: '70vh',
    objectFit: 'contain',
  },
  modalInfo: {
    marginTop: '15px',
    textAlign: 'center',
  },
};

export default RecordingsPage;
