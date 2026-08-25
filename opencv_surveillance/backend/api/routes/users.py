# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
import bcrypt

from backend.database import crud
from backend.database.session import get_db
from backend.api.schemas import user as user_schema
from backend.api.schemas import two_factor as twofa_schema
from backend.api.schemas import password_reset as reset_schema
from backend.core import auth
from backend.core.two_factor_auth import get_2fa_system
from backend.core.audit_logger import get_audit_logger, AuditEventType
from backend.core import security_helpers
from datetime import timedelta

router = APIRouter()
audit_logger = get_audit_logger()


@router.post("/users/", response_model=user_schema.User)
def create_user(
    user: user_schema.UserCreate,
    db: Session = Depends(get_db),
    _admin: user_schema.User = Depends(auth.require_admin),
):
    """
    Create a user account. Administrators only.

    This was reachable anonymously until 2026-08-20, which let anyone on the
    network add accounts to an installed system. The first account is not
    created here — it comes from the first-run wizard (`POST /api/setup/initialize`),
    which refuses once an admin exists — so requiring admin here locks nobody out.
    """
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered")
    return crud.create_user(db=db, user=user)


@router.post("/token")
def login_for_access_token(
        request: Request,
        response: Response,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Check if user has 2FA enabled
    if user.two_factor_enabled:
        # Return error indicating 2FA is required
        # Frontend should then prompt for TOTP token and call /auth/login-2fa
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Two-factor authentication required. Use /auth/login-2fa endpoint.",
            headers={"X-Requires-2FA": "true"},
        )

    # v3.8.0: Create both access and refresh tokens
    device_info = request.headers.get("User-Agent", "Unknown")
    ip_address = request.client.host if request.client else None
    tokens = auth.create_tokens(db, user, device_info, ip_address)

    # Log successful login
    audit_logger.log_login(user.username, ip_address or "unknown", success=True)

    # Also hand the browser a cookie copy so <img>/<video> tags can load media.
    auth.set_media_auth_cookie(response, tokens["access_token"])

    return tokens


@router.post("/auth/login-2fa")
def login_with_2fa(
    http_request: Request,
    response: Response,
    request: twofa_schema.Login2FARequest,
    db: Session = Depends(get_db)
):
    """
    Login with two-factor authentication

    Args:
    - username: Username
    - password: Password
    - totp_token: 6-digit TOTP token (OR)
    - backup_code: Backup recovery code

    Returns:
    - access_token: JWT access token
    - refresh_token: JWT refresh token (v3.8.0)
    - token_type: Bearer
    - expires_in: Token expiration time in seconds
    """
    # Get client info
    device_info = http_request.headers.get("User-Agent", "Unknown")
    ip_address = http_request.client.host if http_request.client else None

    # Authenticate username and password
    user = auth.authenticate_user(db, request.username, request.password)
    if not user:
        audit_logger.log_login(request.username, ip_address or "unknown", success=False, reason="Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if 2FA is enabled
    if not user.two_factor_enabled:
        # User doesn't have 2FA - proceed with normal login
        # v3.8.0: Create both access and refresh tokens
        tokens = auth.create_tokens(db, user, device_info, ip_address)
        audit_logger.log_login(user.username, ip_address or "unknown", success=True)
        auth.set_media_auth_cookie(response, tokens["access_token"])
        tokens["requires_2fa"] = False
        return tokens

    # Check if account is locked due to failed 2FA attempts
    if security_helpers.is_account_locked(user):
        remaining_seconds = security_helpers.get_lockout_remaining_time(user)

        audit_logger.log_login(
            user.username,
            ip_address or "unknown",
            success=False,
            reason=f"account_locked_until_{user.account_locked_until.isoformat()}"
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is temporarily locked due to multiple failed verification attempts. "
                   f"Please try again in {remaining_seconds // 60} minutes."
        )

    # 2FA is enabled - verify TOTP token or backup code
    twofa = get_2fa_system()

    if request.totp_token:
        # Verify TOTP token
        is_valid = twofa.verify_token(user.totp_secret, request.totp_token)
        if not is_valid:
            # Record failed attempt and check for lockout
            lockout_result = security_helpers.record_failed_2fa_attempt(
                db=db,
                user=user,
                ip_address=ip_address or "unknown",
                reason="invalid_totp_login"
            )

            audit_logger.log_login(
                request.username,
                ip_address or "unknown",
                success=False,
                reason=f"invalid_2fa_token_remaining_{lockout_result.get('remaining_attempts', 0)}"
            )

            if lockout_result.get("locked"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Account locked due to multiple failed verification attempts. "
                           f"Locked for {lockout_result['lockout_duration_minutes']} minutes."
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid TOTP token. {lockout_result['remaining_attempts']} attempts remaining."
            )

    elif request.backup_code:
        # Verify backup code
        if not user.backup_codes:
            audit_logger.log_login(request.username, "unknown", success=False, reason="No backup codes")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No backup codes available"
            )

        # Load backup codes
        try:
            backup_codes = json.loads(user.backup_codes)
        except:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error loading backup codes"
            )

        # Check if backup code matches any hashed code
        code_found = False
        for i, hashed_code in enumerate(backup_codes):
            if bcrypt.checkpw(request.backup_code.encode(), hashed_code.encode()):
                code_found = True
                # Remove used backup code
                backup_codes.pop(i)
                user.backup_codes = json.dumps(backup_codes)
                db.commit()
                break

        if not code_found:
            # Record failed attempt for backup code
            lockout_result = security_helpers.record_failed_2fa_attempt(
                db=db,
                user=user,
                ip_address=ip_address or "unknown",
                reason="invalid_backup_code"
            )

            audit_logger.log_login(
                request.username,
                ip_address or "unknown",
                success=False,
                reason=f"invalid_backup_code_remaining_{lockout_result.get('remaining_attempts', 0)}"
            )

            if lockout_result.get("locked"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Account locked due to multiple failed verification attempts. "
                           f"Locked for {lockout_result['lockout_duration_minutes']} minutes."
                )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid backup code. {lockout_result['remaining_attempts']} attempts remaining."
            )

    else:
        # Neither TOTP token nor backup code provided
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either totp_token or backup_code must be provided"
        )

    # 2FA verified successfully - reset failed attempts counter
    security_helpers.record_successful_2fa_attempt(db, user, ip_address or "unknown")

    # Create token pair
    # v3.8.0: Create both access and refresh tokens
    tokens = auth.create_tokens(db, user, device_info, ip_address)

    # Log successful 2FA login
    audit_logger.log_login(user.username, ip_address or "unknown", success=True)

    auth.set_media_auth_cookie(response, tokens["access_token"])

    tokens["requires_2fa"] = False
    return tokens


@router.get("/users/me", response_model=user_schema.User)
def read_users_me(
    current_user: user_schema.User = Depends(
        auth.get_current_user)):
    return current_user


# ============================================================================
# REFRESH TOKEN ENDPOINTS (v3.8.0)
# ============================================================================


class RefreshTokenRequest(BaseModel):
    """
    The refresh token, in the request body.

    Declared as a model on purpose. `refresh_token: str` written directly in the
    signature is read by FastAPI as a QUERY parameter, so a client sending
    {"refresh_token": "..."} as JSON — which is what the browser client does, and
    what the docstring below has always described — was answered with 422. Every
    refresh and every revoke failed that way, from the first release.

    A refresh token also does not belong in a query string: those are logged by
    servers and proxies and kept in browser history.
    """
    refresh_token: str


@router.post("/token/refresh")
def refresh_token(
    http_request: Request,
    response: Response,
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Implements refresh token rotation - generates new refresh token
    and revokes the old one for security.

    Args:
        refresh_token: Refresh token string (in request body)

    Returns:
        New access_token, refresh_token, token_type, and expires_in

    Raises:
        HTTPException 401: If refresh token is invalid, expired, or revoked
    """
    # Get client info
    device_info = http_request.headers.get("User-Agent", "Unknown")
    ip_address = http_request.client.host if http_request.client else None

    # Refresh tokens using refresh token rotation
    tokens = auth.refresh_access_token(
        db, payload.refresh_token, device_info, ip_address)

    # Refresh the cookie too, or media requests start failing 30 minutes into a
    # session that the client believes is still valid.
    auth.set_media_auth_cookie(response, tokens["access_token"])

    return tokens


@router.post("/token/revoke")
def revoke_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_user)
):
    """
    Revoke a refresh token (logout from single device).

    Args:
        refresh_token: Refresh token string to revoke

    Returns:
        Success message

    Raises:
        HTTPException 404: If token not found
    """
    success = crud.revoke_refresh_token(db, payload.refresh_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )

    # Log token revocation
    audit_logger.log_event(
        event_type=AuditEventType.LOGOUT,
        username=current_user.username,
        ip_address="unknown",
        details={"single_device": True}
    )

    return {"message": "Refresh token revoked successfully"}


@router.post("/token/revoke-all")
def revoke_all_tokens(
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_user)
):
    """
    Revoke all refresh tokens for current user (logout from all devices).

    This is useful when:
    - User suspects their account has been compromised
    - User wants to logout from all devices at once
    - Password has been changed

    Returns:
        Number of tokens revoked
    """
    count = crud.revoke_all_user_tokens(db, current_user.id)

    # Log mass token revocation
    audit_logger.log_event(
        event_type=AuditEventType.LOGOUT,
        username=current_user.username,
        ip_address="unknown",
        details={"all_devices": True, "tokens_revoked": count}
    )

    return {
        "message": f"All refresh tokens revoked successfully",
        "tokens_revoked": count
    }


# ============================================================================
# PASSWORD RESET WITH 2FA VERIFICATION
# ============================================================================


@router.post("/auth/check-2fa-status", response_model=reset_schema.Check2FAStatusResponse)
def check_2fa_status_for_reset(
    request: reset_schema.Check2FAStatusRequest,
    db: Session = Depends(get_db)
):
    """
    Check if a user has 2FA enabled (for password reset flow).

    This endpoint does NOT require authentication - it's used during
    the forgot password flow to determine if password reset is allowed.

    Security: This only reveals IF 2FA is enabled, not the TOTP secret.
    Password reset still requires valid TOTP token to proceed.

    Args:
        username: Username to check

    Returns:
        - username: The username checked
        - two_factor_enabled: Whether 2FA is enabled
        - message: User-friendly message
    """
    # Get user from database
    user = crud.get_user_by_username(db, request.username)

    if not user:
        # Don't reveal if user exists - generic message
        return reset_schema.Check2FAStatusResponse(
            username=request.username,
            two_factor_enabled=False,
            message="Password reset is only available for users with Two-Factor Authentication enabled."
        )

    if not user.two_factor_enabled:
        return reset_schema.Check2FAStatusResponse(
            username=request.username,
            two_factor_enabled=False,
            message="Password reset requires Two-Factor Authentication. Please contact an administrator to reset your password."
        )

    return reset_schema.Check2FAStatusResponse(
        username=request.username,
        two_factor_enabled=True,
        message="Two-Factor Authentication is enabled. You can reset your password using your authenticator app."
    )


@router.post("/auth/reset-password", response_model=reset_schema.PasswordResetResponse)
def reset_password_with_2fa(
    http_request: Request,
    request: reset_schema.PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password with 2FA verification.

    This endpoint does NOT require authentication - it's used when users
    have forgotten their password but still have access to their 2FA device.

    Security measures:
    - Only works if user has 2FA enabled
    - Requires valid TOTP code from authenticator app
    - Logs all attempts for auditing
    - Revokes all existing refresh tokens after password change

    Args:
        username: Username to reset password for
        totp_code: 6-digit TOTP code from authenticator app
        new_password: New password (minimum 4 characters)

    Returns:
        - success: Whether password was reset successfully
        - message: User-friendly message
    """
    # Get client IP for logging
    ip_address = http_request.client.host if http_request.client else "unknown"

    # Log password reset attempt
    audit_logger.log_event(
        event_type=AuditEventType.PASSWORD_RESET_ATTEMPTED,
        user=request.username,
        ip_address=ip_address,
        success=True,
        details={"method": "2fa"}
    )

    # Get user from database
    user = crud.get_user_by_username(db, request.username)

    if not user:
        # Log failed attempt (user not found)
        audit_logger.log_event(
            event_type=AuditEventType.PASSWORD_RESET_FAILED,
            user=request.username,
            ip_address=ip_address,
            success=False,
            details={"reason": "user_not_found"}
        )

        # Generic error message (don't reveal if user exists)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or Two-Factor Authentication not enabled"
        )

    # Check if account is locked due to failed 2FA attempts
    if security_helpers.is_account_locked(user):
        remaining_seconds = security_helpers.get_lockout_remaining_time(user)

        audit_logger.log_event(
            event_type=AuditEventType.PASSWORD_RESET_FAILED,
            user=request.username,
            ip_address=ip_address,
            success=False,
            details={
                "reason": "account_locked",
                "locked_until": user.account_locked_until.isoformat(),
                "remaining_seconds": remaining_seconds
            }
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is temporarily locked due to multiple failed verification attempts. "
                   f"Please try again in {remaining_seconds // 60} minutes."
        )

    # Check if user has 2FA enabled
    if not user.two_factor_enabled or not user.totp_secret:
        # Log failed attempt (2FA not enabled)
        audit_logger.log_event(
            event_type=AuditEventType.PASSWORD_RESET_FAILED,
            user=request.username,
            ip_address=ip_address,
            success=False,
            details={"reason": "2fa_not_enabled"}
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password reset is only available for users with Two-Factor Authentication enabled"
        )

    # Verify TOTP token
    twofa = get_2fa_system()
    is_valid = twofa.verify_token(user.totp_secret, request.totp_code)

    if not is_valid:
        # Record failed 2FA attempt and check for lockout
        lockout_result = security_helpers.record_failed_2fa_attempt(
            db=db,
            user=user,
            ip_address=ip_address,
            reason="invalid_totp_password_reset"
        )

        # Log failed password reset
        audit_logger.log_event(
            event_type=AuditEventType.PASSWORD_RESET_FAILED,
            user=request.username,
            ip_address=ip_address,
            success=False,
            details={
                "reason": "invalid_totp",
                "remaining_attempts": lockout_result.get("remaining_attempts", 0),
                "locked": lockout_result.get("locked", False)
            }
        )

        if lockout_result.get("locked"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked due to multiple failed verification attempts. "
                       f"Locked for {lockout_result['lockout_duration_minutes']} minutes."
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Two-Factor Authentication code. "
                   f"{lockout_result['remaining_attempts']} attempts remaining."
        )

    # TOTP verified successfully - reset failed attempts and update password
    security_helpers.record_successful_2fa_attempt(db, user, ip_address)

    hashed_password = bcrypt.hashpw(request.new_password.encode(), bcrypt.gensalt()).decode()
    user.hashed_password = hashed_password

    # Revoke all existing refresh tokens (logout from all devices for security)
    tokens_revoked = crud.revoke_all_user_tokens(db, user.id)

    db.commit()

    # Log successful password reset
    audit_logger.log_event(
        event_type=AuditEventType.PASSWORD_RESET_SUCCESS,
        user=request.username,
        ip_address=ip_address,
        success=True,
        details={"method": "2fa_reset", "tokens_revoked": tokens_revoked}
    )

    return reset_schema.PasswordResetResponse(
        success=True,
        message="Password reset successfully. Please login with your new password."
    )


# ============================================================================
# USER MANAGEMENT API (v3.11.1) - Full CRUD with preferences
# ============================================================================

from backend.database import models
from datetime import datetime
from typing import List, Optional


@router.get("/users/", response_model=user_schema.UserListResponse)
async def list_users(
    page: int = 1,
    page_size: int = 50,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    List all users (admin only for full list, viewers see only themselves).
    
    Returns:
        Paginated list of users with basic info
    """
    # Build query
    query = db.query(models.User)
    
    # Non-admins only see themselves
    if current_user.role != "admin":
        query = query.filter(models.User.id == current_user.id)
    elif not include_inactive:
        query = query.filter(models.User.is_active == True)
    
    # Get total count
    total = query.count()
    
    # Paginate
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # Convert to response
    user_list = []
    for user in users:
        user_list.append(user_schema.User(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            role=user.role,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            face_profile_name=user.face_profile_name,
            two_factor_enabled=user.two_factor_enabled,
            created_at=user.created_at,
            last_login=user.last_login,
            synced_from=user.synced_from,
            synced_at=user.synced_at,
            external_id=user.external_id
        ))
    
    return user_schema.UserListResponse(
        users=user_list,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/users/{user_id}", response_model=user_schema.UserWithPreferences)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Get user details with preferences.
    
    Users can only view their own profile unless they are admin.
    """
    # Check permissions
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own profile"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get preferences
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    return user_schema.UserWithPreferences(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        face_profile_name=user.face_profile_name,
        two_factor_enabled=user.two_factor_enabled,
        created_at=user.created_at,
        last_login=user.last_login,
        synced_from=user.synced_from,
        synced_at=user.synced_at,
        external_id=user.external_id,
        preferences=_preferences_to_schema(prefs) if prefs else None
    )


@router.put("/users/{user_id}", response_model=user_schema.User)
async def update_user(
    user_id: int,
    user_update: user_schema.UserUpdate,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Update user profile.
    
    Users can update their own profile. Admins can update anyone.
    """
    # Check permissions
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields that were provided
    update_data = user_update.model_dump(exclude_unset=True)
    
    # Non-admins cannot deactivate themselves or change certain fields
    if current_user.role != "admin":
        update_data.pop("is_active", None)
    
    # Check username uniqueness if being changed
    if "username" in update_data and update_data["username"] != user.username:
        existing = crud.get_user_by_username(db, update_data["username"])
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    # Log profile update
    audit_logger.log_event(
        event_type=AuditEventType.PROFILE_UPDATED,
        username=current_user.username,
        ip_address="unknown",
        details={"updated_user_id": user_id, "fields": list(update_data.keys())}
    )
    
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Delete a user (admin only).
    
    Note: This also deletes user preferences and revokes all tokens.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users"
        )
    
    # Prevent self-deletion
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    username = user.username
    
    # Revoke all tokens first
    crud.revoke_all_user_tokens(db, user_id)
    
    # Delete user (cascades to preferences and tokens)
    db.delete(user)
    db.commit()
    
    # Log deletion
    audit_logger.log_event(
        event_type=AuditEventType.USER_DELETED,
        username=current_user.username,
        ip_address="unknown",
        details={"deleted_user": username, "deleted_user_id": user_id}
    )
    
    return {"message": f"User '{username}' deleted successfully"}


@router.patch("/users/{user_id}/role", response_model=user_schema.User)
async def change_user_role(
    user_id: int,
    role_change: user_schema.UserRoleChange,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Change user role (admin only).
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles"
        )
    
    # Prevent demoting yourself
    if current_user.id == user_id and role_change.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot demote yourself from admin"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_role = user.role
    user.role = role_change.role.value
    db.commit()
    db.refresh(user)
    
    # Log role change
    audit_logger.log_event(
        event_type=AuditEventType.ROLE_CHANGED,
        username=current_user.username,
        ip_address="unknown",
        details={
            "target_user": user.username,
            "old_role": old_role,
            "new_role": role_change.role.value
        }
    )
    
    return user


@router.post("/users/{user_id}/password", response_model=dict)
async def change_password(
    user_id: int,
    password_change: user_schema.UserPasswordChange,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Change user password.
    
    Users can only change their own password. Requires current password.
    """
    # Users can only change their own password
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own password"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not auth.verify_password(password_change.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Update password
    user.hashed_password = auth.hash_password(password_change.new_password)
    
    # Revoke all refresh tokens for security
    tokens_revoked = crud.revoke_all_user_tokens(db, user_id)
    
    db.commit()
    
    # Log password change
    audit_logger.log_event(
        event_type=AuditEventType.PASSWORD_CHANGED,
        username=current_user.username,
        ip_address="unknown",
        details={"tokens_revoked": tokens_revoked}
    )
    
    return {"message": "Password changed successfully", "tokens_revoked": tokens_revoked}


# ============================================================================
# USER PREFERENCES API (v3.11.1)
# ============================================================================


def _preferences_to_schema(prefs: models.UserPreferences) -> user_schema.UserPreferences:
    """Convert database preferences to schema with JSON parsing."""
    import json
    
    def parse_json(json_str: str, default):
        if not json_str:
            return default
        try:
            return json.loads(json_str)
        except:
            return default
    
    return user_schema.UserPreferences(
        id=prefs.id,
        user_id=prefs.user_id,
        notification_types=user_schema.NotificationTypes(**parse_json(prefs.notification_types, {})),
        notification_channels=user_schema.NotificationChannels(**parse_json(prefs.notification_channels, {})),
        quiet_hours=user_schema.QuietHours(**parse_json(prefs.quiet_hours, {})),
        camera_access=parse_json(prefs.camera_access, None),
        face_associations=parse_json(prefs.face_associations, None),
        ui_preferences=user_schema.UIPreferences(**parse_json(prefs.ui_preferences, {})),
        dashboard_preferences=user_schema.DashboardPreferences(**parse_json(prefs.dashboard_preferences, {})),
        ecosystem_preferences=user_schema.EcosystemPreferences(**parse_json(prefs.ecosystem_preferences, {})),
        presence_settings=user_schema.PresenceSettings(**parse_json(prefs.presence_settings, {})),
        automation_preferences=user_schema.AutomationPreferences(**parse_json(prefs.automation_preferences, {})),
        push_token=prefs.push_token,
        push_platform=prefs.push_platform,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at
    )


@router.get("/users/{user_id}/preferences", response_model=user_schema.UserPreferences)
async def get_user_preferences(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Get user preferences.
    
    Users can only view their own preferences unless admin.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own preferences"
        )
    
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    if not prefs:
        # Create default preferences
        prefs = models.UserPreferences(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    return _preferences_to_schema(prefs)


@router.put("/users/{user_id}/preferences", response_model=user_schema.UserPreferences)
async def update_user_preferences(
    user_id: int,
    prefs_update: user_schema.UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Update user preferences.
    
    Users can only update their own preferences unless admin.
    """
    import json
    
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own preferences"
        )
    
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    if not prefs:
        prefs = models.UserPreferences(user_id=user_id)
        db.add(prefs)
    
    # Update each preference section if provided
    if prefs_update.notification_types:
        prefs.notification_types = json.dumps(prefs_update.notification_types.model_dump())
    if prefs_update.notification_channels:
        prefs.notification_channels = json.dumps(prefs_update.notification_channels.model_dump())
    if prefs_update.quiet_hours:
        prefs.quiet_hours = json.dumps(prefs_update.quiet_hours.model_dump())
    if prefs_update.camera_access is not None:
        prefs.camera_access = json.dumps(prefs_update.camera_access)
    if prefs_update.face_associations is not None:
        prefs.face_associations = json.dumps(prefs_update.face_associations)
    if prefs_update.ui_preferences:
        prefs.ui_preferences = json.dumps(prefs_update.ui_preferences.model_dump())
    if prefs_update.dashboard_preferences:
        prefs.dashboard_preferences = json.dumps(prefs_update.dashboard_preferences.model_dump())
    if prefs_update.ecosystem_preferences:
        prefs.ecosystem_preferences = json.dumps(prefs_update.ecosystem_preferences.model_dump())
    if prefs_update.presence_settings:
        prefs.presence_settings = json.dumps(prefs_update.presence_settings.model_dump())
    if prefs_update.automation_preferences:
        prefs.automation_preferences = json.dumps(prefs_update.automation_preferences.model_dump())
    
    prefs.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prefs)
    
    return _preferences_to_schema(prefs)


# ============================================================================
# FACE PROFILE LINKING (v3.11.1)
# ============================================================================


@router.post("/users/{user_id}/link-face", response_model=user_schema.LinkFaceProfileResponse)
async def link_face_profile(
    user_id: int,
    request: user_schema.LinkFaceProfileRequest,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Link a user account to a face recognition profile.
    
    This allows:
    - User to be automatically detected when their face is seen
    - Notifications to be routed to the correct user
    - Home presence detection for automations
    
    Users can only link their own profile unless admin.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only link your own face profile"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if face profile exists
    from backend.core.paths import paths
    import os
    face_dir = paths.faces_dir / request.face_profile_name
    face_exists = face_dir.exists() and any(face_dir.iterdir())
    
    # Link the face profile
    user.face_profile_name = request.face_profile_name
    db.commit()
    
    # Log the linking
    audit_logger.log_event(
        event_type=AuditEventType.FACE_LINKED,
        username=current_user.username,
        ip_address="unknown",
        details={
            "target_user_id": user_id,
            "face_profile": request.face_profile_name,
            "face_exists": face_exists
        }
    )
    
    return user_schema.LinkFaceProfileResponse(
        user_id=user_id,
        username=user.username,
        face_profile_name=request.face_profile_name,
        linked_at=datetime.utcnow(),
        face_exists=face_exists
    )


@router.delete("/users/{user_id}/link-face")
async def unlink_face_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Unlink a user account from their face profile.
    """
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only unlink your own face profile"
        )
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    old_profile = user.face_profile_name
    user.face_profile_name = None
    db.commit()
    
    return {"message": f"Face profile '{old_profile}' unlinked successfully"}


# ============================================================================
# CAMERA PERMISSIONS (v3.11.1)
# ============================================================================


@router.get("/users/{user_id}/camera-permissions", response_model=user_schema.CameraPermissions)
async def get_camera_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Get camera access permissions for a user.
    """
    import json
    
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own camera permissions"
        )
    
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    camera_ids = None
    if prefs and prefs.camera_access:
        try:
            camera_ids = json.loads(prefs.camera_access)
        except:
            pass
    
    # Admins and users can control, viewers can only view
    user = db.query(models.User).filter(models.User.id == user_id).first()
    can_control = user.role in ["admin", "user"] if user else False
    can_record = user.role == "admin" if user else False
    
    return user_schema.CameraPermissions(
        user_id=user_id,
        camera_ids=camera_ids,
        can_view=True,
        can_control=can_control,
        can_record=can_record
    )


@router.put("/users/{user_id}/camera-permissions", response_model=user_schema.CameraPermissions)
async def update_camera_permissions(
    user_id: int,
    permissions: user_schema.UpdateCameraPermissions,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Update camera access permissions for a user (admin only).
    """
    import json
    
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update camera permissions"
        )
    
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    if not prefs:
        prefs = models.UserPreferences(user_id=user_id)
        db.add(prefs)
    
    if permissions.camera_ids is not None:
        prefs.camera_access = json.dumps(permissions.camera_ids) if permissions.camera_ids else None
    
    prefs.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prefs)
    
    camera_ids = None
    if prefs.camera_access:
        try:
            camera_ids = json.loads(prefs.camera_access)
        except:
            pass
    
    return user_schema.CameraPermissions(
        user_id=user_id,
        camera_ids=camera_ids,
        can_view=permissions.can_view if permissions.can_view is not None else True,
        can_control=permissions.can_control if permissions.can_control is not None else False,
        can_record=permissions.can_record if permissions.can_record is not None else False
    )


# ============================================================================
# ECOSYSTEM USER SYNC (v3.11.1) - Enhanced
# ============================================================================


@router.post("/users/sync", response_model=user_schema.UserSyncResponse)
async def sync_user_from_ecosystem(
    request: user_schema.UserSyncRequest,
    db: Session = Depends(get_db),
    _admin: user_schema.User = Depends(auth.require_admin),
):
    """
    Create or update a user synced from a companion app. Administrators only.

    Used by the MagicMirror ecosystem module to sync users bidirectionally.

    This endpoint was unauthenticated until 2026-08-20 and accepted a
    caller-supplied `role`, so an anonymous caller on the network could create an
    administrator account, or take the update branch below to overwrite an
    existing administrator's email address and redirect their alerting.

    Two things changed. Authentication is now required, and the requested role is
    ignored — see below. Verified before locking it down: appEcosystem does not
    call this endpoint (no reference to /users/sync or /api/users anywhere in
    it), so no companion app breaks.
    """
    # Check if user already exists by external_id or username
    existing = None
    
    if request.external_id:
        existing = db.query(models.User).filter(
            models.User.external_id == request.external_id,
            models.User.synced_from == request.source_app
        ).first()
    
    if not existing:
        existing = crud.get_user_by_username(db, request.username)
    
    if existing:
        # Update existing user with sync info
        existing.synced_from = request.source_app
        existing.synced_at = datetime.utcnow()
        existing.external_id = request.external_id
        
        if request.display_name:
            existing.display_name = request.display_name
        if request.email:
            existing.email = request.email
        if request.face_profile_name:
            existing.face_profile_name = request.face_profile_name
        
        db.commit()
        
        return user_schema.UserSyncResponse(
            user_id=existing.id,
            username=existing.username,
            action="updated",
            synced_at=datetime.utcnow()
        )
    
    # Create new user
    #
    # The role is deliberately NOT taken from the request. A sync is an assertion
    # that a person exists in a companion app; it is not an authorization
    # decision, and letting the caller name the role made this endpoint a
    # privilege-escalation primitive. A synced account starts as a viewer and is
    # promoted through the normal user routes, where the change is audited.
    import secrets
    new_user = models.User(
        username=request.username,
        email=request.email,
        display_name=request.display_name,
        hashed_password=auth.hash_password(secrets.token_urlsafe(32)),  # Random password
        role=user_schema.UserRole.viewer.value,
        face_profile_name=request.face_profile_name,
        synced_from=request.source_app,
        synced_at=datetime.utcnow(),
        external_id=request.external_id,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create default preferences if provided
    if request.preferences:
        await update_user_preferences(new_user.id, request.preferences, db, new_user)
    
    return user_schema.UserSyncResponse(
        user_id=new_user.id,
        username=new_user.username,
        action="created",
        synced_at=datetime.utcnow()
    )


@router.post("/users/sync/bulk", response_model=user_schema.UserBulkSyncResponse)
async def bulk_sync_users(
    request: user_schema.UserBulkSyncRequest,
    db: Session = Depends(get_db),
    _admin: user_schema.User = Depends(auth.require_admin),
):
    """
    Bulk sync users from a companion app. Administrators only.

    Efficiently syncs multiple users in a single request. This delegates to
    sync_user_from_ecosystem for each entry, so it carried exactly the same
    anonymous privilege-escalation exposure and is closed the same way.
    """
    results = []
    errors = []
    created_count = 0
    updated_count = 0
    
    for user_req in request.users:
        try:
            # Override source_app with the bulk request's source
            user_req.source_app = request.source_app
            
            result = await sync_user_from_ecosystem(user_req, db)
            results.append(result)
            
            if result.action == "created":
                created_count += 1
            else:
                updated_count += 1
                
        except HTTPException as e:
            errors.append(f"User '{user_req.username}': {e.detail}")
        except Exception as e:
            errors.append(f"User '{user_req.username}': {str(e)}")
    
    return user_schema.UserBulkSyncResponse(
        synced_count=len(results),
        created_count=created_count,
        updated_count=updated_count,
        errors=errors,
        users=results
    )


# ============================================================================
# PUSH NOTIFICATION REGISTRATION (v3.11.1)
# ============================================================================


@router.post("/users/{user_id}/push-token")
async def register_push_token(
    user_id: int,
    token: str,
    platform: str,  # "ios" or "android"
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(auth.get_current_active_user)
):
    """
    Register a push notification token for a user's device.
    """
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register push tokens for yourself"
        )
    
    prefs = db.query(models.UserPreferences).filter(
        models.UserPreferences.user_id == user_id
    ).first()
    
    if not prefs:
        prefs = models.UserPreferences(user_id=user_id)
        db.add(prefs)
    
    prefs.push_token = token
    prefs.push_platform = platform
    prefs.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Push token registered successfully", "platform": platform}
