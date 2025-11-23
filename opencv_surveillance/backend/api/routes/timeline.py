# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Timeline & Playback API Routes
Provides endpoints for timeline viewing, video playback, and clip exports
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator
import logging
import cv2
import numpy as np
from pathlib import Path
import io

from backend.database.session import get_db
from backend.database import models
from backend.core.auth import get_current_active_user
from backend.core.paths import paths

router = APIRouter(prefix="/timeline", tags=["timeline"])
logger = logging.getLogger(__name__)


# ============================================================
# Pydantic Schemas
# ============================================================

class TimelineEventResponse(BaseModel):
    """Schema for timeline event"""
    id: int
    camera_id: str
    event_type: str
    timestamp: datetime
    duration: Optional[float] = None
    thumbnail_path: Optional[str] = None
    video_path: Optional[str] = None

    # Event-specific data
    motion_detected: bool = False
    faces_detected: int = 0
    known_faces_detected: int = 0
    person_name: Optional[str] = None
    confidence: Optional[float] = None

    # v3.10.0: Object detection fields
    objects_detected: int = 0
    object_class: Optional[str] = None  # vehicle, animal, package
    object_subclass: Optional[str] = None  # car, dog, backpack, etc.
    identified_object_name: Optional[str] = None  # "John's Tesla", "My Dog Rex", etc.

    @field_validator('thumbnail_path', mode='before')
    @classmethod
    def normalize_thumbnail_path(cls, v):
        """Strip directory prefix from thumbnail path for API response"""
        if v is None:
            return None
        # Remove 'data/snapshots/' prefix if present
        path_str = str(v)
        if path_str.startswith('data/snapshots/'):
            return path_str.replace('data/snapshots/', '', 1)
        # Also handle absolute paths
        return Path(path_str).name

    class Config:
        from_attributes = True


class TimelineEventsListResponse(BaseModel):
    """Schema for list of timeline events"""
    events: List[TimelineEventResponse]
    total: int
    start_time: datetime
    end_time: datetime
    cameras: List[str]


class FrameRequest(BaseModel):
    """Schema for frame extraction request"""
    camera_id: str = Field(..., description="Camera ID")
    timestamp: datetime = Field(..., description="Exact timestamp")
    recording_id: Optional[int] = Field(None, description="Specific recording ID")


class ClipExportRequest(BaseModel):
    """Schema for clip export request"""
    recording_id: int = Field(..., description="Recording ID")
    start_time: float = Field(..., description="Start time in seconds from recording start")
    end_time: float = Field(..., description="End time in seconds from recording start")
    output_name: Optional[str] = Field(None, description="Custom output filename")


class ClipExportResponse(BaseModel):
    """Schema for clip export response"""
    success: bool
    clip_path: Optional[str]
    message: str


class CameraLane(BaseModel):
    """Schema for camera lane in timeline"""
    camera_id: str
    camera_name: str
    events: List[TimelineEventResponse]
    recordings: List[dict]


class TimelineViewResponse(BaseModel):
    """Schema for complete timeline view"""
    start_time: datetime
    end_time: datetime
    lanes: List[CameraLane]
    total_events: int


# ============================================================
# API Endpoints
# ============================================================

@router.get("/events", response_model=TimelineEventsListResponse)
def get_timeline_events(
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    camera_ids: Optional[List[str]] = Query(None, description="Filter by camera IDs"),
    event_types: Optional[List[str]] = Query(None, description="Filter by event types (motion, face, recording, object)"),
    limit: int = Query(100, le=1000, description="Maximum number of events"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get timeline events for timeline view

    Returns all events (recordings, motion detections, face detections, object detections) in a time range,
    organized for display in a multi-camera timeline interface.

    **Event Types:**
    - `motion`: Motion detection events
    - `face`: Face detection events
    - `object`: Object detection events (v3.10.0 - vehicles, animals, packages)
    - `recording`: Recording start/stop events

    **Use Case:**
    Display synchronized timeline across multiple cameras showing all activity.
    """
    # Parse time range (default to last 24 hours)
    if end_time:
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    else:
        end_dt = datetime.utcnow()

    if start_time:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    else:
        start_dt = end_dt - timedelta(hours=24)

    timeline_events = []
    cameras_in_range = set()

    # Get all recordings in time range
    recordings_query = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.started_at >= start_dt,
        models.RecordingEvent.started_at <= end_dt
    )

    if camera_ids:
        recordings_query = recordings_query.filter(models.RecordingEvent.camera_id.in_(camera_ids))

    recordings = recordings_query.order_by(models.RecordingEvent.started_at).all()

    # Convert recordings to timeline events
    for rec in recordings:
        cameras_in_range.add(rec.camera_id)

        if not event_types or 'recording' in event_types:
            timeline_events.append(TimelineEventResponse(
                id=rec.id,
                camera_id=rec.camera_id,
                event_type='recording',
                timestamp=rec.started_at,
                duration=rec.duration_seconds,
                video_path=rec.recording_path,
                thumbnail_path=rec.thumbnail_path,
                motion_detected=rec.motion_detected,
                faces_detected=rec.faces_detected or 0,
                known_faces_detected=rec.known_faces_detected or 0
            ))

    # Get motion detection events
    if not event_types or 'motion' in event_types:
        motion_query = db.query(models.MotionDetectionEvent).filter(
            models.MotionDetectionEvent.detected_at >= start_dt,
            models.MotionDetectionEvent.detected_at <= end_dt
        )

        if camera_ids:
            motion_query = motion_query.filter(models.MotionDetectionEvent.camera_id.in_(camera_ids))

        motion_events = motion_query.order_by(models.MotionDetectionEvent.detected_at).limit(limit).all()

        for motion in motion_events:
            cameras_in_range.add(motion.camera_id)
            timeline_events.append(TimelineEventResponse(
                id=motion.id,
                camera_id=motion.camera_id,
                event_type='motion',
                timestamp=motion.detected_at,
                duration=None,
                thumbnail_path=motion.snapshot_path,
                video_path=motion.recording_path,
                motion_detected=True,
                faces_detected=motion.faces_detected or 0
            ))

    # Get face detection events
    if not event_types or 'face' in event_types:
        face_query = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.detected_at >= start_dt,
            models.FaceDetectionEvent.detected_at <= end_dt
        )

        if camera_ids:
            face_query = face_query.filter(models.FaceDetectionEvent.camera_id.in_(camera_ids))

        face_events = face_query.order_by(models.FaceDetectionEvent.detected_at).limit(limit).all()

        for face in face_events:
            cameras_in_range.add(face.camera_id)
            timeline_events.append(TimelineEventResponse(
                id=face.id,
                camera_id=face.camera_id,
                event_type='face',
                timestamp=face.detected_at,
                duration=None,
                thumbnail_path=face.snapshot_path,
                video_path=face.recording_path,
                motion_detected=face.motion_detected,
                person_name=face.person_name,
                confidence=face.confidence
            ))

    # v3.10.0: Get object detection events
    if not event_types or 'object' in event_types:
        object_query = db.query(models.ObjectDetectionEvent).filter(
            models.ObjectDetectionEvent.detected_at >= start_dt,
            models.ObjectDetectionEvent.detected_at <= end_dt
        )

        if camera_ids:
            object_query = object_query.filter(models.ObjectDetectionEvent.camera_id.in_(camera_ids))

        object_events = object_query.order_by(models.ObjectDetectionEvent.detected_at).limit(limit).all()

        for obj in object_events:
            cameras_in_range.add(obj.camera_id)

            # Get identified object name if linked
            identified_name = None
            if obj.identified_object:
                identified_name = obj.identified_object.name

            timeline_events.append(TimelineEventResponse(
                id=obj.id,
                camera_id=obj.camera_id,
                event_type='object',
                timestamp=obj.detected_at,
                duration=None,
                thumbnail_path=obj.snapshot_path,
                video_path=obj.recording_path,
                motion_detected=obj.motion_detected,
                objects_detected=1,
                object_class=obj.object_class,
                object_subclass=obj.object_subclass,
                identified_object_name=identified_name,
                confidence=obj.confidence
            ))

    # Sort all events by timestamp
    timeline_events.sort(key=lambda e: e.timestamp)

    # Apply limit
    timeline_events = timeline_events[:limit]

    return TimelineEventsListResponse(
        events=timeline_events,
        total=len(timeline_events),
        start_time=start_dt,
        end_time=end_dt,
        cameras=sorted(list(cameras_in_range))
    )


@router.get("/view", response_model=TimelineViewResponse)
def get_timeline_view(
    start_time: Optional[str] = Query(None, description="Start time (ISO format)"),
    end_time: Optional[str] = Query(None, description="End time (ISO format)"),
    camera_ids: Optional[List[str]] = Query(None, description="Filter by camera IDs"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get complete timeline view with camera lanes

    Returns a structured timeline view with separate lanes for each camera,
    showing all events and recordings organized by camera.

    **Perfect for:**
    - Multi-camera timeline interface
    - Synchronized playback UI
    - Event correlation across cameras
    """
    # Parse time range (default to last 24 hours)
    if end_time:
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    else:
        end_dt = datetime.utcnow()

    if start_time:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    else:
        start_dt = end_dt - timedelta(hours=24)

    # Get all cameras (or filter by camera_ids)
    cameras_query = db.query(models.Camera)
    if camera_ids:
        cameras_query = cameras_query.filter(models.Camera.camera_id.in_(camera_ids))

    cameras = cameras_query.all()

    lanes = []
    total_events = 0

    for camera in cameras:
        # Get events for this camera
        events_response = get_timeline_events(
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            camera_ids=[camera.camera_id],
            event_types=None,
            limit=1000,
            db=db,
            current_user=current_user
        )

        # Get recordings for this camera
        recordings = db.query(models.RecordingEvent).filter(
            models.RecordingEvent.camera_id == camera.camera_id,
            models.RecordingEvent.started_at >= start_dt,
            models.RecordingEvent.started_at <= end_dt
        ).order_by(models.RecordingEvent.started_at).all()

        recordings_data = [
            {
                "id": rec.id,
                "started_at": rec.started_at.isoformat(),
                "ended_at": rec.ended_at.isoformat() if rec.ended_at else None,
                "duration_seconds": rec.duration_seconds,
                "recording_path": rec.recording_path
            }
            for rec in recordings
        ]

        lane = CameraLane(
            camera_id=camera.camera_id,
            camera_name=camera.camera_id,  # Could add name field to Camera model
            events=events_response.events,
            recordings=recordings_data
        )

        lanes.append(lane)
        total_events += len(events_response.events)

    return TimelineViewResponse(
        start_time=start_dt,
        end_time=end_dt,
        lanes=lanes,
        total_events=total_events
    )


@router.get("/frame")
async def get_frame_at_timestamp(
    recording_id: int = Query(..., description="Recording ID"),
    timestamp_offset: float = Query(..., description="Seconds from recording start"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Extract specific frame from recording at exact timestamp

    Returns a JPEG image of the frame at the specified offset from the
    recording start time.

    **Use Case:**
    - Timeline scrubbing
    - Frame-by-frame navigation
    - Thumbnail generation

    **Parameters:**
    - `recording_id`: ID of the recording
    - `timestamp_offset`: Seconds from the start of the recording (0.0 = first frame)
    """
    # Get recording
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == recording_id
    ).first()

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recording {recording_id} not found"
        )

    # Check if video file exists
    video_path = Path(recording.recording_path)
    if not video_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording file not found on disk"
        )

    try:
        # Open video
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to open video file"
            )

        # Calculate frame number
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_number = int(timestamp_offset * fps)

        # Seek to frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

        # Read frame
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Frame not found at specified timestamp"
            )

        # Encode frame as JPEG
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encode frame"
            )

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
                "X-Frame-Timestamp": str(timestamp_offset),
                "X-Recording-ID": str(recording_id)
            }
        )

    except Exception as e:
        logger.error(f"Error extracting frame: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error extracting frame: {str(e)}"
        )


@router.post("/export-clip", response_model=ClipExportResponse)
async def export_video_clip(
    request: ClipExportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Export a video clip from a recording

    Extracts a portion of a recording and saves it as a new video file.
    Uses FFmpeg for efficient stream copying (no re-encoding).

    **Use Case:**
    - Export specific events
    - Create highlight reels
    - Share evidence clips

    **Parameters:**
    - `recording_id`: Source recording ID
    - `start_time`: Start time in seconds from recording start
    - `end_time`: End time in seconds from recording start
    - `output_name`: Optional custom filename
    """
    # Get recording
    recording = db.query(models.RecordingEvent).filter(
        models.RecordingEvent.id == request.recording_id
    ).first()

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recording {request.recording_id} not found"
        )

    # Validate time range
    if request.start_time < 0 or request.end_time <= request.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid time range"
        )

    if recording.duration_seconds and request.end_time > recording.duration_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End time exceeds recording duration"
        )

    try:
        # Import FFmpeg subprocess functionality
        import subprocess

        # Generate output path
        clips_dir = paths.data_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        if request.output_name:
            output_path = clips_dir / request.output_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = clips_dir / f"clip_{recording.camera_id}_{timestamp}.mp4"

        # Use FFmpeg to extract clip (fast, no re-encoding)
        cmd = [
            "ffmpeg",
            "-i", recording.recording_path,
            "-ss", str(request.start_time),
            "-to", str(request.end_time),
            "-c", "copy",
            "-y",
            str(output_path)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return ClipExportResponse(
                success=False,
                clip_path=None,
                message=f"FFmpeg error: {result.stderr}"
            )

        return ClipExportResponse(
            success=True,
            clip_path=str(output_path),
            message=f"Clip exported successfully ({request.end_time - request.start_time:.1f}s)"
        )

    except subprocess.TimeoutExpired:
        return ClipExportResponse(
            success=False,
            clip_path=None,
            message="Export timeout - clip too large"
        )
    except Exception as e:
        logger.error(f"Error exporting clip: {e}")
        return ClipExportResponse(
            success=False,
            clip_path=None,
            message=f"Export failed: {str(e)}"
        )


@router.get("/dates")
def get_event_dates(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    Get list of dates with recorded events

    Returns a list of dates that have recordings or events, useful for
    calendar navigation in timeline UI.

    **Use Case:**
    - Show active dates in calendar picker
    - Quick navigation to dates with activity
    """
    from sqlalchemy import func, distinct

    # Get distinct dates from recordings
    query = db.query(
        func.date(models.RecordingEvent.started_at).label('date')
    )

    if camera_id:
        query = query.filter(models.RecordingEvent.camera_id == camera_id)

    dates = query.distinct().order_by(func.date(models.RecordingEvent.started_at).desc()).all()

    return {
        "dates": [str(d.date) for d in dates],
        "total": len(dates)
    }
