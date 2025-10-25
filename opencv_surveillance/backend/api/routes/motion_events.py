# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
API routes for Motion Detection Events
Separate from face detection - tracks ALL motion events including those without faces
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel
import zipfile
import io
import os

from backend.database.session import get_db
from backend.database import models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.motion import (
    MotionEventResponse,
    MotionEventListResponse,
    MotionEventCreate
)

router = APIRouter()


@router.get("/motion-events/", response_model=MotionEventListResponse)
def list_motion_events(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    start_date: Optional[datetime] = Query(None, description="Filter events after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter events before this date"),
    has_faces: Optional[bool] = Query(None, description="Filter by face detection presence"),
    db: Session = Depends(get_db)
):
    """
    Get list of motion detection events with filtering and pagination

    Performance optimizations:
    - Uses indexed queries on camera_id and detected_at
    - Paginated results (default 50, max 1000)
    - Efficient sorting by detection time

    This endpoint returns ALL motion events, including:
    - Motion events WITH face detection
    - Motion events WITHOUT face detection (motion-only)

    Use this for timeline views that need to show all activity.
    """
    query = db.query(models.MotionDetectionEvent)

    # Apply filters (uses idx_motion_camera_time index)
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)

    if start_date:
        query = query.filter(models.MotionDetectionEvent.detected_at >= start_date)

    if end_date:
        query = query.filter(models.MotionDetectionEvent.detected_at <= end_date)

    if has_faces is not None:
        if has_faces:
            query = query.filter(models.MotionDetectionEvent.faces_detected > 0)
        else:
            query = query.filter(models.MotionDetectionEvent.faces_detected == 0)

    # Order by most recent (uses idx_motion_detected_at index)
    query = query.order_by(models.MotionDetectionEvent.detected_at.desc())

    # Apply pagination
    events, total, total_pages = paginate(query, page=page, page_size=page_size)

    # Calculate offset for backward compatibility
    offset = (page - 1) * page_size

    return MotionEventListResponse(
        events=events,
        total=total,
        limit=page_size,
        offset=offset,
        has_more=page < total_pages
    )


@router.get("/motion-events/{event_id}", response_model=MotionEventResponse)
def get_motion_event(event_id: int, db: Session = Depends(get_db)):
    """
    Get specific motion detection event by ID
    """
    event = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.id == event_id
    ).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Motion event {event_id} not found"
        )
    
    return event


@router.delete("/motion-events/{event_id}", status_code=status.HTTP_200_OK)
def delete_motion_event(event_id: int, db: Session = Depends(get_db)):
    """
    Delete motion detection event and associated snapshot file
    
    This will:
    1. Delete the snapshot image file (if exists)
    2. Remove the database record
    
    Note: This does NOT delete associated face detection records or recordings,
    only the motion event record itself.
    """
    event = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.id == event_id
    ).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Motion event {event_id} not found"
        )
    
    # Delete snapshot file if it exists
    snapshot_deleted = False
    if event.snapshot_path:
        snapshot_file = Path(event.snapshot_path)
        if snapshot_file.exists():
            try:
                snapshot_file.unlink()
                snapshot_deleted = True
            except Exception as e:
                print(f"Warning: Could not delete snapshot file {event.snapshot_path}: {e}")
    
    # Delete from database
    db.delete(event)
    db.commit()
    
    return {
        "message": "Motion event deleted successfully",
        "id": event_id,
        "snapshot_deleted": snapshot_deleted
    }


@router.post("/motion-events/cleanup", status_code=status.HTTP_200_OK)
def cleanup_old_motion_events(
    days: int = Query(30, ge=1, le=365, description="Delete events older than N days"),
    camera_id: Optional[str] = Query(None, description="Limit cleanup to specific camera"),
    db: Session = Depends(get_db)
):
    """
    Clean up old motion detection events
    
    This will:
    1. Delete motion events older than specified days
    2. Delete associated snapshot files
    3. Return statistics on what was deleted
    
    Use this for periodic maintenance to prevent database bloat.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Build query
    query = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.detected_at < cutoff_date
    )
    
    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)
    
    # Get events to delete (for file cleanup)
    events_to_delete = query.all()
    
    # Delete snapshot files
    deleted_snapshots = 0
    failed_snapshots = 0
    for event in events_to_delete:
        if event.snapshot_path:
            snapshot_file = Path(event.snapshot_path)
            if snapshot_file.exists():
                try:
                    snapshot_file.unlink()
                    deleted_snapshots += 1
                except Exception as e:
                    print(f"Warning: Could not delete snapshot {event.snapshot_path}: {e}")
                    failed_snapshots += 1
    
    # Delete from database
    deleted_count = query.delete()
    db.commit()
    
    return {
        "message": f"Cleaned up {deleted_count} motion events older than {days} days",
        "deleted_events": deleted_count,
        "deleted_snapshots": deleted_snapshots,
        "failed_snapshots": failed_snapshots,
        "cutoff_date": cutoff_date.isoformat(),
        "camera_id": camera_id or "all cameras"
    }


@router.get("/motion-events/statistics/summary", status_code=status.HTTP_200_OK)
def get_motion_statistics(
    days: int = Query(7, ge=1, le=365, description="Statistics period in days"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    db: Session = Depends(get_db)
):
    """
    Get motion detection statistics and analytics (optimized with database aggregation)

    Returns:
    - Total motion events
    - Events with face detection
    - Events without face detection (motion-only)
    - Per-camera breakdown
    - Daily activity pattern
    """
    from sqlalchemy import func, case

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Build query
    query = db.query(models.MotionDetectionEvent).filter(
        models.MotionDetectionEvent.detected_at >= cutoff_date
    )

    if camera_id:
        query = query.filter(models.MotionDetectionEvent.camera_id == camera_id)

    # Use database aggregation for overall statistics
    stats = db.query(
        func.count(models.MotionDetectionEvent.id).label('total_events'),
        func.sum(case((models.MotionDetectionEvent.faces_detected > 0, 1), else_=0)).label('events_with_faces'),
    ).filter(
        models.MotionDetectionEvent.detected_at >= cutoff_date
    )

    if camera_id:
        stats = stats.filter(models.MotionDetectionEvent.camera_id == camera_id)

    result = stats.first()
    total_events = result.total_events or 0
    events_with_faces = result.events_with_faces or 0
    events_without_faces = total_events - events_with_faces

    # For camera breakdown and daily activity, we still need to load events
    # but only once
    events = query.all()
    
    # Per-camera breakdown
    camera_breakdown = {}
    for event in events:
        if event.camera_id not in camera_breakdown:
            camera_breakdown[event.camera_id] = {
                "total": 0,
                "with_faces": 0,
                "without_faces": 0,
                "with_snapshot": 0
            }
        camera_breakdown[event.camera_id]["total"] += 1
        if event.faces_detected > 0:
            camera_breakdown[event.camera_id]["with_faces"] += 1
        else:
            camera_breakdown[event.camera_id]["without_faces"] += 1
        if event.snapshot_path:
            camera_breakdown[event.camera_id]["with_snapshot"] += 1
    
    # Daily activity (events per day)
    daily_activity = {}
    for event in events:
        day = event.detected_at.date().isoformat()
        if day not in daily_activity:
            daily_activity[day] = 0
        daily_activity[day] += 1
    
    return {
        "period_days": days,
        "total_motion_events": total_events,
        "events_with_faces": events_with_faces,
        "events_without_faces": events_without_faces,
        "percentage_with_faces": round(events_with_faces / total_events * 100, 2) if total_events > 0 else 0,
        "camera_breakdown": camera_breakdown,
        "daily_activity": daily_activity,
        "start_date": cutoff_date.isoformat(),
        "end_date": datetime.utcnow().isoformat()
    }


class SnapshotExportRequest(BaseModel):
    """Request model for exporting snapshots as ZIP"""
    event_ids: List[int]


@router.post("/snapshots/export")
def export_snapshots_zip(
    request: SnapshotExportRequest,
    db: Session = Depends(get_db)
):
    """
    Export multiple snapshots as a ZIP file
    
    Args:
        request: SnapshotExportRequest containing list of motion event IDs
        
    Returns:
        StreamingResponse with ZIP file containing snapshot images
    """
    if not request.event_ids:
        raise HTTPException(status_code=400, detail="No event IDs provided")
    
    if len(request.event_ids) > 500:
        raise HTTPException(
            status_code=400, 
            detail="Cannot export more than 500 snapshots at once"
        )
    
    # Fetch motion events from database
    events = (
        db.query(models.MotionDetectionEvent)
        .filter(models.MotionDetectionEvent.id.in_(request.event_ids))
        .filter(models.MotionDetectionEvent.snapshot_path.isnot(None))
        .all()
    )
    
    if not events:
        raise HTTPException(status_code=404, detail="No snapshots found for given event IDs")
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for event in events:
            snapshot_path = event.snapshot_path
            
            # Handle different path formats
            if not os.path.isabs(snapshot_path):
                # Try relative paths from common directories
                possible_paths = [
                    snapshot_path,
                    os.path.join("data/snapshots", os.path.basename(snapshot_path)),
                    os.path.join("snapshots", os.path.basename(snapshot_path)),
                ]
                
                snapshot_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        snapshot_path = path
                        break
            
            # Skip if file doesn't exist
            if not snapshot_path or not os.path.exists(snapshot_path):
                continue
            
            # Create a safe filename with metadata
            timestamp = event.detected_at.strftime("%Y%m%d_%H%M%S")
            filename = f"{event.camera_id}_{timestamp}_{event.id}.jpg"
            
            # Add file to ZIP
            zip_file.write(snapshot_path, arcname=filename)
    
    # Reset buffer position
    zip_buffer.seek(0)
    
    # Generate ZIP filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"snapshots_{timestamp}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )
