# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for face recognition API
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PersonBase(BaseModel):
    """Base schema for a person"""
    name: str = Field(..., description="Person's name")


class PersonCreate(PersonBase):
    """Schema for creating a new person"""
    pass


class PersonUpdate(BaseModel):
    """Schema for updating a person"""
    name: str = Field(..., description="New person's name")


class Person(PersonBase):
    """Schema for person response"""
    photo_count: int = Field(0, description="Number of photos for this person")
    path: str = Field(..., description="Path to person's photo directory")

    class Config:
        from_attributes = True


class PhotoInfo(BaseModel):
    """Schema for photo information"""
    filename: str = Field(..., description="Photo filename")
    path: str = Field(..., description="Full path to photo")
    size_bytes: int = Field(..., description="File size in bytes")
    uploaded_at: datetime = Field(..., description="Upload timestamp")

    class Config:
        from_attributes = True


class FaceLocation(BaseModel):
    """Schema for face location in frame"""
    top: int
    right: int
    bottom: int
    left: int


class FaceDetection(BaseModel):
    """Schema for a detected face"""
    name: str = Field(..., description="Recognized person name or 'Unknown'")
    confidence: float = Field(..., description="Recognition confidence (0.0-1.0)")
    location: FaceLocation
    timestamp: str = Field(..., description="ISO format timestamp")
    motion_detected: Optional[bool] = Field(None, description="Whether motion was detected")


class TrainingRequest(BaseModel):
    """Schema for training request"""
    force_retrain: bool = Field(False, description="Force retraining even if encodings exist")


class TrainingResponse(BaseModel):
    """Schema for training response"""
    total_people: int
    total_encodings: int
    training_time: float
    success: bool = True
    message: str = "Training completed successfully"


class FaceStatistics(BaseModel):
    """Schema for face recognition statistics"""
    total_people: int
    total_encodings: int
    recognitions_today: int
    last_recognition: Optional[str]


class FaceSettings(BaseModel):
    """Schema for face recognition settings"""
    enabled: bool = Field(True, description="Enable face recognition")
    detection_method: str = Field('hog', description="Detection method: 'hog' or 'cnn'")
    recognition_threshold: float = Field(0.6, description="Recognition confidence threshold")
    faces_folder: str = Field('faces', description="Directory for face images")


class UploadResponse(BaseModel):
    """Schema for photo upload response"""
    uploaded_count: int
    person_name: str
    message: str
    success: bool = True


class DeleteResponse(BaseModel):
    """Schema for delete operation response"""
    success: bool
    message: str