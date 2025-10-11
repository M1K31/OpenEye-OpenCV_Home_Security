/**
 * OpenEye WebSocket Service
 * Copyright (c) 2025 M1K31
 * 
 * Manages WebSocket connection for real-time statistics and event streaming.
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Event subscription system
 * - Connection health monitoring
 * - Graceful fallback to polling
 */

class WebSocketService {
  constructor() {
    this.ws = null;
    this.url = null;
    this.token = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 1000; // Start with 1 second
    this.maxReconnectDelay = 30000; // Max 30 seconds
    this.reconnectTimeout = null;
    this.pingInterval = null;
    this.isIntentionalClose = false;
    this.connectionStatus = 'disconnected'; // disconnected, connecting, connected, error
    
    // Event listeners
    this.listeners = {
      statistics_update: [],
      camera_event: [],
      alert: [],
      connection_status: [],
      error: [],
      status_change: [] // Fired when connection status changes
    };
  }

  /**
   * Connect to WebSocket server
   * @param {string} token - JWT authentication token
   */
  connect(token) {
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket already connected or connecting');
      return;
    }

    this.token = token;
    this.isIntentionalClose = false;
    
    // Determine WebSocket URL based on current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    this.url = `${protocol}//${host}/api/ws/statistics?token=${encodeURIComponent(token)}`;
    
    this.updateStatus('connecting');
    console.log('Connecting to WebSocket:', this.url.replace(token, '***'));

    try {
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.updateStatus('error');
      this.scheduleReconnect();
    }
  }

  /**
   * Handle WebSocket open event
   */
  handleOpen() {
    console.log('WebSocket connected successfully');
    this.reconnectAttempts = 0;
    this.reconnectDelay = 1000;
    this.updateStatus('connected');
    
    // Start ping interval to keep connection alive (every 30 seconds)
    this.startPingInterval();
  }

  /**
   * Handle incoming WebSocket messages
   */
  handleMessage(event) {
    try {
      const message = JSON.parse(event.data);
      const messageType = message.type;
      
      // Emit to specific listeners
      if (this.listeners[messageType]) {
        this.listeners[messageType].forEach(callback => {
          try {
            callback(message);
          } catch (error) {
            console.error(`Error in ${messageType} listener:`, error);
          }
        });
      }
      
      // Log certain message types
      if (messageType === 'connection_status') {
        console.log('Connection status:', message);
      } else if (messageType === 'statistics_update') {
        // Statistics updates are frequent, only log in debug mode
        // console.debug('Statistics update received');
      } else {
        console.log('WebSocket message:', messageType, message);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  /**
   * Handle WebSocket error
   */
  handleError(event) {
    console.error('WebSocket error:', event);
    this.updateStatus('error');
    this.emit('error', { error: 'WebSocket connection error', event });
  }

  /**
   * Handle WebSocket close event
   */
  handleClose(event) {
    console.log('WebSocket closed:', event.code, event.reason);
    this.stopPingInterval();
    
    if (!this.isIntentionalClose) {
      this.updateStatus('disconnected');
      this.scheduleReconnect();
    } else {
      this.updateStatus('disconnected');
    }
  }

  /**
   * Schedule reconnection with exponential backoff
   */
  scheduleReconnect() {
    if (this.isIntentionalClose) {
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached, giving up');
      this.emit('error', { 
        error: 'Max reconnection attempts reached', 
        fallback: 'polling' 
      });
      return;
    }

    this.reconnectAttempts++;
    
    // Exponential backoff with jitter
    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      this.maxReconnectDelay
    ) + Math.random() * 1000;
    
    console.log(`Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    this.reconnectTimeout = setTimeout(() => {
      if (this.token && !this.isIntentionalClose) {
        this.connect(this.token);
      }
    }, delay);
  }

  /**
   * Start ping interval to keep connection alive
   */
  startPingInterval() {
    this.stopPingInterval();
    
    this.pingInterval = setInterval(() => {
      if (this.isConnected()) {
        this.send({
          type: 'ping',
          timestamp: new Date().toISOString()
        });
      }
    }, 30000); // Ping every 30 seconds
  }

  /**
   * Stop ping interval
   */
  stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  /**
   * Send message through WebSocket
   */
  send(message) {
    if (this.isConnected()) {
      try {
        this.ws.send(JSON.stringify(message));
      } catch (error) {
        console.error('Failed to send WebSocket message:', error);
      }
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }

  /**
   * Subscribe to specific event types
   */
  subscribe(eventTypes) {
    if (this.isConnected()) {
      this.send({
        type: 'subscribe',
        event_types: Array.isArray(eventTypes) ? eventTypes : [eventTypes]
      });
    }
  }

  /**
   * Unsubscribe from specific event types
   */
  unsubscribe(eventTypes) {
    if (this.isConnected()) {
      this.send({
        type: 'unsubscribe',
        event_types: Array.isArray(eventTypes) ? eventTypes : [eventTypes]
      });
    }
  }

  /**
   * Close WebSocket connection
   */
  disconnect() {
    this.isIntentionalClose = true;
    
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    
    this.stopPingInterval();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    
    this.updateStatus('disconnected');
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Get connection status
   */
  getStatus() {
    return this.connectionStatus;
  }

  /**
   * Update connection status and notify listeners
   */
  updateStatus(status) {
    const oldStatus = this.connectionStatus;
    this.connectionStatus = status;
    
    if (oldStatus !== status) {
      this.emit('status_change', { 
        status, 
        previousStatus: oldStatus,
        timestamp: new Date().toISOString()
      });
    }
  }

  /**
   * Add event listener
   * @param {string} eventType - Type of event to listen for
   * @param {Function} callback - Callback function
   */
  on(eventType, callback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = [];
    }
    this.listeners[eventType].push(callback);
    
    // Return unsubscribe function
    return () => this.off(eventType, callback);
  }

  /**
   * Remove event listener
   */
  off(eventType, callback) {
    if (this.listeners[eventType]) {
      this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback);
    }
  }

  /**
   * Emit event to listeners
   */
  emit(eventType, data) {
    if (this.listeners[eventType]) {
      this.listeners[eventType].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in ${eventType} listener:`, error);
        }
      });
    }
  }

  /**
   * Clear all event listeners
   */
  clearListeners() {
    this.listeners = {
      statistics_update: [],
      camera_event: [],
      alert: [],
      connection_status: [],
      error: [],
      status_change: []
    };
  }
}

// Create singleton instance
const wsService = new WebSocketService();

export default wsService;
