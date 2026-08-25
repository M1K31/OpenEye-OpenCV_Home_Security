// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import CameraDiscoveryPage from './CameraDiscoveryPage';
import CameraSettingsModal from '../components/CameraSettingsModal';
import PTZControl from '../components/PTZControl';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';
import apiClient from '../api/apiClient';
import { Button, TextField, Switch } from '../components/universal';
import { describeApiError } from '../utils/apiError';

const CameraManagementPage = ({ embedded = false }) => {
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

  // Comprehensive camera settings modal state
  const [settingsCamera, setSettingsCamera] = useState(null);

  // camera_id currently being reconnected, or null. Reconnecting a sleeping
  // phone can take several seconds, so the button has to show it is working.
  const [reconnecting, setReconnecting] = useState(null);

  // PTZ control state
  const [ptzCamera, setPtzCamera] = useState(null);

  // Load cameras
  const loadCameras = async () => {
    setLoading(true);
    try {
      const response = await apiClient.get('/cameras/');
      // API returns {cameras: [...], total: n}
      const cameraData = response.data.cameras || [];
      setCameras(cameraData);
    } catch (err) {
      setError(`Failed to load cameras: ${describeApiError(err)}`);
      setCameras([]); // Ensure cameras remains an array on error
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
      await apiClient.post('/cameras/', manualForm);
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
      setError(`❌ Failed to add camera: ${describeApiError(err)}`);
    }
  };

  // Handle camera deletion
  const handleDeleteCamera = async (cameraId) => {
    if (!window.confirm(`Are you sure you want to delete camera "${cameraId}"?`)) {
      return;
    }

    try {
      await apiClient.delete(`/cameras/${cameraId}`);
      setSuccess(`✅ Camera "${cameraId}" deleted successfully!`);
      loadCameras();
    } catch (err) {
      setError(`❌ Failed to delete camera: ${describeApiError(err)}`);
    }
  };

  // Handle camera enable/disable toggle
  const handleToggleCamera = async (cameraId, currentState) => {
    try {
      await apiClient.patch(`/cameras/${cameraId}`, { is_active: !currentState });
      setSuccess(`✅ Camera ${!currentState ? 'enabled' : 'disabled'} successfully!`);
      loadCameras();
    } catch (err) {
      setError(`❌ Failed to toggle camera: ${describeApiError(err)}`);
    }
  };

  /**
   * Ask the server to drop a camera's capture handle and open it again.
   *
   * Nothing recovers a camera that went away and came back: the capture is
   * opened once at start and never reopened, so a phone that locks — or a USB
   * cable knocked loose and pushed back in — stays offline until the whole
   * service restarts. This is the manual escape hatch, and it matters most for
   * phones, which are *expected* to disconnect regularly.
   *
   * Deliberately slow to return: the server releases the device, waits for the
   * OS to finish tearing it down, then reopens. Reconnecting a sleeping phone
   * can take several seconds, so the button reports progress rather than
   * appearing to hang.
   */
  const handleReconnectCamera = async (cameraId) => {
    setReconnecting(cameraId);
    setError(null);
    setSuccess(null);
    try {
      const res = await apiClient.post(`/cameras/${cameraId}/reconnect`);
      if (res.data?.connected) {
        setSuccess(`✅ ${res.data.message || `Camera ${cameraId} reconnected.`}`);
      } else {
        // Not an error: a mobile camera that is simply away is the normal case.
        setError(`⚠️ ${res.data?.message || `Camera ${cameraId} did not come back.`}`);
      }
      loadCameras();
    } catch (err) {
      setError(`❌ Reconnect failed: ${describeApiError(err)}`);
    } finally {
      setReconnecting(null);
    }
  };


  if (activeTab === 'discover') {
    return <CameraDiscoveryPage onBack={() => setActiveTab('list')} />;
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
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
        <Button
          variant={activeTab === 'list' ? 'primary' : 'secondary'}
          size="medium"
          onClick={() => setActiveTab('list')}
          icon="📋"
        >
          Camera List
        </Button>
        <Button
          variant={activeTab === 'discover' ? 'primary' : 'secondary'}
          size="medium"
          onClick={() => setActiveTab('discover')}
          icon="🔍"
        >
          Discover Cameras
        </Button>
        <Button
          variant={activeTab === 'manual' ? 'primary' : 'secondary'}
          size="medium"
          onClick={() => setActiveTab('manual')}
          icon="➕"
        >
          Add Manually
        </Button>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="alert alert-error">
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">{error}</div>
          <Button
            variant="tertiary"
            size="small"
            onClick={() => setError(null)}
            style={{position: 'relative', marginLeft: 'auto'}}
          >
            ×
          </Button>
        </div>
      )}
      {success && (
        <div className="alert alert-success">
          <span className="alert-icon">✓</span>
          <div className="alert-content">{success}</div>
          <Button
            variant="tertiary"
            size="small"
            onClick={() => setSuccess(null)}
            style={{position: 'relative', marginLeft: 'auto'}}
          >
            ×
          </Button>
        </div>
      )}

      {/* Content Area */}
      <div style={styles.content}>
        {/* Camera List Tab */}
        {activeTab === 'list' && (
          <div>
            <div style={styles.sectionHeader}>
              <h2 style={styles.sectionTitle}>Your Cameras</h2>
              <Button
                variant="secondary"
                size="medium"
                onClick={loadCameras}
                disabled={loading}
                loading={loading}
                icon="🔄"
              >
                Refresh
              </Button>
            </div>

            {cameras.length === 0 && !loading ? (
              <div style={styles.emptyState}>
                <span style={styles.emptyIcon}>📹</span>
                <h3>No Cameras Configured</h3>
                <p>Get started by discovering cameras automatically or adding one manually</p>
                <div style={styles.emptyActions}>
                  <Button
                    variant="primary"
                    size="medium"
                    onClick={() => setActiveTab('discover')}
                    icon="🔍"
                  >
                    Discover Cameras
                  </Button>
                  <Button
                    variant="secondary"
                    size="medium"
                    onClick={() => setActiveTab('manual')}
                    icon="➕"
                  >
                    Add Manually
                  </Button>
                </div>
              </div>
            ) : (
              <div style={styles.cameraGrid}>
                {cameras.map((camera) => (
                  <div key={camera.camera_id} style={styles.cameraCard}>
                    <div style={styles.cardHeader}>
                      <div style={styles.cameraInfo}>
                        <h3 style={styles.cameraName}>{camera.camera_id}</h3>
                        <span style={styles.cameraType}>{camera.camera_type?.toUpperCase()}</span>
                      </div>
                      <div style={styles.statusBadge}>
                        {camera.is_active ? (
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
                      <Button
                        variant="primary"
                        size="small"
                        onClick={() => window.open(`/api/cameras/${camera.camera_id}/stream`, '_blank')}
                        icon="👁️"
                        title="View camera stream"
                      >
                        Stream
                      </Button>
                      <Button
                        variant="secondary"
                        size="small"
                        onClick={() => setSettingsCamera(camera)}
                        icon="⚙️"
                        title="Configure camera settings"
                      >
                        Config
                      </Button>
                      <Button
                        variant="secondary"
                        size="small"
                        onClick={() => setPtzCamera(camera)}
                        icon="🎮"
                        title="PTZ controls"
                      >
                        PTZ
                      </Button>
                      <Button
                        variant="secondary"
                        size="small"
                        onClick={() => handleReconnectCamera(camera.camera_id)}
                        disabled={reconnecting === camera.camera_id}
                        icon="🔄"
                        title="Drop the capture and open it again. Use after a phone has been away, or a camera was unplugged and reconnected."
                      >
                        {reconnecting === camera.camera_id ? 'Connecting…' : 'Reconnect'}
                      </Button>
                      <Button
                        variant={camera.is_active ? 'secondary' : 'primary'}
                        size="small"
                        onClick={() => handleToggleCamera(camera.camera_id, camera.is_active)}
                        icon={camera.is_active ? '⏸️' : '▶️'}
                        title={camera.is_active ? 'Disable camera' : 'Enable camera'}
                      >
                        {camera.is_active ? 'Disable' : 'Enable'}
                      </Button>
                      <Button
                        variant="destructive"
                        size="small"
                        onClick={() => handleDeleteCamera(camera.camera_id)}
                        icon="🗑️"
                        title="Delete camera"
                      >
                        Delete
                      </Button>
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
                    className="form-input"
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
                    className="form-input"
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
                    className="form-input"
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
                    className="form-input"
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
                    className="form-input"
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
                    className="form-input"
                  />
                  <small style={styles.hint}>Recommended: 15-30 FPS</small>
                </div>
              </div>

              <div style={styles.formRow}>
                <div style={styles.formGroup}>
                  <Switch
                    checked={manualForm.enabled}
                    onChange={(checked) => setManualForm({...manualForm, enabled: checked})}
                    label="Enable camera immediately"
                  />
                </div>

                <div style={styles.formGroup}>
                  <Switch
                    checked={manualForm.record_motion}
                    onChange={(checked) => setManualForm({...manualForm, record_motion: checked})}
                    label="Record on motion detection"
                  />
                </div>
              </div>

              <div style={styles.formActions}>
                <Button
                  type="submit"
                  variant="primary"
                  size="large"
                  icon="✅"
                >
                  Add Camera
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="large"
                  icon="🔄"
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
                >
                  Reset Form
                </Button>
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

      {/* Comprehensive Camera Settings Modal */}
      {settingsCamera && (
        <CameraSettingsModal
          camera={settingsCamera}
          onClose={() => setSettingsCamera(null)}
          onSave={loadCameras}
        />
      )}

      {/* PTZ Camera Control Panel */}
      {ptzCamera && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px',
          overflow: 'auto'
        }}>
          <div style={{
            backgroundColor: 'var(--card-background, #fff)',
            borderRadius: '8px',
            maxWidth: '900px',
            width: '100%',
            maxHeight: '90vh',
            overflow: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => setPtzCamera(null)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'var(--danger-color, #ef4444)',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: '600',
                zIndex: 10
              }}
            >
              ✕ Close
            </button>
            <PTZControl
              cameraId={ptzCamera.camera_id}
              cameraName={ptzCamera.name}
            />
          </div>
        </div>
      )}
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
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    color: 'var(--text-primary)',
  },
  header: {
    marginBottom: '30px',
  },
  backButton: {
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)',
    padding: '10px 20px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
    marginBottom: '15px',
  },
  title: {
    fontSize: '32px',
    color: 'var(--text-primary)',
    marginBottom: '10px',
  },
  subtitle: {
    fontSize: '16px',
    color: 'var(--text-secondary)',
  },
  tabContainer: {
    display: 'flex',
    gap: '10px',
    marginBottom: '20px',
    borderBottom: '2px solid var(--border-panel)',
  },
  tab: {
    background: 'transparent',
    border: 'none',
    padding: '15px 30px',
    fontSize: '16px',
    cursor: 'pointer',
    borderBottom: '3px solid transparent',
    transition: 'all 0.3s',
    color: 'var(--text-secondary)',
  },
  tabActive: {
    color: 'var(--text-link)',
    borderBottom: '3px solid var(--text-link)',
    fontWeight: 'bold',
  },
  alert: {
    error: {
      background: 'var(--danger-bg, rgba(220, 53, 69, 0.15))',
      border: '1px solid var(--color-error)',
      color: 'var(--color-error)',
      padding: '15px',
      borderRadius: '5px',
      marginBottom: '20px',
      position: 'relative',
    },
    success: {
      background: 'var(--success-bg, rgba(40, 167, 69, 0.15))',
      border: '1px solid var(--color-success)',
      color: 'var(--color-success)',
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
    background: 'var(--bg-panel)',
    borderRadius: '10px',
    padding: '30px',
    border: '1px solid var(--border-panel)',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '24px',
    color: 'var(--text-primary)',
    margin: 0,
  },
  sectionDescription: {
    color: 'var(--text-secondary)',
    marginBottom: '30px',
    lineHeight: '1.6',
  },
  refreshButton: {
    background: 'var(--text-link)',
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
    color: 'var(--text-secondary)',
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
    background: 'var(--bg-panel)',
    color: 'var(--text-link)',
    border: '2px solid var(--text-link)',
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
    background: 'var(--bg-main)',
    border: '2px solid var(--border-panel)',
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
    color: 'var(--color-success)',
  },
  statusDisabled: {
    color: 'var(--color-error)',
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
    color: 'var(--text-primary)',
    display: 'block',
    marginBottom: '5px',
  },
  value: {
    color: 'var(--text-secondary)',
    fontFamily: 'monospace',
    fontSize: '14px',
  },
  cardFooter: {
    padding: '15px',
    display: 'flex',
    flexWrap: 'wrap',
    gap: '8px',
    background: 'var(--bg-panel)',
  },
  viewButton: {
    flex: 1,
    background: 'var(--text-link)',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  enableButton: {
    flex: 1,
    background: 'var(--color-success)',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  disableButton: {
    flex: 1,
    background: 'var(--color-warning)',
    color: 'var(--bg-main)',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  deleteButton: {
    flex: 1,
    background: 'var(--color-error)',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  settingsButton: {
    flex: 1,
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    border: '2px solid var(--border-panel)',
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
    border: '2px solid var(--border-panel)',
    borderRadius: '5px',
    fontSize: '14px',
    fontFamily: 'inherit',
  },
  select: {
    padding: '12px',
    border: '2px solid var(--border-panel)',
    borderRadius: '5px',
    fontSize: '14px',
    fontFamily: 'inherit',
  },
  hint: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    marginTop: '5px',
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontSize: '14px',
    color: 'var(--text-primary)',
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
    background: 'var(--color-success)',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  resetButton: {
    background: 'var(--bg-panel)',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '16px',
  },
  helpSection: {
    background: 'var(--bg-main)',
    borderRadius: '10px',
    padding: '25px',
    marginTop: '40px',
  },
  helpTitle: {
    fontSize: '20px',
    color: 'var(--text-primary)',
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
    background: 'var(--bg-main)',
    color: 'var(--color-success)',
    padding: '10px',
    borderRadius: '5px',
    fontSize: '12px',
    wordBreak: 'break-all',
    marginTop: '10px',
    fontFamily: 'monospace',
  },
  modal: {
    overlay: {
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.7)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    },
    content: {
      backgroundColor: 'var(--bg-panel)',
      borderRadius: '12px',
      maxWidth: '600px',
      width: '90%',
      maxHeight: '90vh',
      overflow: 'auto',
      boxShadow: '0 10px 40px rgba(0,0,0,0.3)',
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '20px',
      borderBottom: '1px solid var(--border-panel)',
    },
    title: {
      margin: 0,
      fontSize: '24px',
      color: 'var(--text-primary)',
    },
    closeButton: {
      background: 'none',
      border: 'none',
      fontSize: '32px',
      cursor: 'pointer',
      color: 'var(--text-secondary)',
      padding: '0',
      width: '40px',
      height: '40px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    },
    body: {
      padding: '20px',
    },
    section: {
      marginBottom: '30px',
      paddingBottom: '20px',
      borderBottom: '1px solid var(--border-panel)',
    },
    sectionTitle: {
      fontSize: '18px',
      fontWeight: '600',
      color: 'var(--text-primary)',
      marginBottom: '15px',
    },
    formGroup: {
      marginBottom: '20px',
    },
    label: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      fontSize: '14px',
      fontWeight: '500',
      color: 'var(--text-primary)',
      marginBottom: '8px',
    },
    slider: {
      width: '100%',
      height: '8px',
      borderRadius: '4px',
      background: 'var(--border-panel)',
      outline: 'none',
      marginTop: '10px',
    },
    sliderLabels: {
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: '11px',
      color: 'var(--text-secondary)',
      marginTop: '5px',
    },
    hint: {
      fontSize: '12px',
      color: 'var(--text-secondary)',
      marginTop: '8px',
      display: 'block',
    },
    checkboxLabel: {
      display: 'flex',
      alignItems: 'center',
      gap: '10px',
      fontSize: '14px',
      color: 'var(--text-primary)',
      cursor: 'pointer',
    },
    checkbox: {
      width: '20px',
      height: '20px',
      cursor: 'pointer',
    },
    footer: {
      display: 'flex',
      gap: '15px',
      padding: '20px',
      borderTop: '1px solid var(--border-panel)',
      justifyContent: 'flex-end',
    },
    cancelButton: {
      background: 'var(--bg-main)',
      color: 'var(--text-primary)',
      border: '2px solid var(--border-panel)',
      padding: '12px 24px',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: '500',
    },
    saveButton: {
      background: 'var(--color-success)',
      color: 'white',
      border: 'none',
      padding: '12px 24px',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '14px',
      fontWeight: '500',
    },
  },
  modalCameraName: {
    fontSize: '20px',
    fontWeight: '600',
    color: 'var(--text-link)',
    marginBottom: '25px',
    paddingBottom: '15px',
    borderBottom: '2px solid var(--border-panel)',
  },
};

export default CameraManagementPage;
