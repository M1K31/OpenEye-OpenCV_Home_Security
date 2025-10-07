# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Advanced Analytics API Routes
Provides detailed insights and visualizations
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from backend.database.session import SessionLocal
from backend.database import models

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/analytics/activity/hourly")
def get_hourly_activity(
    camera_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get activity breakdown by hour of day
    Returns motion and face detection counts per hour
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # Get face detections by hour
    query = db.query(
        func.extract('hour', models.FaceDetectionEvent.detected_at).label('hour'),
        func.count(models.FaceDetectionEvent.id).label('count')
    ).filter(
        models.FaceDetectionEvent.detected_at >= cutoff
    )
    
    if camera_id:
        query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)
    
    face_data = query.group_by('hour').all()
    
    # Create 24-hour array
    hourly_data = {i: {"hour": i, "faces": 0, "motion": 0} for i in range(24)}
    
    for hour, count in face_data:
        hourly_data[int(hour)]["faces"] = count
    
    # Get recording events (proxy for motion)
    query = db.query(
        func.extract('hour', models.RecordingEvent.started_at).label('hour'),
        func.count(models.RecordingEvent.id).label('count')
    ).filter(
        models.RecordingEvent.started_at >= cutoff,
        models.RecordingEvent.motion_detected == True
    )
    
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)
    
    motion_data = query.group_by('hour').all()
    
    for hour, count in motion_data:
        hourly_data[int(hour)]["motion"] = count
    
    return {
        "days_analyzed": days,
        "camera_id": camera_id,
        "hourly_breakdown": list(hourly_data.values())
    }


@router.get("/analytics/summary")
def get_analytics_summary(
    camera_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive analytics summary
    """
    # Last 24 hours
    last_24h = datetime.utcnow() - timedelta(hours=24)
    
    # Last 7 days
    last_7d = datetime.utcnow() - timedelta(days=7)
    
    # Last 30 days
    last_30d = datetime.utcnow() - timedelta(days=30)
    
    # Build queries
    face_query_24h = db.query(func.count(models.FaceDetectionEvent.id)).filter(
        models.FaceDetectionEvent.detected_at >= last_24h
    )
    face_query_7d = db.query(func.count(models.FaceDetectionEvent.id)).filter(
        models.FaceDetectionEvent.detected_at >= last_7d
    )
    face_query_30d = db.query(func.count(models.FaceDetectionEvent.id)).filter(
        models.FaceDetectionEvent.detected_at >= last_30d
    )
    
    if camera_id:
        face_query_24h = face_query_24h.filter(models.FaceDetectionEvent.camera_id == camera_id)
        face_query_7d = face_query_7d.filter(models.FaceDetectionEvent.camera_id == camera_id)
        face_query_30d = face_query_30d.filter(models.FaceDetectionEvent.camera_id == camera_id)
    
    return {
        "camera_id": camera_id,
        "faces_last_24h": face_query_24h.scalar(),
        "faces_last_7d": face_query_7d.scalar(),
        "faces_last_30d": face_query_30d.scalar(),
        "generated_at": datetime.utcnow().isoformat()
    }
