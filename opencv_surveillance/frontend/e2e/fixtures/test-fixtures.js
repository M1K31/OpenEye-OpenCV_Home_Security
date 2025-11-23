// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Test Fixtures
 * Provides shared setup/teardown and reusable test contexts
 */

import { test as base } from '@playwright/test';
import { login, logout, clearAuth } from '../helpers/auth-helper.js';
import {
  DashboardPage,
  CameraManagementPage,
  FaceManagementPage,
  RecordingsPage,
  SettingsPage,
  Sidebar,
  Modal
} from '../helpers/page-objects.js';

/**
 * Extended test fixture with authenticated user
 */
export const test = base.extend({
  // Authenticated page fixture - automatically logs in before each test
  authenticatedPage: async ({ page }, use) => {
    // Setup: Login
    await login(page);

    // Provide page to test
    await use(page);

    // Teardown: Logout
    try {
      await logout(page);
    } catch (error) {
      console.log('Logout failed, clearing auth manually');
      await clearAuth(page);
    }
  },

  // Page object fixtures
  dashboardPage: async ({ page }, use) => {
    await use(new DashboardPage(page));
  },

  cameraManagementPage: async ({ page }, use) => {
    await use(new CameraManagementPage(page));
  },

  faceManagementPage: async ({ page }, use) => {
    await use(new FaceManagementPage(page));
  },

  recordingsPage: async ({ page }, use) => {
    await use(new RecordingsPage(page));
  },

  settingsPage: async ({ page }, use) => {
    await use(new SettingsPage(page));
  },

  sidebar: async ({ page }, use) => {
    await use(new Sidebar(page));
  },

  modal: async ({ page }, use) => {
    await use(new Modal(page));
  }
});

/**
 * Test data generators
 */
export const testData = {
  /**
   * Generate unique camera ID
   */
  uniqueCameraId: () => {
    return `test-camera-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  },

  /**
   * Generate test camera data
   */
  camera: (overrides = {}) => ({
    camera_id: testData.uniqueCameraId(),
    name: 'Test Camera',
    source: 'mock',
    enabled: true,
    motion_detection_enabled: true,
    face_recognition_enabled: true,
    ...overrides
  }),

  /**
   * Generate unique person name
   */
  uniquePersonName: () => {
    return `TestPerson-${Date.now()}`;
  },

  /**
   * Generate test user data
   */
  user: (overrides = {}) => ({
    username: `testuser-${Date.now()}`,
    email: `test-${Date.now()}@openeye.local`,
    password: 'TestPassword123!',
    role: 'user',
    ...overrides
  })
};

/**
 * Common test utilities
 */
export const utils = {
  /**
   * Wait for network to be idle
   */
  waitForNetwork: async (page, timeout = 5000) => {
    await page.waitForLoadState('networkidle', { timeout });
  },

  /**
   * Take screenshot with timestamp
   */
  screenshot: async (page, name) => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    await page.screenshot({ path: `screenshots/${name}-${timestamp}.png` });
  },

  /**
   * Wait for toast/notification message
   */
  waitForNotification: async (page, message) => {
    await page.waitForSelector(`text=${message}`, { timeout: 5000 });
  },

  /**
   * Clear test data (cameras, recordings, etc.)
   */
  clearTestData: async (page) => {
    // Login as admin
    await login(page, 'admin', 'admin');

    // Delete all test cameras
    await page.goto('/cameras');
    const testCameras = page.locator('[data-camera-id^="test-camera-"]');
    const count = await testCameras.count();

    for (let i = 0; i < count; i++) {
      await testCameras.first().locator('button:has-text("Delete")').click();
      await page.click('button:has-text("Confirm")');
      await page.waitForTimeout(500);
    }

    await logout(page);
  }
};

/**
 * Test hooks for common setup/teardown
 */
export const hooks = {
  /**
   * Setup hook - runs before test suite
   */
  beforeAll: async () => {
    console.log('🚀 Starting E2E test suite');
  },

  /**
   * Teardown hook - runs after test suite
   */
  afterAll: async () => {
    console.log('✅ E2E test suite completed');
  },

  /**
   * Before each test hook
   */
  beforeEach: async ({ page }) => {
    // Clear browser storage
    await page.context().clearCookies();
    await clearAuth(page);
  },

  /**
   * After each test hook
   */
  afterEach: async ({ page }, testInfo) => {
    // Take screenshot on failure
    if (testInfo.status !== 'passed') {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      await page.screenshot({
        path: `test-results/failure-${testInfo.title}-${timestamp}.png`,
        fullPage: true
      });
    }
  }
};

export { expect } from '@playwright/test';
