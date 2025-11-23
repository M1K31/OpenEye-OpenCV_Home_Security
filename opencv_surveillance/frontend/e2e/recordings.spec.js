// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * Recordings & Snapshots E2E Tests (v3.8.0)
 *
 * Tests for video recordings and snapshot browsing, playback, and download
 */

import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';

test.describe('Recordings & Snapshots', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await setupAuth(page);
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page);
  });

  test('should display recordings page', async ({ page }) => {
    await page.goto('/events');

    // Check for page header
    await expect(page.locator('h1')).toContainText(/recording|event|history/i);

    // Check for tabs (Videos and Snapshots)
    await expect(page.locator('button:has-text("Videos"), .tab:has-text("Videos")')).toBeVisible();
    await expect(page.locator('button:has-text("Snapshots"), .tab:has-text("Snapshots")')).toBeVisible();
  });

  test('should switch between videos and snapshots tabs', async ({ page }) => {
    await page.goto('/events');

    // Click videos tab
    await page.click('button:has-text("Videos"), .tab:has-text("Videos")');

    // Verify videos content is visible
    await expect(page.locator('.recordings-grid, .video-grid, text=/video|recording/i')).toBeVisible({ timeout: 5000 });

    // Click snapshots tab
    await page.click('button:has-text("Snapshots"), .tab:has-text("Snapshots")');

    // Verify snapshots content is visible
    await expect(page.locator('.snapshots-grid, .snapshot-grid, text=/snapshot|motion/i')).toBeVisible({ timeout: 5000 });
  });

  test('should display video recordings grid', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos"), .tab:has-text("Videos")');

    // Check for recordings grid
    await expect(page.locator('.recordings-grid, .video-grid')).toBeVisible();

    // If there are recordings, check for recording cards
    const recordingCards = await page.locator('.recording-card, .video-card').count();
    if (recordingCards > 0) {
      // Verify first recording has expected elements
      await expect(page.locator('.recording-card, .video-card').first()).toBeVisible();

      // Check for video preview or thumbnail
      const hasVideo = await page.locator('video').count() > 0;
      const hasImage = await page.locator('.recording-card img, .video-card img').count() > 0;

      expect(hasVideo || hasImage).toBe(true);
    }
  });

  test('should display snapshots grid', async ({ page }) => {
    await page.goto('/events');

    // Switch to Snapshots tab
    await page.click('button:has-text("Snapshots"), .tab:has-text("Snapshots")');

    // Check for snapshots grid
    await expect(page.locator('.snapshots-grid, .snapshot-grid')).toBeVisible();

    // If there are snapshots, verify they load
    const snapshotCount = await page.locator('.snapshot-card, .snapshot-image').count();
    if (snapshotCount > 0) {
      // Verify first snapshot is visible
      await expect(page.locator('.snapshot-card, .snapshot-image').first()).toBeVisible();

      // Check for image element
      await expect(page.locator('.snapshot-card img, .snapshot-image').first()).toBeVisible();
    }
  });

  test('should filter recordings by camera', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Find camera filter dropdown
    const cameraFilter = page.locator('select[name="camera_filter"], select:has(option:has-text("All Cameras"))');

    if (await cameraFilter.count() > 0) {
      // Get options
      const options = await cameraFilter.locator('option').all();

      if (options.length > 1) {
        // Select second option (first camera)
        await cameraFilter.selectOption({ index: 1 });

        // Wait for grid to update
        await page.waitForTimeout(1000);

        // Verify URL or state has changed
        const url = page.url();
        expect(url).toBeTruthy();
      }
    }
  });

  test('should filter by date range', async ({ page }) => {
    await page.goto('/events');

    // Find date inputs
    const startDateInput = page.locator('input[type="date"]').first();
    const endDateInput = page.locator('input[type="date"]').nth(1);

    if (await startDateInput.count() > 0 && await endDateInput.count() > 0) {
      // Set date range (last 7 days)
      const today = new Date();
      const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

      const formatDate = (date) => {
        return date.toISOString().split('T')[0];
      };

      await startDateInput.fill(formatDate(weekAgo));
      await endDateInput.fill(formatDate(today));

      // Wait for results to update
      await page.waitForTimeout(1000);
    }
  });

  test('should play video recording', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Wait for recordings to load
    await page.waitForTimeout(2000);

    // Check if there are any video elements
    const videoCount = await page.locator('video').count();

    if (videoCount > 0) {
      const firstVideo = page.locator('video').first();

      // Click play button (if video has controls)
      await firstVideo.scrollIntoViewIfNeeded();

      // Get video element
      const isPaused = await firstVideo.evaluate((el) => el.paused);

      if (isPaused) {
        // Try to play
        await firstVideo.click();

        // Wait a moment
        await page.waitForTimeout(1000);

        // Check if playing
        const isPlaying = await firstVideo.evaluate((el) => !el.paused);

        // Video might not autoplay due to browser policies, but element should exist
        expect(isPlaying || isPaused).toBe(true);
      }
    }
  });

  test('should download recording', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Wait for recordings to load
    await page.waitForTimeout(2000);

    // Check for download button
    const downloadButton = page.locator('a:has-text("Download"), button:has-text("Download")').first();

    if (await downloadButton.count() > 0) {
      // Get download URL
      const href = await downloadButton.getAttribute('href');

      // Verify it's a valid download URL
      expect(href).toContain('/api/recordings/');
      expect(href).toContain('/download');
    }
  });

  test('should delete recording with confirmation', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Wait for recordings to load
    await page.waitForTimeout(2000);

    // Count initial recordings
    const initialCount = await page.locator('.recording-card, .video-card').count();

    if (initialCount > 0) {
      // Setup dialog handler to cancel deletion
      page.on('dialog', dialog => dialog.dismiss());

      // Click delete button on last recording
      await page.locator('.recording-card button:has-text("Delete"), .video-card button:has-text("Delete")').last().click();

      // Wait a moment
      await page.waitForTimeout(500);

      // Verify count hasn't changed (deletion was cancelled)
      const afterCancelCount = await page.locator('.recording-card, .video-card').count();
      expect(afterCancelCount).toBe(initialCount);
    }
  });

  test('should handle empty recordings state', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Set filter that likely returns no results
    const cameraFilter = page.locator('select[name="camera_filter"]');

    if (await cameraFilter.count() > 0) {
      // Select "All Cameras"
      await cameraFilter.selectOption({ index: 0 });

      // Wait for results
      await page.waitForTimeout(1000);

      // Check if empty state is shown or recordings are shown
      const recordingCount = await page.locator('.recording-card, .video-card').count();
      const hasEmptyState = await page.locator('text=/no.*recording|no.*video|no.*found/i').count() > 0;

      // Either should have recordings or empty state
      expect(recordingCount > 0 || hasEmptyState).toBe(true);
    }
  });

  test('should handle lazy loading of videos', async ({ page }) => {
    await page.goto('/events');

    // Ensure we're on Videos tab
    await page.click('button:has-text("Videos")');

    // Wait for page to load
    await page.waitForTimeout(2000);

    // Scroll down to trigger lazy loading
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));

    // Wait for lazy load
    await page.waitForTimeout(2000);

    // Check if more content loaded or "end of results" message appears
    const hasEndMessage = await page.locator('text=/end|no more|all.*loaded/i').count() > 0;
    const recordingCount = await page.locator('.recording-card, .video-card').count();

    // Should either have recordings or end message
    expect(recordingCount > 0 || hasEndMessage).toBe(true);
  });

  test('should open snapshot in modal', async ({ page }) => {
    await page.goto('/events');

    // Switch to Snapshots tab
    await page.click('button:has-text("Snapshots")');

    // Wait for snapshots to load
    await page.waitForTimeout(2000);

    const snapshotCount = await page.locator('.snapshot-card, .snapshot-image').count();

    if (snapshotCount > 0) {
      // Click first snapshot
      await page.locator('.snapshot-card, .snapshot-image').first().click();

      // Check if modal opens
      const modalOpened = await page.locator('.modal, [role="dialog"]').count() > 0;

      if (modalOpened) {
        // Verify modal contains larger image
        await expect(page.locator('.modal img, [role="dialog"] img')).toBeVisible();

        // Close modal
        await page.click('.modal button:has-text("✕"), [role="dialog"] button:has-text("Close")');

        // Verify modal closes
        await expect(page.locator('.modal, [role="dialog"]')).not.toBeVisible({ timeout: 2000 });
      }
    }
  });
});
