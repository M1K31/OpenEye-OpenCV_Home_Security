# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.

"""
Database models for the notification and alert system
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Float
from datetime import datetime
from backend.database.session import Base


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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<AlertConfiguration(id={self.id}, user_id={self.user_id})>"


class NotificationLog(Base):
    """
    Logs all sent notifications for tracking and debugging
    """
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # What triggered the notification
    event_type = Column(String, index=True)  # "motion", "face_known", "face_unknown", "recording"
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
        return f"<NotificationLog(id={self.id}, event={self.event_type}, channel={self.channel})>"


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
        return f"<AlertThrottle(key={self.throttle_key}, last={self.last_alert_time})>"