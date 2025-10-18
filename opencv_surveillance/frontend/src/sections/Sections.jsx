// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React from 'react';
import './Section.css';

export const EventsSection = () => (
  <div className="section-container">
    <h1 className="section-header">🚨 Events & History</h1>
    <p className="section-description">Motion and face detection timeline (coming soon)</p>
    <div className="section-placeholder">
      <span className="placeholder-icon">🚨</span>
      <p>Master-Detail Timeline View</p>
      <ul className="feature-list">
        <li>Date range filtering</li>
        <li>Event thumbnails</li>
        <li>Video playback</li>
        <li>Download/Delete recordings</li>
      </ul>
    </div>
  </div>
);

export const CamerasSection = () => (
  <div className="section-container">
    <h1 className="section-header">📹 Camera Manager</h1>
    <p className="section-description">Configure and manage all cameras</p>
    <div className="section-placeholder">
      <span className="placeholder-icon">📹</span>
      <p>Master-Detail Configuration</p>
      <ul className="feature-list">
        <li>Camera discovery</li>
        <li>Connection settings</li>
        <li>Detection zones</li>
        <li>Scheduling</li>
      </ul>
    </div>
  </div>
);

export const FacesSection = () => (
  <div className="section-container">
    <h1 className="section-header">👤 AI & Faces</h1>
    <p className="section-description">Facial recognition and AI settings</p>
    <div className="section-placeholder">
      <span className="placeholder-icon">👤</span>
      <p>Known Faces Gallery</p>
      <ul className="feature-list">
        <li>Enroll new faces</li>
        <li>Manage known people</li>
        <li>AI confidence settings</li>
        <li>Model training</li>
      </ul>
    </div>
  </div>
);

export const SystemSection = () => (
  <div className="section-container">
    <h1 className="section-header">⚙️ System & Alerts</h1>
    <p className="section-description">Global settings and integrations</p>
    <div className="section-placeholder">
      <span className="placeholder-icon">⚙️</span>
      <p>iOS-Style Settings</p>
      <ul className="feature-list">
        <li>Email & Telegram alerts</li>
        <li>MQTT integration</li>
        <li>HomeKit bridge</li>
        <li>System preferences</li>
      </ul>
    </div>
  </div>
);

export const ThemesSection = () => (
  <div className="section-container">
    <h1 className="section-header">🎨 Themes</h1>
    <p className="section-description">Customize your OpenEye appearance</p>
    <div className="section-placeholder">
      <span className="placeholder-icon">🎨</span>
      <p>Theme Selector</p>
      <p style={{ marginTop: '16px' }}>
        <a href="/theme-selector" className="btn-primary">
          Open Theme Selector
        </a>
      </p>
    </div>
  </div>
);
