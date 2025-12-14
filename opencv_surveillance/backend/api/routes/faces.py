# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Recognition Management API Routes
Provides endpoints for managing people and training face recognition
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from typing import List
import os
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.api.schemas import face as face_schema
from backend.api.schemas.pagination import PaginatedResponse
from backend.core.face_recognition import get_face_manager, is_training_in_progress
from backend.core.paths import paths
from backend.core.camera_manager import manager as camera_manager
from backend.core.auth import get_current_active_user, require_user, require_admin
from backend.api.schemas import user as user_schema
from backend.database.session import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/faces/people", response_model=PaginatedResponse[face_schema.Person])
def list_people(current_user: user_schema.User = Depends(
        get_current_active_user)):
    """
    Get list of all people in the face recognition system

    **Authentication Required**: Any authenticated user

    Returns:
        PaginatedResponse with people data and pagination metadata
    """
    try:
        face_manager = get_face_manager()
        people_data = face_manager.list_people()
        total = len(people_data)

        # Convert dictionaries to Person model instances for Pydantic v2 validation
        people = [
            face_schema.Person(**person_dict)
            for person_dict in people_data
        ]

        # page_size must be >= 1 per PaginationMetadata schema
        page_size = total if total > 0 else 50  # Default to 50 for empty lists

        return {
            "data": people,
            "pagination": {
                "total": total,
                "filtered": total,
                "page": 1,
                "page_size": page_size,
                "total_pages": 1,  # Always at least 1 page (may be empty)
                "has_more": False
            }
        }
    except Exception as e:
        logger.error(f"Error listing people: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/people",
             response_model=face_schema.Person,
             status_code=201)
def add_person(
    person: face_schema.PersonCreate,
    current_user: user_schema.User = Depends(require_user),
):
    """
    Add a new person to the face recognition system

    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()

        # Validate person name
        if not person.name or not person.name.strip():
            raise HTTPException(
                status_code=400,
                detail="Person name cannot be empty")

        # Sanitize name
        clean_name = "".join(
            c for c in person.name if c.isalnum() or c in (" ", "_", "-")
        ).strip()

        if not clean_name:
            raise HTTPException(status_code=400, detail="Invalid person name")

        # Check if person folder already exists
        person_path = paths.faces_dir / clean_name
        
        # If person folder exists, handle merge/overwrite options
        if os.path.exists(person_path) and os.path.isdir(person_path):
            # Handle overwrite option
            if person.overwrite_if_exists:
                import shutil
                shutil.rmtree(person_path)
                logger.info(f"Overwrote existing person folder: {clean_name}")
                # Continue to create new folder below
            # Handle merge option (just return existing person)
            elif person.merge_if_exists:
                # Count existing photos and get preview
                photo_files = [
                    f for f in os.listdir(person_path)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
                photo_count = len(photo_files)
                
                # Get preview photo URL
                preview_photo_url = None
                if photo_files:
                    photo_files.sort()
                    preview_photo_url = f"/faces/{clean_name}/{photo_files[0]}"
                
                logger.info(f"Person '{clean_name}' folder already exists with {photo_count} photos - merging")
                
                return face_schema.Person(
                    name=clean_name,
                    photo_count=photo_count,
                    path=str(person_path),
                    preview_photo_url=preview_photo_url
                )
            # Default: return existing person info (don't error)
            else:
                # Count existing photos and get preview
                photo_files = [
                    f for f in os.listdir(person_path)
                    if f.lower().endswith((".jpg", ".jpeg", ".png"))
                ]
                photo_count = len(photo_files)
                
                # Get preview photo URL
                preview_photo_url = None
                if photo_files:
                    photo_files.sort()
                    preview_photo_url = f"/faces/{clean_name}/{photo_files[0]}"
                
                logger.info(f"Person '{clean_name}' folder already exists with {photo_count} photos - returning existing person")
                
                return face_schema.Person(
                    name=clean_name,
                    photo_count=photo_count,
                    path=str(person_path),
                    preview_photo_url=preview_photo_url
                )
        
        # Add person (creates new folder)
        success = face_manager.add_person(clean_name)

        if not success:
            raise HTTPException(
                status_code=400, detail=f"Person '{clean_name}' already exists"
            )

        # Return person info (new person, no photos yet)
        return face_schema.Person(
            name=clean_name,
            photo_count=0,
            path=str(person_path),
            preview_photo_url=None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/people/{person_name}", response_model=face_schema.Person)
def get_person(
        person_name: str,
        current_user: user_schema.User = Depends(get_current_active_user)):
    """
    Get details for a specific person

    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        person_path = paths.faces_dir / person_name

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        # Count photos and get preview
        photo_count = 0
        preview_photo_url = None
        if os.path.isdir(person_path):
            photo_files = [
                f
                for f in os.listdir(person_path)
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
            ]
            photo_count = len(photo_files)
            
            # Get preview photo URL
            if photo_files:
                photo_files.sort()
                preview_photo_url = f"/faces/{person_name}/{photo_files[0]}"

        return face_schema.Person(
            name=person_name,
            photo_count=photo_count,
            path=str(person_path),
            preview_photo_url=preview_photo_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/faces/people/{person_name}", response_model=face_schema.Person)
def update_person(
    person_name: str,
    new_person: face_schema.PersonUpdate,
    current_user: user_schema.User = Depends(require_user),
):
    """
    Update a person's information (rename)

    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()
        old_path = os.path.join(face_manager.faces_folder, person_name)

        # Check if person exists
        if not os.path.exists(old_path):
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        # Validate new name
        if not new_person.name or not new_person.name.strip():
            raise HTTPException(
                status_code=400, detail="New person name cannot be empty"
            )

        # Sanitize new name
        clean_name = "".join(
            c for c in new_person.name if c.isalnum() or c in (" ", "_", "-")
        ).strip()

        if not clean_name:
            raise HTTPException(
                status_code=400,
                detail="Invalid new person name")

        # Check if new name already exists
        new_path = os.path.join(face_manager.faces_folder, clean_name)
        if os.path.exists(new_path) and clean_name != person_name:
            raise HTTPException(
                status_code=400, detail=f"Person '{clean_name}' already exists"
            )

        # Rename the directory
        if clean_name != person_name:
            os.rename(old_path, new_path)
            logger.info(f"Renamed person '{person_name}' to '{clean_name}'")

        # Count photos and get preview
        photo_files = [
            f
            for f in os.listdir(new_path)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        photo_count = len(photo_files)
        
        # Get preview photo URL
        preview_photo_url = None
        if photo_files:
            photo_files.sort()
            preview_photo_url = f"/faces/{clean_name}/{photo_files[0]}"

        return face_schema.Person(
            name=clean_name,
            photo_count=photo_count,
            path=str(new_path),
            preview_photo_url=preview_photo_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/faces/people/{person_name}",
               response_model=face_schema.DeleteResponse)
def delete_person(
    person_name: str, current_user: user_schema.User = Depends(require_admin)
):
    """
    Delete a person and all their photos from the system

    **Authentication Required**: Admin role only
    """
    try:
        face_manager = get_face_manager()
        success = face_manager.delete_person(person_name)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        return face_schema.DeleteResponse(
            success=True, message=f"Person '{person_name}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/people/{person_name}/photos",
            response_model=List[face_schema.PhotoInfo])
def list_person_photos(
        person_name: str,
        current_user: user_schema.User = Depends(get_current_active_user)):
    """
    List all photos for a specific person

    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        person_path = paths.faces_dir / person_name

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        # Get all photos
        photos = []
        if os.path.isdir(person_path):
            for filename in os.listdir(person_path):
                if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    file_path = os.path.join(person_path, filename)
                    file_stats = os.stat(file_path)

                    photos.append(
                        face_schema.PhotoInfo(
                            filename=filename,
                            path=file_path,
                            size_bytes=file_stats.st_size,
                            uploaded_at=datetime.fromtimestamp(
                                file_stats.st_mtime),
                        ))

        # Sort by upload date (newest first)
        photos.sort(key=lambda x: x.uploaded_at, reverse=True)

        return photos

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/people/{person_name}/photos",
             response_model=face_schema.UploadResponse)
async def upload_photos(
    person_name: str,
    files: List[UploadFile] = File(...),
    current_user: user_schema.User = Depends(require_user),
):
    """
    Upload one or more photos for a person

    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()
        person_path = paths.faces_dir / person_name

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        uploaded_count = 0
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB per file
        MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB total
        total_size = 0

        for file in files:
            # Validate file type
            if not file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                logger.warning(f"Skipping invalid file type: {file.filename}")
                continue

            # Read file content
            content = await file.read()
            file_size = len(content)

            # Validate file size
            if file_size > MAX_FILE_SIZE:
                logger.warning(f"File {file.filename} exceeds size limit ({file_size} bytes)")
                continue

            total_size += file_size
            if total_size > MAX_TOTAL_SIZE:
                logger.warning(f"Total upload size exceeds limit ({total_size} bytes)")
                break

            # Generate unique filename if file already exists
            file_path = os.path.join(person_path, file.filename)
            if os.path.exists(file_path):
                # Add timestamp to filename
                name, ext = os.path.splitext(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join(person_path, f"{name}_{timestamp}{ext}")

            # Save file
            with open(file_path, "wb") as f:
                f.write(content)

            uploaded_count += 1
            logger.info(f"Uploaded photo: {os.path.basename(file_path)} ({file_size} bytes) for {person_name}")

        if uploaded_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No valid image files uploaded (must be .jpg, .jpeg, or .png)",
            )

        return face_schema.UploadResponse(
            uploaded_count=uploaded_count,
            person_name=person_name,
            message=f"Successfully uploaded {uploaded_count} photo(s)",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/faces/people/{person_name}/photos/{filename}",
    response_model=face_schema.DeleteResponse,
)
def delete_person_photo(
    person_name: str,
    filename: str,
    current_user: user_schema.User = Depends(require_user),
):
    """
    Delete a specific photo for a person

    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()
        person_path = paths.faces_dir / person_name

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(
                status_code=404, detail=f"Person '{person_name}' not found"
            )

        # Validate filename (prevent directory traversal)
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check if file exists
        file_path = os.path.join(person_path, filename)
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"Photo '{filename}' not found")

        # Validate file type
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Delete the file
        os.remove(file_path)
        logger.info(f"Deleted photo: {filename} for person: {person_name}")

        return face_schema.DeleteResponse(
            success=True, message=f"Photo '{filename}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/training-status")
def get_training_status(
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Check if face recognition training is currently in progress.

    Used by the UI to display a warning that face detections may be skipped
    during training to prevent crashes.

    **Authentication Required**: Any authenticated user

    Returns:
        Object with training_in_progress boolean and warning message
    """
    training = is_training_in_progress()
    return {
        "training_in_progress": training,
        "message": "Face recognition training in progress. Live face detection is temporarily paused to prevent system crashes. Detections will resume automatically when training completes." if training else None
    }


@router.post("/faces/train", response_model=face_schema.TrainingResponse)
def train_face_recognition(
    request: face_schema.TrainingRequest = None,
    current_user: user_schema.User = Depends(require_admin),
):
    """
    Train the face recognition model with current photos

    **Authentication Required**: Admin role only
    **Note**: Training can take several minutes depending on the number of photos.
    During training, live face detection is temporarily paused to prevent crashes.
    """
    try:
        face_manager = get_face_manager()

        logger.info("Starting face recognition training...")
        result = face_manager.train_face_recognition()

        return face_schema.TrainingResponse(
            total_people=result["total_people"],
            total_encodings=result["total_encodings"],
            training_time=result["training_time"],
            success=True,
            message=f"Training completed: {
                result['total_encodings']} encodings " f"for {
                result['total_people']} people",
        )

    except Exception as e:
        logger.error(f"Error training model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/statistics", response_model=face_schema.FaceStatistics)
def get_face_statistics(
    current_user: user_schema.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Get face recognition statistics (cached for 2 minutes)

    **Authentication Required**: Any authenticated user
    **Performance**: Results are cached for 2 minutes
    """
    try:
        from backend.core.performance import timed_lru_cache
        from backend.database.models import FaceDetectionEvent
        from datetime import datetime, timedelta

        @timed_lru_cache(seconds=120, maxsize=4)
        def _get_cached_stats():
            face_manager = get_face_manager()
            manager_stats = face_manager.get_statistics()
            
            # Query database for accurate "today" counts
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            recognitions_today = db.query(FaceDetectionEvent).filter(
                FaceDetectionEvent.detected_at >= today_start
            ).count()
            
            # Get last recognition from database
            last_event = db.query(FaceDetectionEvent).order_by(
                FaceDetectionEvent.detected_at.desc()
            ).first()
            last_recognition = last_event.detected_at.isoformat() if last_event else None
            
            return {
                "total_people": manager_stats.get("total_people", 0),
                "total_encodings": manager_stats.get("total_encodings", 0),
                "recognitions_today": recognitions_today,
                "last_recognition": last_recognition,
            }

        stats = _get_cached_stats()

        return face_schema.FaceStatistics(
            total_people=stats.get("total_people", 0),
            total_encodings=stats.get("total_encodings", 0),
            recognitions_today=stats.get("recognitions_today", 0),
            last_recognition=stats.get("last_recognition"),
        )

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/settings", response_model=face_schema.FaceSettings)
def get_face_settings(
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Get current face recognition settings

    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()

        return face_schema.FaceSettings(
            enabled=True,  # TODO: Make this configurable
            detection_method=face_manager.detection_method,
            recognition_threshold=face_manager.recognition_threshold,
            faces_folder=str(paths.faces_dir),
        )

    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/faces/settings", response_model=face_schema.FaceSettings)
def update_face_settings(
    settings: face_schema.FaceSettings,
    current_user: user_schema.User = Depends(require_admin),
):
    """
    Update face recognition settings

    **Authentication Required**: Admin role only
    """
    try:
        face_manager = get_face_manager()

        # Update settings
        face_manager.set_detection_method(settings.detection_method)
        face_manager.set_recognition_threshold(settings.recognition_threshold)

        # Return updated settings
        return face_schema.FaceSettings(
            enabled=settings.enabled,
            detection_method=face_manager.detection_method,
            recognition_threshold=face_manager.recognition_threshold,
            faces_folder=str(paths.faces_dir),
        )

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/camera/{camera_id}/enable")
def enable_face_detection(
    camera_id: str,
    enabled: bool = True,
    current_user: user_schema.User = Depends(require_user),
):
    """
    Enable or disable face detection for a specific camera

    **Authentication Required**: Admin or User role
    """
    try:
        camera = camera_manager.get_camera(camera_id)

        if not camera:
            raise HTTPException(
                status_code=404, detail=f"Camera '{camera_id}' not found"
            )

        camera.enable_face_detection(enabled)

        return JSONResponse(
            content={
                "camera_id": camera_id,
                "face_detection_enabled": enabled,
                "message": f"Face detection {
                    'enabled' if enabled else 'disabled'} for camera '{camera_id}'",
            })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling face detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VOICE COMMAND ENDPOINTS (v3.11.0 - Ecosystem Integration)
# ============================================================================


from backend.api.schemas import ecosystem as eco_schema
from backend.database import models
import secrets
import uuid


@router.post("/faces/training/start", response_model=eco_schema.FaceTrainingStartResponse)
def start_face_training(
    request: eco_schema.FaceTrainingStartRequest,
    current_user: user_schema.User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Start an interactive face training session.
    
    Used by voice command "Train face for [name]" from MagicMirror.
    Creates a training session that captures photos progressively.
    
    **Authentication Required**: Admin or User role
    """
    try:
        # Check if person already exists
        face_manager = get_face_manager()
        existing_people = [p['name'] for p in face_manager.list_people()]
        
        if request.person_name in existing_people:
            # Allow adding more photos to existing person
            logger.info(f"Adding training photos to existing person: {request.person_name}")
        
        # Create training session
        session_id = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=10)  # 10 minute session timeout
        
        session = models.FaceTrainingSession(
            session_id=session_id,
            person_name=request.person_name,
            camera_id=request.camera_id,
            photos_required=request.photos_required,
            auto_capture=request.auto_capture,
            status="active",
            expires_at=expires_at
        )
        db.add(session)
        db.commit()
        
        logger.info(f"Started face training session {session_id} for {request.person_name}")
        
        return eco_schema.FaceTrainingStartResponse(
            success=True,
            session_id=session_id,
            person_name=request.person_name,
            photos_required=request.photos_required,
            instructions="Please look at the camera and slowly turn your head left and right"
        )
        
    except Exception as e:
        logger.error(f"Error starting face training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/training/capture", response_model=eco_schema.FaceTrainingCaptureResponse)
def capture_training_photo(
    request: eco_schema.FaceTrainingCaptureRequest,
    current_user: user_schema.User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Capture a training photo during an active session.
    
    Used by voice command "Capture training photo" from MagicMirror.
    
    **Authentication Required**: Admin or User role
    """
    import cv2
    import json
    
    try:
        # Find active session
        session = db.query(models.FaceTrainingSession).filter(
            models.FaceTrainingSession.session_id == request.session_id,
            models.FaceTrainingSession.status == "active"
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Training session not found or expired")
        
        if session.expires_at < datetime.now():
            session.status = "expired"
            db.commit()
            raise HTTPException(status_code=410, detail="Training session has expired")
        
        # Get camera frame
        camera_id = session.camera_id
        camera = None
        
        if camera_id:
            camera = camera_manager.get_camera(camera_id)
        else:
            # Use first available camera
            cameras = camera_manager.list_cameras()
            if cameras:
                camera = camera_manager.get_camera(cameras[0])
        
        if not camera:
            raise HTTPException(status_code=503, detail="No camera available for capture")
        
        frame, _ = camera.get_frame()
        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")
        
        # Check for face in frame
        face_manager = get_face_manager()
        face_locations = face_manager.detector.detect_faces(frame)
        
        if not face_locations:
            return eco_schema.FaceTrainingCaptureResponse(
                success=False,
                photo_number=session.photos_captured,
                total_needed=session.photos_required,
                remaining=session.photos_required - session.photos_captured,
                quality_score=0.0,
                feedback="No face detected. Please position your face in the camera view."
            )
        
        # Save the photo
        person_dir = paths.faces_dir / session.person_name
        person_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"training_{timestamp}.jpg"
        filepath = person_dir / filename
        
        cv2.imwrite(str(filepath), frame)
        
        # Update session
        session.photos_captured += 1
        captured_photos = json.loads(session.captured_photos) if session.captured_photos else []
        captured_photos.append(str(filepath))
        session.captured_photos = json.dumps(captured_photos)
        db.commit()
        
        remaining = session.photos_required - session.photos_captured
        
        # Generate feedback
        if remaining > 0:
            feedback = f"Good! {remaining} more photo(s) needed. Try turning your head slightly."
        else:
            feedback = "All photos captured! Say 'Complete training' to finish."
        
        return eco_schema.FaceTrainingCaptureResponse(
            success=True,
            photo_number=session.photos_captured,
            total_needed=session.photos_required,
            remaining=remaining,
            quality_score=0.9,  # TODO: Calculate actual quality
            feedback=feedback
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error capturing training photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/training/complete", response_model=eco_schema.FaceTrainingCompleteResponse)
def complete_face_training(
    request: eco_schema.FaceTrainingCompleteRequest,
    background_tasks: BackgroundTasks,
    current_user: user_schema.User = Depends(require_user),
    db: Session = Depends(get_db)
):
    """
    Complete a face training session and enroll the face.
    
    Used by voice command "Complete training" from MagicMirror.
    Triggers model retraining with the captured photos.
    
    **Authentication Required**: Admin or User role
    """
    try:
        # Find session
        session = db.query(models.FaceTrainingSession).filter(
            models.FaceTrainingSession.session_id == request.session_id
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="Training session not found")
        
        if session.status != "active":
            raise HTTPException(status_code=400, detail=f"Session is {session.status}")
        
        if session.photos_captured == 0:
            raise HTTPException(status_code=400, detail="No photos captured. Capture at least one photo.")
        
        # Mark session as completed
        session.status = "completed"
        session.completed_at = datetime.now()
        db.commit()
        
        # Trigger model retraining in background
        face_manager = get_face_manager()
        background_tasks.add_task(face_manager.train_model)
        
        logger.info(f"Completed face training for {session.person_name} with {session.photos_captured} photos")
        
        return eco_schema.FaceTrainingCompleteResponse(
            success=True,
            face_id=session.person_name,
            person_name=session.person_name,
            photos_used=session.photos_captured,
            encoding_quality=0.9  # TODO: Calculate actual quality
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing face training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/identify", response_model=eco_schema.FaceIdentifyResponse)
def identify_face_in_frame(
    request: eco_schema.FaceIdentifyRequest,
    current_user: user_schema.User = Depends(require_user)
):
    """
    Identify a person in the current camera frame.
    
    Used by voice command "Who's at the [location]" from MagicMirror.
    Returns the identified person's name and confidence.
    
    **Authentication Required**: Admin or User role
    """
    try:
        camera = camera_manager.get_camera(request.camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail=f"Camera '{request.camera_id}' not found")
        
        frame, _ = camera.get_frame()
        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")
        
        # Run face recognition
        face_manager = get_face_manager()
        results = face_manager.recognize_faces_in_frame(frame)
        
        if not results:
            return eco_schema.FaceIdentifyResponse(
                success=True,
                identified=False,
                person_name=None,
                confidence=None,
                face_id=None,
                bounding_box=None
            )
        
        # Return the first (highest confidence) result
        best_match = results[0]
        
        is_known = best_match['name'] != 'Unknown'
        
        return eco_schema.FaceIdentifyResponse(
            success=True,
            identified=is_known,
            person_name=best_match['name'] if is_known else None,
            confidence=best_match.get('confidence', 0.0),
            face_id=best_match['name'] if is_known else None,
            bounding_box={
                "x": best_match['location'][3],  # left
                "y": best_match['location'][0],  # top
                "width": best_match['location'][1] - best_match['location'][3],  # right - left
                "height": best_match['location'][2] - best_match['location'][0]  # bottom - top
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error identifying face: {e}")
        raise HTTPException(status_code=500, detail=str(e))
