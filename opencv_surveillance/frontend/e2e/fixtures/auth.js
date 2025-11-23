// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Authentication Test Fixtures (v3.8.0)
 *
 * Reusable functions for authentication flows in E2E tests
 */

/**
 * Login as a specific user
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} username - Username to login with
 * @param {string} password - Password to login with
 */
export async function loginAs(page, username = 'admin', password = 'admin') {
  await page.goto('/login');

  // Wait for login form to be visible
  await page.waitForSelector('input[placeholder="Enter username"]', { timeout: 10000 });

  // Fill credentials (using placeholder selectors since inputs don't have name attributes)
  await page.fill('input[placeholder="Enter username"]', username);
  await page.fill('input[placeholder="Enter password"]', password);

  // Submit form
  await page.click('button:has-text("Login")');

  // Wait for navigation to dashboard
  await page.waitForURL('/');

  // Verify we're logged in by checking for dashboard heading
  await page.waitForSelector('h1:has-text("OpenEye")', { timeout: 5000 });
}

/**
 * Login with 2FA code
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} username - Username to login with
 * @param {string} password - Password to login with
 * @param {string} totpCode - 6-digit TOTP code
 */
export async function loginWith2FA(page, username, password, totpCode) {
  await page.goto('/login');

  // Wait for login form to be visible
  await page.waitForSelector('input[placeholder="Enter username"]', { timeout: 10000 });

  // Fill credentials
  await page.fill('input[placeholder="Enter username"]', username);
  await page.fill('input[placeholder="Enter password"]', password);

  // Submit form
  await page.click('button:has-text("Login")');

  // Wait for 2FA prompt
  await page.waitForSelector('input[placeholder="000000"]', { timeout: 5000 });

  // Enter TOTP code
  await page.fill('input[placeholder="000000"]', totpCode);
  await page.click('button:has-text("Login")');

  // Wait for navigation to dashboard
  await page.waitForURL('/');
}

/**
 * Logout the current user
 * @param {import('@playwright/test').Page} page - Playwright page object
 */
export async function logout(page) {
  // Click user menu button to open dropdown
  await page.click('button.user-menu-button, .user-menu button');

  // Wait for dropdown to appear
  await page.waitForSelector('.logout-button', { timeout: 3000 });

  // Click logout button in dropdown
  await page.click('.logout-button');

  // Wait for redirect to login page
  await page.waitForURL('/login');
}

/**
 * Check if user is logged in
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @returns {Promise<boolean>} True if logged in, false otherwise
 */
export async function isLoggedIn(page) {
  try {
    // Check if we're on the dashboard or any protected page
    const url = page.url();
    if (url.includes('/login')) {
      return false;
    }

    // Check for presence of user menu button (indicates logged in state)
    const userMenuButton = await page.locator('button.user-menu-button, .user-menu button').count();
    return userMenuButton > 0;
  } catch (error) {
    return false;
  }
}

/**
 * Setup authenticated context (for beforeEach)
 * @param {import('@playwright/test').Page} page - Playwright page object
 */
export async function setupAuth(page) {
  await loginAs(page);
}

/**
 * Cleanup auth tokens (for afterEach)
 * @param {import('@playwright/test').Page} page - Playwright page object
 */
export async function cleanupAuth(page) {
  try {
    // Clear localStorage tokens (only if page has loaded successfully)
    await page.evaluate(() => {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('token_expires_at');
      localStorage.removeItem('username');
    });
  } catch (error) {
    // Ignore errors if page didn't load (e.g., connection refused)
    // This can happen if the test fails before page loads
    console.log('Cleanup warning: Unable to clear localStorage', error.message);
  }
}
