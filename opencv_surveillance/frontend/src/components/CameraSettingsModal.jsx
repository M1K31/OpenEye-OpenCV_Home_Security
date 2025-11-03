import React, { useState, useEffect, useMemo } from 'react';
import apiClient from '../api/apiClient';
import MotionZoneEditor from './MotionZoneEditor';
import Switch from './Switch';
import './CameraSettingsModal.css';

const CameraSettingsModal = ({ camera, onClose, onSave }) => {
  const [activeTab, setActiveTab] = useState('motion');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Motion Detection Settings
  const [motionSettings, setMotionSettings] = useState({
    motion_detection_enabled: camera?.motion_detection_enabled ?? true,
    motion_threshold: camera?.motion_threshold ?? 25,
    motion_sensitivity: camera?.motion_sensitivity ?? 5,
    motion_percentage_threshold: camera?.motion_percentage_threshold ?? 1.0,
    noise_reduction: camera?.noise_reduction ?? 'medium',
    detect_shadows: camera?.detect_shadows ?? true,
    lighting_compensation_enabled: camera?.lighting_compensation_enabled ?? true,
  });

  // Alert Settings
  const [alertSettings, setAlertSettings] = useState({
    alert_enabled: false,
    alert_cooldown: 300,
    alert_methods: [],
  });

  // Recording Settings
  const [recordingSettings, setRecordingSettings] = useState({
    recording_enabled: camera?.recording_enabled ?? true,
    pre_motion_seconds: camera?.pre_motion_seconds ?? 5,
    post_motion_seconds: camera?.post_motion_seconds ?? 10,
    max_recording_duration: camera?.max_recording_duration ?? 300,
  });

  // Face Detection Settings
  const [faceSettings, setFaceSettings] = useState({
    face_detection_enabled: camera?.face_detection_enabled ?? false,
  });

  // Image Quality Settings
  const [imageSettings, setImageSettings] = useState({
    brightness: camera?.brightness ?? 0,
    contrast: camera?.contrast ?? 1.0,
    saturation: camera?.saturation ?? 1.0,
    fps_target: camera?.fps_target ?? 15,
  });

  // Overlay Settings (timestamp and custom text)
  const [overlaySettings, setOverlaySettings] = useState({
    overlay_enabled: camera?.overlay_enabled ?? true,
    overlay_timestamp_enabled: camera?.overlay_timestamp_enabled ?? true,
    overlay_custom_text: camera?.overlay_custom_text ?? '',
    overlay_position: camera?.overlay_position ?? 'top-left',
    overlay_font_size: camera?.overlay_font_size ?? 1,
    overlay_font_color: camera?.overlay_font_color ?? 'white',
  });

  // Initialize settings from camera prop (no API call needed - data already available!)
  useEffect(() => {
    if (camera) {
      // Update motion settings from camera prop
      setMotionSettings({
        motion_detection_enabled: camera.motion_detection_enabled ?? true,
        motion_threshold: camera.motion_threshold ?? 25,
        motion_sensitivity: camera.motion_sensitivity ?? 5,
        motion_percentage_threshold: camera.motion_percentage_threshold ?? 1.0,
        noise_reduction: camera.noise_reduction ?? 'medium',
        detect_shadows: camera.detect_shadows ?? true,
        lighting_compensation_enabled: camera.lighting_compensation_enabled ?? true,
      });

      // Update recording settings from camera prop
      setRecordingSettings({
        recording_enabled: camera.recording_enabled ?? true,
        pre_motion_seconds: camera.pre_motion_seconds ?? 5,
        post_motion_seconds: camera.post_motion_seconds ?? 10,
        max_recording_duration: camera.max_recording_duration ?? 300,
      });

      // Update face detection settings from camera prop
      setFaceSettings({
        face_detection_enabled: camera.face_detection_enabled ?? false,
      });

      // Update image quality settings from camera prop
      setImageSettings({
        brightness: camera.brightness ?? 0,
        contrast: camera.contrast ?? 1.0,
        saturation: camera.saturation ?? 1.0,
        fps_target: camera.fps_target ?? 15,
      });

      // Update overlay settings from camera prop
      setOverlaySettings({
        overlay_enabled: camera.overlay_enabled ?? true,
        overlay_timestamp_enabled: camera.overlay_timestamp_enabled ?? true,
        overlay_custom_text: camera.overlay_custom_text ?? '',
        overlay_position: camera.overlay_position ?? 'top-left',
        overlay_font_size: camera.overlay_font_size ?? 1,
        overlay_font_color: camera.overlay_font_color ?? 'white',
      });

      setError(null);
      setLoading(false);
    }
  }, [camera]);

  const handleSaveMotionSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put(`/cameras/${camera.camera_id}`, motionSettings);
      setSuccess('Motion detection settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      setError(`Failed to save motion settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRecordingSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put(`/cameras/${camera.camera_id}`, recordingSettings);
      setSuccess('Recording settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      setError(`Failed to save recording settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveFaceSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put(`/cameras/${camera.camera_id}`, faceSettings);
      setSuccess('Face detection settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      setError(`Failed to save face detection settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveImageSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put(`/cameras/${camera.camera_id}`, imageSettings);
      setSuccess('Image quality settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      setError(`Failed to save image quality settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveOverlaySettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      await apiClient.put(`/cameras/${camera.camera_id}`, overlaySettings);
      setSuccess('Overlay settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      setError(`Failed to save overlay settings: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const renderMotionTab = () => (
    <div className="settings-tab-content">
      <h3>Motion Detection Configuration</h3>

      <div className="settings-section">
        <Switch
          checked={motionSettings.motion_detection_enabled}
          onChange={(checked) => setMotionSettings({
            ...motionSettings,
            motion_detection_enabled: checked
          })}
          label="Enable Motion Detection"
          color="primary"
        />
        <p className="settings-hint">
          <strong>Master switch:</strong> Turns motion detection on/off for this camera.
          When disabled, the camera will not analyze frames for motion, saving CPU resources.
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Motion Sensitivity (1-10)
          <span className="settings-value">{motionSettings.motion_sensitivity}</span>
        </label>
        <input
          type="range"
          min="1"
          max="10"
          value={motionSettings.motion_sensitivity}
          onChange={(e) => setMotionSettings({
            ...motionSettings,
            motion_sensitivity: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Higher = more sensitive (detects smaller movements)
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Motion Threshold (1-100)
          <span className="settings-value">{motionSettings.motion_threshold}</span>
        </label>
        <input
          type="range"
          min="1"
          max="100"
          value={motionSettings.motion_threshold}
          onChange={(e) => setMotionSettings({
            ...motionSettings,
            motion_threshold: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Lower = more adaptive to lighting changes
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Motion Percentage Threshold ({motionSettings.motion_percentage_threshold.toFixed(1)}%)
        </label>
        <input
          type="range"
          min="0.1"
          max="10.0"
          step="0.1"
          value={motionSettings.motion_percentage_threshold}
          onChange={(e) => setMotionSettings({
            ...motionSettings,
            motion_percentage_threshold: parseFloat(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Minimum percentage of frame that must contain motion
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">Noise Reduction</label>
        <select
          value={motionSettings.noise_reduction}
          onChange={(e) => setMotionSettings({
            ...motionSettings,
            noise_reduction: e.target.value
          })}
          className="form-select"
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </div>

      <div className="settings-section">
        <Switch
          checked={motionSettings.detect_shadows}
          onChange={(checked) => setMotionSettings({
            ...motionSettings,
            detect_shadows: checked
          })}
          label="Detect and Filter Shadows"
          color="primary"
        />
      </div>

      <div className="settings-section">
        <Switch
          checked={motionSettings.lighting_compensation_enabled}
          onChange={(checked) => setMotionSettings({
            ...motionSettings,
            lighting_compensation_enabled: checked
          })}
          label="Enable Lighting Change Compensation"
          color="primary"
        />
      </div>

      <div className="settings-actions">
        <button
          onClick={handleSaveMotionSettings}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? 'Saving...' : 'Save Motion Settings'}
        </button>
      </div>
    </div>
  );

  const renderRecordingTab = () => (
    <div className="settings-tab-content">
      <h3>Recording Configuration</h3>

      <div className="settings-section">
        <Switch
          checked={recordingSettings.recording_enabled}
          onChange={(checked) => setRecordingSettings({
            ...recordingSettings,
            recording_enabled: checked
          })}
          label="Enable Recording on Motion"
          color="primary"
        />
        <p className="settings-hint">
          <strong>Auto-recording:</strong> When motion is detected, automatically save video recordings.
          This requires motion detection to be enabled (see Motion Detection tab).
          When disabled, motion events are still logged but no video is saved.
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Pre-Motion Buffer (seconds)
          <span className="settings-value">{recordingSettings.pre_motion_seconds}s</span>
        </label>
        <input
          type="range"
          min="0"
          max="30"
          value={recordingSettings.pre_motion_seconds}
          onChange={(e) => setRecordingSettings({
            ...recordingSettings,
            pre_motion_seconds: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Record this many seconds before motion detected
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Post-Motion Duration (seconds)
          <span className="settings-value">{recordingSettings.post_motion_seconds}s</span>
        </label>
        <input
          type="range"
          min="0"
          max="60"
          value={recordingSettings.post_motion_seconds}
          onChange={(e) => setRecordingSettings({
            ...recordingSettings,
            post_motion_seconds: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Continue recording this long after motion stops
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Max Recording Duration (seconds)
          <span className="settings-value">{recordingSettings.max_recording_duration}s</span>
        </label>
        <input
          type="range"
          min="30"
          max="600"
          step="30"
          value={recordingSettings.max_recording_duration}
          onChange={(e) => setRecordingSettings({
            ...recordingSettings,
            max_recording_duration: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Maximum length of a single recording
        </p>
      </div>

      <div className="settings-actions">
        <button
          onClick={handleSaveRecordingSettings}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? 'Saving...' : 'Save Recording Settings'}
        </button>
      </div>
    </div>
  );

  const renderFaceTab = () => (
    <div className="settings-tab-content">
      <h3>Face Detection Configuration</h3>

      <div className="settings-section">
        <Switch
          checked={faceSettings.face_detection_enabled}
          onChange={(checked) => setFaceSettings({
            ...faceSettings,
            face_detection_enabled: checked
          })}
          label="Enable Face Detection"
          color="primary"
        />
        <p className="settings-hint">
          Detect and recognize faces in the camera feed
        </p>
      </div>

      <div className="settings-actions">
        <button
          onClick={handleSaveFaceSettings}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? 'Saving...' : 'Save Face Detection Settings'}
        </button>
      </div>
    </div>
  );

  const renderImageTab = () => (
    <div className="settings-tab-content">
      <h3>Image Quality Configuration</h3>

      <div className="settings-section">
        <label className="settings-label">
          Brightness
          <span className="settings-value">{imageSettings.brightness}</span>
        </label>
        <input
          type="range"
          min="-100"
          max="100"
          value={imageSettings.brightness}
          onChange={(e) => setImageSettings({
            ...imageSettings,
            brightness: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Adjust camera brightness (-100 to 100, 0=normal)
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Contrast
          <span className="settings-value">{imageSettings.contrast.toFixed(1)}</span>
        </label>
        <input
          type="range"
          min="0.5"
          max="3.0"
          step="0.1"
          value={imageSettings.contrast}
          onChange={(e) => setImageSettings({
            ...imageSettings,
            contrast: parseFloat(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Adjust camera contrast (0.5 to 3.0, 1.0=normal)
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Saturation
          <span className="settings-value">{imageSettings.saturation.toFixed(1)}</span>
        </label>
        <input
          type="range"
          min="0.0"
          max="2.0"
          step="0.1"
          value={imageSettings.saturation}
          onChange={(e) => setImageSettings({
            ...imageSettings,
            saturation: parseFloat(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Adjust color saturation (0.0 to 2.0, 1.0=normal)
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Frame Rate (FPS)
          <span className="settings-value">{imageSettings.fps_target}</span>
        </label>
        <input
          type="range"
          min="1"
          max="30"
          value={imageSettings.fps_target}
          onChange={(e) => setImageSettings({
            ...imageSettings,
            fps_target: parseInt(e.target.value)
          })}
          className="settings-slider"
        />
        <p className="settings-hint">
          Frames per second (1-30 FPS)
        </p>
      </div>

      <div className="settings-actions">
        <button
          onClick={handleSaveImageSettings}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? 'Saving...' : 'Save Image Quality Settings'}
        </button>
      </div>
    </div>
  );

  const renderOverlayTab = () => (
    <div className="settings-tab-content">
      <h3>Overlay Configuration</h3>
      <p className="settings-hint">Configure timestamp and custom text overlays on live camera feeds</p>

      <div className="settings-section">
        <div className="settings-row">
          <label className="settings-label">Enable Overlay</label>
          <Switch
            checked={overlaySettings.overlay_enabled}
            onChange={(checked) => setOverlaySettings({
              ...overlaySettings,
              overlay_enabled: checked
            })}
          />
        </div>
        <p className="settings-hint">
          Master switch for all overlay features
        </p>
      </div>

      {overlaySettings.overlay_enabled && (
        <>
          <div className="settings-section">
            <div className="settings-row">
              <label className="settings-label">Show Timestamp</label>
              <Switch
                checked={overlaySettings.overlay_timestamp_enabled}
                onChange={(checked) => setOverlaySettings({
                  ...overlaySettings,
                  overlay_timestamp_enabled: checked
                })}
              />
            </div>
            <p className="settings-hint">
              Display date and time on video feed (format: 2025-01-31 14:30:45)
            </p>
          </div>

          <div className="settings-section">
            <label className="settings-label">Custom Text Message</label>
            <input
              type="text"
              value={overlaySettings.overlay_custom_text}
              onChange={(e) => setOverlaySettings({
                ...overlaySettings,
                overlay_custom_text: e.target.value
              })}
              placeholder="Enter custom message (optional)"
              maxLength={200}
              className="form-input"
            />
            <p className="settings-hint">
              Optional custom message to display on video feed (max 200 characters)
            </p>
          </div>

          <div className="settings-section">
            <label className="settings-label">Position</label>
            <div className="overlay-position-grid">
              {['top-left', 'center-top', 'top-right', 'bottom-left', 'center-bottom', 'bottom-right'].map((pos) => (
                <button
                  key={pos}
                  className={`position-btn ${overlaySettings.overlay_position === pos ? 'active' : ''}`}
                  onClick={() => setOverlaySettings({
                    ...overlaySettings,
                    overlay_position: pos
                  })}
                  title={pos.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                >
                  {pos === 'top-left' && '⬉'}
                  {pos === 'center-top' && '⬆'}
                  {pos === 'top-right' && '⬈'}
                  {pos === 'bottom-left' && '⬋'}
                  {pos === 'center-bottom' && '⬇'}
                  {pos === 'bottom-right' && '⬊'}
                </button>
              ))}
            </div>
            <p className="settings-hint">
              Choose where the overlay appears on the video feed
            </p>
          </div>

          <div className="settings-section">
            <label className="settings-label">
              Font Size
              <span className="settings-value">{overlaySettings.overlay_font_size === 1 ? 'Small' : overlaySettings.overlay_font_size === 2 ? 'Medium' : 'Large'}</span>
            </label>
            <input
              type="range"
              min="1"
              max="3"
              value={overlaySettings.overlay_font_size}
              onChange={(e) => setOverlaySettings({
                ...overlaySettings,
                overlay_font_size: parseInt(e.target.value)
              })}
              className="settings-slider"
            />
            <p className="settings-hint">
              Text size (1=Small, 2=Medium, 3=Large)
            </p>
          </div>

          <div className="settings-section">
            <label className="settings-label">Font Color</label>
            <div className="color-selector">
              {['white', 'yellow', 'cyan', 'green', 'red'].map((color) => (
                <button
                  key={color}
                  className={`color-btn ${overlaySettings.overlay_font_color === color ? 'active' : ''}`}
                  style={{ backgroundColor: color, color: color === 'white' ? '#000' : '#fff' }}
                  onClick={() => setOverlaySettings({
                    ...overlaySettings,
                    overlay_font_color: color
                  })}
                  title={color.charAt(0).toUpperCase() + color.slice(1)}
                >
                  {overlaySettings.overlay_font_color === color && '✓'}
                </button>
              ))}
            </div>
            <p className="settings-hint">
              Choose text color for best visibility
            </p>
          </div>
        </>
      )}

      <div className="settings-actions">
        <button
          onClick={handleSaveOverlaySettings}
          disabled={saving}
          className="btn btn-primary"
        >
          {saving ? 'Saving...' : 'Save Overlay Settings'}
        </button>
      </div>
    </div>
  );

  const renderZonesTab = () => (
    <div className="settings-tab-content zones-tab">
      <MotionZoneEditor
        cameraId={camera.camera_id}
        onClose={null}
      />
    </div>
  );

  if (!camera) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal camera-settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Camera Settings: {camera.camera_id}</h2>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        {error && (
          <div className="alert alert-error">
            <span className="alert-icon">⚠️</span>
            <div className="alert-content">{error}</div>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            <span className="alert-icon">✓</span>
            <div className="alert-content">{success}</div>
          </div>
        )}

        <div className="camera-settings-tabs">
          <button
            className={`settings-tab ${activeTab === 'motion' ? 'active' : ''}`}
            onClick={() => setActiveTab('motion')}
          >
            Motion Detection
          </button>
          <button
            className={`settings-tab ${activeTab === 'recording' ? 'active' : ''}`}
            onClick={() => setActiveTab('recording')}
          >
            Recording
          </button>
          <button
            className={`settings-tab ${activeTab === 'face' ? 'active' : ''}`}
            onClick={() => setActiveTab('face')}
          >
            Face Detection
          </button>
          <button
            className={`settings-tab ${activeTab === 'image' ? 'active' : ''}`}
            onClick={() => setActiveTab('image')}
          >
            Image Quality
          </button>
          <button
            className={`settings-tab ${activeTab === 'overlay' ? 'active' : ''}`}
            onClick={() => setActiveTab('overlay')}
          >
            Overlay
          </button>
          <button
            className={`settings-tab ${activeTab === 'zones' ? 'active' : ''}`}
            onClick={() => setActiveTab('zones')}
          >
            Detection Zones
          </button>
        </div>

        <div className="camera-settings-body">
          {loading ? (
            <div className="camera-settings-loading">Loading settings...</div>
          ) : (
            useMemo(() => {
              switch (activeTab) {
                case 'motion':
                  return renderMotionTab();
                case 'recording':
                  return renderRecordingTab();
                case 'face':
                  return renderFaceTab();
                case 'image':
                  return renderImageTab();
                case 'overlay':
                  return renderOverlayTab();
                case 'zones':
                  return renderZonesTab();
                default:
                  return null;
              }
            }, [activeTab, motionSettings, recordingSettings, faceSettings, imageSettings, overlaySettings, camera.camera_id])
          )}
        </div>
      </div>
    </div>
  );
};

export default CameraSettingsModal;
