// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import './Sidebar.css';

/**
 * Sidebar - Persistent Navigation Component
 * 
 * Implements HIG sidebar with:
 * - Icon + label navigation
 * - Frosted glass effect (Aqua Security theme)
 * - Active state highlighting
 * - Responsive collapse on mobile
 */
const Sidebar = ({ isCollapsed }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const sections = [
    {
      id: 'dashboard',
      icon: '🏠',
      label: 'Live Dashboard',
      path: '/',
      priority: 'high'
    },
    {
      id: 'events',
      icon: '🚨',
      label: 'Events & History',
      path: '/events',
      priority: 'high'
    },
    {
      id: 'cameras',
      icon: '📹',
      label: 'Camera Manager',
      path: '/cameras',
      priority: 'medium'
    },
    {
      id: 'faces',
      icon: '👤',
      label: 'AI & Faces',
      path: '/faces',
      priority: 'medium'
    },
    {
      id: 'system',
      icon: '⚙️',
      label: 'System & Alerts',
      path: '/system',
      priority: 'medium'
    },
    {
      id: 'themes',
      icon: '🎨',
      label: 'Themes',
      path: '/themes',
      priority: 'low'
    }
  ];

  const handleNavigate = (section) => {
    navigate(section.path);
  };

  const isActive = (section) => {
    return location.pathname === section.path;
  };

  return (
    <aside 
      className={`sidebar ${isCollapsed ? 'collapsed' : ''}`}
      role="navigation"
      aria-label="Main Navigation"
    >
      <nav className="sidebar-nav">
        {sections.map((section) => (
          <button
            key={section.id}
            className={`nav-item ${isActive(section) ? 'active' : ''} priority-${section.priority}`}
            onClick={() => handleNavigate(section)}
            aria-current={isActive(section) ? 'page' : undefined}
            title={section.label}
          >
            <span className="nav-icon" role="img" aria-hidden="true">
              {section.icon}
            </span>
            <span className="nav-label">{section.label}</span>
          </button>
        ))}
      </nav>

      {/* Sidebar Footer */}
      <div className="sidebar-footer">
        <div className="version-info">
          <span className="version-label">OpenEye</span>
          <span className="version-number">v3.5.2</span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
