// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
/**
 * User Profile & Preferences Page
 * v3.11.1: Personal settings and preferences for the current user
 * 
 * Features:
 * - View/edit profile
 * - Notification preferences
 * - Camera access view
 * - Face profile linking
 * - UI preferences
 * - Ecosystem sync settings
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/apiClient';
import { logger } from '../utils/logger';
import './UserProfilePage.css';

const UserProfilePage = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  
  // Available options
  const [faceProfiles, setFaceProfiles] = useState([]);
  const [cameras, setCameras] = useState([]);
  
  // Tab state
  const [activeTab, setActiveTab] = useState('profile');
  
  // Form states
  const [profileForm, setProfileForm] = useState({
    display_name: '',
    email: '',
    avatar_url: ''
  });
  
  const [notificationTypes, setNotificationTypes] = useState({
    motion: true,
    face_known: true,
    face_unknown: true,
    doorbell: true,
    alarm: true,
    system: true
  });
  
  const [notificationChannels, setNotificationChannels] = useState({
    push: true,
    email: false,
    sms: false,
    ecosystem: true
  });
  
  const [quietHours, setQuietHours] = useState({
    enabled: false,
    start: '22:00',
    end: '07:00'
  });
  
  const [uiPrefs, setUiPrefs] = useState({
    theme: 'dark',
    default_view: 'grid',
    show_timestamps: true,
    compact_mode: false
  });
  
  const [dashboardPrefs, setDashboardPrefs] = useState({
    cameras_per_row: 2,
    show_events: true,
    max_events: 10,
    auto_refresh_interval: 5
  });
  
  useEffect(() => {
    loadUserData();
    loadFaceProfiles();
    loadCameras();
  }, []);
  
  const loadUserData = async () => {
    setLoading(true);
    try {
      // Get current user
      const userResponse = await apiClient.get('/users/me');
      setUser(userResponse.data);
      
      // Get preferences
      const prefsResponse = await apiClient.get(`/users/${userResponse.data.id}/preferences`);
      setPreferences(prefsResponse.data);
      
      // Populate forms
      setProfileForm({
        display_name: userResponse.data.display_name || '',
        email: userResponse.data.email || '',
        avatar_url: userResponse.data.avatar_url || ''
      });
      
      if (prefsResponse.data.notification_types) {
        setNotificationTypes(prefsResponse.data.notification_types);
      }
      if (prefsResponse.data.notification_channels) {
        setNotificationChannels(prefsResponse.data.notification_channels);
      }
      if (prefsResponse.data.quiet_hours) {
        setQuietHours(prefsResponse.data.quiet_hours);
      }
      if (prefsResponse.data.ui_preferences) {
        setUiPrefs(prefsResponse.data.ui_preferences);
      }
      if (prefsResponse.data.dashboard_preferences) {
        setDashboardPrefs(prefsResponse.data.dashboard_preferences);
      }
      
    } catch (err) {
      showMessage('Failed to load profile: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setLoading(false);
    }
  };
  
  const loadFaceProfiles = async () => {
    try {
      const response = await apiClient.get('/faces/people');
      const people = response.data?.data || response.data?.people || [];
      setFaceProfiles(people.map(p => p.name));
    } catch (err) {
      logger.error('Failed to load face profiles:', err);
    }
  };
  
  const loadCameras = async () => {
    try {
      const response = await apiClient.get('/cameras/');
      setCameras(response.data.cameras || []);
    } catch (err) {
      logger.error('Failed to load cameras:', err);
    }
  };
  
  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };
  
  const saveProfile = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/users/${user.id}`, profileForm);
      showMessage('Profile updated successfully');
      loadUserData();
    } catch (err) {
      showMessage('Failed to save profile: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSaving(false);
    }
  };
  
  const saveNotificationPreferences = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/users/${user.id}/preferences`, {
        notification_types: notificationTypes,
        notification_channels: notificationChannels,
        quiet_hours: quietHours
      });
      showMessage('Notification preferences saved');
    } catch (err) {
      showMessage('Failed to save: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSaving(false);
    }
  };
  
  const saveUIPreferences = async () => {
    setSaving(true);
    try {
      await apiClient.put(`/users/${user.id}/preferences`, {
        ui_preferences: uiPrefs,
        dashboard_preferences: dashboardPrefs
      });
      showMessage('UI preferences saved');
    } catch (err) {
      showMessage('Failed to save: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setSaving(false);
    }
  };
  
  const linkFaceProfile = async (profileName) => {
    try {
      if (profileName) {
        await apiClient.post(`/users/${user.id}/link-face`, { face_profile_name: profileName });
        showMessage(`Linked to face profile: ${profileName}`);
      } else {
        await apiClient.delete(`/users/${user.id}/link-face`);
        showMessage('Face profile unlinked');
      }
      loadUserData();
    } catch (err) {
      showMessage('Failed to link face: ' + (err.response?.data?.detail || err.message), 'error');
    }
  };
  
  if (loading) {
    return (
      <div className="user-profile-page">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="user-profile-page">
      <header className="page-header">
        <div className="header-content">
          <h1>My Profile</h1>
          <p className="subtitle">Manage your account and preferences</p>
        </div>
      </header>
      
      {message && (
        <div className={`message-banner ${message.type}`}>
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)}>×</button>
        </div>
      )}
      
      {/* Tab Navigation */}
      <nav className="tabs-nav">
        <button 
          className={activeTab === 'profile' ? 'active' : ''}
          onClick={() => setActiveTab('profile')}
        >
          Profile
        </button>
        <button 
          className={activeTab === 'notifications' ? 'active' : ''}
          onClick={() => setActiveTab('notifications')}
        >
          Notifications
        </button>
        <button 
          className={activeTab === 'ui' ? 'active' : ''}
          onClick={() => setActiveTab('ui')}
        >
          Interface
        </button>
        <button 
          className={activeTab === 'security' ? 'active' : ''}
          onClick={() => setActiveTab('security')}
        >
          Security
        </button>
      </nav>
      
      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="tab-content">
          <section className="settings-section">
            <h2>Basic Information</h2>
            
            <div className="profile-header">
              <div className="avatar-large">
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt={user.username} />
                ) : (
                  <span className="avatar-placeholder">
                    {(user.display_name || user.username).charAt(0).toUpperCase()}
                  </span>
                )}
              </div>
              <div className="profile-summary">
                <h3>{user.display_name || user.username}</h3>
                <p>@{user.username}</p>
                <span className={`role-badge ${user.role}`}>{user.role}</span>
              </div>
            </div>
            
            <div className="form-group">
              <label>Display Name</label>
              <input
                type="text"
                value={profileForm.display_name}
                onChange={(e) => setProfileForm({...profileForm, display_name: e.target.value})}
                placeholder="Your display name"
              />
            </div>
            
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={profileForm.email}
                onChange={(e) => setProfileForm({...profileForm, email: e.target.value})}
                placeholder="your@email.com"
              />
            </div>
            
            <div className="form-group">
              <label>Avatar URL</label>
              <input
                type="url"
                value={profileForm.avatar_url}
                onChange={(e) => setProfileForm({...profileForm, avatar_url: e.target.value})}
                placeholder="https://example.com/avatar.jpg"
              />
            </div>
            
            <button 
              className="btn btn-primary"
              onClick={saveProfile}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </section>
          
          <section className="settings-section">
            <h2>Face Recognition Link</h2>
            <p className="section-description">
              Link your account to a face recognition profile for automatic detection.
            </p>
            
            <div className="form-group">
              <label>Face Profile</label>
              <select
                value={user.face_profile_name || ''}
                onChange={(e) => linkFaceProfile(e.target.value)}
              >
                <option value="">-- Not linked --</option>
                {faceProfiles.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            
            {user.face_profile_name && (
              <div className="face-link-status">
                <span className="status-indicator success"></span>
                <span>Linked to: <strong>{user.face_profile_name}</strong></span>
              </div>
            )}
          </section>
        </div>
      )}
      
      {/* Notifications Tab */}
      {activeTab === 'notifications' && (
        <div className="tab-content">
          <section className="settings-section">
            <h2>Notification Types</h2>
            <p className="section-description">
              Choose which events trigger notifications.
            </p>
            
            <div className="toggle-group">
              {Object.entries(notificationTypes).map(([key, value]) => (
                <label key={key} className="toggle-item">
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) => setNotificationTypes({...notificationTypes, [key]: e.target.checked})}
                  />
                  <span className="toggle-label">
                    {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                </label>
              ))}
            </div>
          </section>
          
          <section className="settings-section">
            <h2>Delivery Channels</h2>
            <p className="section-description">
              How you want to receive notifications.
            </p>
            
            <div className="toggle-group">
              {Object.entries(notificationChannels).map(([key, value]) => (
                <label key={key} className="toggle-item">
                  <input
                    type="checkbox"
                    checked={value}
                    onChange={(e) => setNotificationChannels({...notificationChannels, [key]: e.target.checked})}
                  />
                  <span className="toggle-label">
                    {key === 'ecosystem' ? 'Send to Connected Devices' : key.replace(/\b\w/g, l => l.toUpperCase())}
                  </span>
                </label>
              ))}
            </div>
          </section>
          
          <section className="settings-section">
            <h2>Quiet Hours</h2>
            <p className="section-description">
              Pause non-critical notifications during these hours.
            </p>
            
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={quietHours.enabled}
                onChange={(e) => setQuietHours({...quietHours, enabled: e.target.checked})}
              />
              <span className="toggle-label">Enable Quiet Hours</span>
            </label>
            
            {quietHours.enabled && (
              <div className="time-range">
                <div className="form-group">
                  <label>Start</label>
                  <input
                    type="time"
                    value={quietHours.start}
                    onChange={(e) => setQuietHours({...quietHours, start: e.target.value})}
                  />
                </div>
                <div className="form-group">
                  <label>End</label>
                  <input
                    type="time"
                    value={quietHours.end}
                    onChange={(e) => setQuietHours({...quietHours, end: e.target.value})}
                  />
                </div>
              </div>
            )}
          </section>
          
          <button 
            className="btn btn-primary"
            onClick={saveNotificationPreferences}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Notification Preferences'}
          </button>
        </div>
      )}
      
      {/* UI Tab */}
      {activeTab === 'ui' && (
        <div className="tab-content">
          <section className="settings-section">
            <h2>Appearance</h2>
            
            <div className="form-group">
              <label>Theme</label>
              <select
                value={uiPrefs.theme}
                onChange={(e) => setUiPrefs({...uiPrefs, theme: e.target.value})}
              >
                <option value="dark">Dark</option>
                <option value="light">Light</option>
                <option value="system">System Default</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Default Camera View</label>
              <select
                value={uiPrefs.default_view}
                onChange={(e) => setUiPrefs({...uiPrefs, default_view: e.target.value})}
              >
                <option value="grid">Grid</option>
                <option value="list">List</option>
                <option value="single">Single Camera</option>
              </select>
            </div>
            
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={uiPrefs.show_timestamps}
                onChange={(e) => setUiPrefs({...uiPrefs, show_timestamps: e.target.checked})}
              />
              <span className="toggle-label">Show Timestamps on Events</span>
            </label>
            
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={uiPrefs.compact_mode}
                onChange={(e) => setUiPrefs({...uiPrefs, compact_mode: e.target.checked})}
              />
              <span className="toggle-label">Compact Mode</span>
            </label>
          </section>
          
          <section className="settings-section">
            <h2>Dashboard</h2>
            
            <div className="form-group">
              <label>Cameras Per Row</label>
              <input
                type="number"
                min="1"
                max="6"
                value={dashboardPrefs.cameras_per_row}
                onChange={(e) => setDashboardPrefs({...dashboardPrefs, cameras_per_row: parseInt(e.target.value)})}
              />
            </div>
            
            <div className="form-group">
              <label>Max Recent Events</label>
              <input
                type="number"
                min="5"
                max="50"
                value={dashboardPrefs.max_events}
                onChange={(e) => setDashboardPrefs({...dashboardPrefs, max_events: parseInt(e.target.value)})}
              />
            </div>
            
            <div className="form-group">
              <label>Auto Refresh (seconds)</label>
              <input
                type="number"
                min="1"
                max="60"
                value={dashboardPrefs.auto_refresh_interval}
                onChange={(e) => setDashboardPrefs({...dashboardPrefs, auto_refresh_interval: parseInt(e.target.value)})}
              />
            </div>
            
            <label className="toggle-item">
              <input
                type="checkbox"
                checked={dashboardPrefs.show_events}
                onChange={(e) => setDashboardPrefs({...dashboardPrefs, show_events: e.target.checked})}
              />
              <span className="toggle-label">Show Recent Events on Dashboard</span>
            </label>
          </section>
          
          <button 
            className="btn btn-primary"
            onClick={saveUIPreferences}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save UI Preferences'}
          </button>
        </div>
      )}
      
      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="tab-content">
          <section className="settings-section">
            <h2>Password</h2>
            <p className="section-description">
              Change your account password.
            </p>
            <button 
              className="btn btn-secondary"
              onClick={() => navigate('/settings?tab=security')}
            >
              Change Password
            </button>
          </section>
          
          <section className="settings-section">
            <h2>Two-Factor Authentication</h2>
            <p className="section-description">
              Add an extra layer of security to your account.
            </p>
            <div className="security-status">
              {user.two_factor_enabled ? (
                <>
                  <span className="status-indicator success"></span>
                  <span>2FA is <strong>enabled</strong></span>
                </>
              ) : (
                <>
                  <span className="status-indicator warning"></span>
                  <span>2FA is <strong>not enabled</strong></span>
                </>
              )}
            </div>
            <button 
              className="btn btn-secondary"
              onClick={() => navigate('/settings?tab=security')}
            >
              {user.two_factor_enabled ? 'Manage 2FA' : 'Enable 2FA'}
            </button>
          </section>
          
          <section className="settings-section">
            <h2>Active Sessions</h2>
            <p className="section-description">
              View and manage your active login sessions.
            </p>
            <button 
              className="btn btn-danger"
              onClick={async () => {
                if (window.confirm('This will log you out of all devices. Continue?')) {
                  try {
                    await apiClient.post('/token/revoke-all');
                    showMessage('All sessions revoked. You will be logged out.');
                    setTimeout(() => navigate('/login'), 2000);
                  } catch (err) {
                    showMessage('Failed to revoke sessions', 'error');
                  }
                }
              }}
            >
              Log Out All Devices
            </button>
          </section>
          
          <section className="settings-section">
            <h2>Account Info</h2>
            <div className="info-list">
              <div className="info-item">
                <span className="info-label">Account Created</span>
                <span className="info-value">
                  {user.created_at ? new Date(user.created_at).toLocaleDateString() : 'Unknown'}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Last Login</span>
                <span className="info-value">
                  {user.last_login ? new Date(user.last_login).toLocaleString() : 'Unknown'}
                </span>
              </div>
              <div className="info-item">
                <span className="info-label">Role</span>
                <span className="info-value">{user.role}</span>
              </div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

export default UserProfilePage;




