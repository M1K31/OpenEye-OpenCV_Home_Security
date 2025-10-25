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

from backend.database.session import SessionLocal
from backend.database import models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.core.paths import paths
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
        file_path: Path to file (from database or user input)
        allowed_dir: Directory that file must be within
        media_type: MIME type for response
        filename: Optional filename for download

    Returns:
        FileResponse if file is safe to serve

    Raises:
        HTTPException: If file is outside allowed directory or doesn't exist
    """
    try:
        # Resolve paths to absolute, following symlinks
        full_path = Path(file_path).resolve()
        allowed_dir = allowed_dir.resolve()

        # Security check: Ensure file is within allowed directory
        if not str(full_path).startswith(str(allowed_dir)):
            logger.warning(
                f"Path traversal attempt blocked: {file_path} not in {allowed_dir}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: File path not in allowed directory"
            )

        # Check file exists and is a file (not directory)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

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
        raise HTTPException(status_code=500, detail="Error serving file")


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


class RecordingListResponse(BaseModel):
    recordings: List[RecordingResponse]
    total: int
    filtered: int
    limit: int = 50
    skip: int = 0
    has_more: bool = False


# Dependency


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoints


@router.get("/recordings/", response_model=RecordingListResponse)
def list_recordings(
    camera_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_faces: Optional[bool] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    List recordings with optional filters and pagination

    Performance optimizations:
    - Uses indexed queries on camera_id and started_at
    - Paginated results (default 50, max 1000)
    - Efficient sorting
    """
    # Get total count before filtering
    total_count = db.query(models.RecordingEvent).count()

    query = db.query(models.RecordingEvent)

    # Apply filters (uses idx_recording_camera_time index)
    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    if start_date:
        start_dt = datetime.fromisoformat(start_date)
        query = query.filter(models.RecordingEvent.started_at >= start_dt)

    if end_date:
        end_dt = datetime.fromisoformat(end_date)
        query = query.filter(models.RecordingEvent.started_at <= end_dt)

    if has_faces is not None:
        if has_faces:
            query = query.filter(models.RecordingEvent.faces_detected > 0)
        else:
            query = query.filter(models.RecordingEvent.faces_detected == 0)

    # Order by most recent (uses idx_recording_started_at index)
    query = query.order_by(models.RecordingEvent.started_at.desc())

    # Apply pagination
    recordings, filtered_count, total_pages = paginate(query, page=page, page_size=page_size)

    # Calculate skip for backward compatibility
    skip = (page - 1) * page_size

    return RecordingListResponse(
        recordings=recordings,
        total=total_count,
        filtered=filtered_count,
        limit=page_size,
        skip=skip,
        has_more=page < total_pages
    )


@router.get("/recordings/{recording_id}")
def get_recording_details(recording_id: int, db: Session = Depends(get_db)):
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
def download_recording(recording_id: int, db: Session = Depends(get_db)):
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
def stream_recording(recording_id: int, db: Session = Depends(get_db)):
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
        full_path = Path(recording.recording_path).resolve()
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
def delete_recording(recording_id: int, db: Session = Depends(get_db)):
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
    days_to_keep: int = Query(30, ge=7), db: Session = Depends(get_db)
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
def get_storage_statistics(db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
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
