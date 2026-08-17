/**
 * Date/Time utility functions
 *
 * The one thing that matters here: a timestamp from this backend that carries no
 * timezone is LOCAL time, not UTC.
 *
 * This file previously assumed the opposite and appended 'Z' to every naive
 * timestamp. The event tables are written with datetime.now(), which is local,
 * so every dashboard time was shifted by the machine's UTC offset — an event at
 * 6:53 PM displayed as 2:53 PM in US Eastern. The events page, which does not
 * use this module, showed the same event correctly, and the disagreement between
 * two pages is what made it visible at all.
 *
 * Worth knowing: the convention is not consistent in the backend either. Eleven
 * writers use datetime.now() (local) while thirty-seven model defaults use
 * datetime.utcnow(). The columns shown on the dashboard are all explicitly
 * written, so they are local; a column that falls back to its model default is
 * UTC and would be four hours out in the other direction. Normalising the
 * backend on UTC is the real fix and needs a data migration, so it is recorded
 * separately rather than attempted here.
 */

/**
 * Parse a timestamp from the backend into a Date.
 *
 * A string carrying explicit timezone information is honoured. A naive string is
 * treated as local time, which is what the backend writes.
 *
 * @param {string|Date|number} timestamp
 * @returns {Date|null}
 */
export function parseBackendTimestamp(timestamp) {
  if (!timestamp) return null;

  if (timestamp instanceof Date) {
    return timestamp;
  }

  if (typeof timestamp === 'number') {
    // Seconds vs milliseconds: anything below the year 2000 expressed in
    // milliseconds must have been intended as seconds.
    return new Date(timestamp < 946684800000 ? timestamp * 1000 : timestamp);
  }

  if (typeof timestamp === 'string') {
    const value = timestamp.trim();

    // Explicit timezone — trust it.
    if (value.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(value)) {
      return new Date(value);
    }

    // Date only: local midnight, so "today" means today here.
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
      return new Date(`${value}T00:00:00`);
    }

    // Naive datetime. JavaScript parses "YYYY-MM-DDTHH:MM:SS" as local, which
    // is exactly right, so it is passed through untouched. A space separator
    // (SQLite's default rendering) is normalised to 'T' because Safari rejects
    // the space form.
    const normalised = value.replace(' ', 'T');
    const parsed = new Date(normalised);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
  }

  const fallback = new Date(timestamp);
  if (!isNaN(fallback.getTime())) {
    return fallback;
  }

  console.warn('Failed to parse timestamp:', timestamp);
  return null;
}

/**
 * Format a timestamp for display.
 *
 * @param {string|Date} timestamp
 * @param {Object} options - passed through to toLocaleString
 * @returns {string}
 */
export function formatTimestamp(timestamp, options = {}) {
  const date = parseBackendTimestamp(timestamp);
  if (!date || isNaN(date.getTime())) {
    return 'Invalid date';
  }

  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
    ...options,
  });
}

/** Short form, e.g. "08/17/2026, 06:53:07 PM". */
export function formatTimestampShort(timestamp) {
  return formatTimestamp(timestamp);
}

/** Long form, including the timezone name. */
export function formatTimestampLong(timestamp) {
  return formatTimestamp(timestamp, { timeZoneName: 'short' });
}
