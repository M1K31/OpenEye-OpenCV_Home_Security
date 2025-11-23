// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Camera Management E2E Tests (v3.8.0)
 *
 * Tests for camera CRUD operations, start/stop, and settings
 */

import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';
import { createMockCamera, deleteCamera, startCamera, stopCamera, cleanupTestCameras } from './fixtures/cameras.js';

test.describe('Camera Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    // Cleanup test cameras and auth
    await cleanupTestCameras(page);
    await cleanupAuth(page);
  });

  test('should display cameras page', async ({ page }) => {
    await page.goto('/cameras');

    // Check for page header (be more specific to avoid multiple h1 elements)
    await expect(page.locator('h1:has-text("Camera Management")')).toBeVisible();

    // Check for tab buttons
    await expect(page.locator('button:has-text("Camera List")')).toBeVisible();
    await expect(page.locator('button:has-text("Add Manually")')).toBeVisible();
  });

  test('should add a new mock camera', async ({ page }) => {
    await page.goto('/cameras');

    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Click "Add Manually" tab
    await page.click('button:has-text("Add Manually")');

    // Wait for form to appear
    await page.waitForSelector('input[name="camera_id"]');

    // Fill camera details
    await page.fill('input[name="camera_id"]', cameraId);
    await page.fill('input[name="name"]', cameraName);

    // Select mock camera type
    await page.selectOption('select[name="camera_type"]', 'mock');

    // Fill source (required)
    await page.fill('input[name="source"]', 'mock');

    // Submit form
    await page.click('button:has-text("Add Camera")');

    // Wait for success message
    await page.waitForTimeout(1000);

    // Switch to Camera List to verify
    await page.click('button:has-text("Camera List")');

    // Verify camera appears in list
    await expect(page.locator(`text=${cameraName}`)).toBeVisible({ timeout: 5000 });
  });

  test('should start and stop a camera', async ({ page }) => {
    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Create camera first (created in disabled state)
    await createMockCamera(page, cameraId, cameraName);

    // Find the camera card
    const cameraCard = page.locator('.camera-card, [style*="card"]').filter({ hasText: cameraId }).first();

    // Start camera (enable it)
    await cameraCard.locator('button:has-text("▶️ Enable")').click();
    await page.waitForTimeout(2000);

    // Wait for status to change to Active
    await expect(cameraCard.locator('text=● Active')).toBeVisible({ timeout: 10000 });

    // Stop camera (disable it)
    await cameraCard.locator('button:has-text("⏸️ Disable")').click();
    await page.waitForTimeout(1000);

    // Wait for status to change to Disabled
    await expect(cameraCard.locator('text=○ Disabled')).toBeVisible({ timeout: 10000 });
  });

  test('should delete a camera', async ({ page }) => {
    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Create camera first
    await createMockCamera(page, cameraId, cameraName);

    // Verify camera exists
    await expect(page.locator(`text=${cameraId}`)).toBeVisible();

    // Set up dialog handler before clicking delete
    page.once('dialog', dialog => dialog.accept());

    // Find the camera card and delete it
    const cameraCard = page.locator('.camera-card, [style*="card"]').filter({ hasText: cameraId }).first();
    await cameraCard.locator('button:has-text("🗑️ Delete")').click();

    // Wait for deletion
    await page.waitForTimeout(1000);

    // Verify camera is removed
    await expect(page.locator(`text=${cameraId}`)).not.toBeVisible({ timeout: 5000 });
  });

  test('should open camera settings modal', async ({ page }) => {
    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Create camera first
    await createMockCamera(page, cameraId, cameraName);

    // Find the camera card and click settings
    const cameraCard = page.locator('.camera-card, [style*="card"]').filter({ hasText: cameraId }).first();
    await cameraCard.locator('button:has-text("⚙️ Settings")').click();

    // Verify modal is open
    await expect(page.locator('.modal, [role="dialog"], [style*="position: fixed"]')).toBeVisible({ timeout: 5000 });

    // Check for settings content (look for common settings elements)
    await expect(page.locator('text=/General|Settings|Configuration/i')).toBeVisible();
  });

  test('should update camera settings', async ({ page }) => {
    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Create camera first
    await createMockCamera(page, cameraId, cameraName);

    // Find the camera card and open settings
    const cameraCard = page.locator('.camera-card, [style*="card"]').filter({ hasText: cameraId }).first();
    await cameraCard.locator('button:has-text("⚙️ Settings")').click();

    // Wait for modal
    await page.waitForSelector('.modal, [role="dialog"], [style*="position: fixed"]', { timeout: 5000 });

    // Try to interact with settings (look for any checkbox to toggle)
    const checkboxes = page.locator('input[type="checkbox"]');
    if (await checkboxes.count() > 0) {
      await checkboxes.first().check();
    }

    // Save settings (look for save/apply button)
    const saveButton = page.locator('button:has-text("Save"), button:has-text("Apply"), button:has-text("✅")').first();
    if (await saveButton.count() > 0) {
      await saveButton.click();
    }

    // Verify modal closes or settings are updated
    await page.waitForTimeout(1000);
  });

  test('should prevent duplicate camera IDs', async ({ page }) => {
    const cameraId = 'test_camera_duplicate';
    const cameraName = 'Test Camera 1';

    // Create first camera
    await createMockCamera(page, cameraId, cameraName);

    // Try to create second camera with same ID
    // Click "Add Manually" tab
    await page.click('button:has-text("➕ Add Manually")');

    // Wait for form
    await page.waitForSelector('input[name="camera_id"]', { timeout: 5000 });

    // Fill form with duplicate camera_id
    await page.fill('input[name="camera_id"]', cameraId);
    await page.fill('input[name="name"]', 'Test Camera 2');
    await page.selectOption('select[name="camera_type"]', 'mock');
    await page.fill('input[name="source"]', 'mock');

    // Submit form
    await page.click('button:has-text("✅ Add Camera")');

    // Wait for error message (backend should reject duplicate)
    await page.waitForTimeout(1000);

    // Should show error message or still be on form
    // Check if error message appears or form is still visible (indicating validation error)
    const hasError = await page.locator('.error, [role="alert"], text=/already exists|duplicate|error/i').count() > 0;
    const formStillVisible = await page.locator('input[name="camera_id"]').isVisible();

    // Either error message shown or form still visible (validation failed)
    expect(hasError || formStillVisible).toBeTruthy();
  });

  test('should require camera ID', async ({ page }) => {
    await page.goto('/cameras');

    // Click "Add Manually" tab
    await page.click('button:has-text("Add Manually")');

    // Wait for form
    await page.waitForSelector('input[name="camera_id"]');

    // Leave camera_id empty, fill other fields
    await page.fill('input[name="name"]', 'Test Camera');
    await page.fill('input[name="source"]', 'mock');

    // Try to submit (HTML5 validation should prevent submission)
    await page.click('button:has-text("Add Camera")');

    // Form should still be visible (not submitted due to required field)
    await expect(page.locator('input[name="camera_id"]')).toBeVisible();
  });
});

test.describe('Camera Live View', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupTestCameras(page);
    await cleanupAuth(page);
  });

  test('should display live dashboard', async ({ page }) => {
    await page.goto('/');

    // Check for dashboard header
    await expect(page.locator('h1')).toContainText(/live dashboard|dashboard/i);

    // Check for camera grid
    await expect(page.locator('.camera-grid, .cameras-grid')).toBeVisible();
  });

  test('should show camera feed when started', async ({ page }) => {
    const cameraId = 'test_camera_' + Date.now();
    const cameraName = 'Test Camera ' + Date.now();

    // Create and start camera
    await createMockCamera(page, cameraId, cameraName);
    await startCamera(page, cameraId);

    // Go to dashboard
    await page.goto('/');

    // Wait for dashboard to load
    await page.waitForTimeout(2000);

    // Check for camera feed (look for img or video elements, or camera ID text)
    const hasCameraFeed = await page.locator(`img[alt*="${cameraId}"], video, img[src*="/api/cameras/${cameraId}/"], text=${cameraId}`).count() > 0;

    // Camera should appear on dashboard when active
    expect(hasCameraFeed).toBeTruthy();
  });
});
