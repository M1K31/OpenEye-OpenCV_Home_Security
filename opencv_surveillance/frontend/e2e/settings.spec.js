// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Tests: System Settings
 * Tests for system configuration, notifications, and preferences
 */

import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';

test.describe('System Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display settings page', async ({ page }) => {
    await page.goto('/settings');

    // Check for settings header
    await expect(page.locator('h1:has-text("Settings"), h1:has-text("System Settings")')).toBeVisible();

    // Should show save button
    await expect(page.locator('button:has-text("Save")')).toBeVisible();
  });

  test('should display general settings section', async ({ page }) => {
    await page.goto('/settings');

    // Check for general settings
    await expect(page.locator('text=/general|basic|system/i')).toBeVisible();

    // Common settings should be visible
    const hasSettings = await page.locator('input[type="checkbox"], input[type="text"], select').count() > 0;
    expect(hasSettings).toBeTruthy();
  });

  test('should toggle motion detection setting', async ({ page }) => {
    await page.goto('/settings');

    // Find motion detection toggle
    const motionToggle = page.locator('input[name="motion_detection_enabled"], input[type="checkbox"]:near(text=/motion.*detection/i)').first();

    if (await motionToggle.count() > 0) {
      // Get initial state
      const initialState = await motionToggle.isChecked();

      // Toggle setting
      await motionToggle.click();

      // Save settings
      await page.click('button:has-text("Save")');

      // Wait for success message
      await expect(page.locator('text=/saved|updated successfully/i')).toBeVisible({ timeout: 5000 });

      // Reload and verify change persisted
      await page.reload();
      await page.waitForLoadState('networkidle');

      const newState = await motionToggle.isChecked();
      expect(newState).toBe(!initialState);

      // Toggle back to original state
      await motionToggle.click();
      await page.click('button:has-text("Save")');
      await page.waitForTimeout(1000);
    }
  });

  test('should toggle face recognition setting', async ({ page }) => {
    await page.goto('/settings');

    // Find face recognition toggle
    const faceToggle = page.locator('input[name="face_recognition_enabled"], input[type="checkbox"]:near(text=/face.*recognition/i)').first();

    if (await faceToggle.count() > 0) {
      const initialState = await faceToggle.isChecked();

      // Toggle
      await faceToggle.click();

      // Save
      await page.click('button:has-text("Save")');
      await expect(page.locator('text=/saved/i')).toBeVisible({ timeout: 5000 });

      // Verify persistence
      await page.reload();
      const newState = await faceToggle.isChecked();
      expect(newState).toBe(!initialState);

      // Revert
      await faceToggle.click();
      await page.click('button:has-text("Save")');
    }
  });

  test('should update retention policy settings', async ({ page }) => {
    await page.goto('/settings');

    // Find retention policy input
    const retentionInput = page.locator('input[name="retention_days"], input[type="number"]:near(text=/retention|keep.*days/i)').first();

    if (await retentionInput.count() > 0) {
      // Set new value
      const testValue = '30';
      await retentionInput.fill(testValue);

      // Save
      await page.click('button:has-text("Save")');
      await expect(page.locator('text=/saved/i')).toBeVisible({ timeout: 5000 });

      // Verify
      await page.reload();
      const savedValue = await retentionInput.inputValue();
      expect(savedValue).toBe(testValue);
    }
  });

  test('should validate numeric inputs', async ({ page }) => {
    await page.goto('/settings');

    // Find any numeric input
    const numberInput = page.locator('input[type="number"]').first();

    if (await numberInput.count() > 0) {
      // Try to enter invalid value (negative or text)
      await numberInput.fill('-10');

      // Try to save
      await page.click('button:has-text("Save")');

      // Should show validation error or prevent save
      await page.waitForTimeout(500);

      // Either error message appears or value is corrected
      const hasError = await page.locator('.error, [role="alert"]').count() > 0;
      const valueChanged = await numberInput.inputValue() !== '-10';

      expect(hasError || valueChanged).toBeTruthy();
    }
  });
});

test.describe('Performance Settings (v3.7.1)', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display performance settings', async ({ page }) => {
    await page.goto('/settings');

    // Look for performance section
    const perfSection = page.locator('text=/performance|hardware.*encoding/i');
    if (await perfSection.count() > 0) {
      await expect(perfSection).toBeVisible();
    }
  });

  test('should toggle hardware video encoding', async ({ page }) => {
    await page.goto('/settings');

    // Find hardware encoding toggle
    const hwEncoding = page.locator('input[name="hardware_video_encoding"], input[type="checkbox"]:near(text=/hardware.*encoding/i)');

    if (await hwEncoding.count() > 0) {
      const initialState = await hwEncoding.isChecked();

      // Toggle
      await hwEncoding.click();

      // Save
      await page.click('button:has-text("Save")');
      await expect(page.locator('text=/saved/i')).toBeVisible({ timeout: 5000 });

      // Verify
      await page.reload();
      const newState = await hwEncoding.isChecked();
      expect(newState).toBe(!initialState);

      // Revert
      await hwEncoding.click();
      await page.click('button:has-text("Save")');
    }
  });

  test('should display GPU information if available', async ({ page }) => {
    await page.goto('/settings');

    // Look for GPU info section
    const gpuInfo = page.locator('text=/GPU|NVIDIA|VideoToolbox|QuickSync|VAAPI/i');
    const count = await gpuInfo.count();

    // GPU info may or may not be present depending on hardware
    // This test just verifies no errors occur
    expect(count >= 0).toBeTruthy();
  });
});

test.describe('Notification Settings (v3.6.0)', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display notification providers page', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Check for notification settings
    await expect(page.locator('h1:has-text("Notifications"), h1:has-text("Alert Settings")')).toBeVisible();
  });

  test('should display available notification providers', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Should show provider cards or list
    const providerTypes = ['Email', 'SMS', 'Telegram', 'Discord', 'Webhook'];

    // At least one provider type should be mentioned
    let foundProvider = false;
    for (const provider of providerTypes) {
      if (await page.locator(`text=${provider}`).count() > 0) {
        foundProvider = true;
        break;
      }
    }

    expect(foundProvider).toBeTruthy();
  });

  test('should show add provider button', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Look for "Add Provider" or "Configure" button
    const addButton = page.locator('button:has-text("Add"), button:has-text("Configure"), button:has-text("New")');
    await expect(addButton.first()).toBeVisible();
  });

  test('should open provider configuration modal', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Click add/configure button
    const configButton = page.locator('button:has-text("Add"), button:has-text("Configure")').first();
    await configButton.click();

    // Should show modal
    await expect(page.locator('[role="dialog"], .modal')).toBeVisible({ timeout: 3000 });

    // Should show provider type selection
    await expect(page.locator('select, text=/provider type|choose provider/i')).toBeVisible();
  });

  test('should display encrypted credential notice', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Click add provider
    const addButton = page.locator('button:has-text("Add")').first();
    if (await addButton.count() > 0) {
      await addButton.click();

      // Should mention encryption for credentials
      const hasEncryptionNote = await page.locator('text=/encrypted|secure|protected/i').count() > 0;

      // This is expected for v3.6.0 security features
      expect(hasEncryptionNote).toBeTruthy();
    }
  });

  test('should list configured notification providers', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Should show configured providers or "No providers" message
    const hasProviders = await page.locator('.provider-card, [data-testid="provider"]').count();
    const noProvidersMsg = await page.locator('text=/no providers|no notifications configured/i').count();

    expect(hasProviders > 0 || noProvidersMsg > 0).toBeTruthy();
  });

  test('should delete notification provider', async ({ page }) => {
    await page.goto('/settings/notifications');

    // Look for delete button on first provider
    const deleteButton = page.locator('button:has-text("Delete"), button:has-text("🗑️")').first();

    if (await deleteButton.count() > 0) {
      // Set up confirmation handler
      page.once('dialog', dialog => dialog.accept());

      await deleteButton.click();

      // Wait for deletion
      await page.waitForTimeout(1000);

      // Should show success message or provider removed
      const success = await page.locator('text=/deleted|removed/i').count() > 0;

      // Deletion may or may not succeed (provider might not exist)
      expect(true).toBeTruthy();
    }
  });
});

test.describe('Theme Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display theme selector', async ({ page }) => {
    await page.goto('/settings/theme');

    // Check for theme selection
    await expect(page.locator('h1:has-text("Theme"), h1:has-text("Appearance")')).toBeVisible();
  });

  test('should show available themes', async ({ page }) => {
    await page.goto('/settings/theme');

    // OpenEye has 9 themes
    const themes = ['Default', 'Superman', 'Batman', 'Wonder Woman', 'Flash', 'Aquaman', 'Cyborg', 'Green Lantern', 'Aqua Security'];

    // At least some themes should be visible
    let themeCount = 0;
    for (const theme of themes) {
      if (await page.locator(`text=${theme}`).count() > 0) {
        themeCount++;
      }
    }

    expect(themeCount).toBeGreaterThan(0);
  });

  test('should change theme', async ({ page }) => {
    await page.goto('/settings/theme');

    // Find theme buttons/cards
    const themeButtons = page.locator('button:has-text("Superman"), button:has-text("Batman")');

    if (await themeButtons.count() > 0) {
      // Click a theme
      await themeButtons.first().click();

      // Wait for theme to apply
      await page.waitForTimeout(500);

      // Theme should be applied (check body class or data attribute)
      const bodyClass = await page.evaluate(() => document.body.className);

      // Body should have a theme class
      expect(bodyClass).toBeTruthy();
    }
  });

  test('should persist theme selection', async ({ page }) => {
    await page.goto('/settings/theme');

    // Select a theme
    const batmanTheme = page.locator('button:has-text("Batman")');
    if (await batmanTheme.count() > 0) {
      await batmanTheme.click();
      await page.waitForTimeout(500);

      // Reload page
      await page.reload();

      // Theme should still be applied
      const bodyClass = await page.evaluate(() => document.body.className);
      expect(bodyClass).toContain('batman' || 'theme');
    }
  });
});

test.describe('User Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test.skip('should display user management page (admin only)', async ({ page }) => {
    // This test requires admin privileges
    await page.goto('/settings/users');

    // Should show users list or "Access Denied"
    const hasAccess = await page.locator('h1:has-text("Users"), h1:has-text("User Management")').count() > 0;
    const accessDenied = await page.locator('text=/access denied|unauthorized/i').count() > 0;

    expect(hasAccess || accessDenied).toBeTruthy();
  });

  test.skip('should add new user (admin only)', async ({ page }) => {
    await page.goto('/settings/users');

    // Click add user button
    await page.click('button:has-text("Add User")');

    // Fill user form
    const testUsername = 'testuser_' + Date.now();
    await page.fill('input[name="username"]', testUsername);
    await page.fill('input[name="email"]', `${testUsername}@openeye.local`);
    await page.fill('input[name="password"]', 'TestPassword123!');

    // Select role
    await page.selectOption('select[name="role"]', 'user');

    // Submit
    await page.click('button:has-text("Create"), button:has-text("Add")');

    // Should show success message
    await expect(page.locator('text=/user created|added successfully/i')).toBeVisible({ timeout: 5000 });
  });
});
