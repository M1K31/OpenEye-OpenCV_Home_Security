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

    # v3.6.0: Two-Factor Authentication
    totp_secret = Column(String, nullable=True)  # Encrypted TOTP secret
    two_factor_enabled = Column(Boolean, default=False)  # 2FA enabled flag
    backup_codes = Column(String, nullable=True)  # JSON array of hashed backup codes
    two_factor_enrolled_at = Column(DateTime, nullable=True)  # When 2FA was enabled

    # v3.9.0: Account lockout for failed 2FA attempts
    failed_2fa_attempts = Column(Integer, default=0)  # Failed 2FA verification count
    last_failed_2fa_attempt = Column(DateTime, nullable=True)  # Last failed attempt timestamp
    account_locked_until = Column(DateTime, nullable=True)  # Account locked until this time
    lockout_count = Column(Integer, default=0)  # Number of times account has been locked

    # v3.11.1: Multi-user ecosystem support
    display_name = Column(String(100), nullable=True)  # Friendly display name
    avatar_url = Column(String(255), nullable=True)  # Profile picture URL
    face_profile_name = Column(String(100), nullable=True)  # Linked face recognition profile
    synced_from = Column(String(50), nullable=True)  # Source app if synced (magicmirror, etc)
    synced_at = Column(DateTime, nullable=True)  # When user was synced
    external_id = Column(String(255), nullable=True)  # External ID from source app
    last_login = Column(DateTime, nullable=True)  # Last login timestamp
    
    # v3.8.0: Refresh Token Relationship
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    # v3.11.1: User Preferences Relationship
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")


class RefreshToken(Base):
    """
    v3.8.0: Refresh Token model for JWT token rotation
    Enables automatic token refresh without re-authentication
    """

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String(512), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False, index=True)

    # Device tracking for security audit
    device_info = Column(String(255), nullable=True)  # User agent
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6

    # Relationship
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, user_id={self.user_id}, revoked={self.revoked})>"


class UserPreferences(Base):
    """
    v3.11.1: User Preferences Model
    Per-user settings for notifications, camera access, UI, and ecosystem integration
    
    Supports:
    - Notification preferences (which events to receive)
    - Camera access permissions (which cameras user can see)
    - Face recognition associations (link user to their face profile)
    - UI preferences (theme, layout)
    - Ecosystem sync settings
    """

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    # Notification Preferences (JSON)
    # {"motion": true, "face_known": true, "face_unknown": false, "doorbell": true}
    notification_types = Column(String, default='{"motion": true, "face_known": true, "face_unknown": true, "doorbell": true, "alarm": true}')
    
    # Notification Channels (JSON)
    # {"push": true, "email": false, "sms": false}
    notification_channels = Column(String, default='{"push": true, "email": false, "sms": false}')
    
    # Quiet Hours (JSON)
    # {"enabled": false, "start": "22:00", "end": "07:00"}
    quiet_hours = Column(String, default='{"enabled": false, "start": "22:00", "end": "07:00"}')
    
    # Camera Access Permissions (JSON array)
    # null = all cameras, ["front_door", "backyard"] = specific cameras only
    camera_access = Column(String, nullable=True)
    
    # Face Recognition Associations (JSON array of person names)
    # When these faces are detected, notify this user
    # ["John", "Jane"] = notify when John or Jane detected
    face_associations = Column(String, nullable=True)
    
    # UI Preferences (JSON)
    # {"theme": "dark", "default_view": "grid", "show_timestamps": true}
    ui_preferences = Column(String, default='{"theme": "dark", "default_view": "grid", "show_timestamps": true}')
    
    # Dashboard Layout (JSON)
    # {"cameras_per_row": 2, "show_events": true, "max_events": 10}
    dashboard_preferences = Column(String, default='{"cameras_per_row": 2, "show_events": true, "max_events": 10}')
    
    # Ecosystem Preferences (JSON)
    # {"sync_enabled": true, "receive_from": ["magicmirror"], "send_to": ["magicmirror"]}
    ecosystem_preferences = Column(String, default='{"sync_enabled": true, "receive_from": [], "send_to": []}')
    
    # Home Presence (for automation)
    # {"home_detection": "face", "away_timeout_minutes": 30}
    presence_settings = Column(String, default='{"home_detection": "face", "away_timeout_minutes": 30}')
    
    # Automation Preferences (JSON)
    # {"automation_ids": [1, 2, 3], "can_trigger": true, "can_receive": true}
    automation_preferences = Column(String, default='{"automation_ids": [], "can_trigger": true, "can_receive": true}')
    
    # Mobile Push Settings
    push_token = Column(String(512), nullable=True)  # APNs or FCM token
    push_platform = Column(String(20), nullable=True)  # ios, android
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="preferences")

    def __repr__(self):
        return f"<UserPreferences(user_id={self.user_id})>"


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
    face_detection_threshold = Column(Float, default=0.6)  # Recognition confidence threshold (0.4-0.8, lower=stricter)
    face_detection_model = Column(String, default="hog")  # "hog" (CPU) or "cnn" (GPU, requires CUDA)
    face_detection_upsample = Column(Integer, default=1)  # Times to upsample image (0-2, higher=slower but finds smaller faces)
    face_detection_scale = Column(String, default="auto")  # "auto", "none", or float like "0.5" (manual scale factor)
    min_face_size_pixels = Column(Integer, default=20)  # Minimum face size to detect (pixels, after scaling)

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

    # v3.5.7: Enhanced motion detection parameters (recommended defaults for shadow mitigation)
    shadow_detection_method = Column(String, default="dual")  # binary, hsv, dual (dual recommended)
    erosion_iterations = Column(Integer, default=2)  # Custom erosion (2 recommended)
    dilation_iterations = Column(Integer, default=3)  # Custom dilation (3 recommended)
    motion_persistence_frames = Column(Integer, default=2)  # Frames to maintain motion state
    use_grayscale = Column(Boolean, default=True)  # Convert to grayscale before processing
    lighting_compensation_enabled = Column(Boolean, default=True)  # Enable lighting change detection
    brightness_change_threshold = Column(Integer, default=15)  # Threshold for lighting changes (1-50)

    # Recording settings
    # CHANGED: Default to False
    recording_enabled = Column(Boolean, default=False)
    post_motion_cooldown = Column(Integer, default=5)
    audio_recording_enabled = Column(Boolean, default=False)  # Enable audio recording with video
    audio_device = Column(String, nullable=True)  # Audio input device (None = default)

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

    # Overlay settings (timestamp and custom text)
    overlay_enabled = Column(Boolean, default=True)  # Master enable/disable
    overlay_timestamp_enabled = Column(Boolean, default=True)  # Show timestamp
    overlay_custom_text = Column(String, nullable=True)  # Custom message text
    overlay_position = Column(String, default="top-left")  # top-left, top-right, bottom-left, bottom-right, center-top, center-bottom
    overlay_font_size = Column(Integer, default=1)  # Font scale 1-3
    overlay_font_color = Column(String, default="white")  # white, yellow, cyan, green, red

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
    objects_detected = Column(Integer, default=0)  # v3.10.0: Total objects detected
    identified_objects_detected = Column(Integer, default=0)  # v3.10.0: Known objects detected

    # File metadata
    file_size_bytes = Column(Integer, nullable=True)
    frame_count = Column(Integer, nullable=True)
    thumbnail_path = Column(String, nullable=True)  # Optional thumbnail for preview

    # Relationships
    face_detections = relationship("FaceDetectionEvent", back_populates="recording")
    motion_detections = relationship("MotionDetectionEvent", back_populates="recording")
    object_detections = relationship("ObjectDetectionEvent", back_populates="recording")  # v3.10.0

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


class MotionZone(Base):
    """
    Motion detection zone model
    Allows users to define specific areas for motion detection with custom sensitivity
    Supports polygon and rectangle zones
    """

    __tablename__ = "motion_zones"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, ForeignKey('cameras.camera_id'), nullable=False, index=True)

    # Zone identification
    name = Column(String, nullable=False)  # User-friendly name (e.g., "Front Door", "Driveway")
    zone_type = Column(String, default="polygon")  # "polygon" or "rectangle"

    # Zone coordinates (JSON array)
    # Polygon: [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}, ...]
    # Rectangle: [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.9}] (top-left, bottom-right)
    # Coordinates are normalized (0.0 to 1.0) relative to frame dimensions
    coordinates = Column(String, nullable=False)  # JSON string

    # Zone settings
    is_active = Column(Boolean, default=True, index=True)
    is_exclusion_zone = Column(Boolean, default=False)  # If True, ignore motion in this zone

    # Sensitivity multiplier (0.0 to 10.0, default 1.0)
    # < 1.0 = less sensitive (fewer alerts)
    # > 1.0 = more sensitive (more alerts)
    sensitivity_multiplier = Column(Float, default=1.0)

    # Display settings (for UI)
    color = Column(String, default="#00FF00")  # Hex color for zone outline
    opacity = Column(Float, default=0.3)  # Zone fill opacity (0.0 to 1.0)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Statistics (optional)
    motion_events_count = Column(Integer, default=0)  # Track motions detected in this zone
    last_motion_at = Column(DateTime, nullable=True)  # Last motion detection in zone

    def __repr__(self):
        return f"<MotionZone(id={self.id}, camera={self.camera_id}, name={self.name}, active={self.is_active})>"


class PTZPreset(Base):
    """
    PTZ Preset Position Model
    Stores saved camera positions for quick recall
    """

    __tablename__ = "ptz_presets"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, ForeignKey('cameras.camera_id'), nullable=False, index=True)

    # Preset identification
    name = Column(String, nullable=False)  # User-friendly name (e.g., "Front Gate", "Parking Lot")
    preset_number = Column(Integer, nullable=False)  # Preset slot (1-255 for ONVIF)

    # PTZ coordinates
    pan = Column(Float, nullable=False)  # Pan position (-1.0 to 1.0 or degrees depending on camera)
    tilt = Column(Float, nullable=False)  # Tilt position (-1.0 to 1.0 or degrees)
    zoom = Column(Float, nullable=False)  # Zoom level (0.0 to 1.0 or actual zoom factor)

    # Optional thumbnail for visual reference
    thumbnail_path = Column(String, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)  # Track how often this preset is used

    def __repr__(self):
        return f"<PTZPreset(id={self.id}, camera={self.camera_id}, name={self.name})>"


class PTZPatrolPattern(Base):
    """
    PTZ Patrol Pattern Model
    Defines automated camera movement patterns (e.g., left → right → center)
    """

    __tablename__ = "ptz_patrol_patterns"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, ForeignKey('cameras.camera_id'), nullable=False, index=True)

    # Pattern identification
    name = Column(String, nullable=False)  # User-friendly name (e.g., "Standard Patrol", "Perimeter Scan")
    description = Column(String, nullable=True)  # Optional description

    # Pattern configuration
    # JSON array of preset IDs or positions in sequence
    # Example: [{"preset_id": 1, "dwell_time": 5}, {"preset_id": 2, "dwell_time": 3}]
    # Or: [{"pan": 0.5, "tilt": 0.0, "zoom": 0.5, "dwell_time": 5}]
    pattern_steps = Column(String, nullable=False)  # JSON string

    # Execution settings
    is_active = Column(Boolean, default=False, index=True)  # Currently running
    loop_enabled = Column(Boolean, default=True)  # Repeat pattern continuously
    interval_seconds = Column(Integer, default=10)  # Time at each position before moving to next

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    run_count = Column(Integer, default=0)  # Track how many times pattern has run

    def __repr__(self):
        return f"<PTZPatrolPattern(id={self.id}, camera={self.camera_id}, name={self.name}, active={self.is_active})>"


class FeatureState(Base):
    """
    Tracks the enabled/disabled state of system features
    Hardware-aware feature management system
    """

    __tablename__ = "feature_states"

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(String, unique=True, index=True, nullable=False)  # From feature_config.py
    enabled = Column(Boolean, default=False, index=True)  # Currently enabled
    auto_configured = Column(Boolean, default=True)  # Was this auto-configured based on hardware?
    user_override = Column(Boolean, default=False)  # Did user manually enable/disable?

    # Hardware compatibility at last check
    hardware_compatible = Column(Boolean, default=True)  # Can current hardware run this?
    compatibility_reason = Column(String, nullable=True)  # Why is it incompatible?

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_checked_at = Column(DateTime, default=datetime.utcnow)  # Last hardware compatibility check

    def __repr__(self):
        return f"<FeatureState(feature={self.feature_id}, enabled={self.enabled}, compatible={self.hardware_compatible})>"


class HardwareScanHistory(Base):
    """
    Tracks hardware scans and changes over time
    Allows users to see hardware changes and scan history
    """

    __tablename__ = "hardware_scan_history"

    id = Column(Integer, primary_key=True, index=True)
    scan_type = Column(String, default="manual")  # manual, startup, scheduled, triggered

    # Hardware snapshot (JSON)
    cpu_cores = Column(Integer)
    ram_total_gb = Column(Float)
    gpu_available = Column(Boolean)
    gpu_name = Column(String, nullable=True)
    gpu_memory_mb = Column(Integer, nullable=True)

    # Classification
    hardware_tier = Column(String)  # minimal, low, medium, high_end

    # Changes detected
    changes_detected = Column(Boolean, default=False)
    changes_summary = Column(String, nullable=True)  # JSON: what changed since last scan

    # Actions taken
    features_enabled = Column(Integer, default=0)  # How many features were auto-enabled
    features_disabled = Column(Integer, default=0)  # How many features were auto-disabled

    # Metadata
    scanned_at = Column(DateTime, default=datetime.utcnow, index=True)
    scanned_by = Column(String, nullable=True)  # username or "system"

    def __repr__(self):
        return f"<HardwareScanHistory(id={self.id}, tier={self.hardware_tier}, scanned_at={self.scanned_at})>"


class ObjectDetectionEvent(Base):
    """
    v3.10.0: Object Detection Event Model
    Tracks detected objects (vehicles, animals, packages) using YOLO
    Similar to FaceDetectionEvent but for general objects
    """

    __tablename__ = "object_detection_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, index=True, nullable=False)

    # Object classification
    object_class = Column(String, index=True, nullable=False)  # vehicle, animal, package, person
    object_subclass = Column(String, nullable=True)  # car, truck, dog, cat, box, etc. (from YOLO)
    confidence = Column(Float, nullable=False)

    # Detection timestamp
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Bounding box location in frame
    bbox_x = Column(Integer, nullable=False)  # Top-left X coordinate
    bbox_y = Column(Integer, nullable=False)  # Top-left Y coordinate
    bbox_width = Column(Integer, nullable=False)  # Bounding box width
    bbox_height = Column(Integer, nullable=False)  # Bounding box height

    # Frame metadata
    frame_width = Column(Integer, nullable=True)
    frame_height = Column(Integer, nullable=True)

    # Snapshot of detection
    snapshot_path = Column(String, nullable=True)

    # Recording linkage
    recording_id = Column(Integer, ForeignKey('recording_events.id'), nullable=True, index=True)
    recording_path = Column(String, nullable=True)

    # Motion detection context
    motion_detected = Column(Boolean, default=False)

    # Identified object linkage (nullable - only if object has been identified)
    identified_object_id = Column(Integer, ForeignKey('identified_objects.id'), nullable=True, index=True)

    # Additional YOLO metadata (JSON string)
    # Can store additional tracking info like object trajectory, speed, direction
    # Note: Renamed from 'metadata' to avoid SQLAlchemy reserved attribute conflict
    detection_metadata = Column(String, nullable=True)

    # Relationships
    recording = relationship("RecordingEvent", back_populates="object_detections")
    identified_object = relationship("IdentifiedObject", back_populates="detections")

    def __repr__(self):
        obj_name = f"{self.object_subclass or self.object_class}"
        return f"<ObjectDetection(object={obj_name}, confidence={self.confidence:.2f}, time={self.detected_at})>"


class IdentifiedObject(Base):
    """
    v3.10.0: Identified Object Model
    Stores user-identified specific objects (e.g., "John's Tesla", "My Dog Rex")
    Allows tracking of specific vehicles, animals, or packages
    Similar to Person model for face recognition
    """

    __tablename__ = "identified_objects"

    id = Column(Integer, primary_key=True, index=True)

    # Unique identifier (user-defined, e.g., "johns_tesla", "my_dog_rex")
    object_id = Column(String, unique=True, index=True, nullable=False)

    # Display name (e.g., "John's Tesla", "My Dog Rex")
    name = Column(String, nullable=False, index=True)

    # Object classification
    object_class = Column(String, index=True, nullable=False)  # vehicle, animal, package
    object_subclass = Column(String, nullable=True)  # car, dog, box, etc.

    # Description and notes
    description = Column(String, nullable=True)  # User notes about the object

    # Representative image path (for UI display)
    representative_image_path = Column(String, nullable=True)

    # Object features for identification (JSON string)
    # Can store color, make/model for vehicles, breed for animals, etc.
    features = Column(String, nullable=True)

    # Tracking statistics
    detection_count = Column(Integer, default=0)  # Total number of detections
    first_seen_at = Column(DateTime, nullable=True)  # First detection timestamp
    last_seen_at = Column(DateTime, nullable=True)  # Most recent detection

    # Notification settings (JSON string)
    # Allow per-object notification preferences
    notification_config = Column(String, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)  # Enable/disable tracking

    # Relationships
    detections = relationship("ObjectDetectionEvent", back_populates="identified_object")

    def __repr__(self):
        return f"<IdentifiedObject(id={self.object_id}, name={self.name}, class={self.object_class})>"


# ============================================================================
# ECOSYSTEM INTEGRATION MODELS (v3.11.0)
# ============================================================================


class EcosystemConnection(Base):
    """
    v3.11.0: Ecosystem Connection Model
    v3.11.1: Enhanced for multi-device/multi-user support
    
    Stores connections to companion apps (MagicMirror, mobile apps, etc.)
    Enables cross-app integration for notifications, user sync, and event streaming
    
    Multi-device architecture:
    - Each device (MagicMirror, phone) has its own connection record
    - device_id uniquely identifies a physical device
    - location identifies where the device is (living_room, kitchen, etc.)
    - Associated users determine which notifications/events route to this device
    - Camera subscriptions filter which camera events this device receives
    """

    __tablename__ = "ecosystem_connections"

    id = Column(Integer, primary_key=True, index=True)
    
    # App identification
    app_name = Column(String(50), nullable=False, index=True)  # magicmirror, ios_app, android_app
    app_version = Column(String(20), nullable=True)
    
    # v3.11.1: Device identification for multi-device support
    device_id = Column(String(100), nullable=True, index=True)  # Unique device identifier
    device_name = Column(String(100), nullable=True)  # Human-friendly name (e.g., "Kitchen Mirror")
    location = Column(String(100), nullable=True, index=True)  # Location in home (kitchen, living_room, etc.)
    
    # Connection details
    host = Column(String(255), nullable=False)  # e.g., http://192.168.1.100:8080
    
    # Authentication tokens
    remote_token = Column(String(512), nullable=True)  # Token to call companion app
    local_token = Column(String(512), nullable=False, unique=True, index=True)  # Token companion uses for us
    
    # Capabilities (JSON array)
    capabilities = Column(String, default="[]")  # ["notifications", "users", "integrations"]
    
    # Webhook configuration
    webhook_url = Column(String(255), nullable=True)  # Callback URL for events
    
    # Connection state
    connected_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)
    
    # Connection metadata
    device_info = Column(String(255), nullable=True)  # User agent or device identifier
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    
    # v3.11.1: Multi-user/Multi-device routing
    # Associated users (JSON array of user IDs or usernames)
    # If empty/null, receives ALL user events; if set, only receives events for these users
    associated_users = Column(String, nullable=True)  # ["john", "jane"] or [1, 2]
    
    # Camera subscriptions (JSON array of camera IDs)
    # If empty/null, receives ALL camera events; if set, only receives events from these cameras
    subscribed_cameras = Column(String, nullable=True)  # ["front_door", "backyard"]
    
    # Notification preferences (JSON object)
    # Overrides per-device: {"motion": true, "face_known": true, "face_unknown": false}
    notification_preferences = Column(String, default="{}")
    
    # Automation scope (JSON array of automation rule IDs this device can trigger)
    # If empty/null, can trigger ALL automations; if set, only these
    automation_scope = Column(String, nullable=True)
    
    # Priority for notifications (higher = more important, receives first)
    priority = Column(Integer, default=0)

    def __repr__(self):
        name = self.device_name or self.device_id or self.host
        return f"<EcosystemConnection(app={self.app_name}, device={name}, active={self.is_active})>"


class NotificationDedup(Base):
    """
    v3.11.0: Notification Deduplication Model
    Prevents duplicate notifications across ecosystem apps
    """

    __tablename__ = "notification_dedup"

    id = Column(Integer, primary_key=True, index=True)
    
    # Deduplication key (hash of notification content)
    dedupe_key = Column(String(64), unique=True, nullable=False, index=True)
    
    # Source tracking
    source = Column(String(50), nullable=False)  # openeye, magicmirror, ios_app, etc.
    notification_type = Column(String(50), nullable=True)  # motion, face, doorbell, etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)

    def __repr__(self):
        return f"<NotificationDedup(key={self.dedupe_key[:16]}..., source={self.source})>"


class MobileDevice(Base):
    """
    v3.11.0: Mobile Device Registration Model
    Stores registered mobile devices for push notifications
    """

    __tablename__ = "mobile_devices"

    id = Column(Integer, primary_key=True, index=True)
    
    # Device identification
    device_id = Column(String(255), unique=True, nullable=False, index=True)
    platform = Column(String(20), nullable=False)  # ios, android
    
    # Push notification token
    device_token = Column(String(512), nullable=False)
    
    # App information
    app_version = Column(String(20), nullable=True)
    
    # User association
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    
    # Notification preferences (JSON)
    notification_preferences = Column(String, default="{}")
    
    # Registration metadata
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True, index=True)

    def __repr__(self):
        return f"<MobileDevice(id={self.device_id[:20]}..., platform={self.platform})>"


class FaceTrainingSession(Base):
    """
    v3.11.0: Face Training Session Model
    Tracks interactive face training sessions (for voice commands)
    """

    __tablename__ = "face_training_sessions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Session identification
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # Training target
    person_name = Column(String(100), nullable=False)
    camera_id = Column(String(100), nullable=True)
    
    # Session configuration
    photos_required = Column(Integer, default=5)
    auto_capture = Column(Boolean, default=True)
    
    # Session progress
    photos_captured = Column(Integer, default=0)
    status = Column(String(20), default="active")  # active, completed, cancelled, expired
    
    # Captured photo paths (JSON array)
    captured_photos = Column(String, default="[]")
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)  # Session timeout

    def __repr__(self):
        return f"<FaceTrainingSession(person={self.person_name}, status={self.status})>"
