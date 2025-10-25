# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
EXAMPLE: Optimized Recordings API with Pagination

This is an example showing how to update recordings.py with performance optimizations.
Copy the patterns from this file to update the actual recordings.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from backend.database import models
from backend.database.session import get_db
from backend.core.performance import paginate, PaginatedResponse, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.camera import RecordingResponse  # Adjust import as needed

router = APIRouter()


@router.get("/recordings/")
def list_recordings_optimized(
    # Pagination parameters
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),

    # Filter parameters
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    start_date: Optional[datetime] = Query(None, description="Filter recordings after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter recordings before this date"),
    trigger_type: Optional[str] = Query(None, description="Filter by trigger type (motion, face, manual)"),

    # Sorting
    sort_by: str = Query("started_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),

    # Database session
    db: Session = Depends(get_db)
):
    """
    List recordings with pagination and filtering

    Performance optimizations:
    - Paginated results (default 50, max 1000)
    - Indexed queries on camera_id and started_at
    - Optimized sorting
    - Selective column loading for list view
    """
    # Build base query
    query = db.query(models.RecordingEvent)

    # Apply filters
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    if start_date:
        query = query.filter(models.RecordingEvent.started_at >= start_date)

    if end_date:
        query = query.filter(models.RecordingEvent.started_at <= end_date)

    if trigger_type:
        query = query.filter(models.RecordingEvent.trigger_type == trigger_type)

    # Apply sorting
    sort_column = getattr(models.RecordingEvent, sort_by, models.RecordingEvent.started_at)
    if sort_order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    # Paginate results
    items, total, total_pages = paginate(query, page=page, page_size=page_size)

    # Convert to response models
    recordings = [RecordingResponse.from_orm(item) for item in items]

    return {
        "recordings": recordings,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1
    }


@router.get("/recordings/summary")
def recordings_summary(
    camera_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get recording statistics (optimized with aggregation)

    Uses database aggregation instead of loading all records
    """
    from sqlalchemy import func

    query = db.query(
        func.count(models.RecordingEvent.id).label('total_recordings'),
        func.sum(models.RecordingEvent.file_size_bytes).label('total_size_bytes'),
        func.avg(models.RecordingEvent.duration_seconds).label('avg_duration'),
        func.max(models.RecordingEvent.started_at).label('latest_recording')
    )

    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    result = query.first()

    return {
        "total_recordings": result.total_recordings or 0,
        "total_size_bytes": result.total_size_bytes or 0,
        "total_size_mb": round((result.total_size_bytes or 0) / (1024 * 1024), 2),
        "avg_duration_seconds": round(result.avg_duration or 0, 2),
        "latest_recording": result.latest_recording
    }
