# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for Motion Detection Events
Separate from face detection events to track all motion activity
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from pathlib import Path


class MotionEventBase(BaseModel):
    """Base motion event schema"""
    camera_id: str
    motion_area: Optional[int] = None
    motion_percentage: Optional[float] = None
    contour_count: Optional[int] = None
    snapshot_path: Optional[str] = None
    recording_path: Optional[str] = None
    faces_detected: int = 0
    triggered_zones: Optional[str] = None


class MotionEventCreate(MotionEventBase):
    """Schema for creating motion event"""
    pass


class MotionEventResponse(MotionEventBase):
    """Schema for motion event response"""
    id: int
    detected_at: datetime
    recording_id: Optional[int] = None
    frame_width: Optional[int] = None
    frame_height: Optional[int] = None
    face_detection_ids: Optional[str] = None

    @field_validator('snapshot_path', mode='before')
    @classmethod
    def normalize_snapshot_path(cls, v):
        """Normalize snapshot path for API response - ensure it has the correct prefix"""
        if v is None:
            return None
        path_str = str(v)
        # Return the path as-is if it already starts with data/snapshots/
        # The frontend will add the leading / to construct the URL
        if path_str.startswith('data/snapshots/'):
            return path_str
        # If it's just a filename, add the prefix
        if '/' not in path_str:
            return f"data/snapshots/{path_str}"
        return path_str

    class Config:
        from_attributes = True


class MotionEventListResponse(BaseModel):
    """Wrapped response for motion events list with pagination metadata"""
    events: List[MotionEventResponse]
    total: int
    limit: int = 100
    offset: int = 0
    has_more: bool = False


# =====================================================
# Motion Zone Schemas
# =====================================================

class MotionZoneBase(BaseModel):
    """Base motion zone schema"""
    name: str = Field(..., min_length=1, max_length=100, description="User-friendly zone name")
    zone_type: str = Field(default="polygon", pattern="^(polygon|rectangle)$", description="Zone shape type")
    coordinates: str = Field(..., description="JSON array of normalized coordinates (0.0-1.0)")
    is_active: bool = Field(default=True, description="Whether zone is currently active")
    is_exclusion_zone: bool = Field(default=False, description="If true, ignore motion in this zone")
    sensitivity_multiplier: float = Field(default=1.0, ge=0.0, le=10.0, description="Sensitivity multiplier")
    color: str = Field(default="#00FF00", pattern="^#[0-9A-Fa-f]{6}$", description="Hex color for UI")
    opacity: float = Field(default=0.3, ge=0.0, le=1.0, description="Zone fill opacity for UI")


class MotionZoneCreate(MotionZoneBase):
    """Schema for creating a new motion zone"""
    camera_id: str = Field(..., description="Camera ID this zone belongs to")


class MotionZoneUpdate(BaseModel):
    """Schema for updating an existing motion zone (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    zone_type: Optional[str] = Field(None, pattern="^(polygon|rectangle)$")
    coordinates: Optional[str] = None
    is_active: Optional[bool] = None
    is_exclusion_zone: Optional[bool] = None
    sensitivity_multiplier: Optional[float] = Field(None, ge=0.0, le=10.0)
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    opacity: Optional[float] = Field(None, ge=0.0, le=1.0)


class MotionZoneResponse(MotionZoneBase):
    """Schema for motion zone response"""
    id: int
    camera_id: str
    created_at: datetime
    updated_at: datetime
    motion_events_count: int = 0
    last_motion_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MotionZoneListResponse(BaseModel):
    """Wrapped response for motion zones list"""
    zones: List[MotionZoneResponse]
    total: int
    camera_id: str
