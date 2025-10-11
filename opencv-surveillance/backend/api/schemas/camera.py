# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for Camera API endpoints
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CameraBase(BaseModel):
    """Base camera schema with common fields"""
    camera_id: str = Field(..., description="Unique camera identifier", min_length=1, max_length=100)
    camera_type: str = Field(..., description="Camera type: rtsp, mock, usb", pattern="^(rtsp|mock|usb|onvif)$")
    source: str = Field(..., description="Camera source URL or device path")
    
    # Face detection settings
    face_detection_enabled: Optional[bool] = True
    face_detection_threshold: Optional[float] = Field(0.6, ge=0.0, le=1.0)
    
    # Motion detection settings
    motion_detection_enabled: Optional[bool] = True
    min_contour_area: Optional[int] = Field(500, ge=100, le=10000)
    motion_sensitivity: Optional[int] = Field(5, ge=1, le=10, description="Motion sensitivity 1-10 (1=low, 10=high)")
    motion_threshold: Optional[int] = Field(50, ge=1, le=100, description="Detection threshold percentage")
    noise_reduction: Optional[str] = Field('medium', pattern="^(low|medium|high)$")
    detect_shadows: Optional[bool] = True
    detection_zones: Optional[str] = Field(None, description="JSON string defining detection zone grid")
    
    # Recording settings
    recording_enabled: Optional[bool] = True
    post_motion_cooldown: Optional[int] = Field(5, ge=1, le=300)
    
    # Video quality settings
    resolution: Optional[str] = Field('1920x1080', pattern="^\\d+x\\d+$")
    fps_target: Optional[int] = Field(15, ge=1, le=30)
    bitrate_kbps: Optional[int] = Field(2000, ge=500, le=10000)
    codec: Optional[str] = Field('h264', pattern="^(h264|h265|mjpeg)$")
    
    # Image quality settings
    jpeg_quality: Optional[int] = Field(90, ge=1, le=100)
    brightness: Optional[int] = Field(0, ge=-100, le=100)
    contrast: Optional[float] = Field(1.0, ge=0.5, le=3.0)
    saturation: Optional[float] = Field(1.0, ge=0.0, le=2.0)
    sharpness: Optional[str] = Field('none', pattern="^(none|low|medium|high)$")
    noise_reduction_strength: Optional[int] = Field(0, ge=0, le=100)


class CameraCreate(CameraBase):
    """Schema for creating a new camera"""
    pass


class CameraUpdate(BaseModel):
    """Schema for updating camera (all fields optional)"""
    camera_id: Optional[str] = Field(None, min_length=1, max_length=100)
    camera_type: Optional[str] = Field(None, pattern="^(rtsp|mock|usb|onvif)$")
    source: Optional[str] = None
    
    # Face detection settings
    face_detection_enabled: Optional[bool] = None
    face_detection_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    
    # Motion detection settings
    motion_detection_enabled: Optional[bool] = None
    min_contour_area: Optional[int] = Field(None, ge=100, le=10000)
    motion_sensitivity: Optional[int] = Field(None, ge=1, le=10)
    motion_threshold: Optional[int] = Field(None, ge=1, le=100)
    noise_reduction: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    detect_shadows: Optional[bool] = None
    detection_zones: Optional[str] = None
    
    # Recording settings
    recording_enabled: Optional[bool] = None
    post_motion_cooldown: Optional[int] = Field(None, ge=1, le=300)
    
    # Video quality settings
    resolution: Optional[str] = Field(None, pattern="^\\d+x\\d+$")
    fps_target: Optional[int] = Field(None, ge=1, le=30)
    bitrate_kbps: Optional[int] = Field(None, ge=500, le=10000)
    codec: Optional[str] = Field(None, pattern="^(h264|h265|mjpeg)$")
    
    # Image quality settings
    jpeg_quality: Optional[int] = Field(None, ge=1, le=100)
    brightness: Optional[int] = Field(None, ge=-100, le=100)
    contrast: Optional[float] = Field(None, ge=0.5, le=3.0)
    saturation: Optional[float] = Field(None, ge=0.0, le=2.0)
    sharpness: Optional[str] = Field(None, pattern="^(none|low|medium|high)$")
    noise_reduction_strength: Optional[int] = Field(None, ge=0, le=100)
    
    is_active: Optional[bool] = None


class CameraResponse(CameraBase):
    """Schema for camera response"""
    id: int
    is_active: bool
    created_at: datetime
    last_active: datetime
    
    class Config:
        from_attributes = True


class CameraListResponse(BaseModel):
    """Schema for listing multiple cameras"""
    cameras: list[CameraResponse]
    total: int


class CameraDiscoveredUSB(BaseModel):
    """Schema for discovered USB camera"""
    device_index: int
    device_path: str
    name: Optional[str] = "USB Camera"
    available: bool = True


class CameraDiscoveredNetwork(BaseModel):
    """Schema for discovered network camera"""
    ip_address: str
    port: int = 80
    onvif_port: Optional[int] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    rtsp_url: Optional[str] = None
    snapshot_url: Optional[str] = None


class CameraDiscoveryUSBResponse(BaseModel):
    """Response for USB camera discovery"""
    cameras: list[CameraDiscoveredUSB]
    total: int


class CameraDiscoveryNetworkResponse(BaseModel):
    """Response for network camera discovery"""
    cameras: list[CameraDiscoveredNetwork]
    total: int


class CameraStatusResponse(BaseModel):
    """Schema for camera status"""
    camera_id: str
    is_active: bool
    is_running: bool
    fps: Optional[float] = None
    last_frame_time: Optional[datetime] = None
    error_message: Optional[str] = None


class CameraSnapshotResponse(BaseModel):
    """Schema for camera snapshot response"""
    camera_id: str
    timestamp: datetime
    snapshot_path: str
    width: int
    height: int
