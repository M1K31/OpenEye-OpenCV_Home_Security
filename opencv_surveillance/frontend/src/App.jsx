// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security
import React, { useState, useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import { ThemeProvider } from './context/ThemeContext';
import authService from './services/authService';
import ErrorBoundary from './components/ErrorBoundary';
import { PageErrorBoundaryWithRouter } from './components/PageErrorBoundary';
import { logger } from './utils/logger';
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
const DetectionsPage = lazy(() => import('./pages/DetectionsPage')); // v3.10.0: Unified detections
const AlertSettingsPage = lazy(() => import('./pages/AlertSettingsPage'));
const NotificationSettingsPage = lazy(() => import('./pages/NotificationSettingsPage'));
const SystemSettingsPage = lazy(() => import('./pages/SystemSettingsPage'));
const TwoFactorSettings = lazy(() => import('./pages/TwoFactorSettings'));
const ThemeSelectorPage = lazy(() => import('./pages/ThemeSelectorPage'));
const AutomationsPage = lazy(() => import('./pages/AutomationsPage'));
const TimelineView = lazy(() => import('./pages/TimelineView'));
const HardwareDetectionPage = lazy(() => import('./pages/HardwareDetectionPage'));
const PerformanceDashboard = lazy(() => import('./pages/PerformanceDashboard'));
const UserManagementPage = lazy(() => import('./pages/UserManagementPage'));
const UserProfilePage = lazy(() => import('./pages/UserProfilePage'));

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
  const [token, setToken] = useState(null);
  const [setupComplete, setSetupComplete] = useState(null);
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    // Validate token on app mount
    const validateToken = () => {
      if (authService.isAuthenticated()) {
        // Token exists and is valid
        setToken(authService.getToken());
      } else {
        // Token is expired or doesn't exist - clear it
        authService.setToken(null);
        authService.setRefreshToken(null);
        setToken(null);
      }
      setCheckingAuth(false);
    };

    validateToken();
  }, []);

  useEffect(() => {
    // Check if setup is complete on initial load
    const checkSetup = async () => {
      try {
        // Use relative URL so it works in Docker and traditional deployments
        const response = await axios.get('/api/setup/status');
        setSetupComplete(response.data.setup_complete);
      } catch (error) {
        logger.error('Error checking setup status:', error);
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

  // Show loading while checking auth and setup status
  if (checkingAuth || checkingSetup) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div>{checkingAuth ? 'Validating session...' : 'Checking setup status...'}</div>
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
                <PageErrorBoundaryWithRouter pageName="Events">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <RecordingsPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="timeline" element={
                <PageErrorBoundaryWithRouter pageName="Timeline">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <TimelineView />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="cameras" element={
                <PageErrorBoundaryWithRouter pageName="Camera Management">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <CameraManagementPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="cameras/discovery" element={
                <PageErrorBoundaryWithRouter pageName="Camera Discovery">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <CameraDiscoveryPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="faces" element={
                <PageErrorBoundaryWithRouter pageName="Face Management">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <FaceManagementPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              {/* Redirect old standalone routes to AI & Faces tabs */}
              <Route path="clusters" element={
                <Navigate to="/faces?tab=clustering" replace />
              } />
              <Route path="detections" element={
                <Navigate to="/faces?tab=detections" replace />
              } />
              <Route path="automations" element={
                <PageErrorBoundaryWithRouter pageName="Automations">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <AutomationsPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="system" element={
                <PageErrorBoundaryWithRouter pageName="System Settings">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <SystemSettingsPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="system/alerts" element={
                <PageErrorBoundaryWithRouter pageName="Alert Settings">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <AlertSettingsPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="system/notifications" element={
                <PageErrorBoundaryWithRouter pageName="Notification Settings">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <NotificationSettingsPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              <Route path="system/2fa" element={
                <Navigate to="/system?tab=2fa" replace />
              } />
              <Route path="themes" element={
                <PageErrorBoundaryWithRouter pageName="Themes">
                  <Suspense fallback={<PageLoadingFallback />}>
                    <ThemeSelectorPage />
                  </Suspense>
                </PageErrorBoundaryWithRouter>
              } />
              {/* Redirect old standalone routes to System & Alerts tabs */}
              <Route path="system/hardware" element={
                <Navigate to="/system?tab=hardware" replace />
              } />
              <Route path="system/performance" element={
                <Navigate to="/system?tab=performance" replace />
              } />
              <Route path="users" element={
                <Navigate to="/system?tab=users" replace />
              } />
              <Route path="profile" element={
                <Navigate to="/system?tab=profile" replace />
              } />
            </Route>
          </Routes>
        </Router>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;