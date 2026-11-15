import React, { useState, useEffect, useRef, useCallback } from 'react';
import { logger } from '../utils/logger';
import './PTZControl.css';
import apiClient from '../api/apiClient';
import { describeApiError } from '../utils/apiError';

const VENDOR_LABELS = {
  tapo: 'TP-Link Tapo',
  hikvision: 'Hikvision',
  dahua: 'Dahua / Amcrest',
  reolink: 'Reolink',
  axis: 'Axis',
  foscam: 'Foscam',
  unifi: 'UniFi Protect',
  generic: 'ONVIF Camera',
};

const PTZControl = ({ cameraId, cameraName, showViewerByDefault = true }) => {
  const [activeTab, setActiveTab] = useState('manual');
  const [isConnected, setIsConnected] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [showConnectionForm, setShowConnectionForm] = useState(false);
  const [speed, setSpeed] = useState(0.8); // Default 80% for brisk, responsive movement
  const [zoom, setZoom] = useState(0.5);
  const [currentPosition, setCurrentPosition] = useState({ pan: 0, tilt: 0, zoom: 0 });
  const [stepMode, setStepMode] = useState(true); // Step nudge on click vs Continuous hold

  // Integrated live camera viewer state
  const [showViewer, setShowViewer] = useState(Boolean(showViewerByDefault));
  const [showReticle, setShowReticle] = useState(true);
  const [streamNonce, setStreamNonce] = useState(() => Date.now());
  const [streamError, setStreamError] = useState(false);
  const [takingSnapshot, setTakingSnapshot] = useState(false);
  const [snapshotNotice, setSnapshotNotice] = useState('');

  const isHoldingRef = useRef(false);
  const pressStartRef = useRef(0);
  const stopTimeoutRef = useRef(null);
  const moveInFlightRef = useRef(false);
  const pendingMoveRef = useRef(null);

  const [ptzMeta, setPtzMeta] = useState({
    protocol: null,
    camera_ip: '',
    port: 2020,
    vendor_hint: 'generic',
    device_info: {},
    capabilities: { pan_tilt: true, zoom: false, home_position: true, presets: true },
    last_error: null,
  });

  // Quick hardware toggles (Smart Track & Privacy Mode)
  const [edgeSettings, setEdgeSettings] = useState({
    auto_tracking: false,
    privacy_mode: false,
  });
  const [togglingEdge, setTogglingEdge] = useState(false);

  // Presets state
  const [presets, setPresets] = useState([]);
  const [loadingPresets, setLoadingPresets] = useState(false);

  // Patrol patterns state
  const [patterns, setPatterns] = useState([]);
  const [loadingPatterns, setLoadingPatterns] = useState(false);

  // Connection form state (optional manual override)
  const [connectionData, setConnectionData] = useState({
    camera_ip: '',
    port: 2020,
    username: '',
    password: '',
    ptz_type: 'auto',
  });

  // Auto-connect and load presets/patterns on component mount
  useEffect(() => {
    if (cameraId) {
      setStreamError(false);
      setStreamNonce(Date.now());
      initializePTZ();
    }
    return () => {
      if (stopTimeoutRef.current) {
        clearTimeout(stopTimeoutRef.current);
      }
    };
  }, [cameraId]);

  const initializePTZ = async () => {
    setConnecting(true);
    await checkConnection(true);
    await Promise.all([loadPresets(), loadPatterns(), loadEdgeHardwareState()]);
    setConnecting(false);
  };

  const checkConnection = async (autoConnect = true) => {
    try {
      const response = await apiClient.get(
        `/cameras/${cameraId}/ptz/status?auto_connect=${autoConnect ? 'true' : 'false'}`
      );
      const data = response.data || {};
      setIsConnected(Boolean(data.connected));
      const pos = data.status?.position || data.position;
      if (pos && typeof pos === 'object') {
        setCurrentPosition({
          pan: Number(pos.pan || 0),
          tilt: Number(pos.tilt || 0),
          zoom: Number(pos.zoom || 0),
        });
        if (typeof pos.zoom === 'number') {
          setZoom(Number(pos.zoom));
        }
      }
      setPtzMeta({
        protocol: data.protocol || data.status?.protocol || null,
        camera_ip: data.camera_ip || data.status?.camera_ip || '',
        port: data.port || data.status?.port || 2020,
        vendor_hint: data.vendor_hint || data.status?.vendor_hint || 'generic',
        device_info: data.device_info || data.status?.device_info || {},
        capabilities: data.status?.capabilities || {
          pan_tilt: true,
          zoom: false,
          home_position: true,
          presets: true,
        },
        last_error: data.last_error || null,
      });
      if (data.camera_ip) {
        setConnectionData((prev) => ({
          ...prev,
          camera_ip: prev.camera_ip || data.camera_ip,
          port: data.port || prev.port,
        }));
      }
    } catch (error) {
      setIsConnected(false);
    }
  };

  const loadEdgeHardwareState = async () => {
    try {
      const res = await apiClient.get(`/cameras/${cameraId}/edge/capabilities`);
      if (res.data?.settings) {
        setEdgeSettings({
          auto_tracking: Boolean(res.data.settings.auto_tracking),
          privacy_mode: Boolean(res.data.settings.privacy_mode),
        });
      }
    } catch (error) {
      logger.debug('Edge capabilities not loaded in PTZ panel:', error);
    }
  };

  const handleToggleEdgeFeature = async (field) => {
    setTogglingEdge(true);
    const nextValue = !edgeSettings[field];
    try {
      const res = await apiClient.put(`/cameras/${cameraId}/edge/settings`, {
        [field]: nextValue,
      });
      if (res.data?.settings) {
        setEdgeSettings({
          auto_tracking: Boolean(res.data.settings.auto_tracking),
          privacy_mode: Boolean(res.data.settings.privacy_mode),
        });
      } else {
        setEdgeSettings((prev) => ({ ...prev, [field]: nextValue }));
      }
      if (field === 'privacy_mode' && !nextValue) {
        setTimeout(() => handleReloadStream(), 400);
      }
    } catch (error) {
      logger.error(`Failed to toggle ${field}:`, error);
      alert(describeApiError(error, `Failed to update ${field}`));
    } finally {
      setTogglingEdge(false);
    }
  };

  const handleReloadStream = () => {
    setStreamError(false);
    setStreamNonce(Date.now());
  };

  const handleTakeSnapshot = async () => {
    if (!cameraId || takingSnapshot) return;
    setTakingSnapshot(true);
    try {
      const res = await apiClient.post(`/cameras/${cameraId}/snapshot`);
      const savedPath = res.data?.snapshot_path || res.data?.filename || 'Saved';
      setSnapshotNotice(`Snapshot saved (${String(savedPath).split('/').pop()})`);
      setTimeout(() => setSnapshotNotice(''), 3500);
    } catch (error) {
      logger.error('Snapshot failed from PTZ viewer:', error);
      alert(describeApiError(error, 'Failed to capture snapshot'));
    } finally {
      setTakingSnapshot(false);
    }
  };

  const handleConnect = async (useStored = false) => {
    setConnecting(true);
    try {
      const payload = useStored ? { ptz_type: 'auto' } : connectionData;
      const response = await apiClient.post(`/cameras/${cameraId}/ptz/connect`, payload);
      const data = response.data || {};
      setIsConnected(true);
      setShowConnectionForm(false);
      setPtzMeta((prev) => ({
        ...prev,
        protocol: data.protocol || prev.protocol,
        camera_ip: data.camera_ip || prev.camera_ip,
        port: data.port || prev.port,
        vendor_hint: data.vendor_hint || prev.vendor_hint,
        device_info: data.device_info || prev.device_info,
        capabilities: data.status?.capabilities || prev.capabilities,
        last_error: null,
      }));
      loadPresets();
    } catch (error) {
      logger.error('Failed to connect PTZ:', error);
      alert(describeApiError(error, 'Failed to connect to PTZ camera'));
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/disconnect`);
      setIsConnected(false);
    } catch (error) {
      logger.error('Failed to disconnect PTZ:', error);
    }
  };

  // ===== Manual Control Functions (Coalesced for Zero Stacking Lag) =====

  const handleRelativeNudge = useCallback(
    async (panDir, tiltDir, zoomDir = 0) => {
      // Coalesce rapid clicks so we never stack overlapping SOAP calls
      if (moveInFlightRef.current) {
        pendingMoveRef.current = { panDir, tiltDir, zoomDir };
        return;
      }
      moveInFlightRef.current = true;
      try {
        const res = await apiClient.post(`/cameras/${cameraId}/ptz/move/relative`, {
          pan_delta: panDir * speed,
          tilt_delta: tiltDir * speed,
          zoom_delta: zoomDir * speed,
          speed,
        });
        if (!isConnected) setIsConnected(true);
        const pos = res.data?.position;
        if (pos && typeof pos === 'object') {
          setCurrentPosition({
            pan: Number(pos.pan || 0),
            tilt: Number(pos.tilt || 0),
            zoom: Number(pos.zoom || 0),
          });
        } else {
          setCurrentPosition((prev) => ({
            pan: Math.max(-1, Math.min(1, Number((prev.pan + panDir * speed * 0.2).toFixed(2)))),
            tilt: Math.max(-1, Math.min(1, Number((prev.tilt + tiltDir * speed * 0.2).toFixed(2)))),
            zoom: Math.max(0, Math.min(1, Number((prev.zoom + zoomDir * speed * 0.15).toFixed(2)))),
          }));
        }
      } catch (error) {
        logger.error('PTZ relative move failed:', error);
      } finally {
        moveInFlightRef.current = false;
        if (pendingMoveRef.current) {
          const next = pendingMoveRef.current;
          pendingMoveRef.current = null;
          handleRelativeNudge(next.panDir, next.tiltDir, next.zoomDir);
        }
      }
    },
    [cameraId, speed, isConnected]
  );

  const handleContinuousMove = async (panDir, tiltDir, zoomDir = 0) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/move/continuous`, {
        pan_velocity: panDir * speed,
        tilt_velocity: tiltDir * speed,
        zoom_velocity: zoomDir * speed,
      });
      if (!isConnected) setIsConnected(true);
    } catch (error) {
      logger.error('PTZ continuous move failed:', error);
    }
  };

  const handleStop = async () => {
    if (stopTimeoutRef.current) {
      clearTimeout(stopTimeoutRef.current);
      stopTimeoutRef.current = null;
    }
    pendingMoveRef.current = null;
    isHoldingRef.current = false;
    if (!isConnected) return;
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/stop`);
    } catch (error) {
      logger.error('PTZ stop failed:', error);
    }
  };

  const handleDirectionPress = (panDir, tiltDir) => {
    if (stopTimeoutRef.current) {
      clearTimeout(stopTimeoutRef.current);
      stopTimeoutRef.current = null;
    }
    if (stepMode) {
      handleRelativeNudge(panDir, tiltDir, 0);
    } else {
      isHoldingRef.current = true;
      pressStartRef.current = Date.now();
      handleContinuousMove(panDir, tiltDir, 0);
    }
  };

  const handleDirectionRelease = () => {
    if (stepMode || !isHoldingRef.current) return;
    isHoldingRef.current = false;
    const elapsed = Date.now() - pressStartRef.current;
    const minHoldMs = 380; // Ensure quick clicks in continuous mode still turn the motor
    if (elapsed < minHoldMs) {
      stopTimeoutRef.current = setTimeout(() => {
        handleStop();
      }, minHoldMs - elapsed);
    } else {
      handleStop();
    }
  };

  const handleGotoHome = async () => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/home`, null, {
        params: { speed },
      });
      setCurrentPosition({ pan: 0, tilt: 0, zoom: 0 });
    } catch (error) {
      logger.error('PTZ home failed:', error);
      alert(describeApiError(error, 'Failed to move to Home position'));
    }
  };

  const handleZoomIn = () => {
    if (stepMode) {
      handleRelativeNudge(0, 0, 0.5);
    } else {
      handleContinuousMove(0, 0, 0.8);
      setTimeout(() => handleStop(), 450);
    }
  };

  const handleZoomOut = () => {
    if (stepMode) {
      handleRelativeNudge(0, 0, -0.5);
    } else {
      handleContinuousMove(0, 0, -0.8);
      setTimeout(() => handleStop(), 450);
    }
  };

  // Keyboard shortcuts while PTZ Studio is open (Arrow keys, Home, +/-)
  useEffect(() => {
    const onKeyDown = (e) => {
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        handleRelativeNudge(0, 1.0, 0);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        handleRelativeNudge(0, -1.0, 0);
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handleRelativeNudge(-1.0, 0, 0);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleRelativeNudge(1.0, 0, 0);
      } else if (e.key === 'Home') {
        e.preventDefault();
        handleGotoHome();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [handleRelativeNudge]);

  // ===== Preset Functions =====

  const loadPresets = async () => {
    setLoadingPresets(true);
    try {
      const response = await apiClient.get(`/cameras/${cameraId}/ptz/presets`);
      setPresets(response.data.presets || []);
    } catch (error) {
      logger.error('Failed to load presets:', error);
    } finally {
      setLoadingPresets(false);
    }
  };

  const handleGotoPreset = async (presetId, presetName) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/presets/${presetId}/goto`, null, {
        params: { speed },
      });
    } catch (error) {
      logger.error('Failed to goto preset:', error);
      alert(describeApiError(error, `Failed to move to preset "${presetName}"`));
    }
  };

  const handleDeletePreset = async (presetId, presetName) => {
    if (!confirm(`Delete preset "${presetName}"?`)) return;

    try {
      await apiClient.delete(`/cameras/${cameraId}/ptz/presets/${presetId}`);
      loadPresets();
    } catch (error) {
      logger.error('Failed to delete preset:', error);
      alert(describeApiError(error, 'Failed to delete preset'));
    }
  };

  const handleAddPreset = () => {
    const name = prompt('Enter preset name (e.g., Front Door, Driveway):');
    if (!name) return;

    const nextSlot =
      presets.length > 0
        ? Math.min(255, Math.max(...presets.map((p) => p.preset_number || 1)) + 1)
        : 1;
    const presetNumber = prompt('Enter preset slot number (1-255):', String(nextSlot));
    if (!presetNumber || isNaN(presetNumber) || presetNumber < 1 || presetNumber > 255) {
      alert('Invalid preset number');
      return;
    }

    createPreset(name, parseInt(presetNumber, 10));
  };

  const createPreset = async (name, presetNumber) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/presets`, {
        name,
        preset_number: presetNumber,
        pan: currentPosition.pan,
        tilt: currentPosition.tilt,
        zoom: currentPosition.zoom || zoom,
      });
      loadPresets();
    } catch (error) {
      logger.error('Failed to create preset:', error);
      alert(describeApiError(error, 'Failed to create preset'));
    }
  };

  // ===== Patrol Pattern Functions =====

  const loadPatterns = async () => {
    setLoadingPatterns(true);
    try {
      const response = await apiClient.get(`/cameras/${cameraId}/ptz/patrol-patterns`);
      setPatterns(response.data.patterns || []);
    } catch (error) {
      logger.error('Failed to load patrol patterns:', error);
    } finally {
      setLoadingPatterns(false);
    }
  };

  const handleStartPattern = async (patternId) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/patrol-patterns/${patternId}/start`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to start patrol pattern:', error);
      alert(describeApiError(error, 'Failed to start patrol pattern'));
    }
  };

  const handleStopPattern = async (patternId) => {
    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/patrol-patterns/${patternId}/stop`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to stop patrol pattern:', error);
      alert(describeApiError(error, 'Failed to stop patrol pattern'));
    }
  };

  const handleDeletePattern = async (patternId, patternName) => {
    if (!confirm(`Delete patrol pattern "${patternName}"?`)) return;

    try {
      await apiClient.delete(`/cameras/${cameraId}/ptz/patrol-patterns/${patternId}`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to delete patrol pattern:', error);
      alert(describeApiError(error, 'Failed to delete patrol pattern'));
    }
  };

  const handleAddPattern = async () => {
    if (presets.length < 2) {
      alert('Save at least 2 presets first so you can build an automated patrol loop between them.');
      setActiveTab('presets');
      return;
    }
    const name = prompt('Enter patrol pattern name:', 'Perimeter Sweep');
    if (!name) return;

    const dwellStr = prompt('Seconds to stay at each preset position (5-120):', '10');
    const dwell = Math.max(2, Math.min(300, parseInt(dwellStr || '10', 10) || 10));

    try {
      await apiClient.post(`/cameras/${cameraId}/ptz/patrol-patterns`, {
        name,
        description: `Automated patrol across ${presets.length} saved presets`,
        pattern_steps: presets.map((p) => ({
          preset_id: p.id,
          pan: p.pan,
          tilt: p.tilt,
          zoom: p.zoom,
          dwell_time: dwell,
        })),
        loop_enabled: true,
        interval_seconds: dwell,
      });
      loadPatterns();
    } catch (error) {
      logger.error('Failed to create patrol pattern:', error);
      alert(describeApiError(error, 'Failed to create patrol pattern'));
    }
  };

  // ===== Render Functions =====

  const renderLiveViewer = () => (
    <div className="ptz-viewer-panel">
      <div className="ptz-viewer-toolbar">
        <div className="ptz-viewer-title">
          <span className={`ptz-live-dot ${!streamError && !edgeSettings.privacy_mode ? 'live' : 'offline'}`} />
          <span>Live Feed — {cameraName || cameraId}</span>
          {snapshotNotice && <span className="ptz-snapshot-pill">✓ {snapshotNotice}</span>}
        </div>
        <div className="ptz-viewer-actions">
          <button
            type="button"
            className="ptz-viewer-btn"
            onClick={() => setShowReticle((v) => !v)}
            title="Toggle center alignment crosshair"
          >
            🎯 Reticle: {showReticle ? 'ON' : 'OFF'}
          </button>
          <button
            type="button"
            className="ptz-viewer-btn"
            onClick={handleTakeSnapshot}
            disabled={takingSnapshot || streamError}
            title="Save a snapshot from the current camera angle"
          >
            {takingSnapshot ? '📸 Saving…' : '📸 Snapshot'}
          </button>
          <button
            type="button"
            className="ptz-viewer-btn"
            onClick={handleReloadStream}
            title="Reload live MJPEG stream"
          >
            ↻ Reload Feed
          </button>
        </div>
      </div>

      <div className="ptz-viewer-stage">
        {edgeSettings.privacy_mode ? (
          <div className="ptz-viewer-unavailable">
            <div className="ptz-viewer-icon">🙈</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Privacy Mask Active</div>
            <div style={{ fontSize: '12px' }}>
              Disable Privacy Mask to resume the live video feed and PTZ movement.
            </div>
            <button
              type="button"
              className="ptz-viewer-reconnect-btn"
              onClick={() => handleToggleEdgeFeature('privacy_mode')}
              disabled={togglingEdge}
            >
              👁️ Disable Privacy Mask
            </button>
          </div>
        ) : !streamError ? (
          <>
            <img
              key={`${cameraId}-${streamNonce}`}
              src={`/api/cameras/${cameraId}/stream?t=${streamNonce}`}
              alt={`${cameraName || cameraId} live PTZ preview`}
              className="ptz-viewer-image"
              onError={() => setStreamError(true)}
            />
            {showReticle && (
              <div className="ptz-reticle" aria-hidden="true">
                <div className="ptz-reticle-h" />
                <div className="ptz-reticle-v" />
                <div className="ptz-reticle-ring" />
              </div>
            )}
            <div className="ptz-video-hud">
              <button
                type="button"
                className="ptz-hud-edge up"
                onClick={() => handleRelativeNudge(0, 1.0, 0)}
                title="Tilt Up (ArrowUp)"
              >
                ▲
              </button>
              <button
                type="button"
                className="ptz-hud-edge down"
                onClick={() => handleRelativeNudge(0, -1.0, 0)}
                title="Tilt Down (ArrowDown)"
              >
                ▼
              </button>
              <button
                type="button"
                className="ptz-hud-edge left"
                onClick={() => handleRelativeNudge(-1.0, 0, 0)}
                title="Pan Left (ArrowLeft)"
              >
                ◀
              </button>
              <button
                type="button"
                className="ptz-hud-edge right"
                onClick={() => handleRelativeNudge(1.0, 0, 0)}
                title="Pan Right (ArrowRight)"
              >
                ▶
              </button>
              <div className="ptz-hud-corner-tools">
                <button
                  type="button"
                  className="ptz-hud-mini-btn"
                  onClick={handleGotoHome}
                  title="Move to Home position (Home key)"
                >
                  🏠 Home
                </button>
                <button
                  type="button"
                  className="ptz-hud-mini-btn"
                  onClick={handleAddPreset}
                  title="Save current angle as a PTZ preset"
                >
                  📍 +Preset
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="ptz-viewer-unavailable">
            <div className="ptz-viewer-icon">📡</div>
            <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Live Stream Unavailable</div>
            <div style={{ fontSize: '12px' }}>
              The camera stream is reconnecting or temporarily unreachable.
            </div>
            <button
              type="button"
              className="ptz-viewer-reconnect-btn"
              onClick={handleReloadStream}
            >
              ↻ Reconnect Live Feed
            </button>
          </div>
        )}
      </div>
    </div>
  );

  const renderConnectionForm = () => (
    <div className="ptz-connection-form">
      <h4>Manual PTZ Connection Override</h4>
      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
        OpenEye automatically uses the IP and encrypted credentials saved with this camera (ONVIF port 2020 for Tapo, 80/8000 for Hikvision, Dahua, Reolink, Axis). Override below only if your camera uses a custom port or separate ONVIF account.
      </p>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Camera IP Address</label>
        <input
          type="text"
          className="ptz-form-input"
          placeholder="192.168.50.135"
          value={connectionData.camera_ip}
          onChange={(e) => setConnectionData({ ...connectionData, camera_ip: e.target.value })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">ONVIF / Control Port (2020 = Tapo, 80 = Standard, 8000 = Reolink)</label>
        <input
          type="number"
          className="ptz-form-input"
          value={connectionData.port}
          onChange={(e) => setConnectionData({ ...connectionData, port: parseInt(e.target.value, 10) || 2020 })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Username (Leave blank to use saved camera username)</label>
        <input
          type="text"
          className="ptz-form-input"
          value={connectionData.username}
          onChange={(e) => setConnectionData({ ...connectionData, username: e.target.value })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Password (Leave blank to use saved camera password)</label>
        <input
          type="password"
          className="ptz-form-input"
          value={connectionData.password}
          onChange={(e) => setConnectionData({ ...connectionData, password: e.target.value })}
        />
      </div>

      <div className="ptz-form-actions">
        <button
          className="ptz-form-btn secondary"
          onClick={() => setShowConnectionForm(false)}
        >
          Cancel
        </button>
        <button
          className="ptz-form-btn secondary"
          onClick={() => handleConnect(true)}
        >
          Auto-Connect with Saved Credentials
        </button>
        <button
          className="ptz-form-btn primary"
          onClick={() => handleConnect(false)}
        >
          Connect Override
        </button>
      </div>
    </div>
  );

  const renderManualControl = () => (
    <div className="ptz-manual-control">
      {!isConnected && ptzMeta.last_error && (
        <div
          style={{
            padding: '10px 14px',
            marginBottom: '14px',
            borderRadius: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            fontSize: '13px',
          }}
        >
          <strong>Connection Notice:</strong> {ptzMeta.last_error}
        </div>
      )}

      {/* Quick Hardware Bar: Mode Switch, Home, Smart Track, Privacy Mode */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '8px',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '12px',
          padding: '10px 12px',
          borderRadius: '8px',
          backgroundColor: 'var(--bg-panel, rgba(255,255,255,0.04))',
          border: '1px solid var(--border-panel, rgba(255,255,255,0.1))',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="ptz-preset-btn"
            onClick={() => setStepMode(!stepMode)}
            title="Switch between Step Nudge (click) and Continuous Hold"
          >
            {stepMode ? '🎯 Mode: Step Nudge (Click)' : '🕹️ Mode: Continuous Hold'}
          </button>
          <button
            type="button"
            className="ptz-preset-btn"
            onClick={handleGotoHome}
            disabled={!isConnected}
            title="Return camera to Home position"
          >
            🏠 Home Position
          </button>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="ptz-preset-btn"
            disabled={togglingEdge}
            onClick={() => handleToggleEdgeFeature('auto_tracking')}
            style={{
              backgroundColor: edgeSettings.auto_tracking ? 'var(--color-success, #10b981)' : undefined,
              color: edgeSettings.auto_tracking ? '#fff' : undefined,
            }}
            title="Toggle camera on-board AI Auto-Tracking (Smart Track)"
          >
            {edgeSettings.auto_tracking ? '🏃 Smart Track: ON' : '🏃 Smart Track: OFF'}
          </button>
          <button
            type="button"
            className="ptz-preset-btn"
            disabled={togglingEdge}
            onClick={() => handleToggleEdgeFeature('privacy_mode')}
            style={{
              backgroundColor: edgeSettings.privacy_mode ? 'var(--color-warning, #f59e0b)' : undefined,
              color: edgeSettings.privacy_mode ? '#000' : undefined,
            }}
            title="Toggle physical lens Privacy Mask"
          >
            {edgeSettings.privacy_mode ? '🙈 Privacy Mask: ON' : '👁️ Privacy Mask: OFF'}
          </button>
        </div>
      </div>

      <div className="ptz-joystick-container">
        <div className="ptz-joystick">
          {/* Top row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(-1.0, 1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Left + Tilt Up"
          >
            ↖
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(0.0, 1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Tilt Up (or press ArrowUp)"
          >
            ↑
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(1.0, 1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Right + Tilt Up"
          >
            ↗
          </button>

          {/* Middle row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(-1.0, 0.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Left (or press ArrowLeft)"
          >
            ←
          </button>
          <button
            className="ptz-direction-btn center"
            onClick={handleStop}
            disabled={!isConnected}
            title="Stop Movement"
          >
            ⬛
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(1.0, 0.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Right (or press ArrowRight)"
          >
            →
          </button>

          {/* Bottom row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(-1.0, -1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Left + Tilt Down"
          >
            ↙
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(0.0, -1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Tilt Down (or press ArrowDown)"
          >
            ↓
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleDirectionPress(1.0, -1.0)}
            onMouseUp={handleDirectionRelease}
            onMouseLeave={handleDirectionRelease}
            disabled={!isConnected}
            title="Pan Right + Tilt Down"
          >
            ↘
          </button>
        </div>

        <div className="ptz-zoom-controls">
          <div className="ptz-zoom-label">
            Zoom {!ptzMeta.capabilities?.zoom && <span style={{ fontSize: '11px', opacity: 0.7 }}>(Pan/Tilt Model)</span>}
          </div>
          <div className="ptz-zoom-buttons">
            <button
              className="ptz-zoom-btn"
              onClick={handleZoomIn}
              disabled={!isConnected || !ptzMeta.capabilities?.zoom}
              title={ptzMeta.capabilities?.zoom ? 'Optical Zoom In' : 'Optical zoom motor not reported by this camera model'}
            >
              +
            </button>
            <button
              className="ptz-zoom-btn"
              onClick={handleZoomOut}
              disabled={!isConnected || !ptzMeta.capabilities?.zoom}
              title={ptzMeta.capabilities?.zoom ? 'Optical Zoom Out' : 'Optical zoom motor not reported by this camera model'}
            >
              −
            </button>
          </div>
        </div>
      </div>

      <div className="ptz-speed-control">
        <div className="ptz-speed-label">
          <span>Movement Speed / Step Size</span>
          <span className="ptz-speed-value">{Math.round(speed * 100)}%</span>
        </div>
        <input
          type="range"
          className="ptz-speed-slider"
          min="0.2"
          max="1"
          step="0.1"
          value={speed}
          onChange={(e) => setSpeed(parseFloat(e.target.value))}
        />
      </div>
    </div>
  );

  const renderPresets = () => (
    <div>
      {loadingPresets ? (
        <div className="ptz-loading">
          <div className="ptz-spinner"></div>
        </div>
      ) : presets.length === 0 ? (
        <div className="ptz-empty-state">
          <div className="ptz-empty-icon">📍</div>
          <h4 className="ptz-empty-title">No Presets Yet</h4>
          <p className="ptz-empty-message">
            Point the camera using Manual Control, then click "+ Save Current Position as Preset" below.
          </p>
        </div>
      ) : (
        <div className="ptz-preset-list">
          {presets.map((preset) => (
            <div key={preset.id} className="ptz-preset-card">
              <div className="ptz-preset-header">
                <div className="ptz-preset-name">{preset.name}</div>
                <div className="ptz-preset-number">#{preset.preset_number}</div>
              </div>
              <div className="ptz-preset-position">
                P: {Number(preset.pan || 0).toFixed(2)} | T: {Number(preset.tilt || 0).toFixed(2)} | Z: {Number(preset.zoom || 0).toFixed(2)}
              </div>
              <div className="ptz-preset-actions">
                <button
                  className="ptz-preset-btn"
                  onClick={() => handleGotoPreset(preset.id, preset.name)}
                  disabled={!isConnected}
                >
                  Go To
                </button>
                <button
                  className="ptz-preset-btn delete"
                  onClick={() => handleDeletePreset(preset.id, preset.name)}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        className="ptz-add-preset-btn"
        onClick={handleAddPreset}
        style={{ marginTop: '16px' }}
      >
        <span>+</span>
        <span>Save Current Position as Preset</span>
      </button>
    </div>
  );

  const renderPatterns = () => (
    <div>
      {loadingPatterns ? (
        <div className="ptz-loading">
          <div className="ptz-spinner"></div>
        </div>
      ) : patterns.length === 0 ? (
        <div className="ptz-empty-state">
          <div className="ptz-empty-icon">🔄</div>
          <h4 className="ptz-empty-title">No Patrol Patterns Yet</h4>
          <p className="ptz-empty-message">
            Create automated patrol loops across your saved presets
          </p>
        </div>
      ) : (
        <div className="ptz-pattern-list">
          {patterns.map((pattern) => (
            <div
              key={pattern.id}
              className={`ptz-pattern-card ${pattern.is_active ? 'active' : ''}`}
            >
              <div className="ptz-pattern-header">
                <div className="ptz-pattern-info">
                  <div className="ptz-pattern-name">{pattern.name}</div>
                  {pattern.description && (
                    <div className="ptz-pattern-description">{pattern.description}</div>
                  )}
                </div>
                <div className={`ptz-pattern-status ${pattern.is_active ? 'active' : 'inactive'}`}>
                  {pattern.is_active ? '● Running' : '○ Stopped'}
                </div>
              </div>

              <div className="ptz-pattern-steps">
                <div className="ptz-pattern-step">
                  📍 {pattern.pattern_steps.length} positions
                </div>
                <div className="ptz-pattern-step">
                  ⏱ {pattern.interval_seconds}s interval
                </div>
                <div className="ptz-pattern-step">
                  {pattern.loop_enabled ? '🔄 Loop enabled' : '▶ Single run'}
                </div>
              </div>

              <div className="ptz-pattern-actions">
                {pattern.is_active ? (
                  <button
                    className="ptz-pattern-btn stop"
                    onClick={() => handleStopPattern(pattern.id)}
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    className="ptz-pattern-btn start"
                    onClick={() => handleStartPattern(pattern.id)}
                    disabled={!isConnected}
                  >
                    Start
                  </button>
                )}
                <button
                  className="ptz-pattern-btn delete"
                  onClick={() => handleDeletePattern(pattern.id, pattern.name)}
                  disabled={pattern.is_active}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <button
        className="ptz-add-pattern-btn"
        onClick={handleAddPattern}
        style={{ marginTop: '16px' }}
      >
        <span>+</span>
        <span>Create Patrol Loop from Presets</span>
      </button>
    </div>
  );

  const vendorLabel = VENDOR_LABELS[ptzMeta.vendor_hint] || 'ONVIF Camera';
  const modelText = ptzMeta.device_info?.Model
    ? ` (${ptzMeta.device_info.Model})`
    : '';

  return (
    <div className="ptz-control-container">
      <div className="ptz-control-header">
        <div>
          <h3 style={{ margin: 0 }}>PTZ Control Studio — {cameraName || cameraId}</h3>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {vendorLabel}{modelText}
            {ptzMeta.camera_ip ? ` • ${ptzMeta.camera_ip}:${ptzMeta.port}` : ''}
            {' • '}
            <span>Tip: Use Arrow keys ↑↓←→ or on-video controls to steer</span>
          </div>
        </div>
        <div className="ptz-connection-status">
          <button
            type="button"
            className="ptz-viewer-btn"
            onClick={() => setShowViewer((v) => !v)}
            style={{ marginRight: '8px' }}
            title="Show or hide the live camera viewer next to the PTZ controls"
          >
            {showViewer ? '📺 Hide Viewer' : '📺 Show Live Viewer'}
          </button>
          <div className={`ptz-status-indicator ${isConnected ? 'connected' : ''}`}></div>
          <span>
            {connecting ? 'Auto-Connecting…' : isConnected ? 'Connected' : 'Disconnected'}
          </span>
          {!connecting && (
            <>
              <button
                onClick={() => handleConnect(true)}
                style={{ marginLeft: '8px', padding: '4px 10px', fontSize: '12px' }}
                title="Auto-connect using camera's saved credentials"
              >
                {isConnected ? 'Reconnect' : 'Auto-Connect'}
              </button>
              <button
                onClick={() => setShowConnectionForm(!showConnectionForm)}
                style={{ marginLeft: '6px', padding: '4px 10px', fontSize: '12px' }}
              >
                ⚙️ Port / Auth
              </button>
              {isConnected && (
                <button
                  onClick={handleDisconnect}
                  style={{ marginLeft: '6px', padding: '4px 10px', fontSize: '12px' }}
                >
                  Disconnect
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {showConnectionForm && renderConnectionForm()}

      <div className={`ptz-workspace-grid ${showViewer ? 'with-viewer' : 'controls-only'}`}>
        {showViewer && renderLiveViewer()}

        <div>
          <div className="ptz-control-tabs">
            <button
              className={`ptz-tab ${activeTab === 'manual' ? 'active' : ''}`}
              onClick={() => setActiveTab('manual')}
            >
              Manual Control
            </button>
            <button
              className={`ptz-tab ${activeTab === 'presets' ? 'active' : ''}`}
              onClick={() => setActiveTab('presets')}
            >
              Presets ({presets.length})
            </button>
            <button
              className={`ptz-tab ${activeTab === 'patterns' ? 'active' : ''}`}
              onClick={() => setActiveTab('patterns')}
            >
              Patrol Patterns ({patterns.length})
            </button>
          </div>

          <div className="ptz-control-content">
            {activeTab === 'manual' && renderManualControl()}
            {activeTab === 'presets' && renderPresets()}
            {activeTab === 'patterns' && renderPatterns()}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PTZControl;
