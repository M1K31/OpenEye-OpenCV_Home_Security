# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Security Helper Functions
Provides centralized security logic for account lockout, 2FA verification, etc.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.database import models
from backend.core.audit_logger import get_audit_logger, AuditEventType
from backend.core.config import (
    MAX_2FA_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
    ATTEMPT_RESET_MINUTES,
)
import logging

logger = logging.getLogger(__name__)
audit_logger = get_audit_logger()


def is_account_locked(user: models.User) -> bool:
    """
    Check if user account is currently locked due to failed 2FA attempts

    Args:
        user: User model instance

    Returns:
        True if account is locked, False otherwise
    """
    if not user.account_locked_until:
        return False

    # Check if lockout period has expired
    if datetime.utcnow() >= user.account_locked_until:
        return False

    return True


def get_lockout_remaining_time(user: models.User) -> int:
    """
    Get remaining lockout time in seconds

    Args:
        user: User model instance

    Returns:
        Remaining seconds, or 0 if not locked
    """
    if not is_account_locked(user):
        return 0

    remaining = (user.account_locked_until - datetime.utcnow()).total_seconds()
    return max(0, int(remaining))


def record_failed_2fa_attempt(
    db: Session,
    user: models.User,
    ip_address: str,
    reason: str = "invalid_code"
) -> dict:
    """
    Record a failed 2FA verification attempt and check if account should be locked

    Args:
        db: Database session
        user: User model instance
        ip_address: Client IP address
        reason: Failure reason (invalid_code, expired_code, etc.)

    Returns:
        dict with 'locked' (bool) and 'remaining_attempts' (int)
    """
    now = datetime.utcnow()

    # Reset attempts counter if last attempt was > 15 minutes ago
    if user.last_failed_2fa_attempt:
        time_since_last = (now - user.last_failed_2fa_attempt).total_seconds() / 60
        if time_since_last > ATTEMPT_RESET_MINUTES:
            user.failed_2fa_attempts = 0
            logger.info(f"Reset failed 2FA attempts for user {user.username} (inactive for {time_since_last:.1f} minutes)")

    # Increment failed attempts
    user.failed_2fa_attempts += 1
    user.last_failed_2fa_attempt = now

    # Log failed attempt
    audit_logger.log_event(
        AuditEventType.TWO_FA_VERIFY_FAILED,
        user=user.username,
        ip_address=ip_address,
        success=False,
        details={
            "reason": reason,
            "failed_attempts": user.failed_2fa_attempts,
            "max_attempts": MAX_2FA_ATTEMPTS
        }
    )

    # Check if account should be locked
    remaining_attempts = MAX_2FA_ATTEMPTS - user.failed_2fa_attempts

    if user.failed_2fa_attempts >= MAX_2FA_ATTEMPTS:
        # Lock the account
        user.account_locked_until = now + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        user.lockout_count += 1
        user.failed_2fa_attempts = 0  # Reset counter after locking

        logger.warning(
            f"Account locked for user {user.username} after {MAX_2FA_ATTEMPTS} failed 2FA attempts. "
            f"Locked until {user.account_locked_until}. Total lockouts: {user.lockout_count}"
        )

        # Log lockout event
        audit_logger.log_event(
            AuditEventType.TWO_FA_ACCOUNT_LOCKED,
            user=user.username,
            ip_address=ip_address,
            success=False,
            details={
                "locked_until": user.account_locked_until.isoformat(),
                "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
                "lockout_count": user.lockout_count
            }
        )

        db.commit()

        return {
            "locked": True,
            "locked_until": user.account_locked_until,
            "lockout_duration_minutes": LOCKOUT_DURATION_MINUTES,
            "remaining_attempts": 0
        }

    db.commit()

    return {
        "locked": False,
        "remaining_attempts": remaining_attempts
    }


def record_successful_2fa_attempt(
    db: Session,
    user: models.User,
    ip_address: str
):
    """
    Record a successful 2FA verification and reset failed attempts counter

    Args:
        db: Database session
        user: User model instance
        ip_address: Client IP address
    """
    # Reset failed attempts on successful verification
    user.failed_2fa_attempts = 0
    user.last_failed_2fa_attempt = None

    # Log successful verification
    audit_logger.log_event(
        AuditEventType.TWO_FA_VERIFY_SUCCESS,
        user=user.username,
        ip_address=ip_address,
        success=True
    )

    db.commit()

    logger.info(f"Successful 2FA verification for user {user.username}")


def unlock_account(
    db: Session,
    user: models.User,
    admin_user: str,
    ip_address: str
):
    """
    Manually unlock a user account (admin action)

    Args:
        db: Database session
        user: User model instance to unlock
        admin_user: Username of admin performing unlock
        ip_address: Admin's IP address
    """
    user.account_locked_until = None
    user.failed_2fa_attempts = 0
    user.last_failed_2fa_attempt = None

    # Log unlock event
    audit_logger.log_event(
        AuditEventType.TWO_FA_ACCOUNT_UNLOCKED,
        user=admin_user,
        ip_address=ip_address,
        success=True,
        resource=user.username,
        details={"manual_unlock": True}
    )

    db.commit()

    logger.info(f"Account unlocked for user {user.username} by admin {admin_user}")


def get_account_security_status(user: models.User) -> dict:
    """
    Get comprehensive security status for a user account

    Args:
        user: User model instance

    Returns:
        dict with security status information
    """
    locked = is_account_locked(user)

    return {
        "is_locked": locked,
        "locked_until": user.account_locked_until.isoformat() if user.account_locked_until else None,
        "lockout_remaining_seconds": get_lockout_remaining_time(user) if locked else 0,
        "failed_2fa_attempts": user.failed_2fa_attempts,
        "max_2fa_attempts": MAX_2FA_ATTEMPTS,
        "remaining_attempts": MAX_2FA_ATTEMPTS - user.failed_2fa_attempts if not locked else 0,
        "last_failed_attempt": user.last_failed_2fa_attempt.isoformat() if user.last_failed_2fa_attempt else None,
        "total_lockouts": user.lockout_count,
        "two_factor_enabled": user.two_factor_enabled
    }
