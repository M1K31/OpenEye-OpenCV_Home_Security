# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Enhanced Audit Logging System
Tracks security-sensitive operations for compliance and forensics
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events"""
    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET_ATTEMPTED = "password_reset_attempted"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    PASSWORD_RESET_FAILED = "password_reset_failed"

    # 2FA events
    TWO_FA_ENABLED = "2fa_enabled"
    TWO_FA_DISABLED = "2fa_disabled"
    TWO_FA_VERIFY_SUCCESS = "2fa_verify_success"
    TWO_FA_VERIFY_FAILED = "2fa_verify_failed"
    TWO_FA_ACCOUNT_LOCKED = "2fa_account_locked"
    TWO_FA_ACCOUNT_UNLOCKED = "2fa_account_unlocked"

    # Authorization events
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"

    # User management
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"
    USER_UPDATED = "user_updated"
    USER_DISABLED = "user_disabled"
    USER_ENABLED = "user_enabled"

    # Camera operations
    CAMERA_ADDED = "camera_added"
    CAMERA_REMOVED = "camera_removed"
    CAMERA_STARTED = "camera_started"
    CAMERA_STOPPED = "camera_stopped"
    CAMERA_UPDATED = "camera_updated"

    # Face recognition
    FACE_UPLOADED = "face_uploaded"
    FACE_DELETED = "face_deleted"
    FACE_IDENTIFIED = "face_identified"

    # Recording operations
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    RECORDING_DELETED = "recording_deleted"
    RECORDING_DOWNLOADED = "recording_downloaded"

    # Alert operations
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_DISMISSED = "alert_dismissed"
    ALERT_CONFIG_CHANGED = "alert_config_changed"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIG_CHANGED = "config_changed"

    # Security events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    CSRF_VALIDATION_FAILED = "csrf_validation_failed"
    INVALID_TOKEN = "invalid_token"


class AuditLogger:
    """
    Centralized audit logging system
    Logs security-sensitive operations to structured log files
    """

    def __init__(self, log_dir: str = "logs/audit"):
        """
        Initialize audit logger

        Args:
            log_dir: Directory for audit log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create separate log file for audit events
        self.audit_log_path = self.log_dir / f"audit_{datetime.now().strftime('%Y%m')}.jsonl"

        logger.info(f"Audit logger initialized: {self.audit_log_path}")

    def log_event(
        self,
        event_type: AuditEventType,
        user: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        resource: Optional[str] = None
    ):
        """
        Log an audit event

        Args:
            event_type: Type of event
            user: Username (if applicable)
            ip_address: Client IP address
            success: Whether operation succeeded
            details: Additional event details
            resource: Resource affected (camera ID, user ID, etc.)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type.value,
            "user": user,
            "ip_address": ip_address,
            "success": success,
            "resource": resource,
            "details": details or {}
        }

        # Write to audit log file (JSONL format)
        try:
            with open(self.audit_log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        # Also log to standard logger for real-time monitoring
        log_level = logging.INFO if success else logging.WARNING
        log_message = (
            f"[AUDIT] {event_type.value} | "
            f"user={user} | ip={ip_address} | "
            f"success={success} | resource={resource}"
        )
        logger.log(log_level, log_message)

    # Convenience methods for common events

    def log_login(self, username: str, ip_address: str, success: bool, reason: Optional[str] = None):
        """Log login attempt"""
        event_type = AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED
        details = {"reason": reason} if reason else None
        self.log_event(event_type, user=username, ip_address=ip_address, success=success, details=details)

    def log_logout(self, username: str, ip_address: str):
        """Log logout"""
        self.log_event(AuditEventType.LOGOUT, user=username, ip_address=ip_address)

    def log_access_denied(self, username: str, ip_address: str, resource: str, required_role: str):
        """Log access denied"""
        self.log_event(
            AuditEventType.ACCESS_DENIED,
            user=username,
            ip_address=ip_address,
            success=False,
            resource=resource,
            details={"required_role": required_role}
        )

    def log_user_created(self, admin_user: str, new_user: str, ip_address: str, role: str):
        """Log user creation"""
        self.log_event(
            AuditEventType.USER_CREATED,
            user=admin_user,
            ip_address=ip_address,
            resource=new_user,
            details={"role": role}
        )

    def log_camera_operation(
        self,
        operation: AuditEventType,
        camera_id: str,
        user: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log camera-related operation"""
        self.log_event(operation, user=user, ip_address=ip_address, resource=camera_id, details=details)

    def log_security_event(
        self,
        event_type: AuditEventType,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security-related event"""
        self.log_event(event_type, ip_address=ip_address, success=False, details=details)


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
