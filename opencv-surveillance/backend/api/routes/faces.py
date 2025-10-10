# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Face Recognition Management API Routes
Provides endpoints for managing people and training face recognition
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from typing import List
import os
import logging
from datetime import datetime

from backend.api.schemas import face as face_schema
from backend.core.face_recognition import get_face_manager
from backend.core.camera_manager import manager as camera_manager
from backend.core.auth import get_current_active_user, require_user, require_admin
from backend.api.schemas import user as user_schema

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/faces/people", response_model=List[face_schema.Person])
def list_people(current_user: user_schema.User = Depends(get_current_active_user)):
    """
    Get list of all people in the face recognition system
    
    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        people = face_manager.list_people()
        return people
    except Exception as e:
        logger.error(f"Error listing people: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/people", response_model=face_schema.Person, status_code=201)
def add_person(
    person: face_schema.PersonCreate,
    current_user: user_schema.User = Depends(require_user)
):
    """
    Add a new person to the face recognition system
    
    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()

        # Validate person name
        if not person.name or not person.name.strip():
            raise HTTPException(status_code=400, detail="Person name cannot be empty")

        # Sanitize name
        clean_name = ''.join(
            c for c in person.name if c.isalnum() or c in (' ', '_', '-')
        ).strip()

        if not clean_name:
            raise HTTPException(status_code=400, detail="Invalid person name")

        # Add person
        success = face_manager.add_person(clean_name)

        if not success:
            raise HTTPException(status_code=400, detail=f"Person '{clean_name}' already exists")

        # Return person info
        person_path = os.path.join(face_manager.faces_folder, clean_name)
        return face_schema.Person(
            name=clean_name,
            photo_count=0,
            path=person_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/people/{person_name}", response_model=face_schema.Person)
def get_person(
    person_name: str,
    current_user: user_schema.User = Depends(get_current_active_user)
):
    """
    Get details for a specific person
    
    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        person_path = os.path.join(face_manager.faces_folder, person_name)

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        # Count photos
        photo_count = 0
        if os.path.isdir(person_path):
            photo_count = len([
                f for f in os.listdir(person_path)
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))
            ])

        return face_schema.Person(
            name=person_name,
            photo_count=photo_count,
            path=person_path
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
    current_user: user_schema.User = Depends(require_user)
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
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        # Validate new name
        if not new_person.name or not new_person.name.strip():
            raise HTTPException(status_code=400, detail="New person name cannot be empty")

        # Sanitize new name
        clean_name = ''.join(
            c for c in new_person.name if c.isalnum() or c in (' ', '_', '-')
        ).strip()

        if not clean_name:
            raise HTTPException(status_code=400, detail="Invalid new person name")

        # Check if new name already exists
        new_path = os.path.join(face_manager.faces_folder, clean_name)
        if os.path.exists(new_path) and clean_name != person_name:
            raise HTTPException(status_code=400, detail=f"Person '{clean_name}' already exists")

        # Rename the directory
        if clean_name != person_name:
            os.rename(old_path, new_path)
            logger.info(f"Renamed person '{person_name}' to '{clean_name}'")
        
        # Count photos
        photo_count = len([
            f for f in os.listdir(new_path)
            if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        ])

        return face_schema.Person(
            name=clean_name,
            photo_count=photo_count,
            path=new_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/faces/people/{person_name}", response_model=face_schema.DeleteResponse)
def delete_person(
    person_name: str,
    current_user: user_schema.User = Depends(require_admin)
):
    """
    Delete a person and all their photos from the system
    
    **Authentication Required**: Admin role only
    """
    try:
        face_manager = get_face_manager()
        success = face_manager.delete_person(person_name)

        if not success:
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        return face_schema.DeleteResponse(
            success=True,
            message=f"Person '{person_name}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting person: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/people/{person_name}/photos", response_model=List[face_schema.PhotoInfo])
def list_person_photos(
    person_name: str,
    current_user: user_schema.User = Depends(get_current_active_user)
):
    """
    List all photos for a specific person
    
    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        person_path = os.path.join(face_manager.faces_folder, person_name)

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        # Get all photos
        photos = []
        if os.path.isdir(person_path):
            for filename in os.listdir(person_path):
                if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                    file_path = os.path.join(person_path, filename)
                    file_stats = os.stat(file_path)
                    
                    photos.append(face_schema.PhotoInfo(
                        filename=filename,
                        path=file_path,
                        size_bytes=file_stats.st_size,
                        uploaded_at=datetime.fromtimestamp(file_stats.st_mtime)
                    ))

        # Sort by upload date (newest first)
        photos.sort(key=lambda x: x.uploaded_at, reverse=True)

        return photos

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/people/{person_name}/photos", response_model=face_schema.UploadResponse)
async def upload_photos(
    person_name: str,
    files: List[UploadFile] = File(...),
    current_user: user_schema.User = Depends(require_user)
):
    """
    Upload one or more photos for a person
    
    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()
        person_path = os.path.join(face_manager.faces_folder, person_name)

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        uploaded_count = 0

        for file in files:
            # Validate file type
            if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue

            # Read file content
            content = await file.read()

            # Save file
            file_path = os.path.join(person_path, file.filename)
            with open(file_path, 'wb') as f:
                f.write(content)

            uploaded_count += 1
            logger.info(f"Uploaded photo: {file.filename} for {person_name}")

        if uploaded_count == 0:
            raise HTTPException(
                status_code=400,
                detail="No valid image files uploaded (must be .jpg, .jpeg, or .png)"
            )

        return face_schema.UploadResponse(
            uploaded_count=uploaded_count,
            person_name=person_name,
            message=f"Successfully uploaded {uploaded_count} photo(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/faces/people/{person_name}/photos/{filename}", response_model=face_schema.DeleteResponse)
def delete_person_photo(
    person_name: str,
    filename: str,
    current_user: user_schema.User = Depends(require_user)
):
    """
    Delete a specific photo for a person
    
    **Authentication Required**: Admin or User role
    """
    try:
        face_manager = get_face_manager()
        person_path = os.path.join(face_manager.faces_folder, person_name)

        # Check if person exists
        if not os.path.exists(person_path):
            raise HTTPException(status_code=404, detail=f"Person '{person_name}' not found")

        # Validate filename (prevent directory traversal)
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check if file exists
        file_path = os.path.join(person_path, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Photo '{filename}' not found")

        # Validate file type
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Delete the file
        os.remove(file_path)
        logger.info(f"Deleted photo: {filename} for person: {person_name}")

        return face_schema.DeleteResponse(
            success=True,
            message=f"Photo '{filename}' deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting photo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/train", response_model=face_schema.TrainingResponse)
def train_face_recognition(
    request: face_schema.TrainingRequest = None,
    current_user: user_schema.User = Depends(require_admin)
):
    """
    Train the face recognition model with current photos
    
    **Authentication Required**: Admin role only
    **Note**: Training can take several minutes depending on the number of photos
    """
    try:
        face_manager = get_face_manager()

        logger.info("Starting face recognition training...")
        result = face_manager.train_face_recognition()

        return face_schema.TrainingResponse(
            total_people=result['total_people'],
            total_encodings=result['total_encodings'],
            training_time=result['training_time'],
            success=True,
            message=f"Training completed: {result['total_encodings']} encodings "
                   f"for {result['total_people']} people"
        )

    except Exception as e:
        logger.error(f"Error training model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/statistics", response_model=face_schema.FaceStatistics)
def get_face_statistics(current_user: user_schema.User = Depends(get_current_active_user)):
    """
    Get face recognition statistics
    
    **Authentication Required**: Any authenticated user
    """
    try:
        face_manager = get_face_manager()
        stats = face_manager.get_statistics()

        return face_schema.FaceStatistics(
            total_people=stats.get('total_people', 0),
            total_encodings=stats.get('total_encodings', 0),
            recognitions_today=stats.get('recognitions_today', 0),
            last_recognition=stats.get('last_recognition')
        )

    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/detections")
def get_recent_detections(current_user: user_schema.User = Depends(get_current_active_user)):
    """
    Get recent face detections from all cameras
    
    **Authentication Required**: Any authenticated user
    """
    try:
        detections = camera_manager.get_all_face_detections()
        return JSONResponse(content=detections)

    except Exception as e:
        logger.error(f"Error getting detections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/faces/settings", response_model=face_schema.FaceSettings)
def get_face_settings(current_user: user_schema.User = Depends(get_current_active_user)):
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
            faces_folder=face_manager.faces_folder
        )

    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/faces/settings", response_model=face_schema.FaceSettings)
def update_face_settings(
    settings: face_schema.FaceSettings,
    current_user: user_schema.User = Depends(require_admin)
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
            faces_folder=face_manager.faces_folder
        )

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/faces/camera/{camera_id}/enable")
def enable_face_detection(
    camera_id: str,
    enabled: bool = True,
    current_user: user_schema.User = Depends(require_user)
):
    """
    Enable or disable face detection for a specific camera
    
    **Authentication Required**: Admin or User role
    """
    try:
        camera = camera_manager.get_camera(camera_id)

        if not camera:
            raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found")

        camera.enable_face_detection(enabled)

        return JSONResponse(content={
            "camera_id": camera_id,
            "face_detection_enabled": enabled,
            "message": f"Face detection {'enabled' if enabled else 'disabled'} for camera '{camera_id}'"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling face detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))