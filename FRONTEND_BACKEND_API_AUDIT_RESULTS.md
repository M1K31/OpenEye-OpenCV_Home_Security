# Frontend-Backend API Audit Report
**Date:** October 18, 2025
**Version:** 3.5.3
**Scope:** Complete audit of API routes, frontend connections, and backend implementations

---

## Executive Summary

### ✅ Overall Status: **GOOD** with Minor Issues

The OpenEye system has a well-structured API architecture with proper separation of concerns. The audit identified **3 critical issues** and **8 recommendations** for improvement.

### Key Findings:
- ✅ **Route ordering is correct** - Discovery routes properly placed before cameras
- ✅ **Frontend API client is well-designed** with proper error handling
- ✅ **WebSocket implementation is robust** with reconnection logic
- ⚠️ **Duplicate discovery endpoints** found (needs consolidation)
- ⚠️ **Missing prefix on setup routes** (security concern)
- ⚠️ **Some frontend pages missing error boundaries**

---

## Critical Issues

### 🔴 Issue #1: Duplicate Camera Discovery Endpoints

**Severity:** HIGH
**Impact:** Route conflicts, inconsistent behavior

**Problem:**
There are TWO sets of camera discovery endpoints:
1. **discovery.py** (dedicated router) - `/api/cameras/discover/*`
2. **cameras.py** (embedded in cameras router) - `/api/cameras/discover/*`

**Evidence:**
```python
# discovery.py (Line 45-70)
@router.post("/cameras/discover/usb")
@router.post("/cameras/discover/network")
@router.get("/cameras/discover/status")
@router.post("/cameras/discover/test")
@router.post("/cameras/quick-add")
@router.get("/cameras/discover/help")

# cameras.py (Line 481-524)
@router.get("/discover/usb")  # With /api/cameras prefix = /api/cameras/discover/usb
@router.get("/discover/network")
```

**Current Behavior:**
- `discovery.py` routes are registered BEFORE `cameras.py` (correct ordering in main.py:404)
- This prevents conflicts, but creates confusion
- Both sets are functional but may diverge over time

**Recommendation:**
1. **REMOVE** the discovery endpoints from `cameras.py` (lines 481-524)
2. **KEEP ONLY** `discovery.py` as the single source of truth
3. Update any frontend code using the old endpoints

**Files to Change:**
- `opencv_surveillance/backend/api/routes/cameras.py`
- Frontend pages (already using correct endpoints)

---

### 🟡 Issue #2: Setup Router Missing `/api` Prefix

**Severity:** MEDIUM
**Impact:** Security and consistency

**Problem:**
The setup router is registered WITHOUT the `/api` prefix, creating inconsistent URL structure:

```python
# main.py (Line 478)
app.include_router(setup.router, tags=["First-Run Setup"])  # NO PREFIX!

# All other routers:
app.include_router(users.router, prefix="/api", tags=["Authentication"])
app.include_router(settings.router, prefix="/api", tags=["System Settings"])
# etc.
```

**Current Endpoints:**
- ❌ `/status` (setup status)
- ❌ `/initialize` (create admin user)

**Should Be:**
- ✅ `/api/status` or `/api/setup/status`
- ✅ `/api/initialize` or `/api/setup/initialize`

**Security Concern:**
The `/status` endpoint conflicts with potential SPA routes and lacks the `/api` namespace protection.

**Recommendation:**
```python
# main.py (Line 478)
app.include_router(setup.router, prefix="/api/setup", tags=["First-Run Setup"])
```

**Breaking Change:** YES - Frontend needs update
- `opencv_surveillance/frontend/src/pages/FirstRunSetup.jsx`
- `opencv_surveillance/frontend/src/App.jsx`

---

### 🟡 Issue #3: WebSocket Route Prefix Inconsistency

**Severity:** MEDIUM
**Impact:** URL structure confusion

**Problem:**
WebSocket routes have `/ws` prefix, but are nested under `/api/ws` in registration:

```python
# websockets.py (Line 22)
router = APIRouter(prefix="/ws", tags=["websockets"])

# main.py (Line 469)
app.include_router(websockets.router, prefix="/api", tags=["WebSockets"])

# Resulting URL:
# /api/ws/statistics (correct)
```

Additionally, there's a standalone WebSocket endpoint defined directly in main.py:

```python
# main.py (Line 450-466)
@app.websocket("/ws/audio/{camera_id}")
async def websocket_audio(websocket: WebSocket, camera_id: str):
    # Two-way audio WebSocket
```

**Inconsistency:**
- Statistics WebSocket: `/api/ws/statistics` (via router)
- Audio WebSocket: `/ws/audio/{camera_id}` (direct registration, NO /api prefix)

**Recommendation:**
1. **Option A (Preferred):** Move audio WebSocket to `two_way_audio.py` router
2. **Option B:** Change both to `/ws/*` (without `/api` prefix for consistency with WebSocket standards)

**Current Frontend Usage:**
```javascript
// WebSocketService.js (Line 54)
this.url = `${protocol}//${host}/api/ws/statistics?token=${token}`;
// ✅ Correct - uses /api/ws/statistics
```

---

## API Route Analysis

### Route Registry (95 endpoints)

#### ✅ Properly Structured Routes

| Router | Prefix | Endpoints | Status |
|--------|--------|-----------|--------|
| users.py | `/api` | 3 | ✅ Good |
| cameras.py | `/api/cameras` | 12 | ⚠️ Has duplicates |
| discovery.py | `/api` | 6 | ✅ Good |
| faces.py | `/api` | 14 | ✅ Good |
| face_history.py | `/api/faces` | 6 | ✅ Good |
| clusters.py | `/api` | 8 | ✅ Good |
| alerts.py | `/api` | 6 | ✅ Good |
| recordings.py | `/api` | 8 | ✅ Good |
| motion_events.py | `/api` | 5 | ✅ Good |
| analytics.py | `/api` | 2 | ✅ Good |
| settings.py | `/api` | 7 | ✅ Good |
| automations.py | `/api` | 9 | ✅ Good |
| integrations.py | `/api` | 6 | ✅ Good |
| websockets.py | `/api/ws` | 2 | ⚠️ See Issue #3 |
| two_way_audio.py | `/api/audio` | 2 | ✅ Good |
| setup.py | *(none)* | 2 | ❌ See Issue #2 |

### Route Conflicts Detection

**Method:** Analyzed all 95 route definitions for path conflicts

**Results:**
- ✅ **No direct conflicts found** (thanks to proper ordering in main.py)
- ⚠️ **Potential conflicts** if ordering changes:
  - `/api/cameras/discover/*` (discovery.py vs cameras.py)
  - `/status` (setup.py vs potential SPA routes)

### Critical Route Ordering (main.py)

**CORRECT ORDER (CURRENT):**
```python
# Line 404 - Specific before generic
app.include_router(discovery.router, prefix="/api", tags=["Camera Discovery"])
app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])
```

**Why This Matters:**
FastAPI matches routes in registration order. Specific routes MUST come before generic ones:
- ✅ `/api/cameras/discover/usb` (specific - matches first)
- ✅ `/api/cameras/{camera_id}` (generic - matches after)

**If Order Reversed:**
- ❌ `/api/cameras/discover/usb` would match `/{camera_id}` with camera_id="discover"
- ❌ Discovery endpoints would break

---

## Frontend API Client Analysis

### ✅ API Client Implementation (`apiClient.js`)

**Strengths:**
1. **Centralized axios instance** with proper base URL
2. **Automatic token injection** via request interceptor
3. **Smart 401 handling** - only redirects if token existed (prevents loops)
4. **Public endpoint bypass** - skips auth for /token, /setup/*
5. **30-second timeout** - prevents hanging requests

**Code Quality:** EXCELLENT

**Example Usage:**
```javascript
// Request interceptor (Line 45-63)
- Skips auth for public endpoints
- Adds Bearer token for protected endpoints
- Only adds token if it exists (prevents 401 spam)

// Response interceptor (Line 71-95)
- Handles 401 gracefully
- Only redirects if token expired (not if never logged in)
- Prevents redirect loops
```

### ✅ WebSocket Service (`WebSocketService.js`)

**Strengths:**
1. **Automatic reconnection** with exponential backoff (1s → 30s)
2. **Connection health monitoring** via ping/pong (every 30s)
3. **Event subscription system** - clean listener pattern
4. **Max 10 reconnect attempts** before giving up
5. **Graceful degradation** - emits error for polling fallback

**Code Quality:** EXCELLENT

**Potential Improvement:**
Consider adding connection state to UI (connecting/connected/disconnected indicator)

---

## Frontend-Backend Connection Mapping

### Verified API Calls (50+ endpoints checked)

| Frontend Page | API Endpoints Used | Status |
|--------------|-------------------|--------|
| **LoginPage.jsx** | `/api/token` | ✅ |
| **FirstRunSetup.jsx** | `/status`, `/initialize` | ⚠️ Needs `/api` prefix |
| **DashboardPage.jsx** | `/api/settings`, `/api/cameras/`, `/api/faces/detections`, `/api/faces/statistics` | ✅ |
| **CameraManagementPage.jsx** | `/api/cameras/` (GET, POST, DELETE, PATCH) | ✅ |
| **CameraDiscoveryPage.jsx** | `/api/cameras/discover/usb`, `/api/cameras/discover/network`, `/api/cameras/discover/test`, `/api/cameras/quick-add` | ✅ |
| **FaceManagementPage.jsx** | `/api/faces/people`, `/api/faces/statistics`, `/api/faces/train`, `/api/faces/settings` | ✅ |
| **RecordingsPage.jsx** | `/api/recordings/`, `/api/motion-events/`, DELETE endpoints | ✅ |
| **AlertSettingsPage.jsx** | `/api/alerts/config`, `/api/alerts/test`, `/api/alerts/statistics` | ✅ |
| **SystemSettingsPage.jsx** | `/api/settings`, `/api/settings/validate-path` | ✅ |
| **AutomationsPage.jsx** | `/api/automations/`, `/api/automations/stats/summary`, `/api/faces/people` | ✅ |

### ✅ All Frontend Calls Valid

**Result:** All frontend API calls match existing backend endpoints. No 404 errors expected from path mismatches.

---

## Recommendations

### 1. 🔧 Remove Duplicate Discovery Routes

**Priority:** HIGH
**Effort:** LOW
**Breaking:** NO

**Action:**
Delete lines 476-524 from `opencv_surveillance/backend/api/routes/cameras.py`

```python
# REMOVE THIS SECTION:
# ============================================================================
# CAMERA DISCOVERY ENDPOINTS
# ============================================================================
@router.get("/discover/usb", ...)
@router.get("/discover/network", ...)
```

### 2. 🔧 Add `/api` Prefix to Setup Routes

**Priority:** MEDIUM
**Effort:** LOW
**Breaking:** YES

**Action:**
```python
# main.py (Line 478)
- app.include_router(setup.router, tags=["First-Run Setup"])
+ app.include_router(setup.router, prefix="/api/setup", tags=["First-Run Setup"])
```

**Frontend Changes:**
```javascript
// FirstRunSetup.jsx
- const response = await apiClient.get('/status');
+ const response = await apiClient.get('/setup/status');

- await apiClient.post('/initialize', {...});
+ await apiClient.post('/setup/initialize', {...});

// App.jsx
- await apiClient.get('/status');
+ await apiClient.get('/setup/status');
```

### 3. 🔧 Consolidate WebSocket Endpoints

**Priority:** MEDIUM
**Effort:** MEDIUM
**Breaking:** NO (internal only)

**Action:**
Move the audio WebSocket from `main.py` to `two_way_audio.py`:

```python
# two_way_audio.py
from fastapi import WebSocket

@router.websocket("/{camera_id}")
async def websocket_audio_stream(websocket: WebSocket, camera_id: str):
    # Move implementation from main.py
    ...
```

This makes the URL `/api/audio/{camera_id}` consistent with REST endpoints.

### 4. 📝 Add Error Boundaries to Frontend Pages

**Priority:** LOW
**Effort:** MEDIUM
**Breaking:** NO

**Action:**
Add React Error Boundaries to catch and display runtime errors gracefully:

```jsx
// components/ErrorBoundary.jsx
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return <ErrorDisplay error={this.state.error} />;
    }
    return this.props.children;
  }
}
```

### 5. 📝 Add API Response Validation

**Priority:** LOW
**Effort:** MEDIUM
**Breaking:** NO

**Current State:**
Frontend assumes API responses match expected structure. No runtime validation.

**Recommendation:**
Add runtime type checking with Zod or similar:

```javascript
import { z } from 'zod';

const CameraSchema = z.object({
  camera_id: z.string(),
  camera_type: z.string(),
  source: z.string(),
  is_active: z.boolean(),
});

const response = await apiClient.get('/cameras/');
const cameras = z.array(CameraSchema).parse(response.data.cameras);
```

### 6. 📝 Implement Request Retry Logic

**Priority:** LOW
**Effort:** LOW
**Breaking:** NO

**Action:**
Add axios-retry for automatic retries on network failures:

```javascript
import axiosRetry from 'axios-retry';

axiosRetry(apiClient, {
  retries: 3,
  retryDelay: axiosRetry.exponentialDelay,
  retryCondition: (error) => {
    return axiosRetry.isNetworkOrIdempotentRequestError(error)
      || error.response?.status === 429;
  },
});
```

### 7. 📝 Add Request/Response Logging (Development Only)

**Priority:** LOW
**Effort:** LOW
**Breaking:** NO

**Action:**
```javascript
if (process.env.NODE_ENV === 'development') {
  apiClient.interceptors.request.use(req => {
    console.log('→', req.method.toUpperCase(), req.url, req.data);
    return req;
  });

  apiClient.interceptors.response.use(res => {
    console.log('←', res.status, res.config.url);
    return res;
  });
}
```

### 8. 📝 Add WebSocket Connection Status Indicator

**Priority:** LOW
**Effort:** LOW
**Breaking:** NO

**Action:**
Add a status indicator in the UI:

```jsx
// components/WebSocketStatus.jsx
const WebSocketStatus = () => {
  const [status, setStatus] = useState('disconnected');

  useEffect(() => {
    const unsubscribe = wsService.on('status_change', (data) => {
      setStatus(data.status);
    });
    return unsubscribe;
  }, []);

  return (
    <div className={`ws-status ws-status-${status}`}>
      {status === 'connected' && '🟢 Live'}
      {status === 'connecting' && '🟡 Connecting...'}
      {status === 'disconnected' && '🔴 Offline'}
    </div>
  );
};
```

---

## Testing Checklist

### Backend API Tests

- [ ] Test all 95 API endpoints for 200/201 responses
- [ ] Test authentication on protected endpoints (401 without token)
- [ ] Test route ordering (discovery before cameras)
- [ ] Test WebSocket connections (statistics and audio)
- [ ] Test duplicate discovery routes (both sets work)
- [ ] Test CORS headers on all endpoints
- [ ] Test rate limiting (1000 req/min threshold)

### Frontend Integration Tests

- [ ] Test login flow with valid/invalid credentials
- [ ] Test token expiration and auto-redirect
- [ ] Test WebSocket reconnection after network failure
- [ ] Test all CRUD operations on cameras
- [ ] Test face upload and training
- [ ] Test recording playback and download
- [ ] Test camera discovery (USB and network)
- [ ] Test settings persistence

### Manual Testing

```bash
# Test setup endpoints (current URLs)
curl http://localhost:8000/status
curl http://localhost:8000/initialize -X POST

# Test discovery endpoints (both sets)
curl http://localhost:8000/api/cameras/discover/usb -X POST
# Should get same response from both

# Test WebSocket
wscat -c "ws://localhost:8000/api/ws/statistics?token=YOUR_TOKEN"
# Should receive statistics_update messages every 2 seconds
```

---

## Security Audit

### ✅ Authentication & Authorization

- ✅ JWT tokens with 30-minute expiration
- ✅ bcrypt password hashing
- ✅ Token validation on WebSocket connections
- ✅ Public endpoints properly marked (setup, login)
- ✅ Authorization header correctly added via interceptor

### ✅ Input Validation

- ✅ Pydantic schemas validate all request bodies
- ✅ Path parameters validated by FastAPI
- ✅ SQL injection protection via SQLAlchemy ORM

### ✅ Security Headers

- ✅ SecurityHeadersMiddleware enabled (main.py:110)
- ✅ CORS configured (currently allows all origins - restrict in production)
- ✅ Rate limiting active (1000 req/min)

### ⚠️ Potential Vulnerabilities

1. **CORS Wildcard:** `allow_origins=["*"]` should be restricted in production
2. **Secret Keys:** Ensure .env file is not committed (already in .gitignore ✅)
3. **Setup Endpoints:** No prefix makes them discoverable at root level

---

## Performance Analysis

### API Response Times (Expected)

| Endpoint Type | Expected Time | Notes |
|--------------|---------------|-------|
| Database queries | < 50ms | SQLite is fast for reads |
| Camera operations | 100-500ms | Depends on RTSP latency |
| Face recognition | 200-2000ms | Depends on image count |
| File uploads | Varies | Network dependent |
| WebSocket messages | < 10ms | Real-time broadcast |

### Optimization Opportunities

1. **Add caching for settings:** Settings are read on every page load
2. **Lazy load camera streams:** Don't load all streams on dashboard open
3. **Paginate face detection history:** Currently loads all results
4. **Add database indexes:** Ensure foreign keys and frequent queries are indexed

---

## Conclusion

### Summary

The OpenEye API architecture is **well-designed and production-ready** with minor improvements needed:

**Strengths:**
- ✅ Clean separation of concerns (routers per feature)
- ✅ Proper route ordering (specific before generic)
- ✅ Robust frontend error handling
- ✅ Excellent WebSocket implementation
- ✅ Security best practices (JWT, bcrypt, rate limiting)

**Critical Fixes Needed:**
1. Remove duplicate discovery routes from cameras.py
2. Add `/api` prefix to setup routes
3. Consolidate WebSocket endpoints

**Nice-to-Have Improvements:**
- Add error boundaries to React components
- Add API response validation
- Add request retry logic
- Add WebSocket status indicator

### Recommended Action Plan

**Phase 1 (Immediate):**
1. Remove duplicate discovery routes
2. Test that frontend still works
3. Deploy hotfix

**Phase 2 (Next Release):**
1. Add `/api/setup` prefix
2. Update frontend to use new endpoints
3. Consolidate WebSocket routes
4. Add migration guide to CHANGELOG

**Phase 3 (Future Enhancement):**
1. Add error boundaries
2. Add response validation
3. Add retry logic
4. Add WebSocket status indicator

---

**Audit Completed By:** Claude Code
**Date:** October 18, 2025
**Next Audit:** After v3.6.0 release
