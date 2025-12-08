/**
 * Date/Time utility functions
 * Handles timezone conversion for timestamps from backend
 */

/**
 * Parse a timestamp from the backend and convert to local time
 * Backend sends UTC timestamps, but may not include timezone info
 * 
 * @param {string|Date} timestamp - Timestamp from backend
 * @returns {Date} - Date object in local timezone
 */
export function parseBackendTimestamp(timestamp) {
  if (!timestamp) return null;
  
  // If already a Date object, return as-is
  // Note: If the Date was created incorrectly (without 'Z'), it's already wrong
  // but we can't fix it at this point. The caller should pass the original string.
  if (timestamp instanceof Date) {
    return timestamp;
  }
  
  // If it's a string, check for timezone info
  if (typeof timestamp === 'string') {
    // Trim whitespace
    timestamp = timestamp.trim();
    
    // Check if it's an ISO datetime string (format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SS.mmm)
    // Backend sends UTC timestamps without timezone info (timezone-naive)
    // JavaScript's Date() interprets these as local time, so we need to explicitly treat as UTC
    
    // Pattern: YYYY-MM-DDTHH:MM:SS (with optional microseconds/milliseconds)
    // Matches: "2025-12-08T00:07:15" or "2025-12-08T00:07:15.329667"
    // More flexible pattern to handle various ISO formats
    const isoPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/;
    
    if (isoPattern.test(timestamp)) {
      // It's an ISO datetime without timezone - backend sends UTC, so append 'Z'
      // This ensures JavaScript interprets it as UTC, not local time
      try {
        const utcDate = new Date(timestamp + 'Z');
        if (isNaN(utcDate.getTime())) {
          // If parsing with Z fails, try without (fallback)
          console.warn('Failed to parse UTC timestamp with Z, trying without:', timestamp);
          return new Date(timestamp);
        }
        return utcDate;
      } catch (e) {
        console.warn('Error parsing timestamp:', timestamp, e);
        // Fallback: try parsing without Z
        return new Date(timestamp);
      }
    }
    
    // Check if it already has timezone info (Z, +HH:MM, or -HH:MM)
    if (timestamp.includes('Z') || timestamp.match(/[+-]\d{2}:\d{2}$/)) {
      // Has timezone info - parse normally
      return new Date(timestamp);
    }
    
    // Other string format - try parsing, but if it looks like ISO without timezone, add Z
    // This is a catch-all for ISO-like formats that didn't match the strict pattern
    if (timestamp.includes('T') && !timestamp.includes('Z') && !timestamp.match(/[+-]\d{2}:\d{2}$/)) {
      // Looks like ISO format without timezone - assume UTC
      // Try appending Z and parsing
      const utcDate = new Date(timestamp + 'Z');
      if (!isNaN(utcDate.getTime())) {
        return utcDate;
      }
      // If that fails, try parsing without Z (fallback)
      return new Date(timestamp);
    }
    
    // If it's just a date string without time (YYYY-MM-DD), parse as UTC midnight
    const dateOnlyPattern = /^\d{4}-\d{2}-\d{2}$/;
    if (dateOnlyPattern.test(timestamp)) {
      return new Date(timestamp + 'T00:00:00Z');
    }
  }
  
  // Number (Unix timestamp in seconds or milliseconds) - parse normally
  if (typeof timestamp === 'number') {
    // If it's a Unix timestamp in seconds (less than year 2000 in milliseconds), convert to milliseconds
    if (timestamp < 946684800000) { // Year 2000 in milliseconds
      return new Date(timestamp * 1000);
    }
    return new Date(timestamp);
  }
  
  // Try parsing as-is (fallback)
  const parsed = new Date(timestamp);
  if (!isNaN(parsed.getTime())) {
    return parsed;
  }
  
  // If all else fails, return null
  console.warn('Failed to parse timestamp:', timestamp);
  return null;
}

/**
 * Format a timestamp for display in the UI
 * 
 * @param {string|Date} timestamp - Timestamp from backend
 * @param {Object} options - Formatting options (same as toLocaleString)
 * @returns {string} - Formatted date string
 */
export function formatTimestamp(timestamp, options = {}) {
  const date = parseBackendTimestamp(timestamp);
  if (!date || isNaN(date.getTime())) {
    return 'Invalid date';
  }
  
  const defaultOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  };
  
  return date.toLocaleString('en-US', { ...defaultOptions, ...options });
}

/**
 * Format a timestamp as a short date string (e.g., "12/7/2025, 6:50:00 PM")
 * 
 * @param {string|Date} timestamp - Timestamp from backend
 * @returns {string} - Formatted date string
 */
export function formatTimestampShort(timestamp) {
  return formatTimestamp(timestamp);
}

/**
 * Format a timestamp as a long date string with timezone
 * 
 * @param {string|Date} timestamp - Timestamp from backend
 * @returns {string} - Formatted date string with timezone
 */
export function formatTimestampLong(timestamp) {
  return formatTimestamp(timestamp, {
    timeZoneName: 'short'
  });
}

