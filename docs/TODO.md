# OpenEye Development ToDo List
**Last Updated**: 2025-11-09

## ✅ Completed

### v3.8.0 - Security & Communication Features (2025-11-09)
- [x] **JWT Refresh Token System** (complete automatic token refresh implementation)
  - RefreshToken database model with Alembic migration
  - Token rotation security pattern (new refresh token on each refresh)
  - /token/refresh, /token/revoke, /token/revoke-all endpoints
  - authService.js rewritten with automatic refresh timer (5 minutes before expiry)
  - 30-minute access tokens, 7-day refresh tokens
  - Device tracking for security audit (user agent, IP address)
- [x] **Two-Way Audio React UI** (production-ready frontend for two-way audio)
  - TwoWayAudio.jsx component with WebRTC connection management
  - TwoWayAudio.css with theme-aware styling and animations
  - Integrated into CameraSettingsModal with dedicated audio tab
  - Microphone permission handling with error states
  - Audio controls (speak, listen, mute/unmute)
  - Real-time connection status indicators

### v3.7.2 - Security Update (2025-11-08)
- [x] Vite 7 upgrade (resolves 6 moderate severity vulnerabilities)
- [x] Frontend dependency security update
- [x] Node.js requirement updated to 20+

### v3.7.1 - FFmpeg Hardware Encoding
- [x] FFmpeg hardware-accelerated video recording (NVENC, QuickSync, VideoToolbox, VAAPI)
- [x] 70-90% CPU reduction during recording
- [x] Async frame buffer (300-frame queue)
- [x] Performance Settings UI in System Settings
- [x] Zero dropped frames with async writer

### v3.7.0 - UX Improvements
- [x] EventDetailModal component for inline event viewing
- [x] Universal Button component integration (Apple HIG compliant)
- [x] Motion detection zones API and UI
- [x] PTZ camera control (backend + frontend)
- [x] Safari browser detection for PiP feature

### v3.6.2 - Motion Threshold UI
- [x] Motion detection threshold slider in System Settings
- [x] Documentation link fixes after consolidation

### v3.6.1 - 2FA Complete Implementation
- [x] Two-factor authentication (2FA) backend (TOTP, QR codes, backup codes)
- [x] **2FA Frontend UI** (`TwoFactorSettings.jsx` - 538 lines)
- [x] **2FA Login Integration** (token + backup code support in `LoginPage.jsx`)
- [x] **2FA Service Layer** (`twoFactorService.js`)
- [x] **2FA Routes** (`/system/2fa`)
- [x] QR code enrollment, backup codes, enable/disable functionality

### v3.6.0 - Security Hardening (MAJOR RELEASE)
- [x] Per-endpoint rate limiting with granular API category limits
- [x] CSRF protection using double-submit cookie pattern
- [x] Two-factor authentication (2FA) with TOTP and QR codes (BACKEND)
- [x] Enhanced audit logging system (42 event types, JSONL format)
- [x] Face clustering for unknown faces (DBSCAN algorithm)
- [x] Notification provider credential encryption (Fernet)
- [x] **WebSocket Authentication** (JWT token verification, proper error handling)

### v3.5.6 - Timeline & Accessibility
- [x] Timeline playback system with interactive event markers
- [x] Accessibility improvements (keyboard navigation, screen reader support)
- [x] Browser cache fixes
- [x] Timeline event linking to recordings

### v3.5.3 - Performance & Stability
- [x] React code splitting and lazy loading (77% bundle size reduction)
- [x] Process cleanup with graceful shutdown
- [x] Database migration system (Alembic)
- [x] Enhanced error boundaries

### v3.5.2 - Frontend Migration
- [x] Create centralized apiClient with auth interceptors
- [x] Migrate all pages to apiClient (Dashboard, Cameras, Faces, Recordings, Alerts, Discovery)
- [x] Add `recording_id` FK to FaceDetectionEvent model
- [x] Add relationship between FaceDetectionEvent and RecordingEvent
- [x] Rename `Camera.last_active` to `Camera.last_active_at`

### Core Features (Various Versions)
- [x] Cloud storage integration (S3, GCS, Azure, MinIO)
- [x] Smart home integration (Home Assistant MQTT, HomeKit bridge)
- [x] Automation engine with person-based triggers
- [x] WebSocket real-time updates for statistics
- [x] **WebSocket authentication with JWT** (implemented in `websockets.py`)
- [x] 9 customizable themes (Superman, Batman, Wonder Woman, etc.)
- [x] Integrated help system (36+ context-sensitive entries)
- [x] Camera discovery (USB, ONVIF network cameras)
- [x] First-run setup wizard
- [x] **Two-way audio backend** (WebRTC, audio processing, routes registered)

### Testing Infrastructure
- [x] **Backend testing framework** (pytest configured, 12 test files)
- [x] **Frontend testing framework** (Vitest configured, test scripts in package.json)
- [x] Test configuration files (conftest.py, setup.js)
- [x] Initial test files (authService, ErrorBoundary, API tests)
- [x] Coverage reporting configured (pytest-cov, vitest coverage-v8)

### Documentation
- [x] Create comprehensive API Reference Guide
- [x] Create ToDo checklist document
- [x] Create docs/ directory structure
- [x] Consolidate 252+ documentation files
- [x] Security guides and testing documentation

---

## 🔄 In Progress (v3.8.0 Development)

### Critical Security Enhancements
- [x] **JWT Refresh Token Implementation** (COMPLETED 2025-11-09)
  - ✅ Automatic token refresh with refresh token rotation
  - ✅ Backend: RefreshToken model, migration, CRUD operations
  - ✅ Backend: /token/refresh, /token/revoke, /token/revoke-all endpoints
  - ✅ Frontend: authService.js rewritten with automatic refresh
  - ✅ 30-minute access tokens, 7-day refresh tokens
  - ✅ Refresh timer triggers 5 minutes before expiry
  - Status: Implementation complete, awaiting testing

### WebSocket Debugging
- [ ] **Investigate WebSocket 403 Errors** (HIGH PRIORITY)
  - Auth implementation exists and is correct
  - Possible configuration or edge case issue
  - Need to reproduce and debug in production scenario

### Testing Coverage Expansion
- [ ] Write more unit tests (backend: cameras, faces, recordings)
- [ ] Write more component tests (frontend: pages, services)
- [ ] Increase test coverage from 5% to 60%+ (infrastructure already exists)
- [ ] End-to-end testing suite setup (Playwright/Cypress)
- [ ] Security testing and penetration testing
- [ ] Performance benchmarking across hardware tiers

---

## 📋 Backlog

### Backend API Improvements (Phase 2)

#### Response Wrapping (HIGH PRIORITY) ✅ COMPLETED v3.10.1
- [x] Wrap `/api/recordings/` response with metadata (Already implemented with PaginatedResponse)
  ```python
  {"data": [...], "pagination": {"total": N, "page": 1, "page_size": 50, ...}}
  ```
- [x] Wrap `/api/history/detections` response with metadata (Already implemented with PaginatedResponse)
  ```python
  {"data": [...], "pagination": {"total": N, "page": 1, "page_size": 50, ...}}
  ```
- [x] Wrap `/api/faces/people` response with metadata (Already implemented with PaginatedResponse)
  ```python
  {"data": [...], "pagination": {"total": N, "page": 1, "page_size": N, ...}}
  ```
- [x] Wrap `/api/alerts/logs` response with metadata (Already implemented with PaginatedResponse)
  ```python
  {"data": [...], "pagination": {"total": N, "page": 1, "page_size": 20, ...}}
  ```
- [x] Update frontend to handle wrapped responses (Verified: all pages handle wrapped responses with fallback)

#### Endpoint Cleanup (MEDIUM PRIORITY)
- [ ] Remove `/api/users/login` endpoint (duplicate of `/api/token`)
- [ ] Update any frontend code using `/api/users/login`
- [ ] Add deprecation notice before removal
- [ ] Remove `/api/faces/detections` (duplicate of `/api/history/detections`)

#### Field Naming Consistency (MEDIUM PRIORITY) ✅ COMPLETED v3.10.1
- [x] Audit all API responses for field name consistency (Verified: all models use descriptive names)
- [x] Ensure `camera_id` used (not just `id`) (Verified: using `camera_id` throughout)
- [x] Ensure `is_active` used (not just `active`) (Verified: using `is_active` throughout)
- [ ] Document field naming conventions in style guide (Pending)

### Frontend Improvements

#### Field Name Consistency (HIGH PRIORITY) ✅ COMPLETED v3.10.1
- [x] Audit all components for shortened field names (Completed: no issues found)
- [x] Replace `camera.id` with `camera.camera_id` (Verified: already using `camera.camera_id`)
- [x] Replace `camera.active` with `camera.is_active` (Verified: already using `camera.is_active`)
- [x] Use full field names throughout (Verified: consistent usage across all components)

#### WebSocket Integration (HIGH PRIORITY) ✅ COMPLETED v3.10.1
- [x] Fix WebSocket 403 authentication errors (FIXED: scheduleReconnect now fetches fresh token from localStorage)
- [x] Connect LiveDashboard to WebSocket for real-time updates (COMPLETED)
- [x] Add connection status indicator (COMPLETED)
- [x] Implement fallback to polling if WebSocket fails (COMPLETED)
- [x] Auto-reconnect on disconnect (COMPLETED)

#### Phase 2 Sections (LOW PRIORITY)
- [ ] Implement full Events & History section
  - Master-detail timeline view
  - Filter by camera, person, date range
  - Export functionality
- [ ] Implement full Camera Manager section
  - Detection zones configuration
  - Advanced settings UI
  - Bulk operations
- [ ] Implement full AI & Faces section
  - Face gallery view
  - Training workflow improvements
  - Confidence threshold tuning
- [ ] Implement full System & Alerts section
  - iOS-style settings interface
  - Alert rule builder
  - System health monitoring
- [ ] Migrate ThemeSelectorPage to Themes section
  - Embed in new layout
  - Remove standalone page

### Database Optimizations

#### Indexes (LOW PRIORITY)
- [ ] Add composite index on `(camera_id, detected_at)` for FaceDetectionEvent
- [ ] Add composite index on `(camera_id, started_at)` for RecordingEvent
- [ ] Add index on `recording_id` in FaceDetectionEvent (if not auto-created)

#### Cleanup (LOW PRIORITY)
- [ ] Add automatic cleanup of old recordings (configurable retention)
- [ ] Add automatic cleanup of orphaned face detection events
- [ ] Add database vacuum/optimize scheduled task

### Testing & Quality

#### Unit Tests (MEDIUM PRIORITY)
- [ ] Add tests for apiClient interceptors
- [ ] Add tests for authentication flow
- [ ] Add tests for API endpoints
- [ ] Add tests for database models
- [ ] Achieve 80% code coverage

#### Integration Tests (LOW PRIORITY)
- [ ] Test camera creation → recording → face detection flow
- [ ] Test user login → camera access → settings update flow
- [ ] Test alert configuration → trigger → notification flow

#### End-to-End Tests (LOW PRIORITY)
- [ ] Set up Playwright or Cypress
- [ ] Test login flow
- [ ] Test camera management flow
- [ ] Test face enrollment flow
- [ ] Test recording playback flow

### Documentation

#### Developer Docs (HIGH PRIORITY)
- [ ] Create CONTRIBUTING.md
- [ ] Document API client usage patterns
- [ ] Document component creation guidelines
- [ ] Document database migration process

#### User Docs (MEDIUM PRIORITY)
- [ ] Update README with new UI screenshots
- [ ] Create user guide for face enrollment
- [ ] Create troubleshooting guide
- [ ] Create FAQ document

### Performance & Optimization

#### Frontend (LOW PRIORITY)
- [ ] Implement React.memo for expensive components
- [x] Add lazy loading for routes (COMPLETED - v3.6.1)
- [x] Optimize bundle size (code splitting) (COMPLETED - 77% reduction)
- [ ] Add service worker for offline support

#### Backend (LOW PRIORITY)
- [ ] Add Redis caching for frequently accessed data
- [ ] Optimize database queries (N+1 issues)
- [ ] Add request/response compression
- [ ] Implement pagination for all list endpoints

### Security

#### High Priority
- [ ] Implement refresh tokens for JWT (automatic token refresh)
- [ ] Add input sanitization/validation (additional validation middleware)
- [ ] Implement password strength requirements (complexity enforcement)
- [ ] Fix WebSocket 403 authentication errors

#### Medium Priority
- [ ] Add API versioning headers
- [ ] Expand role-based access control (RBAC) - granular permissions per resource
- [ ] Additional security hardening (penetration testing, vulnerability scanning)

### Deployment

#### CI/CD (MEDIUM PRIORITY)
- [ ] Set up GitHub Actions workflow
- [ ] Add automated testing in CI
- [ ] Add automated build and deploy
- [ ] Add Docker image building

#### Monitoring (LOW PRIORITY)
- [ ] Add application metrics (Prometheus)
- [ ] Add error tracking (Sentry)
- [ ] Add log aggregation (ELK stack)
- [ ] Set up uptime monitoring

---

## 🐛 Known Issues

### Critical
- None currently

### High Priority
- **JWT Token Auto-Refresh Missing** (users must re-login when token expires after 30 minutes)
  - Impact: User experience degradation
  - Fix: Implement refresh token mechanism (see implementation plan below)
- **WebSocket 403 Errors (Intermittent)** (may affect real-time updates in some scenarios)
  - Impact: Some users report connection failures
  - Note: Auth implementation EXISTS and is correct (`websockets.py:49-84`)
  - Fix: Debug edge cases, possibly related to token expiration during connection

### Medium Priority
- **Camera discovery can be slow** on large networks (ONVIF timeout issues)
- **No progress indicator** for face model training (appears frozen during training)
- **CSRF protection disabled by default** (needs to be enabled for production)
- **pytest-cov not installed** (causes test coverage collection to fail)
  - Fix: `pip install pytest-cov` or add to requirements-dev.txt

### Low Priority
- **Theme changes require page reload** (CSS variable update timing issue)
- **Some tooltips don't display on mobile** (touch event conflicts)
- **Alert test notifications sometimes timeout** (provider-specific delays)
- **Some vitest tests failing** (authService.test.js needs token mocking fixes)

---

## 💡 Future Features

### v3.8.0 (Q1 2025) - Prioritized Roadmap

#### HIGH PRIORITY
- [x] **JWT Refresh Token System** (COMPLETED 2025-11-09)
  - ✅ Automatic token refresh
  - ✅ Refresh token rotation
  - ✅ Token revocation (single device and all devices)
  - ✅ Device tracking for security audit
  - Status: Implementation complete, awaiting testing

- [x] **Two-Way Audio Production UI** (COMPLETED 2025-11-09)
  - ✅ Backend: `backend/core/two_way_audio_system.py` - Full implementation
  - ✅ Backend: `backend/api/routes/two_way_audio.py` - WebRTC endpoints
  - ✅ Frontend: `TwoWayAudio.jsx` component (330 lines)
  - ✅ Frontend: `TwoWayAudio.css` with theme-aware styling
  - ✅ Integrated into `CameraSettingsModal.jsx` with audio tab
  - ✅ WebRTC peer connection management
  - ✅ Microphone permission handling and error states
  - ✅ Audio controls (speak, listen, mute/unmute)
  - Status: Implementation complete, awaiting testing

#### MEDIUM PRIORITY
- [x] **E2E Testing Suite** (COMPLETED 2025-11-09)
  - ✅ Playwright setup and configuration
  - ✅ Test fixtures for authentication and camera operations
  - ✅ Authentication tests (login, logout, JWT tokens) - 10 tests
  - ✅ Camera management tests (CRUD, start/stop) - 9 tests
  - ✅ Recordings & snapshots tests (browse, filter, playback) - 11 tests
  - ✅ GitHub Actions CI/CD workflow
  - ✅ Test scripts in package.json
  - Total: 30 E2E tests
  - Status: Implementation complete, ready for execution

- [ ] Multi-user support with enhanced RBAC (granular permissions)
- [ ] Smart detection zones (ML-based zone optimization)
- [ ] Audio event detection (glass breaking, smoke alarms, gunshots)
- [ ] Advanced face recognition training (auto-enrollment, fine-tuning)
- [ ] Dark/light mode toggle (themes exist, need UI toggle)

#### LOW PRIORITY
- [ ] Mobile app (React Native or Flutter)

### v4.0.0 (Q2 2025)
- [ ] Cloud backup automation (storage integration exists, need scheduling)
- [ ] Multi-site support (centralized management)
- [ ] Advanced analytics dashboard (beyond current performance dashboard)
- [ ] License plate recognition (ALPR) - OpenCV + Tesseract/EasyOCR
- [ ] Object detection (YOLO integration) - YOLOv8/v9 for people, vehicles, packages
- [ ] Video analytics (people counting, dwell time, loitering detection)
- [ ] Heat map generation (movement tracking visualization)
- [ ] Multi-server support (distributed processing)
- [ ] Kubernetes deployment guide

---

## 📊 Progress Metrics

### Code Quality
- **Lines of Code**: ~35,000+ (backend: ~20,000, frontend: ~15,000)
- **Test Coverage**: ~5% (needs significant improvement)
- **Documentation**: ~85% complete
- **Security Features**: ✅ 2FA, rate limiting, CSRF, audit logging, encryption

### Performance (v3.7.1)
- **API Response Time**: <50ms average (improved)
- **Frontend Load Time**: ~500ms (77% bundle reduction with code splitting)
- **Database Query Time**: <30ms average (with indexes)
- **Video Encoding CPU**: 8-12% per camera (with hardware encoding, down from 40-45%)
- **Frame Drop Rate**: 0% (with async frame buffer)

### Feature Completion
- **Core Surveillance**: ✅ 100% (cameras, recording, detection, streaming)
- **Face Recognition**: ✅ 100% (detection, recognition, clustering)
- **Security**: ✅ 100% (2FA complete, WebSocket auth, JWT refresh tokens, rate limiting, CSRF, audit logging)
- **Smart Home**: ✅ 100% (MQTT, HomeKit, automations, webhooks)
- **Cloud Storage**: ✅ 100% (S3, GCS, Azure, MinIO)
- **Two-Way Audio**: ✅ 100% (backend + frontend complete) - awaiting testing
- **Testing Infrastructure**: ✅ 100% (pytest, vitest configured) - test coverage at 5%
- **UI/UX**: ✅ 95% (themes, help system, wizards, 2FA UI) - dark mode toggle pending
- **Mobile**: ❌ 0% (not started)
- **Advanced AI**: ❌ 0% (ALPR, object detection not started)

### Stability
- **Uptime**: 99.5%+ (in production testing)
- **Known Bugs**: 0 critical, 2 high, 3 medium, 3 low
- **Error Rate**: <0.5%
- **Security Incidents**: 0 (no breaches reported)

---

## 🔧 Development Setup

### Quick Start Checklist
- [ ] Clone repository
- [ ] Install Python 3.11+
- [ ] Install Node.js 18+
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Install frontend deps: `cd frontend && npm install`
- [ ] Copy `.env.example` to `.env`
- [ ] Run migrations: `alembic upgrade head`
- [ ] Build frontend: `npm run build`
- [ ] Start server: `./start-local.sh`
- [ ] Access: http://localhost:8000

---

## 📝 Notes

### Migration Strategy
When database schema changes:
1. Create Alembic migration: `alembic revision -m "description"`
2. Edit migration file in `alembic/versions/`
3. Test migration: `alembic upgrade head`
4. Test rollback: `alembic downgrade -1`
5. Document in CHANGELOG.md

### Deprecation Policy
When deprecating APIs:
1. Add deprecation notice in response headers
2. Update documentation with alternative
3. Give users 2 minor versions notice
4. Remove in next major version

### Release Checklist
Before each release:
- [ ] Update version in `__init__.py`
- [ ] Update CHANGELOG.md
- [ ] Run all tests
- [ ] Build frontend
- [ ] Test in production-like environment
- [ ] Create git tag
- [ ] Push to GitHub
- [ ] Create GitHub release with notes

---

## 📘 Detailed Implementation Plans

### 1. JWT Refresh Token System (v3.8.0 - HIGH PRIORITY)

**Estimated Time**: 12-15 hours
**Complexity**: Medium-High
**Dependencies**: None

#### Objectives
- Eliminate forced re-login after 30 minutes
- Improve user experience with seamless authentication
- Maintain security with rotating refresh tokens

#### Backend Changes (8-10 hours)

##### Database Schema
```python
# New model: RefreshToken
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(512), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)
    device_info = Column(String(255))  # User agent, IP

    user = relationship("User", back_populates="refresh_tokens")
```

**Files to Create/Modify**:
1. `backend/database/models.py` - Add RefreshToken model
2. `alembic/versions/XXXXX_add_refresh_tokens.py` - Migration script
3. `backend/database/crud.py` - CRUD operations for refresh tokens

##### Authentication Service Updates
```python
# backend/core/auth.py

def create_tokens(user: User, device_info: str = None) -> dict:
    """
    Create access token and refresh token pair.

    Returns:
        {
            "access_token": "...",
            "refresh_token": "...",
            "token_type": "bearer",
            "expires_in": 1800  # 30 minutes
        }
    """
    # Access token (short-lived: 30 minutes)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=30)
    )

    # Refresh token (long-lived: 7 days)
    refresh_token = secrets.token_urlsafe(64)
    expires_at = datetime.utcnow() + timedelta(days=7)

    # Store in database
    db_refresh_token = RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=expires_at,
        device_info=device_info
    )
    db.add(db_refresh_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 1800
    }

def refresh_access_token(refresh_token: str, db: Session) -> dict:
    """
    Generate new access token using refresh token.
    Implements refresh token rotation for security.
    """
    # Verify refresh token exists and is valid
    token_record = crud.get_refresh_token(db, refresh_token)

    if not token_record or token_record.revoked:
        raise HTTPException(401, "Invalid refresh token")

    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(401, "Refresh token expired")

    user = crud.get_user(db, token_record.user_id)

    # Rotate refresh token (revoke old, create new)
    token_record.revoked = True
    db.commit()

    return create_tokens(user)
```

**Files to Create/Modify**:
4. `backend/core/auth.py` - Add create_tokens(), refresh_access_token()
5. `backend/api/routes/users.py` - Update login endpoint to return refresh token

##### API Endpoints
```python
# backend/api/routes/users.py

@router.post("/token/refresh")
async def refresh_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.
    Implements token rotation for security.
    """
    try:
        tokens = auth.refresh_access_token(refresh_token, db)
        return tokens
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/token/revoke")
async def revoke_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke a refresh token (logout)."""
    crud.revoke_refresh_token(db, refresh_token)
    return {"message": "Token revoked successfully"}

@router.post("/token/revoke-all")
async def revoke_all_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke all refresh tokens for current user (logout all devices)."""
    crud.revoke_all_user_tokens(db, current_user.id)
    return {"message": "All tokens revoked successfully"}
```

**Files to Create/Modify**:
6. `backend/api/routes/users.py` - Add /token/refresh, /token/revoke endpoints

#### Frontend Changes (4-5 hours)

##### Auth Service Updates
```javascript
// frontend/src/services/authService.js

class AuthService {
  async login(username, password) {
    const response = await axios.post('/api/token', {
      username,
      password
    });

    // Store both tokens
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    localStorage.setItem('token_expires_at', Date.now() + (response.data.expires_in * 1000));

    this.startTokenRefreshTimer();

    return response.data;
  }

  async refreshToken() {
    const refreshToken = localStorage.getItem('refresh_token');

    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await axios.post('/api/token/refresh', {
        refresh_token: refreshToken
      });

      // Update tokens
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('refresh_token', response.data.refresh_token);
      localStorage.setItem('token_expires_at', Date.now() + (response.data.expires_in * 1000));

      this.startTokenRefreshTimer();

      return response.data.access_token;
    } catch (error) {
      // Refresh failed, redirect to login
      this.logout();
      window.location.href = '/login';
      throw error;
    }
  }

  startTokenRefreshTimer() {
    // Clear existing timer
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }

    const expiresAt = parseInt(localStorage.getItem('token_expires_at'));
    const now = Date.now();
    const timeUntilExpiry = expiresAt - now;

    // Refresh 5 minutes before expiry
    const refreshTime = timeUntilExpiry - (5 * 60 * 1000);

    if (refreshTime > 0) {
      this.refreshTimer = setTimeout(() => {
        this.refreshToken();
      }, refreshTime);
    }
  }

  logout() {
    const refreshToken = localStorage.getItem('refresh_token');

    // Revoke refresh token on server
    if (refreshToken) {
      axios.post('/api/token/revoke', { refresh_token: refreshToken })
        .catch(err => console.error('Token revocation failed:', err));
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expires_at');

    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
    }
  }
}
```

**Files to Create/Modify**:
7. `frontend/src/services/authService.js` - Add token refresh logic
8. `frontend/src/api/apiClient.js` - Update interceptor to handle 401 with refresh

##### API Client Interceptor
```javascript
// frontend/src/api/apiClient.js

// Response interceptor for automatic token refresh
apiClient.interceptors.response.use(
  response => response,
  async error => {
    const originalRequest = error.config;

    // If 401 and not already retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Attempt token refresh
        const newToken = await authService.refreshToken();

        // Retry original request with new token
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed, user needs to log in again
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

#### Testing Checklist
- [ ] Create refresh token on login
- [ ] Verify token rotation (old token revoked)
- [ ] Test automatic refresh 5 minutes before expiry
- [ ] Test 401 response triggers refresh
- [ ] Test expired refresh token handling
- [ ] Test revoke token on logout
- [ ] Test revoke all tokens functionality
- [ ] Test concurrent requests during refresh
- [ ] Test WebSocket reconnection with new token

#### Security Considerations
1. **Token Rotation**: Each refresh generates new refresh token and revokes old one
2. **Expiry Limits**: Refresh tokens expire after 7 days (configurable)
3. **Revocation**: Tokens can be revoked individually or all at once
4. **Device Tracking**: Store device info for audit trail
5. **HTTPS Only**: Refresh tokens should only be transmitted over HTTPS

#### Migration Path
1. Create migration script for RefreshToken table
2. Update login endpoint to return both tokens (backward compatible)
3. Deploy backend changes
4. Deploy frontend changes
5. Old clients continue working (no refresh, will re-login)
6. New clients get automatic refresh

---

### 2. End-to-End Testing Suite Setup (v3.8.0 - MEDIUM PRIORITY)

**Estimated Time**: 15-20 hours
**Complexity**: Medium
**Dependencies**: None

#### Objectives
- Automated testing of critical user flows
- Catch integration issues before production
- Confidence in deployments

#### Technology Selection: Playwright (Recommended)

**Why Playwright over Cypress**:
- ✅ Better browser support (Chrome, Firefox, Safari, Edge)
- ✅ Faster execution
- ✅ Better TypeScript support
- ✅ Built-in test retry and video recording
- ✅ API testing capabilities

#### Setup (2-3 hours)

##### Installation
```bash
cd opencv_surveillance/frontend
npm install -D @playwright/test
npx playwright install
```

##### Configuration
```javascript
// playwright.config.js
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
  },
});
```

**Files to Create**:
1. `frontend/playwright.config.js` - Playwright configuration
2. `frontend/e2e/` - Test directory

#### Test Implementation (10-12 hours)

##### Test 1: Authentication Flow
```javascript
// e2e/auth.spec.js
import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test('should login with valid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL('/');
    await expect(page.locator('h1')).toContainText('Live Dashboard');
  });

  test('should show error with invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'wrong');
    await page.click('button[type="submit"]');

    await expect(page.locator('.error')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');

    // Logout
    await page.click('button:has-text("Logout")');

    // Should redirect to login
    await expect(page).toHaveURL('/login');
  });
});
```

##### Test 2: Camera Management
```javascript
// e2e/cameras.spec.js
import { test, expect } from '@playwright/test';

test.describe('Camera Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
  });

  test('should add new camera', async ({ page }) => {
    await page.goto('/cameras');

    await page.click('button:has-text("Add Camera")');
    await page.fill('input[name="camera_id"]', 'test_camera');
    await page.fill('input[name="name"]', 'Test Camera');
    await page.selectOption('select[name="source_type"]', 'mock');
    await page.click('button:has-text("Save")');

    // Verify camera appears in list
    await expect(page.locator('text=Test Camera')).toBeVisible();
  });

  test('should start and stop camera', async ({ page }) => {
    await page.goto('/cameras');

    // Start camera
    await page.click('button[data-camera="test_camera"][data-action="start"]');
    await expect(page.locator('[data-camera="test_camera"] .status')).toHaveText('Active');

    // Stop camera
    await page.click('button[data-camera="test_camera"][data-action="stop"]');
    await expect(page.locator('[data-camera="test_camera"] .status')).toHaveText('Inactive');
  });
});
```

##### Test 3: Face Management
```javascript
// e2e/faces.spec.js
import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Face Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
  });

  test('should upload face image', async ({ page }) => {
    await page.goto('/faces');

    await page.click('button:has-text("Add Person")');
    await page.fill('input[name="person_name"]', 'John Doe');

    // Upload image
    const fileInput = await page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(__dirname, 'fixtures/face.jpg'));

    await page.click('button:has-text("Upload")');

    // Verify success message
    await expect(page.locator('.success')).toContainText('uploaded successfully');
  });

  test('should view detection history', async ({ page }) => {
    await page.goto('/faces');

    await page.click('tab:has-text("Detection History")');

    // Should show table with detections
    await expect(page.locator('table')).toBeVisible();
  });
});
```

##### Test 4: Recording Playback
```javascript
// e2e/recordings.spec.js
import { test, expect } from '@playwright/test';

test.describe('Recordings', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
  });

  test('should display recordings list', async ({ page }) => {
    await page.goto('/events');

    await expect(page.locator('h1')).toContainText('Recordings');
    await expect(page.locator('.recording-card')).toHaveCount(5); // Assuming test data
  });

  test('should play recording', async ({ page }) => {
    await page.goto('/events');

    // Click first recording
    await page.click('.recording-card:first-child');

    // Video player should appear
    await expect(page.locator('video')).toBeVisible();

    // Play button
    await page.click('button[aria-label="Play"]');
    await expect(page.locator('video')).toHaveJSProperty('paused', false);
  });

  test('should download recording', async ({ page }) => {
    await page.goto('/events');

    const downloadPromise = page.waitForEvent('download');
    await page.click('.recording-card:first-child button:has-text("Download")');
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/\.mp4$/);
  });
});
```

##### Test 5: 2FA Setup
```javascript
// e2e/two-factor.spec.js
import { test, expect } from '@playwright/test';

test.describe('Two-Factor Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin');
    await page.click('button[type="submit"]');
  });

  test('should enable 2FA', async ({ page }) => {
    await page.goto('/system/2fa');

    // Click enable button
    await page.click('button:has-text("Enable Two-Factor Authentication")');

    // QR code should appear
    await expect(page.locator('img[alt="2FA QR Code"]')).toBeVisible();

    // Backup codes should be shown
    await expect(page.locator('.backup-code')).toHaveCount(10);
  });
});
```

#### Test Fixtures (2-3 hours)

```javascript
// e2e/fixtures/auth.js
export async function loginAs(page, username, password) {
  await page.goto('/login');
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL('/');
}

// e2e/fixtures/cameras.js
export async function createMockCamera(page, cameraId, name) {
  await page.goto('/cameras');
  await page.click('button:has-text("Add Camera")');
  await page.fill('input[name="camera_id"]', cameraId);
  await page.fill('input[name="name"]', name);
  await page.selectOption('select[name="source_type"]', 'mock');
  await page.click('button:has-text("Save")');
}
```

#### CI/CD Integration (2-3 hours)

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '20'

      - name: Install Python dependencies
        run: |
          cd opencv_surveillance
          python -m pip install -r requirements.txt

      - name: Install frontend dependencies
        run: |
          cd opencv_surveillance/frontend
          npm ci

      - name: Install Playwright
        run: |
          cd opencv_surveillance/frontend
          npx playwright install --with-deps

      - name: Start backend
        run: |
          cd opencv_surveillance
          uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
          sleep 10

      - name: Run E2E tests
        run: |
          cd opencv_surveillance/frontend
          npx playwright test

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: opencv_surveillance/frontend/playwright-report/
```

#### Files Summary

**New Files**:
1. `frontend/playwright.config.js` - Playwright configuration
2. `frontend/e2e/auth.spec.js` - Authentication tests
3. `frontend/e2e/cameras.spec.js` - Camera management tests
4. `frontend/e2e/faces.spec.js` - Face management tests
5. `frontend/e2e/recordings.spec.js` - Recording playback tests
6. `frontend/e2e/two-factor.spec.js` - 2FA tests
7. `frontend/e2e/fixtures/auth.js` - Auth helpers
8. `frontend/e2e/fixtures/cameras.js` - Camera helpers
9. `frontend/e2e/fixtures/faces.js` - Face helpers
10. `.github/workflows/e2e-tests.yml` - CI/CD workflow

**Modified Files**:
11. `frontend/package.json` - Add Playwright scripts

#### Testing Checklist
- [ ] All tests pass locally
- [ ] Tests pass in CI/CD
- [ ] Video recordings on failure
- [ ] Screenshots on failure
- [ ] Cross-browser testing (Chrome, Firefox, Safari)
- [ ] Test data cleanup after each test

---

### 3. Two-Way Audio React UI (v3.8.0 - MEDIUM-HIGH PRIORITY)

**Estimated Time**: 8-10 hours
**Complexity**: Medium
**Dependencies**: Backend already complete ✅

#### Objectives
- Production-ready React component for two-way audio
- Integrate into camera settings
- WebRTC connection management
- Audio controls (speak, listen, mute)

#### Implementation (8-10 hours)

##### Component Structure
```javascript
// frontend/src/components/TwoWayAudio.jsx
import React, { useState, useEffect, useRef } from 'react';

const TwoWayAudio = ({ cameraId }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(true);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const pcRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteAudioRef = useRef(null);

  const connect = async () => {
    try {
      // Get user microphone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      localStreamRef.current = stream;

      // Create WebRTC peer connection
      pcRef.current = new RTCPeerConnection({
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
      });

      // Add local tracks
      stream.getTracks().forEach(track => {
        pcRef.current.addTrack(track, stream);
      });

      // Handle remote tracks
      pcRef.current.ontrack = (event) => {
        if (remoteAudioRef.current) {
          remoteAudioRef.current.srcObject = event.streams[0];
          remoteAudioRef.current.play();
        }
      };

      // Connect WebSocket
      const token = localStorage.getItem('access_token');
      wsRef.current = new WebSocket(
        `ws://localhost:8000/api/audio/ws/${cameraId}?token=${token}`
      );

      wsRef.current.onopen = async () => {
        // Create and send offer
        const offer = await pcRef.current.createOffer();
        await pcRef.current.setLocalDescription(offer);

        wsRef.current.send(JSON.stringify({
          type: 'offer',
          sdp: offer.sdp
        }));

        setIsConnected(true);
      };

      wsRef.current.onmessage = async (event) => {
        const message = JSON.parse(event.data);

        if (message.type === 'answer') {
          await pcRef.current.setRemoteDescription({
            type: 'answer',
            sdp: message.sdp
          });
        }
      };

      wsRef.current.onerror = (err) => {
        setError('WebSocket connection failed');
        console.error('WebSocket error:', err);
      };

    } catch (err) {
      setError('Failed to access microphone');
      console.error('Connection error:', err);
    }
  };

  const disconnect = () => {
    // Stop local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
    }

    // Close WebRTC connection
    if (pcRef.current) {
      pcRef.current.close();
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
    }

    setIsConnected(false);
    setIsSpeaking(false);
  };

  const toggleMicrophone = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      audioTrack.enabled = !audioTrack.enabled;
      setIsSpeaking(audioTrack.enabled);
    }
  };

  const toggleSpeaker = () => {
    if (remoteAudioRef.current) {
      remoteAudioRef.current.muted = !remoteAudioRef.current.muted;
      setIsListening(!remoteAudioRef.current.muted);
    }
  };

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  return (
    <div style={styles.container}>
      <h3>Two-Way Audio</h3>

      {error && (
        <div style={styles.error}>{error}</div>
      )}

      {!isConnected ? (
        <button onClick={connect} style={styles.primaryButton}>
          Connect Audio
        </button>
      ) : (
        <div style={styles.controls}>
          <div style={styles.status}>
            <span style={styles.indicator}>🔴</span> Live
          </div>

          <div style={styles.buttonGroup}>
            <button
              onClick={toggleMicrophone}
              style={{
                ...styles.controlButton,
                backgroundColor: isSpeaking ? '#28a745' : '#6c757d'
              }}
            >
              {isSpeaking ? '🎤 Speaking' : '🔇 Muted'}
            </button>

            <button
              onClick={toggleSpeaker}
              style={{
                ...styles.controlButton,
                backgroundColor: isListening ? '#28a745' : '#6c757d'
              }}
            >
              {isListening ? '🔊 Listening' : '🔇 Muted'}
            </button>
          </div>

          <button onClick={disconnect} style={styles.dangerButton}>
            Disconnect
          </button>
        </div>
      )}

      {/* Hidden audio element for remote stream */}
      <audio ref={remoteAudioRef} style={{ display: 'none' }} />
    </div>
  );
};

const styles = {
  container: {
    padding: 'var(--spacing-lg, 24px)',
    backgroundColor: 'var(--bg-panel)',
    borderRadius: 'var(--radius-md, 12px)',
    border: '1px solid var(--border-panel)',
  },
  error: {
    padding: 'var(--spacing-md, 16px)',
    backgroundColor: 'rgba(220, 53, 69, 0.15)',
    borderRadius: 'var(--radius-sm, 8px)',
    color: 'var(--color-error)',
    marginBottom: 'var(--spacing-md, 16px)',
  },
  controls: {
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--spacing-md, 16px)',
  },
  status: {
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--spacing-sm, 8px)',
    fontSize: '14px',
  },
  indicator: {
    animation: 'pulse 2s infinite',
  },
  buttonGroup: {
    display: 'flex',
    gap: 'var(--spacing-md, 16px)',
  },
  primaryButton: {
    backgroundColor: 'var(--theme-primary)',
    color: '#fff',
    padding: 'var(--spacing-md, 16px)',
    border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    cursor: 'pointer',
    fontWeight: '600',
    minHeight: '44px',
  },
  controlButton: {
    flex: 1,
    padding: 'var(--spacing-md, 16px)',
    border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    cursor: 'pointer',
    fontWeight: '600',
    color: '#fff',
    minHeight: '44px',
  },
  dangerButton: {
    backgroundColor: 'var(--color-error, #dc3545)',
    color: '#fff',
    padding: 'var(--spacing-md, 16px)',
    border: 'none',
    borderRadius: 'var(--radius-md, 12px)',
    cursor: 'pointer',
    fontWeight: '600',
    minHeight: '44px',
  },
};

export default TwoWayAudio;
```

##### Integration into Camera Settings
```javascript
// frontend/src/components/CameraSettingsModal.jsx

import TwoWayAudio from './TwoWayAudio';

// Add tab for two-way audio
<Tabs>
  <Tab label="General">...</Tab>
  <Tab label="Recording">...</Tab>
  <Tab label="Audio">
    {camera.capabilities?.audio && (
      <TwoWayAudio cameraId={camera.camera_id} />
    )}
  </Tab>
</Tabs>
```

#### Files to Create/Modify
1. `frontend/src/components/TwoWayAudio.jsx` - Main component (200-250 lines)
2. `frontend/src/components/TwoWayAudio.css` - Styles with animations
3. `frontend/src/components/CameraSettingsModal.jsx` - Add audio tab
4. `backend/database/models.py` - Add `audio_enabled` field to Camera model (if not exists)

#### Testing Checklist
- [ ] Microphone permission request works
- [ ] WebRTC connection establishes
- [ ] Audio transmits both ways
- [ ] Mute/unmute controls work
- [ ] Disconnect cleans up resources
- [ ] Error handling for permission denied
- [ ] Error handling for WebSocket failure
- [ ] Mobile browser compatibility

---

**Last Review**: 2025-11-09
**Next Review**: 2025-11-16
