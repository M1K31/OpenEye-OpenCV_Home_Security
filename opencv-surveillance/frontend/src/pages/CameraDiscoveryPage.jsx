// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const CameraDiscoveryPage = ({ onBack }) => {
  const [usbCameras, setUsbCameras] = useState([]);
  const [networkCameras, setNetworkCameras] = useState([]);
  const [scanning, setScanning] = useState({ usb: false, network: false });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Check network discovery status periodically
  useEffect(() => {
    let interval;
    if (scanning.network) {
      interval = setInterval(async () => {
        try {
          const response = await axios.get('/api/cameras/discover/status');
          if (!response.data.scanning) {
            setNetworkCameras(response.data.cameras || []);
            setScanning(prev => ({ ...prev, network: false }));
          }
        } catch (err) {
          console.error('Error checking discovery status:', err);
        }
      }, 2000); // Check every 2 seconds
    }
    return () => clearInterval(interval);
  }, [scanning.network]);

  const discoverUSB = async () => {
    setScanning({ ...scanning, usb: true });
    setError(null);
    setSuccess(null);

    try {
      const response = await axios.post('/api/cameras/discover/usb');
      setUsbCameras(response.data.cameras || []);
      setSuccess(`Found ${response.data.count} USB camera(s)`);
    } catch (err) {
      setError(`USB discovery failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setScanning({ ...scanning, usb: false });
    }
  };

  const discoverNetwork = async () => {
    setScanning({ ...scanning, network: true });
    setError(null);
    setSuccess(null);
    setNetworkCameras([]); // Clear previous results

    try {
      await axios.post('/api/cameras/discover/network', { subnet: null });
      setSuccess('Network scan started. This may take 30-60 seconds...');
    } catch (err) {
      setError(`Network discovery failed: ${err.response?.data?.detail || err.message}`);
      setScanning({ ...scanning, network: false });
    }
  };

  const testCamera = async (camera) => {
    try {
      const response = await axios.post('/api/cameras/discover/test', {
        camera_type: camera.type,
        source: camera.source || camera.index?.toString() || camera.auto_config?.source
      });
      
      if (response.data.success) {
        setSuccess(`✅ ${camera.name}: Connection successful!`);
        return true;
      } else {
        setError(`❌ ${camera.name}: ${response.data.error}`);
        return false;
      }
    } catch (err) {
      setError(`❌ Test failed: ${err.response?.data?.detail || err.message}`);
      return false;
    }
  };

  const quickAddCamera = async (camera) => {
    setError(null);
    setSuccess(null);

    try {
      const config = camera.auto_config || {
        camera_id: `camera_${Date.now()}`,
        camera_type: camera.type,
        source: camera.source || camera.index?.toString(),
        name: camera.name,
        enabled: true
      };

      await axios.post('/api/cameras/quick-add', config);
      setSuccess(`✅ Camera "${camera.name}" added successfully!`);
      
      // Remove from discovered list
      if (camera.type === 'usb') {
        setUsbCameras(prev => prev.filter(c => c.index !== camera.index));
      } else {
        setNetworkCameras(prev => prev.filter(c => c.ip !== camera.ip));
      }
    } catch (err) {
      setError(`❌ Failed to add camera: ${err.response?.data?.detail || err.message}`);
    }
  };

  const CameraCard = ({ camera, type }) => (
    <div style={styles.cameraCard}>
      <div style={styles.cardHeader}>
        <span style={styles.cameraIcon}>{type === 'usb' ? '🎥' : '📡'}</span>
        <h3 style={styles.cameraName}>{camera.name}</h3>
        <span style={styles.statusBadge}>{camera.status || 'available'}</span>
      </div>

      <div style={styles.cardBody}>
        {type === 'usb' ? (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>Device:</span>
              <span style={styles.value}>{camera.device_path}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Resolution:</span>
              <span style={styles.value}>{camera.resolution}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>FPS:</span>
              <span style={styles.value}>{camera.fps}</span>
            </div>
          </>
        ) : (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>IP Address:</span>
              <span style={styles.value}>{camera.ip}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Port:</span>
              <span style={styles.value}>{camera.port}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Stream URLs:</span>
              <select style={styles.urlSelect}>
                {camera.urls?.map((url, idx) => (
                  <option key={idx} value={url}>{url}</option>
                ))}
              </select>
            </div>
            {camera.requires_auth && (
              <div style={styles.authNote}>
                🔒 Authentication required. Try: admin/admin, admin/12345
              </div>
            )}
          </>
        )}
      </div>

      <div style={styles.cardFooter}>
        <button 
          onClick={() => testCamera(camera)}
          style={styles.testButton}
        >
          🔍 Test Connection
        </button>
        <button 
          onClick={() => quickAddCamera(camera)}
          style={styles.addButton}
        >
          ➕ Quick Add
        </button>
      </div>
    </div>
  );

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <button onClick={onBack} style={styles.backButton}>
          ← Back to Dashboard
        </button>
        <h1 style={styles.title}>🔍 Discover Cameras</h1>
        <p style={styles.subtitle}>
          Automatically find and configure cameras on your network or connected via USB
        </p>
      </div>

      {/* Alert Messages */}
      {error && (
        <div style={styles.alert.error}>
          ❌ {error}
        </div>
      )}
      {success && (
        <div style={styles.alert.success}>
          ✅ {success}
        </div>
      )}

      {/* USB Camera Discovery Section */}
      <section style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>🎥 USB & Built-in Cameras</h2>
          <button 
            onClick={discoverUSB}
            disabled={scanning.usb}
            style={{
              ...styles.scanButton,
              ...(scanning.usb ? styles.scanButton.disabled : {})
            }}
          >
            {scanning.usb ? '🔄 Scanning...' : '🔍 Scan for USB Cameras'}
          </button>
        </div>

        <p style={styles.sectionDescription}>
          Detects webcams and USB cameras connected directly to your system.
          No configuration needed - just click scan!
        </p>

        <div style={styles.cameraGrid}>
          {usbCameras.length === 0 && !scanning.usb ? (
            <div style={styles.emptyState}>
              <span style={styles.emptyIcon}>📷</span>
              <p>No USB cameras discovered yet</p>
              <p style={styles.emptyHint}>Click "Scan for USB Cameras" to detect connected devices</p>
            </div>
          ) : (
            usbCameras.map((camera, idx) => (
              <CameraCard key={`usb-${idx}`} camera={camera} type="usb" />
            ))
          )}
        </div>
      </section>

      {/* Network Camera Discovery Section */}
      <section style={styles.section}>
        <div style={styles.sectionHeader}>
          <h2 style={styles.sectionTitle}>📡 Network Cameras (RTSP/IP)</h2>
          <button 
            onClick={discoverNetwork}
            disabled={scanning.network}
            style={{
              ...styles.scanButton,
              ...(scanning.network ? styles.scanButton.disabled : {})
            }}
          >
            {scanning.network ? '🔄 Scanning Network...' : '🌐 Scan Network'}
          </button>
        </div>

        <p style={styles.sectionDescription}>
          Scans your local network for RTSP/IP cameras (Hikvision, Dahua, Amcrest, Reolink, etc.).
          This process takes 30-60 seconds.
        </p>

        {scanning.network && (
          <div style={styles.scanningIndicator}>
            <div style={styles.spinner}></div>
            <p>Scanning network for cameras...</p>
            <p style={styles.scanningNote}>This may take up to 60 seconds</p>
          </div>
        )}

        <div style={styles.cameraGrid}>
          {networkCameras.length === 0 && !scanning.network ? (
            <div style={styles.emptyState}>
              <span style={styles.emptyIcon}>📡</span>
              <p>No network cameras discovered yet</p>
              <p style={styles.emptyHint}>Click "Scan Network" to search for IP cameras</p>
            </div>
          ) : (
            networkCameras.map((camera, idx) => (
              <CameraCard key={`network-${idx}`} camera={camera} type="network" />
            ))
          )}
        </div>
      </section>

      {/* Help Section */}
      <section style={styles.helpSection}>
        <h3 style={styles.helpTitle}>💡 Tips & Compatibility</h3>
        <div style={styles.helpGrid}>
          <div style={styles.helpCard}>
            <h4>✅ Compatible Devices</h4>
            <ul style={styles.helpList}>
              <li>Any USB webcam or built-in camera</li>
              <li>RTSP/IP cameras (Hikvision, Dahua, Amcrest, Reolink)</li>
              <li>ONVIF-compatible cameras</li>
              <li>Most home security cameras with RTSP</li>
            </ul>
          </div>
          <div style={styles.helpCard}>
            <h4>❌ Not Compatible</h4>
            <ul style={styles.helpList}>
              <li>Nest cameras (proprietary protocol)</li>
              <li>Ring cameras (cloud-only)</li>
              <li>Arlo cameras (proprietary)</li>
              <li>Wyze cameras (without RTSP firmware)</li>
            </ul>
          </div>
          <div style={styles.helpCard}>
            <h4>🔐 Common Credentials</h4>
            <p style={styles.helpText}>If your camera requires authentication, try:</p>
            <ul style={styles.helpList}>
              <li>admin / admin</li>
              <li>admin / 12345</li>
              <li>admin / (blank)</li>
              <li>root / root</li>
            </ul>
          </div>
        </div>
      </section>
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
  alert: {
    error: {
      background: '#fee',
      border: '1px solid #fcc',
      color: '#c33',
      padding: '15px',
      borderRadius: '5px',
      marginBottom: '20px',
    },
    success: {
      background: '#efe',
      border: '1px solid #cfc',
      color: '#3c3',
      padding: '15px',
      borderRadius: '5px',
      marginBottom: '20px',
    },
  },
  section: {
    background: 'white',
    borderRadius: '10px',
    padding: '25px',
    marginBottom: '30px',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '15px',
  },
  sectionTitle: {
    fontSize: '24px',
    color: '#2c3e50',
    margin: 0,
  },
  scanButton: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    border: 'none',
    padding: '12px 30px',
    borderRadius: '25px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
    transition: 'transform 0.2s',
    disabled: {
      background: '#ccc',
      cursor: 'not-allowed',
      transform: 'none',
    },
  },
  sectionDescription: {
    color: '#7f8c8d',
    marginBottom: '20px',
    fontSize: '14px',
  },
  scanningIndicator: {
    textAlign: 'center',
    padding: '40px',
    background: '#f8f9fa',
    borderRadius: '10px',
    marginBottom: '20px',
  },
  spinner: {
    border: '4px solid #f3f3f3',
    borderTop: '4px solid #667eea',
    borderRadius: '50%',
    width: '50px',
    height: '50px',
    animation: 'spin 1s linear infinite',
    margin: '0 auto 20px',
  },
  scanningNote: {
    fontSize: '12px',
    color: '#7f8c8d',
    marginTop: '5px',
  },
  cameraGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
    gap: '20px',
  },
  cameraCard: {
    background: '#f8f9fa',
    border: '2px solid #e9ecef',
    borderRadius: '10px',
    overflow: 'hidden',
    transition: 'transform 0.2s, box-shadow 0.2s',
    cursor: 'pointer',
  },
  cardHeader: {
    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    color: 'white',
    padding: '15px',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  cameraIcon: {
    fontSize: '24px',
  },
  cameraName: {
    flex: 1,
    margin: 0,
    fontSize: '18px',
  },
  statusBadge: {
    background: 'rgba(255,255,255,0.3)',
    padding: '4px 12px',
    borderRadius: '12px',
    fontSize: '12px',
  },
  cardBody: {
    padding: '15px',
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: '10px',
    padding: '8px 0',
    borderBottom: '1px solid #e9ecef',
  },
  label: {
    fontWeight: 'bold',
    color: '#2c3e50',
  },
  value: {
    color: '#7f8c8d',
    fontFamily: 'monospace',
  },
  urlSelect: {
    width: '100%',
    padding: '5px',
    borderRadius: '5px',
    border: '1px solid #ddd',
    fontFamily: 'monospace',
    fontSize: '12px',
  },
  authNote: {
    background: '#fff3cd',
    padding: '10px',
    borderRadius: '5px',
    fontSize: '12px',
    marginTop: '10px',
    color: '#856404',
  },
  cardFooter: {
    padding: '15px',
    display: 'flex',
    gap: '10px',
    background: '#fff',
  },
  testButton: {
    flex: 1,
    background: '#17a2b8',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  addButton: {
    flex: 1,
    background: '#28a745',
    color: 'white',
    border: 'none',
    padding: '10px',
    borderRadius: '5px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 'bold',
  },
  emptyState: {
    textAlign: 'center',
    padding: '60px 20px',
    color: '#7f8c8d',
    gridColumn: '1 / -1',
  },
  emptyIcon: {
    fontSize: '64px',
    display: 'block',
    marginBottom: '20px',
  },
  emptyHint: {
    fontSize: '14px',
    color: '#95a5a6',
  },
  helpSection: {
    background: '#f8f9fa',
    borderRadius: '10px',
    padding: '25px',
  },
  helpTitle: {
    fontSize: '20px',
    color: '#2c3e50',
    marginBottom: '20px',
  },
  helpGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '20px',
  },
  helpCard: {
    background: 'var(--bg-panel)',
    padding: '20px',
    borderRadius: '8px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
    color: 'var(--text-primary)',
  },
  helpList: {
    listStyle: 'none',
    padding: 0,
    margin: '10px 0 0 0',
    color: 'var(--text-primary)',
  },
  helpText: {
    color: 'var(--text-primary)',
    fontSize: '14px',
    marginBottom: '10px',
    opacity: 0.8,
  },
};

// Add keyframe animation for spinner
const styleSheet = document.styleSheets[0];
styleSheet.insertRule(`
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
`, styleSheet.cssRules.length);

export default CameraDiscoveryPage;
