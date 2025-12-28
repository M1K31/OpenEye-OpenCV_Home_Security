# OpenEye Surveillance System - Changelog

All notable changes to the OpenEye Surveillance System project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.11.4] - 2025-12-28

### Added
- **Scheduled Tasks System**
  - Background task scheduler for automated maintenance operations
  - Model retraining: Automatically retrain face recognition model on schedule
  - Retroactive face search: Re-identify faces in past events after model updates
  - Database cleanup: Remove old motion and face detection events
  - Snapshot cleanup: Delete old snapshot files to free disk space
  - Cluster cleanup: Remove empty or stale face clusters
  - Configurable schedule times and intervals per task

- **Retroactive Face Search API**
  - `/api/scheduled/retroactive-search`: Manually trigger retroactive face identification
  - Search past events and update identifications based on current trained model
  - Filter by person name, unknown faces only, time range, and max events
  - `/api/scheduled/train-and-search`: Combined model training + retroactive search

- **MagicMirror Face Search API**
  - `/api/ecosystem/faces/search`: Voice command support for detection queries
  - Natural language date parsing: "today", "yesterday", "December 24", YYYY-MM-DD
  - Case-insensitive partial name matching for person queries
  - Voice response generation for voice assistants (natural language summaries)
  - Filter by person name, date, date ranges, camera, include/exclude unknown faces

- **Ecosystem Statistics Endpoint**
  - `/api/ecosystem/statistics`: Event counts for MagicMirror integration
  - Motion events, face events, and recording counts per camera
  - Configurable time range (1-168 hours)
  - Per-camera breakdown with active status

- **Face Cluster Training Improvements**
  - `/api/clusters/trainable`: List clusters ready for training (minimum faces threshold)
  - `/api/clusters/export-and-train/{cluster_id}`: One-click export cluster to known faces and trigger model training
  - Automatic model retraining after cluster identification

### Fixed
- Fixed import error in scheduled_tasks.py (changed from users.get_current_user to auth.get_current_active_user)

---

## [3.11.1] - 2025-12-14

### Added
- **👥 Complete Multi-User System**
  - Full user management API (list, get, create, update, delete users)
  - Per-user notification preferences (types, channels, quiet hours)
  - Per-user camera access permissions
  - Per-user UI preferences (theme, dashboard layout, etc.)
  - Face profile linking (associate users with face recognition profiles)
  - User Management page (`/users`) - Admin-only user CRUD interface
  - User Profile page (`/profile`) - Personal settings and preferences
  - Role-based access control (admin, user, viewer)

- **🌐 Ecosystem Integration (MagicMirror & Mobile Apps)**
  - Secure token exchange for authenticated cross-app communication
  - User synchronization between apps with bidirectional sync
  - Integration sharing (HomeKit, Home Assistant, Nest credentials)
  - Unified notification routing with deduplication
  - WebSocket event streaming to connected devices
  - REST API for mobile apps (timeline, thumbnails, playback)
  - Voice command support for MagicMirror integration
  - Mobile device registration for push notifications

- **📱 Multi-Device Support**
  - Multiple MagicMirror or mobile devices on same network
  - Per-device notification preferences and camera subscriptions
  - Device-specific event routing based on location and user associations
  - Smart notification filtering (avoid duplicate alerts)

- **🔔 Smart Notification Routing**
  - User-based notification preferences
  - Camera access filtering (only notify for permitted cameras)
  - Face association filtering (notify specific users for their faces)
  - Quiet hours enforcement per user
  - Push notification infrastructure (APNs/FCM ready)

- **🔧 Dynamic Configuration**
  - Environment variable support for host/port configuration
  - `OPENEYE_HOST`, `OPENEYE_PORT` for server binding
  - `MAGICMIRROR_HOST`, `MAGICMIRROR_PORT` for ecosystem discovery
  - Dynamic CORS origins for ecosystem apps

### Changed
- Updated sidebar navigation with User Management and Profile links
- Enhanced User model with display_name, avatar, face_profile_name, sync fields
- Added UserPreferences model with comprehensive preference storage
- Improved ecosystem connection model for multi-device support
- Updated version to 3.11.1 across all components

### Database Migrations
- New `user_preferences` table for per-user settings
- Enhanced `ecosystem_connections` table with device_id, location, subscriptions
- New columns on `users` table: display_name, avatar_url, face_profile_name, synced_from, external_id, last_login

---

## [3.10.2] - 2025-12-08

### Fixed
- **⏱️ Timeline Playback Performance & Reliability Improvements**
  - **Performance**: Added memoization with `useMemo` for expensive calculations (timeline width, axis marks, sorted events)
  - **Performance**: Added debouncing (300ms) to prevent excessive API calls when time range changes
  - **Performance**: Added `limit` parameter to timeline API (default 500 events per camera, max 1000)
  - **Playback Bug Fix**: Replaced unstable playback logic with index-based state machine to prevent race conditions
  - **Playback Bug Fix**: Added `currentEventIndex` state to track position reliably during sequential playback
  - **Playback Bug Fix**: Used `isPlayingRef` to prevent stale closure issues in async callbacks
  - **Playback Bug Fix**: Fixed video/image sequencing that could skip events or fail to load
  - **Files Modified**: `frontend/src/pages/TimelineView.jsx`, `backend/api/routes/timeline.py`

- **🧠 AI & Faces - Delete/Add Person Freeze Fix**
  - **Root Cause**: Synchronous `train_face_recognition()` calls blocked the main thread during dlib operations
  - **Fix**: Made `auto_train=False` default for `delete_person` and `assign_name_to_cluster`
  - **Fix**: Added `BackgroundTasks` for training after cluster operations
  - **Fix**: Enhanced `assign_name_to_cluster` with merge detection and duplicate file handling
  - **Impact**: App no longer freezes when adding/deleting people or assigning names to clusters
  - **Files Modified**: `backend/core/face_recognition.py`, `backend/core/face_clustering.py`, `backend/api/routes/clusters.py`, `backend/api/schemas/clustering.py`

- **🔍 Face Detection Not Recording to Database** (Critical Bug Fix)
  - **Root Cause**: `is_available()` returned `False` if no known faces were trained, completely blocking face detection
  - **Impact**: Face detection events (0 in database) were never created even though face snapshots existed
  - **Fix 1**: Changed `is_available()` to return `True` if face_recognition library is available (not just if known faces exist)
  - **Fix 2**: Modified `recognize_faces_in_frame()` to detect faces even when no known faces are trained
  - **Fix 3**: Unknown faces are now properly detected, saved to database, and available for clustering
  - **Result**: Face detection now works for both known and unknown faces, enabling proper clustering workflow
  - **Files Modified**: `backend/core/face_recognition.py`, `backend/core/face_detection.py`

### Removed
- **🧹 Project Cleanup - Removed Red Herring Files**
  - **`backend/.env`**: Duplicate config with insecure placeholder credentials (root `.env` has proper secure keys)
  - **`docker/docker-compose.yml`**: Outdated Docker compose with wrong paths referencing insecure `backend/.env`
  - **`backend/api/routes/recordings_optimized_example.py`**: Orphaned example file never imported
  - **`frontend/src/pages/SettingsPageSimple.jsx`**: Orphaned test file never imported
  - **`data/surveillance.db`**: Orphaned 0-byte database file (actual database is `surveillance.db` in project root)

---

## [3.10.1] - 2025-11-18

### Added
- **🎤 Enhanced Two-Way Audio Features** - Comprehensive UX improvements
- **🧪 Test Infrastructure Improvements** - Established baseline coverage and fixed test suite
  - Installed `pytest-cov` for coverage analysis (coverage 7.12.0, pytest-cov 7.0.0)
  - **Current Coverage**: 27% → working toward 60% target
  - Coverage configured in `pytest.ini` with HTML/XML reports
  - **Test Results**: 34 passing (was 13), 10 failed, 21 errors (was 65+ errors)
- **🧪 Backend Unit Tests** - Comprehensive test suite for core modules
  - **cache.py**: 21 tests, 100% coverage (was 0%) - Tests for CacheEntry, SimpleCache, @cached decorator, singleton pattern
  - Created `tests/core/test_cache.py` with full coverage of TTL expiration, invalidation patterns, statistics, thread safety
  - **Push-to-Talk Mode**: Walkie-talkie style hold-to-talk button with visual feedback
  - **Volume Control**: Adjustable volume slider (0-100%) for remote audio
  - **Audio Level Indicators**: Real-time visualization for microphone and camera audio using Web Audio API
  - **Audio Diagnostics Panel**: Collapsible diagnostics showing connection stats, bytes sent/received, track counts
  - **Browser Autoplay Fix**: Automatic detection with user-triggered playback option for browsers blocking autoplay
  - Updated `TwoWayAudio.jsx` (713 lines, +383 lines) with all 5 enhancements
  - Updated `TwoWayAudio.css` (559 lines, +318 lines) with theme-aware styling

### Fixed
- **🔌 WebSocket 403 Authentication Errors** - Critical bug fix for intermittent connection failures
  - **Root Cause**: WebSocketService was reusing stale tokens during reconnections after token refresh
  - **Fix**: Modified `scheduleReconnect()` in `WebSocketService.js` to fetch fresh token from localStorage before reconnecting
  - **Impact**: Eliminates 403 errors when tokens are refreshed by authService during active WebSocket sessions
  - **File Modified**: `frontend/src/services/WebSocketService.js:190-202`
- **🔧 Duplicate Logger Imports** - Fixed build errors in 7 frontend files
  - Removed duplicate `import { logger }` statements in:
    - `RecordingsPage.jsx`, `SystemSettingsPage.jsx`, `PerformanceDashboard.jsx`
    - `TimelineView.jsx`, `ClusterDetailModal.jsx`, `PTZControl.jsx`, `SettingsPage.jsx`
- **🧪 Test Fixture API Mismatch** - Fixed incompatibility with updated `crud.create_user()` signature
  - Updated `tests/conftest.py` to use `UserCreate` schema object instead of individual parameters
  - **Before**: `crud.create_user(db, username="...", password="...", email="...")`
  - **After**: `crud.create_user(db, user=UserCreate(...))`
  - **Impact**: Eliminated 65+ test errors from fixture initialization failures
- **🔧 Test Authentication Errors** - Fixed multiple test infrastructure issues
  - **HTTP 405 Error**: Updated `auth_headers` fixture to use correct login endpoint (`/api/auth/login-2fa`)
  - **Duplicate get_db Functions**: Fixed `backend/api/routes/users.py` to import standard `get_db` from `backend.database.session` instead of defining local copy
  - **Database Schema**: Added explicit imports for `alert_models` and `RefreshToken` in `tests/conftest.py` to ensure all tables are created
  - **Impact**: Fixed authentication flow, enabled database session override to work correctly
- **🗄️ Test Database Session Isolation** - Fixed "no such table: refresh_tokens" error in tests
  - **Root Cause**: SQLite `:memory:` database creates separate databases for each connection. TestClient HTTP requests were accessing different in-memory database than test fixtures
  - **Fix**: Added `StaticPool` connection pool to `tests/conftest.py:18-27` to ensure all connections use the same in-memory database
  - **Impact**: All tests now reliably use the same test database. RefreshToken table and other tables are accessible during HTTP requests
- **🔧 Test Camera Fixture Errors** - Fixed incorrect field names in `test_camera` fixture
  - Updated `tests/conftest.py:100-114` to match actual Camera model schema
  - **Field Corrections**: `camera_name`→`camera_type`, `source_url`→`source`, `enabled`→`is_active`, `face_recognition_enabled`→`face_detection_enabled`
  - **Impact**: Eliminated TypeError in all camera-related tests

### Verified
- **✅ API Response Wrapping** - Confirmed all endpoints properly use `PaginatedResponse`:
  - `/api/recordings/` → `PaginatedResponse[RecordingResponse]`
  - `/api/history/detections` → `PaginatedResponse[FaceDetectionEventResponse]`
  - `/api/faces/people` → `PaginatedResponse[Person]`
  - `/api/alerts/logs` → `PaginatedResponse[NotificationLogResponse]`
- **✅ Field Name Consistency** - Verified frontend uses descriptive field names throughout:
  - `camera.camera_id` (not `camera.id`)
  - `camera.is_active` (not `camera.active`)
  - `recording.recording_id` with fallback to `recording.id`

---

## [3.10.0] - 2025-11-15

### Added
- **🎤 Two-Way Audio Communication** - WebRTC-based bidirectional audio with cameras
  - **Real-time Audio**: Low-latency bidirectional audio streaming using WebRTC
  - **Backend Implementation** (`backend/core/two_way_audio_system.py`):
    - `TwoWayAudioManager` - Session management and lifecycle
    - `WebRTCAudioSession` - Per-camera WebRTC peer connections
    - `AudioCapture` - PyAudio-based audio input/output with echo cancellation and noise suppression
    - WebSocket endpoint at `/api/audio/ws/{camera_id}` for signaling
    - Audio devices API at `/api/audio/devices` for device enumeration
    - Test page at `/api/audio/test` for standalone testing
  - **Frontend Integration**:
    - `TwoWayAudio.jsx` component for WebRTC client implementation
    - `AudioModal.jsx` - Theme-aware modal wrapper with accessibility support
    - Dashboard integration with 🎤 audio button on active camera cards
    - Connection states: Connecting → Live → Disconnected
    - Audio controls: Microphone mute/unmute, speaker mute/unmute, disconnect
  - **Features**:
    - ✅ Bidirectional audio (simultaneous listen and speak)
    - ✅ Echo cancellation and noise suppression
    - ✅ DTLS-SRTP encryption for secure audio streams
    - ✅ JWT-authenticated WebSocket connections
    - ✅ Configurable audio parameters (sample rate, channels, chunk size)
    - ✅ STUN/TURN server support for NAT traversal
    - ✅ Multi-camera support (independent sessions)
  - **Dependencies**:
    - `pyaudio>=0.2.13` - Audio I/O library
    - `aiortc>=1.6.0` - WebRTC implementation for Python
    - `av>=11.0.0` - Audio/video processing
  - **Documentation**:
    - Comprehensive guide at `docs/TWO_WAY_AUDIO_GUIDE.md` (400+ lines)
    - Covers requirements, quick start, configuration, troubleshooting, security
  - **Testing**:
    - 13 E2E tests in `frontend/e2e/two-way-audio.spec.js`
    - Tests dashboard integration, modal behavior, API endpoints
    - Total E2E coverage: 101 tests across 7 test files
  - **Browser Support**: Chrome 80+, Edge 80+, Firefox 75+, Safari 14+

- **🔔 Object Detection Notifications** - Smart alerts for AI-detected objects
  - **Alert Configuration** (`backend/database/alert_models.py`):
    - Added 5 new fields to `AlertConfiguration` model:
      - `object_detection_alerts_enabled` - Master toggle for all object detection alerts
      - `vehicle_alerts_enabled` - Alerts for any vehicle detection
      - `animal_alerts_enabled` - Alerts for any animal detection
      - `package_alerts_enabled` - Alerts for any package detection
      - `identified_object_alerts_enabled` - Alerts for specific identified objects
    - Database migration: `f9g6h5i4j3k2_add_object_detection_alert_fields_v3_10_0.py`
  - **Alert Manager** (`backend/core/alert_manager.py`):
    - New method: `trigger_object_detection_alert()` with class-based and entity-based alerts
    - Supports throttling and quiet hours for object detection alerts
    - Event types: `object_vehicle`, `object_animal`, `object_package`, `object_identified_{class}`
  - **Integration** (`backend/core/object_detector.py`):
    - Automatic alert triggering when objects are detected
    - Async background task execution to prevent detection delays
    - Includes detection metadata (bbox, frame dimensions, confidence)
  - **Frontend UI** (`frontend/src/pages/AlertSettingsPage.jsx`):
    - New "Object Detection Alerts" section with master toggle
    - Hierarchical controls: Enable master toggle to reveal class-specific toggles
    - Clear icons for each alert type: 🚗 Vehicles, 🐾 Animals, 📦 Packages, 🏷️ Identified Objects
    - Indented sub-options for better visual hierarchy
  - **Features**:
    - ✅ Class-based notifications (notify on any vehicle, animal, or package)
    - ✅ Entity-based notifications (notify when specific objects like "John's Tesla" are detected)
    - ✅ Multi-channel support (email, SMS, push, webhook)
    - ✅ Configurable throttling to prevent alert spam
    - ✅ Quiet hours support
    - ✅ Per-class enable/disable controls
  - **Use Cases**:
    - Get notified when any vehicle enters your driveway
    - Alert when specific vehicle (e.g., "John's Tesla") arrives
    - Detect packages left at doorstep
    - Monitor wildlife/pets in specific areas

---

## [3.9.0] - 2025-11-14

### Security
- **🔒 Account Lockout System for 2FA** - Protection against brute force attacks
  - **New Feature**: Automatic account lockout after 5 failed 2FA verification attempts
  - **Lockout Duration**: 30 minutes (configurable in `security_helpers.py`)
  - **Auto-Reset**: Failed attempt counter resets after 15 minutes of inactivity
  - **User Feedback**: Shows remaining attempts before lockout (e.g., "4 attempts remaining")
  - **Affected Endpoints**:
    - `/api/auth/login-2fa` - Login with 2FA
    - `/api/auth/reset-password` - Password reset with 2FA
  - **Database Schema**: Added 4 new fields to User model
    - `failed_2fa_attempts` - Counter for failed attempts
    - `last_failed_2fa_attempt` - Timestamp of last failure
    - `account_locked_until` - Lockout expiration time
    - `lockout_count` - Total number of times locked
  - **Migration**: `c4d8e2f1b3a7_add_2fa_account_lockout_fields.py`

- **🚦 Enhanced Rate Limiting** - Stricter limits for security-sensitive endpoints
  - **Password Reset**: 5 attempts per hour per IP (was unlimited)
  - **2FA Verification**: 10 attempts per 5 minutes per IP (was 10/minute)
  - **Implementation**: Pattern-based routing in `EndpointRateLimiter`
  - **Response**: HTTP 429 with `Retry-After` header when exceeded

- **📝 Enhanced Audit Logging** - Comprehensive security event tracking
  - **New Event Types** (9 total):
    - `PASSWORD_RESET_ATTEMPTED/SUCCESS/FAILED` - All password reset attempts
    - `TWO_FA_ENABLED/DISABLED` - 2FA enrollment changes
    - `TWO_FA_VERIFY_SUCCESS/FAILED` - 2FA verification attempts
    - `TWO_FA_ACCOUNT_LOCKED/UNLOCKED` - Account lockout events
  - **Log Format**: JSONL (JSON Lines) at `logs/audit.jsonl`
  - **Details Tracked**: IP address, username, reason, remaining attempts, timestamps
  - **Real-time Monitoring**: All events logged to console with appropriate severity

### Performance
- **📊 Database Query Optimization** - Added 11 new indexes for frequently accessed queries
  - **RecordingEvent Indexes**:
    - `idx_recording_started_at` - Sorting recordings by date
    - `idx_recording_camera_time` - Composite index for camera + time queries
    - `idx_recording_ended_at` - Filtering completed recordings
  - **FaceDetectionEvent Indexes**:
    - `idx_face_camera_time` - Face history per camera over time
    - `idx_face_person_time` - Face history per person over time
  - **MotionDetectionEvent Indexes**:
    - `idx_motion_camera_time` - Motion history per camera over time
  - **FaceCluster Indexes**:
    - `idx_cluster_identified` - Filtering identified vs unidentified clusters
    - `idx_cluster_created_at` - Sorting clusters by creation date
    - `idx_cluster_last_seen` - Finding recently seen clusters
  - **User Indexes**:
    - `idx_user_locked_until` - Checking account lockout status (new security feature)
    - `idx_user_is_active` - Filtering active users
  - **Migration**: `d5e9f3a2b8c4_add_performance_indexes_v3_9_0.py`
  - **Impact**: Significant performance improvement for recordings list, face/motion history queries, and cluster filtering

- **🚀 Query Result Caching Layer** - In-memory cache with TTL support
  - **Implementation**: New `SimpleCache` class in `backend/core/cache.py`
  - **Features**:
    - Thread-safe operations with automatic locking
    - Time-to-live (TTL) expiration (default: 5 minutes)
    - Manual invalidation by key or pattern matching
    - Hit/miss statistics tracking
    - Automatic cleanup of expired entries
  - **Decorator Support**: `@cached(ttl=600, key_prefix="settings")` for easy function caching
  - **Use Cases**: System settings, notification provider configs, frequently accessed data
  - **Benefits**: Reduces database load for rarely changing data

- **⚡ WebSocket Broadcast Optimization** - Reduced bandwidth via change detection
  - **Implementation**: Updated `statistics_broadcaster.py` with smart change detection
  - **How It Works**:
    - Creates hash of statistics data (excluding timestamp)
    - Only broadcasts when data actually changes
    - Tracks broadcasts sent vs skipped for monitoring
  - **Performance Metrics**: New `get_performance_stats()` method
    - `broadcasts_sent` - Number of actual broadcasts
    - `broadcasts_skipped` - Number of skipped (unchanged data)
    - `skip_rate_percent` - Efficiency metric
    - `bandwidth_saved_percent` - Estimated bandwidth reduction
  - **Impact**: Significantly reduces WebSocket traffic when camera stats are stable
  - **Logging**: Debug logs every 20 skipped broadcasts showing efficiency percentage

### Added
- **New Security Helper Module** (`backend/core/security_helpers.py`)
  - `is_account_locked()` - Check if user account is currently locked
  - `get_lockout_remaining_time()` - Get remaining lockout time in seconds
  - `record_failed_2fa_attempt()` - Track failures and auto-lock after threshold
  - `record_successful_2fa_attempt()` - Reset counters on successful verification
  - `unlock_account()` - Manual unlock by admin (future admin panel feature)
  - `get_account_security_status()` - Complete security status for monitoring

- **New Caching Module** (`backend/core/cache.py`)
  - `SimpleCache` class - Thread-safe in-memory cache with TTL
  - `get_cache()` - Singleton cache instance factory
  - `@cached()` decorator - Function result caching with auto invalidation
  - Cache statistics tracking (hits, misses, evictions, hit rate)

### Changed
- **Authentication Flow Improvements**
  - Login and password reset now check for account lockout before verification
  - Failed attempts now return specific error messages with remaining attempt count
  - Successful verifications reset all failed attempt counters
  - Backup code failures now also count toward lockout threshold

### Fixed
- **Authentication Token Validation** - Fixed bug where expired tokens were accepted on page reload
  - Added `isAuthenticated()` check in `App.jsx` on mount
  - Expired tokens now properly cleared from localStorage
  - WebSocket connections no longer show "offline" state with invalid tokens
  - Users must login again after token expiration (proper session management)

### Technical Details
- **Files Created**:
  - `backend/core/security_helpers.py` - Security helper functions
  - `backend/core/cache.py` - In-memory caching layer with TTL support
  - `backend/api/schemas/pagination.py` - Standardized pagination wrapper
  - `alembic/versions/c4d8e2f1b3a7_add_2fa_account_lockout_fields.py` - 2FA lockout database migration
  - `alembic/versions/d5e9f3a2b8c4_add_performance_indexes_v3_9_0.py` - Performance indexes migration

- **Files Modified**:
  - `backend/middleware/endpoint_rate_limiter.py` - Added password reset and 2FA categories
  - `backend/core/audit_logger.py` - Added 9 new security event types
  - `backend/core/statistics_broadcaster.py` - Added change detection and performance tracking
  - `backend/database/models.py` - Added lockout tracking fields to User model
  - `backend/api/routes/users.py` - Integrated lockout logic into auth endpoints
  - `frontend/src/App.jsx` - Added token validation on app mount
  - `frontend/src/pages/RecordingsPage.jsx` - Updated for new pagination format
  - `frontend/src/pages/FaceManagementPage.jsx` - Updated for new pagination format
  - `frontend/src/pages/DashboardPage.jsx` - Updated for new pagination format
  - `frontend/src/pages/AlertSettingsPage.jsx` - Updated for new pagination format

---

## [3.7.2] - 2025-11-08

### Security
- **Frontend Dependency Security Update** - Resolved 6 moderate severity vulnerabilities
  - **Issue**: esbuild ≤0.24.2 vulnerability (GHSA-67mh-4wv8-2f99) allowed any website to send requests to development server and read responses
  - **Solution**: Incremental upgrade from Vite 4 → 5 → 6 → 7 with compatible plugin versions
  - **Impact**: Development environment only, production builds were never affected

  - **Upgraded Packages**:
    - `vite`: 4.5.14 → 7.2.2 (3 major version jump)
    - `@vitejs/plugin-react`: 4.7.0 → 5.1.0
    - `vitest`: 1.6.1 → 4.0.8
    - `@vitest/ui`: 1.6.1 → 4.0.8
    - `@vitest/coverage-v8`: 1.6.1 → 4.0.8
    - `esbuild`: ≤0.24.2 → 0.25.12 (patched)

  - **Testing**: All builds tested at each version (Vite 5, 6, 7) - no breaking changes encountered
  - **Result**: ✅ 0 vulnerabilities, all security issues resolved
  - **Files Modified**: `package.json`, `package-lock.json`

### Changed
- **Node.js Requirement**: Minimum version increased from 16+ to 20+ (Vite 7 requires Node.js 20.19+/22.12+)

---

## [3.7.1] - 2025-11-06 (Integration Complete)

### Added
- **FFmpeg Hardware-Accelerated Video Encoding - FULLY INTEGRATED** ✅
  - **Problem**: cv2.VideoWriter uses CPU-only encoding, high CPU usage (40-45%), dropped frames (2-5%), slow browser playback
  - **Solution**: Complete integration of FFmpeg recorder with hardware acceleration, conditional recorder selection, UI controls
  - **Status**: **PRODUCTION READY** - All tests passing, zero dropped frames confirmed

  - **Core Features**:
    - **Hardware Acceleration**: Auto-detects and uses NVENC (NVIDIA), QuickSync (Intel), VideoToolbox (macOS), VAAPI (Linux), or software fallback
    - **70-90% CPU Reduction**: GPU-accelerated encoding (tested: 40-45% → 8-12% on VideoToolbox)
    - **Async Frame Buffer**: 300-frame queue (10 seconds at 30fps) prevents dropped frames via background writer thread
    - **Zero Dropped Frames**: Non-blocking frame writes, camera thread never waits for disk I/O
    - **Instant Browser Playback**: `-movflags +faststart` moves moov atom to file start for progressive streaming
    - **Face Metadata Tracking**: Records detected faces with timestamps during recording
    - **Buffer Statistics**: Tracks frames queued/written/dropped for performance monitoring
    - **Graceful Fallback**: Auto-falls back to standard recorder if FFmpeg initialization fails

  - **Integration Complete** (2025-11-06):
    - ✅ **API Compatibility**: Added `add_face_detection()` and `should_stop_recording()` methods to FFmpegRecorder
    - ✅ **Camera Manager**: Conditional recorder creation based on `hardware_video_encoding` system setting
    - ✅ **Database Setting**: `hardware_video_encoding` boolean setting added to SystemSettings
    - ✅ **Backend API**: `hardware_video_encoding` field added to SystemSettingsUpdate schema
    - ✅ **Frontend UI**: New "⚡ Performance Settings" section with hardware encoding toggle
    - ✅ **Testing**: Comprehensive integration tests passing with 0.00% frame drop rate
    - ✅ **Documentation**: Complete implementation guide and migration documentation

  - **Test Results** (2025-11-06, macOS VideoToolbox):
    - Encoder: Apple VideoToolbox (h264_videotoolbox)
    - Test Recording: 90 frames, 0.89 seconds
    - Frames Queued: 90, Written: 90, Dropped: 0
    - Drop Rate: **0.00%** ✅
    - File Output: 105 KB MP4 (web-optimized)

  - **Performance Improvements**:
    - **CPU Usage**: 40-45% → 8-12% per camera (76% reduction)
    - **Frame Drops**: 2-5% → 0% (perfect recording)
    - **Max Cameras**: 2-3 → 8+ simultaneous recordings
    - **Quality**: Standard → Excellent (hardware-accelerated H.264)

  - **Files Created/Modified**:
    - `backend/core/ffmpeg_recorder.py` (+32 lines - API compatibility methods)
    - `backend/core/recorder.py` (+6 lines - camera_id parameter support)
    - `backend/core/camera_manager.py` (+38 lines - conditional recorder selection)
    - `backend/api/routes/settings.py` (+4 lines - hardware_video_encoding field)
    - `frontend/src/pages/SystemSettingsPage.jsx` (+29 lines - Performance Settings UI)
    - `docs/development/FFMPEG_INTEGRATION_COMPLETE_v3.7.1.md` (complete documentation)
    - `test_hardware_encoding_integration.py` (integration test suite)
    - `test_recording_manual.py` (direct recorder test)

  - **Usage**:
    - Navigate to System Settings → Performance Settings
    - Enable "Hardware Video Encoding" toggle
    - Save settings and restart cameras
    - Verify in terminal: `✅ FFmpeg recorder initialized with hardware acceleration`

  - **Benefits**:
    - Multiple cameras can record simultaneously without performance degradation
    - Recordings start playing instantly in browser timeline/events pages
    - Scrubbing works immediately without full file download
    - Better quality at same file size with configurable bitrate/CRF
    - Production-ready with comprehensive error handling and fallback mechanisms

- **Enhanced CLAUDE.md Documentation** - Updated developer guidelines
  - **Apple Human Interface Guidelines**: Comprehensive UX standards reference
    - Minimum 44x44px touch targets, 8pt grid system, theme-aware design
    - Detailed sections: Foundations, Patterns, Components, Inputs, Technologies
  - **Material-UI Integration Guide**: Preferred component library standards
    - Component recommendations: MUI Button, TextField, Card, Table, Alert, Snackbar
    - Theme customization, responsive breakpoints, sx prop usage
  - **Hardware-Aware Feature System**: Detailed documentation of feature gating
    - Hardware detection on startup/restart, feature state management rules
    - Example user warning scenarios for GPU-only, high-RAM, CPU-intensive features
    - Optimal configuration recommendations based on hardware tier
  - **File**: `CLAUDE.md` (lines 701-820)

### Documentation
- **FFMPEG_RECORDER_IMPLEMENTATION.md** - Complete implementation guide
  - Architecture overview, class structure, FFmpeg command examples
  - Hardware detection integration, performance benchmarks, metadata format
  - Troubleshooting guide, testing checklist, integration instructions
  - File size comparison, encoder availability matrix, next steps

---

## [3.7.0] - 2025-11-02

### Added
- **EventDetailModal Component** - New modal for viewing event details without navigation
  - Problem: Clicking events navigated away from LiveDashboard, breaking workflow
  - Solution: Created modal with video player, snapshot display, and action buttons
  - Benefits: View events inline, better UX, maintains dashboard context
  - Files Created: `frontend/src/components/EventDetailModal.jsx`, `frontend/src/components/EventDetailModal.css`

- **Universal Button Component Integration** - Apple HIG-compliant buttons throughout app
  - Integrated in LiveDashboard (11 buttons) and EventDetailModal (4 buttons)
  - Features: Icon support, loading states, size variants, accessibility improvements
  - Benefits: 44x44px touch targets, consistent styling, better developer experience
  - Bundle impact: +0.7 kB (+0.21 kB gzipped) - minimal overhead
  - Files Modified: `frontend/src/sections/LiveDashboard.jsx`, `frontend/src/components/EventDetailModal.jsx`

- **Video Duration Analysis Utilities** - Tools to detect and fix recording duration mismatches
  - Problem: Wall-clock duration vs actual video playback duration mismatch
  - Solution: Created utilities to read actual video metadata and fix database records
  - Benefits: Accurate playback duration display, future recording optimization roadmap
  - Files Created: `backend/utils/video_utils.py`, `fix_recording_durations.py`

- **Safari Browser Detection** - Graceful degradation for PiP feature in Safari
  - Problem: Safari doesn't support canvas.captureStream() reliably, causing silent failures
  - Solution: Browser detection with user-friendly error message and auto-close
  - Benefits: Clear feedback instead of broken functionality
  - Files Modified: `frontend/src/components/PipVideoPlayer.jsx`

### Fixed
- **LiveDashboard Auto-Refresh** - Disabled excessive auto-refresh causing flickering
  - Problem: Recent events bar refreshing every 10 seconds, causing UI flicker
  - Solution: Removed auto-refresh interval, rely on manual refresh only
  - Benefits: Stable UI, better performance, no visual disruption
  - Files Modified: `frontend/src/sections/LiveDashboard.jsx`

- **Camera Feed Reloading** - Prevented camera feeds from reloading on event updates
  - Problem: Camera feeds reloading when events updated, causing stream interruptions
  - Solution: Improved React memo and state management to prevent unnecessary re-renders
  - Benefits: Smooth live streaming, better user experience
  - Files Modified: `frontend/src/sections/LiveDashboard.jsx`

- **Grid Size Differentiation** - Increased spacing between Small/Medium/Large/XL grid sizes
  - Problem: Small (240px) and Medium (320px) appeared nearly identical on screen
  - Solution: Updated CSS to use 220px/360px/480px/640px for clear visual differences
  - Benefits: Obvious size differences, better multi-camera viewing options
  - Files Modified: `frontend/src/sections/LiveDashboard.css`

- **Camera Settings Save Feedback** - Added auto-clearing success messages
  - Problem: No visual feedback when saving camera settings
  - Solution: Added 4-second auto-clear timeout for success messages across all 5 save handlers
  - Benefits: Clear confirmation, doesn't require manual dismissal
  - Files Modified: `frontend/src/components/CameraSettingsModal.jsx`

### Changed
- **Event Click Behavior** - Events now open modal instead of navigating to history page
  - Changed from: `navigate('/face-history')` or `navigate('/recordings')`
  - Changed to: `setSelectedEvent(event)` with modal display
  - Benefits: Faster event viewing, maintains dashboard context
  - Files Modified: `frontend/src/sections/LiveDashboard.jsx`

- **Event Video Player** - Replaced placeholder with native HTML5 video player
  - Removed: Redundant "Play" button
  - Added: Native video controls with thumbnail preview
  - Benefits: Consistent with rest of app, better user experience
  - Files Modified: `frontend/src/components/EventDetailModal.jsx`

### Documentation
- **VIDEO_OPTIMIZATION_GUIDE_2025-11-02.md** - Comprehensive video performance optimization guide
  - Evaluates FFmpeg, hardware acceleration, frame buffering, and web optimization
  - Provides implementation roadmap for future enhancements
  - Explains impact (or lack thereof) on facial recognition functionality

- **UNIVERSAL_COMPONENTS_INTEGRATION_2025-11-02.md** - Complete integration documentation
  - Documents all 15+ button instances updated
  - Migration patterns for future components
  - Build performance impact analysis

- **UI_IMPROVEMENTS_GUIDE.md** - Moved to docs/development/ for better organization

---

## [3.6.2] - 2025-10-25

### Added
- **Motion Detection Threshold UI** - Added user-configurable motion sensitivity control
  - Problem: Backend supported motion_percentage_threshold but no UI existed to configure it
  - Solution: Added slider control in System Settings with range validation (0.1-5.0%)
  - Benefits: Users can now tune motion detection sensitivity from the UI without backend changes
  - Files Modified: `frontend/src/pages/SystemSettingsPage.jsx`

### Fixed
- **Documentation Links** - Updated README.md references to point to new consolidated documentation locations
  - Problem: README referenced deleted files after documentation consolidation
  - Solution: Updated all documentation links to new locations in docs/development/ and docs/security/
  - Benefits: All documentation links now work correctly
  - Files Modified: `README.md`

---

## [3.6.1] - 2025-10-25

### Fixed
- **2FA Login Flow** - Corrected login flow to use /auth/login-2fa endpoint after initial authentication
  - Problem: Frontend was attempting to call non-existent /api/auth/login endpoint for 2FA
  - Solution: Updated login flow to properly use /api/auth/login-2fa for two-factor authentication
  - Benefits: 2FA now works correctly end-to-end
  - Files Modified: `frontend/src/pages/LoginPage.jsx`

- **Recording Download Rate Limiting** - Fixed rate limit errors when downloading recordings
  - Problem: Recording downloads were categorized as "read" endpoints (100 req/min), causing issues with large downloads
  - Solution: Moved /api/recordings/{id}/download to "stream" category (500 req/min)
  - Benefits: Users can now download recordings without hitting rate limits
  - Files Modified: `backend/middleware/endpoint_rate_limiter.py`

- **Face Statistics Rate Limiting** - Fixed intermittent 429 errors on face statistics endpoint
  - Problem: /api/faces/statistics endpoint occasionally hit rate limits during polling
  - Solution: Moved statistics endpoint to "read" category with higher limit
  - Benefits: More reliable face statistics updates in the UI
  - Files Modified: `backend/middleware/endpoint_rate_limiter.py`

### Performance Improvements
- **React Code Splitting** - Implemented lazy loading for all major pages
  - Reduced main bundle size from 223KB to 51KB (77% reduction)
  - Pages now load on-demand, improving initial load time
  - Implemented for: Dashboard, Cameras, Faces, Recordings, Timeline, Settings, and all other pages
  - Files Modified: `frontend/src/App.jsx`

- **React 18 Transitions** - Added startTransition for instant navigation feedback
  - Sidebar navigation now shows immediate visual feedback
  - Navigation feels instant even while page chunks load
  - Non-blocking UI updates prevent janky animations
  - Files Modified: `frontend/src/layouts/Sidebar.jsx`

- **WebSocket Optimization** - Optimized message handler using requestIdleCallback
  - Eliminated 175ms blocking time during WebSocket message processing
  - Camera statistics updates now processed during browser idle time
  - Smoother UI performance, especially during heavy data updates
  - Files Modified: `frontend/src/services/WebSocketService.js`

### Changed
- **Documentation Consolidation** - Reorganized documentation for production readiness
  - Root level: README.md, CHANGELOG.md, CLAUDE.md, DOCKER.md (essentials only)
  - Created docs/development/ for development documentation
  - Created docs/security/ for security-related documentation
  - Created docs/features/ for feature implementation documentation
  - Removed redundant root-level documentation files

- **Ignore Files** - Enhanced .gitignore and created .dockerignore
  - Updated .gitignore with comprehensive exclusions (media, logs, cache, etc.)
  - Created .dockerignore to prevent bloat in Docker images
  - Ensures production deployments are clean and efficient

- **Cleanup** - Removed temporary test files and obsolete scripts
  - Removed test_*.py files from opencv_surveillance root (kept in tests/ folder)
  - Removed obsolete scripts: fix-shebangs.sh, recreate-venv.sh, cleanup-docs.sh, etc.
  - Cleaner repository structure for production deployment

## [3.5.3] - 2025-10-18

### Fixed
- **Duplicate Discovery Routes** - Removed duplicate camera discovery endpoints from cameras.py ✅
  - **Problem**: Discovery endpoints existed in both `discovery.py` and `cameras.py`
  - **Solution**: Removed duplicates from `cameras.py`, using only dedicated `discovery.py` router
  - **Benefits**: Single source of truth, easier maintenance, no confusion
  - **Files Modified**: `backend/api/routes/cameras.py`

- **Setup Route Prefix** - Added `/api/setup` prefix for consistency ✅
  - **Problem**: Setup routes at `/status` and `/initialize` without `/api` prefix
  - **Solution**: Added `/api/setup` prefix to setup router
  - **Benefits**: Consistent URL structure, better security, prevents SPA route conflicts
  - **New Endpoints**: `/api/setup/status`, `/api/setup/initialize`
  - **Files Modified**: `backend/main.py`

- **WebSocket Consolidation** - Unified WebSocket endpoint structure ✅
  - **Problem**: Inconsistent WebSocket URLs (statistics under `/api/ws`, audio under `/ws`)
  - **Solution**: Moved audio WebSocket to `two_way_audio.py` router
  - **Benefits**: All WebSockets under `/api/` prefix, better organization
  - **New Endpoint**: `/api/audio/ws/{camera_id}`
  - **Files Modified**: `backend/api/routes/two_way_audio.py`, `backend/main.py`

### Added
- **Error Boundaries** - React error boundaries for graceful error handling ✅
  - Beautiful fallback UI with error details and recovery actions
  - Prevents white screen crashes from runtime errors
  - Dark mode support and mobile responsive
  - **Files Created**: `frontend/src/components/ErrorBoundary.jsx`, `ErrorBoundary.css`
  - **Files Modified**: `frontend/src/App.jsx`

- **Request Retry Logic** - Automatic retry with exponential backoff ✅
  - Retries network errors and server errors (5xx, 429)
  - Exponential backoff: 1s → 2s → 4s (max 3 retries)
  - Jitter to prevent thundering herd
  - Detailed console logging for debugging
  - **Files Modified**: `frontend/src/api/apiClient.js`

- **WebSocket Status Indicator** - Real-time connection status display ✅
  - Visual feedback (🟢 connected, 🟡 connecting, 🔴 disconnected)
  - Shows in sidebar footer with pulse animation
  - Tooltips with detailed status
  - Shows reconnection attempts
  - **Files Created**: `frontend/src/components/WebSocketStatus.jsx`, `WebSocketStatus.css`
  - **Files Modified**: `frontend/src/layouts/Sidebar.jsx`

### Documentation
- **API Audit Report** - Complete frontend-backend API audit
  - 95 endpoints analyzed
  - All critical issues identified and fixed
  - Security audit included
  - **File Created**: `FRONTEND_BACKEND_API_AUDIT_RESULTS.md`

- **Implementation Summary** - Detailed change documentation
  - Complete testing checklist
  - Migration guide for developers
  - Rollback plan included
  - **File Created**: `CRITICAL_FIXES_AND_IMPROVEMENTS_v3.5.3.md`

### Changed
- Updated version numbers across all files to 3.5.3
- Sidebar now displays real-time connection status
- All pages wrapped in error boundaries for better resilience
- Frontend bundle size: +~15KB (new features)

---

## [3.5.2] - 2025-10-13

### Fixed
- **Database Initialization** - Fixed crash on first run with fresh database ✅
  - **Problem**: Server crashed with `sqlalchemy.exc.OperationalError: no such table: system_settings`
  - **Root Cause**: Module-level code tried to query database before tables were created
  - **Solution**:
    - Removed module-level database query (line 493 in main.py)
    - Moved static file mounting into `startup_event()` after database initialization
    - Proper initialization sequence: Create DB → Load settings → Mount directories
  - **Benefits**:
    - ✅ Server starts successfully on first run
    - ✅ Static files mounted with correct user-configured paths
    - ✅ No race conditions between module import and database init
    - ✅ Clean logging showing initialization progress
  - **Files Modified**: `backend/main.py` (removed 170 lines, added 56 lines in startup_event)

- **Process Cleanup** - Complete resolution of orphaned process issue ✅
  - **Problem**: Python/uvicorn processes remained running after shutdown, requiring force quit
  - **Root Causes**:
    - Daemon threads in facial recognition and cloud storage without stop mechanisms
    - Incomplete shutdown sequence (only 2 of 7 required cleanup steps)
    - No signal handlers for SIGINT/SIGTERM
    - Uvicorn --reload mode creating orphaned resource tracker subprocess
  
  - **Solutions Implemented**:
    1. Enhanced shutdown sequence in `backend/main.py`:
       - Added signal handlers (SIGINT, SIGTERM) with global shutdown flag
       - Comprehensive 7-step shutdown with individual timeouts:
         * Stop statistics broadcaster (5s timeout)
         * Close all WebSocket connections
         * Stop all cameras
         * Stop facial recognition threads
         * Stop cloud storage threads  
         * Close database connections
         * Cancel remaining async tasks
       - Detailed logging with ✓/✗/⚠ indicators for each step
       - Error recovery (continues even if step fails)
    
    2. Facial recognition thread cleanup in `backend/core/facial_recognition_system.py`:
       - Added `_stop_event = threading.Event()` for stop signaling
       - New `stop_processing()` method with:
         * Stop event flag
         * Queue sentinel value to unblock `queue.get()`
         * Thread join with 5s timeout
         * Timeout verification and logging
       - Modified `_process_queue()` to check stop event in loop
    
    3. Improved cloud storage thread cleanup in `backend/core/cloud_storage_system.py`:
       - Enhanced `stop_upload_worker()` with proper timeout handling
       - Added verification logging
       - Queue status reporting (pending tasks)
    
    4. WebSocket cleanup in `backend/core/websocket_manager.py`:
       - New `disconnect_all()` method for graceful connection closing
       - Sends shutdown notification to clients
       - Proper close code (1000, "Server shutting down")
       - Clears all connection dictionaries
    
    5. New `stop-server.sh` graceful shutdown script:
       - Finds all uvicorn processes
       - Sends SIGTERM for graceful shutdown
       - 10-second timeout with countdown display
       - Force kill (SIGKILL) fallback if timeout
       - Cleans up orphaned processes
       - Verifies port 8000 is freed
       - Color-coded output (green/yellow/red)
    
    6. Enhanced `start-local.sh` with cleanup trap:
       - Added `cleanup()` function
       - Trap handler for EXIT, INT, TERM signals
       - Captures uvicorn PID for controlled shutdown
       - Sends SIGTERM on Ctrl+C
       - Waits up to 10s for graceful stop, force kills if timeout

  - **Results**:
    - ✅ No orphaned processes after shutdown (verified with `ps aux`)
    - ✅ Port 8000 immediately available (verified with `lsof -ti:8000`)
    - ✅ Ctrl+C works correctly with graceful shutdown
    - ✅ Both manual (Ctrl+C) and script (`./stop-server.sh`) shutdown work perfectly
    - ✅ Detailed shutdown logging for troubleshooting
    - ✅ Graceful 10s timeout with force kill fallback
    - ✅ No resource tracker subprocesses left running
    - ✅ 100% success rate across all test scenarios

### Documentation
- **Process Cleanup Fix Guide**: `docs/development/PROCESS_CLEANUP_FIX.md` (800 lines)
  - Complete root cause analysis (4 main issues)
  - 6 comprehensive solutions with ready-to-use code
  - 7-step implementation checklist
  - Verification procedures
  - Before/after comparisons

- **Implementation Summary**: `PROCESS_CLEANUP_IMPLEMENTATION_v3.5.3.md`
  - Testing results and verification
  - Before vs after comparison
  - Files modified (6 files)
  - Verification commands
  - Known issues

### Testing
- ✅ Start and Ctrl+C shutdown: Clean stop in < 1 second
- ✅ Process verification: Zero orphaned processes
- ✅ Port availability: 8000 freed immediately  
- ✅ Shutdown logging: All 7 steps complete successfully
- ✅ Script-based shutdown: `./stop-server.sh` works perfectly
- ✅ Force kill fallback: Tested and verified

---

## [3.5.2] - 2025-10-12

### Fixed
- **Snapshot Display Bug** - Fixed critical issue where snapshot thumbnails showed broken images
  - Root cause: Database stores absolute file system paths but frontend tried to use them as URLs
  - Solution: Added `convertPathToUrl()` function in RecordingsPage.jsx to convert paths to web URLs
  - Fixed path detection logic to handle both custom storage paths and legacy default paths
  - Download button now works correctly with converted paths
  - All snapshots load properly with HTTP 200 responses

- **Path Validation** - Advanced settings now auto-verify storage paths
  - Added visual feedback for valid/invalid paths
  - Improved user experience when configuring custom storage locations

- **Slider Validation** - Fixed input validation issues in advanced settings
  - Range sliders now properly enforce min/max values
  - Improved user feedback for invalid inputs

### Improved
- **Docker Build Optimization** - Reduced build context from 8GB to ~50MB (99% reduction)
  - Updated `.dockerignore` with comprehensive exclusions
  - Excluded venv/ (5.8GB), all media files, Python cache, test data
  - Build times significantly improved
  - Image size remains optimized at 2GB (compresses to ~650MB on Docker Hub)

- **Project Cleanup** - Enhanced repository organization and security
  - Updated `.gitignore` with comprehensive media file exclusions
  - Removed all Python cache files (__pycache__, *.pyc)
  - Excluded 1,089 media files (snapshots, videos) from git
  - No personal data or surveillance footage in repository
  - Proper separation of code vs user data

- **Documentation** - Consolidated and organized project documentation
  - Moved deployment docs to `docs/deployment/`
  - Moved development docs to `docs/development/`
  - Removed redundant session summaries and task-specific documents
  - All release information consolidated in CHANGELOG.md
  - Created comprehensive deployment verification report
  - Only essential files remain in project root

### Deployment
- **Automated Deployment Scripts** - New tools for easy deployment
  - `deploy.sh` - Interactive script for GitHub and Docker Hub deployment
  - `prepare-deployment.sh` - Pre-deployment checks and cleanup
  - `cleanup-docs.sh` - Documentation organization automation

- **Docker Hub** - Published images now available
  - Repository: `im1k31s/openeye-opencv_home_security`
  - Tags: `v3.5.2` and `latest`
  - Multi-stage optimized build
  - No media files included in images

- **GitHub** - Repository fully synced and updated
  - All changes committed and pushed
  - Documentation organized in proper structure
  - Privacy-compliant (no surveillance data exposed)

### Security
- **Privacy Protection** - No sensitive data exposed
  - Verified zero media files in GitHub repository (current and history)
  - Verified zero media files in Docker Hub images
  - All user data (faces, recordings, snapshots) remains local only
  - Database files properly excluded
  - Environment files properly excluded

---

## [Unreleased]

### Added
- **Complete API Migration** - All frontend pages now use centralized apiClient
  - Migrated 7 pages: SystemSettingsPage, DashboardPage, FaceManagementPage, CameraManagementPage, RecordingsPage, AlertSettingsPage, CameraDiscoveryPage
  - Automatic JWT token injection
  - Graceful 401 error handling
  - Public endpoint bypass for unauthenticated routes
  - No more console spam when not logged in

- **Event-to-Recording Linking** - Database improvements for better event tracking
  - Added `recording_id` foreign key to FaceDetectionEvent model
  - Added bi-directional relationship between FaceDetectionEvent and RecordingEvent
  - Frontend timeline events now link directly to source recordings
  - Click any event to jump to its recording playback

- **Comprehensive API Documentation** - New docs/ directory structure
  - Created `docs/API_REFERENCE.md` with complete API endpoint documentation
  - Created `docs/TODO.md` with development checklist and roadmap
  - Consolidated all API audit documents into reference guide
  - Removed temporary audit documents from project root

- **HIG Split View Layout** - Complete Apple Human Interface Guidelines implementation
  - Persistent sidebar navigation with 6 sections (Dashboard, Events, Cameras, Faces, System, Themes)
  - Frosted glass effects with 20px backdrop blur and color saturation
  - Responsive breakpoints: 1024px (tablet), 768px (mobile), 480px (small mobile)
  - MainLayout component with fixed header and dynamic content pane
  - Section-based routing replacing old page-based navigation
  - Mobile-friendly collapsible sidebar with hamburger menu
  - Accessibility features: keyboard navigation, screen reader support, reduced motion support

- **Live Dashboard Section** - Real-time camera monitoring and event timeline
  - Camera grid with auto-fill columns (minmax 320px)
  - Collapsible event timeline (300px right panel)
  - Real-time API integration with auto-refresh every 10 seconds
  - Merged motion events and face detection events in unified timeline
  - Clickable events linked to recordings with recording_id
  - Event metadata display: duration, confidence, face counts
  - "Recording Available" badge on all linked events
  - Error handling with fallback states

- **Centralized API Client** - No more 401 error spam!
  - Automatic JWT token injection for authenticated requests
  - Smart public endpoint bypass (no auth for /token, /setup/status)
  - Graceful 401 handling (only redirects if token existed and expired)
  - No more console spam when unauthenticated
  - Request/response interceptors for consistent error handling
  - Helper functions: isAuthenticated(), validateToken(), setToken(), clearAuth()

- **API Integration Audit Document** - Complete backend-frontend mapping
  - All 80+ API endpoints documented
  - Data structure schemas for each endpoint
  - Frontend component → API endpoint mapping
  - Identified integration gaps and opportunities
  - Phase-based implementation recommendations

- **Aqua Security Theme** - New modern liquid glass theme with frosted transparency
  - Frosted glass/liquid glass aesthetic with backdrop blur effects
  - Dynamic cyan accents (#00AEEF) on deep charcoal background (#1A1A1D)
  - Modern glassmorphism design with 20px blur strength
  - Enhanced depth with subtle shadows and transparency layers
  - Pill-shaped buttons with smooth cubic-bezier transitions
  - Full compatibility with existing component system

### Changed
- **All Frontend Pages** - Migrated to centralized API client
  - SystemSettingsPage: 5 API calls migrated
  - DashboardPage: 4 API calls migrated
  - FaceManagementPage: 10 API calls migrated (including file upload)
  - CameraManagementPage: 4 API calls migrated
  - RecordingsPage: 5 API calls migrated
  - AlertSettingsPage: 6 API calls migrated
  - CameraDiscoveryPage: 5 API calls migrated
  - Total: 39 API calls standardized with authentication handling

- **Database Schema** - Improved data model relationships
  - FaceDetectionEvent now includes `recording_id` FK (nullable)
  - RecordingEvent includes `face_detections` relationship
  - Camera model `last_active` renamed to `last_active_at` for consistency
  - All timestamp fields now use consistent `*_at` naming convention

- **Authentication System** - Improved to prevent 401 spam
  - Created apiClient.js replacing direct axios calls
  - Only adds Authorization header when token exists
  - Skips auth for public endpoints automatically
  - Redirects to login only if token expired (not missing)
  - Prevents redirect loops on login page

- **Event Timeline** - Enhanced with rich metadata
  - Merged motion events (recordings) with face detections
  - Shows "Motion + Face" combined events
  - Displays person names for face detections
  - Shows confidence percentage for face recognition
  - Shows duration for motion recordings
  - Hover effects with Aqua Security cyan glow
  - Clickable with cursor:pointer and visual feedback

- **Camera Grid** - Fixed API integration
  - Now uses correct field names: camera_id, is_active (not id, active)
  - Handles API response structure: {cameras: [...], total: number}
  - Added error handling for stream failures with SVG fallback
  - Displays resolution and motion detection status

- **Routing Architecture** - Section-based vs page-based
  - Old: /dashboard, /face-management, /camera-discovery (separate pages)
  - New: /, /events, /cameras, /faces, /system, /themes (nested routes)
  - React Router Outlet for dynamic content rendering
  - All sections share MainLayout wrapper (header + sidebar)
  - No page reloads, smooth client-side transitions

- **Global Button Style** - Applied pill-shaped buttons (border-radius: 999px) to all themes
  - Smooth transitions with cubic-bezier easing (0.2s)
  - Subtle lift effect on hover (translateY(-1px))
  - Enhanced box shadows for depth
  - Each theme retains its unique color palette
  - Consistent padding (8px 20px) and font-weight (500)

- **Input Fields** - Updated with rounded corners (12px) for modern consistency
- **Cards/Panels** - Added rounded corners (12px) and subtle shadows across all themes
- **Theme System** - Updated from 8 to 9 available themes

### Fixed
- **401 Authentication Error Spam** - No more console spam!
  - Created centralized API client with smart interceptors
  - Only attempts authentication when token exists
  - Public endpoints bypass authentication
  - Graceful error handling prevents redirect loops

- **Timeline Event Data Structure** - Fixed multiple API format issues
  - Added array validation before .map() calls
  - Handle multiple response structures (array, {recordings: []}, {detections: []})
  - Added fallback keys for event rendering
  - Merged recording and detection timestamps correctly

- **Camera Feed Not Working** - Fixed stream display
  - Corrected API field names (camera_id vs id, is_active vs active)
  - Added onError handler for stream failures
  - Displays SVG fallback when stream unavailable
  - Fixed Authorization header injection

- **Placeholder Data** - Replaced with real API data
  - Timeline now shows actual recordings from /api/recordings/
  - Face detections from /api/history/detections
  - Camera list from /api/cameras/ with correct structure
  - All events include complete metadata (timestamps, faces, durations)

- **Backend Type Annotations** - Added missing typing imports for Python 3.12 compatibility
  - Fixed `Optional` import in `backend/core/image_processor.py`
  - Fixed `Tuple, List, Dict` imports in `backend/core/face_detection.py`
  - Fixed typing imports in `backend/core/facial_recognition_system.py`
  - Resolved `NameError` issues preventing server startup

### Documentation
- Created `docs/API_REFERENCE.md` - Complete API documentation (700+ lines)
- Created `docs/TODO.md` - Development checklist and roadmap
- Created `IMPLEMENTATION_SUMMARY_v3.5.2.md` - Complete task implementation summary
- Removed `API_INTEGRATION_AUDIT_v3.5.2.md` - Consolidated into API_REFERENCE
- Removed `API_NAMING_CONSISTENCY_AUDIT_v3.5.2.md` - Consolidated into API_REFERENCE
- Removed `API_CONSISTENCY_FIXES_v3.5.2.md` - Consolidated into TODO.md
- Updated CHANGELOG.md with comprehensive Phase 1 and Phase 2 changes

### Technical Notes
- Frontend requires rebuild after changes: `npm run build`
- Latest build hash: `index-211a1e2f.js` (226.46 kB gzipped: 74.82 kB)
- API client is now the standard way to make backend calls
- All components should import apiClient, not axios directly (except public endpoints)
- List API responses now wrapped with metadata: {items: [...], total: N, filtered: N}
- Frontend uses backward-compatible handlers (supports both wrapped and legacy array responses)
- Recording events include full metadata: faces_detected, known_faces_detected, duration_seconds
- Every recording has a unique recording_id that links to playback
- Face detections now include recording_id FK linking back to source video
- Database migration script: `scripts/migrate_database_v3.5.2.py`
- Run migration: `cd opencv_surveillance && source venv/bin/activate && python scripts/migrate_database_v3.5.2.py`
- Theme applies via CSS class on `html` element for maximum specificity
- Button styles are global, theme-specific colors take precedence
- All UI elements now have consistent rounded corners for modern aesthetic

### Known Issues
- WebSocket connection shows 403 errors (token validation issue - not yet fixed)
- Some legacy page components still exist but are unused
- Camera Manager, AI & Faces, System & Alerts sections are placeholders (Phase 2)
- Themes section needs existing ThemeSelectorPage migration

### Next Phase (v3.5.3)
- Wrap all list API responses with metadata objects
- Remove duplicate `/api/users/login` endpoint
- Implement full Events & History section (master-detail timeline)
- Implement full Camera Manager section (detection zones, configuration)
- Implement full AI & Faces section (gallery, enrollment workflow)
- Implement full System & Alerts section (iOS-style settings)
- Connect WebSocket for real-time updates (fix 403 auth issue)
- Remove legacy page components
- Add recording playback modal
- Implement face detection filtering in timeline
- Create database migrations for schema changes

---

## [3.5.1.4] - 2025-10-11

### Fixed
- **CRITICAL: Path Validation 422 Errors** - Fixed route ordering issue in settings API
  - Reordered FastAPI routes to put specific `/settings/validate-path` before generic `/settings/{setting_key}`
  - Prevents path parameter matching that was causing Pydantic validation errors
  - Users can now successfully validate and configure custom storage paths
  - Enhanced frontend error logging to display detailed Pydantic validation errors

### Changed
- **Version Updates** - Updated version to 3.5.1.4 across all backend endpoints
  - FastAPI app version (main.py)
  - Root endpoint version
  - API root endpoint version

### Documentation
- Added comprehensive root cause analysis in PATH_VALIDATION_FIX_v3.5.1.4.md
- Created TESTING_CHECKLIST_v3.5.1.4.md with 40+ test scenarios
- Documented FastAPI route ordering best practices

### Technical Details
- **Root Cause**: FastAPI matches routes in order; generic routes with path parameters must come AFTER specific routes
- **Impact**: Enables System Settings page path validation to work correctly
- **Testing**: Verified with 200 OK responses for path validation, settings persistence confirmed

---

## [3.5.1.0-3.5.1.3] - 2025-10-10 to 2025-10-11

### Added
- **System Settings Page** - New comprehensive settings interface
  - Custom storage path configuration for recordings and face images
  - Path validation with directory creation support
  - Display mode controls (Grid/Vertical/Horizontal/Cycle)
  - Recording duration and cycle interval settings
  - Per-camera feature toggles (Motion Detection, Recording, Face Detection)
  
- **System Settings API** - Backend support for configurable system settings
  - Database model for storing key-value settings
  - CRUD operations for system settings
  - Path validation endpoint
  - Settings persistence across restarts

- **Display Modes** - Multiple camera layout options
  - Grid view (default)
  - Vertical split (2 columns)
  - Horizontal rows
  - Auto-cycle between cameras with configurable interval

- **Granular Camera Controls** - Per-camera feature toggles
  - Enable/disable motion detection per camera
  - Enable/disable recording per camera
  - Enable/disable face detection per camera
  - Settings persist in database

### Changed
- **Camera Defaults** - New cameras default to features disabled for user control
- **Recorder** - Supports configurable output directory and recording duration
- **Face Detection** - Supports configurable faces directory path
- **Camera Manager** - Loads and merges system settings on startup

### Fixed
- Settings page tab persistence and UI improvements (v3.5.1.1)
- Recordings page playback and metadata display (v3.5.1.2)
- Path selection browser security restrictions (v3.5.1.3)

---

## [3.4.0] - 2025-01-10

### Added
- **WebSocket Real-Time Updates (MAJOR PERFORMANCE IMPROVEMENT)**: Replaced polling with WebSocket connections
  - 99% bandwidth reduction (~360 KB/hour → ~1 KB/hour)
  - 50x faster updates (<100ms latency vs 0-5 seconds)
  - Real-time statistics streaming to dashboard
  - Automatic reconnection with exponential backoff (1s → 30s max)
  - Graceful fallback to polling if WebSocket unavailable
  - Connection health indicator (🟢 Live / 🟡 Connecting / 🔵 Polling)
  - JWT authentication on WebSocket connection
  - Rate limiting (max 5 connections per user)
  - Keep-alive ping every 30 seconds
- **WebSocket Connection Manager**: Thread-safe connection lifecycle management
  - Per-user connection tracking
  - Broadcast to all or specific users
  - Automatic cleanup of stale connections
  - Connection statistics endpoint
- **Background Statistics Task**: Periodic broadcasting every 5 seconds
  - Face recognition statistics
  - Camera events
  - System alerts

### Changed
- **Dashboard Page**: Integrated WebSocket service with fallback logic
  - Real-time statistics updates via WebSocket
  - Visual connection status in header
  - Polling only used if WebSocket fails
- **Backend Architecture**: Added async background tasks
  - Statistics broadcast task in main.py
  - WebSocket manager singleton pattern
  - Event-driven updates

### Technical
- **Backend**: 
  - `backend/core/websocket_manager.py`: Connection management (285 lines)
  - `backend/api/routes/websockets.py`: WebSocket endpoints (186 lines)
  - `backend/main.py`: Background broadcast task
- **Frontend**:
  - `frontend/src/services/WebSocketService.js`: WebSocket client (345 lines)
  - `frontend/src/pages/DashboardPage.jsx`: WebSocket integration
- **Documentation**: Complete implementation guide (`WEBSOCKETS_IMPLEMENTATION.md`)

### Performance
- **Bandwidth**: 99.7% reduction (360 KB/hour → 1 KB/hour)
- **Latency**: 50x improvement (5000ms → 100ms)
- **Server Load**: 99.86% reduction (720 requests/hour → 1 request/hour)

---

## [3.3.8] - 2025-10-09

### Fixed
- **Help Button Tooltip Flickering (CRITICAL UX)**: Fixed tooltip disappearing when moving mouse toward it
  - Root cause: No delay on hide + conflicting hover/click handlers + tooltip couldn't receive mouse events
  - Added 300ms delay before hiding tooltip to allow smooth mouse movement
  - Added `pointer-events: auto` to tooltip so it can receive mouse events
  - Tooltip now stays visible when hovering over it
  - Click-outside-to-close functionality added
  - Better mobile support with fixed positioning
  - Cleanup of timeouts on unmount to prevent memory leaks
  - Added `aria-expanded` attribute for accessibility
- **Help Button Mobile Support**: Improved tooltip positioning on mobile devices
  - Changed to `position: fixed` with bottom positioning
  - Arrow pointer now points upward from bottom
  - Better touch device interaction

### Changed
- Enhanced help tooltip UX with smooth transitions
- Hover shows/hides smoothly, click toggles for touch devices
- Added proper z-index layering (container: 100, tooltip: 1001)
- Improved accessibility with proper ARIA attributes

### Technical
- **Frontend**: Added `useRef` and `useEffect` hooks for timeout management
- **CSS**: Added `pointer-events: auto` to enable tooltip interaction
- **Mobile**: Fixed positioning prevents tooltip from going off-screen

---

## [3.3.7] - 2025-10-10

### Added
- **Password Visibility Toggle**: Eye/hide emoji buttons for passwords in First-Run Setup and Login pages
- **API Documentation**: Comprehensive API reference with examples (`/docs/API_DOCUMENTATION.md`)
  - Complete endpoint documentation
  - Python and JavaScript integration examples
  - Webhook integration guide
  - Authentication guide

### Fixed
- **Face Recognition Photo Upload (CRITICAL)**: Fixed invisible file upload button
  - Root cause: Undefined CSS variable `var(--primary-color)`
  - Solution: Hardcoded blue color (#007bff) with enhanced styling
  - Added file icon, bold text, hover effects
  - Users can now successfully upload photos and train face recognition
- **Camera Discovery 404 Errors**: Fixed `/api/cameras/discover/status` returning 404
  - Root cause: Router registration order
  - Solution: Moved discovery router before cameras router in `main.py`
  - Eliminates console spam during camera scanning
- **Alert Configuration Validation**: Fixed 422 errors when saving alert config
  - Empty strings now properly converted to `null` for backend validation
- **Content Security Policy**: Updated CSP to allow `data:` URIs for inline SVG images

### Changed
- Enhanced file upload modal with explicit styling to prevent CSS conflicts
- Improved console logging for debugging file uploads and modal rendering
- Better error messages for alert configuration saves

### Technical
- **Frontend**: Axios interceptor properly reads JWT token on every request
- **Backend**: Router order ensures discovery routes take precedence
- **CSP Headers**: `img-src 'self' data:;` allows inline SVG images

---

## [3.3.0] - 2025-10-08

### Fixed
- **Async/Await Context Issues**: Fixed `asyncio.create_task()` being called from synchronous camera threads by using `asyncio.run_coroutine_threadsafe()` instead
- **Missing camera_id Attribute**: Camera instances now properly store their ID on both camera and recorder objects
- **Password Hashing Consistency**: Standardized all password hashing to use `auth.hash_password()` throughout the codebase
- **Missing Directory Creation**: Added automatic creation of required directories (recordings, faces, data, snapshots, thumbnails) on startup
- **Thread Safety**: Implemented `threading.Lock()` for all CameraManager dictionary operations to prevent race conditions
- **Face Detection Logging**: Face detection data now properly logged to recorder metadata during recording sessions
- **Database Schema Verification**: Added runtime assertion to ensure Base classes are identical across models

### Changed
- Improved error handling for motion alert triggering
- Enhanced thread-safe camera management
- Better metadata tracking for face detections in recordings

### Technical Details
- Fixed RuntimeError exceptions in motion alert system
- Camera identification now works correctly throughout application
- All user creation flows use consistent password hashing
- Application works on fresh installations without manual directory creation
- Thread-safe camera management prevents crashes and race conditions
- Recording metadata includes all detected faces with timestamps and frame numbers

---

## [3.2.9] - 2025-10-07

### Fixed
- **Theme System**: Complete rewrite of theme system to fix CSS specificity conflicts
- **Import Order**: Fixed CSS import order in main.jsx (themes.css before index.css)
- **Theme Application**: Themes now properly apply to `<html>` element instead of wrapper div
- **CSS Variables**: Unified all theme CSS variables under single themes.css file
- **Theme Switching**: Removed conflicts between global-theme.css and themes.css

### Changed
- Removed wrapper div from ThemeContext for cleaner DOM structure
- Applied themes to document.documentElement for maximum CSS specificity
- Cleaned up index.css to remove all hardcoded colors
- All 8 themes now fully functional with proper color application

---

## [3.2.8] - 2025-10-07

### Fixed
- Alert Settings Page CSS corruption causing spinning text boxes
- SMTP configuration code block styling (dark background)
- Method description text color (uses var(--text-primary))
- No-logs message color (uses #88c0d0)
- Help text and link styling

### Added
- Comprehensive macOS USB camera limitations documentation
- Four workarounds for macOS USB camera issues:
  - Use Network/IP Cameras (Recommended)
  - Run Backend Natively on macOS
  - USB/IP Forwarding (Experimental)
  - Use Linux Development Environment

### Documentation
- Created DOCKER_HUB_DESCRIPTION.md with complete overview
- Updated README with USB camera limitations
- Improved Docker Hub description

---

## [3.2.0] - 2025-10-06

### Changed
- **Major UI/UX Restructure**: Complete overhaul of frontend interface
- Improved navigation and user experience
- Enhanced component organization
- Better responsive design

---

## [3.1.3] - 2025-10-05

### Fixed
- **Bcrypt Truncation Issue**: Properly handle bcrypt's 72-byte limit
- Password truncation now done transparently in hash_password()
- No more silent password length errors
- Updated documentation with password limits

### Security
- Enhanced password hashing security
- Better error messages for password issues

---

## [3.1.2] - 2025-10-05

### Fixed
- **Password Validation**: Fixed password validation errors
- **White Screen Issue**: Resolved blank screen on startup
- Frontend routing issues
- Database initialization problems

### Changed
- Improved error handling in authentication flow
- Better user feedback for login issues

---

## [3.1.1] - 2025-10-05

### Fixed
- **Frontend Serving**: Fixed React frontend not being served correctly
- Static file serving configuration
- Build output path issues

### Changed
- Updated Dockerfile to properly copy frontend build
- Improved static file handling in FastAPI

---

## [3.1.0] - 2025-10-05

### Added - Camera Discovery
- **USB Camera Detection**: Automatic scanning of USB webcams (indices 0-10)
- **Network RTSP Scanning**: Discovers IP cameras on local subnets
- **Pre-Add Testing**: Validate camera connections before adding
- **Auto-Configuration**: Automatically generates camera configs with resolution/FPS
- **One-Click Addition**: Quick-add discovered cameras
- New CameraDiscovery service
- API endpoints for camera discovery:
  - `GET /api/cameras/discover/usb` - Discover USB cameras
  - `GET /api/cameras/discover/network` - Discover network cameras

### Added - Camera Management
- Complete camera management interface
- Three-tab interface (List, Discovery, Manual)
- Live camera status indicators
- Enable/disable camera toggle
- Delete cameras with confirmation
- Common RTSP URL templates
- Form validation and error handling
- API endpoints:
  - `GET /api/cameras/` - List all cameras
  - `POST /api/cameras/` - Add new camera
  - `GET /api/cameras/{id}` - Get camera details
  - `PUT /api/cameras/{id}` - Update camera
  - `DELETE /api/cameras/{id}` - Remove camera

### Added - Theme System
- 8 superhero-inspired themes:
  - Default (Dark Professional)
  - Superman (Classic red/blue)
  - Batman (Dark knight)
  - Wonder Woman (Warrior princess)
  - Flash (Speed force)
  - Aquaman (Ocean depths)
  - Cyborg (Tech enhanced)
  - Green Lantern (Willpower)
- Custom color palettes and typography per theme
- Animated overlays and effects
- Persistent theme selection (localStorage)
- Live theme preview
- Theme selector page

### Added - Help System
- 36+ inline help entries
- Context-sensitive help
- Modal help dialogs
- Comprehensive documentation for all features

### Added - First-Run Setup
- Setup wizard for first-time users
- Admin account creation
- Security key generation
- Database initialization
- Guided setup process

### Documentation
- Complete Docker deployment guide
- Camera discovery usage guide
- Web dashboard documentation
- Theme system documentation
- Updated README with all new features

---

## [3.0.0] - 2025-10-01

### Added - Core Features (Phases 1-2)
- Multi-camera support (RTSP streams and mock cameras)
- Motion detection using OpenCV MOG2 background subtraction
- Automatic motion-triggered recording
- Live MJPEG streaming with real-time overlays
- Face recognition with dlib
- Face management interface
- Detection history tracking
- SQLite database persistence
- User authentication and authorization

### Added - Notifications (Phase 3)
- Email alerts via SMTP
- SMS alerts (Twilio integration)
- Push notifications (Firebase)
- Webhook support
- Alert throttling to prevent spam
- Configurable notification channels

### Added - Smart Home Integration (Phase 4)
- Home Assistant MQTT integration
- Apple HomeKit bridge
- Google Nest integration
- Automation triggers

### Added - Cloud & Mobile (Phase 5)
- Cloud storage support (AWS S3, Google Cloud Storage, Azure Blob)
- MinIO support for self-hosted cloud storage
- React Native mobile app foundation
- WebSocket real-time streaming
- Remote access via WireGuard/Tailscale

### Added - Advanced Features (Phase 6)
- Recording management (search, download, stream)
- Advanced analytics (hourly/daily activity breakdown)
- Storage management with automatic cleanup
- Multi-user system (Admin, User, Viewer roles)
- Rate limiting for API protection
- SQL injection protection
- PostgreSQL support for production
- Docker containerization

### Added - API
- Complete REST API with FastAPI
- JWT authentication
- API documentation (Swagger/ReDoc)
- Rate limiting
- CORS support

### Added - Frontend
- React-based web interface
- Real-time video streaming
- Face management UI
- Camera configuration
- Settings and preferences
- Responsive design

### Security
- JWT-based authentication
- Bcrypt password hashing
- API rate limiting
- SQL injection protection
- CORS configuration
- Environment variable configuration

---

## Future Work

### Planned Features
- [ ] Advanced face recognition training options
- [ ] License plate recognition (ALPR)
- [ ] Object detection (YOLO integration)
- [ ] Timeline playback system
- [ ] Two-way audio support
- [ ] Advanced analytics dashboard
- [ ] Mobile app completion
- [ ] Multi-server support
- [ ] Kubernetes deployment guide
- [ ] Advanced automation rules
- [ ] Integration with more smart home platforms
- [ ] Custom alert rules engine
- [ ] Video analytics (people counting, dwell time)
- [ ] Heat map generation
- [ ] PTZ camera control
- [ ] Audio event detection
- [ ] Cloud backup automation
- [ ] Multi-language support
- [ ] Dark/light mode toggle
- [ ] Custom dashboard widgets

### Known Limitations
- macOS Docker USB camera support limited (requires native backend or network cameras)
- Face recognition is CPU-intensive (GPU acceleration recommended for multiple cameras)
- SQLite has limitations for >5 concurrent users (use PostgreSQL for production)
- dlib installation requires system dependencies (cmake, libopenblas-dev, liblapack-dev)

---

## Links

- **GitHub Repository**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security
- **Docker Hub**: https://hub.docker.com/r/im1k31s/openeye-opencv_home_security
- **Documentation**: See README.md
- **Issues**: https://github.com/M1K31/OpenEye-OpenCV_Home_Security/issues

---

*For detailed installation instructions, usage examples, and troubleshooting, see the [README.md](README.md)*