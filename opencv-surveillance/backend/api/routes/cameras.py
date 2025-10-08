# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import cv2
import asyncio
import os

from backend.core.camera_manager import manager as camera_manager
from backend.database.session import get_db
from backend.database import crud
from backend.api.schemas import camera as camera_schema

router = APIRouter()

# ============================================================================
# CAMERA CRUD ENDPOINTS
# ============================================================================

@router.post("/", response_model=camera_schema.CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    camera: camera_schema.CameraCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new camera configuration and start monitoring
    
    - **camera_id**: Unique identifier (e.g., 'front-door', 'backyard')
    - **camera_type**: Type of camera (rtsp, usb, mock, onvif)
    - **source**: RTSP URL, device path (/dev/video0), or 'mock'
    - **face_detection_enabled**: Enable face recognition
    - **motion_detection_enabled**: Enable motion detection
    - **recording_enabled**: Enable automatic recording
    """
    # Check if camera already exists in database
    existing_camera = crud.get_camera_by_id(db, camera.camera_id)
    if existing_camera:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Camera with ID '{camera.camera_id}' already exists"
        )
    
    # Create camera in database
    camera_data = camera.model_dump()
    db_camera = crud.create_camera(db, camera_data)
    
    # Start camera in camera manager
    try:
        camera_manager.add_camera(
            camera_id=camera.camera_id,
            camera_type=camera.camera_type,
            source=camera.source
        )
        
        # Verify camera started successfully
        active_camera = camera_manager.get_camera(camera.camera_id)
        if not active_camera or not active_camera.is_running:
            crud.delete_camera(db, camera.camera_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start camera '{camera.camera_id}'. Check source URL and logs."
            )
    except Exception as e:
        crud.delete_camera(db, camera.camera_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting camera: {str(e)}"
        )
    
    return db_camera


@router.get("/", response_model=camera_schema.CameraListResponse)
def list_cameras(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get list of all cameras with pagination
    
    - **skip**: Number of cameras to skip (default: 0)
    - **limit**: Maximum cameras to return (default: 100)
    - **active_only**: Only return active cameras (default: False)
    """
    if active_only:
        cameras = crud.get_active_cameras(db)
        total = len(cameras)
    else:
        cameras = crud.get_cameras(db, skip=skip, limit=limit)
        total = db.query(crud.models.Camera).count()
    
    return {
        "cameras": cameras,
        "total": total
    }


@router.get("/{camera_id}", response_model=camera_schema.CameraResponse)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """
    Get camera configuration by camera_id
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    return db_camera


@router.put("/{camera_id}", response_model=camera_schema.CameraResponse)
def update_camera(
    camera_id: str,
    camera_update: camera_schema.CameraUpdate,
    db: Session = Depends(get_db)
):
    """
    Update camera configuration
    
    - Can update any camera settings
    - Changes to source require camera restart
    - Returns updated camera configuration
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    # Get only fields that were provided
    update_data = camera_update.model_dump(exclude_unset=True)
    
    # If source or type changed, need to restart camera
    restart_required = ('source' in update_data or 'camera_type' in update_data)
    
    if restart_required:
        # Stop camera if running
        if camera_manager.get_camera(camera_id):
            camera_manager.remove_camera(camera_id)
        
        # Update database
        updated_camera = crud.update_camera(db, camera_id, update_data)
        
        # Restart camera with new config
        try:
            camera_manager.add_camera(
                camera_id=updated_camera.camera_id,
                camera_type=updated_camera.camera_type,
                source=updated_camera.source
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error restarting camera: {str(e)}"
            )
    else:
        # Just update database (settings changes don't require restart)
        updated_camera = crud.update_camera(db, camera_id, update_data)
    
    return updated_camera


@router.delete("/{camera_id}", status_code=status.HTTP_200_OK)
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    """
    Delete camera configuration and stop monitoring
    
    - Stops camera stream
    - Removes from database
    - Does not delete recordings
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    # Stop camera if running
    if camera_manager.get_camera(camera_id):
        camera_manager.remove_camera(camera_id)
    
    # Delete from database
    crud.delete_camera(db, camera_id)
    
    return {"message": f"Camera '{camera_id}' deleted successfully"}


@router.post("/{camera_id}/deactivate", response_model=camera_schema.CameraResponse)
def deactivate_camera(camera_id: str, db: Session = Depends(get_db)):
    """
    Deactivate camera (soft delete - keeps configuration)
    
    - Stops camera stream
    - Marks as inactive in database
    - Can be reactivated later
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    # Stop camera if running
    if camera_manager.get_camera(camera_id):
        camera_manager.remove_camera(camera_id)
    
    # Mark as inactive
    updated_camera = crud.deactivate_camera(db, camera_id)
    
    return updated_camera


@router.post("/{camera_id}/activate", response_model=camera_schema.CameraResponse)
def activate_camera(camera_id: str, db: Session = Depends(get_db)):
    """
    Activate previously deactivated camera
    
    - Starts camera stream
    - Marks as active in database
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    # Start camera
    try:
        camera_manager.add_camera(
            camera_id=db_camera.camera_id,
            camera_type=db_camera.camera_type,
            source=db_camera.source
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting camera: {str(e)}"
        )
    
    # Mark as active
    update_data = {"is_active": True}
    updated_camera = crud.update_camera(db, camera_id, update_data)
    
    return updated_camera


@router.get("/{camera_id}/status", response_model=camera_schema.CameraStatusResponse)
def get_camera_status(camera_id: str, db: Session = Depends(get_db)):
    """
    Get real-time camera status
    
    - **is_active**: Camera is in database
    - **is_running**: Camera manager has active stream
    - **fps**: Current frames per second
    - **last_frame_time**: Timestamp of last frame
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    active_camera = camera_manager.get_camera(camera_id)
    
    status_data = {
        "camera_id": camera_id,
        "is_active": db_camera.is_active,
        "is_running": active_camera is not None and active_camera.is_running if active_camera else False,
        "fps": None,
        "last_frame_time": None,
        "error_message": None
    }
    
    if active_camera:
        if hasattr(active_camera, 'fps'):
            status_data["fps"] = active_camera.fps
        if hasattr(active_camera, 'last_frame_time'):
            status_data["last_frame_time"] = active_camera.last_frame_time
        if hasattr(active_camera, 'error_message'):
            status_data["error_message"] = active_camera.error_message
    
    return status_data


# ============================================================================
# CAMERA STREAMING ENDPOINTS
# ============================================================================

async def generate_frames(camera_id: str):
    """
    Generator function to yield frames from a camera as MJPEG
    """
    camera = camera_manager.get_camera(camera_id)
    if not camera or not camera.is_running:
        print(f"Camera '{camera_id}' not found or not running.")
        return

    while True:
        frame, motion_detected = camera.get_frame()
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03)  # Limit to ~30 FPS


@router.get("/{camera_id}/stream")
def stream_video(camera_id: str, db: Session = Depends(get_db)):
    """
    Stream live video feed as MJPEG
    
    - Returns multipart/x-mixed-replace stream
    - Suitable for HTML <img> tags
    - ~30 FPS frame rate
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running"
        )

    return StreamingResponse(
        generate_frames(camera_id),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )


@router.get("/{camera_id}/snapshot")
def capture_snapshot(camera_id: str, db: Session = Depends(get_db)):
    """
    Capture a single frame snapshot
    
    - Returns JPEG image
    - Saves snapshot to disk
    - Returns image file path
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )
    
    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running"
        )
    
    frame, _ = active_camera.get_frame()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture frame from camera '{camera_id}'"
        )
    
    # Create snapshots directory
    snapshots_dir = os.path.join('data', 'snapshots')
    os.makedirs(snapshots_dir, exist_ok=True)
    
    # Save snapshot
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{camera_id}_{timestamp}.jpg"
    filepath = os.path.join(snapshots_dir, filename)
    
    cv2.imwrite(filepath, frame)
    
    # Update last_active in database
    crud.update_camera_last_active(db, camera_id)
    
    return FileResponse(
        filepath,
        media_type='image/jpeg',
        filename=filename
    )


# ============================================================================
# CAMERA DISCOVERY ENDPOINTS
# ============================================================================

@router.get("/discover/usb", response_model=camera_schema.CameraDiscoveryUSBResponse)
def discover_usb_cameras():
    """
    Discover connected USB webcams
    
    - Scans /dev/video* devices (Linux)
    - Tests each device for availability
    - Returns list of working cameras
    
    **Note:** USB discovery has limitations in Docker on macOS.
    See documentation for workarounds.
    """
    discovered_cameras = []
    
    # Try common video device indices
    for index in range(10):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            ret, _ = cap.read()
            device_path = f"/dev/video{index}" if os.name != 'nt' else f"video{index}"
            
            discovered_cameras.append({
                "device_index": index,
                "device_path": device_path,
                "name": f"USB Camera {index}",
                "available": ret
            })
            cap.release()
    
    return {
        "cameras": discovered_cameras,
        "total": len(discovered_cameras)
    }


@router.get("/discover/network", response_model=camera_schema.CameraDiscoveryNetworkResponse)
def discover_network_cameras():
    """
    Discover ONVIF-compatible network cameras
    
    - Scans local network for ONVIF devices
    - Returns camera details and RTSP URLs
    - Requires onvif-zeep library
    
    **Implementation Note:** This is a placeholder.
    Full ONVIF discovery requires the onvif-zeep library.
    """
    # TODO: Implement ONVIF discovery
    # This requires:
    # 1. Install onvif-zeep: pip install onvif-zeep
    # 2. Use WS-Discovery to find cameras
    # 3. Query device information
    # 4. Get stream URIs
    
    discovered_cameras = []
    
    # Placeholder response
    return {
        "cameras": discovered_cameras,
        "total": 0
    }
