import { describe, it, expect, beforeEach, vi } from 'vitest';
import authService from '../authService';

describe('authService', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('getToken', () => {
    it('returns null when no token is stored', () => {
      const token = authService.getToken();
      expect(token).toBeNull();
    });

    it('returns token when one is stored', () => {
      localStorage.setItem('access_token', 'test-token-123');
      const token = authService.getToken();
      expect(token).toBe('test-token-123');
    });
  });

  describe('setToken', () => {
    it('stores token in localStorage', () => {
      authService.setToken('new-token-456');
      expect(localStorage.getItem('access_token')).toBe('new-token-456');
    });

    it('overwrites existing token', () => {
      localStorage.setItem('access_token', 'old-token');
      authService.setToken('new-token');
      expect(localStorage.getItem('access_token')).toBe('new-token');
    });
  });

  describe('logout', () => {
    it('removes token from localStorage', () => {
      localStorage.setItem('access_token', 'test-token');
      authService.logout();
      expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('handles logout when no token exists', () => {
      expect(() => authService.logout()).not.toThrow();
      expect(localStorage.getItem('access_token')).toBeNull();
    });
  });

  describe('isAuthenticated', () => {
    it('returns false when no token exists', () => {
      const isAuth = authService.isAuthenticated();
      expect(isAuth).toBe(false);
    });

    it('returns true when a valid unexpired token exists', () => {
      // Must be a real JWT. The previous version stored the string
      // 'test-token', which cannot be decoded, so isTokenExpired() correctly
      // treated it as expired and this returned false. The test was asserting
      // that any non-empty string counts as authenticated — the implementation
      // was right to disagree.
      const payload = { sub: 'alice', exp: Math.floor(Date.now() / 1000) + 3600 };
      const encode = (obj) => btoa(JSON.stringify(obj)).replace(/=+$/, '');
      const validToken = `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.sig`;

      localStorage.setItem('access_token', validToken);
      expect(authService.isAuthenticated()).toBe(true);
    });

    it('returns false for a token that cannot be decoded', () => {
      localStorage.setItem('access_token', 'not-a-jwt');
      expect(authService.isAuthenticated()).toBe(false);
    });

    it('returns false for an expired token', () => {
      const payload = { sub: 'alice', exp: Math.floor(Date.now() / 1000) - 60 };
      const encode = (obj) => btoa(JSON.stringify(obj)).replace(/=+$/, '');
      localStorage.setItem(
        'access_token',
        `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.sig`,
      );
      expect(authService.isAuthenticated()).toBe(false);
    });
  });
});
