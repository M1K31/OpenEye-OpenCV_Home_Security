import React, { useState, useEffect, useCallback } from 'react';
import { logger } from '../utils/logger';
import './PTZControl.css';
import apiClient from '../api/apiClient';

const PTZControl = ({ cameraId, cameraName }) => {
  const [activeTab, setActiveTab] = useState('manual');
  const [isConnected, setIsConnected] = useState(false);
  const [showConnectionForm, setShowConnectionForm] = useState(false);
  const [speed, setSpeed] = useState(0.5);
  const [zoom, setZoom] = useState(0.5);

  // Presets state
  const [presets, setPresets] = useState([]);
  const [loadingPresets, setLoadingPresets] = useState(false);

  // Patrol patterns state
  const [patterns, setPatterns] = useState([]);
  const [loadingPatterns, setLoadingPatterns] = useState(false);

  // Connection form state
  const [connectionData, setConnectionData] = useState({
    camera_ip: '',
    port: 80,
    username: '',
    password: '',
    ptz_type: 'onvif'
  });

  // Load presets and patterns on component mount
  useEffect(() => {
    if (cameraId) {
      loadPresets();
      loadPatterns();
      checkConnection();
    }
  }, [cameraId]);

  const checkConnection = async () => {
    try {
      const response = await apiClient.get(`/api/cameras/${cameraId}/ptz/status`);
      setIsConnected(response.data.connected);
    } catch (error) {
      setIsConnected(false);
    }
  };

  const handleConnect = async () => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/connect`, connectionData);
      setIsConnected(true);
      setShowConnectionForm(false);
      alert('PTZ connected successfully!');
    } catch (error) {
      logger.error('Failed to connect PTZ:', error);
      alert(error.response?.data?.detail || 'Failed to connect to PTZ camera');
    }
  };

  const handleDisconnect = async () => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/disconnect`);
      setIsConnected(false);
      alert('PTZ disconnected successfully!');
    } catch (error) {
      logger.error('Failed to disconnect PTZ:', error);
    }
  };

  // ===== Manual Control Functions =====

  const handleMove = async (pan, tilt) => {
    if (!isConnected) return;

    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/move/absolute`, {
        pan,
        tilt,
        zoom,
        speed
      });
    } catch (error) {
      logger.error('PTZ move failed:', error);
      alert(error.response?.data?.detail || 'PTZ move command failed');
    }
  };

  const handleContinuousMove = async (panVelocity, tiltVelocity, zoomVelocity = 0) => {
    if (!isConnected) return;

    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/move/continuous`, {
        pan_velocity: panVelocity,
        tilt_velocity: tiltVelocity,
        zoom_velocity: zoomVelocity
      });
    } catch (error) {
      logger.error('PTZ continuous move failed:', error);
    }
  };

  const handleStop = async () => {
    if (!isConnected) return;

    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/stop`);
    } catch (error) {
      logger.error('PTZ stop failed:', error);
    }
  };

  const handleZoomChange = (value) => {
    setZoom(parseFloat(value));
  };

  const handleZoomIn = () => {
    handleContinuousMove(0, 0, 0.5);
    setTimeout(() => handleStop(), 500);
  };

  const handleZoomOut = () => {
    handleContinuousMove(0, 0, -0.5);
    setTimeout(() => handleStop(), 500);
  };

  // ===== Preset Functions =====

  const loadPresets = async () => {
    setLoadingPresets(true);
    try {
      const response = await apiClient.get(`/api/cameras/${cameraId}/ptz/presets`);
      setPresets(response.data.presets);
    } catch (error) {
      logger.error('Failed to load presets:', error);
    } finally {
      setLoadingPresets(false);
    }
  };

  const handleGotoPreset = async (presetId, presetName) => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/presets/${presetId}/goto`, null, {
        params: { speed }
      });
      alert(`Moved to preset: ${presetName}`);
    } catch (error) {
      logger.error('Failed to goto preset:', error);
      alert(error.response?.data?.detail || 'Failed to move to preset');
    }
  };

  const handleDeletePreset = async (presetId, presetName) => {
    if (!confirm(`Delete preset "${presetName}"?`)) return;

    try {
      await apiClient.delete(`/api/cameras/${cameraId}/ptz/presets/${presetId}`);
      alert(`Deleted preset: ${presetName}`);
      loadPresets();
    } catch (error) {
      logger.error('Failed to delete preset:', error);
      alert(error.response?.data?.detail || 'Failed to delete preset');
    }
  };

  const handleAddPreset = () => {
    const name = prompt('Enter preset name:');
    if (!name) return;

    const presetNumber = prompt('Enter preset number (1-255):');
    if (!presetNumber || isNaN(presetNumber) || presetNumber < 1 || presetNumber > 255) {
      alert('Invalid preset number');
      return;
    }

    createPreset(name, parseInt(presetNumber));
  };

  const createPreset = async (name, presetNumber) => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/presets`, {
        name,
        preset_number: presetNumber,
        pan: 0,  // TODO: Get current position
        tilt: 0,
        zoom: zoom
      });
      alert(`Created preset: ${name}`);
      loadPresets();
    } catch (error) {
      logger.error('Failed to create preset:', error);
      alert(error.response?.data?.detail || 'Failed to create preset');
    }
  };

  // ===== Patrol Pattern Functions =====

  const loadPatterns = async () => {
    setLoadingPatterns(true);
    try {
      const response = await apiClient.get(`/api/cameras/${cameraId}/ptz/patrol-patterns`);
      setPatterns(response.data.patterns);
    } catch (error) {
      logger.error('Failed to load patrol patterns:', error);
    } finally {
      setLoadingPatterns(false);
    }
  };

  const handleStartPattern = async (patternId, patternName) => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/patrol-patterns/${patternId}/start`);
      alert(`Started patrol pattern: ${patternName}`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to start patrol pattern:', error);
      alert(error.response?.data?.detail || 'Failed to start patrol pattern');
    }
  };

  const handleStopPattern = async (patternId, patternName) => {
    try {
      await apiClient.post(`/api/cameras/${cameraId}/ptz/patrol-patterns/${patternId}/stop`);
      alert(`Stopped patrol pattern: ${patternName}`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to stop patrol pattern:', error);
      alert(error.response?.data?.detail || 'Failed to stop patrol pattern');
    }
  };

  const handleDeletePattern = async (patternId, patternName) => {
    if (!confirm(`Delete patrol pattern "${patternName}"?`)) return;

    try {
      await apiClient.delete(`/api/cameras/${cameraId}/ptz/patrol-patterns/${patternId}`);
      alert(`Deleted patrol pattern: ${patternName}`);
      loadPatterns();
    } catch (error) {
      logger.error('Failed to delete patrol pattern:', error);
      alert(error.response?.data?.detail || 'Failed to delete patrol pattern');
    }
  };

  const handleAddPattern = () => {
    alert('Pattern builder coming soon! For now, you can create patterns with 2-4 presets that will patrol in sequence.');
  };

  // ===== Render Functions =====

  const renderConnectionForm = () => (
    <div className="ptz-connection-form">
      <h4>Connect PTZ Camera</h4>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Camera IP Address</label>
        <input
          type="text"
          className="ptz-form-input"
          placeholder="192.168.1.100"
          value={connectionData.camera_ip}
          onChange={(e) => setConnectionData({ ...connectionData, camera_ip: e.target.value })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">ONVIF Port</label>
        <input
          type="number"
          className="ptz-form-input"
          value={connectionData.port}
          onChange={(e) => setConnectionData({ ...connectionData, port: parseInt(e.target.value) })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Username</label>
        <input
          type="text"
          className="ptz-form-input"
          value={connectionData.username}
          onChange={(e) => setConnectionData({ ...connectionData, username: e.target.value })}
        />
      </div>

      <div className="ptz-form-group">
        <label className="ptz-form-label">Password</label>
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
          className="ptz-form-btn primary"
          onClick={handleConnect}
        >
          Connect
        </button>
      </div>
    </div>
  );

  const renderManualControl = () => (
    <div className="ptz-manual-control">
      <div className="ptz-joystick-container">
        <div className="ptz-joystick">
          {/* Top row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(-0.5, 0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↖
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(0, 0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↑
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(0.5, 0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↗
          </button>

          {/* Middle row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(-0.5, 0, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ←
          </button>
          <button
            className="ptz-direction-btn center"
            onClick={handleStop}
            disabled={!isConnected}
          >
            ⬛
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(0.5, 0, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            →
          </button>

          {/* Bottom row */}
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(-0.5, -0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↙
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(0, -0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↓
          </button>
          <button
            className="ptz-direction-btn"
            onMouseDown={() => handleContinuousMove(0.5, -0.5, 0)}
            onMouseUp={handleStop}
            onMouseLeave={handleStop}
            disabled={!isConnected}
          >
            ↘
          </button>
        </div>

        <div className="ptz-zoom-controls">
          <div className="ptz-zoom-label">Zoom</div>
          <div className="ptz-zoom-buttons">
            <button
              className="ptz-zoom-btn"
              onClick={handleZoomIn}
              disabled={!isConnected}
            >
              +
            </button>
            <button
              className="ptz-zoom-btn"
              onClick={handleZoomOut}
              disabled={!isConnected}
            >
              −
            </button>
          </div>
        </div>
      </div>

      <div className="ptz-speed-control">
        <div className="ptz-speed-label">
          <span>Movement Speed</span>
          <span className="ptz-speed-value">{Math.round(speed * 100)}%</span>
        </div>
        <input
          type="range"
          className="ptz-speed-slider"
          min="0"
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
            Create preset positions for quick camera movements
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
                P: {preset.pan.toFixed(2)} | T: {preset.tilt.toFixed(2)} | Z: {preset.zoom.toFixed(2)}
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
        <span>Add Preset</span>
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
            Create automated patrol patterns with multiple positions
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
                    onClick={() => handleStopPattern(pattern.id, pattern.name)}
                  >
                    Stop
                  </button>
                ) : (
                  <button
                    className="ptz-pattern-btn start"
                    onClick={() => handleStartPattern(pattern.id, pattern.name)}
                    disabled={!isConnected}
                  >
                    Start
                  </button>
                )}
                <button
                  className="ptz-pattern-btn"
                  onClick={() => alert('Edit pattern feature coming soon!')}
                >
                  Edit
                </button>
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
        <span>Add Patrol Pattern</span>
      </button>
    </div>
  );

  return (
    <div className="ptz-control-container">
      <div className="ptz-control-header">
        <h3>PTZ Control - {cameraName}</h3>
        <div className="ptz-connection-status">
          <div className={`ptz-status-indicator ${isConnected ? 'connected' : ''}`}></div>
          <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          {isConnected ? (
            <button onClick={handleDisconnect} style={{ marginLeft: '8px', padding: '4px 12px', fontSize: '12px' }}>
              Disconnect
            </button>
          ) : (
            <button onClick={() => setShowConnectionForm(true)} style={{ marginLeft: '8px', padding: '4px 12px', fontSize: '12px' }}>
              Connect
            </button>
          )}
        </div>
      </div>

      {showConnectionForm && renderConnectionForm()}

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
          Presets
        </button>
        <button
          className={`ptz-tab ${activeTab === 'patterns' ? 'active' : ''}`}
          onClick={() => setActiveTab('patterns')}
        >
          Patrol Patterns
        </button>
      </div>

      <div className="ptz-control-content">
        {activeTab === 'manual' && renderManualControl()}
        {activeTab === 'presets' && renderPresets()}
        {activeTab === 'patterns' && renderPatterns()}
      </div>
    </div>
  );
};

export default PTZControl;
