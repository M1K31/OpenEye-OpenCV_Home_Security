# WebSocket Authentication Fix - v3.5.4

**Date:** October 18, 2025
**Status:** ✅ Fixed
**Priority:** HIGH - Critical functionality restored

---

## 🐛 Problem Description

### User Report
WebSocket connections to `/api/ws/statistics` were failing with 403 Forbidden errors, preventing real-time dashboard updates.

### Symptoms
```javascript
WebSocket connection to 'ws://localhost:8000/api/ws/statistics?token=...' failed
Error: HTTP 403 Forbidden
```

**Impact:**
- Real-time statistics not updating in dashboard
- Live camera feeds not refreshing automatically
- Users forced to rely on polling fallback (5-second intervals)
- Poor user experience with delayed updates

---

## 🔍 Root Cause Analysis

### The Problem: FastAPI Dependency Injection with WebSockets

The issue was in `backend/api/routes/websockets.py`:

```python
# ❌ BROKEN CODE
async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),  # ← This doesn't work with WebSockets!
) -> Optional[User]:
    ...
```

**Why This Failed:**

1. **WebSockets are Long-Lived Connections**
   - HTTP requests: Short-lived, request → response → done
   - WebSocket connections: Long-lived, stay open for minutes/hours

2. **Database Session Generator Issue**
   ```python
   def get_db():
       db = SessionLocal()
       try:
           yield db  # ← Yields to caller
       finally:
           db.close()  # ← Closes after use
   ```

3. **FastAPI Dependency Injection Mismatch**
   - For HTTP endpoints: FastAPI calls `get_db()`, gets session, calls endpoint, closes session
   - For WebSocket endpoints: FastAPI tries to inject dependency **but the WebSocket hasn't been accepted yet**
   - Result: Dependency injection fails → 403 Forbidden before authentication can even run

### Technical Details

The WebSocket lifecycle in FastAPI:

```
1. Client initiates WebSocket connection
2. FastAPI tries to resolve dependencies (including Depends(get_db))
3. ❌ FAIL: Dependencies can't be resolved before accepting connection
4. Connection rejected with 403
5. Authentication function never runs
```

The correct flow should be:

```
1. Client initiates WebSocket connection
2. FastAPI resolves simple dependencies (Query params)
3. Authentication function runs
4. ✓ If auth succeeds: Accept connection
5. ✗ If auth fails: Reject with proper error code
6. Handle messages in connection loop
```

---

## ✅ Solution Implemented

### Code Changes

**File:** `backend/api/routes/websockets.py`

#### Change 1: Remove Database Dependency from Authentication Function

```python
# BEFORE (Broken)
async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),  # ❌ Remove this
) -> Optional[User]:
    ...
```

```python
# AFTER (Fixed)
async def authenticate_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # ✓ Only simple dependencies
) -> Optional[User]:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        websocket: FastAPI WebSocket instance
        token: JWT token from query parameter

    Returns:
        User object if authenticated, None otherwise
    """
    if not token:
        logger.warning("WebSocket connection attempted without token")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )
        return None

    try:
        # Create database session manually for WebSocket
        db = SessionLocal()  # ← Create session directly
        try:
            # Verify token and get user
            user = verify_token(token, db)
            if not user:
                raise Exception("Invalid token")
            return user
        finally:
            db.close()  # ← Ensure cleanup
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token"
        )
        return None
```

#### Change 2: Add SessionLocal Import

```python
# BEFORE
from backend.database.session import get_db
```

```python
# AFTER
from backend.database.session import get_db, SessionLocal  # ← Added SessionLocal
```

#### Change 3: Update WebSocket Endpoint Signature

```python
# BEFORE (Broken)
@router.websocket("/statistics")
async def websocket_statistics_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),  # ❌ Remove this
):
```

```python
# AFTER (Fixed)
@router.websocket("/statistics")
async def websocket_statistics_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),  # ✓ Only query param
):
```

#### Change 4: Update Authentication Call

```python
# BEFORE
user = await authenticate_websocket(websocket, token, db)
```

```python
# AFTER
user = await authenticate_websocket(websocket, token)
```

---

## 🔑 Key Insights

### Why Manual Session Management?

For WebSocket endpoints, we **must** manually manage database sessions because:

1. **Dependency Injection Timing**
   - FastAPI resolves dependencies **before** accepting the WebSocket
   - But we need to accept the connection **first**, then authenticate

2. **Session Lifecycle Control**
   - We only need the DB session for authentication (brief)
   - Not for the entire WebSocket connection duration (long)
   - Manual creation allows precise control

3. **Resource Efficiency**
   ```python
   # ❌ BAD: Session held for entire connection (minutes/hours)
   db = Depends(get_db)  # Held open whole time

   # ✓ GOOD: Session created and closed quickly
   db = SessionLocal()
   try:
       user = verify_token(token, db)
   finally:
       db.close()  # Released immediately after auth
   ```

### Best Practices for WebSocket Endpoints

1. **Use `Query()` for simple parameters** (token, connection_id, etc.)
2. **Manually create database sessions** when needed
3. **Always use try/finally** to ensure cleanup
4. **Accept WebSocket early**, reject with proper error codes
5. **Keep authentication fast** (don't hold resources)

---

## 🧪 Testing

### Manual Testing with Test Script

Created `opencv_surveillance/test_websocket_connection.py`:

```bash
# Install websockets library
pip install websockets

# Run test (replace with your credentials)
cd opencv_surveillance
python test_websocket_connection.py admin your_password
```

**Expected Output:**
```
============================================================
WebSocket Connection Test
============================================================
Authenticating as admin...
✓ Successfully obtained token: eyJhbGciOiJIUzI1NiIs...

Connecting to WebSocket...
URL: ws://localhost:8000/api/ws/statistics?token=***
✓ WebSocket connected!

Waiting for welcome message...
✓ Received welcome message:
{
  "type": "connection_status",
  "status": "connected",
  "connection_id": "a1b2c3d4-...",
  "user": {
    "id": 1,
    "username": "admin"
  },
  "message": "WebSocket connection established successfully"
}

Sending ping...
✓ Ping sent

Waiting for pong...
✓ Received pong:
{
  "type": "pong",
  "timestamp": "2025-10-18T12:00:00"
}

Listening for statistics updates (max 5 seconds)...
✓ Received statistics_update message
  Statistics: {...}

✓ WebSocket test completed successfully!

============================================================
✓ ALL TESTS PASSED
============================================================
```

### Testing with Frontend

1. **Start Backend:**
   ```bash
   cd opencv_surveillance
   ./venv/bin/python3 -m backend.main
   ```

2. **Start Frontend (if needed):**
   ```bash
   cd opencv_surveillance/frontend
   npm run dev
   ```

3. **Open Browser:**
   - Navigate to `http://localhost:8000`
   - Login with credentials
   - Check browser console (F12)

**Expected Console Output:**
```javascript
Connecting to WebSocket: ws://localhost:8000/api/ws/statistics?token=***
WebSocket connected successfully
Connection status: {type: 'connection_status', status: 'connected', ...}
```

4. **Check WebSocket Status Indicator:**
   - Look at bottom-left of sidebar
   - Should show: 🟢 Connected

---

## 📊 Verification Checklist

- [x] Code changes implemented
- [x] Test script created
- [x] Manual testing passed
- [x] Frontend integration verified
- [x] Browser console shows no errors
- [x] Real-time statistics updating
- [ ] Production testing (user verification)

---

## 🚀 Deployment

### Files Changed
1. `backend/api/routes/websockets.py` - Fixed dependency injection
2. `test_websocket_connection.py` - New test script

### Deployment Steps

1. **Update Backend:**
   ```bash
   # No additional dependencies needed
   # Changes are code-only
   ```

2. **Restart Server:**
   ```bash
   # Stop current server (Ctrl+C)
   cd opencv_surveillance
   ./venv/bin/python3 -m backend.main
   ```

3. **Verify Fix:**
   ```bash
   # Run test script
   python test_websocket_connection.py admin your_password
   ```

4. **Frontend Refresh:**
   ```bash
   # Users may need to hard refresh browser
   # Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows/Linux)
   ```

---

## 🔄 Rollback Plan

If issues occur:

```bash
git checkout HEAD -- opencv_surveillance/backend/api/routes/websockets.py
# Restart server
```

**Note:** This returns to broken state, but fallback polling will still work.

---

## 📝 Related Issues

### Similar Patterns in Codebase

Checked all WebSocket endpoints for similar issues:

1. **✓ `/api/ws/statistics`** - Fixed in this PR
2. **✓ `/api/audio/ws/{camera_id}`** - No database dependencies, already correct

No other WebSocket endpoints have this issue.

---

## 💡 Lessons Learned

### 1. FastAPI WebSocket Dependency Limitations

FastAPI's dependency injection works differently for WebSockets:

| Feature | HTTP Endpoints | WebSocket Endpoints |
|---------|---------------|---------------------|
| `Depends()` | ✓ Works | ⚠️ Limited |
| Query params | ✓ Works | ✓ Works |
| Path params | ✓ Works | ✓ Works |
| Request body | ✓ Works | ✗ N/A |
| Database sessions | ✓ Auto-managed | ⚠️ Manual only |

### 2. Resource Management

**Short-lived operations** (authentication) should use manual session management:
```python
db = SessionLocal()
try:
    # Quick operation
    user = verify_token(token, db)
finally:
    db.close()
```

**Long-lived operations** (entire request) can use `Depends()`:
```python
@router.get("/users/")
def list_users(db: Session = Depends(get_db)):  # ✓ OK for HTTP
    return db.query(User).all()
```

### 3. Error Handling Best Practices

Always close WebSocket with appropriate status codes:
```python
# Authentication failure
await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")

# Rate limit exceeded
await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Rate limit exceeded")

# Normal closure
await websocket.close(code=1000, reason="Client disconnect")
```

---

## 🔮 Future Improvements

### 1. Connection Pooling
Consider connection pooling for WebSocket database access:
```python
from sqlalchemy.pool import StaticPool

engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool,  # Better for WebSocket usage
    pool_size=20,
    max_overflow=40
)
```

### 2. Authentication Caching
Cache user lookups to avoid repeated database queries:
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user_by_username(username: str):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()
```

### 3. Token Refresh
Implement token refresh for long-lived WebSocket connections:
```python
# Client sends refresh request before token expires
{
  "type": "refresh_token",
  "refresh_token": "..."
}

# Server responds with new token
{
  "type": "token_refreshed",
  "access_token": "new_token_here"
}
```

---

## 📚 References

- **FastAPI WebSockets:** https://fastapi.tiangolo.com/advanced/websockets/
- **WebSocket Status Codes:** https://developer.mozilla.org/en-US/docs/Web/API/CloseEvent/code
- **SQLAlchemy Sessions:** https://docs.sqlalchemy.org/en/20/orm/session_basics.html

---

## 🎯 Summary

### What Was Broken
- WebSocket endpoint using `Depends(get_db)` for database session
- FastAPI couldn't resolve dependency before accepting WebSocket connection
- All WebSocket connections rejected with 403 Forbidden

### What Was Fixed
- Removed database dependency from function signature
- Manually create database session only when needed (authentication)
- Proper cleanup with try/finally blocks
- WebSocket connections now succeed

### Impact
- ✅ Real-time dashboard updates working
- ✅ Live camera statistics streaming
- ✅ No more forced polling fallback
- ✅ Better user experience

---

**Fix Implemented By:** Claude Code
**Date:** October 18, 2025
**Test Status:** ✅ Passing
**Ready for Deployment:** Yes

---

**End of Report**
