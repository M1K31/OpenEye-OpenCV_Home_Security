# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenEye is a 100% free, self-hosted AI-powered surveillance system using OpenCV and face recognition. The system consists of:

- **Backend**: FastAPI (Python 3.11+) with OpenCV, face_recognition (dlib), SQLAlchemy
- **Frontend**: React 18 with Vite, React Router, modern CSS with 8pt grid system
- **Database**: SQLite (default) or PostgreSQL (production)
- **Deployment**: Docker (recommended) or native Python installation

**Current Version**: 3.6.0

## Development Commands

### Backend Development

```bash
# Navigate to backend directory
cd opencv_surveillance

# Activate virtual environment (required for all commands)
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate    # Windows

# Start development server with hot reload
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests
pytest

# Run specific test file
pytest tests/test_face_recognition.py

# Database migrations (automated with Alembic)
# View current migration status
python3 -m alembic current

# Create new migration after model changes
python3 -m alembic revision --autogenerate -m "Description of changes"

# Apply migrations (also runs automatically on app startup)
python3 -m alembic upgrade head

# View migration history
python3 -m alembic history

# Rollback to previous migration (use with caution)
python3 -m alembic downgrade -1

# System audit (check for API/class mismatches)
python scripts/audit-system.py
```

### Frontend Development

```bash
# Navigate to frontend directory
cd opencv_surveillance/frontend

# Install dependencies
npm install

# Development server (with Vite)
npm run dev

# Production build (outputs to dist/)
npm run build

# Preview production build
npm run preview
```

### Full Stack Development

```bash
# From repository root - start complete stack natively
./start-local.sh

# Build and deploy Docker image
./deploy.sh

# Automated production setup (creates venv, installs deps, generates keys, builds frontend)
./setup-production.sh

# Graceful shutdown
./stop-server.sh

# Force kill (emergency)
./kill-server.sh

# Complete uninstall with backup options
./uninstall.sh
```

## Architecture

### Backend Structure (`opencv_surveillance/backend/`)

#### Core Modules (`backend/core/`)
These modules contain the business logic and are stateful singletons:

- **camera_manager.py**: Central camera registry. Manages all camera instances (RTSP, USB, Mock). Access via `manager` singleton.
- **face_recognition.py**: Stateless face recognition using `get_face_manager()` factory function. Loads known faces from filesystem.
- **face_clustering.py**: AI-powered face grouping using DBSCAN. Groups similar unknown faces for batch identification.
- **motion_detector.py**: OpenCV MOG2 background subtraction for motion detection.
- **recorder.py**: Video recording with H.264 codec. Manages recording lifecycle per camera.
- **alert_manager.py**: Alert throttling and notification dispatch.
- **alert_notification_system.py**: Multi-channel notifications (email, SMS, push, webhooks).
- **cloud_storage_system.py**: Upload recordings to S3/GCS/Azure/MinIO with background threads.
- **camera_discovery.py**: Auto-discover USB and network (ONVIF) cameras.
- **automation_engine.py**: Person-based automation rules and triggers.
- **websocket_manager.py**: WebSocket connection management for real-time updates.
- **statistics_broadcaster.py**: Background task broadcasting camera stats via WebSocket every 2 seconds.
- **clustering_scheduler.py**: Automated background scheduler for face clustering (configurable interval and threshold).
- **audit_logger.py**: Enhanced security audit logging with 42 event types, JSONL format.
- **two_factor_auth.py**: TOTP-based 2FA authentication system.
- **two_way_audio_system.py**: Bidirectional audio communication with cameras.
- **performance.py**: Performance monitoring and optimization utilities.
- **paths.py**: Centralized path management (PathManager singleton) for all data directories.

#### API Routes (`backend/api/routes/`)
FastAPI router modules - all prefixed with `/api`:

- **cameras.py**: Camera CRUD, start/stop, stream endpoints
- **faces.py**: Upload faces, train model, delete faces
- **face_history.py**: Query face detection events with pagination
- **clusters.py**: Face clustering API - list clusters, identify clusters
- **alerts.py**: Alert configuration and history
- **recordings.py**: List, download, stream, delete recordings
- **motion_events.py**: Motion detection event history
- **analytics.py**: Advanced analytics and statistics
- **discovery.py**: Camera discovery (USB, network scan)
- **settings.py**: System settings (CRUD with validation)
- **automations.py**: Automation rules API
- **setup.py**: First-run setup wizard
- **users.py**: Authentication (login, token refresh)
- **websockets.py**: WebSocket endpoints for real-time stats
- **timeline.py**: Timeline playback and video navigation
- **two_way_audio.py**: Two-way audio streaming endpoints
- **metrics.py**: Performance metrics and monitoring
- **notification_providers.py**: Notification provider configuration (encrypted credentials)
- **two_factor_auth.py**: 2FA setup, verification, and management

**IMPORTANT Route Ordering**: In `main.py`, specific routes MUST be registered before generic ones:
```python
# ✅ CORRECT ORDER
app.include_router(discovery.router, prefix="/api", tags=["Camera Discovery"])  # /api/cameras/discover
app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])    # /api/cameras/{id}
```

#### Database (`backend/database/`)

- **models.py**: Main models (User, FaceDetectionEvent, FaceCluster, RecordingEvent, Camera, MotionDetectionEvent, SystemLog, SystemSettings, AutomationRule)
- **alert_models.py**: Alert-specific models (AlertConfiguration, NotificationLog, AlertThrottle)
- **crud.py**: Database operations - centralized CRUD functions (prefer using this over direct SQLAlchemy)
- **session.py**: Database engine and session factory

**Database Migrations**: The project uses Alembic for automatic database migrations. Migrations run automatically on app startup via `main.py:startup_event()`. Migration files are stored in `alembic/versions/`. To create a new migration after modifying models, run: `python3 -m alembic revision --autogenerate -m "Description"`

**Database Philosophy**: Use `crud.py` functions for consistency. Add new operations to crud.py rather than inline SQLAlchemy queries.

#### Middleware (`backend/middleware/`)

Security and performance middleware (applied in `main.py`):

- **rate_limiter.py**: Legacy global rate limiter (deprecated in favor of EndpointRateLimiter)
- **endpoint_rate_limiter.py**: Per-endpoint rate limiting with category-based limits (v3.6.0)
- **csrf_protection.py**: CSRF protection using double-submit cookie pattern (v3.6.0)
- **security.py**: Security headers, IP whitelist, SQL injection protection
- **performance.py**: Performance monitoring middleware
- **query_profiler.py**: Database query profiling (optional, enable via env var)

**Middleware Order**: Middleware is applied in reverse order in FastAPI. Security middleware should be added first (executed last) to ensure all requests are validated.

#### Integrations (`backend/integrations/`)

- **homeassistant_integration.py**: MQTT integration with Home Assistant
- **homekit_integration.py**: HomeKit bridge (HAP-python)
- **mqtt_integration.py**: Generic MQTT client
- **webhook_system.py**: Webhook notifications

### Frontend Structure (`opencv_surveillance/frontend/src/`)

#### Pages (`src/pages/`)
Main application views:

- **DashboardPage.jsx**: Live camera grid with real-time stats via WebSocket
- **CameraManagementPage.jsx**: Camera CRUD with discovery integration
- **FaceManagementPage.jsx**: Upload faces, view detection history, face clustering
- **RecordingsPage.jsx**: Video playback, download, search
- **AlertSettingsPage.jsx**: Configure multi-channel notifications
- **SystemSettingsPage.jsx**: System configuration (paths, display modes, camera toggles)
- **ThemeSelectorPage.jsx**: 9 theme options (Default, Superman, Batman, etc.)
- **FirstRunSetup.jsx**: Wizard for initial admin account creation
- **FaceClusteringPage.jsx**: AI-powered face clustering with batch identification
- **TimelineView.jsx**: Interactive video timeline with event markers and playback controls (v3.5.6+)
- **NotificationSettingsPage.jsx**: Notification provider configuration with encrypted credentials
- **PerformanceDashboard.jsx**: Real-time performance metrics and system monitoring (v3.6.0)
- **AutomationsPage.jsx**: Person-based automation rules and triggers

#### Components

- **LiveDashboard.jsx**: Real-time camera feed component with motion/face overlays
- **HelpButton.jsx**: Context-sensitive help system (36+ entries)
- **Sidebar.jsx**: Navigation with theme switching
- **ClusterCard.jsx**: Face cluster display with thumbnail grid
- **ClusterDetailModal.jsx**: Modal for viewing cluster details and identification
- **DeleteClusterModal.jsx**: Confirmation modal for cluster deletion
- **Pagination.jsx**: Reusable pagination component with page size controls

#### Services

- **WebSocketService.js**: WebSocket client for real-time statistics (connects to `/ws/statistics`)
- **authService.js**: JWT token management, automatic refresh on 401
- **apiClient.js**: Axios wrapper with auth interceptors
- **clusteringService.js**: Face clustering API client (statistics, cluster management)
- **notificationService.js**: Notification provider configuration API client

#### Styling

- **themes.css**: 9 complete theme definitions with CSS variables
- **global-theme.css**: Theme-agnostic global styles
- **8pt Grid System**: All spacing uses multiples of 8px (margin, padding, gaps)
- **44px Touch Targets**: Minimum button/interactive element size per Apple HIG

### Key Design Patterns

#### Stateless Face Recognition
```python
# ✅ CORRECT - Use factory function
from backend.core.face_recognition import get_face_manager
face_manager = get_face_manager(faces_folder="faces")
results = face_manager.recognize_faces(frame)

# ❌ WRONG - Don't instantiate directly
from backend.core.face_recognition import FaceRecognitionManager
manager = FaceRecognitionManager("faces")  # Don't do this
```

#### Camera Manager Singleton
```python
# ✅ CORRECT - Use global manager instance
from backend.core.camera_manager import manager as camera_manager
camera_manager.add_camera(camera_id="front_door", ...)
camera = camera_manager.get_camera("front_door")

# ❌ WRONG - Don't create new instances
from backend.core.camera_manager import CameraManager
manager = CameraManager()  # Don't do this
```

#### Database Access via CRUD
```python
# ✅ CORRECT - Use crud functions
from backend.database import crud
camera = crud.get_camera_by_id(db, camera_id="front_door")

# ❌ AVOID - Direct SQLAlchemy queries
from backend.database.models import Camera
camera = db.query(Camera).filter(Camera.camera_id == "front_door").first()
```

#### Graceful Shutdown Sequence
The app uses an 8-step shutdown process (see `main.py:shutdown_event`):
1. Stop face clustering scheduler
2. Stop statistics broadcaster (WebSocket updates)
3. Close all WebSocket connections
4. Stop all cameras and release resources
5. Skip face recognition (stateless)
6. Stop cloud storage upload threads
7. Close database connections
8. Cancel remaining async tasks

**IMPORTANT**: Daemon threads and background tasks MUST be properly stopped to prevent orphaned processes.

#### Centralized Path Management
```python
# ✅ CORRECT - Use PathManager singleton
from backend.core.paths import paths
snapshot_path = paths.snapshots_dir / "camera_id" / "snapshot.jpg"
recordings = paths.recordings_dir / "camera_id"

# Update paths dynamically (from database settings)
paths.update_paths(recordings_dir="/custom/recordings", faces_dir="/custom/faces")

# ❌ WRONG - Don't hardcode paths
snapshot_path = "data/snapshots/camera_id/snapshot.jpg"  # Don't do this
```

**PathManager features**:
- Automatic directory creation on access
- Configurable paths via database settings
- Thread-safe singleton pattern
- Centralized path updates across entire app

## File System Paths

### Default Directory Structure
```
opencv_surveillance/
├── backend/           # FastAPI application
├── frontend/          # React application
├── data/
│   ├── snapshots/     # Camera snapshots (motion/face events)
│   └── thumbnails/    # Video thumbnails
├── faces/             # Known face images (training data)
├── recordings/        # Motion-triggered recordings
├── models/            # Face detection models (dlib)
├── venv/              # Python virtual environment
└── surveillance.db    # SQLite database
```

### Configurable Paths
Users can configure custom paths via System Settings:
- `recordings_path` (default: "recordings")
- `faces_path` (default: "faces")

**Mount Order**: Static file mounts in `main.py` MUST be defined BEFORE the catch-all SPA route to ensure proper precedence.

## Environment Variables

Create `.env` in `opencv_surveillance/` directory:

```bash
# Security (REQUIRED)
SECRET_KEY=<random-hex-64-chars>
JWT_SECRET_KEY=<random-hex-64-chars>
NOTIFICATION_ENCRYPTION_KEY=<fernet-key>  # v3.6.0: For encrypted notification credentials
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database (optional - defaults to SQLite)
DATABASE_URL=sqlite:///./surveillance.db
# DATABASE_URL=postgresql://user:pass@localhost:5432/openeye

# CORS (optional)
CORS_ORIGINS=http://localhost:8000,http://localhost:3000

# Features (optional - all enabled by default)
ENABLE_MOTION_DETECTION=true
ENABLE_FACE_RECOGNITION=true
ENABLE_RECORDING=true

# Performance Monitoring (optional - v3.6.0)
ENABLE_QUERY_PROFILING=false
SLOW_QUERY_THRESHOLD_MS=100

# Logging
LOG_LEVEL=INFO
```

Generate secret keys:
```bash
# SECRET_KEY and JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# NOTIFICATION_ENCRYPTION_KEY (Fernet key)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Note**: The automated setup script (`setup-production.sh`) generates all required keys automatically.

## Testing

OpenEye has comprehensive testing infrastructure for both backend (Python/FastAPI) and frontend (React/Vitest).

### Backend Testing (`opencv_surveillance/tests/`)

#### Test Structure
```
tests/
├── conftest.py                 # Shared fixtures (client, db_session, auth_headers)
├── api/                        # API endpoint tests
│   ├── test_recordings.py      # Recordings API tests
│   ├── test_cameras.py         # Camera API tests
│   └── test_faces.py           # Face recognition API tests
├── test_face_recognition.py    # Unit tests for face recognition
├── test_user_*.py              # Authentication tests
└── integration_testing_utils.py
```

#### Running Backend Tests
```bash
cd opencv_surveillance
source venv/bin/activate

# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/api/test_recordings.py -v

# Run specific test class
pytest tests/api/test_recordings.py::TestRecordingsAPI -v

# Run with coverage report
pytest --cov=backend --cov-report=html --cov-report=term

# Run tests by marker
pytest -m api        # API tests only
pytest -m unit       # Unit tests only
pytest -m integration # Integration tests only
```

#### Test Markers
Use pytest markers to categorize tests:
- `@pytest.mark.unit` - Fast unit tests
- `@pytest.mark.integration` - Integration tests (database, API)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.slow` - Slow tests
- `@pytest.mark.auth` - Authentication tests

#### Writing Backend Tests
```python
# Example API test using fixtures
def test_list_recordings(client, auth_headers):
    response = client.get("/api/recordings/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "recordings" in data
    assert "total" in data
```

### Frontend Testing (`opencv_surveillance/frontend/`)

#### Test Structure
```
frontend/src/
├── components/__tests__/       # Component tests
├── services/__tests__/         # Service/utility tests
└── test/
    ├── setup.js                # Global test setup
    └── README.md               # Frontend testing guide
```

#### Running Frontend Tests
```bash
cd opencv_surveillance/frontend

# Install test dependencies
npm install

# Run all tests
npm test

# Run tests in watch mode (reruns on file changes)
npm test -- --watch

# Run tests with coverage
npm run test:coverage

# Run tests with interactive UI
npm run test:ui
```

#### Writing Frontend Tests
```javascript
// Component test example
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MyComponent from '../MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });
});
```

### Coverage Reports

Backend coverage reports are generated in `htmlcov/index.html` after running:
```bash
pytest --cov=backend --cov-report=html
```

Frontend coverage reports are generated in `coverage/index.html` after running:
```bash
npm run test:coverage
```

### Continuous Integration

Tests should be run in CI/CD pipelines before deployment:
```bash
# Backend
pytest --cov=backend --cov-fail-under=60

# Frontend
npm test -- --run --reporter=verbose
```

## Database Migrations

The project uses **Alembic** for systematic database schema versioning and migrations. This eliminates the need for manual migration scripts and provides automatic upgrades during deployments.

### How It Works

1. **Automatic on Startup**: Migrations run automatically when the app starts (see `backend/main.py:startup_event()`)
2. **Fallback Safety**: If migrations fail, the app falls back to legacy `create_all()` for compatibility
3. **SQLite Batch Mode**: Configured to support ALTER operations on SQLite databases
4. **Version Tracking**: Alembic tracks which migrations have been applied in the `alembic_version` table

### Creating New Migrations

When you modify database models, create a new migration:

```bash
# After editing models.py or alert_models.py
python3 -m alembic revision --autogenerate -m "Add new_column to users table"

# Review the generated migration in alembic/versions/
# Edit if needed (autogenerate isn't perfect)

# Apply the migration
python3 -m alembic upgrade head
```

### Important Notes

- **Review Generated Migrations**: Alembic's autogenerate is smart but not perfect. Always review migration files before committing.
- **SQLite Limitations**: SQLite has limited ALTER TABLE support. Use batch mode (already configured) for complex changes.
- **Baseline Migration**: The initial migration (`79605a54272e`) is a no-op baseline that marks existing schemas as up-to-date.
- **No Manual Scripts**: Avoid creating manual migration scripts in `backend/database/migrations/` - use Alembic instead.

### Migration Commands Reference

```bash
# Check current migration version
python3 -m alembic current

# View migration history
python3 -m alembic history

# Upgrade to latest version
python3 -m alembic upgrade head

# Rollback one migration (use with caution)
python3 -m alembic downgrade -1

# Rollback to specific version
python3 -m alembic downgrade <revision_id>
```

## Common Gotchas

### 1. Process Cleanup
Always stop daemon threads and background tasks in shutdown handlers. The app uses signal handlers (SIGINT/SIGTERM) for graceful shutdown.

### 2. Static File Mounting
Static file mounts (`/recordings`, `/faces`, `/data/snapshots`) MUST be mounted before the SPA catch-all route in `main.py`.

### 3. Route Ordering
Specific routes must be registered before generic catch-all routes. Example: `/api/cameras/discover` before `/api/cameras/{camera_id}`.

### 4. Database Initialization
On fresh installations, database tables are created at startup. Settings initialization happens BEFORE static file mounts to load custom paths.

### 5. Frontend Build Location
The frontend build output is `opencv_surveillance/frontend/dist/`. The backend serves this via StaticFiles mounts and a catch-all SPA handler.

### 6. Camera Source Formats
- **RTSP**: `rtsp://username:password@ip:port/stream`
- **USB**: `/dev/video0` or integer index `0`
- **Mock**: `mock` (generates test pattern)

### 7. WebSocket Statistics
The statistics broadcaster sends updates every 2 seconds via `/ws/statistics`. Frontend components subscribe using `WebSocketService.js`.

### 8. Face Clustering Scheduler
The automated clustering scheduler runs in the background. Configure interval and threshold via SystemSettings API or database directly. Default: 60 minutes interval, 10 faces minimum threshold.

### 9. Notification Encryption
Notification provider credentials are encrypted using Fernet. The `NOTIFICATION_ENCRYPTION_KEY` must be set in `.env` before storing any provider credentials. Missing this key will cause encryption errors.

### 10. Middleware Order Matters
FastAPI applies middleware in reverse order. Always add security middleware (CSRF, rate limiting) before application middleware to ensure proper request validation.

### 11. Audit Logs
Audit logs are written to `logs/audit.jsonl` in JSONL format. Each line is a separate JSON object. Implement log rotation in production to prevent disk space issues.

## Deployment

### Docker (Recommended)
```bash
cd opencv_surveillance

# Build image
docker build -t openeye:latest .

# Run container
docker run -d \
  -p 8000:8000 \
  -v ./data:/app/data \
  -v ./recordings:/app/recordings \
  -v ./faces:/app/faces \
  -e SECRET_KEY=<your-key> \
  -e JWT_SECRET_KEY=<your-key> \
  openeye:latest
```

### Native Installation
```bash
# From repository root
./start-local.sh

# Or manually:
cd opencv_surveillance
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Documentation Files

### User Documentation
- **README.md**: User-facing installation and usage guide
- **DOCKER_HUB_OVERVIEW.md**: Docker deployment guide with compose examples
- **docs/USER_GUIDE.md**: Comprehensive user manual
- **docs/UNINSTALL_GUIDE.md**: Safe removal instructions
- **docs/setup_guide.md**: Smart home integration setup

### Technical Documentation
- **docs/API_DOCUMENTATION.md** (or **docs/API_REFERENCE.md**): Complete API reference
- **docs/WEBSOCKET_IMPLEMENTATION.md**: WebSocket architecture details
- **docs/LINUX_SYSTEMD_SERVICE.md**: Production systemd setup
- **docs/CLUSTERING_SCHEDULER_GUIDE.md**: Face clustering automation guide
- **docs/FEATURES_AND_IMPLEMENTATION.md**: Feature implementation details
- **docs/SECURITY_GUIDE.md**: Comprehensive security documentation (v3.6.0)
- **docs/QUICK_REFERENCE.md**: Common tasks quick reference

### Development Documentation
- **CHANGELOG.md**: Version history and release notes
- **TODO.md**: Project roadmap and planned features
- **FIXES.md**: Complete fix history
- **SESSION_SUMMARY.md**: Recent development session notes
- **opencv_surveillance/TESTING_GUIDE.md**: Testing infrastructure guide
- **opencv_surveillance/PERFORMANCE_OPTIMIZATION_GUIDE.md**: Performance tuning guide
- **opencv_surveillance/SECURITY_AUDIT_REPORT.md**: Security audit findings (v3.6.0)
- **opencv_surveillance/SECURITY_FIXES_v4.0.0.md**: Security hardening implementation details

## Version Numbering

Format: `MAJOR.MINOR.PATCH.HOTFIX`
- **MAJOR**: Breaking changes or major features (e.g., 3.0.0)
- **MINOR**: New features, non-breaking (e.g., 3.5.0)
- **PATCH**: Bug fixes, improvements (e.g., 3.5.3)
- **HOTFIX**: Critical fixes (e.g., 3.5.1.4)

Update version in:
1. `backend/main.py` (3 locations: app metadata, API root, health check)
2. `README.md` (badge and features)
3. `CHANGELOG.md` (new entry)
4. `deploy.sh` (VERSION variable)

## Security (v3.6.0 Enhanced)

### Security Middleware Stack
The app uses multiple security layers configured in `main.py`:

1. **SecurityHeadersMiddleware**: Adds security headers (X-Frame-Options, X-Content-Type-Options, etc.)
2. **SQLInjectionProtection**: Validates requests for SQL injection patterns
3. **EndpointRateLimiter**: Per-endpoint rate limiting with category-based limits
   - `auth`: 10 requests/minute (login, token refresh)
   - `write`: 30 requests/minute (POST, PUT, DELETE)
   - `read`: 100 requests/minute (GET)
   - `stream`: 500 requests/minute (video/WebSocket)
4. **CSRFProtection**: Double-submit cookie pattern (disabled by default, enable in production)
5. **PerformanceMonitoringMiddleware**: Logs slow requests (>1 second threshold)
6. **IPWhitelistMiddleware**: Optional IP filtering (disabled by default)

### Security Features

- **Never commit** `.env` files or secret keys
- **Per-endpoint rate limiting**: Granular limits per API category (v3.6.0)
- **CSRF protection**: Double-submit cookie pattern available (v3.6.0)
- **SQL injection protection**: Request validation middleware enabled by default
- **CORS**: Specific origin whitelist (configured via `CORS_ORIGINS` env var)
- **Authentication**: JWT tokens with 30-minute expiration
- **Two-Factor Authentication**: TOTP-based 2FA with QR code setup (v3.6.0)
- **Password hashing**: bcrypt via passlib
- **Credential encryption**: Fernet encryption for notification provider secrets
- **Audit logging**: Comprehensive security event tracking (42 event types, JSONL format)

### Important Security Notes

- **CSRF Protection**: Disabled by default for ease of development. Enable in production by uncommenting in `main.py:142`
- **Rate Limiting**: Uses in-memory store. For production clusters, consider Redis-backed limiter
- **Audit Logs**: Stored in `logs/audit.jsonl` - rotate regularly in production
- **Notification Encryption**: Requires `NOTIFICATION_ENCRYPTION_KEY` in `.env` (auto-generated by setup script)

## UI Elements and Functionality

### Design Guidelines

OpenEye follows professional UI/UX standards to ensure a polished, accessible user experience:

#### Apple Human Interface Guidelines (Primary Reference)
- **Always Use**: https://developer.apple.com/design/human-interface-guidelines/
- **Key Sections to Reference**:
  - **Getting Started**: Platform design principles
  - **Foundations**: Layout, color, typography, icons
  - **Patterns**: Navigation, modals, feedback, user input
  - **Components**: Buttons, cards, lists, tables, forms
  - **Inputs**: Touch targets, gestures, keyboard navigation
  - **Technologies**: Accessibility, localization, privacy

**Important Adaptations for Web**:
- Minimum touch target size: 44x44px (Apple HIG standard)
- 8pt grid system for consistent spacing
- Theme-aware color variables (supports 9 themes)
- Clear visual hierarchy with appropriate contrast ratios

#### Material-UI (Preferred Component Library)
- **Documentation**: https://mui.com/material-ui/getting-started/usage/
- **Component Preference**:
  - **Buttons**: Use MUI Button with variants (contained, outlined, text)
  - **Text Inputs**: Use MUI TextField with proper labels and validation states
  - **Cards**: Use MUI Card for grouping related content
  - **Data Display**: Use MUI Table, DataGrid for tabular data
  - **Feedback**: Use MUI Alert, Snackbar for notifications
  - **Navigation**: Use MUI AppBar, Drawer, Tabs for navigation structures

**Integration Notes**:
- Material-UI provides ready-made, accessible components
- Customize with theme tokens to match OpenEye's visual identity
- Use MUI's built-in responsive breakpoints for mobile/desktop views
- Leverage MUI's sx prop for theme-aware styling

### Hardware-Aware Feature System

**Core Principle**: OpenEye automatically detects available hardware and intelligently manages feature availability.

#### Feature Management Rules
1. **Hardware Detection on Startup**:
   - App scans CPU, RAM, GPU, storage on first run
   - Re-scans on user request or after system restart
   - Detects: CPU cores/threads, total RAM, GPU type (NVIDIA/AMD/Intel), VRAM, available storage

2. **Feature State Management**:
   - All intensive features are **OFF by default**
   - Features require explicit user opt-in with full awareness
   - Hardware requirements clearly displayed before enabling

3. **User Warnings**:
   - **GPU-only features**: Disabled if no compatible GPU detected
   - **High-RAM features**: Warning if RAM < required threshold
   - **CPU-intensive features**: Recommend disabling on low-core systems
   - Show expected performance impact (1-10 scale)

4. **Optimal Configuration**:
   - System recommends best configuration for user's hardware tier
   - Hardware tiers: minimal, low, medium, high_end
   - Automatically suggests which features to enable/disable

#### Example Scenarios

**Scenario 1: User without GPU tries to enable CNN face detection**
```
❌ Feature Unavailable
CNN Face Detection requires:
  • NVIDIA GPU with CUDA support
  • Minimum 4GB VRAM

Your system: No compatible GPU detected

Alternative: Use HOG Face Detection (CPU mode)
```

**Scenario 2: Low-RAM system enables too many features**
```
⚠️ Performance Warning
Enabling all detection features requires:
  • Minimum 16GB RAM

Your system: 8GB RAM detected

Recommendation: Enable only Motion Detection and Face Recognition
Disable: Object Detection, License Plate Recognition
```

**Scenario 3: Optimal configuration on high-end hardware**
```
✅ Recommended Configuration
Based on your hardware:
  • Intel i7-10700 (8 cores)
  • 32GB RAM
  • NVIDIA RTX 3060 (12GB VRAM)

Optimal features:
  ✅ Face Recognition (GPU mode)
  ✅ Object Detection
  ✅ License Plate Recognition
  ✅ Hardware Video Encoding (NVENC)
  ✅ All performance optimizations

Expected CPU usage: 40-60%
Expected GPU usage: 50-70%
```

#### Implementation References
- **Hardware Detection**: `backend/core/hardware_detector.py`
- **Feature Configuration**: `backend/core/feature_config.py`
- **API Routes**: `backend/api/routes/hardware.py`, `backend/api/routes/features.py`
- **Frontend UI**: `frontend/src/pages/HardwareDetectionPage.jsx`

**Key Files for Feature Gating**:
- Check hardware before enabling features in `feature_config.py`
- Display warnings in UI before enabling intensive features
- Log hardware detection results to `logs/hardware_scan.log` 
