# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from backend.database import models
from backend.api.schemas import user as user_schema
from backend.core.auth import hash_password  # FIXED: Use consistent hash_password from auth


# ============================================================================
# USER CRUD OPERATIONS
# ============================================================================

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


def create_user(db: Session, user: user_schema.UserCreate):
    hashed_password = hash_password(user.password)  # FIXED: Changed from get_password_hash
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================================================
# CAMERA CRUD OPERATIONS
# ============================================================================

def get_camera_by_id(db: Session, camera_id: str) -> Optional[models.Camera]:
    """Get camera by camera_id"""
    return db.query(models.Camera).filter(models.Camera.camera_id == camera_id).first()


def get_camera_by_pk(db: Session, id: int) -> Optional[models.Camera]:
    """Get camera by primary key"""
    return db.query(models.Camera).filter(models.Camera.id == id).first()


def get_cameras(db: Session, skip: int = 0, limit: int = 100) -> List[models.Camera]:
    """Get list of cameras with pagination"""
    return db.query(models.Camera).offset(skip).limit(limit).all()


def get_active_cameras(db: Session) -> List[models.Camera]:
    """Get only active cameras"""
    return db.query(models.Camera).filter(models.Camera.is_active == True).all()


def create_camera(db: Session, camera_data: dict) -> models.Camera:
    """Create a new camera"""
    db_camera = models.Camera(**camera_data)
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


def update_camera(db: Session, camera_id: str, camera_data: dict) -> Optional[models.Camera]:
    """Update existing camera"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return None
    
    for key, value in camera_data.items():
        setattr(db_camera, key, value)
    
    db_camera.last_active = datetime.utcnow()
    db.commit()
    db.refresh(db_camera)
    return db_camera


def delete_camera(db: Session, camera_id: str) -> bool:
    """Delete camera from database"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return False
    
    db.delete(db_camera)
    db.commit()
    return True


def deactivate_camera(db: Session, camera_id: str) -> Optional[models.Camera]:
    """Soft delete - mark camera as inactive"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return None
    
    db_camera.is_active = False
    db.commit()
    db.refresh(db_camera)
    return db_camera


def update_camera_last_active(db: Session, camera_id: str) -> Optional[models.Camera]:
    """Update last_active timestamp"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return None
    
    db_camera.last_active = datetime.utcnow()
    db.commit()
    db.refresh(db_camera)
    return db_camera


# ============================================================================
# FACE DETECTION EVENT CRUD OPERATIONS
# ============================================================================

def create_face_detection_event(db: Session, event_data: dict) -> models.FaceDetectionEvent:
    """Create a new face detection event"""
    db_event = models.FaceDetectionEvent(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_face_detection_events(
    db: Session, 
    camera_id: Optional[str] = None,
    person_name: Optional[str] = None,
    skip: int = 0, 
    limit: int = 100
) -> List[models.FaceDetectionEvent]:
    """Get face detection events with optional filtering"""
    query = db.query(models.FaceDetectionEvent)
    
    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)
    
    if person_name:
        query = query.filter(models.FaceDetectionEvent.person_name == person_name)
    
    return query.order_by(models.FaceDetectionEvent.detected_at.desc()).offset(skip).limit(limit).all()


# ============================================================================
# RECORDING EVENT CRUD OPERATIONS
# ============================================================================

def create_recording_event(db: Session, event_data: dict) -> models.RecordingEvent:
    """Create a new recording event"""
    db_event = models.RecordingEvent(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def update_recording_event(db: Session, id: int, event_data: dict) -> Optional[models.RecordingEvent]:
    """Update recording event (e.g., when recording ends)"""
    db_event = db.query(models.RecordingEvent).filter(models.RecordingEvent.id == id).first()
    if not db_event:
        return None
    
    for key, value in event_data.items():
        setattr(db_event, key, value)
    
    db.commit()
    db.refresh(db_event)
    return db_event


def get_recording_events(
    db: Session,
    camera_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.RecordingEvent]:
    """Get recording events with optional filtering"""
    query = db.query(models.RecordingEvent)
    
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)
    
    return query.order_by(models.RecordingEvent.started_at.desc()).offset(skip).limit(limit).all()


# ============================================================================
# SYSTEM LOG CRUD OPERATIONS
# ============================================================================

def create_system_log(db: Session, log_data: dict) -> models.SystemLog:
    """Create a system log entry"""
    db_log = models.SystemLog(**log_data)
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log


def get_system_logs(
    db: Session,
    log_level: Optional[str] = None,
    component: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[models.SystemLog]:
    """Get system logs with optional filtering"""
    query = db.query(models.SystemLog)
    
    if log_level:
        query = query.filter(models.SystemLog.log_level == log_level)
    
    if component:
        query = query.filter(models.SystemLog.component == component)
    
    return query.order_by(models.SystemLog.created_at.desc()).offset(skip).limit(limit).all()
