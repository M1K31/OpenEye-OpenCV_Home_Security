# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional

from backend.database import models
from backend.api.schemas import user as user_schema
from backend.core.auth import (
    hash_password,
)  # FIXED: Use consistent hash_password from auth


# ============================================================================
# USER CRUD OPERATIONS
# ============================================================================


def get_user_by_username(db: Session, username: str):
    return db.query(
        models.User).filter(
        models.User.username == username).first()


def create_user(db: Session, user: user_schema.UserCreate):
    hashed_password = hash_password(
        user.password
    )  # FIXED: Changed from get_password_hash
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ============================================================================
# CAMERA CRUD OPERATIONS
# ============================================================================


def get_camera_by_id(db: Session, camera_id: str) -> Optional[models.Camera]:
    """Get camera by camera_id"""
    return db.query(
        models.Camera).filter(
        models.Camera.camera_id == camera_id).first()


def get_camera_by_pk(db: Session, id: int) -> Optional[models.Camera]:
    """Get camera by primary key"""
    return db.query(models.Camera).filter(models.Camera.id == id).first()


def get_cameras(db: Session, skip: int = 0,
                limit: int = 100) -> List[models.Camera]:
    """Get list of cameras with pagination"""
    return db.query(models.Camera).offset(skip).limit(limit).all()


def get_active_cameras(db: Session) -> List[models.Camera]:
    """Get only active cameras"""
    return db.query(models.Camera).filter(models.Camera.is_active).all()


def create_camera(db: Session, camera_data: dict) -> models.Camera:
    """Create a new camera"""
    db_camera = models.Camera(**camera_data)
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


def update_camera(
    db: Session, camera_id: str, camera_data: dict
) -> Optional[models.Camera]:
    """Update existing camera"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return None

    for key, value in camera_data.items():
        setattr(db_camera, key, value)

    db_camera.last_active_at = datetime.utcnow()
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


def update_camera_last_active(db: Session,
                              camera_id: str) -> Optional[models.Camera]:
    """Update last_active_at timestamp"""
    db_camera = get_camera_by_id(db, camera_id)
    if not db_camera:
        return None

    db_camera.last_active_at = datetime.utcnow()
    db.commit()
    db.refresh(db_camera)
    return db_camera


# ============================================================================
# FACE DETECTION EVENT CRUD OPERATIONS
# ============================================================================


def create_face_detection_event(
    db: Session, event_data: dict
) -> models.FaceDetectionEvent:
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
    limit: int = 100,
) -> List[models.FaceDetectionEvent]:
    """Get face detection events with optional filtering"""
    query = db.query(models.FaceDetectionEvent)

    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

    if person_name:
        query = query.filter(
            models.FaceDetectionEvent.person_name == person_name)

    return (
        query.order_by(models.FaceDetectionEvent.detected_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ============================================================================
# RECORDING EVENT CRUD OPERATIONS
# ============================================================================


def create_recording_event(
        db: Session,
        event_data: dict) -> models.RecordingEvent:
    """Create a new recording event"""
    db_event = models.RecordingEvent(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def update_recording_event(
    db: Session, id: int, event_data: dict
) -> Optional[models.RecordingEvent]:
    """Update recording event (e.g., when recording ends)"""
    db_event = (
        db.query(
            models.RecordingEvent).filter(
            models.RecordingEvent.id == id).first())
    if not db_event:
        return None

    for key, value in event_data.items():
        setattr(db_event, key, value)

    db.commit()
    db.refresh(db_event)
    return db_event


def get_recording_events(db: Session,
                         camera_id: Optional[str] = None,
                         skip: int = 0,
                         limit: int = 100) -> List[models.RecordingEvent]:
    """Get recording events with optional filtering"""
    query = db.query(models.RecordingEvent)

    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    return (
        query.order_by(models.RecordingEvent.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


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
    limit: int = 100,
) -> List[models.SystemLog]:
    """Get system logs with optional filtering"""
    query = db.query(models.SystemLog)

    if log_level:
        query = query.filter(models.SystemLog.log_level == log_level)

    if component:
        query = query.filter(models.SystemLog.component == component)

    return (
        query.order_by(models.SystemLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ============================================================================
# SYSTEM SETTINGS CRUD OPERATIONS
# ============================================================================


def get_system_setting(
    db: Session, setting_key: str
) -> Optional[models.SystemSettings]:
    """Get a system setting by key"""
    return (
        db.query(models.SystemSettings)
        .filter(models.SystemSettings.setting_key == setting_key)
        .first()
    )


def get_all_system_settings(db: Session) -> List[models.SystemSettings]:
    """Get all system settings"""
    return db.query(models.SystemSettings).all()


def set_system_setting(
    db: Session,
    setting_key: str,
    setting_value: str,
    setting_type: str = "string",
    description: str = None,
) -> models.SystemSettings:
    """Set or update a system setting"""
    db_setting = get_system_setting(db, setting_key)

    if db_setting:
        # Update existing setting
        db_setting.setting_value = setting_value
        db_setting.setting_type = setting_type
        if description:
            db_setting.description = description
        db_setting.updated_at = datetime.utcnow()
    else:
        # Create new setting
        db_setting = models.SystemSettings(
            setting_key=setting_key,
            setting_value=setting_value,
            setting_type=setting_type,
            description=description,
        )
        db.add(db_setting)

    db.commit()
    db.refresh(db_setting)
    return db_setting


def delete_system_setting(db: Session, setting_key: str) -> bool:
    """Delete a system setting"""
    db_setting = get_system_setting(db, setting_key)
    if not db_setting:
        return False

    db.delete(db_setting)
    db.commit()
    return True


def initialize_default_settings(db: Session):
    """Initialize default system settings if they don't exist"""
    import os

    defaults = {
        "recordings_path": (
            "recordings",
            "string",
            "Directory where video recordings are saved",
        ),
        "faces_path": ("faces", "string", "Directory where face images are saved"),
        "snapshots_path": (
            "data/snapshots",
            "string",
            "Directory where motion detection snapshots are saved",
        ),
        "display_mode": (
            "grid",
            "string",
            "Camera display mode: grid, vertical, horizontal, cycle",
        ),
        "cycle_interval": ("5", "int", "Seconds between camera switches in cycle mode"),
        "max_recording_duration": (
            "300",
            "int",
            "Maximum recording duration in seconds",
        ),
        "theme": ("dark", "string", "UI theme: light or dark"),
    }

    for key, (value, stype, desc) in defaults.items():
        existing = get_system_setting(db, key)
        if not existing:
            set_system_setting(db, key, value, stype, desc)


# ============================================================================
# SPECIALIZED FACE DETECTION CRUD OPERATIONS
# ============================================================================


def get_recent_face_detections(
    db: Session,
    camera_id: Optional[str] = None,
    person_name: Optional[str] = None,
    limit: int = 50,
    hours: int = 24,
) -> List[models.FaceDetectionEvent]:
    """Get recent face detection events with optional filters"""
    from sqlalchemy import desc
    from datetime import timedelta

    query = db.query(models.FaceDetectionEvent)

    # Filter by time
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(
        models.FaceDetectionEvent.detected_at >= time_threshold)

    # Optional filters
    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

    if person_name:
        query = query.filter(
            models.FaceDetectionEvent.person_name == person_name)

    # Order by most recent and limit
    query = query.order_by(desc(models.FaceDetectionEvent.detected_at))
    query = query.limit(limit)

    return query.all()


def get_face_detection_statistics(
    db: Session, camera_id: Optional[str] = None, days: int = 7
):
    """Get statistics about face detections"""
    from sqlalchemy import func, desc
    from datetime import timedelta

    time_threshold = datetime.utcnow() - timedelta(days=days)

    query = db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.detected_at >= time_threshold
    )

    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

    total_detections = query.count()

    # Count unique people detected
    unique_people = db.query(
        func.count(func.distinct(models.FaceDetectionEvent.person_name))
    ).filter(
        models.FaceDetectionEvent.detected_at >= time_threshold,
        models.FaceDetectionEvent.person_name != "Unknown",
    )

    if camera_id:
        unique_people = unique_people.filter(
            models.FaceDetectionEvent.camera_id == camera_id
        )

    unique_people_count = unique_people.scalar()

    # Get most detected person
    most_detected = (
        query.filter(models.FaceDetectionEvent.person_name != "Unknown")
        .group_by(models.FaceDetectionEvent.person_name)
        .order_by(desc(func.count(models.FaceDetectionEvent.person_name)))
        .first()
    )

    return {
        "total_detections": total_detections,
        "unique_people": unique_people_count,
        "most_detected_person": most_detected.person_name if most_detected else None,
        "time_period_days": days,
    }


def get_person_detection_history(
    db: Session, person_name: str, limit: int = 100
) -> List[models.FaceDetectionEvent]:
    """Get detection history for a specific person"""
    from sqlalchemy import desc

    return (
        db.query(models.FaceDetectionEvent)
        .filter(models.FaceDetectionEvent.person_name == person_name)
        .order_by(desc(models.FaceDetectionEvent.detected_at))
        .limit(limit)
        .all()
    )


def get_recent_recordings(
    db: Session, camera_id: Optional[str] = None, limit: int = 20
) -> List[models.RecordingEvent]:
    """Get recent recording events"""
    from sqlalchemy import desc

    query = db.query(models.RecordingEvent)

    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    return query.order_by(
        desc(models.RecordingEvent.started_at)).limit(limit).all()


def cleanup_old_events(db: Session, days_to_keep: int = 30):
    """Clean up old events from the database"""
    from datetime import timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

    # Delete old face detections
    face_detections_deleted = (
        db.query(models.FaceDetectionEvent)
        .filter(models.FaceDetectionEvent.detected_at < cutoff_date)
        .delete()
    )

    # Delete old recordings
    recordings_deleted = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.started_at < cutoff_date)
        .delete()
    )

    # Delete old logs
    logs_deleted = (
        db.query(models.SystemLog)
        .filter(models.SystemLog.created_at < cutoff_date)
        .delete()
    )

    db.commit()

    return {
        "face_detections_deleted": face_detections_deleted,
        "recordings_deleted": recordings_deleted,
        "logs_deleted": logs_deleted,
    }


# ============================================================================
# PTZ PRESET CRUD OPERATIONS
# ============================================================================


def get_ptz_presets_by_camera(db: Session, camera_id: str) -> List[models.PTZPreset]:
    """Get all PTZ presets for a camera"""
    return (
        db.query(models.PTZPreset)
        .filter(models.PTZPreset.camera_id == camera_id)
        .order_by(models.PTZPreset.preset_number)
        .all()
    )


def get_ptz_preset_by_id(db: Session, preset_id: int) -> Optional[models.PTZPreset]:
    """Get PTZ preset by ID"""
    return db.query(models.PTZPreset).filter(models.PTZPreset.id == preset_id).first()


def get_ptz_preset_by_number(
    db: Session, camera_id: str, preset_number: int
) -> Optional[models.PTZPreset]:
    """Get PTZ preset by camera and preset number"""
    return (
        db.query(models.PTZPreset)
        .filter(
            models.PTZPreset.camera_id == camera_id,
            models.PTZPreset.preset_number == preset_number,
        )
        .first()
    )


def create_ptz_preset(db: Session, camera_id: str, preset_data: dict) -> models.PTZPreset:
    """Create a new PTZ preset"""
    db_preset = models.PTZPreset(camera_id=camera_id, **preset_data)
    db.add(db_preset)
    db.commit()
    db.refresh(db_preset)
    return db_preset


def update_ptz_preset(
    db: Session, preset_id: int, preset_data: dict
) -> Optional[models.PTZPreset]:
    """Update a PTZ preset"""
    db_preset = get_ptz_preset_by_id(db, preset_id)
    if not db_preset:
        return None

    for key, value in preset_data.items():
        if value is not None and hasattr(db_preset, key):
            setattr(db_preset, key, value)

    db_preset.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_preset)
    return db_preset


def delete_ptz_preset(db: Session, preset_id: int) -> bool:
    """Delete a PTZ preset"""
    db_preset = get_ptz_preset_by_id(db, preset_id)
    if not db_preset:
        return False

    db.delete(db_preset)
    db.commit()
    return True


def increment_preset_usage(db: Session, preset_id: int) -> bool:
    """Increment preset usage counter and update last_used_at"""
    db_preset = get_ptz_preset_by_id(db, preset_id)
    if not db_preset:
        return False

    db_preset.usage_count += 1
    db_preset.last_used_at = datetime.utcnow()
    db.commit()
    return True


# ============================================================================
# PTZ PATROL PATTERN CRUD OPERATIONS
# ============================================================================


def get_patrol_patterns_by_camera(
    db: Session, camera_id: str
) -> List[models.PTZPatrolPattern]:
    """Get all patrol patterns for a camera"""
    return (
        db.query(models.PTZPatrolPattern)
        .filter(models.PTZPatrolPattern.camera_id == camera_id)
        .order_by(models.PTZPatrolPattern.created_at.desc())
        .all()
    )


def get_patrol_pattern_by_id(
    db: Session, pattern_id: int
) -> Optional[models.PTZPatrolPattern]:
    """Get patrol pattern by ID"""
    return (
        db.query(models.PTZPatrolPattern)
        .filter(models.PTZPatrolPattern.id == pattern_id)
        .first()
    )


def get_active_patrol_patterns(db: Session, camera_id: str) -> List[models.PTZPatrolPattern]:
    """Get all active patrol patterns for a camera"""
    return (
        db.query(models.PTZPatrolPattern)
        .filter(
            models.PTZPatrolPattern.camera_id == camera_id,
            models.PTZPatrolPattern.is_active == True,
        )
        .all()
    )


def create_patrol_pattern(
    db: Session, camera_id: str, pattern_data: dict
) -> models.PTZPatrolPattern:
    """Create a new patrol pattern"""
    db_pattern = models.PTZPatrolPattern(camera_id=camera_id, **pattern_data)
    db.add(db_pattern)
    db.commit()
    db.refresh(db_pattern)
    return db_pattern


def update_patrol_pattern(
    db: Session, pattern_id: int, pattern_data: dict
) -> Optional[models.PTZPatrolPattern]:
    """Update a patrol pattern"""
    db_pattern = get_patrol_pattern_by_id(db, pattern_id)
    if not db_pattern:
        return None

    for key, value in pattern_data.items():
        if value is not None and hasattr(db_pattern, key):
            setattr(db_pattern, key, value)

    db_pattern.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_pattern)
    return db_pattern


def delete_patrol_pattern(db: Session, pattern_id: int) -> bool:
    """Delete a patrol pattern"""
    db_pattern = get_patrol_pattern_by_id(db, pattern_id)
    if not db_pattern:
        return False

    db.delete(db_pattern)
    db.commit()
    return True


def increment_patrol_run_count(db: Session, pattern_id: int) -> bool:
    """Increment patrol pattern run counter"""
    db_pattern = get_patrol_pattern_by_id(db, pattern_id)
    if not db_pattern:
        return False

    db_pattern.run_count += 1
    db.commit()
    return True


# ============================================================================
# REFRESH TOKEN CRUD OPERATIONS (v3.8.0)
# ============================================================================


def create_refresh_token(
    db: Session,
    user_id: int,
    token: str,
    expires_at: datetime,
    device_info: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> models.RefreshToken:
    """
    Create a new refresh token for a user.

    Args:
        db: Database session
        user_id: User ID
        token: Refresh token string
        expires_at: Token expiration datetime
        device_info: User agent string
        ip_address: Client IP address

    Returns:
        RefreshToken model instance
    """
    db_token = models.RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        device_info=device_info,
        ip_address=ip_address,
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def get_refresh_token(db: Session, token: str) -> Optional[models.RefreshToken]:
    """
    Get refresh token by token string.

    Args:
        db: Database session
        token: Refresh token string

    Returns:
        RefreshToken if found, None otherwise
    """
    return (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token == token)
        .first()
    )


def get_user_refresh_tokens(
    db: Session, user_id: int, active_only: bool = True
) -> List[models.RefreshToken]:
    """
    Get all refresh tokens for a user.

    Args:
        db: Database session
        user_id: User ID
        active_only: Only return non-revoked, non-expired tokens

    Returns:
        List of RefreshToken instances
    """
    query = db.query(models.RefreshToken).filter(
        models.RefreshToken.user_id == user_id
    )

    if active_only:
        query = query.filter(
            models.RefreshToken.revoked == False,
            models.RefreshToken.expires_at > datetime.utcnow(),
        )

    return query.all()


def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    Revoke a refresh token.

    Args:
        db: Database session
        token: Refresh token string

    Returns:
        True if token was revoked, False if not found
    """
    db_token = get_refresh_token(db, token)
    if not db_token:
        return False

    db_token.revoked = True
    db.commit()
    return True


def revoke_all_user_tokens(db: Session, user_id: int) -> int:
    """
    Revoke all refresh tokens for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of tokens revoked
    """
    count = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked == False,
        )
        .update({models.RefreshToken.revoked: True})
    )
    db.commit()
    return count


def delete_expired_tokens(db: Session) -> int:
    """
    Delete all expired refresh tokens (cleanup task).

    Args:
        db: Database session

    Returns:
        Number of tokens deleted
    """
    count = (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.expires_at < datetime.utcnow())
        .delete()
    )
    db.commit()
    return count


def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """
    Get user by ID.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        User if found, None otherwise
    """
    return db.query(models.User).filter(models.User.id == user_id).first()


# ============================================================================
# v3.10.0: OBJECT DETECTION EVENT CRUD OPERATIONS
# ============================================================================


def create_object_detection_event(
    db: Session, event_data: dict
) -> models.ObjectDetectionEvent:
    """Create a new object detection event"""
    db_event = models.ObjectDetectionEvent(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


def get_object_detection_events(
    db: Session,
    camera_id: Optional[str] = None,
    object_class: Optional[str] = None,
    identified_object_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[models.ObjectDetectionEvent]:
    """
    Get object detection events with optional filtering

    Args:
        db: Database session
        camera_id: Filter by camera ID
        object_class: Filter by object class (vehicle, animal, package, person)
        identified_object_id: Filter by identified object
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of object detection events
    """
    query = db.query(models.ObjectDetectionEvent)

    if camera_id:
        query = query.filter(models.ObjectDetectionEvent.camera_id == camera_id)

    if object_class:
        query = query.filter(models.ObjectDetectionEvent.object_class == object_class)

    if identified_object_id is not None:
        query = query.filter(
            models.ObjectDetectionEvent.identified_object_id == identified_object_id
        )

    return (
        query.order_by(models.ObjectDetectionEvent.detected_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_object_detection_events(
    db: Session,
    camera_id: Optional[str] = None,
    object_class: Optional[str] = None,
    identified_object_id: Optional[int] = None,
) -> int:
    """Count object detection events with optional filtering"""
    query = db.query(models.ObjectDetectionEvent)

    if camera_id:
        query = query.filter(models.ObjectDetectionEvent.camera_id == camera_id)

    if object_class:
        query = query.filter(models.ObjectDetectionEvent.object_class == object_class)

    if identified_object_id is not None:
        query = query.filter(
            models.ObjectDetectionEvent.identified_object_id == identified_object_id
        )

    return query.count()


def get_object_detection_event_by_id(
    db: Session, event_id: int
) -> Optional[models.ObjectDetectionEvent]:
    """Get object detection event by ID"""
    return db.query(models.ObjectDetectionEvent).filter(
        models.ObjectDetectionEvent.id == event_id
    ).first()


# ============================================================================
# v3.10.0: IDENTIFIED OBJECT CRUD OPERATIONS
# ============================================================================


def create_identified_object(
    db: Session, object_data: dict
) -> models.IdentifiedObject:
    """Create a new identified object"""
    db_object = models.IdentifiedObject(**object_data)
    db.add(db_object)
    db.commit()
    db.refresh(db_object)
    return db_object


def get_identified_object_by_id(
    db: Session, object_id: str
) -> Optional[models.IdentifiedObject]:
    """Get identified object by object_id (string identifier)"""
    return db.query(models.IdentifiedObject).filter(
        models.IdentifiedObject.object_id == object_id
    ).first()


def get_identified_object_by_pk(
    db: Session, id: int
) -> Optional[models.IdentifiedObject]:
    """Get identified object by primary key"""
    return db.query(models.IdentifiedObject).filter(
        models.IdentifiedObject.id == id
    ).first()


def get_identified_objects(
    db: Session,
    object_class: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 100,
) -> List[models.IdentifiedObject]:
    """
    Get identified objects with optional filtering

    Args:
        db: Database session
        object_class: Filter by object class (vehicle, animal, package)
        is_active: Filter by active status
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return

    Returns:
        List of identified objects
    """
    query = db.query(models.IdentifiedObject)

    if object_class:
        query = query.filter(models.IdentifiedObject.object_class == object_class)

    if is_active is not None:
        query = query.filter(models.IdentifiedObject.is_active == is_active)

    return (
        query.order_by(models.IdentifiedObject.name)
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_identified_objects(
    db: Session,
    object_class: Optional[str] = None,
    is_active: Optional[bool] = True,
) -> int:
    """Count identified objects with optional filtering"""
    query = db.query(models.IdentifiedObject)

    if object_class:
        query = query.filter(models.IdentifiedObject.object_class == object_class)

    if is_active is not None:
        query = query.filter(models.IdentifiedObject.is_active == is_active)

    return query.count()


def update_identified_object(
    db: Session, object_id: str, object_data: dict
) -> Optional[models.IdentifiedObject]:
    """Update identified object"""
    db_object = get_identified_object_by_id(db, object_id)
    if not db_object:
        return None

    for key, value in object_data.items():
        setattr(db_object, key, value)

    db_object.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_object)
    return db_object


def delete_identified_object(db: Session, object_id: str) -> bool:
    """Delete identified object from database"""
    db_object = get_identified_object_by_id(db, object_id)
    if not db_object:
        return False

    db.delete(db_object)
    db.commit()
    return True


def update_identified_object_stats(
    db: Session,
    identified_object_id: int,
    detection_timestamp: datetime
) -> Optional[models.IdentifiedObject]:
    """
    Update identified object statistics after detection

    Updates:
    - detection_count (increment)
    - last_seen_at (latest detection)
    - first_seen_at (if None)

    Args:
        db: Database session
        identified_object_id: Primary key of identified object
        detection_timestamp: Timestamp of detection

    Returns:
        Updated identified object
    """
    db_object = get_identified_object_by_pk(db, identified_object_id)
    if not db_object:
        return None

    # Update stats
    db_object.detection_count += 1
    db_object.last_seen_at = detection_timestamp

    if db_object.first_seen_at is None:
        db_object.first_seen_at = detection_timestamp

    db.commit()
    db.refresh(db_object)
    return db_object
