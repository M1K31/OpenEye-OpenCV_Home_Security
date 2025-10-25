// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import { ThemeProvider } from './context/ThemeContext';
import authService from './services/authService';
import ErrorBoundary from './components/ErrorBoundary';
// REMOVED: import './themes.css'; - Now in main.jsx

// New Layout Components
import MainLayout from './layouts/MainLayout';

// Eager load critical pages (Login, Setup, Dashboard)
import LoginPage from './pages/LoginPage';
import FirstRunSetup from './pages/FirstRunSetup';
import LiveDashboard from './sections/LiveDashboard';

// Lazy load all other pages for code splitting and faster initial load
const RecordingsPage = lazy(() => import('./pages/RecordingsPage'));
const CameraManagementPage = lazy(() => import('./pages/CameraManagementPage'));
const CameraDiscoveryPage = lazy(() => import('./pages/CameraDiscoveryPage'));
const FaceManagementPage = lazy(() => import('./pages/FaceManagementPage'));
const FaceClusteringPage = lazy(() => import('./pages/FaceClusteringPage'));
const AlertSettingsPage = lazy(() => import('./pages/AlertSettingsPage'));
const NotificationSettingsPage = lazy(() => import('./pages/NotificationSettingsPage'));
const SystemSettingsPage = lazy(() => import('./pages/SystemSettingsPage'));
const TwoFactorSettings = lazy(() => import('./pages/TwoFactorSettings'));
const ThemeSelectorPage = lazy(() => import('./pages/ThemeSelectorPage'));
const AutomationsPage = lazy(() => import('./pages/AutomationsPage'));
const TimelineView = lazy(() => import('./pages/TimelineView'));

// Loading fallback component
const PageLoadingFallback = () => (
  <div style={{
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100%',
    minHeight: '400px',
    color: 'var(--text-secondary)',
    fontSize: '14px'
  }}>
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: '24px', marginBottom: '16px' }}>⏳</div>
      <div>Loading page...</div>
    </div>
  </div>
);

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
              {/* Section-based Navigation with Working Pages - Wrapped in Suspense for lazy loading */}
              <Route index element={<ErrorBoundary><LiveDashboard /></ErrorBoundary>} />
              <Route path="events" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <RecordingsPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="timeline" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <TimelineView />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="cameras" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <CameraManagementPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="cameras/discovery" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <CameraDiscoveryPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="faces" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <FaceManagementPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="clusters" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <FaceClusteringPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="automations" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <AutomationsPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="system" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <SystemSettingsPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="system/alerts" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <AlertSettingsPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="system/notifications" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <NotificationSettingsPage />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="system/2fa" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <TwoFactorSettings />
                  </Suspense>
                </ErrorBoundary>
              } />
              <Route path="themes" element={
                <ErrorBoundary>
                  <Suspense fallback={<PageLoadingFallback />}>
                    <ThemeSelectorPage />
                  </Suspense>
                </ErrorBoundary>
              } />
            </Route>
          </Routes>
        </Router>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;