// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import { ThemeProvider } from './context/ThemeContext';
import authService from './services/authService';
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
import AlertSettingsPage from './pages/AlertSettingsPage';
import SystemSettingsPage from './pages/SystemSettingsPage';
import ThemeSelectorPage from './pages/ThemeSelectorPage';

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
            <Route index element={<LiveDashboard />} />
            <Route path="events" element={<RecordingsPage />} />
            <Route path="cameras" element={<CameraManagementPage />} />
            <Route path="cameras/discovery" element={<CameraDiscoveryPage />} />
            <Route path="faces" element={<FaceManagementPage />} />
            <Route path="system" element={<SystemSettingsPage />} />
            <Route path="system/alerts" element={<AlertSettingsPage />} />
            <Route path="themes" element={<ThemeSelectorPage />} />
          </Route>
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;