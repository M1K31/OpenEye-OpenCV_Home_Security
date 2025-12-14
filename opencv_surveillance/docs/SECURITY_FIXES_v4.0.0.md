# Security Fixes for v4.0.0 - Implementation Guide

## Quick Reference

This document provides copy-paste code fixes for the critical security issues identified in the security audit.

---

## Fix 1: Enforce Strong SECRET_KEY (CRITICAL)

**File**: `backend/core/auth.py`

**Replace lines 19-22:**

```python
# BEFORE
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

**WITH:**

```python
# AFTER
import sys

# Require SECRET_KEY and JWT_SECRET_KEY in production
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Separate key for JWTs
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Reduced from 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Validate secret keys
if not SECRET_KEY or SECRET_KEY in ["your-secret-key", "dev-secret-key"]:
    if os.getenv("ENVIRONMENT", "development") == "production":
        logger.error("CRITICAL: SECRET_KEY must be set in production!")
        sys.exit(1)
    logger.warning("Using weak SECRET_KEY - DEVELOPMENT ONLY")
    SECRET_KEY = "dev-secret-key-change-in-production"

if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = SECRET_KEY  # Fallback to SECRET_KEY if not set
    logger.warning("JWT_SECRET_KEY not set, using SECRET_KEY")
```

---

## Fix 2: Implement Refresh Tokens (HIGH)

**File**: `backend/core/auth.py`

**Add these functions after `create_access_token`:**

```python
def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "type": "refresh"  # Mark as refresh token
    })
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_refresh_token(token: str) -> Optional[str]:
    """
    Verify refresh token and return username if valid

    Args:
        token: Refresh token to verify

    Returns:
        Username if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            logger.warning("Invalid token type")
            return None
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError as e:
        logger.warning(f"Refresh token validation failed: {e}")
        return None


def refresh_access_token(refresh_token: str, db: Session) -> Optional[dict]:
    """
    Generate new access token from refresh token

    Args:
        refresh_token: Valid refresh token
        db: Database session

    Returns:
        Dictionary with new access token and user info, or None if invalid
    """
    username = verify_refresh_token(refresh_token)
    if not username:
        return None

    user = crud.get_user_by_username(db, username=username)
    if not user or not user.is_active:
        return None

    # Create new access token
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username
    }
```

**Add refresh endpoint in `backend/api/routes/users.py`:**

```python
@router.post("/auth/refresh")
def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Returns new access token if refresh token is valid
    """
    result = auth.refresh_access_token(refresh_token, db)
    if not result:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token"
        )
    return result
```

**Update login endpoint to return both tokens:**

```python
@router.post("/auth/login")
def login(form_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access + refresh tokens"""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    # Create both access and refresh tokens
    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = auth.create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,  # NEW
        "token_type": "bearer",
        "expires_in": auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # seconds
        "username": user.username
    }
```

---

## Fix 3: Restrict CORS Origins (HIGH)

**File**: `backend/main.py`

**Replace lines 103-109:**

```python
# BEFORE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DANGER
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**WITH:**

```python
# AFTER
# Load CORS origins from environment
CORS_ORIGINS_STR = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:3000"  # Dev defaults
)
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]

logger.info(f"CORS origins configured: {CORS_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
```

---

## Fix 4: Add Path Traversal Protection (MEDIUM)

**File**: `backend/api/routes/recordings.py` (and similar files)

**Add this helper function at the top:**

```python
from pathlib import Path
from backend.core.paths import paths
import logging

logger = logging.getLogger(__name__)


def safe_file_response(
    file_path: str,
    allowed_dir: Path,
    media_type: str = "application/octet-stream",
    filename: Optional[str] = None
) -> FileResponse:
    """
    Safely serve a file with path traversal protection

    Args:
        file_path: Path to file (from database)
        allowed_dir: Directory that file must be within
        media_type: MIME type for response
        filename: Optional filename for download

    Returns:
        FileResponse if file is safe to serve

    Raises:
        HTTPException: If file is outside allowed directory or doesn't exist
    """
    try:
        # Resolve paths to absolute
        full_path = Path(file_path).resolve()
        allowed_dir = allowed_dir.resolve()

        # Check if file is within allowed directory
        if not str(full_path).startswith(str(allowed_dir)):
            logger.warning(
                f"Path traversal attempt: {file_path} not in {allowed_dir}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: File path not in allowed directory"
            )

        # Check file exists
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        # Serve file
        if not filename:
            filename = full_path.name

        return FileResponse(
            path=str(full_path),
            media_type=media_type,
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Error serving file")
```

**Update download_recording function:**

```python
@router.get("/recordings/{recording_id}/download")
def download_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user)  # ADD AUTH
):
    """Download a recording file (with path traversal protection)"""
    recording = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Use safe file serving with path validation
    return safe_file_response(
        file_path=recording.recording_path,
        allowed_dir=paths.recordings_dir,
        media_type="video/mp4",
        filename=Path(recording.recording_path).name
    )
```

---

## Fix 5: Add Authentication to API Endpoints (CRITICAL)

**Files**: All files in `backend/api/routes/`

**Pattern to follow:**

```python
# BEFORE (NO AUTH)
@router.get("/recordings/")
def list_recordings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    ...

# AFTER (WITH AUTH)
@router.get("/recordings/")
def list_recordings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user)  # ADD THIS
):
    ...

# For admin-only endpoints
@router.delete("/recordings/{recording_id}")
def delete_recording(
    recording_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(require_admin)  # ADMIN ONLY
):
    ...
```

**Endpoints that MUST have authentication:**

```markdown
# User-level (require_user or get_current_active_user)
- GET /api/recordings/
- GET /api/recordings/{id}
- GET /api/recordings/{id}/download
- GET /api/cameras/
- GET /api/cameras/{id}
- GET /api/faces/people
- GET /api/faces/history
- GET /api/clusters/
- GET /api/motion_events/

# Admin-level (require_admin)
- DELETE /api/recordings/{id}
- POST /api/cameras/
- PUT /api/cameras/{id}
- DELETE /api/cameras/{id}
- POST /api/faces/upload
- DELETE /api/faces/{name}
- POST /api/faces/train
- POST /api/settings/update
- POST /api/automations/
- PUT /api/automations/{id}
- DELETE /api/automations/{id}
```

---

## Environment Variables for Production

**Create `.env` file:**

```bash
# Security - REQUIRED in production
SECRET_KEY=<generate-with-openssl-rand-hex-64>
JWT_SECRET_KEY=<generate-with-openssl-rand-hex-64>
ALGORITHM=HS256
ENVIRONMENT=production

# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS - CHANGE TO YOUR DOMAIN
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/openeye

# Logging
LOG_LEVEL=INFO
```

**Generate secure keys:**

```bash
# Generate SECRET_KEY
openssl rand -hex 64

# Generate JWT_SECRET_KEY (different from SECRET_KEY)
openssl rand -hex 64
```

---

## Testing Security Fixes

**Test authentication:**

```bash
# Should fail (401 Unauthorized)
curl http://localhost:8000/api/recordings/

# Should succeed with token
TOKEN=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | jq -r '.access_token')

curl http://localhost:8000/api/recordings/ \
  -H "Authorization: Bearer $TOKEN"
```

**Test refresh token:**

```bash
# Get refresh token
REFRESH=$(curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}' \
  | jq -r '.refresh_token')

# Use refresh token to get new access token
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}"
```

**Test path traversal protection:**

```bash
# Should fail (403 Forbidden)
# Manually modify database to set recording_path to ../../../../etc/passwd
# Then try to download - should be blocked
```

---

## Migration Checklist

```markdown
- [ ] Update auth.py with SECRET_KEY enforcement
- [ ] Implement refresh token functions
- [ ] Add refresh endpoint to users.py
- [ ] Update login endpoint to return refresh token
- [ ] Restrict CORS origins in main.py
- [ ] Add safe_file_response helper
- [ ] Update all file-serving endpoints
- [ ] Add authentication to all protected routes
- [ ] Test with authentication disabled (should fail)
- [ ] Test with valid authentication (should succeed)
- [ ] Test refresh token flow
- [ ] Test CORS from allowed/blocked origins
- [ ] Test path traversal attempts
- [ ] Update frontend to handle refresh tokens
- [ ] Update documentation
```

---

## Frontend Changes Required

**Update authService.js:**

```javascript
// Store both tokens
export const login = async (username, password) => {
  const response = await axios.post('/api/auth/login', {
    username,
    password
  });

  localStorage.setItem('access_token', response.data.access_token);
  localStorage.setItem('refresh_token', response.data.refresh_token);  // NEW

  return response.data;
};

// Refresh access token when expired
export const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return null;

  try {
    const response = await axios.post('/api/auth/refresh', {
      refresh_token: refreshToken
    });

    localStorage.setItem('access_token', response.data.access_token);
    return response.data.access_token;
  } catch (error) {
    // Refresh token expired, logout
    logout();
    return null;
  }
};

// Add axios interceptor to auto-refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const newToken = await refreshAccessToken();
      if (newToken) {
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return axios(originalRequest);
      }
    }

    return Promise.reject(error);
  }
);
```

---

## Summary

Implementing these fixes will:
1. ✅ Eliminate hardcoded secret key vulnerability
2. ✅ Add refresh token mechanism for better UX
3. ✅ Restrict CORS to prevent CSRF attacks
4. ✅ Prevent path traversal attacks
5. ✅ Enforce authentication on all endpoints

**Estimated Implementation Time**: 1-2 days

**Priority Order**:
1. SECRET_KEY enforcement (30 min)
2. CORS restriction (15 min)
3. Add authentication to endpoints (2-3 hours)
4. Path traversal protection (1 hour)
5. Refresh token mechanism (3-4 hours)
