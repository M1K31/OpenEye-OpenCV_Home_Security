/**
 * Tests for backend timestamp parsing.
 *
 * The defect these exist for: a naive timestamp from this backend is LOCAL, and
 * treating it as UTC shifted every dashboard time by the machine's offset. An
 * event at 6:53 PM displayed as 2:53 PM in US Eastern, while the events page —
 * which does not use this module — showed it correctly. Two pages disagreeing
 * about the same event is what made it visible.
 */

import { describe, it, expect } from 'vitest';
import {
  parseBackendTimestamp,
  formatTimestamp,
} from '../dateUtils';

describe('parseBackendTimestamp', () => {
  it('treats a naive timestamp as local, not UTC', () => {
    // The exact shape SQLAlchemy hands back for a datetime.now() column.
    const parsed = parseBackendTimestamp('2026-08-17T18:53:07.760699');

    expect(parsed.getHours()).toBe(18);
    expect(parsed.getMinutes()).toBe(53);
  });

  it('accepts the space separator SQLite renders', () => {
    // Safari rejects "YYYY-MM-DD HH:MM:SS" outright, so this must be normalised
    // rather than passed through.
    const parsed = parseBackendTimestamp('2026-08-17 18:53:07');

    expect(parsed).not.toBeNull();
    expect(isNaN(parsed.getTime())).toBe(false);
    expect(parsed.getHours()).toBe(18);
  });

  it('honours an explicit Z as UTC', () => {
    const parsed = parseBackendTimestamp('2026-08-17T18:53:07Z');

    expect(parsed.getUTCHours()).toBe(18);
  });

  it('honours an explicit offset', () => {
    const parsed = parseBackendTimestamp('2026-08-17T18:53:07+02:00');

    expect(parsed.getUTCHours()).toBe(16);
  });

  it('reads a date-only string as local midnight', () => {
    const parsed = parseBackendTimestamp('2026-08-17');

    expect(parsed.getHours()).toBe(0);
    expect(parsed.getDate()).toBe(17);
  });

  it('passes a Date through unchanged', () => {
    const now = new Date();
    expect(parseBackendTimestamp(now)).toBe(now);
  });

  it('reads a seconds-based unix timestamp', () => {
    const parsed = parseBackendTimestamp(1755455587);
    expect(parsed.getFullYear()).toBeGreaterThan(2000);
  });

  it('returns null for nothing', () => {
    expect(parseBackendTimestamp(null)).toBeNull();
    expect(parseBackendTimestamp('')).toBeNull();
    expect(parseBackendTimestamp(undefined)).toBeNull();
  });
});

describe('formatTimestamp', () => {
  it('shows the hour the backend recorded', () => {
    const text = formatTimestamp('2026-08-17T18:53:07.760699');

    expect(text).toContain('06:53:07 PM');
    expect(text).toContain('08/17/2026');
  });

  it('does not silently render garbage as a date', () => {
    expect(formatTimestamp('not a date')).toBe('Invalid date');
  });
});
