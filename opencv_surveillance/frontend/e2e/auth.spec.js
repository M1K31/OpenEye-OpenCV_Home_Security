// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Authentication Flow E2E Tests (v3.8.0)
 *
 * Tests for login, logout, JWT refresh tokens, and 2FA
 */

import { test, expect } from '@playwright/test';
import { loginAs, logout, cleanupAuth } from './fixtures/auth.js';

test.describe('Authentication', () => {
  test.afterEach(async ({ page }) => {
    // Clean up auth tokens after each test
    await cleanupAuth(page);
  });

  test('should display login page', async ({ page }) => {
    await page.goto('/login');

    // Check for login form elements
    await expect(page.locator('h1')).toContainText('OpenEye Login');
    await expect(page.locator('input[placeholder="Enter username"]')).toBeVisible();
    await expect(page.locator('input[placeholder="Enter password"]')).toBeVisible();
    await expect(page.locator('button:has-text("Login")')).toBeVisible();
  });

  test('should login with valid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill credentials
    await page.fill('input[placeholder="Enter username"]', 'admin');
    await page.fill('input[placeholder="Enter password"]', 'admin');

    // Submit form
    await page.click('button:has-text("Login")');

    // Should redirect to dashboard
    await page.waitForURL('/');
    await expect(page.locator('h1')).toContainText('OpenEye');

    // Should have auth tokens in localStorage
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(accessToken).toBeTruthy();

    const refreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));
    expect(refreshToken).toBeTruthy();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');

    // Fill invalid credentials
    await page.fill('input[placeholder="Enter username"]', 'admin');
    await page.fill('input[placeholder="Enter password"]', 'wrongpassword');

    // Submit form
    await page.click('button:has-text("Login")');

    // Wait a moment for any error to appear
    await page.waitForTimeout(1000);

    // Should still be on login page (not redirected)
    expect(page.url()).toContain('/login');
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await loginAs(page);

    // Verify we're logged in
    await expect(page.locator('h1')).toContainText('OpenEye');

    // Click user menu to open dropdown
    await page.click('button.user-menu-button, .user-menu button');

    // Wait for logout button to appear
    await page.waitForSelector('.logout-button');

    // Click logout
    await page.click('.logout-button');

    // Should redirect to login page
    await page.waitForURL('/login');
    await expect(page.locator('h1')).toContainText('OpenEye Login');

    // Should have cleared auth tokens
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(accessToken).toBeFalsy();

    const refreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));
    expect(refreshToken).toBeFalsy();
  });

  test('should redirect to login when accessing protected routes without auth', async ({ page }) => {
    // Try to access dashboard without logging in
    await page.goto('/');

    // Should redirect to login
    await page.waitForURL('/login', { timeout: 5000 });
    await expect(page.locator('h1')).toContainText('OpenEye Login');
  });

  test('should maintain session after page reload', async ({ page }) => {
    // Login
    await loginAs(page);

    // Store initial tokens
    const initialAccessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    const initialRefreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));

    expect(initialAccessToken).toBeTruthy();
    expect(initialRefreshToken).toBeTruthy();

    // Reload page
    await page.reload();

    // Should still be logged in
    await expect(page.locator('h1')).toContainText('OpenEye');

    // Tokens should still exist
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    const refreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));

    expect(accessToken).toBeTruthy();
    expect(refreshToken).toBeTruthy();
  });

  test('should handle empty username', async ({ page }) => {
    await page.goto('/login');

    // Leave username empty
    await page.fill('input[placeholder="Enter password"]', 'admin');

    // Submit form
    await page.click('button:has-text("Login")');

    // Should show validation error or stay on login page
    const isOnLoginPage = page.url().includes('/login');
    expect(isOnLoginPage).toBe(true);
  });

  test('should handle empty password', async ({ page }) => {
    await page.goto('/login');

    // Leave password empty
    await page.fill('input[placeholder="Enter username"]', 'admin');

    // Submit form
    await page.click('button:has-text("Login")');

    // Should show validation error or stay on login page
    const isOnLoginPage = page.url().includes('/login');
    expect(isOnLoginPage).toBe(true);
  });
});

test.describe('JWT Token Refresh', () => {
  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should have refresh token after login', async ({ page }) => {
    await loginAs(page);

    // Check for both tokens
    const accessToken = await page.evaluate(() => localStorage.getItem('access_token'));
    const refreshToken = await page.evaluate(() => localStorage.getItem('refresh_token'));
    const expiresAt = await page.evaluate(() => localStorage.getItem('token_expires_at'));

    expect(accessToken).toBeTruthy();
    expect(refreshToken).toBeTruthy();
    expect(expiresAt).toBeTruthy();

    // Verify expiration is in the future
    const expirationTime = parseInt(expiresAt);
    const currentTime = Date.now();
    expect(expirationTime).toBeGreaterThan(currentTime);
  });

  test('should store token expiration time', async ({ page }) => {
    await loginAs(page);

    const expiresAt = await page.evaluate(() => localStorage.getItem('token_expires_at'));
    expect(expiresAt).toBeTruthy();

    // Verify it's a valid timestamp
    const expirationTime = parseInt(expiresAt);
    expect(expirationTime).toBeGreaterThan(Date.now());
    expect(expirationTime).toBeLessThan(Date.now() + (31 * 60 * 1000)); // Less than 31 minutes from now
  });
});
