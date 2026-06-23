# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Scheduled Tasks API Routes
Manages scheduled events like model retraining, retroactive face search, and cleanup
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import time

from backend.core.scheduled_tasks import (
    get_scheduled_tasks_manager,
    TaskType,
    TaskStatus
)
from backend.core.auth import get_current_active_user
from backend.database.models import User

router = APIRouter()


class TaskConfigUpdate(BaseModel):
    """Model for updating task configuration"""
    enabled: Optional[bool] = None
    schedule_time: Optional[str] = None  # HH:MM format
    interval_hours: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Response model for task info"""
    task_type: str
    enabled: bool
    schedule_time: Optional[str]
    interval_hours: Optional[int]
    last_run: Optional[str]
    config: Dict[str, Any]
    status: str
    last_result: Optional[Dict[str, Any]]


class RetroactiveSearchRequest(BaseModel):
    """Request model for manual retroactive search"""
    person_name: Optional[str] = None  # Search for specific person
    search_unknown_only: bool = True  # Default to unknown only for safety
    hours_back: int = 168  # Default 1 week
    max_events: int = 5000
    tolerance: float = 0.5  # Confidence threshold (0.3=strict, 0.6=normal, 0.8=lenient)


@router.get("/tasks", response_model=List[TaskResponse])
async def list_scheduled_tasks(
    current_user: User = Depends(get_current_active_user)
):
    """
    List all scheduled tasks and their configuration
    """
    manager = get_scheduled_tasks_manager()
    return manager.get_all_tasks()


@router.get("/tasks/{task_type}", response_model=TaskResponse)
async def get_scheduled_task(
    task_type: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get info for a specific scheduled task
    """
    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")

    manager = get_scheduled_tasks_manager()
    task = manager.get_task(task_type_enum)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.put("/tasks/{task_type}")
async def update_scheduled_task(
    task_type: str,
    update: TaskConfigUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update scheduled task configuration
    """
    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")

    manager = get_scheduled_tasks_manager()

    success = manager.update_task(
        task_type=task_type_enum,
        enabled=update.enabled,
        schedule_time=update.schedule_time,
        interval_hours=update.interval_hours,
        config=update.config
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to update task")

    return {"message": "Task updated successfully", "task": manager.get_task(task_type_enum)}


@router.post("/tasks/{task_type}/run")
async def trigger_scheduled_task(
    task_type: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually trigger a scheduled task
    """
    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")

    manager = get_scheduled_tasks_manager()
    result = await manager.trigger_task(task_type_enum)

    return {
        "message": f"Task {task_type} executed",
        "result": result
    }


@router.post("/retroactive-search")
async def manual_retroactive_search(
    request: RetroactiveSearchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually run retroactive face search

    This searches past face detection events and updates identifications
    based on the current trained model.

    Parameters:
    - person_name: Optional - search for a specific person only
    - search_unknown_only: If true, only search events marked as "Unknown"
    - hours_back: How many hours back to search
    - max_events: Maximum number of events to process
    - tolerance: Confidence threshold (0.3=strict, 0.6=normal)
    """
    manager = get_scheduled_tasks_manager()

    config = {
        "search_unknown_only": request.search_unknown_only,
        "hours_back": request.hours_back,
        "max_events": request.max_events,
        "tolerance": request.tolerance
    }

    if request.person_name:
        config["filter_person"] = request.person_name

    # Temporarily update the task config and run
    manager.update_task(
        task_type=TaskType.RETROACTIVE_SEARCH,
        config=config
    )

    result = await manager.trigger_task(TaskType.RETROACTIVE_SEARCH)

    return {
        "message": "Retroactive search completed",
        "result": result
    }


class PersonSearchRequest(BaseModel):
    """Request model for person-specific retroactive search"""
    tolerance: float = 0.4  # Default to strict matching
    hours_back: int = 168  # Default 1 week
    max_events: int = 5000


@router.post("/search-person/{person_name}")
async def search_for_person(
    person_name: str,
    request: PersonSearchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Search past events for a specific person

    This searches through past "Unknown" face detection events to find
    faces that match the specified person. Uses the person's trained
    face encodings to identify matches.

    The tolerance setting controls matching strictness:
    - 0.3 = Very strict (fewer false positives, may miss some matches)
    - 0.4 = Strict (recommended for manual searches)
    - 0.5 = Moderate
    - 0.6 = Normal (system default)

    **This does NOT affect automatic face recognition settings.**

    Parameters:
    - person_name: The person to search for (must be trained)
    - tolerance: Matching threshold (lower = stricter)
    - hours_back: How many hours back to search
    - max_events: Maximum events to process
    """
    from backend.core.face_recognition import get_face_manager
    from backend.database.session import get_db
    from backend.database.models import FaceDetectionEvent
    from backend.database.utils import get_db_context
    from datetime import datetime, timedelta
    import numpy as np
    import face_recognition
    import logging

    logger = logging.getLogger(__name__)

    # Validate tolerance range
    if not 0.1 <= request.tolerance <= 0.9:
        raise HTTPException(
            status_code=400,
            detail="Tolerance must be between 0.1 and 0.9"
        )

    result = {
        "person_name": person_name,
        "tolerance": request.tolerance,
        "events_searched": 0,
        "events_updated": 0,
        "matches_found": 0,
        "already_identified": 0,
        "errors": 0
    }

    # Get face manager and check if person exists
    face_manager = get_face_manager()
    face_manager.load_encodings()

    # Find encodings for this specific person
    person_indices = [
        i for i, name in enumerate(face_manager.known_face_names)
        if name == person_name
    ]

    if not person_indices:
        raise HTTPException(
            status_code=404,
            detail=f"Person '{person_name}' not found or has no trained face encodings. Please add photos and train first."
        )

    person_encodings = [face_manager.known_face_encodings[i] for i in person_indices]
    result["person_encodings_count"] = len(person_encodings)

    with get_db_context() as db:
        # Query past events
        cutoff_time = datetime.now() - timedelta(hours=request.hours_back)

        events = db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.detected_at >= cutoff_time,
            FaceDetectionEvent.face_encoding.isnot(None),
            FaceDetectionEvent.person_name == "Unknown"  # Only search unknowns
        ).order_by(
            FaceDetectionEvent.detected_at.desc()
        ).limit(request.max_events).all()

        result["events_searched"] = len(events)

        for event in events:
            try:
                if not event.face_encoding:
                    continue

                # Decode stored encoding
                encoding = np.frombuffer(event.face_encoding, dtype=np.float64)

                if len(encoding) != 128:
                    continue

                # Compare with this person's encodings using custom tolerance
                matches = face_recognition.compare_faces(
                    person_encodings,
                    encoding,
                    tolerance=request.tolerance
                )

                if True in matches:
                    # Calculate confidence from best match
                    face_distances = face_recognition.face_distance(
                        person_encodings,
                        encoding
                    )
                    best_distance = min(face_distances)
                    confidence = float(1 - best_distance)

                    result["matches_found"] += 1

                    # Update the event
                    event.person_name = person_name
                    event.confidence = confidence
                    result["events_updated"] += 1

                    logger.info(
                        f"Retroactive match: event {event.id} -> {person_name} "
                        f"(confidence: {confidence:.2%})"
                    )

            except Exception as e:
                result["errors"] += 1
                logger.warning(f"Error processing event {event.id}: {e}")

        db.commit()

    return {
        "success": True,
        "message": f"Found {result['matches_found']} matches for {person_name}",
        "result": result
    }


@router.post("/train-and-search")
async def train_and_retroactive_search(
    current_user: User = Depends(get_current_active_user)
):
    """
    Train the face recognition model with any new faces and then
    run retroactive search to update past events

    This is the recommended way to update identifications after:
    - Adding new person folders with face images
    - Identifying clusters of unknown faces
    - Importing face data
    """
    manager = get_scheduled_tasks_manager()

    # Run model retraining with retroactive search enabled
    result = await manager.trigger_task(TaskType.MODEL_RETRAIN)

    return {
        "message": "Model trained and retroactive search completed",
        "result": result
    }


@router.get("/statistics")
async def get_scheduler_statistics(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get scheduler statistics
    """
    manager = get_scheduled_tasks_manager()
    return manager.get_statistics()


@router.get("/task-types")
async def list_task_types(
    current_user: User = Depends(get_current_active_user)
):
    """
    List available task types with descriptions
    """
    return {
        "task_types": [
            {
                "type": TaskType.MODEL_RETRAIN.value,
                "name": "Model Retraining",
                "description": "Retrain face recognition model with new face images"
            },
            {
                "type": TaskType.RETROACTIVE_SEARCH.value,
                "name": "Retroactive Face Search",
                "description": "Search past events and update face identifications"
            },
            {
                "type": TaskType.CLUSTER_CLEANUP.value,
                "name": "Cluster Cleanup",
                "description": "Remove empty or old face clusters"
            },
            {
                "type": TaskType.DATABASE_CLEANUP.value,
                "name": "Database Cleanup",
                "description": "Clean up old motion and face detection events"
            },
            {
                "type": TaskType.SNAPSHOT_CLEANUP.value,
                "name": "Snapshot Cleanup",
                "description": "Delete old snapshot files to free disk space"
            }
        ]
    }
