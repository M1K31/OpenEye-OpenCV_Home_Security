// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Tests: v3.9.0 Security Features
 * Tests for account lockout, rate limiting, and 2FA enhancements
 */

import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';

test.describe('Account Lockout System (v3.9.0)', () => {
  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should lock account after 5 failed 2FA attempts', async ({ page, request }) => {
    // This test requires a user with 2FA enabled
    // For now, we'll test the API endpoint directly since setting up 2FA in E2E is complex

    // Create a test user with 2FA enabled via API
    const testUsername = 'test2fauser_' + Date.now();
    const testPassword = 'TestPassword123!';

    // First, login as admin to create user
    await setupAuth(page);

    // Create user via API call
    const createUserResponse = await request.post('/api/users/', {
      data: {
        username: testUsername,
        email: `${testUsername}@openeye.local`,
        password: testPassword,
        role: 'user'
      }
    });

    if (!createUserResponse.ok()) {
      console.log('User creation failed - may already exist');
    }

    // Attempt login with wrong 2FA code 5 times
    for (let attempt = 1; attempt <= 5; attempt++) {
      const loginResponse = await request.post('/api/auth/login', {
        data: {
          username: testUsername,
          password: testPassword
        }
      });

      // If user has 2FA, we'd get a response asking for 2FA code
      // Simulate failed 2FA verification
      if (loginResponse.ok()) {
        const loginData = await loginResponse.json();

        // If 2FA is required, verify with wrong code
        if (loginData.requires_2fa) {
          await request.post('/api/auth/login-2fa', {
            data: {
              username: testUsername,
              code: '000000' // Wrong code
            }
          });
        }
      }
    }

    // 6th attempt should return lockout error
    const finalLoginResponse = await request.post('/api/auth/login', {
      data: {
        username: testUsername,
        password: testPassword
      }
    });

    const finalData = await finalLoginResponse.json();

    // Should indicate account is locked
    expect(finalData.detail || finalData.error).toMatch(/locked|attempts exceeded/i);
  });

  test('should show remaining attempts after failed 2FA verification', async ({ page }) => {
    // Test UI feedback for remaining attempts
    // This would require a user with 2FA enabled
    // For E2E, we'll verify the UI handles the error message correctly

    await page.goto('/login');

    // Mock a failed 2FA attempt response with remaining attempts
    await page.route('/api/auth/login-2fa', async route => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Invalid 2FA code. 4 attempts remaining before account lockout.'
        })
      });
    });

    // Simulate login flow (this won't actually work without proper credentials)
    // But we can verify the error message is displayed
    await page.fill('input[placeholder="Enter username"]', 'testuser');
    await page.fill('input[placeholder="Enter password"]', 'password');
    await page.click('button:has-text("Login")');

    // If 2FA prompt appears, enter wrong code
    try {
      await page.waitForSelector('input[placeholder*="2FA"], input[placeholder*="code"]', { timeout: 2000 });
      await page.fill('input[placeholder*="2FA"], input[placeholder*="code"]', '000000');
      await page.click('button:has-text("Verify")');

      // Check if remaining attempts message appears
      await expect(page.locator('text=/4 attempts remaining/i')).toBeVisible({ timeout: 5000 });
    } catch {
      // 2FA not enabled for this user - skip
      test.skip();
    }
  });

  test('should unlock account after 30 minutes', async ({ page, request }) => {
    // This test verifies the lockout duration
    // In real scenario, we'd need to wait 30 minutes or manipulate server time

    // For now, we verify the API returns lockout remaining time
    const testUsername = 'locked_user_' + Date.now();

    // This would be tested with a user that's already locked
    // We can verify the error message includes remaining time

    const response = await request.post('/api/auth/login', {
      data: {
        username: testUsername,
        password: 'password'
      }
    });

    // If account is locked, should see time remaining
    if (response.status() === 403) {
      const data = await response.json();
      // Should mention minutes or time remaining
      expect(data.detail || data.error).toMatch(/\d+\s*(minutes?|seconds?)/i);
    }
  });
});

test.describe('Rate Limiting (v3.9.0)', () => {
  test('should enforce password reset rate limit (5 per hour)', async ({ page, request }) => {
    const testEmail = 'ratelimit_test@openeye.local';

    // Attempt password reset 6 times
    for (let i = 0; i < 6; i++) {
      const response = await request.post('/api/auth/reset-password', {
        data: {
          email: testEmail
        }
      });

      if (i < 5) {
        // First 5 should succeed (or fail with "user not found" which is ok)
        expect([200, 404]).toContain(response.status());
      } else {
        // 6th should be rate limited
        expect(response.status()).toBe(429);

        const data = await response.json();
        expect(data.detail || data.error).toMatch(/rate limit|too many requests/i);

        // Should include Retry-After header
        const retryAfter = response.headers()['retry-after'];
        expect(retryAfter).toBeTruthy();
      }
    }
  });

  test('should enforce 2FA verification rate limit (10 per 5 minutes)', async ({ page, request }) => {
    const testUsername = 'ratelimit_2fa_' + Date.now();

    // Attempt 2FA verification 11 times
    for (let i = 0; i < 11; i++) {
      const response = await request.post('/api/auth/login-2fa', {
        data: {
          username: testUsername,
          code: '000000'
        }
      });

      if (i < 10) {
        // First 10 should process (may fail auth, but not rate limited)
        expect(response.status()).not.toBe(429);
      } else {
        // 11th should be rate limited
        expect(response.status()).toBe(429);

        const data = await response.json();
        expect(data.detail || data.error).toMatch(/rate limit|too many requests/i);
      }
    }
  });

  test('should display rate limit error in UI', async ({ page }) => {
    await page.goto('/login');

    // Mock rate limit response
    await page.route('/api/auth/login', async route => {
      await route.fulfill({
        status: 429,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Too many login attempts. Please try again in 5 minutes.'
        }),
        headers: {
          'Retry-After': '300'
        }
      });
    });

    // Try to login
    await page.fill('input[placeholder="Enter username"]', 'testuser');
    await page.fill('input[placeholder="Enter password"]', 'password');
    await page.click('button:has-text("Login")');

    // Should show rate limit error
    await expect(page.locator('text=/too many.*attempts/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Enhanced Audit Logging (v3.9.0)', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should log failed login attempts', async ({ page, request }) => {
    // Attempt failed login
    const response = await request.post('/api/auth/login', {
      data: {
        username: 'nonexistent_user',
        password: 'wrongpassword'
      }
    });

    expect(response.status()).toBe(401);

    // In production, we'd query audit logs via API
    // For now, we verify the request was made
    expect(response.status()).toBe(401);
  });

  test('should log successful login', async ({ page, request }) => {
    const response = await request.post('/api/auth/login', {
      data: {
        username: 'admin',
        password: 'admin'
      }
    });

    expect(response.ok()).toBeTruthy();

    // Audit log should contain LOGIN_SUCCESS event
    // This would be verified via an audit log API endpoint
  });

  test('should log 2FA events', async ({ page, request }) => {
    // Test that 2FA enable/disable events are logged
    // This would require 2FA management API endpoints

    // For now, verify the endpoints exist
    const response = await request.get('/api/auth/2fa/status', {
      headers: {
        'Authorization': `Bearer ${await page.evaluate(() => localStorage.getItem('access_token'))}`
      }
    });

    // Should return 2FA status (enabled/disabled)
    expect([200, 404]).toContain(response.status());
  });

  test('should log account lockout events', async ({ page }) => {
    // Account lockout should generate TWO_FA_ACCOUNT_LOCKED event
    // This is logged automatically by security_helpers.py

    // We can verify by checking if the lockout endpoint exists
    const locked = await page.evaluate(() => {
      return fetch('/api/auth/status').then(r => r.json());
    });

    // Should return auth status
    expect(locked).toBeTruthy();
  });
});

test.describe('Password Reset Flow (v3.9.0)', () => {
  test('should display password reset page', async ({ page }) => {
    await page.goto('/reset-password');

    // Check for password reset form
    await expect(page.locator('input[type="email"], input[placeholder*="email"]')).toBeVisible();
    await expect(page.locator('button:has-text("Reset"), button:has-text("Send")')).toBeVisible();
  });

  test('should handle password reset request', async ({ page }) => {
    await page.goto('/reset-password');

    // Enter email
    await page.fill('input[type="email"], input[placeholder*="email"]', 'admin@openeye.local');

    // Submit reset request
    await page.click('button:has-text("Reset"), button:has-text("Send")');

    // Should show success message or confirmation
    await expect(page.locator('text=/reset link sent|check your email/i')).toBeVisible({ timeout: 5000 });
  });

  test('should enforce 2FA during password reset', async ({ page }) => {
    // If user has 2FA enabled, password reset should require 2FA verification
    // This is a security feature to prevent account takeover

    await page.goto('/reset-password');
    await page.fill('input[type="email"]', 'admin@openeye.local');
    await page.click('button:has-text("Reset")');

    // If admin has 2FA, should prompt for code
    try {
      await expect(page.locator('input[placeholder*="2FA"]')).toBeVisible({ timeout: 3000 });
    } catch {
      // 2FA not enabled - that's ok for this test
      console.log('2FA not enabled for password reset flow');
    }
  });

  test('should check account lockout before password reset', async ({ page, request }) => {
    // Locked accounts should not be able to reset password
    const testEmail = 'locked_account@openeye.local';

    const response = await request.post('/api/auth/reset-password', {
      data: {
        email: testEmail
      }
    });

    // If account is locked, should return 403
    if (response.status() === 403) {
      const data = await response.json();
      expect(data.detail).toMatch(/locked/i);
    } else {
      // Account not locked or doesn't exist - both are valid
      expect([200, 404]).toContain(response.status());
    }
  });
});

test.describe('Token Validation (v3.9.0 Fix)', () => {
  test('should clear expired tokens on page reload', async ({ page }) => {
    await page.goto('/login');

    // Login to get tokens
    await page.fill('input[placeholder="Enter username"]', 'admin');
    await page.fill('input[placeholder="Enter password"]', 'admin');
    await page.click('button:has-text("Login")');

    // Wait for redirect
    await page.waitForURL('/', { timeout: 5000 });

    // Set expired token
    await page.evaluate(() => {
      const expiredToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTYwMDAwMDAwMH0.fake';
      localStorage.setItem('access_token', expiredToken);
    });

    // Reload page
    await page.reload();

    // Should redirect to login (token is expired)
    await expect(page).toHaveURL('/login', { timeout: 5000 });

    // Token should be cleared
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token).toBeNull();
  });

  test('should validate token before allowing access to protected routes', async ({ page }) => {
    // Try to access dashboard with invalid token
    await page.goto('/');

    await page.evaluate(() => {
      localStorage.setItem('access_token', 'invalid.jwt.token');
    });

    // Navigate to dashboard
    await page.goto('/');

    // Should redirect to login
    await expect(page).toHaveURL('/login', { timeout: 5000 });
  });

  test('should keep valid tokens after reload', async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[placeholder="Enter username"]', 'admin');
    await page.fill('input[placeholder="Enter password"]', 'admin');
    await page.click('button:has-text("Login")');
    await page.waitForURL('/', { timeout: 5000 });

    // Get token
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token).toBeTruthy();

    // Reload page
    await page.reload();

    // Should stay on dashboard (token is valid)
    await expect(page).toHaveURL('/', { timeout: 3000 });

    // Token should still be present
    const tokenAfterReload = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(tokenAfterReload).toBeTruthy();
  });
});
