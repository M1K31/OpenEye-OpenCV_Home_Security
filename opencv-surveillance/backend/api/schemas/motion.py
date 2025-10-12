# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for Motion Detection Events
Separate from face detection events to track all motion activity
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


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
    
    class Config:
        from_attributes = True


class MotionEventListResponse(BaseModel):
    """Wrapped response for motion events list with pagination metadata"""
    events: List[MotionEventResponse]
    total: int
    limit: int = 100
    offset: int = 0
