# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for face recognition API
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PersonBase(BaseModel):
    """Base schema for a person"""

    name: str = Field(..., description="Person's name")


class PersonCreate(PersonBase):
    """Schema for creating a new person"""
    
    merge_if_exists: bool = Field(False, description="If person folder exists, merge instead of error")
    overwrite_if_exists: bool = Field(False, description="If person folder exists, overwrite (delete existing) instead of error")


class PersonUpdate(BaseModel):
    """Schema for updating a person"""

    name: str = Field(..., description="New person's name")


class Person(PersonBase):
    """Schema for person response"""

    photo_count: int = Field(default=0, description="Number of photos for this person")
    path: str = Field(..., description="Path to person's photo directory")
    preview_photo_url: Optional[str] = Field(None, description="URL to preview photo (first photo)")

    class Config:
        from_attributes = True


class PeopleListResponse(BaseModel):
    """Schema for people list response"""
    
    people: list['Person']
    total: int


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
    confidence: float = Field(...,
                              description="Recognition confidence (0.0-1.0)")
    location: FaceLocation
    detected_at: datetime = Field(
        ...,
        alias="timestamp",
        description="Detection timestamp (accepts 'timestamp' for backward compatibility)"
    )
    motion_detected: Optional[bool] = Field(
        None, description="Whether motion was detected"
    )

    class Config:
        populate_by_name = True  # Allow both 'detected_at' and 'timestamp'


class TrainingRequest(BaseModel):
    """Schema for training request"""

    force_retrain: bool = Field(
        False, description="Force retraining even if encodings exist"
    )


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
    detection_method: str = Field(
        "hog", description="Detection method: 'hog' or 'cnn'")
    recognition_threshold: float = Field(
        0.6, description="Recognition confidence threshold"
    )
    faces_folder: str = Field("faces", description="Directory for face images (managed by PathManager)")


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


class PhotoValidationResult(BaseModel):
    """Per-photo validation result returned during upload"""

    filename: str
    has_face: bool
    face_count: int = 0
    match_result: Optional[str] = Field(
        None,
        description=(
            "'existing_match' if face matches target person, "
            "'cross_match' if face matches a different person, "
            "'new_face' if face found but no match, "
            "'no_face' if no face detected"
        ),
    )
    matched_person: Optional[str] = None
    match_confidence: Optional[float] = None
    saved: bool = False
    warning: Optional[str] = None


class ValidatedUploadResponse(BaseModel):
    """Enhanced upload response with per-photo face validation"""

    uploaded_count: int
    rejected_count: int
    person_name: str
    message: str
    success: bool = True
    photo_results: List[PhotoValidationResult] = []
    warnings: List[str] = []
