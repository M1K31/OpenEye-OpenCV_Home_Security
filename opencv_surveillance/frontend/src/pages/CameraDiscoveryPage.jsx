// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import apiClient from '../api/apiClient';
import { Button } from '../components/universal';
import { describeApiError } from '../utils/apiError';

const CameraCard = ({ camera, type, onTest, onQuickAdd, busyAction }) => {
  const defaultUrl =
    camera.urls?.[0] ||
    camera.auto_config?.source ||
    camera.source ||
    camera.index?.toString() ||
    '';
  const [selectedUrl, setSelectedUrl] = useState(defaultUrl);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [customName, setCustomName] = useState(camera.name || '');

  useEffect(() => {
    setSelectedUrl(
      camera.urls?.[0] ||
        camera.auto_config?.source ||
        camera.source ||
        camera.index?.toString() ||
        ''
    );
  }, [camera]);

  const cardKey = type === 'usb' ? `usb-${camera.index}` : `net-${camera.ip}-${camera.port}`;
  const isTesting = busyAction === `test-${cardKey}`;
  const isAdding = busyAction === `add-${cardKey}`;

  return (
    <div style={styles.cameraCard}>
      <div style={styles.cardHeader}>
        <span style={styles.cameraIcon} aria-hidden="true">
          {type === 'usb' ? '🎥' : '📡'}
        </span>
        <div style={styles.headerTextGroup}>
          <h3 style={styles.cameraName}>{camera.name}</h3>
          {camera.manufacturer && (
            <span style={styles.vendorSubtitle}>{camera.manufacturer}</span>
          )}
        </div>
        <span style={styles.statusBadge}>{camera.status || 'available'}</span>
      </div>

      <div style={styles.cardBody}>
        {type === 'usb' ? (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>Device</span>
              <span style={styles.value}>{camera.device_path}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Resolution</span>
              <span style={styles.value}>{camera.resolution}</span>
            </div>
            <div style={styles.infoRow}>
              <span style={styles.label}>Frame Rate</span>
              <span style={styles.value}>{camera.fps} FPS</span>
            </div>
          </>
        ) : (
          <>
            <div style={styles.infoRow}>
              <span style={styles.label}>IP & Port</span>
              <span style={styles.value}>
                {camera.ip}:{camera.port}
                {camera.onvif_port ? ` (ONVIF :${camera.onvif_port})` : ''}
              </span>
            </div>

            <div style={styles.fieldGroup}>
              <label style={styles.fieldLabel} htmlFor={`stream-url-${cardKey}`}>
                Stream Profile
              </label>
              <select
                id={`stream-url-${cardKey}`}
                style={styles.urlSelect}
                value={selectedUrl}
                onChange={(e) => setSelectedUrl(e.target.value)}
              >
                {camera.urls?.map((url, idx) => (
                  <option key={idx} value={url}>
                    {url}
                    {idx === 0 && url.endsWith('/stream1') ? ' (Main HD)' : ''}
                    {url.endsWith('/stream2') ? ' (Sub Low-CPU)' : ''}
                  </option>
                ))}
              </select>
            </div>

            <div style={styles.credentialsBox}>
              <div style={styles.credentialsHeader}>
                <span style={styles.credentialsTitle}>
                  {camera.requires_auth
                    ? '🔒 Camera Credentials Required'
                    : '🔑 Camera Credentials (Optional)'}
                </span>
                <span style={styles.encryptedBadge} title="Encrypted with Fernet at rest">
                  Encrypted at rest
                </span>
              </div>
              {camera.auth_hint && (
                <p style={styles.authHintText}>{camera.auth_hint}</p>
              )}
              <div style={styles.credentialsGrid}>
                <div style={styles.credentialField}>
                  <label style={styles.smallLabel} htmlFor={`cam-user-${cardKey}`}>
                    Username
                  </label>
                  <input
                    id={`cam-user-${cardKey}`}
                    type="text"
                    autoComplete="off"
                    placeholder="Camera username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    style={styles.textInput}
                  />
                </div>
                <div style={styles.credentialField}>
                  <label style={styles.smallLabel} htmlFor={`cam-pass-${cardKey}`}>
                    Password
                  </label>
                  <input
                    id={`cam-pass-${cardKey}`}
                    type="password"
                    autoComplete="new-password"
                    placeholder="Camera password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    style={styles.textInput}
                  />
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <div style={styles.cardFooter}>
        <Button
          onClick={() =>
            onTest(camera, {
              source: selectedUrl,
              username,
              password,
              cardKey,
            })
          }
          disabled={isTesting || isAdding}
          loading={isTesting}
          variant="secondary"
          size="medium"
          icon="🔍"
        >
          {isTesting ? 'Testing…' : 'Test Connection'}
        </Button>
        <Button
          onClick={() =>
            onQuickAdd(camera, {
              source: selectedUrl,
              username,
              password,
              name: customName || camera.name,
              cardKey,
            })
          }
          disabled={isTesting || isAdding}
          loading={isAdding}
          variant="primary"
          size="medium"
          icon="➕"
        >
          {isAdding ? 'Adding…' : 'Quick Add'}
        </Button>
      </div>
    </div>
  );
};

const CameraDiscoveryPage = ({ onBack }) => {
  const [usbCameras, setUsbCameras] = useState([]);
  const [networkCameras, setNetworkCameras] = useState([]);
  const [scanning, setScanning] = useState({ usb: false, network: false });
  const [busyAction, setBusyAction] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [customSubnet, setCustomSubnet] = useState('');

  // Stream incremental and final network discovery results
  useEffect(() => {
    let interval;
    let timeout;

    if (scanning.network) {
      timeout = setTimeout(() => {
        setScanning((prev) => ({ ...prev, network: false }));
        apiClient
          .get('/cameras/discover/status')
          .then((response) => {
            const found = response.data.cameras || [];
            setNetworkCameras(found);
            if (found.length > 0) {
              setSuccess(`Found ${found.length} network camera(s)`);
              setError(null);
            } else {
              setError('Network scan timed out with no cameras responding.');
            }
          })
          .catch((err) => console.error('Error fetching final status:', err));
      }, 75000);

      interval = setInterval(async () => {
        try {
          const response = await apiClient.get('/cameras/discover/status');
          const liveCameras = response.data.cameras || [];
          if (liveCameras.length > 0) {
            setNetworkCameras(liveCameras);
          }

          if (!response.data.scanning) {
            setNetworkCameras(liveCameras);
            setScanning((prev) => ({ ...prev, network: false }));

            const count = liveCameras.length;
            if (count > 0) {
              setSuccess(`Found ${count} network camera(s)`);
            } else {
              setSuccess('Network scan complete. No new RTSP cameras found.');
            }

            clearTimeout(timeout);
          }
        } catch (err) {
          console.error('Error checking discovery status:', err);
          setError(`Error checking scan status: ${describeApiError(err)}`);
          setScanning((prev) => ({ ...prev, network: false }));
          clearTimeout(timeout);
        }
      }, 1500);
    }

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [scanning.network]);

  const discoverUSB = async () => {
    setScanning((prev) => ({ ...prev, usb: true }));
    setError(null);
    setSuccess(null);

    try {
      const response = await apiClient.post('/cameras/discover/usb');
      setUsbCameras(response.data.cameras || []);
      if (response.data.permission_denied) {
        setError(response.data.warnings?.[0] || response.data.message);
      } else {
        setSuccess(response.data.message || `Found ${response.data.count} USB camera(s)`);
      }
    } catch (err) {
      setError(`USB discovery failed: ${describeApiError(err)}`);
    } finally {
      setScanning((prev) => ({ ...prev, usb: false }));
    }
  };

  const discoverNetwork = async () => {
    setScanning((prev) => ({ ...prev, network: true }));
    setError(null);
    setSuccess(null);
    setNetworkCameras([]);

    try {
      const subnetPayload = customSubnet.trim() ? customSubnet.trim() : null;
      await apiClient.post('/cameras/discover/network', { subnet: subnetPayload });
      setSuccess(
        'Scanning local network (ARP-prioritized fast probe + subnet sweep)…'
      );
    } catch (err) {
      setError(`Network discovery failed: ${describeApiError(err)}`);
      setScanning((prev) => ({ ...prev, network: false }));
    }
  };

  const testCamera = async (camera, options = {}) => {
    const cardKey = options.cardKey || camera.ip || camera.index;
    setBusyAction(`test-${cardKey}`);
    setError(null);
    setSuccess(null);

    try {
      const source =
        options.source ||
        camera.source ||
        camera.index?.toString() ||
        camera.auto_config?.source;

      const response = await apiClient.post('/cameras/discover/test', {
        camera_type: camera.type,
        source,
        username: options.username || undefined,
        password: options.password || undefined,
      });

      if (response.data.success) {
        setSuccess(
          `${camera.name}: Connected (${response.data.resolution || 'stream active'})`
        );
        return true;
      } else {
        setError(`${camera.name}: ${response.data.error}`);
        return false;
      }
    } catch (err) {
      setError(`Test failed: ${describeApiError(err)}`);
      return false;
    } finally {
      setBusyAction(null);
    }
  };

  const quickAddCamera = async (camera, options = {}) => {
    const cardKey = options.cardKey || camera.ip || camera.index;
    setBusyAction(`add-${cardKey}`);
    setError(null);
    setSuccess(null);

    try {
      const baseConfig = camera.auto_config || {
        camera_id: `camera_${Date.now()}`,
        camera_type: camera.type,
        source: camera.source || camera.index?.toString(),
        name: camera.name,
        enabled: true,
      };

      const payload = {
        ...baseConfig,
        source: options.source || baseConfig.source,
        name: options.name || camera.name,
        username: options.username || undefined,
        password: options.password || undefined,
      };

      await apiClient.post('/cameras/quick-add', payload);
      setSuccess(
        `Camera "${camera.name}" added and credentials encrypted at rest.`
      );

      if (camera.type === 'usb') {
        setUsbCameras((prev) => prev.filter((c) => c.index !== camera.index));
      } else {
        setNetworkCameras((prev) => prev.filter((c) => c.ip !== camera.ip));
      }
    } catch (err) {
      setError(`Failed to add camera: ${describeApiError(err)}`);
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        {onBack && (
          <div style={{ marginBottom: '12px' }}>
            <Button onClick={onBack} variant="secondary" size="small" icon="←">
              Back to Cameras
            </Button>
          </div>
        )}
        <h1 style={styles.title}>Discover Cameras</h1>
        <p style={styles.subtitle}>
          Automatically detect RTSP/ONVIF network cameras and local USB/Continuity cameras
        </p>
      </div>

      {error && <div style={styles.alert.error}>⚠️ {error}</div>}
      {success && <div style={styles.alert.success}>✓ {success}</div>}

      {/* USB Camera Discovery Section */}
      <section style={styles.section}>
        <div style={styles.sectionHeader}>
          <div>
            <h2 style={styles.sectionTitle}>USB & Built-in Cameras</h2>
            <p style={styles.sectionDescription}>
              Detects local USB webcams, built-in cameras, and Apple Continuity Cameras.
            </p>
          </div>
          <Button
            onClick={discoverUSB}
            disabled={scanning.usb}
            loading={scanning.usb}
            variant="primary"
            size="medium"
            icon={scanning.usb ? '🔄' : '🔍'}
          >
            {scanning.usb ? 'Scanning…' : 'Scan USB Cameras'}
          </Button>
        </div>

        <div style={styles.cameraGrid}>
          {usbCameras.length === 0 && !scanning.usb ? (
            <div style={styles.emptyState}>
              <span style={styles.emptyIcon} aria-hidden="true">📷</span>
              <p style={styles.emptyTitle}>No USB cameras discovered yet</p>
              <p style={styles.emptyHint}>
                Click "Scan USB Cameras" to probe attached video devices
              </p>
            </div>
          ) : (
            usbCameras.map((camera, idx) => (
              <CameraCard
                key={`usb-${camera.index ?? idx}`}
                camera={camera}
                type="usb"
                onTest={testCamera}
                onQuickAdd={quickAddCamera}
                busyAction={busyAction}
              />
            ))
          )}
        </div>
      </section>

      {/* Network Camera Discovery Section */}
      <section style={styles.section}>
        <div style={styles.sectionHeader}>
          <div>
            <h2 style={styles.sectionTitle}>Network Cameras (RTSP / ONVIF)</h2>
            <p style={styles.sectionDescription}>
              Discovers TP-Link Tapo, Hikvision, Dahua, Amcrest, Reolink, Axis, UniFi, and ONVIF cameras on your LAN.
            </p>
          </div>
          <div style={styles.networkControls}>
            <input
              type="text"
              placeholder="Auto-detect subnet (or e.g. 192.168.50.0/24)"
              value={customSubnet}
              onChange={(e) => setCustomSubnet(e.target.value)}
              style={styles.subnetInput}
              aria-label="Optional subnet CIDR to scan"
            />
            <Button
              onClick={discoverNetwork}
              disabled={scanning.network}
              loading={scanning.network}
              variant="primary"
              size="medium"
              icon={scanning.network ? '🔄' : '🌐'}
            >
              {scanning.network ? 'Scanning…' : 'Scan Network'}
            </Button>
          </div>
        </div>

        {scanning.network && (
          <div style={styles.scanningIndicator}>
            <div style={styles.spinner}></div>
            <p style={{ margin: '0 0 4px 0', fontWeight: 600 }}>
              Scanning local network for RTSP & ONVIF cameras…
            </p>
            <p style={styles.scanningNote}>
              Active ARP-cached cameras appear within seconds while the full subnet sweep completes.
            </p>
          </div>
        )}

        <div style={styles.cameraGrid}>
          {networkCameras.length === 0 && !scanning.network ? (
            <div style={styles.emptyState}>
              <span style={styles.emptyIcon} aria-hidden="true">📡</span>
              <p style={styles.emptyTitle}>No network cameras discovered yet</p>
              <p style={styles.emptyHint}>
                Click "Scan Network" to discover RTSP cameras on your local subnet
              </p>
            </div>
          ) : (
            networkCameras.map((camera, idx) => (
              <CameraCard
                key={`network-${camera.ip}-${camera.port}-${idx}`}
                camera={camera}
                type="network"
                onTest={testCamera}
                onQuickAdd={quickAddCamera}
                busyAction={busyAction}
              />
            ))
          )}
        </div>
      </section>

      {/* Help Section */}
      <section style={styles.helpSection}>
        <h3 style={styles.helpTitle}>Camera Compatibility & Setup Guide</h3>
        <div style={styles.helpGrid}>
          <div style={styles.helpCard}>
            <h4 style={styles.helpCardHeading}>TP-Link Tapo Cameras</h4>
            <p style={styles.helpText}>
              Tapo cameras expose RTSP on port <code>554</code> (<code>/stream1</code> for HD, <code>/stream2</code> for 360p) and ONVIF on port <code>2020</code>.
            </p>
            <p style={styles.helpText}>
              Create your camera credentials in the Tapo mobile app under <strong>Camera Settings → Advanced Settings → Camera Account</strong>.
            </p>
          </div>
          <div style={styles.helpCard}>
            <h4 style={styles.helpCardHeading}>Supported Manufacturers</h4>
            <ul style={styles.helpList}>
              <li>• TP-Link Tapo (C100, C110, C200, C210, C310, C320WS, etc.)</li>
              <li>• Hikvision, Annke & ONVIF Profile S cameras</li>
              <li>• Dahua, Amcrest & Lorex IP cameras</li>
              <li>• Reolink, Axis, Foscam & Ubiquiti UniFi</li>
            </ul>
          </div>
          <div style={styles.helpCard}>
            <h4 style={styles.helpCardHeading}>Security & Privacy</h4>
            <p style={styles.helpText}>
              Camera usernames and passwords are percent-encoded for special-character safety, redacted in API responses and logs, and encrypted at rest in SQLite using Fernet symmetric encryption.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

// Apple HIG-aligned styles using theme variables
const styles = {
  container: {
    padding: '24px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif',
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    color: 'var(--text-primary)',
  },
  header: {
    marginBottom: '28px',
  },
  title: {
    fontSize: '28px',
    fontWeight: 700,
    letterSpacing: '-0.02em',
    color: 'var(--text-primary)',
    margin: '0 0 6px 0',
  },
  subtitle: {
    fontSize: '15px',
    color: 'var(--text-secondary)',
    margin: 0,
  },
  alert: {
    error: {
      background: 'var(--error-bg, rgba(255, 59, 48, 0.12))',
      border: '1px solid var(--error-border, rgba(255, 59, 48, 0.35))',
      color: 'var(--error-text, #ff453a)',
      padding: '14px 18px',
      borderRadius: '10px',
      marginBottom: '20px',
      fontSize: '14px',
      fontWeight: 500,
    },
    success: {
      background: 'var(--success-bg, rgba(52, 199, 89, 0.12))',
      border: '1px solid var(--success-border, rgba(52, 199, 89, 0.35))',
      color: 'var(--success-text, #30d158)',
      padding: '14px 18px',
      borderRadius: '10px',
      marginBottom: '20px',
      fontSize: '14px',
      fontWeight: 500,
    },
  },
  section: {
    background: 'var(--bg-panel)',
    borderRadius: '14px',
    padding: '24px',
    marginBottom: '28px',
    border: '1px solid var(--border-panel)',
    boxShadow: '0 4px 14px var(--shadow, rgba(0,0,0,0.06))',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: '16px',
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '20px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    margin: '0 0 4px 0',
  },
  sectionDescription: {
    color: 'var(--text-secondary)',
    margin: 0,
    fontSize: '14px',
  },
  networkControls: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    flexWrap: 'wrap',
  },
  subnetInput: {
    padding: '8px 12px',
    borderRadius: '8px',
    border: '1px solid var(--border-panel)',
    background: 'var(--bg-input, var(--bg-main))',
    color: 'var(--text-primary)',
    fontSize: '13px',
    minWidth: '250px',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
  },
  scanningIndicator: {
    textAlign: 'center',
    padding: '28px 20px',
    background: 'var(--bg-input, var(--bg-main))',
    borderRadius: '12px',
    marginBottom: '20px',
    border: '1px solid var(--border-panel)',
  },
  spinner: {
    border: '3px solid var(--border-panel)',
    borderTop: '3px solid var(--accent-color, #007aff)',
    borderRadius: '50%',
    width: '36px',
    height: '36px',
    animation: 'spin 0.9s linear infinite',
    margin: '0 auto 14px',
  },
  scanningNote: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    margin: 0,
  },
  cameraGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
    gap: '20px',
  },
  cameraCard: {
    background: 'var(--bg-input, var(--bg-main))',
    border: '1px solid var(--border-panel)',
    borderRadius: '12px',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.06)',
  },
  cardHeader: {
    background: 'linear-gradient(135deg, #007aff 0%, #5856d6 100%)',
    color: 'white',
    padding: '14px 16px',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  cameraIcon: {
    fontSize: '22px',
  },
  headerTextGroup: {
    flex: 1,
    minWidth: 0,
  },
  cameraName: {
    margin: 0,
    fontSize: '16px',
    fontWeight: 600,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  vendorSubtitle: {
    display: 'block',
    fontSize: '12px',
    opacity: 0.9,
    marginTop: '2px',
  },
  statusBadge: {
    background: 'rgba(255, 255, 255, 0.22)',
    padding: '4px 10px',
    borderRadius: '999px',
    fontSize: '11px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.03em',
  },
  cardBody: {
    padding: '16px',
    flex: 1,
  },
  infoRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '10px',
    paddingBottom: '8px',
    borderBottom: '1px solid var(--border-panel)',
    fontSize: '13px',
  },
  label: {
    fontWeight: 600,
    color: 'var(--text-secondary)',
  },
  value: {
    color: 'var(--text-primary)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: '13px',
  },
  fieldGroup: {
    marginTop: '12px',
    marginBottom: '12px',
  },
  fieldLabel: {
    display: 'block',
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: '6px',
  },
  urlSelect: {
    width: '100%',
    padding: '8px 10px',
    borderRadius: '8px',
    border: '1px solid var(--border-panel)',
    background: 'var(--bg-panel)',
    color: 'var(--text-primary)',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    fontSize: '12px',
  },
  credentialsBox: {
    marginTop: '12px',
    padding: '12px',
    borderRadius: '10px',
    background: 'var(--bg-panel)',
    border: '1px solid var(--border-panel)',
  },
  credentialsHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '6px',
  },
  credentialsTitle: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-primary)',
  },
  encryptedBadge: {
    fontSize: '11px',
    padding: '2px 8px',
    borderRadius: '999px',
    background: 'rgba(52, 199, 89, 0.15)',
    color: 'var(--color-success, #30d158)',
    fontWeight: 600,
  },
  authHintText: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    margin: '0 0 10px 0',
    lineHeight: 1.4,
  },
  credentialsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '10px',
  },
  credentialField: {
    display: 'flex',
    flexDirection: 'column',
  },
  smallLabel: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-secondary)',
    marginBottom: '4px',
  },
  textInput: {
    padding: '7px 10px',
    borderRadius: '7px',
    border: '1px solid var(--border-panel)',
    background: 'var(--bg-input, var(--bg-main))',
    color: 'var(--text-primary)',
    fontSize: '13px',
    width: '100%',
    boxSizing: 'border-box',
  },
  cardFooter: {
    padding: '14px 16px',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '10px',
    background: 'var(--bg-panel)',
    borderTop: '1px solid var(--border-panel)',
  },
  emptyState: {
    textAlign: 'center',
    padding: '48px 20px',
    color: 'var(--text-secondary)',
    gridColumn: '1 / -1',
  },
  emptyIcon: {
    fontSize: '48px',
    display: 'block',
    marginBottom: '12px',
  },
  emptyTitle: {
    fontSize: '15px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    margin: '0 0 4px 0',
  },
  emptyHint: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    margin: 0,
  },
  helpSection: {
    background: 'var(--bg-panel)',
    borderRadius: '14px',
    padding: '24px',
    border: '1px solid var(--border-panel)',
  },
  helpTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: 'var(--text-primary)',
    margin: '0 0 16px 0',
  },
  helpGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
    gap: '16px',
  },
  helpCard: {
    background: 'var(--bg-input, var(--bg-main))',
    padding: '18px',
    borderRadius: '10px',
    border: '1px solid var(--border-panel)',
    color: 'var(--text-primary)',
  },
  helpCardHeading: {
    margin: '0 0 8px 0',
    fontSize: '15px',
    fontWeight: 600,
  },
  helpList: {
    listStyle: 'none',
    padding: 0,
    margin: '8px 0 0 0',
    fontSize: '13px',
    lineHeight: 1.7,
    color: 'var(--text-secondary)',
  },
  helpText: {
    color: 'var(--text-secondary)',
    fontSize: '13px',
    lineHeight: 1.5,
    margin: '0 0 8px 0',
  },
};

if (typeof document !== 'undefined' && document.styleSheets?.length > 0) {
  try {
    const styleSheet = document.styleSheets[0];
    styleSheet.insertRule(
      `
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `,
      styleSheet.cssRules.length
    );
  } catch (_) {
    // Ignore cross-origin stylesheet insertion errors
  }
}

export default CameraDiscoveryPage;
