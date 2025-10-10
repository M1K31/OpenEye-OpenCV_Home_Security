// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
// SIMPLE TEST VERSION - Settings Page
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const SettingsPageSimple = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('test');

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerTop}>
          <h1 style={styles.title}>⚙️ Settings (Test Version)</h1>
          <button onClick={() => navigate('/')} style={styles.backButton}>
            ← Back to Dashboard
          </button>
        </div>
      </header>

      <div style={styles.content}>
        <h2 style={{ color: 'var(--text-primary)' }}>Settings Page Test</h2>
        <p style={{ color: 'var(--text-secondary)' }}>
          If you can see this, the Settings page routing works!
        </p>
        <p style={{ color: 'var(--text-secondary)' }}>
          The issue is likely with the embedded pages (Cameras, Faces, Alerts, Themes).
        </p>
        
        <div style={styles.testButtons}>
          <button 
            onClick={() => navigate('/camera-management')}
            style={styles.testButton}
          >
            Test Camera Management Directly
          </button>
          <button 
            onClick={() => navigate('/face-management')}
            style={styles.testButton}
          >
            Test Face Management Directly
          </button>
          <button 
            onClick={() => navigate('/alerts')}
            style={styles.testButton}
          >
            Test Alerts Directly
          </button>
          <button 
            onClick={() => navigate('/theme-selector')}
            style={styles.testButton}
          >
            Test Themes Directly
          </button>
        </div>

        <div style={styles.infoBox}>
          <h3 style={{ color: 'var(--text-primary)', marginTop: 0 }}>Debugging Instructions:</h3>
          <ol style={{ color: 'var(--text-secondary)', lineHeight: '1.8' }}>
            <li>Open Browser DevTools (Press F12)</li>
            <li>Go to the Console tab</li>
            <li>Look for messages starting with [SettingsPage]</li>
            <li>Look for any red error messages</li>
            <li>Try clicking the test buttons above</li>
            <li>If individual pages work but Settings doesn't, the issue is with embedded rendering</li>
          </ol>
        </div>
      </div>
    </div>
  );
};

const styles = {
  container: {
    backgroundColor: 'var(--bg-main)',
    minHeight: '100vh',
    color: 'var(--text-primary)',
  },
  header: {
    backgroundColor: 'var(--bg-panel)',
    borderBottom: '1px solid var(--border-panel)',
    padding: '20px',
    position: 'sticky',
    top: 0,
    zIndex: 10,
  },
  headerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  title: {
    margin: 0,
    fontSize: '28px',
    fontWeight: '600',
    color: 'var(--text-primary)',
  },
  backButton: {
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border-panel)',
    color: 'var(--text-primary)',
    padding: '10px 20px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    transition: 'all 0.2s',
  },
  content: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '40px 20px',
  },
  testButtons: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
    gap: '15px',
    margin: '30px 0',
  },
  testButton: {
    backgroundColor: 'var(--text-link)',
    color: 'white',
    border: 'none',
    padding: '15px 20px',
    borderRadius: '6px',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '600',
    transition: 'all 0.2s',
  },
  infoBox: {
    backgroundColor: 'rgba(0, 123, 255, 0.15)',
    border: '1px solid var(--text-link)',
    borderRadius: '8px',
    padding: '20px',
    marginTop: '30px',
  },
};

export default SettingsPageSimple;
