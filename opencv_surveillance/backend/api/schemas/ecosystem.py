# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Ecosystem Integration Schemas
Pydantic models for MagicMirror and mobile app integration
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# APP DISCOVERY & HEALTH
# ============================================================================


class AppInfo(BaseModel):
    """Application info for discovery"""
    app_name: str = "OpenEye"
    version: str = "3.11.1"
    capabilities: List[str] = [
        "notifications", "users", "integrations", 
        "cameras", "events", "faces", "recordings"
    ]
    uptime: int = 0  # Seconds since startup
    status: str = "healthy"


# ============================================================================
# ECOSYSTEM CONNECTION
# ============================================================================


class EcosystemConnectRequest(BaseModel):
    """Request to connect a companion app"""
    app: str = Field(..., description="App identifier (magicmirror, ios_app, android_app)")
    version: str = Field(..., description="App version")
    host: str = Field(..., description="App's host URL for callbacks")
    token: str = Field(..., description="App's API token for callbacks")
    capabilities: List[str] = Field(default=[], description="App capabilities")
    
    # v3.11.1: Multi-device identification
    device_id: Optional[str] = Field(None, description="Unique device identifier")
    device_name: Optional[str] = Field(None, description="Human-friendly device name (e.g., 'Kitchen Mirror')")
    location: Optional[str] = Field(None, description="Device location (kitchen, living_room, bedroom, etc.)")
    
    # v3.11.1: User and camera subscriptions
    associated_users: Optional[List[str]] = Field(None, description="Users associated with this device")
    subscribed_cameras: Optional[List[str]] = Field(None, description="Camera IDs this device wants events from")
    notification_preferences: Optional[Dict[str, bool]] = Field(None, description="Notification type preferences")


class EcosystemConnectResponse(BaseModel):
    """Response after connecting a companion app"""
    success: bool
    token: str = Field(..., description="Token for the companion app to use")
    expires_in: int = Field(default=86400, description="Token expiration in seconds")
    capabilities: List[str] = Field(..., description="OpenEye capabilities")
    webhook_url: str = Field(..., description="Webhook URL for receiving events")


class EcosystemConnectionInfo(BaseModel):
    """Information about a connected ecosystem app"""
    id: int
    app_name: str
    app_version: Optional[str]
    host: str
    capabilities: List[str]
    connected_at: datetime
    last_seen: datetime
    is_active: bool
    
    # v3.11.1: Multi-device info
    device_id: Optional[str] = None
    device_name: Optional[str] = None
    location: Optional[str] = None
    associated_users: Optional[List[str]] = None
    subscribed_cameras: Optional[List[str]] = None


class EcosystemStatusResponse(BaseModel):
    """Current ecosystem status"""
    connected_apps: List[EcosystemConnectionInfo]
    total_connections: int
    active_connections: int


# ============================================================================
# NOTIFICATIONS
# ============================================================================


class NotificationRequest(BaseModel):
    """Incoming notification from companion app"""
    type: str = Field(..., description="Notification type (calendar, weather, etc)")
    title: str
    message: str
    source: str = Field(..., description="Source app identifier")
    priority: str = Field(default="normal", description="normal, high, urgent")
    timestamp: Optional[datetime] = None
    dedupe_key: Optional[str] = Field(None, description="Key for deduplication")
    delivery_methods: List[str] = Field(default=["push", "display"])


class NotificationResponse(BaseModel):
    """Response after receiving notification"""
    success: bool
    notification_id: Optional[str] = None
    delivered_via: List[str] = []
    deduplicated: bool = False


class NotificationSettings(BaseModel):
    """Notification preferences for ecosystem"""
    methods: Dict[str, Dict[str, Any]] = {
        "push": {"enabled": True, "priority": 1},
        "email": {"enabled": False, "priority": 3},
        "sms": {"enabled": False, "priority": 4}
    }
    quiet_hours: Dict[str, Any] = {
        "enabled": False,
        "start": "22:00",
        "end": "07:00"
    }
    types: Dict[str, bool] = {
        "motion": True,
        "face": True,
        "doorbell": True,
        "alarm": True,
        "calendar": False,
        "weather": False
    }


# ============================================================================
# USER SYNCHRONIZATION
# ============================================================================


class EcosystemUser(BaseModel):
    """User data for ecosystem sync"""
    id: Optional[str] = None
    username: str
    email: Optional[str] = None
    role: str = "user"
    face_id: Optional[str] = None
    synced_from: Optional[str] = None
    created_at: Optional[datetime] = None


class UserSyncRequest(BaseModel):
    """Request to sync a user from companion app"""
    username: str
    email: Optional[str] = None
    role: str = "user"
    synced_from: str
    password_hash: Optional[str] = None  # Optional if using shared auth


class UserSyncResponse(BaseModel):
    """Response after user sync"""
    success: bool
    user_id: Optional[int] = None
    message: str


class UserListResponse(BaseModel):
    """List of users for ecosystem sync"""
    users: List[EcosystemUser]


# ============================================================================
# INTEGRATION SHARING
# ============================================================================


class IntegrationConfig(BaseModel):
    """Configuration for a single integration"""
    host: Optional[str] = None
    token: Optional[str] = None
    configured: bool = False
    devices: Optional[List[Dict[str, Any]]] = None
    project_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None


class IntegrationsResponse(BaseModel):
    """All configured integrations"""
    homeassistant: Optional[IntegrationConfig] = None
    homekit: Optional[IntegrationConfig] = None
    googlenest: Optional[IntegrationConfig] = None


class IntegrationSyncRequest(BaseModel):
    """Request to sync integrations from companion app"""
    homeassistant: Optional[Dict[str, Any]] = None
    homekit: Optional[Dict[str, Any]] = None
    googlenest: Optional[Dict[str, Any]] = None


class IntegrationSyncResponse(BaseModel):
    """Response after integration sync"""
    success: bool
    synced: List[str]
    skipped: List[str]
    conflicts: List[str]


# ============================================================================
# SYSTEM STATUS (Voice Command: "Security status")
# ============================================================================


class CameraStatusSummary(BaseModel):
    """Camera status summary"""
    total: int
    online: int
    recording: int
    motion_detected: int


class FaceStatusSummary(BaseModel):
    """Face recognition status summary"""
    enrolled: int
    recognized_today: int


class StorageStatusSummary(BaseModel):
    """Storage status summary"""
    used_gb: float
    total_gb: float
    percent_used: float


class LastEventInfo(BaseModel):
    """Last event information"""
    type: str
    camera_id: Optional[str] = None
    timestamp: datetime


class SystemStatusResponse(BaseModel):
    """Complete system status (for voice command "Security status")"""
    success: bool = True
    cameras: CameraStatusSummary
    faces: FaceStatusSummary
    storage: StorageStatusSummary
    uptime_seconds: int
    last_event: Optional[LastEventInfo] = None


# ============================================================================
# VOICE COMMAND ENDPOINTS
# ============================================================================


# Camera Discovery
class DiscoveredCamera(BaseModel):
    """Discovered camera info"""
    id: str
    name: str
    ip: str
    port: int
    protocol: str  # rtsp, onvif
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    onvif: bool = False


class CameraDiscoveryResponse(BaseModel):
    """Response from camera discovery"""
    success: bool
    cameras: List[DiscoveredCamera]
    scan_duration_ms: int


# Snapshot Capture
class SnapshotResponse(BaseModel):
    """Response after capturing snapshot"""
    success: bool
    snapshot_url: str
    camera_id: str
    timestamp: datetime
    resolution: str


# Face Training
class FaceTrainingStartRequest(BaseModel):
    """Request to start face training session"""
    person_name: str
    camera_id: Optional[str] = None
    auto_capture: bool = True
    photos_required: int = 5


class FaceTrainingStartResponse(BaseModel):
    """Response after starting training session"""
    success: bool
    session_id: str
    person_name: str
    photos_required: int
    instructions: str = "Please look at the camera and slowly turn your head"


class FaceTrainingCaptureRequest(BaseModel):
    """Request to capture training photo"""
    session_id: str


class FaceTrainingCaptureResponse(BaseModel):
    """Response after capturing training photo"""
    success: bool
    photo_number: int
    total_needed: int
    remaining: int
    quality_score: float
    feedback: str


class FaceTrainingCompleteRequest(BaseModel):
    """Request to complete training session"""
    session_id: str


class FaceTrainingCompleteResponse(BaseModel):
    """Response after completing training"""
    success: bool
    face_id: Optional[str] = None
    person_name: str
    photos_used: int
    encoding_quality: float


# Face Identification
class FaceIdentifyRequest(BaseModel):
    """Request to identify face in current frame"""
    camera_id: str


class FaceIdentifyResponse(BaseModel):
    """Response from face identification"""
    success: bool
    identified: bool
    person_name: Optional[str] = None
    confidence: Optional[float] = None
    face_id: Optional[str] = None
    bounding_box: Optional[Dict[str, int]] = None


# Recording Control
class RecordingStartResponse(BaseModel):
    """Response after starting recording"""
    success: bool
    recording_id: Optional[int] = None
    camera_id: str
    started_at: datetime


class RecordingStopResponse(BaseModel):
    """Response after stopping recording"""
    success: bool
    recording_id: Optional[int] = None
    duration_seconds: float
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None


# ============================================================================
# MOBILE APP ENDPOINTS
# ============================================================================


class DeviceRegisterRequest(BaseModel):
    """Request to register mobile device for push notifications"""
    platform: str = Field(..., description="ios or android")
    device_token: str = Field(..., description="APNs or FCM token")
    app_version: Optional[str] = None
    user_id: Optional[int] = None
    notification_preferences: Dict[str, bool] = {
        "motion": True,
        "face_recognized": True,
        "face_unknown": True,
        "doorbell": True,
        "recording": False
    }


class DeviceRegisterResponse(BaseModel):
    """Response after device registration"""
    success: bool
    device_id: str
    registered_at: datetime


class MobileStreamResponse(BaseModel):
    """Response with mobile-optimized stream info"""
    success: bool
    stream_url: str
    format: str  # mjpeg, hls
    expires_at: Optional[datetime] = None
    auth_token: Optional[str] = None


class ThumbnailResponse(BaseModel):
    """Response with camera thumbnail"""
    success: bool
    thumbnail_url: str
    captured_at: datetime
    camera_online: bool


class TimelineEvent(BaseModel):
    """Event for mobile timeline"""
    id: str
    type: str
    camera_id: str
    camera_name: str
    timestamp: datetime
    thumbnail_url: Optional[str] = None
    clip_available: bool = False
    clip_duration_seconds: Optional[int] = None


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int
    per_page: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class TimelineResponse(BaseModel):
    """Paginated timeline for mobile apps"""
    success: bool
    events: List[TimelineEvent]
    pagination: PaginationInfo


class RecordingPlaybackResponse(BaseModel):
    """Response with recording playback info"""
    success: bool
    playback_url: str
    format: str
    duration_seconds: float
    resolution: str
    file_size_bytes: int
    download_url: str


# ============================================================================
# WEBHOOK EVENTS
# ============================================================================


class WebhookEvent(BaseModel):
    """Event sent to companion apps via webhook"""
    source: str = "openeye"
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    signature: Optional[str] = None  # HMAC-SHA256 signature

