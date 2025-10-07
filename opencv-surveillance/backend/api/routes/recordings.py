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
import os
import json
from pathlib import Path

from backend.database.session import SessionLocal
from backend.database import models
from pydantic import BaseModel

router = APIRouter()


# Pydantic Models

class RecordingResponse(BaseModel):
    id: int
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


class RecordingSearchRequest(BaseModel):
    camera_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    has_faces: Optional[bool] = None
    min_duration: Optional[int] = None
    limit: int = 50


# Dependency

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoints

@router.get("/recordings/", response_model=List[RecordingResponse])
def list_recordings(
    camera_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    has_faces: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """
    List recordings with optional filters
    """
    query = db.query(models.RecordingEvent)
    
    # Apply filters
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
    
    # Order by most recent
    recordings = query.order_by(
        models.RecordingEvent.started_at.desc()
    ).limit(limit).all()
    
    return recordings


@router.get("/recordings/{recording_id}")
def get_recording_details(
    recording_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a recording including metadata
    """
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Load metadata file if exists
    metadata = None
    metadata_path = recording.recording_path.replace('.mp4', '_metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    
    return {
        "recording": RecordingResponse.from_orm(recording),
        "metadata": metadata
    }


@router.get("/recordings/{recording_id}/download")
def download_recording(
    recording_id: int,
    db: Session = Depends(get_db)
):
    """
    Download a recording file
    """
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if not os.path.exists(recording.recording_path):
        raise HTTPException(status_code=404, detail="Recording file not found")
    
    filename = os.path.basename(recording.recording_path)
    return FileResponse(
        recording.recording_path,
        media_type='video/mp4',
        filename=filename
    )


@router.get("/recordings/{recording_id}/stream")
def stream_recording(
    recording_id: int,
    db: Session = Depends(get_db)
):
    """
    Stream a recording file
    """
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    if not os.path.exists(recording.recording_path):
        raise HTTPException(status_code=404, detail="Recording file not found")
    
    def iterfile():
        with open(recording.recording_path, mode="rb") as file_like:
            yield from file_like
    
    return StreamingResponse(iterfile(), media_type="video/mp4")


@router.delete("/recordings/{recording_id}")
def delete_recording(
    recording_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a recording and its files
    """
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()
    
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Delete video file
    if os.path.exists(recording.recording_path):
        os.remove(recording.recording_path)
    
    # Delete metadata file
    metadata_path = recording.recording_path.replace('.mp4', '_metadata.json')
    if os.path.exists(metadata_path):
        os.remove(metadata_path)
    
    # Delete database entry
    db.delete(recording)
    db.commit()
    
    return {"message": "Recording deleted successfully"}


@router.post("/recordings/cleanup")
def cleanup_old_recordings(
    days_to_keep: int = Query(30, ge=7),
    db: Session = Depends(get_db)
):
    """
    Delete recordings older than specified days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    
    old_recordings = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.started_at < cutoff_date
    ).all()
    
    deleted_count = 0
    freed_space = 0
    
    for recording in old_recordings:
        # Delete files
        if os.path.exists(recording.recording_path):
            file_size = os.path.getsize(recording.recording_path)
            os.remove(recording.recording_path)
            freed_space += file_size
        
        metadata_path = recording.recording_path.replace('.mp4', '_metadata.json')
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        
        # Delete database entry
        db.delete(recording)
        deleted_count += 1
    
    db.commit()
    
    return {
        "deleted_count": deleted_count,
        "freed_space_mb": freed_space / (1024 * 1024),
        "days_kept": days_to_keep
    }


@router.get("/recordings/storage/stats")
def get_storage_statistics(db: Session = Depends(get_db)):
    """
    Get storage usage statistics
    """
    recordings = db.query(models.RecordingEvent).all()
    
    total_size = sum(r.file_size_bytes or 0 for r in recordings)
    total_count = len(recordings)
    total_duration = sum(r.duration_seconds or 0 for r in recordings)
    
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
        "average_file_size_mb": (total_size / total_count / (1024**2)) if total_count > 0 else 0
    }
