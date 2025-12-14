# OpenEye Security Audit Report

**Date**: October 2025
**Version**: Pre-v4.0.0
**Auditor**: Security Review
**Priority**: HIGH

---

## Executive Summary

This security audit of OpenEye surveillance system identifies **8 security findings** across authentication, authorization, CORS configuration, and file access controls. While the codebase demonstrates good security practices (bcrypt password hashing, SQL injection protection, security headers), several **CRITICAL** and **HIGH** priority issues require immediate attention before v4.0.0 release.

### Risk Summary
- **CRITICAL**: 2 findings
- **HIGH**: 3 findings
- **MEDIUM**: 2 findings
- **LOW**: 1 finding

---

## 1. Authentication Vulnerabilities

### 🔴 CRITICAL: Weak Default Secret Key

**File**: `backend/core/auth.py:20`

**Issue**:
```python
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
```

The application uses a hardcoded fallback secret key if the environment variable is not set. This allows attackers to forge JWT tokens and gain unauthorized access.

**Impact**: Complete authentication bypass, privilege escalation

**Recommendation**:
```python
# Require SECRET_KEY in production
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "your-secret-key":
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("SECRET_KEY must be set in production!")
    logger.warning("Using weak SECRET_KEY - DEVELOPMENT ONLY")
    SECRET_KEY = "dev-secret-key-not-for-production"
```

---

### 🟡 HIGH: No Refresh Token Mechanism

**File**: `backend/core/auth.py`

**Issue**: JWT tokens expire after 30 minutes with no refresh token mechanism. Users must re-authenticate frequently, leading to poor UX and potential security issues (credentials sent more often).

**Current**:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # No refresh token
```

**Impact**:
- Frequent re-authentication required
- Credentials transmitted more often (increased attack surface)
- Poor user experience

**Recommendation**: Implement refresh token pattern
```python
# In backend/core/auth.py
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Short-lived access token
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Long-lived refresh token

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_refresh_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload.get("sub")
    except JWTError:
        return None
```

---

### 🟢 MEDIUM: JWT Token Expiration Too Long

**File**: `backend/core/auth.py:22`

**Issue**: 30-minute token expiration is too long for a security-sensitive application handling surveillance footage.

**Current**:
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 30
```

**Recommendation**: Reduce to 15 minutes with refresh token support
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # More secure with refresh tokens
```

---

### ✅ GOOD: Password Hashing

**File**: `backend/core/auth.py:59-83`

**Analysis**: Uses bcrypt with automatic salting. Handles 72-byte limit correctly.

```python
salt = bcrypt.gensalt()
hashed = bcrypt.hashpw(password_bytes, salt)
```

**Status**: ✅ SECURE - No changes needed

---

## 2. Authorization Vulnerabilities

### 🔴 CRITICAL: Missing Authorization Checks on API Endpoints

**Files**: Multiple route files

**Issue**: Many API endpoints lack `Depends(get_current_active_user)` or role-based checks, allowing unauthenticated access.

**Examples**:
- `/api/recordings/` - List all recordings (should require auth)
- `/api/cameras/` - Camera management (should require auth)
- `/api/faces/history` - Face detection history (should require auth)

**Impact**:
- Unauthorized access to surveillance footage
- Ability to manipulate camera settings
- Privacy violations

**Recommendation**: Add authentication to ALL API endpoints

```python
# BEFORE (vulnerable)
@router.get("/recordings/")
def list_recordings(db: Session = Depends(get_db)):
    ...

# AFTER (secure)
@router.get("/recordings/")
def list_recordings(
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user)
):
    ...
```

**Required Changes**:
1. Audit ALL routes in `backend/api/routes/`
2. Add `Depends(get_current_active_user)` to protected endpoints
3. Add `Depends(require_admin)` to admin-only endpoints
4. Document public vs. protected endpoints

---

### 🟡 HIGH: No Role-Based Access Control (RBAC)

**File**: `backend/core/auth.py:143-168`

**Issue**: RBAC framework exists but is NOT implemented on any endpoints. All authenticated users have full access.

**Current State**:
```python
# RBAC exists but unused
require_admin = require_role(["admin"])
require_user = require_role(["admin", "user"])
```

**Impact**: Any authenticated user can:
- Delete surveillance footage
- Modify camera configurations
- Access admin functions
- Change system settings

**Recommendation**: Implement RBAC on sensitive endpoints

```python
# Admin-only endpoints
@router.delete("/recordings/{recording_id}", dependencies=[Depends(require_admin)])
@router.delete("/cameras/{camera_id}", dependencies=[Depends(require_admin)])
@router.post("/settings/update", dependencies=[Depends(require_admin)])

# User endpoints (read-only)
@router.get("/recordings/", dependencies=[Depends(require_user)])
@router.get("/cameras/", dependencies=[Depends(require_user)])
```

---

## 3. CORS & Security Headers

### 🟡 HIGH: Permissive CORS Configuration

**File**: `backend/main.py:103-109`

**Issue**: CORS allows ALL origins in production

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❌ DANGEROUS in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impact**:
- CSRF attacks possible
- Credentials can be stolen from malicious websites
- Session hijacking

**Recommendation**: Restrict to specific origins

```python
# Load from environment
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:3000"  # Dev default
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # ✅ Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Specific methods
    allow_headers=["Authorization", "Content-Type"],  # Specific headers
)
```

---

### ✅ GOOD: Security Headers

**File**: `backend/middleware/security.py:17-42`

**Analysis**: Implements comprehensive security headers:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy` with reasonable defaults

**Status**: ✅ SECURE - Good implementation

---

## 4. File Access & Path Traversal

### 🟢 MEDIUM: Path Traversal Risk in File Serving

**Files**: `backend/api/routes/recordings.py`, `backend/api/routes/cameras.py`

**Issue**: File paths are retrieved from database and served directly without validation against allowed directories.

**Vulnerable Code**:
```python
@router.get("/recordings/{recording_id}/download")
def download_recording(recording_id: int, db: Session = Depends(get_db)):
    recording = db.query(models.RecordingEvent).filter(...).first()
    # No validation that recording.recording_path is within allowed directory
    return FileResponse(recording.recording_path, ...)
```

**Attack Scenario**:
1. Attacker modifies database (SQL injection or compromised admin)
2. Sets `recording_path` to `../../../../etc/passwd`
3. Downloads sensitive system files

**Recommendation**: Validate paths before serving

```python
from backend.core.paths import paths

def safe_file_response(file_path: str, allowed_dir: Path) -> FileResponse:
    """Validate file is within allowed directory"""
    try:
        full_path = Path(file_path).resolve()
        allowed_dir = allowed_dir.resolve()

        # Check if path is within allowed directory
        if not str(full_path).startswith(str(allowed_dir)):
            raise HTTPException(403, "Access denied: Invalid file path")

        if not full_path.exists():
            raise HTTPException(404, "File not found")

        return FileResponse(full_path, ...)
    except Exception as e:
        logger.error(f"File access error: {e}")
        raise HTTPException(403, "Access denied")

# Usage
@router.get("/recordings/{recording_id}/download")
def download_recording(...):
    ...
    return safe_file_response(
        recording.recording_path,
        paths.recordings_dir
    )
```

---

### ✅ GOOD: Path Management

**File**: `backend/core/paths.py`

**Analysis**: Centralized path management with:
- Environment variable support
- Automatic directory creation
- Relative path conversion
- Type-safe Path operations

**Status**: ✅ SECURE - Well-designed system

---

## 5. Input Validation

### ✅ GOOD: SQL Injection Protection

**File**: `backend/middleware/security.py:80-128`

**Analysis**:
- SQLAlchemy ORM used throughout (parameterized queries)
- Pattern-based SQL injection detection middleware
- Validates query parameters and paths

**Status**: ✅ SECURE - Defense in depth approach

---

### 🟢 LOW: Frontend XSS Prevention

**Files**: Frontend React components

**Issue**: React provides default XSS protection, but some components use `dangerouslySetInnerHTML` or direct DOM manipulation.

**Recommendation**:
1. Audit all `dangerouslySetInnerHTML` usage
2. Sanitize user input with DOMPurify
3. Use CSP headers (already implemented)

```bash
# Search for potential XSS vectors
cd frontend/src
grep -r "dangerouslySetInnerHTML" .
grep -r "innerHTML" .
```

---

## 6. Dependency Vulnerabilities

### 🟡 Recommended: Run Safety Check

**Command**:
```bash
cd opencv_surveillance
safety check --json
```

**Purpose**: Check for known vulnerabilities in Python dependencies

**Note**: Safety was installed during this audit but not run due to Python 3.14 compatibility issues with Bandit.

---

## Priority Action Items

### Before v4.0.0 Release (MUST FIX)

1. **Fix SECRET_KEY fallback** (`auth.py:20`) - CRITICAL
2. **Add authentication to all protected endpoints** - CRITICAL
3. **Restrict CORS origins** (`main.py:105`) - HIGH
4. **Implement refresh token mechanism** - HIGH
5. **Add path traversal validation** (`recordings.py`, `cameras.py`) - MEDIUM

### v4.0.0 Features (Planned)

6. **Implement RBAC on all endpoints** - HIGH
7. **Reduce token expiration to 15 minutes** - MEDIUM
8. **Audit frontend for XSS vectors** - LOW

---

## Security Checklist for Deployment

```markdown
- [ ] Set strong SECRET_KEY environment variable (64+ random chars)
- [ ] Set JWT_SECRET_KEY environment variable (different from SECRET_KEY)
- [ ] Configure CORS_ORIGINS for your domain
- [ ] Enable HTTPS/TLS (Strict-Transport-Security already configured)
- [ ] Review and restrict API endpoint access (add authentication)
- [ ] Implement RBAC for multi-user access
- [ ] Set up refresh token mechanism
- [ ] Validate file paths before serving
- [ ] Run `safety check` on dependencies
- [ ] Enable rate limiting (already at 1000 req/min)
- [ ] Configure firewall rules
- [ ] Set up log monitoring for security events
```

---

## Security Best Practices Summary

### ✅ Currently Implemented
- Bcrypt password hashing with salting
- JWT token authentication
- SQL injection protection (ORM + middleware)
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Rate limiting (1000 requests/minute)
- Centralized path management
- Input validation on query parameters

### ❌ Needs Implementation
- Strong secret key enforcement
- Refresh token mechanism
- Per-endpoint authentication checks
- Role-based access control (RBAC)
- Restricted CORS origins
- Path traversal prevention in file serving
- Regular dependency vulnerability scanning

---

## Tools & Resources

### Security Tools
```bash
# Install security tools
pip install bandit safety

# Run security linters
bandit -r backend/ -f html -o security_report.html
safety check --json

# Audit frontend
npm audit
```

### Recommended Reading
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)

---

## Conclusion

OpenEye demonstrates solid security fundamentals but requires critical fixes before v4.0.0 release. The most urgent issues are:
1. Hardcoded secret key fallback
2. Missing authentication on API endpoints
3. Permissive CORS configuration

Addressing these issues will significantly improve the security posture of the application and protect users' surveillance data.

**Estimated Remediation Time**: 2-3 days for critical issues, 1 week for full implementation including RBAC.
