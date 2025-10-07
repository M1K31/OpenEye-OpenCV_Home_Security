// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import './AlertSettingsPage.css';

const AlertSettingsPage = () => {
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
      const response = await axios.get('/api/alerts/config?user_id=1');
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
          email_enabled: true,
          sms_enabled: false,
          push_enabled: false,
          webhook_enabled: false,
          email_address: '',
          phone_number: '',
          push_token: '',
          webhook_url: '',
          min_seconds_between_alerts: 300,
          quiet_hours_enabled: false,
          quiet_hours_start: '22:00',
          quiet_hours_end: '07:00'
        });
      }
      setLoading(false);
    } catch (error) {
      showMessage('Error loading configuration: ' + error.message, 'error');
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await axios.get('/api/alerts/statistics?days=7');
      setStats(response.data);
    } catch (error) {
      console.error('Error loading statistics:', error);
    }
  };

  const loadLogs = async () => {
    try {
      const response = await axios.get('/api/alerts/logs?limit=20');
      setLogs(response.data);
    } catch (error) {
      console.error('Error loading logs:', error);
    }
  };

  const saveConfiguration = async () => {
    setSaving(true);
    try {
      if (config.id) {
        // Update existing
        await axios.put(`/api/alerts/config/${config.id}`, config);
        showMessage('Configuration updated successfully', 'success');
      } else {
        // Create new
        const response = await axios.post('/api/alerts/config', config);
        setConfig(response.data);
        showMessage('Configuration created successfully', 'success');
      }
      loadStatistics();
    } catch (error) {
      showMessage('Error saving configuration: ' + error.message, 'error');
    } finally {
      setSaving(false);
    }
  };

  const testAlert = async (channel) => {
    setTesting(true);
    try {
      await axios.post('/api/alerts/test', {
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
        <h1>Alert & Notification Settings</h1>
        <button onClick={() => navigate('/')} className="btn-secondary">
          Back to Dashboard
        </button>
      </header>

      {message && (
        <div className={`message message-${message.type}`}>
          {message.text}
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <section className="stats-section">
          <h2>Alert Statistics (Last 7 Days)</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats.total_notifications}</div>
              <div className="stat-label">Total Alerts</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.successful}</div>
              <div className="stat-label">Successful</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.failed}</div>
              <div className="stat-label">Failed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.success_rate.toFixed(1)}%</div>
              <div className="stat-label">Success Rate</div>
            </div>
          </div>
        </section>
      )}

      {/* Alert Types */}
      <section className="settings-section">
        <h2>Alert Types</h2>
        <div className="form-grid">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.motion_alerts_enabled}
              onChange={(e) => updateConfig('motion_alerts_enabled', e.target.checked)}
            />
            <span>Motion Detection Alerts</span>
          </label>
          
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.face_recognition_alerts_enabled}
              onChange={(e) => updateConfig('face_recognition_alerts_enabled', e.target.checked)}
            />
            <span>Known Face Detection Alerts</span>
          </label>
          
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.unknown_face_alerts_enabled}
              onChange={(e) => updateConfig('unknown_face_alerts_enabled', e.target.checked)}
            />
            <span>Unknown Face Detection Alerts</span>
          </label>
          
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.recording_alerts_enabled}
              onChange={(e) => updateConfig('recording_alerts_enabled', e.target.checked)}
            />
            <span>Recording Start/Stop Alerts</span>
          </label>
        </div>
      </section>

      {/* Email Settings */}
      <section className="settings-section">
        <h2>📧 Email Notifications</h2>
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.email_enabled}
              onChange={(e) => updateConfig('email_enabled', e.target.checked)}
            />
            <span>Enable Email Notifications</span>
          </label>
        </div>
        {config.email_enabled && (
          <>
            <div className="form-group">
              <label>Email Address:</label>
              <input
                type="email"
                value={config.email_address || ''}
                onChange={(e) => updateConfig('email_address', e.target.value)}
                placeholder="your@email.com"
              />
            </div>
            {config.id && config.email_address && (
              <button
                onClick={() => testAlert('email')}
                disabled={testing}
                className="btn-test"
              >
                Send Test Email
              </button>
            )}
          </>
        )}
      </section>

      {/* SMS Settings */}
      <section className="settings-section">
        <h2>📱 SMS Notifications (Twilio)</h2>
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.sms_enabled}
              onChange={(e) => updateConfig('sms_enabled', e.target.checked)}
            />
            <span>Enable SMS Notifications</span>
          </label>
        </div>
        {config.sms_enabled && (
          <>
            <div className="form-group">
              <label>Phone Number (E.164 format):</label>
              <input
                type="tel"
                value={config.phone_number || ''}
                onChange={(e) => updateConfig('phone_number', e.target.value)}
                placeholder="+1234567890"
              />
              <small>Include country code (e.g., +1 for USA)</small>
            </div>
            {config.id && config.phone_number && (
              <button
                onClick={() => testAlert('sms')}
                disabled={testing}
                className="btn-test"
              >
                Send Test SMS
              </button>
            )}
          </>
        )}
      </section>

      {/* Webhook Settings */}
      <section className="settings-section">
        <h2>🔗 Webhook Notifications</h2>
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.webhook_enabled}
              onChange={(e) => updateConfig('webhook_enabled', e.target.checked)}
            />
            <span>Enable Webhook Notifications</span>
          </label>
        </div>
        {config.webhook_enabled && (
          <>
            <div className="form-group">
              <label>Webhook URL:</label>
              <input
                type="url"
                value={config.webhook_url || ''}
                onChange={(e) => updateConfig('webhook_url', e.target.value)}
                placeholder="https://your-webhook-url.com/endpoint"
              />
            </div>
            {config.id && config.webhook_url && (
              <button
                onClick={() => testAlert('webhook')}
                disabled={testing}
                className="btn-test"
              >
                Send Test Webhook
              </button>
            )}
          </>
        )}
      </section>

      {/* Throttling */}
      <section className="settings-section">
        <h2>⏱️ Alert Throttling</h2>
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
        <h2>🌙 Quiet Hours</h2>
        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={config.quiet_hours_enabled}
              onChange={(e) => updateConfig('quiet_hours_enabled', e.target.checked)}
            />
            <span>Enable Quiet Hours (no alerts during this time)</span>
          </label>
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
        <button
          onClick={saveConfiguration}
          disabled={saving}
          className="btn-primary btn-large"
        >
          {saving ? 'Saving...' : 'Save Configuration'}
        </button>
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