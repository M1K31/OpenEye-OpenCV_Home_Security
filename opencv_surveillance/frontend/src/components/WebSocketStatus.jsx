/*
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security
*/

import React, { useState, useEffect } from 'react';
import wsService from '../services/WebSocketService';
import './WebSocketStatus.css';

/**
 * WebSocket Connection Status Indicator
 *
 * Shows the current connection status of the WebSocket service
 * with visual feedback and tooltips.
 *
 * Statuses:
 * - connected: 🟢 Green - Live updates active
 * - connecting: 🟡 Yellow - Attempting to connect
 * - disconnected: 🔴 Red - No connection (fallback to polling)
 * - error: 🔴 Red - Connection error
 */
const WebSocketStatus = ({ minimal = false }) => {
  const [status, setStatus] = useState(wsService.getStatus());
  const [lastUpdate, setLastUpdate] = useState(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  useEffect(() => {
    // Subscribe to status changes
    const unsubscribe = wsService.on('status_change', (data) => {
      setStatus(data.status);
      setLastUpdate(new Date());

      if (data.status === 'disconnected') {
        setReconnectAttempts(wsService.reconnectAttempts || 0);
      } else if (data.status === 'connected') {
        setReconnectAttempts(0);
      }
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
    };
  }, []);

  const getStatusConfig = () => {
    switch (status) {
      case 'connected':
        return {
          icon: '🟢',
          label: 'Live',
          className: 'ws-status-connected',
          tooltip: 'Real-time updates active'
        };
      case 'connecting':
        return {
          icon: '🟡',
          label: 'Connecting',
          className: 'ws-status-connecting',
          tooltip: 'Establishing connection...'
        };
      case 'disconnected':
        return {
          icon: '🔴',
          label: 'Offline',
          className: 'ws-status-disconnected',
          tooltip: reconnectAttempts > 0
            ? `Reconnecting (attempt ${reconnectAttempts}/${wsService.maxReconnectAttempts})`
            : 'Disconnected - using fallback polling'
        };
      case 'error':
        return {
          icon: '🔴',
          label: 'Error',
          className: 'ws-status-error',
          tooltip: 'Connection error - check network'
        };
      default:
        return {
          icon: '⚪',
          label: 'Unknown',
          className: 'ws-status-unknown',
          tooltip: 'Status unknown'
        };
    }
  };

  const config = getStatusConfig();

  if (minimal) {
    return (
      <span className={`ws-status-minimal ${config.className}`} title={config.tooltip}>
        <span className="ws-status-icon">{config.icon}</span>
      </span>
    );
  }

  return (
    <div className={`ws-status ${config.className}`} title={config.tooltip}>
      <span className="ws-status-icon">{config.icon}</span>
      <span className="ws-status-label">{config.label}</span>
      {lastUpdate && status === 'connected' && (
        <span className="ws-status-pulse"></span>
      )}
    </div>
  );
};

export default WebSocketStatus;
