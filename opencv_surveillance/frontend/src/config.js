// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Centralized Frontend Configuration
 *
 * All configurable constants and settings for the OpenEye frontend.
 * This module provides a single source of truth for:
 * - API configuration and timeouts
 * - Retry logic and exponential backoff
 * - WebSocket settings
 * - UI/UX constants
 * - Feature flags
 *
 * Usage:
 *   import { API_TIMEOUT, RETRY_CONFIG, WS_PING_INTERVAL } from './config';
 *
 * Environment Variables:
 *   Settings can be overridden using Vite environment variables.
 *   Use VITE_ prefix for custom variables (e.g., VITE_API_TIMEOUT)
 */

// ============================================================================
// API CONFIGURATION
// ============================================================================

/**
 * API Client Settings
 */
export const API_CONFIG = {
  // Base URL - automatically uses relative URL in production
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',

  // Timeout for API requests (milliseconds)
  // Longer timeout for operations like camera discovery
  timeout: parseInt(import.meta.env.VITE_API_TIMEOUT) || 90000, // 90 seconds

  // Headers
  defaultHeaders: {
    'Content-Type': 'application/json',
  },

  // Request size limits
  maxRequestSize: parseInt(import.meta.env.VITE_MAX_REQUEST_SIZE) || 100 * 1024 * 1024, // 100MB
  maxUploadFiles: parseInt(import.meta.env.VITE_MAX_UPLOAD_FILES) || 50,
};

/**
 * API Retry Configuration
 * Implements exponential backoff with jitter
 */
export const RETRY_CONFIG = {
  // Maximum number of retry attempts
  maxRetries: parseInt(import.meta.env.VITE_RETRY_MAX_RETRIES) || 3,

  // Initial delay before first retry (milliseconds)
  initialDelay: parseInt(import.meta.env.VITE_RETRY_INITIAL_DELAY) || 1000, // 1 second

  // Maximum delay between retries (milliseconds)
  maxDelay: parseInt(import.meta.env.VITE_RETRY_MAX_DELAY) || 10000, // 10 seconds

  // Exponential backoff multiplier
  backoffMultiplier: parseFloat(import.meta.env.VITE_RETRY_BACKOFF_MULTIPLIER) || 2,

  // Jitter percentage (0-1) to prevent thundering herd
  jitterPercent: parseFloat(import.meta.env.VITE_RETRY_JITTER_PERCENT) || 0.25, // 25%

  // HTTP status codes that should trigger retry
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],

  // HTTP methods that are safe to retry
  retryableMethods: ['GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'],
};

/**
 * Public API Endpoints (no auth required)
 */
export const PUBLIC_ENDPOINTS = [
  '/token',
  '/token/refresh',
  '/token/revoke',
  '/token/revoke-all',
  '/setup/status',
  '/setup/initialize',
];

// ============================================================================
// WEBSOCKET CONFIGURATION
// ============================================================================

/**
 * WebSocket Settings
 */
export const WEBSOCKET_CONFIG = {
  // WebSocket URL - automatically determined from window.location
  url: import.meta.env.VITE_WS_URL || null, // null = auto-detect

  // Ping interval to keep connection alive (milliseconds)
  pingInterval: parseInt(import.meta.env.VITE_WS_PING_INTERVAL) || 30000, // 30 seconds

  // Ping timeout before considering connection dead (milliseconds)
  pingTimeout: parseInt(import.meta.env.VITE_WS_PING_TIMEOUT) || 10000, // 10 seconds

  // Reconnection settings
  reconnect: {
    enabled: import.meta.env.VITE_WS_RECONNECT_ENABLED !== 'false',
    maxAttempts: parseInt(import.meta.env.VITE_WS_RECONNECT_MAX_ATTEMPTS) || 10,
    initialDelay: parseInt(import.meta.env.VITE_WS_RECONNECT_INITIAL_DELAY) || 1000, // 1 second
    maxDelay: parseInt(import.meta.env.VITE_WS_RECONNECT_MAX_DELAY) || 30000, // 30 seconds
    backoffMultiplier: parseFloat(import.meta.env.VITE_WS_RECONNECT_BACKOFF) || 1.5,
  },

  // Message queue settings
  messageQueue: {
    maxSize: parseInt(import.meta.env.VITE_WS_QUEUE_SIZE) || 100,
    processInterval: parseInt(import.meta.env.VITE_WS_PROCESS_INTERVAL) || 100, // milliseconds
  },
};

// ============================================================================
// UI/UX CONSTANTS
// ============================================================================

/**
 * Design System Constants
 */
export const DESIGN_SYSTEM = {
  // Grid system (8pt grid)
  gridUnit: 8, // All spacing should be multiples of 8px

  // Touch targets (Apple HIG)
  minTouchTarget: 44, // Minimum touch target size (44x44px)

  // Breakpoints (responsive design)
  breakpoints: {
    mobile: 320,
    tablet: 768,
    desktop: 1024,
    wide: 1440,
  },

  // Animation timing
  animationDuration: {
    fast: 150, // milliseconds
    normal: 300,
    slow: 500,
  },

  // Z-index layers
  zIndex: {
    dropdown: 1000,
    sticky: 1020,
    modal: 1030,
    overlay: 1040,
    tooltip: 1050,
  },
};

/**
 * Pagination Defaults
 */
export const PAGINATION = {
  defaultPageSize: parseInt(import.meta.env.VITE_PAGE_SIZE) || 50,
  pageSizeOptions: [10, 25, 50, 100, 250],
  maxPageSize: parseInt(import.meta.env.VITE_MAX_PAGE_SIZE) || 1000,
};

/**
 * Data Refresh Intervals (milliseconds)
 */
export const REFRESH_INTERVALS = {
  statistics: 10000, // 10 seconds - general statistics
  cameraStatus: 5000, // 5 seconds - camera status updates
  liveStream: 2000, // 2 seconds - live stream stats via WebSocket
  detectionHistory: 30000, // 30 seconds - detection history
  alerts: 15000, // 15 seconds - alert notifications
};

/**
 * Toast/Notification Settings
 */
export const NOTIFICATION_CONFIG = {
  // Auto-dismiss durations (milliseconds)
  duration: {
    success: 3000, // 3 seconds
    info: 5000, // 5 seconds
    warning: 7000, // 7 seconds
    error: 10000, // 10 seconds
  },

  // Maximum number of simultaneous notifications
  maxVisible: 3,

  // Position
  position: import.meta.env.VITE_NOTIFICATION_POSITION || 'top-right',
};

/**
 * Video Player Settings
 */
export const VIDEO_PLAYER = {
  // Playback controls
  seekStep: 5, // seconds - keyboard seek step
  volumeStep: 0.1, // 10% volume change per step

  // Buffer settings
  preloadTime: 30, // seconds - how much to preload
  bufferSize: 10, // seconds - buffer size for smooth playback

  // Quality settings
  defaultQuality: 'auto', // 'auto', 'high', 'medium', 'low'
  adaptiveStreaming: true,
};

// ============================================================================
// CAMERA & STREAMING
// ============================================================================

/**
 * Camera Configuration
 */
export const CAMERA_CONFIG = {
  // Snapshot refresh interval (milliseconds)
  snapshotRefresh: 1000, // 1 second

  // Stream reconnection timeout (milliseconds)
  streamReconnectTimeout: 5000, // 5 seconds

  // Maximum reconnection attempts
  maxReconnectAttempts: 3,

  // Default camera types
  supportedTypes: ['rtsp', 'usb', 'mock', 'onvif'],

  // Default resolutions
  defaultResolutions: [
    { label: '4K (3840x2160)', width: 3840, height: 2160 },
    { label: '1080p (1920x1080)', width: 1920, height: 1080 },
    { label: '720p (1280x720)', width: 1280, height: 720 },
    { label: '480p (854x480)', width: 854, height: 480 },
  ],

  // Default FPS options
  fpsOptions: [5, 10, 15, 20, 25, 30],
};

// ============================================================================
// FACE RECOGNITION & DETECTION
// ============================================================================

/**
 * Face Recognition Settings
 */
export const FACE_RECOGNITION = {
  // Confidence threshold for face matches (0-1)
  confidenceThreshold: parseFloat(import.meta.env.VITE_FACE_CONFIDENCE_THRESHOLD) || 0.6,

  // Maximum file size for face uploads (bytes)
  maxFileSize: parseInt(import.meta.env.VITE_FACE_MAX_FILE_SIZE) || 5 * 1024 * 1024, // 5MB

  // Allowed file types
  allowedTypes: ['image/jpeg', 'image/jpg', 'image/png'],

  // Minimum image dimensions (pixels)
  minDimensions: {
    width: 80,
    height: 80,
  },

  // Face thumbnail size (pixels)
  thumbnailSize: 150,
};

/**
 * Face Clustering Settings
 */
export const CLUSTERING = {
  // Minimum faces required to trigger clustering
  minThreshold: parseInt(import.meta.env.VITE_CLUSTERING_MIN_THRESHOLD) || 10,

  // Clustering algorithm parameters
  dbscanEps: parseFloat(import.meta.env.VITE_CLUSTERING_EPS) || 0.5,
  dbscanMinSamples: parseInt(import.meta.env.VITE_CLUSTERING_MIN_SAMPLES) || 3,

  // Auto-refresh interval (milliseconds)
  refreshInterval: 60000, // 1 minute
};

// ============================================================================
// FEATURE FLAGS
// ============================================================================

/**
 * Feature Toggles
 * Control feature availability in the UI
 */
export const FEATURES = {
  // Core features
  faceRecognition: import.meta.env.VITE_FEATURE_FACE_RECOGNITION !== 'false',
  motionDetection: import.meta.env.VITE_FEATURE_MOTION_DETECTION !== 'false',
  recording: import.meta.env.VITE_FEATURE_RECORDING !== 'false',

  // Advanced features
  faceClustering: import.meta.env.VITE_FEATURE_FACE_CLUSTERING !== 'false',
  twoFactorAuth: import.meta.env.VITE_FEATURE_TWO_FACTOR_AUTH !== 'false',
  automations: import.meta.env.VITE_FEATURE_AUTOMATIONS !== 'false',
  twoWayAudio: import.meta.env.VITE_FEATURE_TWO_WAY_AUDIO !== 'false',

  // Experimental features
  objectDetection: import.meta.env.VITE_FEATURE_OBJECT_DETECTION === 'true',
  licensePlateRecognition: import.meta.env.VITE_FEATURE_LICENSE_PLATE === 'true',
  cloudStorage: import.meta.env.VITE_FEATURE_CLOUD_STORAGE === 'true',

  // Performance features
  hardwareAcceleration: import.meta.env.VITE_FEATURE_HW_ACCELERATION === 'true',
  performanceMonitoring: import.meta.env.VITE_FEATURE_PERFORMANCE_MONITORING !== 'false',
};

// ============================================================================
// DEVELOPMENT & DEBUG
// ============================================================================

/**
 * Development Settings
 */
export const DEV = {
  // Environment detection
  isDevelopment: import.meta.env.MODE === 'development' || import.meta.env.DEV === true,
  isProduction: import.meta.env.PROD === true,
  isTesting: import.meta.env.MODE === 'test',

  // Debug logging
  enableDebugLogging: import.meta.env.VITE_DEBUG_LOGGING === 'true',
  logLevel: import.meta.env.VITE_LOG_LEVEL || 'info', // 'debug', 'info', 'warn', 'error'

  // Mock data for development
  useMockData: import.meta.env.VITE_USE_MOCK_DATA === 'true',

  // Performance monitoring
  enablePerformanceMonitoring: import.meta.env.VITE_PERFORMANCE_MONITORING === 'true',
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Check if running in development mode
 * @returns {boolean} True if in development mode
 * @example
 * if (isDevelopment()) {
 *   console.log('Running in development');
 * }
 */
export const isDevelopment = () => DEV.isDevelopment;

/**
 * Check if running in production mode
 * @returns {boolean} True if in production mode
 * @example
 * if (isProduction()) {
 *   // Disable verbose logging
 * }
 */
export const isProduction = () => DEV.isProduction;

/**
 * Check if a feature is enabled
 * @param {string} featureName - Name of the feature to check
 * @returns {boolean} True if feature is enabled
 * @example
 * if (isFeatureEnabled('faceRecognition')) {
 *   // Show face recognition UI
 * }
 */
export const isFeatureEnabled = (featureName) => {
  return FEATURES[featureName] === true;
};

/**
 * Get configuration summary for debugging
 * @returns {Object} Configuration summary object
 * @property {string} environment - Current environment (development/production/test)
 * @property {string} apiBaseURL - API base URL
 * @property {number} apiTimeout - API request timeout in milliseconds
 * @property {number} retryMaxRetries - Maximum retry attempts
 * @property {boolean} wsReconnectEnabled - WebSocket reconnection enabled
 * @property {string[]} features - List of enabled features
 * @property {string} breakpoint - Current responsive breakpoint
 * @example
 * console.log('Config:', getConfigSummary());
 * // Output: { environment: 'development', apiBaseURL: '/api', ... }
 */
export const getConfigSummary = () => ({
  environment: import.meta.env.MODE,
  apiBaseURL: API_CONFIG.baseURL,
  apiTimeout: API_CONFIG.timeout,
  retryMaxRetries: RETRY_CONFIG.maxRetries,
  wsReconnectEnabled: WEBSOCKET_CONFIG.reconnect.enabled,
  features: Object.keys(FEATURES).filter(key => FEATURES[key] === true),
  breakpoint: getCurrentBreakpoint(),
});

/**
 * Get current responsive breakpoint
 * @returns {string} Current breakpoint: 'mobile' | 'tablet' | 'desktop' | 'wide'
 * @example
 * const breakpoint = getCurrentBreakpoint();
 * if (breakpoint === 'mobile') {
 *   // Show mobile layout
 * }
 */
export const getCurrentBreakpoint = () => {
  const width = window.innerWidth;
  if (width < DESIGN_SYSTEM.breakpoints.tablet) return 'mobile';
  if (width < DESIGN_SYSTEM.breakpoints.desktop) return 'tablet';
  if (width < DESIGN_SYSTEM.breakpoints.wide) return 'desktop';
  return 'wide';
};

/**
 * Calculate spacing based on grid unit (8px grid system)
 * @param {number} multiplier - Grid unit multiplier
 * @returns {string} CSS spacing value (e.g., "16px" for multiplier 2)
 * @example
 * // 8pt grid system
 * <div style={{ margin: spacing(2) }}>  // "16px"
 * <div style={{ padding: spacing(3) }}> // "24px"
 */
export const spacing = (multiplier) => {
  return `${DESIGN_SYSTEM.gridUnit * multiplier}px`;
};

// Default export with all config
export default {
  API_CONFIG,
  RETRY_CONFIG,
  PUBLIC_ENDPOINTS,
  WEBSOCKET_CONFIG,
  DESIGN_SYSTEM,
  PAGINATION,
  REFRESH_INTERVALS,
  NOTIFICATION_CONFIG,
  VIDEO_PLAYER,
  CAMERA_CONFIG,
  FACE_RECOGNITION,
  CLUSTERING,
  FEATURES,
  DEV,
  // Helper functions
  isDevelopment,
  isProduction,
  isFeatureEnabled,
  getConfigSummary,
  getCurrentBreakpoint,
  spacing,
};
