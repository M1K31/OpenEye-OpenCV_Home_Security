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
      localStorage.setItem('token', 'test-token-123');
      const token = authService.getToken();
      expect(token).toBe('test-token-123');
    });
  });

  describe('setToken', () => {
    it('stores token in localStorage', () => {
      authService.setToken('new-token-456');
      expect(localStorage.getItem('token')).toBe('new-token-456');
    });

    it('overwrites existing token', () => {
      localStorage.setItem('token', 'old-token');
      authService.setToken('new-token');
      expect(localStorage.getItem('token')).toBe('new-token');
    });
  });

  describe('logout', () => {
    it('removes token from localStorage', () => {
      localStorage.setItem('token', 'test-token');
      authService.logout();
      expect(localStorage.getItem('token')).toBeNull();
    });

    it('handles logout when no token exists', () => {
      expect(() => authService.logout()).not.toThrow();
      expect(localStorage.getItem('token')).toBeNull();
    });
  });

  describe('isAuthenticated', () => {
    it('returns false when no token exists', () => {
      const isAuth = authService.isAuthenticated();
      expect(isAuth).toBe(false);
    });

    it('returns true when token exists', () => {
      localStorage.setItem('token', 'test-token');
      const isAuth = authService.isAuthenticated();
      expect(isAuth).toBe(true);
    });
  });
});
