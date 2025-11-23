// Copyright (c) 2025 Mikel Smart
// This file is part of OpenEye-OpenCV_Home_Security

/**
 * E2E Test Helper: Page Object Models
 * Provides reusable page interaction patterns
 */

/**
 * Dashboard Page Object
 */
export class DashboardPage {
  constructor(page) {
    this.page = page;
    this.cameraGrid = page.locator('[data-testid="camera-grid"]');
    this.statsPanel = page.locator('[data-testid="stats-panel"]');
  }

  async goto() {
    await this.page.goto('/dashboard');
    await this.page.waitForLoadState('networkidle');
  }

  async getCameraCount() {
    const cameras = await this.cameraGrid.locator('.camera-card').count();
    return cameras;
  }

  async clickCamera(cameraId) {
    await this.page.click(`[data-camera-id="${cameraId}"]`);
  }

  async waitForStats() {
    await this.statsPanel.waitFor({ state: 'visible' });
  }
}

/**
 * Camera Management Page Object
 */
export class CameraManagementPage {
  constructor(page) {
    this.page = page;
    this.addButton = page.locator('button:has-text("Add Camera")');
    this.cameraList = page.locator('[data-testid="camera-list"]');
  }

  async goto() {
    await this.page.goto('/cameras');
    await this.page.waitForLoadState('networkidle');
  }

  async addCamera(cameraData) {
    await this.addButton.click();

    // Wait for modal
    await this.page.waitForSelector('[role="dialog"]');

    // Fill form
    await this.page.fill('input[name="camera_id"]', cameraData.camera_id);
    await this.page.fill('input[name="name"]', cameraData.name);
    await this.page.fill('input[name="source"]', cameraData.source);

    // Submit
    await this.page.click('button:has-text("Save")');

    // Wait for modal to close
    await this.page.waitForSelector('[role="dialog"]', { state: 'hidden' });
  }

  async deleteCamera(cameraId) {
    // Click delete button for specific camera
    await this.page.click(`[data-camera-id="${cameraId}"] button:has-text("Delete")`);

    // Confirm deletion
    await this.page.click('button:has-text("Confirm")');
  }

  async getCameraByName(name) {
    return await this.page.locator(`text=${name}`);
  }
}

/**
 * Face Management Page Object
 */
export class FaceManagementPage {
  constructor(page) {
    this.page = page;
    this.uploadButton = page.locator('button:has-text("Upload Faces")');
    this.peopleList = page.locator('[data-testid="people-list"]');
  }

  async goto() {
    await this.page.goto('/faces');
    await this.page.waitForLoadState('networkidle');
  }

  async uploadFaces(files) {
    await this.uploadButton.click();

    // Wait for file input
    const fileInput = await this.page.locator('input[type="file"]');
    await fileInput.setInputFiles(files);

    // Submit upload
    await this.page.click('button:has-text("Upload")');
  }

  async getPeopleCount() {
    return await this.peopleList.locator('.person-card').count();
  }

  async clickPerson(personName) {
    await this.page.click(`text=${personName}`);
  }
}

/**
 * Recordings Page Object
 */
export class RecordingsPage {
  constructor(page) {
    this.page = page;
    this.recordingsList = page.locator('[data-testid="recordings-list"]');
    this.videoPlayer = page.locator('video');
  }

  async goto() {
    await this.page.goto('/recordings');
    await this.page.waitForLoadState('networkidle');
  }

  async getRecordingsCount() {
    return await this.recordingsList.locator('.recording-card').count();
  }

  async playRecording(index = 0) {
    const recordings = await this.recordingsList.locator('.recording-card');
    await recordings.nth(index).click();

    // Wait for video player
    await this.videoPlayer.waitFor({ state: 'visible' });
  }

  async deleteRecording(index = 0) {
    const recordings = await this.recordingsList.locator('.recording-card');
    await recordings.nth(index).locator('button:has-text("Delete")').click();

    // Confirm deletion
    await this.page.click('button:has-text("Confirm")');
  }

  async filterByCamera(cameraId) {
    await this.page.selectOption('select[name="camera"]', cameraId);
    await this.page.waitForLoadState('networkidle');
  }
}

/**
 * Settings Page Object
 */
export class SettingsPage {
  constructor(page) {
    this.page = page;
    this.saveButton = page.locator('button:has-text("Save Settings")');
  }

  async goto() {
    await this.page.goto('/settings');
    await this.page.waitForLoadState('networkidle');
  }

  async toggleSetting(settingName) {
    await this.page.click(`input[name="${settingName}"]`);
  }

  async updateTextSetting(settingName, value) {
    await this.page.fill(`input[name="${settingName}"]`, value);
  }

  async saveSettings() {
    await this.saveButton.click();

    // Wait for success message
    await this.page.waitForSelector('text=Settings saved successfully', { timeout: 5000 });
  }
}

/**
 * Sidebar Navigation Object
 */
export class Sidebar {
  constructor(page) {
    this.page = page;
  }

  async navigateTo(pageName) {
    await this.page.click(`nav a:has-text("${pageName}")`);
    await this.page.waitForLoadState('networkidle');
  }

  async logout() {
    await this.page.click('button:has-text("Logout")');
    await this.page.waitForURL('**/');
  }
}

/**
 * Modal Dialog Object
 */
export class Modal {
  constructor(page) {
    this.page = page;
    this.dialog = page.locator('[role="dialog"]');
  }

  async waitForOpen() {
    await this.dialog.waitFor({ state: 'visible' });
  }

  async waitForClose() {
    await this.dialog.waitFor({ state: 'hidden' });
  }

  async clickButton(buttonText) {
    await this.dialog.locator(`button:has-text("${buttonText}")`).click();
  }

  async fillInput(inputName, value) {
    await this.dialog.locator(`input[name="${inputName}"]`).fill(value);
  }

  async getTitle() {
    return await this.dialog.locator('h2, h3').first().textContent();
  }
}
