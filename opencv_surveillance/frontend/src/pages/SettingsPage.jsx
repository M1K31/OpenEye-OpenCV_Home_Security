// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState } from 'react';
import { logger } from '../utils/logger';
import { useNavigate } from 'react-router-dom';
import CameraManagementPage from './CameraManagementPage';
import FaceManagementPage from './FaceManagementPage';
import AlertSettingsPage from './AlertSettingsPage';
import ThemeSelectorPage from './ThemeSelectorPage';
import SystemSettingsPage from './SystemSettingsPage';
import { Button } from '../components/universal';

const SettingsPage = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('cameras');

  logger.log('[SettingsPage] Rendering with activeTab:', activeTab);

  const tabs = [
    { id: 'cameras', label: 'Cameras', icon: '📹' },
    { id: 'faces', label: 'Faces', icon: '👤' },
    { id: 'alerts', label: 'Alerts', icon: '🔔' },
    { id: 'themes', label: 'Themes', icon: '🎨' },
    { id: 'system', label: 'System', icon: '⚙️' },
  ];

  const renderContent = () => {
    try {
      logger.log('[SettingsPage] renderContent called with tab:', activeTab);
      switch (activeTab) {
        case 'cameras':
          return <CameraManagementPage embedded={true} />;
        case 'faces':
          return <FaceManagementPage embedded={true} />;
        case 'alerts':
          return <AlertSettingsPage embedded={true} />;
        case 'themes':
          return <ThemeSelectorPage embedded={true} />;
        case 'system':
          return <SystemSettingsPage embedded={true} />;
        default:
          return <div style={styles.loading}>Select a tab</div>;
      }
    } catch (error) {
      logger.error('[SettingsPage] Error rendering tab content:', error);
      return <div style={styles.error}>Error loading content: {error.message}</div>;
    }
  };

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerTop}>
          <h1 style={styles.title}>⚙️ Settings</h1>
        </div>
      </header>

      <div style={styles.tabContainer}>
        <div style={styles.tabs}>
          {tabs.map(tab => (
            <Button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              variant={activeTab === tab.id ? 'primary' : 'tertiary'}
              size="medium"
              icon={tab.icon}
            >
              {tab.label}
            </Button>
          ))}
        </div>

        <div style={styles.content}>
          {renderContent()}
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
  tabContainer: {
    maxWidth: '1400px',
    margin: '0 auto',
    padding: '20px',
  },
  tabs: {
    display: 'flex',
    gap: '10px',
    marginBottom: '30px',
    borderBottom: '2px solid var(--border-panel)',
    paddingBottom: '8px',
    flexWrap: 'wrap',
  },
  content: {
    backgroundColor: 'var(--bg-main)',
    borderRadius: '8px',
    minHeight: '500px',
  },
  loading: {
    textAlign: 'center',
    padding: '40px',
    color: 'var(--text-primary)',
    fontSize: '16px',
  },
  error: {
    textAlign: 'center',
    padding: '40px',
    color: 'var(--color-error)',
    fontSize: '16px',
    backgroundColor: 'var(--danger-bg, rgba(220, 53, 69, 0.15))',
    borderRadius: '8px',
    border: '1px solid var(--color-error)',
  },
};

export default SettingsPage;
