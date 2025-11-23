// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/apiClient';
import HelpButton from '../components/HelpButton';
import { HELP_CONTENT } from '../utils/helpContent';
import { Button, TextField, Switch } from '../components/universal';
import './AlertSettingsPage.css';

const AlertSettingsPage = ({ embedded = false }) => {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState(null);
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
    loadStatistics();
    loadLogs();
  }, []);

  const loadConfiguration = async () => {
    try {
      const response = await apiClient.get('/alerts/config?user_id=1');
      if (response.data.length > 0) {
        setConfig(response.data[0]);
      } else {
        // Create default configuration
        setConfig({
          user_id: 1,
          motion_alerts_enabled: true,
          face_recognition_alerts_enabled: true,
          unknown_face_alerts_enabled: true,
          recording_alerts_enabled: false,
          // v3.10.0: Object detection alerts
          object_detection_alerts_enabled: true,
          vehicle_alerts_enabled: true,
          animal_alerts_enabled: true,
          package_alerts_enabled: true,
          identified_object_alerts_enabled: true,
          email_enabled: true,
          sms_enabled: false,
          push_enabled: false,
          webhook_enabled: false,
          email_address: null,
          phone_number: null,
          push_token: null,
          webhook_url: null,
          min_seconds_between_alerts: 300,
          quiet_hours_enabled: false,
          quiet_hours_start: '22:00',
          quiet_hours_end: '07:00'
        });
      }
      setLoading(false);
    } catch (error) {
      // Set default config on error to prevent null access
      setConfig({
        user_id: 1,
        motion_alerts_enabled: true,
        face_recognition_alerts_enabled: true,
        unknown_face_alerts_enabled: true,
        recording_alerts_enabled: false,
        // v3.10.0: Object detection alerts
        object_detection_alerts_enabled: true,
        vehicle_alerts_enabled: true,
        animal_alerts_enabled: true,
        package_alerts_enabled: true,
        identified_object_alerts_enabled: true,
        email_enabled: true,
        sms_enabled: false,
        push_enabled: false,
        webhook_enabled: false,
        email_address: null,
        phone_number: null,
        push_token: null,
        webhook_url: null,
        min_seconds_between_alerts: 300,
        quiet_hours_enabled: false,
        quiet_hours_start: '22:00',
        quiet_hours_end: '07:00'
      });
      showMessage('Error loading configuration: ' + error.message, 'error');
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await apiClient.get('/alerts/statistics?days=7');
      setStats(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await apiClient.get('/alerts/logs?page=1&page_size=20');
      // Handle new paginated response format
      const logsData = response.data?.data ||
        response.data?.logs ||  // Legacy format
        (Array.isArray(response.data) ? response.data : []);
      setLogs(logsData);
    } catch (error) {
      console.error('Error loading logs:', error);
    }
  };

  const saveConfiguration = async () => {
    console.log('[AlertSettings] Starting saveConfiguration...');
    console.log('[AlertSettings] Current config:', config);
    setSaving(true);
    try {
      // Clean the config data - convert empty strings to null
      const cleanConfig = {
        ...config,
        email_address: config.email_address?.trim() || null,
        phone_number: config.phone_number?.trim() || null,
        push_token: config.push_token?.trim() || null,
        webhook_url: config.webhook_url?.trim() || null,
      };

      console.log('[AlertSettings] Cleaned config:', cleanConfig);

      if (cleanConfig.id) {
        // Update existing
        console.log('[AlertSettings] Updating existing config ID:', cleanConfig.id);
        await apiClient.put(`/alerts/config/${cleanConfig.id}`, cleanConfig);
        showMessage('Configuration updated successfully', 'success');
      } else {
        // Create new
        console.log('[AlertSettings] Creating new config');
        const response = await apiClient.post('/alerts/config', cleanConfig);
        setConfig(response.data);
        showMessage('Configuration created successfully', 'success');
      }
      loadStatistics();
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      console.error('[AlertSettings] Error saving configuration:', errorMsg);
      console.error('[AlertSettings] Full error:', error);
      console.error('[AlertSettings] Error response:', error.response?.data);
      showMessage('Error saving configuration: ' + errorMsg, 'error');
    } finally {
      setSaving(false);
      console.log('[AlertSettings] saveConfiguration complete');
    }
  };

  const testAlert = async (channel) => {
    setTesting(true);
    try {
      await apiClient.post('/alerts/test', {
        alert_config_id: config.id,
        channel: channel,
        message: 'This is a test alert from OpenEye'
      });
      showMessage(`Test ${channel} sent successfully!`, 'success');
    } catch (error) {
      showMessage(`Failed to send test ${channel}: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setTesting(false);
    }
  };

  const showMessage = (text, type) => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const updateConfig = (field, value) => {
    setConfig({ ...config, [field]: value });
  };

  if (loading) {
    return <div className="loading">Loading...</div>;
  }

  return (
    <div className="alert-settings-container">
      <header className="page-header">
        <div>
          <h1>Alert & Notification Settings</h1>
          <Button
            variant="primary"
            onClick={() => navigate('/system/notifications')}
            icon="🔔"
            style={{ marginTop: '8px' }}
          >
            Configure Notification Providers
          </Button>
        </div>
      </header>

      {message && (
        <div className={`alert alert-${message.type}`}>
          <span className="alert-icon">{message.type === 'success' ? '✓' : '⚠️'}</span>
          <div className="alert-content">{message.text}</div>
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <section className="stats-section">
          <h2>Alert Statistics (Last 7 Days)</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.total_notifications || 0}</div>
              <div className="stat-label">Total Alerts</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.successful || 0}</div>
              <div className="stat-label">Successful</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.failed || 0}</div>
              <div className="stat-label">Failed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{(stats.success_rate || 0).toFixed(1)}%</div>
              <div className="stat-label">Success Rate</div>
            </div>
          </div>
        </section>
      )}

      {/* Alert Types */}
      <section className="settings-section">
        <h2>Alert Types</h2>
        <div className="form-grid">
          <Switch
            checked={config.motion_alerts_enabled}
            onChange={(checked) => updateConfig('motion_alerts_enabled', checked)}
            label="Motion Detection Alerts"
          />

          <Switch
            checked={config.face_recognition_alerts_enabled}
            onChange={(checked) => updateConfig('face_recognition_alerts_enabled', checked)}
            label="Known Face Detection Alerts"
          />

          <Switch
            checked={config.unknown_face_alerts_enabled}
            onChange={(checked) => updateConfig('unknown_face_alerts_enabled', checked)}
            label="Unknown Face Detection Alerts"
          />

          <Switch
            checked={config.recording_alerts_enabled}
            onChange={(checked) => updateConfig('recording_alerts_enabled', checked)}
            label="Recording Start/Stop Alerts"
          />
        </div>
      </section>

      {/* v3.10.0: Object Detection Alerts */}
      <section className="settings-section">
        <h2>🔍 Object Detection Alerts (v3.10.0)</h2>
        <p className="section-description">
          Configure alerts for AI-detected objects (vehicles, animals, packages).
          Requires YOLO object detection to be enabled in system settings.
        </p>
        <div className="form-grid">
          <Switch
            checked={config.object_detection_alerts_enabled || false}
            onChange={(checked) => updateConfig('object_detection_alerts_enabled', checked)}
            label="Enable Object Detection Alerts (Master Toggle)"
            color="default"
          />

          {config.object_detection_alerts_enabled && (
            <>
              <div className="checkbox-indent">
                <Switch
                  checked={config.vehicle_alerts_enabled || false}
                  onChange={(checked) => updateConfig('vehicle_alerts_enabled', checked)}
                  label="🚗 Vehicle Detection Alerts (cars, trucks, motorcycles, etc.)"
                />
              </div>

              <div className="checkbox-indent">
                <Switch
                  checked={config.animal_alerts_enabled || false}
                  onChange={(checked) => updateConfig('animal_alerts_enabled', checked)}
                  label="🐾 Animal Detection Alerts (dogs, cats, birds, etc.)"
                />
              </div>

              <div className="checkbox-indent">
                <Switch
                  checked={config.package_alerts_enabled || false}
                  onChange={(checked) => updateConfig('package_alerts_enabled', checked)}
                  label="📦 Package Detection Alerts (boxes, bags, suitcases, etc.)"
                />
              </div>

              <div className="checkbox-indent">
                <Switch
                  checked={config.identified_object_alerts_enabled || false}
                  onChange={(checked) => updateConfig('identified_object_alerts_enabled', checked)}
                  label="🏷️ Identified Object Alerts (e.g., 'John's Tesla', 'My Dog Rex')"
                />
              </div>
            </>
          )}
        </div>
      </section>

      {/* Email Settings */}
      <section className="settings-section">
        <h2>
          ✉️ Email Notifications
          <HelpButton 
            title={HELP_CONTENT.EMAIL_NOTIFICATIONS.title}
            description={HELP_CONTENT.EMAIL_NOTIFICATIONS.description}
          />
        </h2>
        <div className="notification-method-header">
          <p className="method-description">
            Receive alert notifications via email. Configure SMTP server in Docker environment.
          </p>
        </div>
        <div className="form-group">
          <Switch
            checked={config.email_enabled}
            onChange={(checked) => updateConfig('email_enabled', checked)}
            label="Enable Email Notifications"
          />
        </div>
        {config.email_enabled && (
          <>
            <div className="form-group">
              <TextField
                type="email"
                label="Recipient Email Address"
                value={config.email_address || ''}
                onChange={(e) => updateConfig('email_address', e.target.value)}
                placeholder="your@email.com"
                fullWidth
              />
            </div>
            <div className="help-text mt-15">
              <p><strong>📧 SMTP Server Configuration</strong></p>
              <div style={{
                padding: '16px',
                background: 'var(--card-bg)',
                border: '2px solid var(--primary-color)',
                borderRadius: '8px',
                marginTop: '8px'
              }}>
                <p style={{ margin: '0 0 8px 0', fontWeight: '600' }}>✨ Configure via UI (No coding required!)</p>
                <p style={{ margin: '0 0 12px 0', fontSize: '14px' }}>Click the button below to set up email notifications through our user-friendly interface.</p>
                <Button
                  variant="primary"
                  size="medium"
                  onClick={() => navigate('/system/notifications')}
                  icon="📧"
                >
                  Configure Email Provider
                </Button>
                <small style={{ display: 'block', marginTop: '12px', opacity: '0.8' }}>
                  💡 For Gmail: You'll need an <a href="https://support.google.com/accounts/answer/185833" target="_blank" rel="noopener noreferrer">App Password</a>
                </small>
              </div>
            </div>
            {config.id && config.email_address && (
              <Button
                variant="secondary"
                size="small"
                onClick={() => testAlert('email')}
                disabled={testing}
                loading={testing}
              >
                Send Test Email
              </Button>
            )}
          </>
        )}
      </section>      {/* SMS Settings */}
      <section className="settings-section">
        <h2>
          📱 SMS Notifications
          <HelpButton
            title="SMS & Telegram Notifications"
            description="Send SMS alerts via Twilio (paid) or Telegram Bot (FREE!). Configure providers through the notification settings UI - no coding required!"
          />
        </h2>
        <div className="notification-method-header">
          <p className="method-description">
            Send SMS alerts via Twilio or Telegram Bot. Telegram is FREE! 🎉
          </p>
        </div>
        <div className="form-group">
          <Switch
            checked={config.sms_enabled}
            onChange={(checked) => updateConfig('sms_enabled', checked)}
            label="Enable SMS Notifications"
          />
        </div>
        {config.sms_enabled && (
          <>
            <div style={{
              padding: '16px',
              background: 'var(--card-bg)',
              border: '2px solid var(--primary-color)',
              borderRadius: '8px',
              marginTop: '16px'
            }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: '600' }}>✨ Configure via UI (No coding required!)</p>
              <p style={{ margin: '0 0 12px 0', fontSize: '14px' }}>Set up SMS (Twilio) or Telegram notifications through our user-friendly interface.</p>

              <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
                <Button
                  variant="primary"
                  size="medium"
                  onClick={() => navigate('/system/notifications')}
                  icon="📱"
                >
                  Configure SMS Provider
                </Button>
                <Button
                  variant="primary"
                  size="medium"
                  onClick={() => navigate('/system/notifications')}
                  icon="✈️"
                >
                  Configure Telegram Bot
                </Button>
              </div>

              <div className="help-text" style={{ fontSize: '13px', marginTop: '12px' }}>
                <p><strong>Telegram Setup:</strong></p>
                <p>1. Message <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a> to create a bot</p>
                <p>2. Get your chat ID from <a href="https://t.me/userinfobot" target="_blank" rel="noopener noreferrer">@userinfobot</a></p>
                <p>3. Enter credentials in the UI above (FREE! 🎉)</p>
              </div>
            </div>
            {config.id && config.phone_number && (
              <Button
                variant="secondary"
                size="small"
                onClick={() => testAlert('sms')}
                disabled={testing}
                loading={testing}
              >
                Send Test SMS/Telegram
              </Button>
            )}
          </>
        )}
      </section>

      {/* Push Notifications */}
      <section className="settings-section">
        <h2>
          🔔 Push Notifications
          <HelpButton
            title="Push Notifications"
            description="Send push notifications to mobile devices via Firebase Cloud Messaging. Configure through the notification settings UI - no coding required!"
          />
        </h2>
        <div className="notification-method-header">
          <p className="method-description">
            Send push notifications to mobile devices. Choose between Firebase or ntfy.sh (FREE & Open Source!)
          </p>
        </div>
        <div className="form-group">
          <Switch
            checked={config.push_enabled}
            onChange={(checked) => updateConfig('push_enabled', checked)}
            label="Enable Push Notifications"
          />
        </div>
        {config.push_enabled && (
          <>
            <div style={{
              padding: '16px',
              background: 'var(--card-bg)',
              border: '2px solid var(--primary-color)',
              borderRadius: '8px',
              marginTop: '16px'
            }}>
              <p style={{ margin: '0 0 8px 0', fontWeight: '600' }}>✨ Configure via UI (No coding required!)</p>
              <p style={{ margin: '0 0 12px 0', fontSize: '14px' }}>Set up push notifications through Firebase Cloud Messaging.</p>

              <Button
                variant="primary"
                size="medium"
                onClick={() => navigate('/system/notifications')}
                icon="🔔"
                style={{ marginBottom: '12px' }}
              >
                Configure Push Provider
              </Button>

              <div className="help-text" style={{ fontSize: '13px', marginTop: '12px' }}>
                <p><strong>Firebase Setup:</strong></p>
                <p>1. Create project at <a href="https://console.firebase.google.com/" target="_blank" rel="noopener noreferrer">Firebase Console</a></p>
                <p>2. Get your FCM Server Key from project settings</p>
                <p>3. Enter credentials in the UI above</p>
              </div>
              
              <div className="form-group mt-20">
                <TextField
                  type="text"
                  label="Device Token (FCM only)"
                  value={config.push_token || ''}
                  onChange={(e) => updateConfig('push_token', e.target.value)}
                  placeholder="Your FCM device token"
                  helperText="Leave empty if using ntfy.sh"
                  fullWidth
                />
              </div>
            </div>
            {config.id && (
              <Button
                variant="secondary"
                size="small"
                onClick={() => testAlert('push')}
                disabled={testing}
                loading={testing}
              >
                Send Test Push Notification
              </Button>
            )}
          </>
        )}
      </section>

      {/* Webhook Settings */}
      <section className="settings-section">
        <h2>
          🔗 Webhook Notifications
          <HelpButton 
            title={HELP_CONTENT.WEBHOOKS.title}
            description={HELP_CONTENT.WEBHOOKS.description}
          />
        </h2>
        <div className="form-group">
          <Switch
            checked={config.webhook_enabled}
            onChange={(checked) => updateConfig('webhook_enabled', checked)}
            label="Enable Webhook Notifications"
          />
        </div>
        {config.webhook_enabled && (
          <>
            <div className="form-group">
              <TextField
                type="url"
                label="Webhook URL"
                value={config.webhook_url || ''}
                onChange={(e) => updateConfig('webhook_url', e.target.value)}
                placeholder="https://your-webhook-url.com/endpoint"
                fullWidth
              />
            </div>
            {config.id && config.webhook_url && (
              <Button
                variant="secondary"
                size="small"
                onClick={() => testAlert('webhook')}
                disabled={testing}
                loading={testing}
              >
                Send Test Webhook
              </Button>
            )}
          </>
        )}
      </section>

      {/* Throttling */}
      <section className="settings-section">
        <h2>
          ⏱️ Alert Throttling
          <HelpButton 
            title={HELP_CONTENT.ALERT_THROTTLING.title}
            description={HELP_CONTENT.ALERT_THROTTLING.description}
          />
        </h2>
        <div className="form-group">
          <label>Minimum Seconds Between Alerts: {config.min_seconds_between_alerts}</label>
          <input
            type="range"
            min="60"
            max="3600"
            step="60"
            value={config.min_seconds_between_alerts}
            onChange={(e) => updateConfig('min_seconds_between_alerts', parseInt(e.target.value))}
          />
          <small>{Math.floor(config.min_seconds_between_alerts / 60)} minutes</small>
        </div>
      </section>

      {/* Quiet Hours */}
      <section className="settings-section">
        <h2>
          🌙 Quiet Hours
          <HelpButton 
            title={HELP_CONTENT.QUIET_HOURS.title}
            description={HELP_CONTENT.QUIET_HOURS.description}
          />
        </h2>
        <div className="form-group">
          <Switch
            checked={config.quiet_hours_enabled}
            onChange={(checked) => updateConfig('quiet_hours_enabled', checked)}
            label="Enable Quiet Hours (no alerts during this time)"
          />
        </div>
        {config.quiet_hours_enabled && (
          <div className="form-grid">
            <div className="form-group">
              <label>Start Time:</label>
              <input
                type="time"
                value={config.quiet_hours_start}
                onChange={(e) => updateConfig('quiet_hours_start', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>End Time:</label>
              <input
                type="time"
                value={config.quiet_hours_end}
                onChange={(e) => updateConfig('quiet_hours_end', e.target.value)}
              />
            </div>
          </div>
        )}
      </section>

      {/* Save Button */}
      <div className="save-section">
        <Button
          variant="primary"
          size="large"
          onClick={saveConfiguration}
          disabled={saving}
          loading={saving}
        >
          Save Configuration
        </Button>
      </div>

      {/* Recent Logs */}
      <section className="logs-section">
        <h2>Recent Notification Log</h2>
        {logs.length === 0 ? (
          <p className="no-logs">No notifications sent yet</p>
        ) : (
          <div className="logs-table-container">
            <table className="logs-table">
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Event</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className={log.sent_successfully ? 'success' : 'failed'}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.event_type}</td>
                    <td>{log.channel}</td>
                    <td>
                      <span className={`status ${log.sent_successfully ? 'success' : 'failed'}`}>
                        {log.sent_successfully ? '✓ Sent' : '✗ Failed'}
                      </span>
                    </td>
                    <td>{log.message.substring(0, 50)}...</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};

export default AlertSettingsPage;