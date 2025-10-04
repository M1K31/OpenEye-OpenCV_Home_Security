// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye.
import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import FaceManagementPage from './pages/FaceManagementPage';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));

  const handleSetToken = (newToken) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  return (
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
      </Routes>
    </Router>
  );
}

export default App;