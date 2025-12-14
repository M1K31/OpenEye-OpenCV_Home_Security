# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
User Management Schemas
v3.11.1: Enhanced for multi-user ecosystem support
"""
from pydantic import BaseModel, Field, EmailStr
from pydantic import ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    """User role levels"""
    admin = "admin"      # Full system access
    user = "user"        # Can view/control cameras, manage own settings
    viewer = "viewer"    # Read-only access


# ============================================================================
# NOTIFICATION PREFERENCES
# ============================================================================

class NotificationTypes(BaseModel):
    """Which event types trigger notifications"""
    motion: bool = True
    face_known: bool = True
    face_unknown: bool = True
    doorbell: bool = True
    alarm: bool = True
    system: bool = True  # System alerts


class NotificationChannels(BaseModel):
    """How notifications are delivered"""
    push: bool = True
    email: bool = False
    sms: bool = False
    ecosystem: bool = True  # Forward to connected apps


class QuietHours(BaseModel):
    """Do not disturb settings"""
    enabled: bool = False
    start: str = "22:00"
    end: str = "07:00"


# ============================================================================
# UI PREFERENCES
# ============================================================================

class UIPreferences(BaseModel):
    """User interface preferences"""
    theme: str = "dark"  # dark, light, system, custom
    default_view: str = "grid"  # grid, list, map
    show_timestamps: bool = True
    compact_mode: bool = False
    language: str = "en"


class DashboardPreferences(BaseModel):
    """Dashboard layout preferences"""
    cameras_per_row: int = 2
    show_events: bool = True
    max_events: int = 10
    auto_refresh_interval: int = 5  # seconds
    show_statistics: bool = True


# ============================================================================
# ECOSYSTEM PREFERENCES
# ============================================================================

class EcosystemPreferences(BaseModel):
    """Cross-app integration settings"""
    sync_enabled: bool = True
    receive_from: List[str] = []  # App names to receive events from
    send_to: List[str] = []  # App names to send events to
    sync_faces: bool = True  # Sync face recognition data
    sync_automations: bool = True


class PresenceSettings(BaseModel):
    """Home presence detection settings"""
    home_detection: str = "face"  # face, device, manual
    away_timeout_minutes: int = 30
    notify_on_arrival: bool = True
    notify_on_departure: bool = False


class AutomationPreferences(BaseModel):
    """Automation scope for this user"""
    automation_ids: List[int] = []  # Specific automations this user can trigger
    can_trigger: bool = True  # Can trigger automations
    can_receive: bool = True  # Receives automation notifications


# ============================================================================
# USER PREFERENCES (COMBINED)
# ============================================================================

class UserPreferencesBase(BaseModel):
    """Base user preferences"""
    notification_types: Optional[NotificationTypes] = None
    notification_channels: Optional[NotificationChannels] = None
    quiet_hours: Optional[QuietHours] = None
    camera_access: Optional[List[str]] = None  # null = all cameras
    face_associations: Optional[List[str]] = None  # Face profiles to track
    ui_preferences: Optional[UIPreferences] = None
    dashboard_preferences: Optional[DashboardPreferences] = None
    ecosystem_preferences: Optional[EcosystemPreferences] = None
    presence_settings: Optional[PresenceSettings] = None
    automation_preferences: Optional[AutomationPreferences] = None


class UserPreferencesCreate(UserPreferencesBase):
    """Create user preferences"""
    pass


class UserPreferencesUpdate(UserPreferencesBase):
    """Update user preferences (all fields optional)"""
    pass


class UserPreferences(UserPreferencesBase):
    """Full user preferences response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    push_token: Optional[str] = None
    push_platform: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ============================================================================
# USER SCHEMAS
# ============================================================================

class UserBase(BaseModel):
    """Base user fields"""
    model_config = ConfigDict(from_attributes=True)
    username: str
    email: Optional[str] = None


class UserCreate(UserBase):
    """Create new user"""
    password: str
    role: UserRole = UserRole.viewer
    display_name: Optional[str] = None
    face_profile_name: Optional[str] = None  # Link to face recognition profile
    # Ecosystem sync fields
    synced_from: Optional[str] = None
    external_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Update existing user (all fields optional)"""
    model_config = ConfigDict(from_attributes=True)
    
    username: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    face_profile_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserPasswordChange(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserRoleChange(BaseModel):
    """Change user role (admin only)"""
    role: UserRole


class UserLogin(BaseModel):
    """Schema for login with JSON credentials"""
    username: str
    password: str


class User(UserBase):
    """User response (without sensitive data)"""
    id: int
    is_active: bool
    role: str = "viewer"
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    face_profile_name: Optional[str] = None
    two_factor_enabled: bool = False
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    # Ecosystem fields
    synced_from: Optional[str] = None
    synced_at: Optional[datetime] = None
    external_id: Optional[str] = None


class UserWithPreferences(User):
    """User with full preferences"""
    preferences: Optional[UserPreferences] = None


class UserListResponse(BaseModel):
    """Paginated user list response"""
    users: List[User]
    total: int
    page: int = 1
    page_size: int = 50


# ============================================================================
# USER SYNC SCHEMAS (ECOSYSTEM)
# ============================================================================

class UserSyncRequest(BaseModel):
    """Request to sync user from companion app"""
    source_app: str  # "magicmirror", "ios_app", etc.
    external_id: str
    username: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    role: UserRole = UserRole.viewer
    face_profile_name: Optional[str] = None
    preferences: Optional[UserPreferencesCreate] = None


class UserSyncResponse(BaseModel):
    """Response after user sync"""
    user_id: int
    username: str
    action: str  # "created", "updated", "linked"
    synced_at: datetime


class UserBulkSyncRequest(BaseModel):
    """Bulk sync users from companion app"""
    source_app: str
    users: List[UserSyncRequest]


class UserBulkSyncResponse(BaseModel):
    """Response after bulk user sync"""
    synced_count: int
    created_count: int
    updated_count: int
    errors: List[str]
    users: List[UserSyncResponse]


# ============================================================================
# FACE PROFILE LINKING
# ============================================================================

class LinkFaceProfileRequest(BaseModel):
    """Link a user to a face recognition profile"""
    face_profile_name: str  # Name of the person in face recognition


class LinkFaceProfileResponse(BaseModel):
    """Response after linking face profile"""
    user_id: int
    username: str
    face_profile_name: str
    linked_at: datetime
    face_exists: bool  # Whether the face profile exists in the system


# ============================================================================
# CAMERA PERMISSIONS
# ============================================================================

class CameraPermissions(BaseModel):
    """Camera access permissions for a user"""
    user_id: int
    camera_ids: Optional[List[str]] = None  # null = all cameras
    can_view: bool = True
    can_control: bool = False  # PTZ control
    can_record: bool = False  # Manual recording


class UpdateCameraPermissions(BaseModel):
    """Update camera permissions"""
    camera_ids: Optional[List[str]] = None  # null = all cameras
    can_view: Optional[bool] = None
    can_control: Optional[bool] = None
    can_record: Optional[bool] = None
