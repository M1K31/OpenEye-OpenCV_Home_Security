
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
CRUD operations for face detection events and related data
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from backend.database import models


def create_face_detection_event(
    db: Session,
    camera_id: str,
    person_name: str,
    confidence: float,
    location: Dict[str, int],
    motion_detected: bool = False,
    recording_path: Optional[str] = None,
    snapshot_path: Optional[str] = None
) -> models.FaceDetectionEvent:
    """Create a new face detection event in the database"""
    
    event = models.FaceDetectionEvent(
        camera_id=camera_id,
        person_name=person_name,
        confidence=confidence,
        location_top=location.get('top'),
        location_right=location.get('right'),
        location_bottom=location.get('bottom'),
        location_left=location.get('left'),
        motion_detected=motion_detected,
        recording_path=recording_path,
        snapshot_path=snapshot_path,
        detected_at=datetime.utcnow()
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_recent_face_detections(
    db: Session,
    camera_id: Optional[str] = None,
    person_name: Optional[str] = None,
    limit: int = 50,
    hours: int = 24
) -> List[models.FaceDetectionEvent]:
    """Get recent face detection events with optional filters"""
    
    query = db.query(models.FaceDetectionEvent)
    
    # Filter by time
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    query = query.filter(models.FaceDetectionEvent.detected_at >= time_threshold)
    
    # Optional filters
    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)
    
    if person_name:
        query = query.filter(models.FaceDetectionEvent.person_name == person_name)
    
    # Order by most recent and limit
    query = query.order_by(desc(models.FaceDetectionEvent.detected_at))
    query = query.limit(limit)
    
    return query.all()


def get_face_detection_statistics(
    db: Session,
    camera_id: Optional[str] = None,
    days: int = 7
) -> Dict:
    """Get statistics about face detections"""
    
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
        models.FaceDetectionEvent.person_name != 'Unknown'
    )
    
    if camera_id:
        unique_people = unique_people.filter(
            models.FaceDetectionEvent.camera_id == camera_id
        )
    
    unique_people_count = unique_people.scalar()
    
    # Get most detected person
    most_detected = query.filter(
        models.FaceDetectionEvent.person_name != 'Unknown'
    ).group_by(
        models.FaceDetectionEvent.person_name
    ).order_by(
        desc(func.count(models.FaceDetectionEvent.person_name))
    ).first()
    
    return {
        'total_detections': total_detections,
        'unique_people': unique_people_count,
        'most_detected_person': most_detected.person_name if most_detected else None,
        'time_period_days': days
    }


def get_person_detection_history(
    db: Session,
    person_name: str,
    limit: int = 100
) -> List[models.FaceDetectionEvent]:
    """Get detection history for a specific person"""
    
    return db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.person_name == person_name
    ).order_by(
        desc(models.FaceDetectionEvent.detected_at)
    ).limit(limit).all()


def create_recording_event(
    db: Session,
    camera_id: str,
    recording_path: str,
    started_at: datetime
) -> models.RecordingEvent:
    """Create a new recording event"""
    
    event = models.RecordingEvent(
        camera_id=camera_id,
        recording_path=recording_path,
        started_at=started_at,
        motion_detected=True
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_recording_event(
    db: Session,
    event_id: int,
    ended_at: datetime,
    duration_seconds: float,
    faces_detected: int = 0,
    known_faces_detected: int = 0,
    file_size_bytes: Optional[int] = None
) -> models.RecordingEvent:
    """Update a recording event when it ends"""
    
    event = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == event_id
    ).first()
    
    if event:
        event.ended_at = ended_at
        event.duration_seconds = duration_seconds
        event.faces_detected = faces_detected
        event.known_faces_detected = known_faces_detected
        event.file_size_bytes = file_size_bytes
        
        db.commit()
        db.refresh(event)
    
    return event


def get_recent_recordings(
    db: Session,
    camera_id: Optional[str] = None,
    limit: int = 20
) -> List[models.RecordingEvent]:
    """Get recent recording events"""
    
    query = db.query(models.RecordingEvent)
    
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)
    
    return query.order_by(
        desc(models.RecordingEvent.started_at)
    ).limit(limit).all()


def create_system_log(
    db: Session,
    log_level: str,
    component: str,
    message: str,
    details: Optional[str] = None
) -> models.SystemLog:
    """Create a system log entry"""
    
    log = models.SystemLog(
        log_level=log_level,
        component=component,
        message=message,
        details=details,
        created_at=datetime.utcnow()
    )
    
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_system_logs(
    db: Session,
    log_level: Optional[str] = None,
    component: Optional[str] = None,
    hours: int = 24,
    limit: int = 100
) -> List[models.SystemLog]:
    """Get system logs with optional filters"""
    
    time_threshold = datetime.utcnow() - timedelta(hours=hours)
    
    query = db.query(models.SystemLog).filter(
        models.SystemLog.created_at >= time_threshold
    )
    
    if log_level:
        query = query.filter(models.SystemLog.log_level == log_level)
    
    if component:
        query = query.filter(models.SystemLog.component == component)
    
    return query.order_by(
        desc(models.SystemLog.created_at)
    ).limit(limit).all()


def cleanup_old_events(
    db: Session,
    days_to_keep: int = 30
) -> Dict[str, int]:
    """Clean up old events from the database"""
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    # Delete old face detections
    face_detections_deleted = db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.detected_at < cutoff_date
    ).delete()
    
    # Delete old recordings
    recordings_deleted = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.started_at < cutoff_date
    ).delete()
    
    # Delete old logs
    logs_deleted = db.query(models.SystemLog).filter(
        models.SystemLog.created_at < cutoff_date
    ).delete()
    
    db.commit()
    
    return {
        'face_detections_deleted': face_detections_deleted,
        'recordings_deleted': recordings_deleted,
        'logs_deleted': logs_deleted
    }