# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from datetime import datetime, timedelta, timezone
from typing import Optional
import sys
import logging
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt

from backend.database import crud
from backend.api.schemas import user as user_schema
from sqlalchemy.orm import Session
from backend.database.session import SessionLocal
from backend.core.security import verify_password
import os

logger = logging.getLogger(__name__)

# Security Configuration (imported from centralized config)
from backend.core.config import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

# Require SECRET_KEY and JWT_SECRET_KEY in production
SECRET_KEY = os.getenv("SECRET_KEY")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Separate key for JWTs

# Validate secret keys
if not SECRET_KEY or SECRET_KEY in ["your-secret-key", "dev-secret-key"]:
    if os.getenv("ENVIRONMENT", "development") == "production":
        logger.error("CRITICAL: SECRET_KEY must be set in production!")
        logger.error("Generate with: openssl rand -hex 64")
        sys.exit(1)
    logger.warning("Using weak SECRET_KEY - DEVELOPMENT ONLY")
    SECRET_KEY = "dev-secret-key-change-in-production"

if not JWT_SECRET_KEY:
    JWT_SECRET_KEY = SECRET_KEY  # Fallback to SECRET_KEY if not set
    logger.warning("JWT_SECRET_KEY not set, using SECRET_KEY (set separate key in production)")
elif JWT_SECRET_KEY == SECRET_KEY:
    logger.warning(
        "⚠️  SECURITY WARNING: JWT_SECRET_KEY and SECRET_KEY are identical! "
        "Use separate keys in production for better security isolation. "
        "Generate a new key: openssl rand -hex 64"
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {
                    ', '.join(allowed_roles)}",
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

    # Check if token is revoked
    if token_record.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
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
