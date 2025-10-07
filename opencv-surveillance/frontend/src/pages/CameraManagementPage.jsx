// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CameraDiscoveryPage from './CameraDiscoveryPage';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';
import axios from 'axios';

const CameraManagementPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('list'); // 'list', 'discover', 'manual'
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  // Manual camera form state
  const [manualForm, setManualForm] = useState({
    camera_id: '',
    name: '',
    camera_type: 'rtsp',
    source: '',
    enabled: true,
    record_motion: true,
    fps: 30,
    resolution: '1920x1080'
  });

  // Load cameras
  const loadCameras = async () => {
    setLoading(true);
    try {
      const response = await axios.get('/api/cameras/');
      setCameras(response.data);
    } catch (err) {
      setError(`Failed to load cameras: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Initial load
  React.useEffect(() => {
    if (activeTab === 'list') {
      loadCameras();
    }
  }, [activeTab]);

  // Handle manual form submission
  const handleManualSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    try {
      await axios.post('/api/cameras/', manualForm);
      setSuccess(`✅ Camera "${manualForm.name}" added successfully!`);
      
      // Reset form
      setManualForm({
        camera_id: '',
        name: '',
        camera_type: 'rtsp',
        source: '',
        enabled: true,
        record_motion: true,
        fps: 30,
        resolution: '1920x1080'
      });
      
      // Reload camera list
      loadCameras();
    } catch (err) {
      setError(`❌ Failed to add camera: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Handle camera deletion
  const handleDeleteCamera = async (cameraId) => {
    if (!window.confirm(`Are you sure you want to delete camera "${cameraId}"?`)) {
      return;
    }

    try {
      await axios.delete(`/api/cameras/${cameraId}`);
      setSuccess(`✅ Camera "${cameraId}" deleted successfully!`);
      loadCameras();
    } catch (err) {
      setError(`❌ Failed to delete camera: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Handle camera enable/disable toggle
  const handleToggleCamera = async (cameraId, currentState) => {
    try {
      await axios.patch(`/api/cameras/${cameraId}`, { enabled: !currentState });
      setSuccess(`✅ Camera ${!currentState ? 'enabled' : 'disabled'} successfully!`);
      loadCameras();
    } catch (err) {
      setError(`❌ Failed to toggle camera: ${err.response?.data?.detail || err.message}`);
    }
  };

  if (activeTab === 'discover') {
    return <CameraDiscoveryPage onBack={() => setActiveTab('list')} />;
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <button onClick={() => navigate('/')} style={styles.backButton}>
          ← Back to Dashboard
        </button>
        <h1 style={styles.title}>
          📹 Camera Management
          <HelpButton 
            title="Camera Management"
            description="Add and manage surveillance cameras. Use 'Discovery' to auto-detect USB and network cameras, 'Manual' to add cameras by URL, or 'List' to view and manage existing cameras."
          />
        </h1>
        <p style={styles.subtitle}>
          Manage your surveillance cameras - add, configure, or discover new devices
        </p>
      </div>

      {/* Tab Navigation */}
      <div style={styles.tabContainer}>
        <button
          onClick={() => setActiveTab('list')}
          style={{
            ...styles.tab,
            ...(activeTab === 'list' ? styles.tabActive : {})
          }}
        >
          📋 Camera List
        </button>
        <button
          onClick={() => setActiveTab('discover')}
          style={{
            ...styles.tab,
            ...(activeTab === 'discover' ? styles.tabActive : {})
          }}
        >
          🔍 Discover Cameras
        </button>
        <button
          onClick={() => setActiveTab('manual')}
          style={{
            ...styles.tab,
            ...(activeTab === 'manual' ? styles.tabActive : {})
          }}
        >
          ➕ Add Manually
        </button>
      </div>

      {/* Alert Messages */}
      {error && (
        <div style={styles.alert.error}>
          {error}
          <button onClick={() => setError(null)} style={styles.closeAlert}>×</button>
        </div>
      )}
      {success && (
        <div style={styles.alert.success}>
          {success}
          <button onClick={() => setSuccess(null)} style={styles.closeAlert}>×</button>
        </div>
      )}

      {/* Content Area */}
      <div style={styles.content}>
        {/* Camera List Tab */}
        {activeTab === 'list' && (
          <div>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Your Cameras</h2>
              <button onClick={loadCameras} style={styles.refreshButton} disabled={loading}>
                {loading ? '🔄 Loading...' : '🔄 Refresh'}
              </button>
            </div>

            {cameras.length === 0 && !loading ? (
              <div style={styles.emptyState}>
                <span style={styles.emptyIcon}>📹</span>
                <h3>No Cameras Configured</h3>
                <p>Get started by discovering cameras automatically or adding one manually</p>
                <div style={styles.emptyActions}>
                  <button onClick={() => setActiveTab('discover')} style={styles.primaryButton}>
                    🔍 Discover Cameras
                  </button>
                  <button onClick={() => setActiveTab('manual')} style={styles.secondaryButton}>
                    ➕ Add Manually
                  </button>
                </div>
              </div>
            ) : (
              <div style={styles.cameraGrid}>
                {cameras.map((camera) => (
                  <div key={camera.camera_id} style={styles.cameraCard}>
                    <div style={styles.cardHeader}>
                      <div style={styles.cameraInfo}>
                        <h3 style={styles.cameraName}>{camera.name}</h3>
                        <span style={styles.cameraType}>{camera.camera_type?.toUpperCase()}</span>
                      </div>
                      <div style={styles.statusBadge}>
                        {camera.enabled ? (
                          <span style={styles.statusEnabled}>● Active</span>
                        ) : (
                          <span style={styles.statusDisabled}>○ Disabled</span>
                        )}
                      </div>
                    </div>

                    <div style={styles.cardBody}>
                      <div style={styles.infoRow}>
                        <span style={styles.label}>Camera ID:</span>
                        <span style={styles.value}>{camera.camera_id}</span>
                      </div>
                      <div style={styles.infoRow}>
                        <span style={styles.label}>Source:</span>
                        <span style={styles.value}>{camera.source}</span>
                      </div>
                      <div style={styles.infoRow}>
                        <span style={styles.label}>Resolution:</span>
                        <span style={styles.value}>{camera.resolution || 'Auto'}</span>
                      </div>
                      <div style={styles.infoRow}>
                        <span style={styles.label}>FPS:</span>
                        <span style={styles.value}>{camera.fps || 'Auto'}</span>
                      </div>
                      <div style={styles.infoRow}>
                        <span style={styles.label}>Recording:</span>
                        <span style={styles.value}>{camera.record_motion ? 'On Motion' : 'Disabled'}</span>
                      </div>
                    </div>

                    <div style={styles.cardFooter}>
                      <button
                        onClick={() => window.open(`/api/cameras/${camera.camera_id}/stream`, '_blank')}
                        style={styles.viewButton}
                      >
                        👁️ View Stream
                      </button>
                      <button
                        onClick={() => handleToggleCamera(camera.camera_id, camera.enabled)}
                        style={camera.enabled ? styles.disableButton : styles.enableButton}
                      >
                        {camera.enabled ? '⏸️ Disable' : '▶️ Enable'}
                      </button>
                      <button
                        onClick={() => handleDeleteCamera(camera.camera_id)}
                        style={styles.deleteButton}
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Manual Add Tab */}
        {activeTab === 'manual' && (
          <div>
            <h2 style={styles.sectionTitle}>Add Camera Manually</h2>
            <p style={styles.sectionDescription}>
              Configure a camera manually by providing its connection details. Use this for cameras
              that weren't automatically discovered or require custom configuration.
            </p>

            <form onSubmit={handleManualSubmit} style={styles.form}>
              <div style={styles.formRow}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Camera ID *</label>
                  <input
                    type="text"
                    value={manualForm.camera_id}
                    onChange={(e) => setManualForm({...manualForm, camera_id: e.target.value})}
                    placeholder="e.g., front_door_cam"
                    required
                    style={styles.input}
                  />
                  <small style={styles.hint}>Unique identifier (no spaces, use underscores)</small>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Camera Name *</label>
                  <input
                    type="text"
                    value={manualForm.name}
                    onChange={(e) => setManualForm({...manualForm, name: e.target.value})}
                    placeholder="e.g., Front Door"
                    required
                    style={styles.input}
                  />
                  <small style={styles.hint}>Friendly display name</small>
                </div>
              </div>

              <div style={styles.formRow}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Camera Type *</label>
                  <select
                    value={manualForm.camera_type}
                    onChange={(e) => setManualForm({...manualForm, camera_type: e.target.value})}
                    style={styles.select}
                  >
                    <option value="rtsp">RTSP (Network Camera)</option>
                    <option value="usb">USB Camera</option>
                    <option value="http">HTTP/MJPEG</option>
                    <option value="mock">Mock Camera (Testing)</option>
                  </select>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>Source/URL *</label>
                  <input
                    type="text"
                    value={manualForm.source}
                    onChange={(e) => setManualForm({...manualForm, source: e.target.value})}
                    placeholder={
                      manualForm.camera_type === 'rtsp' ? 'rtsp://192.168.1.100:554/stream' :
                      manualForm.camera_type === 'usb' ? '0' :
                      manualForm.camera_type === 'http' ? 'http://192.168.1.100/mjpeg' :
                      'mock_stream'
                    }
                    required
                    style={styles.input}
                  />
                  <small style={styles.hint}>
                    {manualForm.camera_type === 'rtsp' && 'RTSP URL with credentials if needed'}
                    {manualForm.camera_type === 'usb' && 'USB device index (0, 1, 2, etc.)'}
                    {manualForm.camera_type === 'http' && 'HTTP stream URL'}
                    {manualForm.camera_type === 'mock' && 'Mock camera identifier'}
                  </small>
                </div>
              </div>

              <div style={styles.formRow}>
                <div style={styles.formGroup}>
                  <label style={styles.label}>Resolution</label>
                  <input
                    type="text"
                    value={manualForm.resolution}
                    onChange={(e) => setManualForm({...manualForm, resolution: e.target.value})}
                    placeholder="1920x1080"
                    style={styles.input}
                  />
                  <small style={styles.hint}>e.g., 1920x1080, 1280x720 (leave blank for auto)</small>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.label}>FPS (Frames Per Second)</label>
                  <input
                    type="number"
                    value={manualForm.fps}
                    onChange={(e) => setManualForm({...manualForm, fps: parseInt(e.target.value)})}
                    min="1"
                    max="60"
                    style={styles.input}
                  />
                  <small style={styles.hint}>Recommended: 15-30 FPS</small>
                </div>
              </div>

              <div style={styles.formRow}>
                <div style={styles.formGroup}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={manualForm.enabled}
                      onChange={(e) => setManualForm({...manualForm, enabled: e.target.checked})}
                      style={styles.checkbox}
                    />
                    Enable camera immediately
                  </label>
                </div>

                <div style={styles.formGroup}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={manualForm.record_motion}
                      onChange={(e) => setManualForm({...manualForm, record_motion: e.target.checked})}
                      style={styles.checkbox}
                    />
                    Record on motion detection
                  </label>
                </div>
              </div>

              <div style={styles.formActions}>
                <button type="submit" style={styles.submitButton}>
                  ✅ Add Camera
                </button>
                <button
                  type="button"
                  onClick={() => setManualForm({
                    camera_id: '',
                    name: '',
                    camera_type: 'rtsp',
                    source: '',
                    enabled: true,
                    record_motion: true,
                    fps: 30,
                    resolution: '1920x1080'
                  })}
                  style={styles.resetButton}
                >
                  🔄 Reset Form
                </button>
              </div>
            </form>

            {/* Help Section */}
            <div style={styles.helpSection}>
              <h3 style={styles.helpTitle}>💡 Common RTSP URL Formats</h3>
              <div style={styles.helpGrid}>
                <div style={styles.helpCard}>
                  <h4>Hikvision</h4>
                  <code style={styles.code}>rtsp://admin:password@IP:554/Streaming/Channels/101</code>
                </div>
                <div style={styles.helpCard}>
                  <h4>Dahua/Amcrest</h4>
                  <code style={styles.code}>rtsp://admin:password@IP:554/cam/realmonitor?channel=1&subtype=0</code>
                </div>
                <div style={styles.helpCard}>
                  <h4>Reolink</h4>
                  <code style={styles.code}>rtsp://admin:password@IP:554/h264Preview_01_main</code>
                </div>
                <div style={styles.helpCard}>
                  <h4>Generic ONVIF</h4>
                  <code style={styles.code}>rtsp://admin:password@IP:554/stream1</code>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// Styles
const styles = {
  container: {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'Arial, sans-serif',
  },
  header: {
    marginBottom: '30px',
  },
  backButton: {
    background: '#6c757d',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
    marginBottom: '15px',
  },
  title: {
    fontSize: '32px',
    color: '#2c3e50',
    marginBottom: '10px',
  },
  subtitle: {
    fontSize: '16px',
    color: '#7f8c8d',
  },
  tabContainer: {
    display: 'flex',
    gap: '10px',
    marginBottom: '20px',
    borderBottom: '2px solid #e9ecef',
  },
  tab: {
    background: 'transparent',
    border: 'none',
    padding: '15px 30px',
    fontSize: '16px',
    cursor: 'pointer',
    borderBottom: '3px solid transparent',
    transition: 'all 0.3s',
    color: '#7f8c8d',
  },
  tabActive: {
    color: '#667eea',
    borderBottom: '3px solid #667eea',
    fontWeight: 'bold',
  },
  alert: {
    error: {
      background: '#fee',
      border: '1px solid #fcc',
      color: '#c33',
      padding: '15px',
      borderRadius: '5px',
      marginBottom: '20px',
      position: 'relative',
    },
    success: {
      background: '#efe',
      border: '1px solid #cfc',
      color: '#3c3',
      padding: '15px',
      borderRadius: '5px',
      marginBottom: '20px',
      position: 'relative',
    },
  },
  closeAlert: {
    position: 'absolute',
    right: '10px',
    top: '10px',
    background: 'transparent',
    border: 'none',
    fontSize: '24px',
    cursor: 'pointer',
    color: 'inherit',
  },
  content: {
    background: 'white',
    borderRadius: '10px',
    padding: '30px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '24px',
    color: '#2c3e50',
    margin: 0,
  },
  sectionDescription: {
    color: '#7f8c8d',
    marginBottom: '30px',
    lineHeight: '1.6',
  },
  refreshButton: {
    background: '#17a2b8',
    color: 'white',
    border: 'none',
    padding: '10px 20px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  emptyState: {
    textAlign: 'center',
    padding: '80px 20px',
    color: '#7f8c8d',
  },
  emptyIcon: {
    fontSize: '64px',
    display: 'block',
    marginBottom: '20px',
  },
  emptyActions: {
    display: 'flex',
    gap: '15px',
    justifyContent: 'center',
    marginTop: '30px',
  },
  primaryButton: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '25px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  secondaryButton: {
    background: '#fff',
    color: '#667eea',
    border: '2px solid #667eea',
    padding: '15px 40px',
    borderRadius: '25px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  cameraGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(400px, 1fr))',
    gap: '20px',
  },
  cameraCard: {
    background: '#f8f9fa',
    border: '2px solid #e9ecef',
    borderRadius: '10px',
    overflow: 'hidden',
  },
  cardHeader: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '15px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  cameraInfo: {
    flex: 1,
  },
  cameraName: {
    margin: '0 0 5px 0',
    fontSize: '18px',
  },
  cameraType: {
    background: 'rgba(255,255,255,0.3)',
    padding: '2px 8px',
    borderRadius: '10px',
    fontSize: '12px',
  },
  statusBadge: {
    fontSize: '14px',
  },
  statusEnabled: {
    color: '#4ade80',
  },
  statusDisabled: {
    color: '#f87171',
  },
  cardBody: {
    padding: '15px',
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    padding: '8px 0',
    borderBottom: '1px solid #e9ecef',
  },
  label: {
    fontWeight: 'bold',
    color: '#2c3e50',
    display: 'block',
    marginBottom: '5px',
  },
  value: {
    color: '#7f8c8d',
    fontFamily: 'monospace',
    fontSize: '14px',
  },
  cardFooter: {
    padding: '15px',
    display: 'flex',
    gap: '10px',
    background: '#fff',
  },
  viewButton: {
    flex: 1,
    background: '#17a2b8',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  enableButton: {
    flex: 1,
    background: '#28a745',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  disableButton: {
    flex: 1,
    background: '#ffc107',
    color: '#000',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  deleteButton: {
    flex: 1,
    background: '#dc3545',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  form: {
    marginBottom: '40px',
  },
  formRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
    marginBottom: '20px',
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
  },
  input: {
    padding: '12px',
    border: '2px solid #e9ecef',
    borderRadius: '5px',
    fontSize: '14px',
    fontFamily: 'inherit',
  },
  select: {
    padding: '12px',
    border: '2px solid #e9ecef',
    borderRadius: '5px',
    fontSize: '14px',
    fontFamily: 'inherit',
  },
  hint: {
    fontSize: '12px',
    color: '#7f8c8d',
    marginTop: '5px',
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '14px',
    color: '#2c3e50',
  },
  checkbox: {
    width: '20px',
    height: '20px',
  },
  formActions: {
    display: 'flex',
    gap: '15px',
    marginTop: '30px',
  },
  submitButton: {
    background: '#28a745',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  resetButton: {
    background: '#6c757d',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '16px',
  },
  helpSection: {
    background: '#f8f9fa',
    borderRadius: '10px',
    padding: '25px',
    marginTop: '40px',
  },
  helpTitle: {
    fontSize: '20px',
    color: '#2c3e50',
    marginBottom: '20px',
  },
  helpGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '15px',
  },
  helpCard: {
    background: 'white',
    padding: '15px',
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  },
  code: {
    display: 'block',
    background: '#2c3e50',
    color: '#4ade80',
    padding: '10px',
    borderRadius: '5px',
    fontSize: '12px',
    wordBreak: 'break-all',
    marginTop: '10px',
    fontFamily: 'monospace',
  },
};

export default CameraManagementPage;
