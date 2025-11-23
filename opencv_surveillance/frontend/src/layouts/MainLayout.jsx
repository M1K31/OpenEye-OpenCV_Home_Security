// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import KeyboardShortcuts from '../components/KeyboardShortcuts';
import wsService from '../services/WebSocketService';
import { getToken } from '../api/apiClient';
import { logger } from '../utils/logger';
import './MainLayout.css';

/**
 * MainLayout - Split View Layout
 * 
 * Two-column layout with persistent sidebar and dynamic content:
 * - Fixed sidebar navigation (left)
 * - Dynamic content pane (right)
 * - Responsive breakpoints for mobile/tablet
 */
const MainLayout = ({ onLogout }) => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Initialize WebSocket connection and reconnect when token changes
  useEffect(() => {
    const token = getToken();

    if (token) {
      logger.log('Initializing WebSocket connection with token...');
      // Disconnect any existing connection first
      wsService.disconnect();
      // Connect with new token
      wsService.connect(token);
    } else {
      logger.warn('No token found, WebSocket not initialized');
      wsService.disconnect();
    }

    // Cleanup: disconnect WebSocket on unmount
    return () => {
      logger.log('Disconnecting WebSocket...');
      wsService.disconnect();
    };
  }, [getToken()]); // Re-run when token changes

  const toggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  const handleLogout = () => {
    // Disconnect WebSocket before logout
    wsService.disconnect();

    if (onLogout) {
      onLogout();
    }
  };

  return (
    <div className="main-layout">
      {/* Top Bar */}
      <header className="main-layout-header">
        <div className="header-left">
          <button 
            className="sidebar-toggle" 
            onClick={toggleSidebar}
            aria-label="Toggle Sidebar"
          >
            {isSidebarCollapsed ? '☰' : '×'}
          </button>
          <h1 className="app-title">OpenEye</h1>
        </div>
        <div className="header-right">
          <span className="system-status">All Systems Nominal</span>
          <div className="user-menu-container">
            <button 
              className="user-menu-button" 
              aria-label="User Menu"
              onClick={() => setShowUserMenu(!showUserMenu)}
            >
              👤
            </button>
            {showUserMenu && (
              <div className="user-menu-dropdown">
                <button onClick={handleLogout} className="logout-button">
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Split View Container */}
      <div className="split-view-container">
        {/* Sidebar (Master) */}
        <Sidebar isCollapsed={isSidebarCollapsed} />

        {/* Content Pane (Detail) - React Router Outlet */}
        <main 
          className={`content-pane ${isSidebarCollapsed ? 'expanded' : ''}`}
          role="main"
        >
          <Outlet />
        </main>
      </div>

      {/* Keyboard Shortcuts Help - Floating button (bottom right) */}
      <KeyboardShortcuts />
    </div>
  );
};

export default MainLayout;
