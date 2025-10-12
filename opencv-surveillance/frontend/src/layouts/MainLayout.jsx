// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import './MainLayout.css';

/**
 * MainLayout - HIG Split View Architecture
 * 
 * Implements Apple Human Interface Guidelines Split View pattern:
 * - Fixed sidebar navigation (left)
 * - Dynamic content pane (right)
 * - Responsive breakpoints for mobile/tablet
 */
const MainLayout = ({ onLogout }) => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed);
  };

  const handleLogout = () => {
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
    </div>
  );
};

export default MainLayout;
