// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Test Helper: Authentication Utilities
 * Provides reusable authentication functions for Playwright tests
 */

/**
 * Login to OpenEye with username and password
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} username - Username (default: 'admin')
 * @param {string} password - Password (default: 'admin')
 * @returns {Promise<void>}
 */
export async function login(page, username = 'admin', password = 'admin') {
  // Navigate to login page
  await page.goto('/');

  // Wait for login form to be visible
  await page.waitForSelector('input[type="text"]', { timeout: 10000 });

  // Fill in credentials
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);

  // Click login button
  await page.click('button[type="submit"]');

  // Wait for navigation to dashboard (no 2FA)
  // OR wait for 2FA prompt if 2FA is enabled
  try {
    // Check if 2FA is required
    await page.waitForSelector('text=Enter 2FA Code', { timeout: 2000 });
    console.log('2FA detected - needs manual code entry');
  } catch {
    // No 2FA - should be on dashboard
    await page.waitForURL('**/dashboard', { timeout: 5000 });
  }
}

/**
 * Login with 2FA code
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} username - Username
 * @param {string} password - Password
 * @param {string} twoFactorCode - 6-digit 2FA code
 * @returns {Promise<void>}
 */
export async function loginWith2FA(page, username, password, twoFactorCode) {
  await page.goto('/');

  // Enter credentials
  await page.fill('input[type="text"]', username);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  // Wait for 2FA prompt
  await page.waitForSelector('text=Enter 2FA Code', { timeout: 5000 });

  // Enter 2FA code
  await page.fill('input[placeholder*="2FA"]', twoFactorCode);
  await page.click('button:has-text("Verify")');

  // Wait for dashboard
  await page.waitForURL('**/dashboard', { timeout: 5000 });
}

/**
 * Logout from OpenEye
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @returns {Promise<void>}
 */
export async function logout(page) {
  // Click logout button (usually in sidebar or header)
  await page.click('button:has-text("Logout")');

  // Wait for redirect to login page
  await page.waitForURL('**/', { timeout: 5000 });

  // Verify login form is visible
  await page.waitForSelector('input[type="text"]');
}

/**
 * Check if user is logged in (by checking for dashboard elements)
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @returns {Promise<boolean>}
 */
export async function isLoggedIn(page) {
  try {
    // Check for dashboard-specific elements
    await page.waitForSelector('text=Dashboard', { timeout: 2000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Get authentication token from localStorage
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @returns {Promise<string|null>}
 */
export async function getAuthToken(page) {
  return await page.evaluate(() => localStorage.getItem('token'));
}

/**
 * Set authentication token in localStorage
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} token - JWT token
 * @returns {Promise<void>}
 */
export async function setAuthToken(page, token) {
  await page.evaluate((token) => {
    localStorage.setItem('token', token);
  }, token);
}

/**
 * Clear all authentication data
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @returns {Promise<void>}
 */
export async function clearAuth(page) {
  await page.evaluate(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
  });
}

/**
 * Wait for API request to complete
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} urlPattern - URL pattern to match (e.g., '**/api/cameras')
 * @param {Function} action - Action that triggers the request
 * @returns {Promise<import('@playwright/test').Response>}
 */
export async function waitForAPI(page, urlPattern, action) {
  const responsePromise = page.waitForResponse(urlPattern);
  await action();
  return await responsePromise;
}

/**
 * Create a test user via API
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {Object} userData - User data
 * @returns {Promise<void>}
 */
export async function createTestUser(page, userData = {}) {
  const defaultUser = {
    username: 'testuser',
    email: 'test@openeye.local',
    password: 'TestPassword123!',
    role: 'user',
    ...userData
  };

  // Create user via API
  const response = await page.request.post('/api/users/', {
    data: defaultUser
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test user: ${response.statusText()}`);
  }

  return defaultUser;
}

/**
 * Delete a test user via direct database access (for cleanup)
 * Note: This requires backend API endpoint for user deletion
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} username - Username to delete
 * @returns {Promise<void>}
 */
export async function deleteTestUser(page, username) {
  // First login as admin to get token
  const token = await getAuthToken(page);

  // Delete user via API
  await page.request.delete(`/api/users/${username}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
}
