# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Recording Management and Playback API Routes
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from pathlib import Path
import os
import json
import zipfile
import io
import tempfile
import logging

from backend.database.session import SessionLocal, get_db
from backend.core.auth import get_current_active_user, get_current_user_media
from backend.database import models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.core.paths import paths
from backend.api.schemas.pagination import PaginatedResponse
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


# Security: Path Traversal Protection Helper
def safe_file_response(
    file_path: str,
    allowed_dir: Path,
    media_type: str = "application/octet-stream",
    filename: Optional[str] = None
) -> FileResponse:
    """
    Safely serve a file with path traversal protection

    Args:
        file_path: Path to file (from database - can be relative or absolute)
        allowed_dir: Directory that file must be within
        media_type: MIME type for response
        filename: Optional filename for download

    Returns:
        FileResponse if file is safe to serve

    Raises:
        HTTPException: If file is outside allowed directory or doesn't exist
    """
    try:
        # Use PathManager to properly resolve relative paths (stored relative to PROJECT_ROOT)
        full_path = paths.resolve_path(file_path)
        allowed_dir_resolved = allowed_dir.resolve()

        # Security check: Ensure file is within allowed directory
        if not str(full_path).startswith(str(allowed_dir_resolved)):
            logger.warning(
                f"Path traversal attempt blocked: {file_path} -> {full_path} not in {allowed_dir_resolved}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: File path not in allowed directory"
            )

        # Check file exists and is a file (not directory)
        if not full_path.exists():
            logger.warning(f"Recording file not found: {full_path} (original path: {file_path})")
            raise HTTPException(status_code=404, detail=f"File not found: {full_path.name}")

        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Serve file safely
        if not filename:
            filename = full_path.name

        return FileResponse(
            path=str(full_path),
            media_type=media_type,
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")


# Pydantic Models


class RecordingResponse(BaseModel):
    id: int = Field(..., serialization_alias="recording_id", description="Recording ID")
    camera_id: str
    recording_path: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[float]
    file_size_bytes: Optional[int]
    faces_detected: int
    known_faces_detected: int
    thumbnail_path: Optional[str]

    class Config:
        from_attributes = True
        populate_by_name = True  # Allow both 'id' and 'recording_id'


class RecordingSearchRequest(BaseModel):
    camera_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    has_faces: Optional[bool] = None
    min_duration: Optional[int] = None
    limit: int = 50


# Dependency


# get_db is imported from backend.database.session rather than redefined here:
# FastAPI matches dependency_overrides by function identity, so a module-local
# copy is a *different* dependency and silently escapes any override (and used a
# separate session provider from the rest of the app).


# Endpoints


@router.get("/recordings/", response_model=PaginatedResponse[RecordingResponse])
def list_recordings(
    camera_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_faces: Optional[bool] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
):
    """
    List recordings with optional filters and pagination

    Performance optimizations:
    - Uses indexed queries on camera_id and started_at
    - Paginated results (default 50, max 1000)
    - Efficient sorting
    - Optimized COUNT queries: single query when no filters applied (v3.11.7)

    Returns:
        PaginatedResponse with recordings data and pagination metadata
    """
    from backend.core.performance import paginate_with_metadata

    # Build base query (unfiltered)
    base_query = db.query(models.RecordingEvent)
    query = db.query(models.RecordingEvent)

    # Track if any filters are applied
    has_filters = False

    # Apply filters (uses idx_recording_camera_time index)
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)
        has_filters = True

    if start_date:
        # Parse ISO format date string (handles timezone-aware strings)
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        # Ensure timezone-aware for comparison
        if start_dt.tzinfo is None:
            from datetime import timezone
            start_dt = start_dt.replace(tzinfo=timezone.utc)
        query = query.filter(models.RecordingEvent.started_at >= start_dt)
        has_filters = True

    if end_date:
        # Parse ISO format date string (handles timezone-aware strings)
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        # Ensure timezone-aware for comparison
        if end_dt.tzinfo is None:
            from datetime import timezone
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        query = query.filter(models.RecordingEvent.started_at <= end_dt)
        has_filters = True

    if has_faces is not None:
        if has_faces:
            query = query.filter(models.RecordingEvent.faces_detected > 0)
        else:
            query = query.filter(models.RecordingEvent.faces_detected == 0)
        has_filters = True

    # Order by most recent (uses idx_recording_started_at index)
    query = query.order_by(models.RecordingEvent.started_at.desc())

    # Apply optimized pagination (single COUNT when no filters)
    return paginate_with_metadata(
        query=query,
        base_query=base_query,
        page=page,
        page_size=page_size,
        has_filters=has_filters
    )


@router.get("/recordings/{recording_id}")
def get_recording_details(recording_id: int, db: Session = Depends(get_db),
                          current_user = Depends(get_current_active_user)):
    """
    Get detailed information about a recording including metadata
    """
    recording = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Load metadata file if exists
    metadata = None
    metadata_path = recording.recording_path.replace(".mp4", "_metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

    return {"recording": RecordingResponse.from_orm(
        recording), "metadata": metadata}


@router.get("/recordings/{recording_id}/download")
def download_recording(recording_id: int, db: Session = Depends(get_db),
                       current_user = Depends(get_current_user_media)):
    """
    Download a recording file (with path traversal protection)
    """
    recording = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Use safe file serving with path validation
    return safe_file_response(
        file_path=recording.recording_path,
        allowed_dir=paths.recordings_dir,
        media_type="video/mp4",
        filename=Path(recording.recording_path).name
    )


@router.get("/recordings/{recording_id}/stream")
def stream_recording(recording_id: int, db: Session = Depends(get_db),
                     current_user = Depends(get_current_user_media)):
    """
    Stream a recording file (with path traversal protection)
    """
    recording = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Security: Validate file path before streaming
    try:
        # Through PathManager, not Path().resolve(): stored paths are relative
        # on older installs, and resolving those against the working directory
        # pointed them wherever the process happened to be started — which then
        # failed the containment check below and returned 403 for a file that was
        # perfectly legitimate. /download already went through PathManager; this
        # route was left behind.
        full_path = paths.resolve_path(recording.recording_path)
        allowed_dir = paths.recordings_dir.resolve()

        if not str(full_path).startswith(str(allowed_dir)):
            logger.warning(
                f"Path traversal attempt blocked in stream: {recording.recording_path}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: File path not in allowed directory"
            )

        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="Recording file not found")

        def iterfile():
            with open(str(full_path), mode="rb") as file_like:
                yield from file_like

        return StreamingResponse(iterfile(), media_type="video/mp4")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming recording {recording_id}: {e}")
        raise HTTPException(status_code=500, detail="Error streaming file")


@router.delete("/recordings/{recording_id}")
def delete_recording(recording_id: int, db: Session = Depends(get_db),
                     current_user = Depends(get_current_active_user)):
    """
    Delete a recording and its files
    """
    recording = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    # Delete video file
    if os.path.exists(recording.recording_path):
        os.remove(recording.recording_path)

    # Delete metadata file
    metadata_path = recording.recording_path.replace(".mp4", "_metadata.json")
    if os.path.exists(metadata_path):
        os.remove(metadata_path)

    # Delete database entry
    db.delete(recording)
    db.commit()

    return {"message": "Recording deleted successfully"}


@router.post("/recordings/cleanup")
def cleanup_old_recordings(
    days_to_keep: int = Query(30, ge=7), db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user),
):
    """
    Delete recordings older than specified days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

    old_recordings = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.started_at < cutoff_date)
        .all()
    )

    deleted_count = 0
    freed_space = 0

    for recording in old_recordings:
        # Delete files
        if os.path.exists(recording.recording_path):
            file_size = os.path.getsize(recording.recording_path)
            os.remove(recording.recording_path)
            freed_space += file_size

        metadata_path = recording.recording_path.replace(
            ".mp4", "_metadata.json")
        if os.path.exists(metadata_path):
            os.remove(metadata_path)

        # Delete database entry
        db.delete(recording)
        deleted_count += 1

    db.commit()

    return {
        "deleted_count": deleted_count,
        "freed_space_mb": freed_space / (1024 * 1024),
        "days_kept": days_to_keep,
    }


@router.get("/recordings/storage/stats")
def get_storage_statistics(db: Session = Depends(get_db),
                           current_user = Depends(get_current_active_user)):
    """
    Get storage usage statistics (optimized with database aggregation)
    """
    from sqlalchemy import func

    # Use database aggregation instead of loading all records
    result = db.query(
        func.count(models.RecordingEvent.id).label('total_count'),
        func.sum(models.RecordingEvent.file_size_bytes).label('total_size'),
        func.sum(models.RecordingEvent.duration_seconds).label('total_duration')
    ).first()

    total_count = result.total_count or 0
    total_size = result.total_size or 0
    total_duration = result.total_duration or 0

    # Get disk usage
    recordings_dir = "recordings"
    if os.path.exists(recordings_dir):
        disk_usage = sum(
            os.path.getsize(os.path.join(recordings_dir, f))
            for f in os.listdir(recordings_dir)
            if os.path.isfile(os.path.join(recordings_dir, f))
        )
    else:
        disk_usage = 0

    return {
        "total_recordings": total_count,
        "total_size_bytes": total_size,
        "total_size_gb": total_size / (1024**3),
        "total_duration_hours": total_duration / 3600,
        "disk_usage_bytes": disk_usage,
        "disk_usage_gb": disk_usage / (1024**3),
        "average_file_size_mb": (
            (total_size / total_count / (1024**2)) if total_count > 0 else 0
        ),
    }


class ExportRequest(BaseModel):
    """Request model for exporting recordings as ZIP"""
    recording_ids: List[int]


@router.post("/recordings/export")
def export_recordings_zip(
    request: ExportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Export multiple recordings as a ZIP file
    
    Args:
        request: ExportRequest containing list of recording IDs
        
    Returns:
        StreamingResponse with ZIP file
    """
    if not request.recording_ids:
        raise HTTPException(status_code=400, detail="No recording IDs provided")
    
    if len(request.recording_ids) > 100:
        raise HTTPException(
            status_code=400, 
            detail="Cannot export more than 100 recordings at once"
        )
    
    # Fetch recordings from database
    recordings = (
        db.query(models.RecordingEvent)
        .filter(models.RecordingEvent.id.in_(request.recording_ids))
        .all()
    )
    
    if not recordings:
        raise HTTPException(status_code=404, detail="No recordings found")
    
    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for recording in recordings:
            if not os.path.exists(recording.recording_path):
                continue
            
            # Create a safe filename
            filename = os.path.basename(recording.recording_path)
            arcname = f"{recording.camera_id}_{filename}"
            
            # Add file to ZIP
            zip_file.write(recording.recording_path, arcname=arcname)
    
    # Reset buffer position
    zip_buffer.seek(0)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"recordings_{timestamp}.zip"
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
    )
