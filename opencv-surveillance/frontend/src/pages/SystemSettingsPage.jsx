// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SystemSettingsPage = ({ embedded = false }) => {
  const [settings, setSettings] = useState({
    recordings_path: '',
    faces_path: '',
    display_mode: 'grid',
    cycle_interval: 5,
    max_recording_duration: 300,
    theme: 'dark',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [pathValidation, setPathValidation] = useState({});
  const [cameras, setCameras] = useState([]);

  // Load settings and cameras
  useEffect(() => {
    loadSettings();
    loadCameras();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await axios.get('/api/settings');
      setSettings(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Error loading settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
      setLoading(false);
    }
  };

  const loadCameras = async () => {
    try {
      const response = await axios.get('/api/cameras/');
      setCameras(response.data.cameras || []);
    } catch (error) {
      console.error('Error loading cameras:', error);
    }
  };

  const validatePath = async (path, pathType) => {
    if (!path || path.trim() === '') {
      setPathValidation(prev => ({
        ...prev,
        [pathType]: { valid: false, message: 'Path cannot be empty' }
      }));
      return false;
    }

    try {
      // Send as JSON request body
      console.log('Validating path:', path.trim());
      const requestData = {
        path: path.trim(),
        create_if_missing: true
      };
      console.log('Request data:', requestData);
      
      const response = await axios.post('/api/settings/validate-path', requestData);
      console.log('Validation response:', response.data);

      const isValid = response.data.exists && response.data.is_directory && response.data.writable;

      setPathValidation(prev => ({
        ...prev,
        [pathType]: {
          valid: isValid,
          message: isValid
            ? `✓ Valid and writable (${response.data.absolute_path})`
            : response.data.exists
              ? response.data.is_directory
                ? '⚠ Path exists but not writable'
                : '✗ Path exists but is not a directory'
              : '✗ Path does not exist and could not be created'
        }
      }));

      return isValid;
    } catch (error) {
      console.error('Path validation error:', error);
      console.error('Error response:', error.response?.data);
      
      // Log the full error detail array to see what Pydantic is complaining about
      if (error.response?.data?.detail && Array.isArray(error.response.data.detail)) {
        console.error('Pydantic validation errors:', JSON.stringify(error.response.data.detail, null, 2));
      }
      
      // Extract error message properly, handling various formats
      let errorMsg = 'Error validating path';
      if (error.response?.data?.detail) {
        const detail = error.response.data.detail;
        if (typeof detail === 'string') {
          errorMsg = detail;
        } else if (Array.isArray(detail) && detail.length > 0) {
          // Pydantic validation errors come as array
          errorMsg = detail.map(err => err.msg || JSON.stringify(err)).join(', ');
        } else if (typeof detail === 'object') {
          errorMsg = detail.message || JSON.stringify(detail);
        }
      } else if (error.message) {
        errorMsg = error.message;
      }
      
      setPathValidation(prev => ({
        ...prev,
        [pathType]: { valid: false, message: `✗ ${errorMsg}` }
      }));
      return false;
    }
  };

  const handleInputChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
    
    // Don't validate paths if they're empty
    if (field === 'recordings_path' || field === 'faces_path') {
      if (value && value.trim() !== '') {
        // Debounce validation to avoid excessive API calls
        clearTimeout(window.pathValidationTimeout);
        window.pathValidationTimeout = setTimeout(() => {
          validatePath(value, field);
        }, 500);
      }
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage({ type: '', text: '' });

    try {
      // Skip path validation for now - just save
      const response = await axios.patch('/api/settings', settings);
      setMessage({ type: 'success', text: '✓ Settings saved successfully! Restart server for changes to take effect.' });
      setSaving(false);
    } catch (error) {
      console.error('Error saving settings:', error);
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to save settings'
      });
      setSaving(false);
    }
  };

  const handleCameraFeatureToggle = async (cameraId, feature, enabled) => {
    try {
      await axios.patch(`/api/cameras/${cameraId}`, {
        [feature]: enabled
      });
      
      // Reload cameras to reflect changes
      loadCameras();
      setMessage({ type: 'success', text: `✓ Camera ${feature} updated` });
    } catch (error) {
      console.error('Error updating camera:', error);
      setMessage({ type: 'error', text: 'Failed to update camera settings' });
    }
  };

  // Helper function to get camera setting value with safe defaults
  const getCameraValue = (camera, property, defaultValue) => {
    const value = camera[property];
    if (value === undefined || value === null || isNaN(value)) {
      return defaultValue;
    }
    return value;
  };

  // Handle directory selection via file input
  // Note: Due to browser security, we can't get the actual filesystem path
  // This function now serves as a helper to guide users
  const handleDirectorySelect = (pathType) => {
    // Show a helpful dialog with path examples
    const pathName = pathType === 'recordings_path' ? 'recordings' : 'face images';
    const defaultPath = pathType === 'recordings_path' ? 'recordings' : 'faces';
    
    const userPath = prompt(
      `Enter the full path where you want to store ${pathName}:\n\n` +
      `Leave empty to use default: "${defaultPath}"\n\n` +
      `Examples:\n` +
      `• macOS/Linux: /Users/yourname/${defaultPath}\n` +
      `• Windows: C:\\Users\\yourname\\${defaultPath}\n` +
      `• Relative: ./${defaultPath} (relative to app folder)`
    );
    
    if (userPath !== null) {  // User clicked OK (even if empty)
      const trimmedPath = userPath.trim();
      
      if (trimmedPath) {
        // User entered a path - set it and validate
        setSettings(prev => ({ ...prev, [pathType]: trimmedPath }));
        setTimeout(() => {
          validatePath(trimmedPath, pathType);
        }, 100);
      } else {
        // User left empty - use default without validation
        setSettings(prev => ({ ...prev, [pathType]: defaultPath }));
        // Clear any previous validation messages
        setPathValidation(prev => ({
          ...prev,
          [pathType]: { valid: true, message: `✓ Using default: ${defaultPath}` }
        }));
      }
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <div style={styles.spinner}>⏳</div>
        <p>Loading settings...</p>
      </div>
    );
  }

  return (
    <div style={embedded ? {} : styles.container}>
      <div style={styles.content}>
        {!embedded && (
          <h1 style={styles.mainTitle}>🔧 System Settings</h1>
        )}

        {message.text && (
          <div style={{
            ...styles.message,
            ...(message.type === 'success' ? styles.messageSuccess : styles.messageError)
          }}>
            {message.text}
          </div>
        )}

        {/* Storage Paths Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>💾 Storage Configuration</h2>
          <p style={styles.sectionDescription}>
            Configure where recordings and face images are stored. Paths are relative to the application directory.
          </p>

          <div style={styles.formGroup}>
            <label style={styles.label}>
              <span style={styles.labelText}>Recordings Path</span>
              <span style={styles.labelHint}>Full path to directory where video recordings are saved (e.g., /path/to/recordings)</span>
            </label>
            <div style={styles.pathInputContainer}>
              <input
                type="text"
                value={settings.recordings_path}
                onChange={(e) => handleInputChange('recordings_path', e.target.value)}
                onBlur={(e) => validatePath(e.target.value, 'recordings_path')}
                style={styles.pathInput}
                placeholder="recordings"
              />
              <button
                onClick={() => handleDirectorySelect('recordings_path')}
                style={styles.browseButton}
                type="button"
                title="Enter path with helpful examples"
              >
                � Set Path
              </button>
            </div>
            {pathValidation.recordings_path && (
              <div style={{
                ...styles.validationMessage,
                color: pathValidation.recordings_path.valid ? 'var(--color-success)' : 'var(--color-error)'
              }}>
                {pathValidation.recordings_path.message}
              </div>
            )}
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>
              <span style={styles.labelText}>Faces Path</span>
              <span style={styles.labelHint}>Full path to directory where face images are stored (e.g., /path/to/faces)</span>
            </label>
            <div style={styles.pathInputContainer}>
              <input
                type="text"
                value={settings.faces_path}
                onChange={(e) => handleInputChange('faces_path', e.target.value)}
                onBlur={(e) => validatePath(e.target.value, 'faces_path')}
                style={styles.pathInput}
                placeholder="faces"
              />
              <button
                onClick={() => handleDirectorySelect('faces_path')}
                style={styles.browseButton}
                type="button"
                title="Enter path with helpful examples"
              >
                � Set Path
              </button>
            </div>
            {pathValidation.faces_path && (
              <div style={{
                ...styles.validationMessage,
                color: pathValidation.faces_path.valid ? 'var(--color-success)' : 'var(--color-error)'
              }}>
                {pathValidation.faces_path.message}
              </div>
            )}
          </div>
        </div>

        {/* Display Settings Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>📺 Display Settings</h2>
          <p style={styles.sectionDescription}>
            Configure how camera feeds are displayed on the dashboard.
          </p>

          <div style={styles.formGroup}>
            <label style={styles.label}>
              <span style={styles.labelText}>Display Mode</span>
              <span style={styles.labelHint}>How cameras are arranged on the dashboard</span>
            </label>
            <select
              value={settings.display_mode}
              onChange={(e) => handleInputChange('display_mode', e.target.value)}
              style={styles.select}
            >
              <option value="grid">Grid - Responsive grid layout</option>
              <option value="vertical">Vertical - Stacked vertically</option>
              <option value="horizontal">Horizontal - Side by side</option>
              <option value="cycle">Cycle - Auto-rotate through cameras</option>
            </select>
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>
              <span style={styles.labelText}>Cycle Interval (seconds)</span>
              <span style={styles.labelHint}>Time between camera switches in cycle mode</span>
            </label>
            <input
              type="number"
              min="1"
              max="60"
              value={settings.cycle_interval || 5}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                if (!isNaN(val) && val >= 1 && val <= 60) {
                  handleInputChange('cycle_interval', val);
                }
              }}
              style={styles.input}
            />
          </div>
        </div>

        {/* Recording Settings Section */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>⏺️ Recording Settings</h2>
          <p style={styles.sectionDescription}>
            Configure recording behavior and limits.
          </p>

          <div style={styles.formGroup}>
            <label style={styles.label}>
              <span style={styles.labelText}>Max Recording Duration (seconds)</span>
              <span style={styles.labelHint}>Maximum length of a single recording (30-1800 seconds)</span>
            </label>
            <input
              type="number"
              min="30"
              max="1800"
              value={settings.max_recording_duration || 300}
              onChange={(e) => {
                const val = parseInt(e.target.value);
                if (!isNaN(val) && val >= 30 && val <= 1800) {
                  handleInputChange('max_recording_duration', val);
                }
              }}
              style={styles.input}
            />
            <div style={styles.hint}>
              Current: {Math.floor((settings.max_recording_duration || 300) / 60)} minutes {(settings.max_recording_duration || 300) % 60} seconds
            </div>
          </div>
        </div>

        {/* Per-Camera Feature Controls */}
        <div style={styles.section}>
          <h2 style={styles.sectionTitle}>📹 Per-Camera Controls</h2>
          <p style={styles.sectionDescription}>
            Enable or disable features for individual cameras. All features are disabled by default.
          </p>

          {cameras.length === 0 ? (
            <div style={styles.noCameras}>
              No cameras configured. Add cameras to manage their settings.
            </div>
          ) : (
            <div style={styles.cameraList}>
              {cameras.map(camera => (
                <div key={camera.camera_id} style={styles.cameraCard}>
                  <div style={styles.cameraHeader}>
                    <h3 style={styles.cameraName}>{camera.name || camera.camera_id}</h3>
                    <span style={camera.is_active ? styles.statusActive : styles.statusInactive}>
                      {camera.is_active ? '🟢 Active' : '⚫ Inactive'}
                    </span>
                  </div>
                  
                  <div style={styles.featureToggles}>
                    <div style={styles.toggleRow}>
                      <label style={styles.toggleLabel}>
                        <input
                          type="checkbox"
                          checked={camera.motion_detection_enabled || false}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'motion_detection_enabled',
                            e.target.checked
                          )}
                          style={styles.checkbox}
                        />
                        <span style={styles.toggleText}>Motion Detection</span>
                      </label>
                      <span style={styles.toggleHint}>Detect motion and trigger events</span>
                    </div>

                    <div style={styles.toggleRow}>
                      <label style={styles.toggleLabel}>
                        <input
                          type="checkbox"
                          checked={camera.recording_enabled || false}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'recording_enabled',
                            e.target.checked
                          )}
                          style={styles.checkbox}
                        />
                        <span style={styles.toggleText}>Video Recording</span>
                      </label>
                      <span style={styles.toggleHint}>Record video when motion detected</span>
                    </div>

                    <div style={styles.toggleRow}>
                      <label style={styles.toggleLabel}>
                        <input
                          type="checkbox"
                          checked={camera.face_detection_enabled || false}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'face_detection_enabled',
                            e.target.checked
                          )}
                          style={styles.checkbox}
                        />
                        <span style={styles.toggleText}>Face Detection</span>
                      </label>
                      <span style={styles.toggleHint}>Detect and recognize faces</span>
                    </div>

                    {/* Advanced Camera Settings */}
                    <div style={styles.advancedSection}>
                      <h4 style={styles.advancedTitle}>🎛️ Advanced Settings</h4>
                      
                      {/* Brightness Control */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Brightness</span>
                          <span style={styles.sliderValue}>{getCameraValue(camera, 'brightness', 50)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={getCameraValue(camera, 'brightness', 50)}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'brightness',
                            parseInt(e.target.value)
                          )}
                          style={styles.slider}
                        />
                        <span style={styles.sliderHint}>Adjust camera brightness (0-100%)</span>
                      </div>

                      {/* Contrast Control */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Contrast</span>
                          <span style={styles.sliderValue}>{getCameraValue(camera, 'contrast', 50)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={getCameraValue(camera, 'contrast', 50)}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'contrast',
                            parseInt(e.target.value)
                          )}
                          style={styles.slider}
                        />
                        <span style={styles.sliderHint}>Adjust camera contrast (0-100%)</span>
                      </div>

                      {/* Saturation Control */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Saturation</span>
                          <span style={styles.sliderValue}>{getCameraValue(camera, 'saturation', 50)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={getCameraValue(camera, 'saturation', 50)}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'saturation',
                            parseInt(e.target.value)
                          )}
                          style={styles.slider}
                        />
                        <span style={styles.sliderHint}>Adjust color saturation (0-100%)</span>
                      </div>

                      {/* Motion Sensitivity */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Motion Sensitivity</span>
                          <span style={styles.sliderValue}>{getCameraValue(camera, 'motion_sensitivity', 50)}%</span>
                        </label>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={getCameraValue(camera, 'motion_sensitivity', 50)}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'motion_sensitivity',
                            parseInt(e.target.value)
                          )}
                          style={styles.slider}
                        />
                        <span style={styles.sliderHint}>Lower = less sensitive, Higher = more sensitive</span>
                      </div>

                      {/* FPS Control */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Frame Rate (FPS)</span>
                          <span style={styles.sliderValue}>{getCameraValue(camera, 'fps', 15)}</span>
                        </label>
                        <input
                          type="range"
                          min="5"
                          max="30"
                          step="5"
                          value={getCameraValue(camera, 'fps', 15)}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'fps',
                            parseInt(e.target.value)
                          )}
                          style={styles.slider}
                        />
                        <span style={styles.sliderHint}>Frames per second (5-30 FPS)</span>
                      </div>

                      {/* Resolution Control */}
                      <div style={styles.sliderRow}>
                        <label style={styles.sliderLabel}>
                          <span style={styles.sliderText}>Resolution</span>
                          <span style={styles.sliderValue}>{camera.resolution || '640x480'}</span>
                        </label>
                        <select
                          value={camera.resolution || '640x480'}
                          onChange={(e) => handleCameraFeatureToggle(
                            camera.camera_id,
                            'resolution',
                            e.target.value
                          )}
                          style={styles.cameraSelect}
                        >
                          <option value="320x240">320x240 (Low)</option>
                          <option value="640x480">640x480 (Standard)</option>
                          <option value="1280x720">1280x720 (HD)</option>
                          <option value="1920x1080">1920x1080 (Full HD)</option>
                        </select>
                        <span style={styles.sliderHint}>Camera resolution (higher uses more bandwidth)</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Save Button */}
        <div style={styles.actions}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              ...styles.saveButton,
              ...(saving ? styles.saveButtonDisabled : {})
            }}
          >
            {saving ? '⏳ Saving...' : '💾 Save Settings'}
          </button>
        </div>

        <div style={styles.infoBox}>
          <strong>ℹ️ Note:</strong> Some settings (like storage paths) require a server restart to take full effect.
          Changing paths will affect where new files are saved.
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    padding: '20px',
    color: 'var(--text-primary)',
  },
  content: {
    maxWidth: '900px',
    margin: '0 auto',
  },
  mainTitle: {
    fontSize: '32px',
    fontWeight: '600',
    marginBottom: '30px',
    color: 'var(--text-primary)',
  },
  loading: {
    textAlign: 'center',
    padding: '60px 20px',
    color: 'var(--text-primary)',
  },
  spinner: {
    fontSize: '48px',
    marginBottom: '20px',
  },
  message: {
    padding: '15px 20px',
    borderRadius: '8px',
    marginBottom: '25px',
    fontSize: '14px',
    fontWeight: '500',
  },
  messageSuccess: {
    backgroundColor: 'rgba(40, 167, 69, 0.15)',
    color: 'var(--color-success)',
    border: '1px solid var(--color-success)',
  },
  messageError: {
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    color: 'var(--color-error)',
    border: '1px solid var(--color-error)',
  },
  section: {
    backgroundColor: 'var(--bg-panel)',
    borderRadius: '10px',
    padding: '25px',
    marginBottom: '25px',
    border: '1px solid var(--border-panel)',
  },
  sectionTitle: {
    fontSize: '20px',
    fontWeight: '600',
    marginBottom: '10px',
    color: 'var(--text-primary)',
  },
  sectionDescription: {
    fontSize: '14px',
    color: 'var(--text-secondary)',
    marginBottom: '25px',
    lineHeight: '1.6',
  },
  formGroup: {
    marginBottom: '25px',
  },
  label: {
    display: 'block',
    marginBottom: '8px',
  },
  labelText: {
    fontSize: '15px',
    fontWeight: '600',
    color: 'var(--text-primary)',
    display: 'block',
    marginBottom: '4px',
  },
  labelHint: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    display: 'block',
  },
  input: {
    width: '100%',
    padding: '12px 15px',
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border-input)',
    borderRadius: '6px',
    color: 'var(--text-primary)',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  pathInputContainer: {
    display: 'flex',
    gap: '10px',
    alignItems: 'stretch',
  },
  pathInput: {
    flex: 1,
    padding: '12px 15px',
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border-input)',
    borderRadius: '6px',
    color: 'var(--text-primary)',
    fontSize: '14px',
    boxSizing: 'border-box',
  },
  browseButton: {
    padding: '12px 20px',
    backgroundColor: 'var(--color-primary)',
    color: 'white',
    border: 'none',
    borderRadius: '6px',
    fontSize: '14px',
    fontWeight: '500',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    transition: 'background-color 0.2s',
  },
  select: {
    width: '100%',
    padding: '12px 15px',
    backgroundColor: 'var(--bg-input)',
    border: '1px solid var(--border-input)',
    borderRadius: '6px',
    color: 'var(--text-primary)',
    fontSize: '14px',
    cursor: 'pointer',
    boxSizing: 'border-box',
  },
  validationMessage: {
    fontSize: '13px',
    marginTop: '6px',
    fontWeight: '500',
  },
  hint: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    marginTop: '6px',
  },
  cameraList: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
    gap: '20px',
  },
  cameraCard: {
    backgroundColor: 'var(--bg-main)',
    border: '1px solid var(--border-panel)',
    borderRadius: '8px',
    padding: '20px',
  },
  cameraHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '1px solid var(--border-panel)',
  },
  cameraName: {
    fontSize: '16px',
    fontWeight: '600',
    margin: 0,
    color: 'var(--text-primary)',
  },
  statusActive: {
    fontSize: '13px',
    color: 'var(--color-success)',
    fontWeight: '500',
  },
  statusInactive: {
    fontSize: '13px',
    color: 'var(--text-secondary)',
    fontWeight: '500',
  },
  featureToggles: {
    display: 'flex',
    flexDirection: 'column',
    gap: '15px',
  },
  toggleRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  toggleLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    cursor: 'pointer',
    fontSize: '14px',
  },
  toggleText: {
    fontWeight: '500',
    color: 'var(--text-primary)',
  },
  toggleHint: {
    fontSize: '12px',
    color: 'var(--text-secondary)',
    marginLeft: '30px',
  },
  checkbox: {
    width: '18px',
    height: '18px',
    cursor: 'pointer',
  },
  advancedSection: {
    marginTop: '20px',
    paddingTop: '20px',
    borderTop: '1px solid var(--border-panel)',
  },
  advancedTitle: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-primary)',
    marginBottom: '15px',
  },
  sliderRow: {
    marginBottom: '20px',
  },
  sliderLabel: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '8px',
  },
  sliderText: {
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--text-primary)',
  },
  sliderValue: {
    fontSize: '14px',
    fontWeight: '600',
    color: 'var(--text-link)',
    minWidth: '60px',
    textAlign: 'right',
  },
  slider: {
    width: '100%',
    height: '6px',
    borderRadius: '3px',
    outline: 'none',
    cursor: 'pointer',
    marginBottom: '5px',
  },
  sliderHint: {
    fontSize: '11px',
    color: 'var(--text-secondary)',
    display: 'block',
  },
  cameraSelect: {
    width: '100%',
    padding: '8px 12px',
    backgroundColor: 'var(--bg-main)',
    color: 'var(--text-primary)',
    border: '1px solid var(--border-panel)',
    borderRadius: '6px',
    fontSize: '14px',
    cursor: 'pointer',
    marginBottom: '5px',
  },
  noCameras: {
    textAlign: 'center',
    padding: '40px 20px',
    color: 'var(--text-secondary)',
    fontSize: '14px',
    backgroundColor: 'var(--bg-main)',
    borderRadius: '8px',
    border: '1px dashed var(--border-panel)',
  },
  actions: {
    display: 'flex',
    justifyContent: 'center',
    marginTop: '30px',
    marginBottom: '25px',
  },
  saveButton: {
    backgroundColor: 'var(--text-link)',
    color: 'white',
    border: 'none',
    padding: '15px 40px',
    borderRadius: '8px',
    fontSize: '16px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: '0 2px 8px rgba(0, 123, 255, 0.3)',
  },
  saveButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  infoBox: {
    backgroundColor: 'rgba(0, 123, 255, 0.15)',
    border: '1px solid var(--text-link)',
    borderRadius: '8px',
    padding: '15px 20px',
    fontSize: '13px',
    color: 'var(--text-primary)',
    lineHeight: '1.6',
  },
};

export default SystemSettingsPage;
