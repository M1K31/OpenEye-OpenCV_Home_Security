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
import os
import logging

from backend.database.session import SessionLocal, get_db
from backend.core.auth import get_current_active_user, get_current_user_media
from backend.database import crud, models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.pagination import PaginatedResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def normalize_snapshot_path(path: Optional[str]) -> Optional[str]:
    """
    Convert snapshot path to URL-friendly format.
    Handles both absolute paths and already-normalized URL paths.
    """
    if not path:
        return None

    # Already in URL format
    if path.startswith('/data/snapshots/') or path.startswith('/api/snapshots/'):
        return path

    # Extract filename from absolute path
    filename = os.path.basename(path)
    if filename:
        return f"/data/snapshots/{filename}"

    return None


# =====================================================
# Face Review Schemas (v3.11.5)
# =====================================================

class FaceReassignRequest(BaseModel):
    """Schema for reassigning a face detection to a different person"""
    new_person_name: str = Field(..., description="New person name to assign, or 'Unknown' to mark as unknown")


class FaceReassignResponse(BaseModel):
    """Schema for face reassignment response"""
    success: bool
    message: str
    face_id: int
    old_person_name: str
    new_person_name: str


class BulkFaceReassignRequest(BaseModel):
    """Schema for bulk face reassignment"""
    face_ids: List[int] = Field(..., description="List of face detection event IDs to reassign")
    new_person_name: str = Field(..., description="New person name to assign, or 'Unknown' to mark as unknown")


class BulkFaceDeleteRequest(BaseModel):
    """Schema for bulk face detection deletion"""
    face_ids: List[int] = Field(..., description="List of face detection event IDs to delete")


def _remove_snapshot_file(snapshot_path: Optional[str]) -> bool:
    """
    Delete a detection's snapshot from disk. Returns True if a file was removed.

    Snapshot paths are stored inconsistently — some absolute, some rooted at
    "/data/snapshots/...", some bare filenames — because they were written by
    different code paths over time. Rather than trust the stored string, resolve
    it against the configured snapshots directory and refuse anything that lands
    outside it: a path from the database should never be able to direct a delete
    at an arbitrary location on disk.
    """
    if not snapshot_path:
        return False

    try:
        from backend.core.paths import paths

        snap_root = os.path.realpath(str(paths.snapshots_dir))
        raw = str(snapshot_path).replace("\\", "/")

        marker = "data/snapshots/"
        idx = raw.rfind(marker)
        relative = raw[idx + len(marker):] if idx != -1 else os.path.basename(raw)

        candidate = os.path.realpath(os.path.join(snap_root, relative))

        # Containment check, not decoration: without it a stored value of
        # "../../etc/something" would escape the snapshots directory.
        if not candidate.startswith(snap_root + os.sep):
            logger.warning(
                "Refusing to delete snapshot outside the snapshots directory: %r",
                snapshot_path)
            return False

        if os.path.isfile(candidate):
            os.remove(candidate)
            return True
        return False

    except Exception as e:
        # A missing or unreadable file must not fail the database deletion; the
        # row is the thing that matters, the file is best-effort cleanup.
        logger.warning("Could not remove snapshot %r: %s", snapshot_path, e)
        return False


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
    snapshot_path: Optional[str] = None
    cluster_id: Optional[int] = None
    event_type: str = "face_detected"

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


# get_db is imported from backend.database.session rather than redefined here:
# FastAPI matches dependency_overrides by function identity, so a module-local
# copy is a *different* dependency and silently escapes any override (and used a
# separate session provider from the rest of the app).


@router.get("/history",
            response_model=PaginatedResponse[FaceDetectionEventResponse])
def get_detection_history(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    person_name: Optional[str] = Query(None, description="Filter by person name"),
    event_type: Optional[str] = Query(None, description="Filter by event type: 'face_detected', 'motion_only'"),
    hours: int = Query(24, description="Number of hours to look back"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)):
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

    Performance:
        Optimized COUNT queries: single query when only time filter applied (v3.11.7)
    """
    try:
        # Time filter (always applied)
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Build time-filtered base query (for accurate "total in time range")
        base_query = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.detected_at >= cutoff_time
        )
        query = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.detected_at >= cutoff_time
        )

        # Track if additional filters are applied (beyond time)
        has_additional_filters = False

        # Camera filter (uses idx_face_camera_time index)
        if camera_id:
            query = query.filter(models.FaceDetectionEvent.camera_id == camera_id)
            has_additional_filters = True

        # Person filter (uses idx_face_person_time index)
        if person_name:
            query = query.filter(models.FaceDetectionEvent.person_name == person_name)
            has_additional_filters = True

        # Event type filter (uses idx_face_event_type index)
        if event_type:
            query = query.filter(models.FaceDetectionEvent.event_type == event_type)
            has_additional_filters = True

        # Order by most recent
        query = query.order_by(models.FaceDetectionEvent.detected_at.desc())

        # Optimized count: only count once if no additional filters
        if has_additional_filters:
            # Two counts: total in time range vs filtered
            total_count = base_query.count()
            filtered_count = query.count()
        else:
            # Single count: no additional filters, total = filtered
            filtered_count = query.count()
            total_count = filtered_count

        # Calculate pagination
        total_pages = (filtered_count + page_size - 1) // page_size if filtered_count > 0 else 1
        page = min(page, total_pages)
        offset = (page - 1) * page_size

        # Execute paginated query
        events = query.offset(offset).limit(page_size).all()

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
                    snapshot_path=normalize_snapshot_path(event.snapshot_path),
                    cluster_id=event.cluster_id,
                    event_type=getattr(event, "event_type", "face_detected"),
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
        logger.exception(f"Error in get_detection_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/statistics", response_model=FaceStatisticsResponse)
def get_detection_statistics(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    days: int = Query(7, description="Number of days for statistics"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)):
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
    current_user = Depends(get_current_active_user)):
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
                    snapshot_path=normalize_snapshot_path(event.snapshot_path),
                    cluster_id=event.cluster_id,
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
    current_user = Depends(get_current_active_user)):
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
    current_user = Depends(get_current_active_user)):
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
    current_user = Depends(get_current_active_user)):
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


# =====================================================
# Face Review Endpoints (v3.11.5)
# =====================================================

@router.post("/history/{face_id}/reassign", response_model=FaceReassignResponse)
def reassign_face_detection(
    face_id: int,
    request: FaceReassignRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)):
    """
    Reassign a face detection event to a different person.

    This is used when reviewing face recognition results to correct
    misidentifications. The face can be reassigned to any known person
    or marked as 'Unknown'.

    - **face_id**: ID of the face detection event
    - **new_person_name**: Name of the person to reassign to, or 'Unknown'
    """
    try:
        # Get the face detection event
        face_event = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.id == face_id
        ).first()

        if not face_event:
            raise HTTPException(status_code=404, detail=f"Face detection {face_id} not found")

        old_person_name = face_event.person_name
        new_person_name = request.new_person_name.strip()

        if not new_person_name:
            raise HTTPException(status_code=400, detail="Person name cannot be empty")

        # Update the person_name
        face_event.person_name = new_person_name

        # If reassigning away from a cluster, clear the cluster_id
        if new_person_name != old_person_name and face_event.cluster_id:
            old_cluster = db.query(models.FaceCluster).filter(
                models.FaceCluster.id == face_event.cluster_id
            ).first()

            # Remove from old cluster
            face_event.cluster_id = None

            # Update old cluster face count
            if old_cluster:
                remaining_faces = db.query(models.FaceDetectionEvent).filter(
                    models.FaceDetectionEvent.cluster_id == old_cluster.id
                ).count()
                old_cluster.face_count = remaining_faces

        db.commit()

        return FaceReassignResponse(
            success=True,
            message=f"Face reassigned from '{old_person_name}' to '{new_person_name}'",
            face_id=face_id,
            old_person_name=old_person_name,
            new_person_name=new_person_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{face_id}")
def delete_face_detection(
    face_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user)):
    """
    Delete a single face detection, including its snapshot on disk.

    Reassigning could move a wrong detection to another person, but there was no
    way to say "this is not a face at all" or "this frame is garbage" — a
    misfire, a reflection, a blurred smear — so bad detections could only be
    shuffled between people, never removed. That is why a cluster built from
    them stayed wrong no matter how it was re-labelled.

    Deletes the snapshot file too. Leaving it behind would repeat the bug found
    in delete_person: rows removed, files orphaned, or the reverse — a gallery
    entry pointing at an image nobody can account for.
    """
    face_event = db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.id == face_id
    ).first()

    if not face_event:
        raise HTTPException(status_code=404, detail=f"Face detection {face_id} not found")

    cluster_id = face_event.cluster_id
    snapshot = face_event.snapshot_path

    db.delete(face_event)

    # Keep the owning cluster's count honest, exactly as bulk-reassign does.
    if cluster_id:
        remaining = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.cluster_id == cluster_id
        ).count()
        db.query(models.FaceCluster).filter(
            models.FaceCluster.id == cluster_id
        ).update({models.FaceCluster.face_count: remaining},
                 synchronize_session=False)

    db.commit()

    removed_file = _remove_snapshot_file(snapshot)

    logger.info("Deleted face detection %s (cluster=%s, file_removed=%s)",
                face_id, cluster_id, removed_file)

    return {
        "success": True,
        "message": f"Detection {face_id} deleted",
        "deleted_count": 1,
        "file_removed": removed_file,
    }


@router.post("/history/bulk-delete")
def bulk_delete_face_detections(
    request: BulkFaceDeleteRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user)):
    """
    Delete several face detections at once, with their snapshots.

    The batch counterpart of the endpoint above. Correcting a badly clustered
    person means acting on tens of thumbnails, and doing that one request at a
    time is slow enough that people give up and delete the whole person instead —
    losing the good detections along with the bad.
    """
    if not request.face_ids:
        raise HTTPException(status_code=400, detail="No face IDs provided")

    face_events = db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.id.in_(request.face_ids)
    ).all()

    if not face_events:
        raise HTTPException(status_code=404, detail="No matching faces found")

    affected_clusters = {f.cluster_id for f in face_events if f.cluster_id}
    snapshots = [f.snapshot_path for f in face_events]
    deleted_count = len(face_events)

    db.query(models.FaceDetectionEvent).filter(
        models.FaceDetectionEvent.id.in_(request.face_ids)
    ).delete(synchronize_session=False)

    for cluster_id in affected_clusters:
        remaining = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.cluster_id == cluster_id
        ).count()
        db.query(models.FaceCluster).filter(
            models.FaceCluster.id == cluster_id
        ).update({models.FaceCluster.face_count: remaining},
                 synchronize_session=False)

    db.commit()

    files_removed = sum(1 for s in snapshots if _remove_snapshot_file(s))
    not_found = len(request.face_ids) - deleted_count

    logger.info("Bulk-deleted %s detection(s); %s snapshot file(s) removed",
                deleted_count, files_removed)

    return {
        "success": True,
        "message": f"Deleted {deleted_count} detection(s)",
        "deleted_count": deleted_count,
        "files_removed": files_removed,
        "errors": [f"{not_found} face(s) not found"] if not_found else [],
    }


@router.post("/history/bulk-reassign")
def bulk_reassign_face_detections(
    request: BulkFaceReassignRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)):
    """
    Bulk reassign multiple face detection events to a different person.

    - **face_ids**: List of face detection event IDs to reassign
    - **new_person_name**: Name of the person to reassign to, or 'Unknown'
    """
    try:
        new_person_name = request.new_person_name.strip()

        if not new_person_name:
            raise HTTPException(status_code=400, detail="Person name cannot be empty")

        if not request.face_ids:
            raise HTTPException(status_code=400, detail="No face IDs provided")

        # Get all faces in one query (much faster than individual queries)
        face_events = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.id.in_(request.face_ids)
        ).all()

        if not face_events:
            raise HTTPException(status_code=404, detail="No matching faces found")

        # Track affected clusters
        affected_clusters = set()
        for face_event in face_events:
            if face_event.cluster_id:
                affected_clusters.add(face_event.cluster_id)

        # Count how many we're reassigning
        reassigned_count = len(face_events)
        not_found_count = len(request.face_ids) - reassigned_count

        # Bulk update: set person_name and clear cluster_id in single operations
        db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.id.in_(request.face_ids)
        ).update(
            {
                models.FaceDetectionEvent.person_name: new_person_name,
                models.FaceDetectionEvent.cluster_id: None
            },
            synchronize_session=False
        )

        # Update face counts for affected clusters (batch update)
        for cluster_id in affected_clusters:
            remaining_count = db.query(models.FaceDetectionEvent).filter(
                models.FaceDetectionEvent.cluster_id == cluster_id
            ).count()
            db.query(models.FaceCluster).filter(
                models.FaceCluster.id == cluster_id
            ).update(
                {models.FaceCluster.face_count: remaining_count},
                synchronize_session=False
            )

        db.commit()

        errors = []
        if not_found_count > 0:
            errors.append(f"{not_found_count} face(s) not found")

        return {
            "success": True,
            "message": f"Reassigned {reassigned_count} face(s) to '{new_person_name}'",
            "reassigned_count": reassigned_count,
            "new_person_name": new_person_name,
            "errors": errors,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
