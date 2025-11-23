# OpenEye E2E Tests (v3.9.0)

End-to-end testing suite for OpenEye using Playwright.

## Overview

This directory contains comprehensive E2E tests that verify critical user flows:

- **Authentication** - Login, logout, JWT token refresh, 2FA, account lockout
- **Security** - Rate limiting, password reset, token validation (v3.9.0)
- **Camera Management** - Add, start, stop, delete cameras, live view
- **Face Management** - Upload faces, detection history, clustering (v3.6.0)
- **Recordings & Snapshots** - Browse, filter, playback, download
- **System Settings** - Configuration, notifications, themes, performance

## Running Tests

### Prerequisites

1. Backend server must be running on `http://localhost:8000`
2. Test admin account must exist:
   - Username: `admin`
   - Password: `admin`

### Commands

```bash
# Run all tests (headless)
npm run test:e2e

# Run tests with visible browser
npm run test:e2e:headed

# Run tests in debug mode (step through with inspector)
npm run test:e2e:debug

# Run tests with interactive UI
npm run test:e2e:ui

# View last test report
npm run test:e2e:report
```

### Running Specific Tests

```bash
# Run only authentication tests
npx playwright test auth.spec.js

# Run only camera tests
npx playwright test cameras.spec.js

# Run only recordings tests
npx playwright test recordings.spec.js

# Run tests matching a pattern
npx playwright test --grep "should login"
```

## Test Structure

```
e2e/
├── README.md                 # This file
├── helpers/                  # Reusable test helpers (v3.9.0)
│   ├── auth-helper.js       # Authentication utilities
│   └── page-objects.js      # Page object models
├── fixtures/                 # Test fixtures and shared setup
│   ├── auth.js              # Legacy auth utilities
│   ├── cameras.js           # Camera management utilities
│   └── test-fixtures.js     # Extended fixtures (v3.9.0)
├── auth.spec.js             # Authentication tests (13 tests)
├── security-v3.9.0.spec.js  # Security features tests (17 tests)
├── cameras.spec.js          # Camera management tests (12 tests)
├── faces.spec.js            # Face management tests (17 tests)
├── recordings.spec.js       # Recordings & snapshots tests (11 tests)
├── settings.spec.js         # System settings tests (22 tests)
└── two-way-audio.spec.js    # Two-way audio tests (13 tests)
```

## Test Fixtures

Fixtures provide reusable functions for common operations:

### Authentication (`fixtures/auth.js`)

```javascript
import { loginAs, logout, setupAuth, cleanupAuth } from './fixtures/auth.js';

// Login as admin
await loginAs(page, 'admin', 'admin');

// Logout
await logout(page);

// Setup auth for beforeEach
await setupAuth(page);

// Cleanup auth for afterEach
await cleanupAuth(page);
```

### Cameras (`fixtures/cameras.js`)

```javascript
import { createMockCamera, deleteCamera, startCamera, stopCamera } from './fixtures/cameras.js';

// Create test camera
await createMockCamera(page, 'test_camera_1', 'Test Camera');

// Start camera
await startCamera(page, 'test_camera_1');

// Stop camera
await stopCamera(page, 'test_camera_1');

// Delete camera
await deleteCamera(page, 'test_camera_1');
```

## Writing New Tests

### Basic Test Template

```javascript
import { test, expect } from '@playwright/test';
import { setupAuth, cleanupAuth } from './fixtures/auth.js';

test.describe('My Feature', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page); // Login before each test
  });

  test.afterEach(async ({ page }) => {
    await cleanupAuth(page); // Cleanup after each test
  });

  test('should do something', async ({ page }) => {
    await page.goto('/my-page');

    // Your test steps
    await expect(page.locator('h1')).toContainText('My Page');
  });
});
```

### Best Practices

1. **Use fixtures** - Don't duplicate login/setup code
2. **Clean up after tests** - Delete test data in afterEach
3. **Use unique IDs** - Use timestamps for test cameras: `test_camera_${Date.now()}`
4. **Wait for elements** - Use `waitForSelector` instead of fixed delays
5. **Handle dialogs** - Use `page.on('dialog')` for confirmations
6. **Check visibility** - Use `toBeVisible()` instead of `toBeTruthy()`
7. **Use semantic selectors** - Prefer `text=Login` over CSS selectors

## CI/CD Integration

Tests run automatically on:
- **Push to main/develop** branches
- **Pull requests** to main
- **Manual trigger** via GitHub Actions UI

### GitHub Actions Workflow

Location: `.github/workflows/e2e-tests.yml`

Features:
- Runs on Ubuntu with Python 3.11 and Node.js 20
- Installs all dependencies (Python, Node, Playwright, system libs)
- Sets up test database with admin user
- Starts backend server
- Runs E2E tests
- Uploads reports, videos, and screenshots on failure

## Troubleshooting

### Tests fail with "connection refused"

**Problem**: Backend server not running

**Solution**:
```bash
cd opencv_surveillance
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Tests fail with "admin user not found"

**Problem**: Test database not set up

**Solution**:
```bash
cd opencv_surveillance
python -c "from backend.database.session import Base, engine; Base.metadata.create_all(bind=engine)"

# Create admin user
python -c "
from backend.database.session import SessionLocal
from backend.database.models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
db = SessionLocal()

user = User(
    username='admin',
    email='admin@openeye.local',
    hashed_password=pwd_context.hash('admin'),
    is_active=True,
    role='admin'
)
db.add(user)
db.commit()
db.close()
"
```

### Tests are flaky

**Problem**: Race conditions or timing issues

**Solution**:
- Use `waitForSelector` instead of `waitForTimeout`
- Increase timeout for slow operations
- Use `page.waitForLoadState('networkidle')` after navigation

### Browser doesn't close after test

**Problem**: Playwright process hung

**Solution**:
```bash
# Kill all Playwright processes
pkill -f playwright
```

## Test Coverage

Current E2E test coverage (v3.10.0):

- ✅ **Authentication** - Login, logout, token refresh, validation (13 tests)
- ✅ **Security (v3.9.0)** - Account lockout, rate limiting, password reset, 2FA, audit logging (17 tests)
- ✅ **Camera Management** - CRUD operations, start/stop, live view, settings (12 tests)
- ✅ **Face Management** - Upload, detection history, clustering, identification (17 tests)
- ✅ **Recordings** - Browse, filter, playback, lazy loading, download (11 tests)
- ✅ **System Settings** - Configuration, notifications, themes, performance, user management (22 tests)
- ✅ **Two-Way Audio (v3.10.0)** - Modal integration, WebRTC connection, audio controls, API endpoints (13 tests)

**Total**: 101 E2E tests across 7 test files

## Performance

- **Test execution time**: ~2-3 minutes for all tests
- **CI/CD runtime**: ~5-7 minutes (including setup)
- **Browser**: Chromium (default), Firefox/Safari optional

## Test Helpers & Page Objects (v3.9.0)

### Authentication Helper (`helpers/auth-helper.js`)

```javascript
import { login, logout, loginWith2FA, clearAuth, getAuthToken } from './helpers/auth-helper.js';

// Basic login
await login(page, 'admin', 'admin');

// Login with 2FA
await loginWith2FA(page, 'user', 'password', '123456');

// Logout
await logout(page);

// Clear auth data
await clearAuth(page);

// Get stored token
const token = await getAuthToken(page);
```

### Page Objects (`helpers/page-objects.js`)

```javascript
import { DashboardPage, CameraManagementPage, SettingsPage } from './helpers/page-objects.js';

// Use page objects for cleaner tests
const dashboard = new DashboardPage(page);
await dashboard.goto();
const cameraCount = await dashboard.getCameraCount();

const cameras = new CameraManagementPage(page);
await cameras.addCamera({ camera_id: 'test', name: 'Test Camera', source: 'mock' });
```

### Extended Fixtures (`fixtures/test-fixtures.js`)

```javascript
import { test, expect, testData, utils } from './fixtures/test-fixtures.js';

// Use extended test with authenticated page
test('my test', async ({ authenticatedPage }) => {
  // Already logged in!
  await authenticatedPage.goto('/dashboard');
});

// Use test data generators
const camera = testData.camera({ name: 'My Camera' });
const user = testData.user({ role: 'admin' });

// Use utilities
await utils.waitForNotification(page, 'Success');
await utils.screenshot(page, 'test-result');
```

## Future Improvements

1. **Visual Regression Testing** - Playwright snapshots for UI consistency
2. **API Testing** - Direct API endpoint testing alongside UI tests
3. **Mobile Viewport Testing** - Test responsive design on mobile sizes
4. **Cross-Browser Matrix** - Expand to Firefox, Safari, WebKit
5. **Performance Testing** - Lighthouse integration for performance metrics
6. **Accessibility Testing** - axe-core integration for WCAG compliance
7. **Real 2FA Testing** - TOTP code generation for complete 2FA flow testing
8. **Video Upload Testing** - Test file uploads with actual media files

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright CI/CD Guide](https://playwright.dev/docs/ci)
- [OpenEye Testing Guide](../../TESTING_GUIDE.md)
