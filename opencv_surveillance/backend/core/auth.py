# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import logging
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt

from backend.database import crud
from backend.api.schemas import user as user_schema
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal, get_db
from backend.core.security import verify_password
import os

logger = logging.getLogger(__name__)

# Security Configuration (imported from centralized config)
from backend.core.config import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

# Known published/placeholder keys that must never be used to sign tokens.
# The service binds 0.0.0.0, so signing with any value committed to source
# control would let any host on the network forge an admin JWT (audit F-02).
_KNOWN_WEAK_KEYS = {
    "",
    "your-secret-key",
    "dev-secret-key",
    "dev-secret-key-change-in-production",
    "change-me",
    "changeme",
}


def _load_or_create_secret_key() -> str:
    """
    Return a strong SECRET_KEY, never a published constant.

    Resolution order:
      1. A strong ``SECRET_KEY`` from the environment (the production path).
      2. A per-install key persisted at ``<data-dir>/secret.key`` with owner-only
         (0600) permissions, generated once and reused so sessions survive
         restarts. This replaces the old fallback to a constant that shipped in
         the repository.
      3. As a last resort (unwritable data dir), an ephemeral in-memory key —
         still random, still never the published constant.
    """
    env_key = os.getenv("SECRET_KEY")
    if env_key and env_key not in _KNOWN_WEAK_KEYS:
        return env_key

    if env_key:
        logger.warning(
            "SECRET_KEY is a known weak/placeholder value; generating a "
            "per-install key instead."
        )

    data_root = Path(
        os.getenv("OPENEYE_DATA_DIR")
        or os.getenv("OPENEYE_DATA_ROOT")
        or (Path.home() / ".local" / "share" / "openeye")
    )
    key_file = data_root / "secret.key"

    try:
        if key_file.exists():
            existing = key_file.read_text().strip()
            if existing and existing not in _KNOWN_WEAK_KEYS:
                return existing

        key_file.parent.mkdir(parents=True, exist_ok=True)
        new_key = secrets.token_hex(64)
        key_file.write_text(new_key)
        key_file.chmod(0o600)
        logger.warning(
            "SECRET_KEY was not provided; generated a new per-install key at %s "
            "(set SECRET_KEY in the environment to override).",
            key_file,
        )
        return new_key
    except OSError as exc:
        logger.error(
            "Could not persist a SECRET_KEY (%s); using an ephemeral in-memory "
            "key. Sessions will not survive a restart. Set SECRET_KEY explicitly.",
            exc,
        )
        return secrets.token_hex(64)


SECRET_KEY = _load_or_create_secret_key()

# JWT signing key. Falls back to SECRET_KEY when a separate key is not provided;
# both are now guaranteed strong (never a published constant).
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = SECRET_KEY
    logger.info("JWT_SECRET_KEY not set; deriving it from SECRET_KEY.")
elif JWT_SECRET_KEY in _KNOWN_WEAK_KEYS:
    logger.warning(
        "JWT_SECRET_KEY is a known weak/placeholder value; deriving from "
        "SECRET_KEY instead."
    )
    JWT_SECRET_KEY = SECRET_KEY

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


# get_db is imported from backend.database.session (see imports) rather than
# redefined here. FastAPI matches dependency_overrides by function IDENTITY, so a
# module-local copy — even an identical one — is a different dependency: overriding
# the canonical get_db silently missed this one, and authentication kept querying the
# real database. It also meant auth used a separate session provider from the rest of
# the app. Import the single definition instead of duplicating it.


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, username: str, password: str):
    user = crud.get_user_by_username(db, username=username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Bcrypt has a 72-byte limit. We automatically truncate passwords to 72 bytes
    to prevent errors while maintaining security. This is done transparently
    so users don't need to worry about byte limits.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    # Truncate to 72 bytes if necessary (bcrypt limit)
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    # Use bcrypt directly to bypass passlib's validation
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string in the format passlib expects
    return hashed.decode("utf-8")


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> user_schema.User:
    """
    Dependency to get the current authenticated user from JWT token

    Args:
        token: JWT access token from Authorization header
        db: Database session

    Returns:
        User object if authenticated

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: user_schema.User = Depends(get_current_user),
) -> user_schema.User:
    """
    Dependency to get the current active (not disabled) user

    Args:
        current_user: Current authenticated user

    Returns:
        User object if active

    Raises:
        HTTPException: If user is disabled
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_current_user_media(
    request: Request, db: Session = Depends(get_db)
) -> user_schema.User:
    """
    Authenticate a MEDIA request from either the Authorization header or a cookie.

    Media is loaded by the browser itself — live camera feeds are <img src=...> and
    recordings are <video src=...> / download links. A plain tag cannot attach an
    Authorization header, so protecting those routes with the normal bearer-only
    dependency would authenticate nothing and simply break playback. The browser DOES
    send cookies automatically, so accept the same JWT from an `access_token` cookie
    as a fallback.

    Deliberately NOT accepting the token from a query string: URLs end up in browser
    history, proxy logs and Referer headers, which is exactly where a credential
    should never be.

    Use this only for media/streaming endpoints; JSON APIs should keep using
    get_current_active_user so the bearer token stays the single mechanism there.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = None
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def require_role(allowed_roles: list):
    """
    Dependency factory to require specific user roles

    Args:
        allowed_roles: List of allowed role names (e.g., ['admin', 'user'])

    Returns:
        Dependency function that checks user role

    Example:
        @router.post("/admin-only", dependencies=[Depends(require_role(['admin']))])
    """

    async def role_checker(
        current_user: user_schema.User = Depends(get_current_active_user),
    ) -> user_schema.User:
        if current_user.role not in allowed_roles:
            roles_str = ', '.join(allowed_roles)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {roles_str}",
            )
        return current_user

    return role_checker


# Convenience dependencies for common role checks
require_admin = require_role(["admin"])
require_user = require_role(["admin", "user"])  # Admin or User (not Viewer)
require_any_authenticated = Depends(
    get_current_active_user)  # Any authenticated user


# ============================================================================
# REFRESH TOKEN FUNCTIONS (v3.8.0)
# ============================================================================


def create_tokens(
    db: Session,
    user: user_schema.User,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Create access token and refresh token pair for a user.

    This implements JWT token rotation with refresh tokens for improved security.
    The access token is short-lived (30 minutes) while the refresh token
    is long-lived (7 days) and stored in the database.

    Args:
        db: Database session
        user: User object to create tokens for
        device_info: User agent string for device tracking
        ip_address: Client IP address for security audit

    Returns:
        Dictionary with access_token, refresh_token, token_type, and expires_in

    Example:
        tokens = create_tokens(db, user, request.headers.get('User-Agent'))
        {
            "access_token": "eyJ...",
            "refresh_token": "abc123...",
            "token_type": "bearer",
            "expires_in": 1800
        }
    """
    # Create short-lived access token (30 minutes)
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Create long-lived refresh token (7 days)
    refresh_token = secrets.token_urlsafe(64)
    refresh_token_expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Store refresh token in database
    crud.create_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=refresh_token_expires,
        device_info=device_info,
        ip_address=ip_address,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
    }


def refresh_access_token(
    db: Session,
    refresh_token: str,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Generate new access token and refresh token using a refresh token.

    This implements refresh token rotation for security - each refresh
    generates a new refresh token and revokes the old one. This prevents
    token replay attacks.

    Args:
        db: Database session
        refresh_token: Refresh token string
        device_info: User agent string for new token
        ip_address: Client IP address for new token

    Returns:
        Dictionary with new access_token, refresh_token, token_type, and expires_in

    Raises:
        HTTPException: If refresh token is invalid, expired, or revoked

    Security Notes:
        - Old refresh token is immediately revoked
        - New refresh token is generated (token rotation)
        - Expired tokens are rejected
        - Revoked tokens are rejected
    """
    # Get refresh token from database
    token_record = crud.get_refresh_token(db, refresh_token)

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reuse detection. Refresh tokens are single-use: a successful refresh revokes
    # the old one. So being presented with an ALREADY-REVOKED token means the token
    # was replayed — either it was stolen and used after the legitimate client had
    # already rotated it, or the legitimate client is replaying a token an attacker
    # has also seen. Either way the family must be considered compromised, so revoke
    # every refresh token for this user and force a fresh login (OAuth 2.0 Security
    # BCP, "Refresh Token Protection"). Simply rejecting this one token would leave
    # the thief's other tokens working.
    if token_record.revoked:
        revoked_count = crud.revoke_all_user_tokens(db, token_record.user_id)
        logger.warning(
            "Refresh token reuse detected for user_id=%s (ip=%s); revoked %s token(s) "
            "for this user and forcing re-authentication.",
            token_record.user_id, ip_address, revoked_count,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if token is expired
    if token_record.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    user = crud.get_user(db, token_record.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke old refresh token (rotation)
    token_record.revoked = True
    db.commit()

    # Create new token pair
    return create_tokens(db, user, device_info, ip_address)


# Name of the cookie get_current_user_media falls back to. Kept here so the
# setter and the reader cannot drift apart.
MEDIA_COOKIE_NAME = "access_token"


def set_media_auth_cookie(response, access_token: str) -> None:
    """
    Mirror the access token into a cookie so the browser can load media.

    get_current_user_media has always accepted an `access_token` cookie, but
    nothing ever set one — the frontend keeps its token in localStorage, which a
    plain <img>/<video> tag cannot attach to a request. The result was that every
    media route protected by that dependency answered 401 to the tags that needed
    it, and inline recording playback did not work.

    HttpOnly, because JavaScript already has the token in localStorage for the
    Authorization header and does not need a second copy it can read — this one
    exists purely so the browser attaches it automatically.

    SameSite=Strict, because it is the CSRF control for these routes: the cookie
    is not sent on cross-site requests, so another site cannot use it to pull
    footage. See docs/development/ADR-001-csrf.md.

    Secure is set only when not serving over plain HTTP on localhost. Most
    installs are http://<lan-ip>:8000 with no certificate, and a Secure cookie
    would simply never be sent there, which would silently reintroduce the bug.
    """
    secure = os.getenv("OPENEYE_HTTPS", "false").lower() == "true"
    response.set_cookie(
        key=MEDIA_COOKIE_NAME,
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/",
    )


def clear_media_auth_cookie(response) -> None:
    """Remove the media cookie on logout, so the browser stops sending it."""
    response.delete_cookie(key=MEDIA_COOKIE_NAME, path="/")
