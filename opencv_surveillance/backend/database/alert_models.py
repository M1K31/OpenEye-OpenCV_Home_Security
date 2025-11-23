# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Database models for the notification and alert system
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float, Text
from datetime import datetime
from backend.database.session import Base
from cryptography.fernet import Fernet
import os
import base64

# SAFETY CHECK: Verify Base consistency
from backend.database.models import Base as ModelsBase

assert Base is ModelsBase, "Base classes must be identical!"


class AlertConfiguration(Base):
    """
    Stores user alert preferences and notification channel settings
    """

    __tablename__ = "alert_configurations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # Links to User model

    # Alert Types - Enable/disable specific alerts
    motion_alerts_enabled = Column(Boolean, default=True)
    face_recognition_alerts_enabled = Column(Boolean, default=True)
    unknown_face_alerts_enabled = Column(Boolean, default=True)
    recording_alerts_enabled = Column(Boolean, default=False)

    # v3.10.0: Object Detection Alerts
    object_detection_alerts_enabled = Column(Boolean, default=True)  # Master toggle
    vehicle_alerts_enabled = Column(Boolean, default=True)  # Any vehicle detection
    animal_alerts_enabled = Column(Boolean, default=True)  # Any animal detection
    package_alerts_enabled = Column(Boolean, default=True)  # Any package detection
    identified_object_alerts_enabled = Column(Boolean, default=True)  # Specific identified objects

    # Notification Channels
    email_enabled = Column(Boolean, default=True)
    sms_enabled = Column(Boolean, default=False)
    push_enabled = Column(Boolean, default=False)
    webhook_enabled = Column(Boolean, default=False)

    # Contact Information
    email_address = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    push_token = Column(String, nullable=True)
    webhook_url = Column(String, nullable=True)

    # Alert Throttling (prevent spam)
    min_seconds_between_alerts = Column(Integer, default=300)  # 5 minutes

    # Quiet Hours (optional)
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String, default="22:00")  # "HH:MM" format
    quiet_hours_end = Column(String, default="07:00")

    # Per-camera settings (JSON: camera_id -> settings)
    camera_settings = Column(JSON, default={})

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AlertConfiguration(id={self.id}, user_id={self.user_id})>"


class NotificationLog(Base):
    """
    Logs all sent notifications for tracking and debugging
    """

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)

    # What triggered the notification
    event_type = Column(
        String, index=True
    )  # "motion", "face_known", "face_unknown", "recording"
    camera_id = Column(String, index=True)

    # Notification details
    channel = Column(String)  # "email", "sms", "push", "webhook"
    recipient = Column(String)  # Email address, phone number, etc.

    # Content
    subject = Column(String, nullable=True)
    message = Column(String)

    # Metadata
    event_data = Column(JSON, nullable=True)  # Additional event info

    # Status
    sent_successfully = Column(Boolean, default=False)
    error_message = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    sent_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<NotificationLog(id={
            self.id}, event={
            self.event_type}, channel={
            self.channel})>"


class AlertThrottle(Base):
    """
    Tracks when alerts were last sent to prevent notification spam
    """

    __tablename__ = "alert_throttles"

    id = Column(Integer, primary_key=True, index=True)

    # Throttle key (e.g., "motion_camera1", "face_known_john_camera2")
    throttle_key = Column(String, unique=True, index=True)

    # Last alert timestamp
    last_alert_time = Column(DateTime, default=datetime.utcnow)

    # Count of alerts sent in current window
    alert_count = Column(Integer, default=1)

    def __repr__(self):
        return f"<AlertThrottle(key={
            self.throttle_key}, last={
            self.last_alert_time})>"


class NotificationProvider(Base):
    """
    Stores notification provider credentials and settings

    Supports multiple notification channels:
    - Email (SMTP)
    - SMS (Twilio)
    - Push (Firebase FCM)
    - Telegram Bot
    - Discord Webhook
    - Custom Webhooks

    Credentials are encrypted at rest using Fernet (symmetric encryption)
    """

    __tablename__ = "notification_providers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # Links to User model

    # Provider identification
    provider_type = Column(String, index=True)  # "email", "sms", "push", "telegram", "discord", "webhook"
    provider_name = Column(String)  # User-friendly name (e.g., "Gmail", "Personal Twilio")
    enabled = Column(Boolean, default=True)

    # Encrypted credentials (JSON stored as encrypted text)
    # Structure varies by provider type:
    # - email: {smtp_host, smtp_port, username, password, from_email, use_tls}
    # - sms: {account_sid, auth_token, from_number}
    # - push: {fcm_server_key}
    # - telegram: {bot_token}
    # - discord: {webhook_url}
    # - webhook: {url, headers, method, timeout}
    encrypted_config = Column(Text, nullable=False)

    # Test status
    last_tested_at = Column(DateTime, nullable=True)
    test_status = Column(String, nullable=True)  # "success", "failed", "not_tested"
    test_error = Column(String, nullable=True)

    # Usage tracking
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<NotificationProvider(id={self.id}, type={self.provider_type}, name={self.provider_name})>"

    @staticmethod
    def get_encryption_key():
        """
        Get or create encryption key for credentials

        Key is stored in environment variable NOTIFICATION_ENCRYPTION_KEY.
        If not set, generates a new key (should be set in production).
        """
        key_str = os.getenv("NOTIFICATION_ENCRYPTION_KEY")

        if not key_str:
            # Generate new key for development
            key = Fernet.generate_key()
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                "NOTIFICATION_ENCRYPTION_KEY not set! Generated temporary key. "
                "Set this in production: NOTIFICATION_ENCRYPTION_KEY=" + key.decode()
            )
            return key

        return key_str.encode()

    def encrypt_config(self, config_dict: dict) -> str:
        """
        Encrypt configuration dictionary

        Args:
            config_dict: Configuration to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        import json
        fernet = Fernet(self.get_encryption_key())
        config_json = json.dumps(config_dict)
        encrypted = fernet.encrypt(config_json.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_config(self) -> dict:
        """
        Decrypt configuration

        Returns:
            Configuration dictionary
        """
        import json
        fernet = Fernet(self.get_encryption_key())
        encrypted = base64.b64decode(self.encrypted_config.encode())
        decrypted = fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())

    def set_config(self, config_dict: dict):
        """
        Set configuration (encrypts automatically)

        Args:
            config_dict: Configuration dictionary
        """
        self.encrypted_config = self.encrypt_config(config_dict)

    def get_config(self) -> dict:
        """
        Get decrypted configuration

        Returns:
            Configuration dictionary
        """
        return self.decrypt_config()
