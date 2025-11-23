// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Environment-Aware Logger Utility
 *
 * Provides console logging with automatic suppression in production builds.
 * Only errors are logged in production to prevent log clutter and
 * potential information leakage.
 *
 * Usage:
 *   import { logger } from '../utils/logger';
 *   logger.log('Debug message');          // Only in development
 *   logger.error('Error occurred', err);  // Always logged
 *   logger.warn('Warning message');       // Only in development
 *   logger.debug('Debug details');        // Only in development
 *
 * Features:
 * - Automatic detection of development vs production environment
 * - Errors always logged for debugging production issues
 * - Preserves console.log API (multiple arguments, objects, etc.)
 * - Zero performance overhead in production (functions become no-ops)
 */

// Detect environment - Vite uses import.meta.env.MODE
const isDevelopment = import.meta.env.MODE === 'development' ||
                      import.meta.env.DEV === true ||
                      !import.meta.env.PROD;

// Optional: Enable debug logging even in production via localStorage
const forceDebugLogging = () => {
  try {
    return localStorage.getItem('ENABLE_DEBUG_LOGGING') === 'true';
  } catch {
    return false;
  }
};

/**
 * Logger class with environment-aware methods
 */
class Logger {
  constructor() {
    this.isDevelopment = isDevelopment;
    this.forceDebug = forceDebugLogging();
  }

  /**
   * Log informational messages
   * Suppressed in production unless forceDebug is enabled
   */
  log(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.log(...args);
    }
  }

  /**
   * Log error messages
   * ALWAYS logged, even in production
   */
  error(...args) {
    console.error(...args);
  }

  /**
   * Log warning messages
   * Suppressed in production unless forceDebug is enabled
   */
  warn(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.warn(...args);
    }
  }

  /**
   * Log debug messages
   * Suppressed in production unless forceDebug is enabled
   */
  debug(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.debug(...args);
    }
  }

  /**
   * Log informational messages with 'info' prefix
   * Suppressed in production unless forceDebug is enabled
   */
  info(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.info(...args);
    }
  }

  /**
   * Group related log messages
   * Suppressed in production unless forceDebug is enabled
   */
  group(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.group(...args);
    }
  }

  /**
   * End grouped log messages
   */
  groupEnd() {
    if (this.isDevelopment || this.forceDebug) {
      console.groupEnd();
    }
  }

  /**
   * Log a table (useful for arrays of objects)
   * Suppressed in production unless forceDebug is enabled
   */
  table(...args) {
    if (this.isDevelopment || this.forceDebug) {
      console.table(...args);
    }
  }

  /**
   * Start a timer for performance measurement
   * Suppressed in production unless forceDebug is enabled
   */
  time(label) {
    if (this.isDevelopment || this.forceDebug) {
      console.time(label);
    }
  }

  /**
   * End a timer and log the elapsed time
   * Suppressed in production unless forceDebug is enabled
   */
  timeEnd(label) {
    if (this.isDevelopment || this.forceDebug) {
      console.timeEnd(label);
    }
  }

  /**
   * Enable debug logging in production
   * Run in browser console: logger.enableProductionDebugging()
   */
  enableProductionDebugging() {
    try {
      localStorage.setItem('ENABLE_DEBUG_LOGGING', 'true');
      this.forceDebug = true;
      console.log('✅ Production debug logging enabled. Reload page to take effect.');
    } catch (error) {
      console.error('Failed to enable debug logging:', error);
    }
  }

  /**
   * Disable debug logging in production
   */
  disableProductionDebugging() {
    try {
      localStorage.removeItem('ENABLE_DEBUG_LOGGING');
      this.forceDebug = false;
      console.log('✅ Production debug logging disabled.');
    } catch (error) {
      console.error('Failed to disable debug logging:', error);
    }
  }
}

// Create and export singleton instance
export const logger = new Logger();

// Also export as default for convenience
export default logger;

/**
 * Production Debug Instructions:
 *
 * To enable debug logging in production:
 * 1. Open browser console
 * 2. Run: logger.enableProductionDebugging()
 * 3. Reload the page
 * 4. To disable: logger.disableProductionDebugging()
 */
