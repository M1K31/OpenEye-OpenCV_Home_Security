# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
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
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered")
    return crud.create_user(db=db, user=user)


@router.post("/token")
def login_for_access_token(
        request: Request,
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

    return tokens


@router.post("/auth/login-2fa")
def login_with_2fa(
    http_request: Request,
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


@router.post("/token/refresh")
def refresh_token(
    http_request: Request,
    refresh_token: str,
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
    tokens = auth.refresh_access_token(db, refresh_token, device_info, ip_address)

    return tokens


@router.post("/token/revoke")
def revoke_token(
    refresh_token: str,
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
    success = crud.revoke_refresh_token(db, refresh_token)

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
