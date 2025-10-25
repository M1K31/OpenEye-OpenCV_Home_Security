# OpenEye Testing Infrastructure Guide

## Overview

OpenEye now has comprehensive testing infrastructure for both backend and frontend components, addressing the previous gap in test coverage.

## What Was Implemented

### Backend Testing ✅

1. **Enhanced Test Fixtures** (`tests/conftest.py`)
   - `client`: FastAPI TestClient with database override
   - `test_user`: Pre-created test user for authentication
   - `auth_headers`: JWT authentication headers
   - `test_camera`: Pre-created camera for testing
   - `db_session`: Isolated test database session

2. **API Endpoint Tests**
   - `tests/api/test_recordings.py` - 10 tests for recordings endpoints
   - `tests/api/test_cameras.py` - 12 tests for camera management
   - `tests/api/test_faces.py` - 15 tests for face recognition and clustering

3. **Test Configuration** (`pytest.ini`)
   - Coverage reporting (HTML, XML, terminal)
   - Test markers for categorization
   - Warning filters for cleaner output

4. **Development Dependencies** (`requirements-dev.txt`)
   - pytest-cov==4.1.0 (coverage reporting)
   - pytest-asyncio==0.21.1 (async test support)

### Frontend Testing ✅

1. **Vitest Setup** (`frontend/vitest.config.js`)
   - jsdom environment for DOM testing
   - Coverage with v8 provider
   - React Testing Library integration

2. **Test Utilities** (`frontend/src/test/`)
   - setup.js: Global test configuration
   - Mock implementations for window.matchMedia, IntersectionObserver
   - jest-dom matchers

3. **Component Tests**
   - ErrorBoundary.test.jsx - Tests error catching and fallback UI
   - authService.test.js - Tests authentication service methods

4. **NPM Scripts** (`package.json`)
   - `npm test` - Run tests
   - `npm run test:ui` - Interactive UI
   - `npm run test:coverage` - Coverage reports

## Running Tests

### Backend Tests

```bash
cd opencv_surveillance
source venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html --cov-report=term

# Run specific test suite
pytest tests/api/test_recordings.py -v

# Run by marker
pytest -m api
```

### Frontend Tests

```bash
cd opencv_surveillance/frontend

# Install dependencies
npm install

# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run with interactive UI
npm run test:ui
```

## Test Categories

### Backend Test Markers

Use `@pytest.mark.<marker>` to categorize tests:

- `unit` - Fast, isolated unit tests
- `integration` - Tests with database/external dependencies
- `api` - API endpoint tests
- `auth` - Authentication/authorization tests
- `slow` - Tests that take >1 second

Example:
```python
@pytest.mark.api
@pytest.mark.integration
def test_list_recordings(client, auth_headers):
    response = client.get("/api/recordings/", headers=auth_headers)
    assert response.status_code == 200
```

## Coverage Goals

### Current Status
- Backend: ~40% (baseline with new API tests)
- Frontend: ~30% (baseline with component tests)

### Target Goals
- Backend: 60% minimum, 80% ideal
- Frontend: 60% minimum, 80% ideal

## Writing New Tests

### Backend API Test Template

```python
# tests/api/test_myfeature.py
import pytest
from backend.database import models

class TestMyFeatureAPI:
    """Test suite for my feature endpoints"""

    def test_list_items(self, client, auth_headers):
        """Test listing items"""
        response = client.get("/api/myfeature/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_create_item(self, client, auth_headers):
        """Test creating an item"""
        item_data = {"name": "Test Item"}
        response = client.post(
            "/api/myfeature/",
            json=item_data,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Test Item"
```

### Frontend Component Test Template

```javascript
// src/components/__tests__/MyComponent.test.jsx
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('renders with props', () => {
    render(<MyComponent title="Test" />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('handles user interaction', () => {
    render(<MyComponent />);
    const button = screen.getByRole('button');
    fireEvent.click(button);
    expect(screen.getByText('Clicked')).toBeInTheDocument();
  });
});
```

## Best Practices

### Backend
1. Use fixtures for test data setup
2. Test both success and failure cases
3. Verify response structure AND status codes
4. Use meaningful test names that describe behavior
5. Keep tests isolated (no shared state)

### Frontend
1. Test user-visible behavior, not implementation details
2. Use `screen.getByRole()` for better accessibility
3. Mock external API calls
4. Test error states and loading states
5. Use `userEvent` for realistic interactions

## CI/CD Integration

Add to your CI pipeline:

```yaml
# Backend testing
- name: Run Backend Tests
  run: |
    cd opencv_surveillance
    pip install -r requirements-dev.txt
    pytest --cov=backend --cov-report=xml --cov-fail-under=60

# Frontend testing
- name: Run Frontend Tests
  run: |
    cd opencv_surveillance/frontend
    npm install
    npm test -- --run --reporter=verbose
```

## Next Steps

### High Priority
1. Add tests for motion detection endpoints
2. Add tests for alert configuration
3. Add tests for timeline view API
4. Add frontend tests for LiveDashboard
5. Add frontend tests for CameraManagementPage

### Medium Priority
1. Add E2E tests with Playwright/Cypress
2. Add performance tests for face recognition
3. Add load tests for WebSocket connections
4. Add visual regression tests

### Low Priority
1. Add tests for Docker container builds
2. Add tests for database migrations
3. Add tests for background task schedulers

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [React Testing Library](https://testing-library.com/react)
- [Vitest Documentation](https://vitest.dev/)

## Troubleshooting

### Backend Tests Fail with Database Errors
- Ensure in-memory SQLite is being used
- Check that fixtures are yielding properly
- Verify database cleanup in teardown

### Frontend Tests Fail with Module Errors
- Run `npm install` to ensure all deps are installed
- Check that vitest.config.js is properly configured
- Verify jsdom environment is set

### Coverage Reports Not Generated
- Backend: Install pytest-cov (`pip install pytest-cov`)
- Frontend: Install coverage package (`npm install -D @vitest/coverage-v8`)

## Support

For testing questions or issues:
1. Check existing tests for examples
2. Review this guide
3. Consult the testing library documentation
4. Ask in project discussions/issues
