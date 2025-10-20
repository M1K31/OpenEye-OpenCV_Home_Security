// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import { ThemeProvider } from './context/ThemeContext';
import authService from './services/authService';
import ErrorBoundary from './components/ErrorBoundary';
// REMOVED: import './themes.css'; - Now in main.jsx

// New Layout Components
import MainLayout from './layouts/MainLayout';

// New Section Components
import LiveDashboard from './sections/LiveDashboard';

// Working Pages (formerly "Legacy Pages")
import RecordingsPage from './pages/RecordingsPage';
import CameraManagementPage from './pages/CameraManagementPage';
import CameraDiscoveryPage from './pages/CameraDiscoveryPage';
import FaceManagementPage from './pages/FaceManagementPage';
import FaceClusteringPage from './pages/FaceClusteringPage';
import AlertSettingsPage from './pages/AlertSettingsPage';
import SystemSettingsPage from './pages/SystemSettingsPage';
import ThemeSelectorPage from './pages/ThemeSelectorPage';
import AutomationsPage from './pages/AutomationsPage';
import TimelineView from './pages/TimelineView';

// Legacy Pages (for setup and login)
import LoginPage from './pages/LoginPage';
import FirstRunSetup from './pages/FirstRunSetup';

// Auth service automatically sets up axios interceptors
// for token management and automatic refresh

function App() {
  const [token, setToken] = useState(authService.getToken());
  const [setupComplete, setSetupComplete] = useState(null);
  const [checkingSetup, setCheckingSetup] = useState(true);

  useEffect(() => {
    // Check if setup is complete on initial load
    const checkSetup = async () => {
      try {
        // Use relative URL so it works in Docker and traditional deployments
        const response = await axios.get('/api/setup/status');
        setSetupComplete(response.data.setup_complete);
      } catch (error) {
        console.error('Error checking setup status:', error);
        // If check fails, assume setup is complete to avoid blocking
        setSetupComplete(true);
      } finally {
        setCheckingSetup(false);
      }
    };
    checkSetup();
  }, []);

  const handleSetToken = (newToken) => {
    authService.setToken(newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    authService.logout();
    setToken(null);
  };

  // Show loading while checking setup status
  if (checkingSetup) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div>Checking setup status...</div>
      </div>
    );
  }

  // If setup is not complete, redirect to setup page
  if (!setupComplete) {
    return (
      <ThemeProvider>
        <Router>
          <Routes>
            <Route 
              path="/setup" 
              element={
                <FirstRunSetup 
                  onComplete={() => {
                    setSetupComplete(true);
                  }} 
                />
              } 
            />
            <Route path="*" element={<Navigate to="/setup" />} />
          </Routes>
        </Router>
      </ThemeProvider>
    );
  }

  return (
    <ErrorBoundary fallbackMessage="Sorry, the application encountered an error. Please try refreshing the page.">
      <ThemeProvider>
        <Router>
          <Routes>
            <Route
              path="/login"
              element={!token ? <LoginPage setToken={handleSetToken} /> : <Navigate to="/" />}
            />
            {/* Protected Routes - All wrapped in MainLayout */}
            <Route
              path="/"
              element={token ? <MainLayout onLogout={handleLogout} /> : <Navigate to="/login" />}
            >
              {/* Section-based Navigation with Working Pages */}
              <Route index element={<ErrorBoundary><LiveDashboard /></ErrorBoundary>} />
              <Route path="events" element={<ErrorBoundary><RecordingsPage /></ErrorBoundary>} />
              <Route path="timeline" element={<ErrorBoundary><TimelineView /></ErrorBoundary>} />
              <Route path="cameras" element={<ErrorBoundary><CameraManagementPage /></ErrorBoundary>} />
              <Route path="cameras/discovery" element={<ErrorBoundary><CameraDiscoveryPage /></ErrorBoundary>} />
              <Route path="faces" element={<ErrorBoundary><FaceManagementPage /></ErrorBoundary>} />
              <Route path="clusters" element={<ErrorBoundary><FaceClusteringPage /></ErrorBoundary>} />
              <Route path="automations" element={<ErrorBoundary><AutomationsPage /></ErrorBoundary>} />
              <Route path="system" element={<ErrorBoundary><SystemSettingsPage /></ErrorBoundary>} />
              <Route path="system/alerts" element={<ErrorBoundary><AlertSettingsPage /></ErrorBoundary>} />
              <Route path="themes" element={<ErrorBoundary><ThemeSelectorPage /></ErrorBoundary>} />
            </Route>
          </Routes>
        </Router>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;