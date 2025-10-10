// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import { ThemeProvider } from './context/ThemeContext';
// REMOVED: import './themes.css'; - Now in main.jsx
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import FaceManagementPage from './pages/FaceManagementPage';
import AlertSettingsPage from './pages/AlertSettingsPage';
import CameraDiscoveryPage from './pages/CameraDiscoveryPage';
import CameraManagementPage from './pages/CameraManagementPage';
import ThemeSelectorPage from './pages/ThemeSelectorPage';
import SettingsPage from './pages/SettingsPage';
import FirstRunSetup from './pages/FirstRunSetup';

// Configure axios interceptor to add Authorization header to all requests
axios.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    console.log('[Axios Interceptor] Request to:', config.url, 'Token exists:', !!token);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('[Axios Interceptor] Added Authorization header');
    } else {
      console.warn('[Axios Interceptor] No token found in localStorage');
    }
    return config;
  },
  (error) => {
    console.error('[Axios Interceptor] Request error:', error);
    return Promise.reject(error);
  }
);

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
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
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
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
          <Route
            path="/"
            element={token ? <DashboardPage onLogout={handleLogout} /> : <Navigate to="/login" />}
          />
          <Route
            path="/face-management"
            element={token ? <FaceManagementPage /> : <Navigate to="/login" />}
          />
          <Route
            path="/camera-discovery"
            element={token ? <CameraDiscoveryPage /> : <Navigate to="/login" />}
          />
          <Route
            path="/camera-management"
            element={token ? <CameraManagementPage /> : <Navigate to="/login" />}
          />
          <Route
            path="/theme-selector"
            element={token ? <ThemeSelectorPage /> : <Navigate to="/login" />}
          />
          <Route
            path="/alerts"
            element={token ? <AlertSettingsPage /> : <Navigate to="/login" />}
          />
          <Route
            path="/settings"
            element={token ? <SettingsPage /> : <Navigate to="/login" />}
          />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;