// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Camera Test Fixtures (v3.8.0)
 *
 * Reusable functions for camera operations in E2E tests
 */

/**
 * Create a mock camera
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} cameraId - Camera ID (e.g., 'test_camera_1')
 * @param {string} name - Display name (e.g., 'Test Camera')
 */
export async function createMockCamera(page, cameraId, name) {
  await page.goto('/cameras');

  // Click "Add Manually" tab
  await page.click('button:has-text("Add Manually")');

  // Wait for form to be visible
  await page.waitForSelector('input[name="camera_id"]', { timeout: 5000 });

  // Fill camera details
  await page.fill('input[name="camera_id"]', cameraId);
  await page.fill('input[name="name"]', name);

  // Set camera type to mock
  await page.selectOption('select[name="camera_type"]', 'mock');

  // Fill source field (required even for mock)
  await page.fill('input[name="source"]', 'mock');

  // Submit form (button text is "✅ Add Camera")
  await page.click('button:has-text("Add Camera")');

  // Wait for success message or camera to appear in list
  await page.waitForTimeout(1000);

  // Switch to Camera List tab to verify
  await page.click('button:has-text("Camera List")');
  await page.waitForTimeout(500);
}

/**
 * Delete a camera
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} cameraId - Camera ID to delete
 */
export async function deleteCamera(page, cameraId) {
  await page.goto('/cameras');

  // Set up dialog handler before clicking delete
  page.once('dialog', dialog => dialog.accept());

  // Find the camera card by camera_id heading and click delete button
  const cameraCard = page.locator(`.camera-card, [style*="card"]`).filter({ hasText: cameraId }).first();
  await cameraCard.locator('button:has-text("🗑️ Delete")').click();

  // Wait for camera to disappear
  await page.waitForTimeout(1000);
}

/**
 * Start a camera (enable it)
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} cameraId - Camera ID to start
 */
export async function startCamera(page, cameraId) {
  await page.goto('/cameras');

  // Find the camera card and click enable button
  const cameraCard = page.locator(`.camera-card, [style*="card"]`).filter({ hasText: cameraId }).first();
  const enableButton = cameraCard.locator('button:has-text("▶️ Enable")');

  // Only click if button exists (camera might already be active)
  if (await enableButton.count() > 0) {
    await enableButton.click();
    await page.waitForTimeout(2000); // Wait for camera to start
  }

  // Wait for status to change to Active
  await cameraCard.locator('text=● Active').waitFor({ timeout: 10000 });
}

/**
 * Stop a camera (disable it)
 * @param {import('@playwright/test').Page} page - Playwright page object
 * @param {string} cameraId - Camera ID to stop
 */
export async function stopCamera(page, cameraId) {
  await page.goto('/cameras');

  // Find the camera card and click disable button
  const cameraCard = page.locator(`.camera-card, [style*="card"]`).filter({ hasText: cameraId }).first();
  const disableButton = cameraCard.locator('button:has-text("⏸️ Disable")');

  // Only click if button exists (camera might already be disabled)
  if (await disableButton.count() > 0) {
    await disableButton.click();
    await page.waitForTimeout(1000);
  }

  // Wait for status to change to Disabled
  await cameraCard.locator('text=○ Disabled').waitFor({ timeout: 10000 });
}

/**
 * Cleanup all test cameras (cameras with IDs starting with 'test_')
 * @param {import('@playwright/test').Page} page - Playwright page object
 */
export async function cleanupTestCameras(page) {
  try {
    await page.goto('/cameras');
    await page.waitForTimeout(1000);

    // Find all camera cards with test_ IDs
    const cameraCards = await page.locator('.camera-card, [style*="card"]').all();

    for (const card of cameraCards) {
      try {
        const cardText = await card.textContent();
        // Look for test_ camera IDs in the card text
        if (cardText && cardText.includes('test_')) {
          // Extract camera ID from the card
          const cameraIdMatch = cardText.match(/test_camera_\d+/);
          if (cameraIdMatch) {
            const cameraId = cameraIdMatch[0];
            await deleteCamera(page, cameraId);
          }
        }
      } catch (error) {
        console.warn('Failed to cleanup camera:', error.message);
      }
    }
  } catch (error) {
    console.warn('Failed to cleanup test cameras:', error.message);
  }
}
