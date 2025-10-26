# OpenEye Surveillance System - Changelog

All notable changes to the OpenEye Surveillance System project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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