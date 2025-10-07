// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const SettingsPage = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('general');
  const [saveMessage, setSaveMessage] = useState('');
  const [settings, setSettings] = useState({
    // Email settings
    email_enabled: false,
    smtp_server: '',
    smtp_port: 587,
    smtp_username: '',
    smtp_password: '',
    email_from: '',
    email_to: '',
    
    // Telegram settings
    telegram_enabled: false,
    telegram_token: '',
    telegram_chat_id: '',
    
    // Recording settings
    record_motion: true,
    recording_duration: 30,
    pre_record_buffer: 5,
    
    // Face recognition settings
    face_recognition_enabled: true,
    face_confidence_threshold: 0.6,
    unknown_face_notification: true,
    
    // System settings
    max_storage_gb: 100,
    retention_days: 30,
    log_level: 'INFO',
  });

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      // Load settings from environment/config
      // This would need a backend endpoint
      const response = await axios.get('/api/settings');
      setSettings(response.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      await axios.post('/api/settings', settings);
      showSaveMessage('Settings saved successfully!');
    } catch (error) {
      showSaveMessage('Failed to save settings: ' + (error.response?.data?.detail || error.message), true);
    }
  };

  const showSaveMessage = (message, isError = false) => {
    setSaveMessage({ text: message, isError });
    setTimeout(() => setSaveMessage(''), 3000);
  };

  const testEmailSettings = async () => {
    try {
      await axios.post('/api/settings/test-email');
      showSaveMessage('Test email sent successfully!');
    } catch (error) {
      showSaveMessage('Failed to send test email: ' + (error.response?.data?.detail || error.message), true);
    }
  };

  const testTelegramSettings = async () => {
    try {
      await axios.post('/api/settings/test-telegram');
      showSaveMessage('Test Telegram message sent successfully!');
    } catch (error) {
      showSaveMessage('Failed to send test message: ' + (error.response?.data?.detail || error.message), true);
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1>Settings</h1>
        <button onClick={() => navigate('/')} style={styles.backButton}>
          ← Back to Dashboard
        </button>
      </header>

      {saveMessage && (
        <div style={{
          ...styles.saveMessage,
          backgroundColor: saveMessage.isError ? '#fee' : '#efe',
          borderColor: saveMessage.isError ? '#c33' : '#3c3',
        }}>
          {saveMessage.text}
        </div>
      )}

      <div style={styles.content}>
        {/* Sidebar Navigation */}
        <aside style={styles.sidebar}>
          <button
            onClick={() => setActiveSection('general')}
            style={{
              ...styles.sidebarButton,
              ...(activeSection === 'general' ? styles.sidebarButtonActive : {})
            }}
          >
            ⚙️ General
          </button>
          <button
            onClick={() => setActiveSection('notifications')}
            style={{
              ...styles.sidebarButton,
              ...(activeSection === 'notifications' ? styles.sidebarButtonActive : {})
            }}
          >
            🔔 Notifications
          </button>
          <button
            onClick={() => setActiveSection('recording')}
            style={{
              ...styles.sidebarButton,
              ...(activeSection === 'recording' ? styles.sidebarButtonActive : {})
            }}
          >
            🎥 Recording
          </button>
          <button
            onClick={() => setActiveSection('faces')}
            style={{
              ...styles.sidebarButton,
              ...(activeSection === 'faces' ? styles.sidebarButtonActive : {})
            }}
          >
            👤 Face Recognition
          </button>
          <button
            onClick={() => setActiveSection('storage')}
            style={{
              ...styles.sidebarButton,
              ...(activeSection === 'storage' ? styles.sidebarButtonActive : {})
            }}
          >
            💾 Storage
          </button>
        </aside>

        {/* Main Content */}
        <main style={styles.main}>
          {activeSection === 'general' && (
            <div style={styles.section}>
              <h2>General Settings</h2>
              
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Log Level
                  <select
                    value={settings.log_level}
                    onChange={(e) => handleChange('log_level', e.target.value)}
                    style={styles.select}
                  >
                    <option value="DEBUG">Debug</option>
                    <option value="INFO">Info</option>
                    <option value="WARNING">Warning</option>
                    <option value="ERROR">Error</option>
                  </select>
                </label>
              </div>
            </div>
          )}

          {activeSection === 'notifications' && (
            <div style={styles.section}>
              <h2>Notification Settings</h2>
              
              {/* Email Settings */}
              <div style={styles.subsection}>
                <h3>Email Notifications</h3>
                
                <div style={styles.formGroup}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={settings.email_enabled}
                      onChange={(e) => handleChange('email_enabled', e.target.checked)}
                    />
                    Enable Email Notifications
                  </label>
                </div>

                {settings.email_enabled && (
                  <>
                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        SMTP Server
                        <input
                          type="text"
                          value={settings.smtp_server}
                          onChange={(e) => handleChange('smtp_server', e.target.value)}
                          placeholder="smtp.gmail.com"
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        SMTP Port
                        <input
                          type="number"
                          value={settings.smtp_port}
                          onChange={(e) => handleChange('smtp_port', parseInt(e.target.value))}
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        SMTP Username
                        <input
                          type="text"
                          value={settings.smtp_username}
                          onChange={(e) => handleChange('smtp_username', e.target.value)}
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        SMTP Password
                        <input
                          type="password"
                          value={settings.smtp_password}
                          onChange={(e) => handleChange('smtp_password', e.target.value)}
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        From Email
                        <input
                          type="email"
                          value={settings.email_from}
                          onChange={(e) => handleChange('email_from', e.target.value)}
                          placeholder="alerts@yourdomain.com"
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        To Email
                        <input
                          type="email"
                          value={settings.email_to}
                          onChange={(e) => handleChange('email_to', e.target.value)}
                          placeholder="you@example.com"
                          style={styles.input}
                        />
                      </label>
                    </div>

                    <button onClick={testEmailSettings} style={styles.testButton}>
                      Send Test Email
                    </button>
                  </>
                )}
              </div>

              {/* Telegram Settings */}
              <div style={styles.subsection}>
                <h3>Telegram Notifications</h3>
                
                <div style={styles.formGroup}>
                  <label style={styles.checkboxLabel}>
                    <input
                      type="checkbox"
                      checked={settings.telegram_enabled}
                      onChange={(e) => handleChange('telegram_enabled', e.target.checked)}
                    />
                    Enable Telegram Notifications
                  </label>
                </div>

                {settings.telegram_enabled && (
                  <>
                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        Telegram Bot Token
                        <input
                          type="text"
                          value={settings.telegram_token}
                          onChange={(e) => handleChange('telegram_token', e.target.value)}
                          placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                          style={styles.input}
                        />
                      </label>
                      <small style={styles.hint}>
                        Get your bot token from @BotFather on Telegram
                      </small>
                    </div>

                    <div style={styles.formGroup}>
                      <label style={styles.label}>
                        Chat ID
                        <input
                          type="text"
                          value={settings.telegram_chat_id}
                          onChange={(e) => handleChange('telegram_chat_id', e.target.value)}
                          placeholder="123456789"
                          style={styles.input}
                        />
                      </label>
                      <small style={styles.hint}>
                        Send /start to your bot to get your chat ID
                      </small>
                    </div>

                    <button onClick={testTelegramSettings} style={styles.testButton}>
                      Send Test Message
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {activeSection === 'recording' && (
            <div style={styles.section}>
              <h2>Recording Settings</h2>
              
              <div style={styles.formGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={settings.record_motion}
                    onChange={(e) => handleChange('record_motion', e.target.checked)}
                  />
                  Enable Motion Recording
                </label>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Recording Duration (seconds)
                  <input
                    type="number"
                    value={settings.recording_duration}
                    onChange={(e) => handleChange('recording_duration', parseInt(e.target.value))}
                    min="10"
                    max="300"
                    style={styles.input}
                  />
                </label>
                <small style={styles.hint}>
                  How long to record after motion is detected
                </small>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Pre-Record Buffer (seconds)
                  <input
                    type="number"
                    value={settings.pre_record_buffer}
                    onChange={(e) => handleChange('pre_record_buffer', parseInt(e.target.value))}
                    min="0"
                    max="30"
                    style={styles.input}
                  />
                </label>
                <small style={styles.hint}>
                  Record this many seconds before motion is detected
                </small>
              </div>
            </div>
          )}

          {activeSection === 'faces' && (
            <div style={styles.section}>
              <h2>Face Recognition Settings</h2>
              
              <div style={styles.formGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={settings.face_recognition_enabled}
                    onChange={(e) => handleChange('face_recognition_enabled', e.target.checked)}
                  />
                  Enable Face Recognition
                </label>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Confidence Threshold
                  <input
                    type="range"
                    value={settings.face_confidence_threshold}
                    onChange={(e) => handleChange('face_confidence_threshold', parseFloat(e.target.value))}
                    min="0.3"
                    max="0.9"
                    step="0.05"
                    style={styles.range}
                  />
                  <span style={styles.rangeValue}>{(settings.face_confidence_threshold * 100).toFixed(0)}%</span>
                </label>
                <small style={styles.hint}>
                  Higher values require more certainty before identifying a face
                </small>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={settings.unknown_face_notification}
                    onChange={(e) => handleChange('unknown_face_notification', e.target.checked)}
                  />
                  Notify on Unknown Faces
                </label>
              </div>

              <div style={styles.infoBox}>
                <strong>Supported Image Formats:</strong>
                <ul style={styles.formatList}>
                  <li>JPEG (.jpg, .jpeg)</li>
                  <li>PNG (.png)</li>
                  <li>BMP (.bmp)</li>
                  <li>TIFF (.tiff, .tif)</li>
                  <li>WebP (.webp)</li>
                </ul>
              </div>
            </div>
          )}

          {activeSection === 'storage' && (
            <div style={styles.section}>
              <h2>Storage Settings</h2>
              
              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Maximum Storage (GB)
                  <input
                    type="number"
                    value={settings.max_storage_gb}
                    onChange={(e) => handleChange('max_storage_gb', parseInt(e.target.value))}
                    min="10"
                    max="1000"
                    style={styles.input}
                  />
                </label>
                <small style={styles.hint}>
                  Maximum disk space to use for recordings
                </small>
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>
                  Retention Period (days)
                  <input
                    type="number"
                    value={settings.retention_days}
                    onChange={(e) => handleChange('retention_days', parseInt(e.target.value))}
                    min="1"
                    max="365"
                    style={styles.input}
                  />
                </label>
                <small style={styles.hint}>
                  Automatically delete recordings older than this
                </small>
              </div>
            </div>
          )}

          {/* Save Button */}
          <div style={styles.saveButtonContainer}>
            <button onClick={handleSave} style={styles.saveButton}>
              💾 Save Settings
            </button>
          </div>
        </main>
      </div>
    </div>
  );
};

const styles = {
  container: {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
    paddingBottom: '15px',
    borderBottom: '2px solid var(--me-border-color, #DDDDDD)',
  },
  backButton: {
    backgroundColor: 'var(--me-accent-blue, #42A5F5)',
    color: '#FFFFFF',
    padding: '10px 20px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontWeight: 'bold',
    fontSize: '14px',
  },
  saveMessage: {
    padding: '15px',
    borderRadius: '6px',
    marginBottom: '20px',
    border: '2px solid',
    fontWeight: 'bold',
    textAlign: 'center',
  },
  content: {
    display: 'flex',
    gap: '20px',
  },
  sidebar: {
    width: '200px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  sidebarButton: {
    backgroundColor: 'var(--me-card-background, #FFFFFF)',
    color: 'var(--me-text-primary, #212121)',
    padding: '12px 16px',
    border: '1px solid var(--me-border-color, #DDDDDD)',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    textAlign: 'left',
    transition: 'all 0.2s',
  },
  sidebarButtonActive: {
    backgroundColor: 'var(--me-accent-blue, #42A5F5)',
    color: '#FFFFFF',
    borderColor: 'var(--me-accent-blue, #42A5F5)',
    fontWeight: 'bold',
  },
  main: {
    flex: 1,
    backgroundColor: 'var(--me-card-background, #FFFFFF)',
    padding: '30px',
    borderRadius: '8px',
    boxShadow: '0 2px 8px var(--me-shadow-color, rgba(0, 0, 0, 0.1))',
  },
  section: {
    marginBottom: '40px',
  },
  subsection: {
    marginTop: '30px',
    padding: '20px',
    backgroundColor: 'var(--me-background, #F4F4F4)',
    borderRadius: '6px',
  },
  formGroup: {
    marginBottom: '20px',
  },
  label: {
    display: 'block',
    fontWeight: 'bold',
    marginBottom: '8px',
    color: 'var(--me-text-primary, #212121)',
  },
  checkboxLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    fontWeight: 'bold',
    color: 'var(--me-text-primary, #212121)',
    cursor: 'pointer',
  },
  input: {
    width: '100%',
    padding: '10px',
    border: '1px solid var(--me-border-color, #DDDDDD)',
    borderRadius: '4px',
    fontSize: '14px',
    marginTop: '5px',
  },
  select: {
    width: '100%',
    padding: '10px',
    border: '1px solid var(--me-border-color, #DDDDDD)',
    borderRadius: '4px',
    fontSize: '14px',
    marginTop: '5px',
  },
  range: {
    width: '80%',
    marginTop: '5px',
    marginRight: '10px',
  },
  rangeValue: {
    fontWeight: 'bold',
    color: 'var(--me-accent-blue, #42A5F5)',
  },
  hint: {
    display: 'block',
    marginTop: '5px',
    color: 'var(--me-text-secondary, #757575)',
    fontSize: '12px',
  },
  testButton: {
    backgroundColor: 'var(--me-accent-green, #66BB6A)',
    color: '#FFFFFF',
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '14px',
    marginTop: '10px',
  },
  infoBox: {
    backgroundColor: '#E3F2FD',
    padding: '15px',
    borderRadius: '6px',
    border: '1px solid var(--me-accent-blue, #42A5F5)',
    marginTop: '20px',
  },
  formatList: {
    marginTop: '10px',
    marginBottom: '0',
  },
  saveButtonContainer: {
    marginTop: '30px',
    padding: '20px',
    backgroundColor: 'var(--me-background, #F4F4F4)',
    borderRadius: '6px',
    textAlign: 'center',
  },
  saveButton: {
    backgroundColor: 'var(--me-accent-blue, #42A5F5)',
    color: '#FFFFFF',
    padding: '12px 40px',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
};

export default SettingsPage;
