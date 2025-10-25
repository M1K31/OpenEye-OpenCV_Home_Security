# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Two-Factor Authentication API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import json
import bcrypt

from backend.core.auth import get_current_active_user, get_db
from backend.core.two_factor_auth import get_2fa_system
from backend.core.security import verify_password
from backend.api.schemas import user as user_schema
from backend.api.schemas import two_factor as twofa_schema
from backend.database import crud
from backend.database.models import User
from backend.core.audit_logger import get_audit_logger, AuditEventType

router = APIRouter()
audit_logger = get_audit_logger()


@router.post("/enable", response_model=twofa_schema.Enable2FAResponse)
async def enable_2fa(
    current_user: user_schema.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Enable two-factor authentication for the current user

    Returns:
    - TOTP secret key
    - QR code for authenticator app
    - 10 backup codes for recovery
    """
    # Check if 2FA is already enabled
    db_user = crud.get_user_by_username(db, current_user.username)
    if db_user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication is already enabled"
        )

    # Generate 2FA credentials
    twofa = get_2fa_system()
    secret = twofa.generate_secret()
    qr_code = twofa.generate_qr_code(current_user.username, secret)
    backup_codes = twofa.get_backup_codes(count=10)

    # Store secret (temporarily - will be confirmed on verification)
    # Hash backup codes before storing
    hashed_backup_codes = [
        bcrypt.hashpw(code.encode(), bcrypt.gensalt()).decode()
        for code in backup_codes
    ]

    # Update user with temporary 2FA data (not enabled yet)
    db_user.totp_secret = secret
    db_user.backup_codes = json.dumps(hashed_backup_codes)
    db.commit()

    # Log event
    audit_logger.log_event(
        AuditEventType.USER_UPDATED,
        user=current_user.username,
        resource=current_user.username,
        details={"action": "2fa_enrollment_initiated"}
    )

    return twofa_schema.Enable2FAResponse(
        secret=secret,
        qr_code=qr_code,
        backup_codes=backup_codes
    )


@router.post("/verify", response_model=twofa_schema.Verify2FAResponse)
async def verify_2fa(
    request: twofa_schema.Verify2FARequest,
    current_user: user_schema.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Verify TOTP token and activate two-factor authentication

    Args:
    - token: 6-digit TOTP token from authenticator app

    Returns:
    - Success status
    - Confirmation message
    """
    db_user = crud.get_user_by_username(db, current_user.username)

    # Check if user has initiated 2FA enrollment
    if not db_user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor authentication has not been initiated. Call /enable first."
        )

    # Verify the token
    twofa = get_2fa_system()
    is_valid = twofa.verify_token(db_user.totp_secret, request.token)

    if not is_valid:
        # Log failed verification
        audit_logger.log_event(
            AuditEventType.USER_UPDATED,
            user=current_user.username,
            resource=current_user.username,
            success=False,
            details={"action": "2fa_verification_failed"}
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP token. Please try again."
        )

    # Token is valid - enable 2FA
    db_user.two_factor_enabled = True
    db_user.two_factor_enrolled_at = datetime.utcnow()
    db.commit()

    # Log successful enablement
    audit_logger.log_event(
        AuditEventType.USER_UPDATED,
        user=current_user.username,
        resource=current_user.username,
        details={"action": "2fa_enabled"}
    )

    return twofa_schema.Verify2FAResponse(
        success=True,
        message="Two-factor authentication enabled successfully",
        two_factor_enabled=True
    )


@router.post("/disable", response_model=twofa_schema.Disable2FAResponse)
async def disable_2fa(
    request: twofa_schema.Disable2FARequest,
    current_user: user_schema.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Disable two-factor authentication

    Requires user's password for confirmation

    Args:
    - password: User's password for confirmation

    Returns:
    - Success status
    - Confirmation message
    """
    db_user = crud.get_user_by_username(db, current_user.username)

    # Verify password
    if not verify_password(request.password, db_user.hashed_password):
        # Log failed attempt
        audit_logger.log_event(
            AuditEventType.USER_UPDATED,
            user=current_user.username,
            resource=current_user.username,
            success=False,
            details={"action": "2fa_disable_failed", "reason": "invalid_password"}
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password"
        )

    # Disable 2FA
    db_user.two_factor_enabled = False
    db_user.totp_secret = None
    db_user.backup_codes = None
    db_user.two_factor_enrolled_at = None
    db.commit()

    # Log successful disable
    audit_logger.log_event(
        AuditEventType.USER_UPDATED,
        user=current_user.username,
        resource=current_user.username,
        details={"action": "2fa_disabled"}
    )

    return twofa_schema.Disable2FAResponse(
        success=True,
        message="Two-factor authentication disabled",
        two_factor_enabled=False
    )


@router.get("/status", response_model=twofa_schema.TwoFactorStatus)
async def get_2fa_status(
    current_user: user_schema.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's 2FA status

    Returns:
    - Whether 2FA is enabled
    - Enrollment date
    - Number of remaining backup codes
    """
    db_user = crud.get_user_by_username(db, current_user.username)

    # Count remaining backup codes
    backup_codes_remaining = None
    if db_user.backup_codes:
        try:
            codes = json.loads(db_user.backup_codes)
            backup_codes_remaining = len(codes)
        except:
            pass

    return twofa_schema.TwoFactorStatus(
        two_factor_enabled=db_user.two_factor_enabled or False,
        enrolled_at=db_user.two_factor_enrolled_at,
        backup_codes_remaining=backup_codes_remaining
    )
