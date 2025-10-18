# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenEye is a 100% free, self-hosted AI-powered surveillance system using OpenCV and face recognition. The system consists of:

- **Backend**: FastAPI (Python 3.11+) with OpenCV, face_recognition (dlib), SQLAlchemy
- **Frontend**: React 18 with Vite, React Router, modern CSS with 8pt grid system
- **Database**: SQLite (default) or PostgreSQL (production)
- **Deployment**: Docker (recommended) or native Python installation

**Current Version**: 3.5.3

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

# Database migrations (manual - no Alembic used)
python scripts/migrate_database_v3.5.2.py

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

# Test accessibility API
./test-accessibility-api.sh
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

**IMPORTANT Route Ordering**: In `main.py`, specific routes MUST be registered before generic ones:
```python
# ✅ CORRECT ORDER
app.include_router(discovery.router, prefix="/api", tags=["Camera Discovery"])  # /api/cameras/discover
app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])    # /api/cameras/{id}
```

#### Database (`backend/database/`)

- **models.py**: Main models (User, FaceDetectionEvent, FaceCluster, RecordingEvent, Camera, MotionEvent, AutomationRule)
- **alert_models.py**: Alert-specific models (Alert, AlertNotificationConfig)
- **crud.py**: Database operations - centralized CRUD functions (prefer using this over direct SQLAlchemy)
- **session.py**: Database engine and session factory
- **migrations/**: Manual migration scripts (no Alembic - just Python scripts)

**Database Philosophy**: Use `crud.py` functions for consistency. Add new operations to crud.py rather than inline SQLAlchemy queries.

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

#### Components

- **LiveDashboard.jsx**: Real-time camera feed component with motion/face overlays
- **HelpButton.jsx**: Context-sensitive help system (36+ entries)
- **Sidebar.jsx**: Navigation with theme switching

#### Services

- **WebSocketService.js**: WebSocket client for real-time statistics (connects to `/ws/statistics`)
- **authService.js**: JWT token management, automatic refresh on 401
- **apiClient.js**: Axios wrapper with auth interceptors

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
The app uses a 7-step shutdown process (see `main.py:shutdown_event`):
1. Stop statistics broadcaster (WebSocket updates)
2. Close all WebSocket connections
3. Stop all cameras and release resources
4. Skip face recognition (stateless)
5. Stop cloud storage upload threads
6. Close database connections
7. Cancel remaining async tasks

**IMPORTANT**: Daemon threads and background tasks MUST be properly stopped to prevent orphaned processes.

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

# Logging
LOG_LEVEL=INFO
```

Generate secret keys:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Testing

### Test Structure (`opencv_surveillance/tests/`)
- **conftest.py**: Pytest fixtures (test client, test database)
- **test_face_recognition.py**: Face recognition unit tests
- **test_user_*.py**: User authentication and authorization tests
- **integration_testing_utils.py**: Integration test helpers
- **phase4_testing_utils.py**: Smart home integration tests

### Running Tests
```bash
cd opencv_surveillance
source venv/bin/activate

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_face_recognition.py -v

# Run with coverage
pytest --cov=backend --cov-report=html
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

- **README.md**: User-facing installation and usage guide
- **CHANGELOG.md**: Version history and release notes
- **docs/API_DOCUMENTATION.md**: Complete API reference
- **docs/USER_GUIDE.md**: Comprehensive user manual
- **docs/WEBSOCKET_IMPLEMENTATION.md**: WebSocket architecture details
- **docs/LINUX_SYSTEMD_SERVICE.md**: Production systemd setup
- **docs/development/**: Technical implementation notes

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

## Security Notes

- **Never commit** `.env` files or secret keys
- **Rate limiting**: 1000 requests/minute (configurable in `main.py`)
- **SQL injection protection**: Middleware enabled by default
- **CORS**: Configured to allow all origins in development (restrict in production)
- **Authentication**: JWT tokens with 30-minute expiration
- **Password hashing**: bcrypt via passlib
