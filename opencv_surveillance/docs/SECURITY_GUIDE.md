# OpenEye Security Guide (v3.6.0)

**Last Updated**: 2025-10-24
**Version**: 3.6.0

This guide covers all security features in OpenEye, including the new v3.6.0 enhancements.

---

## Table of Contents

1. [Security Overview](#security-overview)
2. [Per-Endpoint Rate Limiting](#per-endpoint-rate-limiting)
3. [CSRF Protection](#csrf-protection)
4. [Two-Factor Authentication (2FA)](#two-factor-authentication-2fa)
5. [Audit Logging](#audit-logging)
6. [Existing Security Features](#existing-security-features)
7. [Production Security Checklist](#production-security-checklist)
8. [Troubleshooting](#troubleshooting)

---

## Security Overview

OpenEye implements multiple layers of security to protect your surveillance system:

### v3.6.0 New Security Features ✨

- **Per-Endpoint Rate Limiting** - Granular rate limits for different API categories
- **CSRF Protection** - Double-submit cookie pattern for state-changing requests
- **Two-Factor Authentication (2FA)** - TOTP-based 2FA with QR code setup
- **Enhanced Audit Logging** - Comprehensive security event tracking

### Existing Security Features (v3.5.x)

- **JWT Authentication** - Secure token-based authentication
- **Password Hashing** - bcrypt with salt
- **Global Rate Limiting** - 1000 requests/minute
- **SQL Injection Protection** - Pattern-based detection
- **Security Headers** - X-Frame-Options, CSP, HSTS, etc.
- **Role-Based Access Control** - Admin, User, Viewer roles
- **Encrypted Credentials** - Fernet encryption for notification providers

---

## Per-Endpoint Rate Limiting

Replaces the global rate limiter with granular limits per API category.

### How It Works

Different API endpoints have different rate limits based on their category:

```python
{
    "auth": (10, 60),    # Authentication: 10 requests/minute
    "write": (30, 60),   # Write operations: 30 requests/minute
    "read": (100, 60),   # Read operations: 100 requests/minute
    "stream": (500, 60), # Streaming: 500 requests/minute
}
```

### Configuration

Edit `backend/main.py` to customize limits:

```python
app.add_middleware(EndpointRateLimiter, custom_limits={
    "auth": (5, 60),     # Stricter: 5 auth requests/minute
    "write": (50, 60),   # More generous: 50 writes/minute
    "read": (200, 60),   # More generous: 200 reads/minute
    "stream": (1000, 60),# Very generous: 1000 streams/minute
})
```

### Endpoint Categories

**Authentication (`auth`)**:
- `/api/token`
- `/api/auth/login`
- `/api/auth/register`

**Write Operations (`write`)**:
- POST/PUT/DELETE to `/api/cameras`, `/api/faces`, `/api/alerts`, etc.

**Read Operations (`read`)**:
- GET requests (default category)

**Streaming (`stream`)**:
- `/api/cameras/*/stream`
- `/recordings/*`

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Category: read
```

### Testing

```bash
# Test authentication rate limit
for i in {1..15}; do
  curl -X POST http://localhost:8000/api/token \
    -d "username=test&password=wrong"
  echo "Request $i"
done

# You should get 429 Too Many Requests after 10 attempts
```

---

## CSRF Protection

Cross-Site Request Forgery protection using the double-submit cookie pattern.

### How It Works

1. Server generates CSRF token on first GET request
2. Token stored in HttpOnly cookie
3. Client must include token in `X-CSRF-Token` header for state-changing requests
4. Server validates cookie and header match

### Enabling CSRF Protection

**By default, CSRF is DISABLED** for ease of development. Enable in production:

Edit `backend/main.py`:

```python
# Uncomment this line:
app.add_middleware(CSRFProtection)
```

### Exempt Endpoints

These endpoints do NOT require CSRF tokens:
- `/api/token` - OAuth2 token endpoint
- `/api/auth/login` - Login
- `/api/auth/register` - Registration
- `/api/docs` - API documentation
- `/ws/*` - WebSocket endpoints

### Frontend Integration

#### 1. Include Token in Headers

```javascript
// Get CSRF token from cookie
function getCSRFToken() {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : null;
}

// Include in all POST/PUT/DELETE requests
fetch('/api/cameras', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CSRF-Token': getCSRFToken(),  // Required!
  },
  body: JSON.stringify({...})
});
```

#### 2. Axios Interceptor (Recommended)

```javascript
import axios from 'axios';

// Automatically add CSRF token to all requests
axios.interceptors.request.use(config => {
  if (['post', 'put', 'delete', 'patch'].includes(config.method)) {
    const csrfToken = getCSRFToken();
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});
```

### Error Handling

If CSRF validation fails, you'll receive:

```json
{
  "detail": "CSRF token validation failed. Please refresh the page."
}
```

Status code: `403 Forbidden`

---

## Two-Factor Authentication (2FA)

TOTP-based two-factor authentication for enhanced account security.

### Features

- TOTP (Time-based One-Time Password) using authenticator apps
- QR code enrollment for easy setup
- 10 backup codes for account recovery
- Compatible with Google Authenticator, Authy, Microsoft Authenticator, etc.

### Database Migration

Run the 2FA migration to add required fields:

```bash
cd opencv_surveillance
./venv/bin/python3 scripts/migrate_add_2fa_v3.6.0.py
```

This adds to the `users` table:
- `totp_secret` - Encrypted TOTP secret
- `two_factor_enabled` - Boolean flag
- `backup_codes` - JSON array of hashed backup codes
- `two_factor_enrolled_at` - Enrollment timestamp

### API Endpoints

#### 1. Enable 2FA (Get QR Code)

```bash
POST /api/auth/2fa/enable
Authorization: Bearer {token}
```

**Response**:
```json
{
  "secret": "JBSWY3DPEHPK3PXP",
  "qr_code": "data:image/png;base64,...",
  "backup_codes": [
    "ABCD-1234-WXYZ",
    "EFGH-5678-STUV",
    ...
  ]
}
```

#### 2. Verify and Activate 2FA

```bash
POST /api/auth/2fa/verify
Authorization: Bearer {token}
Content-Type: application/json

{
  "token": "123456"
}
```

**Response**:
```json
{
  "success": true,
  "message": "2FA enabled successfully"
}
```

#### 3. Login with 2FA

```bash
POST /api/auth/login-2fa
Content-Type: application/json

{
  "username": "admin",
  "password": "your-password",
  "totp_token": "123456"
}
```

**Response**:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

#### 4. Disable 2FA

```bash
POST /api/auth/2fa/disable
Authorization: Bearer {token}
Content-Type: application/json

{
  "password": "your-password"
}
```

### Setup Instructions for Users

**Step 1: Enable 2FA**

1. Go to Account Settings → Security
2. Click "Enable Two-Factor Authentication"
3. Scan the QR code with your authenticator app:
   - Google Authenticator (iOS/Android)
   - Authy (iOS/Android/Desktop)
   - Microsoft Authenticator (iOS/Android)
   - 1Password, LastPass, etc.

**Step 2: Save Backup Codes**

⚠️ **IMPORTANT**: Save your 10 backup codes in a secure location. You'll need them if you lose access to your authenticator app.

**Step 3: Verify Setup**

1. Enter the 6-digit code from your authenticator app
2. If correct, 2FA is now enabled

**Step 4: Login with 2FA**

1. Enter username and password as usual
2. When prompted, enter the 6-digit code from your authenticator app
3. Code refreshes every 30 seconds

### Backup Code Recovery

If you lose your authenticator device:

1. Click "Use backup code" on login screen
2. Enter one of your 10 backup codes
3. Each backup code can only be used once
4. After using a backup code, disable and re-enable 2FA to generate new codes

### Security Best Practices

1. **Store backup codes securely** - Print them or use a password manager
2. **Don't share your secret key** - The QR code contains sensitive data
3. **Use a trusted authenticator app** - Avoid SMS-based 2FA (less secure)
4. **Enable 2FA for admin accounts** - Protect high-privilege accounts first

---

## Audit Logging

Comprehensive logging of security-sensitive operations for compliance and forensics.

### What Gets Logged

**Authentication Events**:
- Login success/failure
- Logout
- Token refresh
- Password changes
- 2FA enrollment/disable

**Authorization Events**:
- Access denied (role-based)
- Permission changes

**User Management**:
- User created/deleted/updated
- User disabled/enabled

**Camera Operations**:
- Camera added/removed
- Camera started/stopped
- Camera configuration changes

**Face Recognition**:
- Face uploaded/deleted
- Face identified in stream

**Recording Operations**:
- Recording started/stopped
- Recording deleted
- Recording downloaded

**Alert Operations**:
- Alert triggered/dismissed
- Alert configuration changed

**System Events**:
- System startup/shutdown
- Configuration changes

**Security Events**:
- Rate limit exceeded
- SQL injection attempts
- CSRF validation failures
- Invalid JWT tokens

### Log Format

Audit logs are stored in JSONL format (one JSON object per line):

**Location**: `logs/audit/audit_YYYYMM.jsonl`

**Example Entry**:
```json
{
  "timestamp": "2025-10-24T14:30:15.123456",
  "event_type": "login_success",
  "user": "admin",
  "ip_address": "192.168.1.100",
  "success": true,
  "resource": null,
  "details": {}
}
```

### Querying Audit Logs

#### Using `jq` (JSON query tool)

```bash
# View all login attempts today
cat logs/audit/audit_202510.jsonl | grep "login" | jq .

# Count failed logins by user
cat logs/audit/audit_202510.jsonl | \
  grep "login_failed" | \
  jq -r '.user' | sort | uniq -c

# Find all actions by specific user
cat logs/audit/audit_202510.jsonl | \
  jq 'select(.user == "admin")'

# Security events only
cat logs/audit/audit_202510.jsonl | \
  jq 'select(.event_type | contains("sql_injection") or contains("rate_limit"))'
```

#### Using Python

```python
import json
from pathlib import Path

# Load audit log
audit_file = Path("logs/audit/audit_202510.jsonl")
events = []

with open(audit_file) as f:
    for line in f:
        events.append(json.loads(line))

# Filter failed logins
failed_logins = [
    e for e in events
    if e['event_type'] == 'login_failed'
]

# Group by IP address
from collections import Counter
ip_counts = Counter(e['ip_address'] for e in failed_logins)
print(f"Failed logins by IP: {ip_counts}")
```

### Retention Policy

- Audit logs are rotated monthly (one file per month)
- **Recommendation**: Retain logs for at least 90 days
- For compliance, consider archiving to cold storage (S3 Glacier, etc.)

### Compliance

Audit logging helps meet requirements for:
- GDPR (data access tracking)
- HIPAA (access logging)
- PCI DSS (security event monitoring)
- SOC 2 (audit trails)

---

## Existing Security Features

### JWT Authentication

**Configuration** (`.env`):
```bash
JWT_SECRET_KEY=<random-64-char-hex>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Token Refresh**:
- Tokens expire after 30 minutes
- Frontend automatically refreshes on 401 Unauthorized

### Password Requirements

- Minimum 8 characters
- Hashed with bcrypt (cost factor 12)
- Automatically truncated to 72 bytes (bcrypt limit)

### SQL Injection Protection

Blocks common SQL injection patterns:
- `UNION SELECT`
- `DROP TABLE`
- `INSERT INTO`
- SQL comments (`--`, `/*`)
- Boolean logic (`OR 1=1`)

### Security Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy: default-src 'self'`

### Role-Based Access Control

Three roles with different permissions:

**Admin**:
- Full system access
- User management
- System configuration
- Camera management

**User**:
- View cameras and recordings
- Manage own cameras
- Upload faces
- Configure personal alerts

**Viewer**:
- View-only access
- No configuration changes
- No deletions

---

## Production Security Checklist

### Pre-Deployment

- [ ] Change default admin password
- [ ] Generate strong secret keys:
  ```bash
  openssl rand -hex 32  # SECRET_KEY
  openssl rand -hex 32  # JWT_SECRET_KEY
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # NOTIFICATION_ENCRYPTION_KEY
  ```
- [ ] Enable HTTPS with valid SSL certificate (nginx/Caddy reverse proxy)
- [ ] Restrict CORS_ORIGINS to your domain only
- [ ] Enable CSRF protection (uncomment in main.py)
- [ ] Configure firewall rules (only port 8000 or HTTPS 443)
- [ ] Set up database backups (SQLite or PostgreSQL)

### Post-Deployment

- [ ] Monitor audit logs daily for suspicious activity
- [ ] Review rate limit headers to ensure proper configuration
- [ ] Test 2FA enrollment and login flow
- [ ] Verify CSRF protection on all forms
- [ ] Check security headers with SecurityHeaders.com
- [ ] Run security scan (OWASP ZAP, Burp Suite Community)
- [ ] Set up log rotation and archival
- [ ] Document incident response procedures

### Ongoing Maintenance

- [ ] Review audit logs weekly
- [ ] Update dependencies monthly (`pip list --outdated`)
- [ ] Rotate JWT_SECRET_KEY quarterly (invalidates all sessions)
- [ ] Review user accounts and remove inactive users
- [ ] Test backup restoration quarterly
- [ ] Review and update firewall rules

---

## Troubleshooting

### Rate Limiting Issues

**Problem**: Getting 429 Too Many Requests

**Solution**:
1. Check rate limit headers in response:
   ```
   X-RateLimit-Limit: 10
   X-RateLimit-Remaining: 0
   X-RateLimit-Category: auth
   ```
2. Increase limits in `main.py` if needed
3. Wait 60 seconds for rate limit to reset

### CSRF Protection Issues

**Problem**: 403 Forbidden on POST/PUT/DELETE requests

**Solution**:
1. Check if CSRF protection is enabled (should be disabled in dev)
2. Ensure frontend includes `X-CSRF-Token` header
3. Verify cookie is being set on GET requests
4. Check cookie is not being blocked by browser (SameSite policy)

### 2FA Issues

**Problem**: "Invalid token" error

**Solution**:
1. Check system time is synchronized (TOTP is time-based)
   ```bash
   timedatectl status  # Linux
   date  # macOS
   ```
2. Ensure token is entered within 30-second window
3. Try using backup code if token consistently fails
4. Re-enable 2FA if secret was compromised

**Problem**: Lost authenticator device

**Solution**:
1. Use backup code to login
2. Disable 2FA in settings
3. Re-enable 2FA with new QR code
4. Generate new backup codes

### Audit Log Issues

**Problem**: Audit log file not being created

**Solution**:
1. Check `logs/audit` directory exists and is writable
2. Verify `get_audit_logger()` is called during startup
3. Check application logs for errors

**Problem**: Audit log file growing too large

**Solution**:
1. Implement log rotation:
   ```bash
   # Linux logrotate config
   /path/to/logs/audit/*.jsonl {
       monthly
       rotate 12
       compress
       missingok
       notifempty
   }
   ```
2. Archive old logs to S3/GCS/Azure

---

## See Also

- [API Documentation](API_DOCUMENTATION.md)
- [User Guide](USER_GUIDE.md)
- [Deployment Guide](../DOCKER_HUB_OVERVIEW.md)
- [TODO - Security Roadmap](../../TODO.md)

---

**Version**: 3.6.0
**Last Updated**: 2025-10-24
**Maintained By**: OpenEye Security Team
