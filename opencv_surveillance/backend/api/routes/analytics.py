# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Advanced Analytics API Routes
Provides detailed insights and visualizations
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta
import hashlib

from backend.database.session import SessionLocal
from backend.database.utils import get_db_context
from backend.database import models
from backend.core.performance import timed_lru_cache

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@timed_lru_cache(seconds=300, maxsize=32)  # Cache for 5 minutes
def _calculate_hourly_activity(camera_id: Optional[str], days: int, cutoff_iso: str):
    """
    Cached helper function for hourly activity calculation

    Uses ISO string for cutoff to make it hashable for caching
    """
    # FIXED: Use context manager to prevent session leak (v3.6.0.1)
    with get_db_context() as db:
        cutoff = datetime.fromisoformat(cutoff_iso)

        # Get face detections by hour
        query = db.query(
            func.extract("hour", models.FaceDetectionEvent.detected_at).label("hour"),
            func.count(models.FaceDetectionEvent.id).label("count"),
        ).filter(models.FaceDetectionEvent.detected_at >= cutoff)

        if camera_id:
            query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

        face_data = query.group_by("hour").all()

        # Create 24-hour array
        hourly_data = {i: {"hour": i, "faces": 0, "motion": 0} for i in range(24)}

        for hour, count in face_data:
            hourly_data[int(hour)]["faces"] = count

        # Get recording events (proxy for motion)
        query = db.query(
            func.extract("hour", models.RecordingEvent.started_at).label("hour"),
            func.count(models.RecordingEvent.id).label("count"),
        ).filter(
            models.RecordingEvent.started_at >= cutoff,
            models.RecordingEvent.motion_detected.is_(True),
        )

        if camera_id:
            query = query.filter(models.RecordingEvent.camera_id == camera_id)

        motion_data = query.group_by("hour").all()

        for hour, count in motion_data:
            hourly_data[int(hour)]["motion"] = count

        return list(hourly_data.values())


@router.get("/analytics/activity/hourly")
def get_hourly_activity(
    camera_id: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """
    Get activity breakdown by hour of day (cached for 5 minutes)
    Returns motion and face detection counts per hour

    Performance: Results are cached for 5 minutes per camera/days combination
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    hourly_breakdown = _calculate_hourly_activity(camera_id, days, cutoff.isoformat())

    return {
        "days_analyzed": days,
        "camera_id": camera_id,
        "hourly_breakdown": hourly_breakdown,
        "cached": True,
    }


@timed_lru_cache(seconds=180, maxsize=16)  # Cache for 3 minutes
def _calculate_analytics_summary(camera_id: Optional[str], last_24h_iso: str, last_7d_iso: str, last_30d_iso: str):
    """
    Cached helper function for analytics summary calculation

    Uses ISO strings for dates to make them hashable for caching
    """
    # FIXED: Use context manager to prevent session leak (v3.6.0.1)
    with get_db_context() as db:
        last_24h = datetime.fromisoformat(last_24h_iso)
        last_7d = datetime.fromisoformat(last_7d_iso)
        last_30d = datetime.fromisoformat(last_30d_iso)

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
            face_query_24h = face_query_24h.filter(
                models.FaceDetectionEvent.camera_id == camera_id
            )
            face_query_7d = face_query_7d.filter(
                models.FaceDetectionEvent.camera_id == camera_id
            )
            face_query_30d = face_query_30d.filter(
                models.FaceDetectionEvent.camera_id == camera_id
            )

        return {
            "faces_last_24h": face_query_24h.scalar(),
            "faces_last_7d": face_query_7d.scalar(),
            "faces_last_30d": face_query_30d.scalar(),
        }


@router.get("/analytics/summary")
def get_analytics_summary(
    camera_id: Optional[str] = Query(None), db: Session = Depends(get_db)
):
    """
    Get comprehensive analytics summary (cached for 3 minutes)

    Performance: Results are cached for 3 minutes per camera
    """
    # Calculate time ranges
    last_24h = datetime.utcnow() - timedelta(hours=24)
    last_7d = datetime.utcnow() - timedelta(days=7)
    last_30d = datetime.utcnow() - timedelta(days=30)

    # Get cached results
    summary = _calculate_analytics_summary(
        camera_id,
        last_24h.isoformat(),
        last_7d.isoformat(),
        last_30d.isoformat()
    )

    return {
        "camera_id": camera_id,
        **summary,
        "generated_at": datetime.utcnow().isoformat(),
        "cached": True,
    }
