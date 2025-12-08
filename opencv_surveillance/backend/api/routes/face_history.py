# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Face Detection History and Analytics API Routes
Provides endpoints for querying historical face detection data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from backend.database.session import SessionLocal
from backend.database import crud, models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.pagination import PaginatedResponse
from pydantic import BaseModel

router = APIRouter()


# Pydantic Models for Responses
class FaceDetectionEventResponse(BaseModel):
    id: int
    camera_id: str
    person_name: str
    confidence: float
    detected_at: datetime
    location: dict
    motion_detected: bool
    recording_path: Optional[str]

    class Config:
        from_attributes = True


class FaceStatisticsResponse(BaseModel):
    total_detections: int
    unique_people: int
    most_detected_person: Optional[str]
    time_period_days: int


class RecordingEventResponse(BaseModel):
    id: int
    camera_id: str
    recording_path: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    faces_detected: int
    known_faces_detected: int

    class Config:
        from_attributes = True


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/history",
            response_model=PaginatedResponse[FaceDetectionEventResponse])
def get_detection_history(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    person_name: Optional[str] = Query(None, description="Filter by person name"),
    hours: int = Query(24, description="Number of hours to look back"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Get recent face detection events with optional filters and pagination

    Performance optimizations:
    - Uses indexed queries on camera_id/person_name and detected_at
    - Paginated results (default 50, max 1000)
    - Efficient sorting by detection time

    Args:
        - **camera_id**: Optional camera ID to filter by
        - **person_name**: Optional person name to filter by
        - **hours**: Number of hours to look back (default: 24)
        - **page**: Page number (default: 1)
        - **page_size**: Items per page (default: 50, max: 1000)

    Returns:
        PaginatedResponse with detection events and pagination metadata
    """
    try:
        # Build query with filters (apply filters FIRST for performance)
        query = db.query(models.FaceDetectionEvent)

        # Time filter
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        query = query.filter(models.FaceDetectionEvent.detected_at >= cutoff_time)

        # Camera filter (uses idx_face_camera_time index)
        if camera_id:
            query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)

        # Person filter (uses idx_face_person_time index)
        if person_name:
            query = query.filter(models.FaceDetectionEvent.person_name == person_name)

        # Order by most recent
        query = query.order_by(models.FaceDetectionEvent.detected_at.desc())

        # Get total count (before pagination)
        total_count = db.query(models.FaceDetectionEvent).count()

        # Apply pagination (this counts the filtered results, not the entire table)
        events, filtered_count, total_pages = paginate(query, page=page, page_size=page_size)

        # Format response
        results = []
        for event in events:
            results.append(
                FaceDetectionEventResponse(
                    id=event.id,
                    camera_id=event.camera_id,
                    person_name=event.person_name,
                    confidence=event.confidence,
                    detected_at=event.detected_at,
                    location={
                        "top": event.location_top,
                        "right": event.location_right,
                        "bottom": event.location_bottom,
                        "left": event.location_left,
                    },
                    motion_detected=event.motion_detected,
                    recording_path=event.recording_path,
                )
            )

        return {
            "data": results,
            "pagination": {
                "total": total_count,
                "filtered": filtered_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_more": page < total_pages
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/statistics", response_model=FaceStatisticsResponse)
def get_detection_statistics(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    days: int = Query(7, description="Number of days for statistics"),
    db: Session = Depends(get_db),
):
    """
    Get face detection statistics for the specified time period

    - **camera_id**: Optional camera ID to filter by
    - **days**: Number of days to analyze (default: 7)
    """
    try:
        stats = crud.get_face_detection_statistics(
            db=db, camera_id=camera_id, days=days
        )

        return FaceStatisticsResponse(**stats)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/person/{person_name}",
            response_model=List[FaceDetectionEventResponse])
def get_person_history(
    person_name: str,
    limit: int = Query(100, description="Maximum number of results", le=500),
    db: Session = Depends(get_db),
):
    """
    Get detection history for a specific person

    - **person_name**: Name of the person to get history for
    - **limit**: Maximum number of results (default: 100, max: 500)
    """
    try:
        events = crud.get_person_detection_history(
            db=db, person_name=person_name, limit=limit
        )

        results = []
        for event in events:
            results.append(
                FaceDetectionEventResponse(
                    id=event.id,
                    camera_id=event.camera_id,
                    person_name=event.person_name,
                    confidence=event.confidence,
                    detected_at=event.detected_at,
                    location={
                        "top": event.location_top,
                        "right": event.location_right,
                        "bottom": event.location_bottom,
                        "left": event.location_left,
                    },
                    motion_detected=event.motion_detected,
                    recording_path=event.recording_path,
                )
            )

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/recordings", response_model=List[RecordingEventResponse])
def get_recording_history(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    limit: int = Query(20, description="Maximum number of results", le=100),
    db: Session = Depends(get_db),
):
    """
    Get recent recording events

    - **camera_id**: Optional camera ID to filter by
    - **limit**: Maximum number of results (default: 20, max: 100)
    """
    try:
        recordings = crud.get_recent_recordings(
            db=db, camera_id=camera_id, limit=limit
        )

        return [RecordingEventResponse.from_orm(r) for r in recordings]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/cleanup")
def cleanup_old_data(
        days_to_keep: int = Query(
            30,
            description="Number of days of data to keep"),
    db: Session = Depends(get_db),
):
    """
    Clean up old events from the database

    - **days_to_keep**: Number of days of data to retain (default: 30)

    **Warning**: This will permanently delete old data
    """
    try:
        if days_to_keep < 7:
            raise HTTPException(
                status_code=400, detail="Cannot delete data newer than 7 days"
            )

        result = crud.cleanup_old_events(db=db, days_to_keep=days_to_keep)

        return {"message": "Cleanup completed successfully", **result}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/timeline")
def get_detection_timeline(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    hours: int = Query(24, description="Number of hours to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get a timeline of face detections grouped by hour

    - **camera_id**: Optional camera ID to filter by
    - **hours**: Number of hours to analyze (default: 24)
    """
    try:
        events = crud.get_recent_face_detections(
            db=db, camera_id=camera_id, limit=1000, hours=hours
        )

        # Group by hour
        timeline = {}
        for event in events:
            hour_key = event.detected_at.strftime("%Y-%m-%d %H:00")

            if hour_key not in timeline:
                timeline[hour_key] = {
                    "total_detections": 0,
                    "unique_people": set(),
                    "known_faces": 0,
                    "unknown_faces": 0,
                }

            timeline[hour_key]["total_detections"] += 1
            timeline[hour_key]["unique_people"].add(event.person_name)

            if event.person_name == "Unknown":
                timeline[hour_key]["unknown_faces"] += 1
            else:
                timeline[hour_key]["known_faces"] += 1

        # Convert sets to counts
        result = []
        for hour, data in sorted(timeline.items()):
            result.append(
                {
                    "hour": hour,
                    "total_detections": data["total_detections"],
                    "unique_people": len(data["unique_people"]),
                    "known_faces": data["known_faces"],
                    "unknown_faces": data["unknown_faces"],
                }
            )

        return {"timeline": result, "total_hours": len(result)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
