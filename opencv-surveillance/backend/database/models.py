# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database models for OpenEye Surveillance System
UPDATED to include face detection events tracking
"""

from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database.session import Base


class User(Base):
    """User model for authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Phase 6: User roles for access control
    role = Column(String, default="viewer")  # admin, user, viewer


class FaceDetectionEvent(Base):
    """
    NEW: Model for storing face detection events
    Tracks when and where faces are detected
    """
    __tablename__ = "face_detection_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True)
    person_name = Column(String, index=True)
    confidence = Column(Float)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Location of face in frame
    location_top = Column(Integer)
    location_right = Column(Integer)
    location_bottom = Column(Integer)
    location_left = Column(Integer)
    
    # Recording information
    recording_path = Column(String, nullable=True)
    snapshot_path = Column(String, nullable=True)
    
    # Motion detection context
    motion_detected = Column(Boolean, default=False)
    
    # Additional metadata
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)
    
    def __repr__(self):
        return f"<FaceDetection(person={self.person_name}, confidence={self.confidence:.2f}, time={self.detected_at})>"


class Camera(Base):
    """
    NEW: Model for storing camera configurations
    Allows persistence of camera settings
    """
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, unique=True, index=True)
    camera_type = Column(String)  # 'rtsp' or 'mock'
    source = Column(String)
    
    # Face detection settings
    face_detection_enabled = Column(Boolean, default=True)
    face_detection_threshold = Column(Float, default=0.6)
    
    # Motion detection settings
    motion_detection_enabled = Column(Boolean, default=True)
    min_contour_area = Column(Integer, default=500)
    motion_sensitivity = Column(Integer, default=5)  # 1-10 scale (5=medium)
    motion_threshold = Column(Integer, default=50)  # varThreshold 1-100
    noise_reduction = Column(String, default='medium')  # low, medium, high
    detect_shadows = Column(Boolean, default=True)
    detection_zones = Column(String, nullable=True)  # JSON string for zone grid
    
    # Recording settings
    recording_enabled = Column(Boolean, default=True)
    post_motion_cooldown = Column(Integer, default=5)
    
    # Video quality settings
    resolution = Column(String, default='1920x1080')
    fps_target = Column(Integer, default=15)
    bitrate_kbps = Column(Integer, default=2000)
    codec = Column(String, default='h264')
    
    # Image quality settings
    jpeg_quality = Column(Integer, default=90)  # 1-100
    brightness = Column(Integer, default=0)  # -100 to +100
    contrast = Column(Float, default=1.0)  # 0.5 to 3.0
    saturation = Column(Float, default=1.0)  # 0.0 to 2.0
    sharpness = Column(String, default='none')  # none, low, medium, high
    noise_reduction_strength = Column(Integer, default=0)  # 0-100
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Camera(id={self.camera_id}, type={self.camera_type})>"


class RecordingEvent(Base):
    """
    NEW: Model for tracking recording events
    Links recordings to motion and face detection events
    """
    __tablename__ = "recording_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True)
    recording_path = Column(String)
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Detection context
    motion_detected = Column(Boolean, default=False)
    faces_detected = Column(Integer, default=0)
    known_faces_detected = Column(Integer, default=0)
    
    # File metadata
    file_size_bytes = Column(Integer, nullable=True)
    frame_count = Column(Integer, nullable=True)
    
    def __repr__(self):
        return f"<Recording(camera={self.camera_id}, started={self.started_at})>"


class SystemLog(Base):
    """
    NEW: Model for system-level logging
    Tracks important events and errors
    """
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(String, index=True)  # INFO, WARNING, ERROR, CRITICAL
    component = Column(String, index=True)  # camera_manager, face_recognition, etc.
    message = Column(String)
    details = Column(String, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<SystemLog({self.log_level}: {self.component} - {self.message})>"