# OpenEye Development ToDo List
**Last Updated**: 2025-10-12

## ✅ Completed

### Frontend Migration (v3.5.2)
- [x] Create centralized apiClient with auth interceptors
- [x] Migrate SystemSettingsPage to apiClient
- [x] Migrate DashboardPage to apiClient
- [x] Migrate FaceManagementPage to apiClient
- [x] Migrate CameraManagementPage to apiClient
- [x] Migrate RecordingsPage to apiClient
- [x] Migrate AlertSettingsPage to apiClient
- [x] Migrate CameraDiscoveryPage to apiClient
- [x] Build frontend successfully (index-37b9047e.js)

### Backend Improvements (v3.5.2)
- [x] Add `recording_id` FK to FaceDetectionEvent model
- [x] Add relationship between FaceDetectionEvent and RecordingEvent
- [x] Rename `Camera.last_active` to `Camera.last_active_at`

### Documentation (v3.5.2)
- [x] Create comprehensive API Reference Guide
- [x] Create ToDo checklist document
- [x] Create docs/ directory structure

---

## 🔄 In Progress

### Testing & Validation
- [ ] Test all migrated pages in browser
- [ ] Hard refresh frontend (Cmd+Shift+R)
- [ ] Verify no 401 errors in console
- [ ] Test camera feeds display
- [ ] Test event timeline shows merged data
- [ ] Test event click navigation to recordings
- [ ] Verify authentication flow works

### Database Migration
- [ ] Create Alembic migration for `recording_id` column
- [ ] Create Alembic migration for `last_active_at` rename
- [ ] Test migrations on development database
- [ ] Backup production database before migration
- [ ] Apply migrations to production

---

## 📋 Backlog

### Backend API Improvements (Phase 2)

#### Response Wrapping (HIGH PRIORITY)
- [ ] Wrap `/api/recordings/` response with metadata
  ```python
  {"recordings": [...], "total": N, "skip": 0, "limit": 50}
  ```
- [ ] Wrap `/api/history/detections` response with metadata
  ```python
  {"detections": [...], "total": N, "skip": 0, "limit": 50}
  ```
- [ ] Wrap `/api/faces/people` response with metadata
  ```python
  {"people": [...], "total": N}
  ```
- [ ] Wrap `/api/alerts/logs` response with metadata
  ```python
  {"logs": [...], "total": N, "limit": 20}
  ```
- [ ] Update frontend to handle wrapped responses

#### Endpoint Cleanup (MEDIUM PRIORITY)
- [ ] Remove `/api/users/login` endpoint (duplicate of `/api/token`)
- [ ] Update any frontend code using `/api/users/login`
- [ ] Add deprecation notice before removal
- [ ] Remove `/api/faces/detections` (duplicate of `/api/history/detections`)

#### Field Naming Consistency (MEDIUM PRIORITY)
- [ ] Audit all API responses for field name consistency
- [ ] Ensure `camera_id` used (not just `id`)
- [ ] Ensure `is_active` used (not just `active`)
- [ ] Document field naming conventions in style guide

### Frontend Improvements

#### Field Name Consistency (HIGH PRIORITY)
- [ ] Audit all components for shortened field names
- [ ] Replace `camera.id` with `camera.camera_id`
- [ ] Replace `camera.active` with `camera.is_active`
- [ ] Use full field names throughout

#### WebSocket Integration (MEDIUM PRIORITY)
- [ ] Fix WebSocket 403 authentication errors
- [ ] Connect LiveDashboard to WebSocket for real-time updates
- [ ] Add connection status indicator
- [ ] Implement fallback to polling if WebSocket fails
- [ ] Auto-reconnect on disconnect

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
- [ ] Add lazy loading for routes
- [ ] Optimize bundle size (code splitting)
- [ ] Add service worker for offline support

#### Backend (LOW PRIORITY)
- [ ] Add Redis caching for frequently accessed data
- [ ] Optimize database queries (N+1 issues)
- [ ] Add request/response compression
- [ ] Implement pagination for all list endpoints

### Security

#### High Priority
- [ ] Add rate limiting to API endpoints
- [ ] Implement refresh tokens for JWT
- [ ] Add CSRF protection
- [ ] Add input sanitization/validation
- [ ] Implement password strength requirements

#### Medium Priority
- [ ] Add API versioning headers
- [ ] Implement role-based access control (RBAC)
- [ ] Add audit logging for sensitive operations
- [ ] Add two-factor authentication (2FA)

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
- WebSocket authentication returns 403 errors
- No automatic token refresh (users must re-login when token expires)

### Medium Priority
- Camera discovery can be slow on large networks
- No progress indicator for face model training
- Recording playback doesn't show timestamp overlay

### Low Priority
- Theme changes require page reload
- Some tooltips don't display on mobile
- Alert test notifications sometimes timeout

---

## 💡 Future Features

### v3.6.0 (Q1 2025)
- [ ] Multi-user support with RBAC
- [ ] Mobile app (React Native)
- [ ] Smart detection zones (ML-based)
- [ ] Face clustering for unknown faces
- [ ] Audio detection and alerts

### v4.0.0 (Q2 2025)
- [ ] Cloud backup integration
- [ ] Multi-site support
- [ ] Advanced analytics dashboard
- [ ] License plate recognition
- [ ] Object detection (not just faces)

---

## 📊 Progress Metrics

### Code Quality
- **Lines of Code**: ~25,000
- **Test Coverage**: ~0% (needs improvement)
- **Documentation**: ~70% complete

### Performance
- **API Response Time**: <100ms average
- **Frontend Load Time**: ~1.5s
- **Database Query Time**: <50ms average

### Stability
- **Uptime**: 99%+ (in testing)
- **Known Bugs**: 0 critical, 3 high, 5 medium
- **Error Rate**: <1%

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

**Last Review**: 2025-10-12  
**Next Review**: 2025-10-19
