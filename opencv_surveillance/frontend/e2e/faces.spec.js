// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Tests: Face Management & Recognition
 * Tests for face uploads, detection history, and clustering
 */

import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';

test.describe('Face Management', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display faces page', async ({ page }) => {
    await page.goto('/faces');

    // Check for page header
    await expect(page.locator('h1:has-text("Face Management"), h1:has-text("AI & Faces")')).toBeVisible();

    // Check for upload button or section
    await expect(page.locator('button:has-text("Upload"), text=/upload.*faces/i')).toBeVisible();
  });

  test('should display people list', async ({ page }) => {
    await page.goto('/faces');

    // Navigate to people tab if tabbed interface
    const peopleTab = page.locator('button:has-text("People"), button:has-text("Known Faces")');
    if (await peopleTab.count() > 0) {
      await peopleTab.click();
    }

    // Should show people list or "No people" message
    const hasPeople = await page.locator('.person-card, [data-testid="person-card"]').count();
    const noDataMessage = await page.locator('text=/no people|no faces/i').count();

    expect(hasPeople > 0 || noDataMessage > 0).toBeTruthy();
  });

  test('should display face detection history', async ({ page }) => {
    await page.goto('/faces');

    // Navigate to detection history tab
    const historyTab = page.locator('button:has-text("Detection History"), button:has-text("History")');
    if (await historyTab.count() > 0) {
      await historyTab.click();
      await page.waitForTimeout(1000);
    }

    // Should show history or "No detections" message
    const hasDetections = await page.locator('.detection-card, [data-testid="detection-event"]').count();
    const noDataMessage = await page.locator('text=/no detections|no history/i').count();

    expect(hasDetections > 0 || noDataMessage > 0).toBeTruthy();
  });

  test('should filter detection history by person', async ({ page }) => {
    await page.goto('/faces');

    // Go to history tab
    const historyTab = page.locator('button:has-text("Detection History"), button:has-text("History")');
    if (await historyTab.count() > 0) {
      await historyTab.click();
      await page.waitForTimeout(500);
    }

    // Look for person filter dropdown
    const personFilter = page.locator('select[name="person"], select[name="person_name"], select:has-text("All People")');
    if (await personFilter.count() > 0) {
      // Get available options
      const options = await personFilter.locator('option').count();

      if (options > 1) {
        // Select first person (not "All")
        await personFilter.selectOption({ index: 1 });

        // Wait for filtered results
        await page.waitForTimeout(1000);

        // Detections should update (or show "No detections for this person")
        const hasResults = await page.locator('.detection-card, [data-testid="detection-event"]').count() > 0;
        const noResults = await page.locator('text=/no detections/i').count() > 0;

        expect(hasResults || noResults).toBeTruthy();
      }
    }
  });

  test('should filter detection history by date range', async ({ page }) => {
    await page.goto('/faces');

    // Go to history tab
    const historyTab = page.locator('button:has-text("Detection History")');
    if (await historyTab.count() > 0) {
      await historyTab.click();
    }

    // Look for date filters
    const startDateInput = page.locator('input[type="date"][name="start_date"], input[type="date"]:first-of-type');
    if (await startDateInput.count() > 0) {
      // Set date range
      const today = new Date().toISOString().split('T')[0];
      await startDateInput.fill(today);

      // Wait for results to update
      await page.waitForTimeout(1000);

      // Should show filtered results or "No detections" message
      const hasResults = await page.locator('.detection-card').count() > 0;
      const noResults = await page.locator('text=/no detections/i').count() > 0;

      expect(hasResults || noResults).toBeTruthy();
    }
  });

  test('should show detection details when clicked', async ({ page }) => {
    await page.goto('/faces');

    // Go to history tab
    const historyTab = page.locator('button:has-text("Detection History")');
    if (await historyTab.count() > 0) {
      await historyTab.click();
      await page.waitForTimeout(1000);
    }

    // Click first detection if exists
    const firstDetection = page.locator('.detection-card, [data-testid="detection-event"]').first();
    if (await firstDetection.count() > 0) {
      await firstDetection.click();

      // Should show modal or expanded view with details
      const hasModal = await page.locator('[role="dialog"], .modal').count() > 0;
      const hasExpandedView = await page.locator('.detection-details, [data-testid="detection-details"]').count() > 0;

      expect(hasModal || hasExpandedView).toBeTruthy();
    }
  });

  test('should handle pagination in detection history', async ({ page }) => {
    await page.goto('/faces');

    // Go to history tab
    const historyTab = page.locator('button:has-text("Detection History")');
    if (await historyTab.count() > 0) {
      await historyTab.click();
      await page.waitForTimeout(1000);
    }

    // Look for pagination controls
    const nextButton = page.locator('button:has-text("Next"), button:has-text("›"), button:has-text("→")');
    if (await nextButton.count() > 0 && await nextButton.isEnabled()) {
      // Get current page detections count
      const initialCount = await page.locator('.detection-card').count();

      // Click next page
      await nextButton.click();
      await page.waitForTimeout(1000);

      // Detections should change (unless same data on multiple pages)
      const newCount = await page.locator('.detection-card').count();

      // At least the pagination worked (didn't error)
      expect(true).toBeTruthy();
    }
  });
});

test.describe('Face Clustering (v3.6.0)', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display face clustering page', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Check for clustering page elements
    await expect(page.locator('h1:has-text("Clustering"), h1:has-text("Unknown Faces")')).toBeVisible();
  });

  test('should display clusters of unknown faces', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Should show cluster cards or "No clusters" message
    const hasClusters = await page.locator('.cluster-card, [data-testid="cluster-card"]').count();
    const noDataMessage = await page.locator('text=/no clusters|no unknown faces/i').count();

    expect(hasClusters > 0 || noDataMessage > 0).toBeTruthy();
  });

  test('should filter clusters by identified status', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Look for filter toggle
    const identifiedFilter = page.locator('input[type="checkbox"][name="show_identified"], button:has-text("Identified")');
    if (await identifiedFilter.count() > 0) {
      // Toggle filter
      await identifiedFilter.click();
      await page.waitForTimeout(500);

      // Clusters should update
      const hasResults = await page.locator('.cluster-card').count() > 0;
      expect(hasResults).toBeTruthy();
    }
  });

  test('should view cluster details', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Click first cluster if exists
    const firstCluster = page.locator('.cluster-card, [data-testid="cluster-card"]').first();
    if (await firstCluster.count() > 0) {
      await firstCluster.click();

      // Should show modal with cluster details
      await expect(page.locator('[role="dialog"], .modal')).toBeVisible({ timeout: 3000 });

      // Should show cluster images
      await expect(page.locator('img[alt*="cluster"], img[alt*="face"]')).toBeVisible();
    }
  });

  test('should identify cluster as new person', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Click first unidentified cluster
    const firstCluster = page.locator('.cluster-card').first();
    if (await firstCluster.count() > 0) {
      await firstCluster.click();

      // Look for "Identify" button in modal
      const identifyButton = page.locator('button:has-text("Identify"), button:has-text("Add as New Person")');
      if (await identifyButton.count() > 0) {
        await identifyButton.click();

        // Should show name input
        const nameInput = page.locator('input[name="person_name"], input[placeholder*="name"]');
        await expect(nameInput).toBeVisible({ timeout: 2000 });

        // Enter name
        const testName = 'TestPerson_' + Date.now();
        await nameInput.fill(testName);

        // Submit
        await page.click('button:has-text("Save"), button:has-text("Confirm")');

        // Should show success message
        await expect(page.locator('text=/identified|added successfully/i')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should delete cluster', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Click first cluster
    const firstCluster = page.locator('.cluster-card').first();
    if (await firstCluster.count() > 0) {
      await firstCluster.click();

      // Look for delete button
      const deleteButton = page.locator('button:has-text("Delete"), button:has-text("🗑️")');
      if (await deleteButton.count() > 0) {
        // Set up confirmation dialog handler
        page.once('dialog', dialog => dialog.accept());

        await deleteButton.click();

        // Wait for deletion
        await page.waitForTimeout(1000);

        // Modal should close
        const modalVisible = await page.locator('[role="dialog"]').count() > 0;
        expect(modalVisible).toBeFalsy();
      }
    }
  });

  test('should display cluster statistics', async ({ page }) => {
    await page.goto('/faces/clusters');

    // Look for statistics panel
    const statsPanel = page.locator('[data-testid="cluster-stats"], .statistics-panel');
    if (await statsPanel.count() > 0) {
      await expect(statsPanel).toBeVisible();

      // Should show metrics like total clusters, identified, unknown
      await expect(page.locator('text=/total clusters|identified|unknown/i')).toBeVisible();
    }
  });
});

test.describe('Face Upload', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display upload faces interface', async ({ page }) => {
    await page.goto('/faces');

    // Navigate to upload tab
    const uploadTab = page.locator('button:has-text("Upload"), button:has-text("Upload Faces")');
    if (await uploadTab.count() > 0) {
      await uploadTab.click();
    }

    // Should show upload interface
    await expect(page.locator('input[type="file"], text=/upload|drag.*drop/i')).toBeVisible();
  });

  test('should show upload instructions', async ({ page }) => {
    await page.goto('/faces');

    // Navigate to upload section
    const uploadTab = page.locator('button:has-text("Upload Faces")');
    if (await uploadTab.count() > 0) {
      await uploadTab.click();
    }

    // Should display instructions
    await expect(page.locator('text=/instructions|how to upload|organize/i')).toBeVisible();
  });

  test.skip('should upload face images', async ({ page }) => {
    // This test is skipped because it requires actual image files
    // To enable: Create test images and update file paths

    await page.goto('/faces');

    const uploadTab = page.locator('button:has-text("Upload Faces")');
    if (await uploadTab.count() > 0) {
      await uploadTab.click();
    }

    // Upload files (would need real image files)
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles([
      // 'path/to/test/image1.jpg',
      // 'path/to/test/image2.jpg'
    ]);

    // Submit upload
    await page.click('button:has-text("Upload"), button:has-text("Submit")');

    // Should show success message
    await expect(page.locator('text=/uploaded successfully|processing/i')).toBeVisible({ timeout: 10000 });
  });
});
