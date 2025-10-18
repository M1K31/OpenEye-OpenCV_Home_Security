# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database models for OpenEye Surveillance System
UPDATED to include face detection events tracking
"""

from sqlalchemy import Boolean, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from opencv_surveillance.backend.database.session import Base


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
    recording_id = Column(Integer, ForeignKey('recording_events.id'), nullable=True, index=True)
    snapshot_path = Column(String, nullable=True)

    # Motion detection context
    motion_detected = Column(Boolean, default=False)

    # Additional metadata
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)

    # Face embedding for clustering (pickled numpy array as binary)
    face_encoding = Column(String, nullable=True)  # Base64 encoded face encoding
    
    # Cluster assignment
    cluster_id = Column(Integer, ForeignKey('face_clusters.id'), nullable=True, index=True)

    # Relationships
    recording = relationship("RecordingEvent", back_populates="face_detections")
    cluster = relationship("FaceCluster", back_populates="face_detections")

    def __repr__(self):
        return f"<FaceDetection(person={
            self.person_name}, confidence={
            self.confidence:.2f}, time={
            self.detected_at})>"


class FaceCluster(Base):
    """
    Model for storing face clusters
    Groups similar unknown faces together for identification
    """

    __tablename__ = "face_clusters"

    id = Column(Integer, primary_key=True, index=True)
    
    # Cluster information
    label = Column(String, nullable=True)  # User-assigned label/name
    is_identified = Column(Boolean, default=False)  # Whether cluster has been identified
    
    # Cluster statistics
    face_count = Column(Integer, default=0)  # Number of faces in cluster
    avg_confidence = Column(Float, nullable=True)  # Average detection confidence
    
    # Representative face (centroid)
    representative_encoding = Column(String, nullable=True)  # Base64 encoded centroid
    representative_snapshot_path = Column(String, nullable=True)  # Path to best example
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)  # Last detection time
    
    # Clustering algorithm metadata
    clustering_algorithm = Column(String, default="dbscan")  # dbscan, kmeans, etc.
    clustering_params = Column(String, nullable=True)  # JSON string of parameters
    
    # Relationships
    face_detections = relationship("FaceDetectionEvent", back_populates="cluster")

    def __repr__(self):
        label = self.label or f"Cluster-{self.id}"
        return f"<FaceCluster(id={self.id}, label={label}, faces={self.face_count})>"


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
    motion_detection_enabled = Column(
        Boolean, default=False
    )  # CHANGED: Default to False
    min_contour_area = Column(Integer, default=500)
    motion_sensitivity = Column(Integer, default=5)  # 1-10 scale (5=medium)
    motion_threshold = Column(Integer, default=50)  # varThreshold 1-100 (pixel sensitivity)
    motion_percentage_threshold = Column(Float, default=1.0)  # Min % of frame with motion (0.0-100.0)
    noise_reduction = Column(String, default="medium")  # low, medium, high
    detect_shadows = Column(Boolean, default=True)
    # JSON string for zone grid
    detection_zones = Column(String, nullable=True)

    # Recording settings
    # CHANGED: Default to False
    recording_enabled = Column(Boolean, default=False)
    post_motion_cooldown = Column(Integer, default=5)

    # Video quality settings
    resolution = Column(String, default="1920x1080")
    fps_target = Column(Integer, default=15)
    bitrate_kbps = Column(Integer, default=2000)
    codec = Column(String, default="h264")

    # Image quality settings
    jpeg_quality = Column(Integer, default=90)  # 1-100
    brightness = Column(Integer, default=0)  # -100 to +100
    contrast = Column(Float, default=1.0)  # 0.5 to 3.0
    saturation = Column(Float, default=1.0)  # 0.0 to 2.0
    sharpness = Column(String, default="none")  # none, low, medium, high
    noise_reduction_strength = Column(Integer, default=0)  # 0-100

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow)
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

    # Relationships
    face_detections = relationship("FaceDetectionEvent", back_populates="recording")
    motion_detections = relationship("MotionDetectionEvent", back_populates="recording")

    def __repr__(self):
        return f"<Recording(camera={
            self.camera_id}, started={
            self.started_at})>"


class MotionDetectionEvent(Base):
    """
    Motion detection event model
    Tracks all motion events, including those without face detection
    Separate from FaceDetectionEvent to capture motion-only activity
    """

    __tablename__ = "motion_detection_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Motion details
    motion_area = Column(Integer, nullable=True)  # Size of motion area in pixels
    motion_percentage = Column(Float, nullable=True)  # Percentage of frame with motion
    contour_count = Column(Integer, nullable=True)  # Number of motion contours detected

    # Snapshot information
    snapshot_path = Column(String, nullable=True)
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)

    # Recording linkage
    recording_id = Column(Integer, ForeignKey('recording_events.id'), nullable=True, index=True)
    recording_path = Column(String, nullable=True)

    # Face detection context
    faces_detected = Column(Integer, default=0)  # How many faces were in this motion event
    face_detection_ids = Column(String, nullable=True)  # JSON array of face detection IDs

    # Motion zone information (which zones triggered)
    triggered_zones = Column(String, nullable=True)  # JSON array of zone indices

    # Relationship
    recording = relationship("RecordingEvent", back_populates="motion_detections")

    def __repr__(self):
        return f"<MotionDetection(camera={self.camera_id}, area={self.motion_area}, time={self.detected_at})>"


class SystemLog(Base):
    """
    NEW: Model for system-level logging
    Tracks important events and errors
    """

    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_level = Column(String, index=True)  # INFO, WARNING, ERROR, CRITICAL
    # camera_manager, face_recognition, etc.
    component = Column(String, index=True)
    message = Column(String)
    details = Column(String, nullable=True)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<SystemLog({
            self.log_level}: {
            self.component} - {
            self.message})>"


class SystemSettings(Base):
    """
    NEW: Global system settings model
    Stores user preferences for paths, display modes, and global configurations
    """

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    # Unique key for each setting
    setting_key = Column(String, unique=True, index=True)
    setting_value = Column(String)  # Value stored as string (JSON if complex)
    # string, int, float, boolean, json
    setting_type = Column(String, default="string")
    description = Column(String, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<SystemSettings({self.setting_key}={self.setting_value})>"


class AutomationRule(Base):
    """
    Automation rules for person-based triggers
    Executes actions when specific people are detected
    """

    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Human-readable rule name
    person_name = Column(String, index=True, nullable=False)  # Person to trigger on
    enabled = Column(Boolean, default=True, index=True)
    
    # Conditions (JSON string)
    # Example: {"cameras": ["front_door"], "time_range": {"start": "08:00", "end": "18:00"}}
    conditions = Column(String, nullable=True)
    
    # Actions to execute (JSON array)
    # Example: [{"type": "notification", "message": "John detected"}, {"type": "record", "duration": 30}]
    actions = Column(String, nullable=False)
    
    # Cooldown period in seconds (prevent spam)
    cooldown_seconds = Column(Integer, default=300)  # 5 minutes default
    last_triggered_at = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    trigger_count = Column(Integer, default=0)  # Track how many times it's triggered
    
    def __repr__(self):
        return f"<AutomationRule(name={self.name}, person={self.person_name}, enabled={self.enabled})>"
