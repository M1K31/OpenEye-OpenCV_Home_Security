import React, { useState, useEffect, useMemo } from 'react';
import { useEscapeToClose } from '../hooks/useEscapeToClose';
import { useDialogA11y } from '../hooks/useDialogA11y';
import apiClient from '../api/apiClient';
import MotionZoneEditor from './MotionZoneEditor';
import Switch from './Switch';
import TwoWayAudio from './TwoWayAudio';
import PTZControl from './PTZControl';
import './CameraSettingsModal.css';
import { describeApiError } from '../utils/apiError';

const CameraSettingsModal = ({ camera, onClose, onSave, initialTab = 'motion' }) => {
  const [activeTab, setActiveTab] = useState(initialTab || 'motion');
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

  // Multi-Vendor Camera Edge AI & Hardware Settings
  const [edgeInfo, setEdgeInfo] = useState({
    vendor: 'generic',
    camera_ip: '',
    onvif_port: 2020,
    is_network_camera: true,
    device_info: {},
    capabilities: {},
    recent_events: [],
    loading: false,
  });
  const [edgeSettings, setEdgeSettings] = useState({
    edge_ai_enabled: true,
    person_detection: true,
    vehicle_detection: true,
    pet_detection: true,
    package_detection: false,
    audio_alarm_detection: false,
    motion_detection: true,
    auto_tracking: false,
    privacy_mode: false,
    night_vision_mode: 'auto',
    trigger_recording_on_edge_ai: true,
    cooldown_seconds: 10,
  });
  const [sirenBusy, setSirenBusy] = useState(false);

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
      loadEdgeCapabilities( false );
    }
  }, [camera]);

  const loadEdgeCapabilities = async (refresh = false) => {
    if (!camera?.camera_id) return;
    setEdgeInfo((prev) => ({ ...prev, loading: true }));
    try {
      const res = await apiClient.get(
        `/cameras/${camera.camera_id}/edge/capabilities?refresh=${refresh ? 'true' : 'false'}`
      );
      const data = res.data || {};
      setEdgeInfo({
        vendor: data.vendor || 'generic',
        camera_ip: data.camera_ip || '',
        onvif_port: data.onvif_port || 2020,
        is_network_camera: Boolean(data.is_network_camera),
        device_info: data.device_info || {},
        capabilities: data.capabilities || {},
        recent_events: data.recent_events || [],
        loading: false,
      });
      if (data.settings) {
        setEdgeSettings((prev) => ({ ...prev, ...data.settings }));
      }
    } catch (err) {
      setEdgeInfo((prev) => ({ ...prev, loading: false }));
    }
  };

  const handleSaveEdgeSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await apiClient.put(`/cameras/${camera.camera_id}/edge/settings`, edgeSettings);
      if (res.data?.settings) {
        setEdgeSettings((prev) => ({ ...prev, ...res.data.settings }));
      }
      setSuccess('Camera Edge AI & hardware settings saved!');
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError(`Failed to save Edge AI settings: ${describeApiError(err)}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTriggerSiren = async (active) => {
    setSirenBusy(true);
    setError(null);
    try {
      await apiClient.post(`/cameras/${camera.camera_id}/edge/siren`, {
        active,
        duration_seconds: 5,
      });
      setSuccess(active ? 'Camera siren triggered (5s auto-stop)' : 'Camera siren stopped');
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError(`Siren command failed: ${describeApiError(err)}`);
    } finally {
      setSirenBusy(false);
    }
  };

  const handleTestEdgeEvent = async (objectClass) => {
    setSaving(true);
    setError(null);
    try {
      await apiClient.post(`/cameras/${camera.camera_id}/edge/test-event`, {
        object_class: objectClass,
        confidence: 0.96,
      });
      setSuccess(`Recorded camera Edge AI ${objectClass} detection event!`);
      await loadEdgeCapabilities(false);
      setTimeout(() => setSuccess(null), 4000);
    } catch (err) {
      setError(`Failed to test Edge AI event: ${describeApiError(err)}`);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveMotionSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      console.log('Saving motion settings for camera:', camera.camera_id, motionSettings);
      const response = await apiClient.put(`/cameras/${camera.camera_id}`, motionSettings);
      console.log('Motion settings saved successfully:', response.data);
      setSuccess('Motion detection settings saved successfully!');

      // Auto-clear success message after 4 seconds
      setTimeout(() => setSuccess(null), 4000);

      if (onSave) {
        onSave(camera.camera_id);
      }
    } catch (err) {
      console.error('Failed to save motion settings:', err);
      const errorMsg = describeApiError(err);
      setError(`Failed to save motion settings: ${errorMsg}`);
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
          Object Size Filter (1-10)
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
          <strong>Step 1 - Filter by object size:</strong> Controls the minimum size of moving objects to detect.
          1 = only large objects (people, vehicles), 10 = detect tiny movements (insects, leaves, noise).
          <em>Recommended: 3-5 for indoor, 1-3 for outdoor.</em>
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Pixel Sensitivity (1-100)
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
          <strong>Step 2 - Pixel change detection:</strong> How much a pixel must change to be considered "moving".
          Lower = more sensitive to subtle changes, Higher = ignores shadows and minor lighting shifts.
          <em>Recommended: 25-50 for most cameras, higher if getting false positives from lighting.</em>
        </p>
      </div>

      <div className="settings-section">
        <label className="settings-label">
          Trigger Threshold ({motionSettings.motion_percentage_threshold.toFixed(1)}% of frame)
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
          <strong>Step 3 - Final filter:</strong> What percentage of the frame must contain detected motion to trigger an event.
          0.5% = small hand wave triggers, 5% = requires larger movement like walking across frame.
          <em>Recommended: 0.5-2% for most use cases.</em>
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
          Recording Frame Rate (FPS)
          <span className="settings-value">{imageSettings.fps_target} FPS</span>
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
        <div className="settings-hint-box">
          <p className="settings-hint">
            <strong>Recording FPS:</strong> This controls how many frames per second are saved in motion recordings.
          </p>
          <p className="settings-hint" style={{ marginTop: '8px' }}>
            <strong>Important:</strong> For accurate playback speed, set this to match your camera's native FPS from the manufacturer specifications.
            Common values: 15 FPS (budget cameras), 25 FPS (PAL), 30 FPS (NTSC/most IP cameras).
          </p>
          <p className="settings-hint" style={{ marginTop: '8px', color: 'var(--color-info, #2196F3)' }}>
            <strong>Note:</strong> This setting only affects <em>recordings</em>. Live streaming is not affected and always displays at full camera speed.
          </p>
        </div>
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

  const renderAudioTab = () => (
    <div className="settings-tab-content audio-tab">
      <TwoWayAudio cameraId={camera.camera_id} />
    </div>
  );

  const renderEdgeTab = () => {
    const vendorNames = {
      tapo: 'TP-Link Tapo (ONVIF + Smart AI)',
      hikvision: 'Hikvision (ONVIF + ISAPI)',
      dahua: 'Dahua / Amcrest (ONVIF + CGI)',
      reolink: 'Reolink (ONVIF + AI State API)',
      axis: 'Axis (ONVIF + VAPIX)',
      generic: 'Standard ONVIF Profile S/T',
    };
    const vendorDisplay = vendorNames[edgeInfo.vendor] || vendorNames.generic;
    const devModel = edgeInfo.device_info?.Model ? ` • ${edgeInfo.device_info.Model}` : '';

    return (
      <div className="settings-tab-content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div>
            <h3 style={{ margin: 0 }}>Built-In Camera AI & Hardware Controls</h3>
            <p className="settings-hint" style={{ marginTop: '4px' }}>
              {vendorDisplay}{devModel}
              {edgeInfo.camera_ip ? ` (${edgeInfo.camera_ip}:${edgeInfo.onvif_port})` : ''}
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => loadEdgeCapabilities(true)}
            disabled={edgeInfo.loading}
          >
            {edgeInfo.loading ? 'Probing…' : '🔄 Re-Probe Hardware'}
          </button>
        </div>

        <div className="settings-section">
          <Switch
            checked={edgeSettings.edge_ai_enabled}
            onChange={(checked) => setEdgeSettings({ ...edgeSettings, edge_ai_enabled: checked })}
            label="Ingest On-Camera Edge AI Events (ONVIF / Native NPU)"
            color="primary"
          />
          <p className="settings-hint">
            Listens to the camera's built-in AI processor for Person, Vehicle, Pet, and Motion events—saving Mac CPU usage while logging detections directly into the Detections page and triggering recordings.
          </p>
        </div>

        <div className="settings-section">
          <h4 style={{ marginBottom: '10px' }}>On-Camera AI Detection Filters</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            <Switch
              checked={edgeSettings.person_detection}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, person_detection: checked })}
              label="👤 Person / Human AI"
            />
            <Switch
              checked={edgeSettings.vehicle_detection}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, vehicle_detection: checked })}
              label="🚗 Vehicle AI"
            />
            <Switch
              checked={edgeSettings.pet_detection}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, pet_detection: checked })}
              label="🐾 Pet / Animal AI"
            />
            <Switch
              checked={edgeSettings.package_detection}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, package_detection: checked })}
              label="📦 Package AI"
            />
            <Switch
              checked={edgeSettings.audio_alarm_detection}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, audio_alarm_detection: checked })}
              label="🔊 Baby Cry / Bark / Glass Break"
            />
            <Switch
              checked={edgeSettings.trigger_recording_on_edge_ai}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, trigger_recording_on_edge_ai: checked })}
              label="🎥 Auto-Record on Camera AI Event"
            />
          </div>
        </div>

        <div className="settings-section">
          <h4 style={{ marginBottom: '10px' }}>Camera Hardware Features (Multi-Vendor & Tapo)</h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '12px' }}>
            <Switch
              checked={edgeSettings.auto_tracking}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, auto_tracking: checked })}
              label="🏃 PTZ Smart Auto-Tracking (Follow Person)"
            />
            <Switch
              checked={edgeSettings.privacy_mode}
              onChange={(checked) => setEdgeSettings({ ...edgeSettings, privacy_mode: checked })}
              label="🙈 Hardware Privacy Mask (Hide Lens)"
            />
          </div>

          <div style={{ marginTop: '16px' }}>
            <label className="settings-label">Night Vision / IR / Spotlight Mode</label>
            <select
              value={edgeSettings.night_vision_mode}
              onChange={(e) => setEdgeSettings({ ...edgeSettings, night_vision_mode: e.target.value })}
              className="form-select"
            >
              <option value="auto">Smart Auto (Switch IR / Color on Motion)</option>
              <option value="ir">Infrared Night Vision (B&W IR LED)</option>
              <option value="color">Full-Color Starlight / White Spotlight</option>
              <option value="off">Day Mode Only (IR Filter Engaged)</option>
            </select>
          </div>
        </div>

        <div className="settings-section">
          <h4 style={{ marginBottom: '10px' }}>Built-In Siren & Edge AI Verification</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={sirenBusy}
              onClick={() => handleTriggerSiren(true)}
            >
              🚨 Trigger Siren (5s)
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={sirenBusy}
              onClick={() => handleTriggerSiren(false)}
            >
              🔕 Stop Siren
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={saving}
              onClick={() => handleTestEdgeEvent('person')}
            >
              🧪 Test Person AI Event
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={saving}
              onClick={() => handleTestEdgeEvent('vehicle')}
            >
              🧪 Test Vehicle AI Event
            </button>
          </div>
        </div>

        <div className="settings-actions">
          <button
            onClick={handleSaveEdgeSettings}
            disabled={saving}
            className="btn btn-primary"
          >
            {saving ? 'Saving...' : 'Save Edge AI & Hardware Settings'}
          </button>
        </div>
      </div>
    );
  };

  if (!camera) return null;

  // Escape closes this dialog. It renders its own overlay rather than using

  // the shared Modal component, so without this a keyboard user could open

  // it and have no way to dismiss it.

  useEscapeToClose(onClose);

  const { dialogRef, dialogProps } = useDialogA11y(true, undefined);


  return (
    <div className="modal-overlay" onClick={onClose}>
      <div ref={dialogRef} {...dialogProps} className="modal camera-settings-modal" onClick={(e) => e.stopPropagation()}>
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
          <button
            className={`settings-tab ${activeTab === 'audio' ? 'active' : ''}`}
            onClick={() => setActiveTab('audio')}
          >
            Two-Way Audio
          </button>
          <button
            className={`settings-tab ${activeTab === 'ptz' ? 'active' : ''}`}
            onClick={() => setActiveTab('ptz')}
          >
            🎮 PTZ & Viewer
          </button>
          <button
            className={`settings-tab ${activeTab === 'edge' ? 'active' : ''}`}
            onClick={() => setActiveTab('edge')}
          >
            🧠 Edge AI & Hardware
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
                case 'audio':
                  return renderAudioTab();
                case 'ptz':
                  return (
                    <div className="settings-tab-content">
                      <PTZControl
                        cameraId={camera.camera_id}
                        cameraName={camera.name || camera.camera_id}
                      />
                    </div>
                  );
                case 'edge':
                  return renderEdgeTab();
                default:
                  return null;
              }
            }, [activeTab, motionSettings, recordingSettings, faceSettings, imageSettings, overlaySettings, edgeSettings, edgeInfo, sirenBusy, saving, camera.camera_id, camera.name])
          )}
        </div>
      </div>
    </div>
  );
};

export default CameraSettingsModal;
