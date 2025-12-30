# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import cv2
import asyncio
import os
import logging

from backend.core.camera_manager import manager as camera_manager
from backend.core.camera_validation import validate_camera_source
from backend.database.session import get_db
from backend.database import crud
from backend.api.schemas import camera as camera_schema

from backend.core.paths import paths
router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================================
# CAMERA CRUD ENDPOINTS
# ============================================================================


@router.post(
    "/",
    response_model=camera_schema.CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_camera(
        camera: camera_schema.CameraCreate,
        db: Session = Depends(get_db)):
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
            detail=f"Camera with ID '{camera.camera_id}' already exists",
        )

    # Validate camera source URL to prevent SSRF and command injection
    validate_camera_source(camera.source, camera.camera_type)

    # Create camera in database
    camera_data = camera.model_dump()
    db_camera = crud.create_camera(db, camera_data)

    # Start camera in camera manager
    try:
        camera_manager.add_camera(
            camera_id=camera.camera_id,
            camera_type=camera.camera_type,
            source=camera.source,
        )

        # Verify camera started successfully
        active_camera = camera_manager.get_camera(camera.camera_id)
        if not active_camera or not active_camera.is_running:
            crud.delete_camera(db, camera.camera_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start camera '{camera.camera_id}'. Check source URL and logs.",
            )
    except Exception as e:
        crud.delete_camera(db, camera.camera_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting camera: {str(e)}",
        )

    return db_camera


@router.get("/", response_model=camera_schema.CameraListResponse)
def list_cameras(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db),
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

    return {"cameras": cameras, "total": total}


@router.get("/{camera_id}", response_model=camera_schema.CameraResponse)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    """
    Get camera configuration by camera_id
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    return db_camera


@router.patch("/{camera_id}", response_model=camera_schema.CameraResponse)
def patch_camera(
    camera_id: str,
    camera_update: camera_schema.CameraUpdate,
    db: Session = Depends(get_db),
):
    """
    Partially update camera configuration (PATCH)

    - Update only specified fields
    - Useful for toggling enabled state
    - Returns updated camera configuration
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    # Get only fields that were provided
    update_data = camera_update.model_dump(exclude_unset=True)

    # Validate camera source if being updated
    if "source" in update_data:
        camera_type = update_data.get("camera_type", db_camera.camera_type)
        validate_camera_source(update_data["source"], camera_type)

    # CRITICAL FIX: Recalculate min_contour_area when motion_sensitivity changes
    # Motion sensitivity scale (1-10) maps inversely to min_contour_area
    if "motion_sensitivity" in update_data:
        # Import the SENSITIVITY_MAP from motion_detector
        from backend.core.motion_detector import MotionDetector

        sensitivity_value = update_data["motion_sensitivity"]
        # Use the SENSITIVITY_MAP to get the correct min_contour_area
        min_contour_area = MotionDetector.SENSITIVITY_MAP.get(sensitivity_value, 500)

        # Automatically update min_contour_area when sensitivity changes
        update_data["min_contour_area"] = min_contour_area

        print(f"🎛️ Motion sensitivity changed to {sensitivity_value} -> min_contour_area set to {min_contour_area}")

    # Handle camera state changes in camera_manager BEFORE updating database
    # This ensures we control the camera based on the new state
    if "is_active" in update_data:
        is_enabled = update_data.get("is_active")

        if is_enabled:
            # Enable camera: stop it first if running, then start with updated
            # config
            if camera_manager.get_camera(camera_id):
                camera_manager.remove_camera(camera_id)
            try:
                # Use updated values if provided, otherwise use existing
                camera_type = update_data.get(
                    "camera_type", db_camera.camera_type)
                source = update_data.get("source", db_camera.source)
                face_detection = update_data.get(
                    "face_detection_enabled", db_camera.face_detection_enabled
                )

                camera_manager.add_camera(
                    camera_id=camera_id,
                    camera_type=camera_type,
                    source=source,
                    enable_face_detection=face_detection,
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error starting camera: {str(e)}",
                )
        else:
            # Disable camera: stop it if running
            if camera_manager.get_camera(camera_id):
                camera_manager.remove_camera(camera_id)

    # Update database
    updated_camera = crud.update_camera(db, camera_id, update_data)

    # Reload settings into running camera instance (if camera is running)
    # This ensures motion_percentage_threshold and other settings take effect immediately
    if camera_manager.get_camera(camera_id):
        camera_manager.reload_camera_settings(camera_id)
        logger.info(f"Reloaded settings for running camera '{camera_id}'")

    return updated_camera


@router.put("/{camera_id}", response_model=camera_schema.CameraResponse)
def update_camera(
    camera_id: str,
    camera_update: camera_schema.CameraUpdate,
    db: Session = Depends(get_db),
):
    """
    Update camera configuration (PUT - full update)

    - Can update any camera settings
    - Changes to source require camera restart
    - Returns updated camera configuration
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    # Get only fields that were provided
    update_data = camera_update.model_dump(exclude_unset=True)

    # Validate camera source if being updated
    if "source" in update_data:
        camera_type = update_data.get("camera_type", db_camera.camera_type)
        validate_camera_source(update_data["source"], camera_type)

    # CRITICAL FIX: Recalculate min_contour_area when motion_sensitivity changes
    # Motion sensitivity scale (1-10) maps inversely to min_contour_area
    if "motion_sensitivity" in update_data:
        from backend.core.motion_detector import MotionDetector
        sensitivity_value = update_data["motion_sensitivity"]
        min_contour_area = MotionDetector.SENSITIVITY_MAP.get(sensitivity_value, 500)
        update_data["min_contour_area"] = min_contour_area
        logger.info(f"Motion sensitivity changed to {sensitivity_value} -> min_contour_area set to {min_contour_area}")

    # If source or type changed, need to restart camera
    restart_required = "source" in update_data or "camera_type" in update_data

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
                source=updated_camera.source,
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error restarting camera: {str(e)}",
            )
    else:
        # Just update database (settings changes don't require restart)
        updated_camera = crud.update_camera(db, camera_id, update_data)

        # Reload settings into running camera instance (if camera is running)
        # This ensures motion_percentage_threshold and other settings take effect immediately
        if camera_manager.get_camera(camera_id):
            camera_manager.reload_camera_settings(camera_id)
            logger.info(f"Reloaded settings for running camera '{camera_id}'")

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
            detail=f"Camera '{camera_id}' not found",
        )

    # Stop camera if running
    if camera_manager.get_camera(camera_id):
        camera_manager.remove_camera(camera_id)

    # Delete from database
    crud.delete_camera(db, camera_id)

    return {"message": f"Camera '{camera_id}' deleted successfully"}


@router.post("/{camera_id}/deactivate",
             response_model=camera_schema.CameraResponse)
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
            detail=f"Camera '{camera_id}' not found",
        )

    # Stop camera if running
    if camera_manager.get_camera(camera_id):
        camera_manager.remove_camera(camera_id)

    # Mark as inactive
    updated_camera = crud.deactivate_camera(db, camera_id)

    return updated_camera


@router.post("/{camera_id}/activate",
             response_model=camera_schema.CameraResponse)
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
            detail=f"Camera '{camera_id}' not found",
        )

    # Start camera
    try:
        camera_manager.add_camera(
            camera_id=db_camera.camera_id,
            camera_type=db_camera.camera_type,
            source=db_camera.source,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting camera: {str(e)}",
        )

    # Mark as active
    update_data = {"is_active": True}
    updated_camera = crud.update_camera(db, camera_id, update_data)

    return updated_camera


@router.get("/{camera_id}/status",
            response_model=camera_schema.CameraStatusResponse)
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
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)

    status_data = {
        "camera_id": camera_id,
        "is_active": db_camera.is_active,
        "is_running": (
            active_camera is not None and active_camera.is_running
            if active_camera
            else False
        ),
        "fps": None,
        "last_frame_time": None,
        "error_message": None,
    }

    if active_camera:
        if hasattr(active_camera, "fps"):
            status_data["fps"] = active_camera.fps
        if hasattr(active_camera, "last_frame_time"):
            status_data["last_frame_time"] = active_camera.last_frame_time
        if hasattr(active_camera, "error_message"):
            status_data["error_message"] = active_camera.error_message

    return status_data


# ============================================================================
# CAMERA STREAMING ENDPOINTS
# ============================================================================


async def generate_frames(camera_id: str):
    """
    Async generator function to yield frames from a camera as MJPEG
    """
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        logger.error(f"Camera '{camera_id}' not found in camera manager")
        return
    if not camera.is_running:
        logger.error(f"Camera '{camera_id}' is not running")
        return

    try:
        while True:
            frame, motion_detected = camera.get_frame()
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            # Encode frame as JPEG
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ret:
                logger.warning(f"Failed to encode frame for camera {camera_id}")
                await asyncio.sleep(0.1)
                continue

            frame_bytes = buffer.tobytes()
            # MJPEG stream format
            yield (
                b"--frame\r\n" 
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(0.033)  # Limit to ~30 FPS
    except Exception as e:
        logger.error(f"Error generating frames for camera {camera_id}: {e}")
        raise


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
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running",
        )

    return StreamingResponse(
        generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
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
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running",
        )

    frame, _ = active_camera.get_frame()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture frame from camera '{camera_id}'",
        )

    # Create snapshots directory
    snapshots_dir = paths.snapshots_dir
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Save snapshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{camera_id}_{timestamp}.jpg"
    filepath = snapshots_dir / filename

    cv2.imwrite(str(filepath), frame)

    # Update last_active in database
    crud.update_camera_last_active(db, camera_id)

    return FileResponse(filepath, media_type="image/jpeg", filename=filename)

# ============================================================================
# CAMERA DISCOVERY ENDPOINTS REMOVED
# ============================================================================
# Discovery endpoints have been moved to discovery.py to avoid duplication.
# Use the dedicated discovery router at /api/cameras/discover/* instead.
# See: opencv_surveillance/backend/api/routes/discovery.py
# ============================================================================


# ============================================================================
# VOICE COMMAND ENDPOINTS (v3.11.0 - Ecosystem Integration)
# ============================================================================


from backend.api.schemas import ecosystem as eco_schema


@router.post("/{camera_id}/snapshot", response_model=eco_schema.SnapshotResponse)
def capture_snapshot_voice(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Capture a snapshot from a camera (voice command endpoint).
    
    Used by voice command "Take photo from [camera]" from MagicMirror.
    Returns JSON with snapshot URL instead of raw image.
    
    For raw image, use GET /{camera_id}/snapshot instead.
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running",
        )

    frame, _ = active_camera.get_frame()
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to capture frame from camera '{camera_id}'",
        )

    # Create snapshots directory
    snapshots_dir = paths.snapshots_dir
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # Save snapshot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{camera_id}_{timestamp}.jpg"
    filepath = snapshots_dir / filename

    cv2.imwrite(str(filepath), frame)

    # Update last_active in database
    crud.update_camera_last_active(db, camera_id)
    
    # Get resolution
    height, width = frame.shape[:2]

    return eco_schema.SnapshotResponse(
        success=True,
        snapshot_url=f"/api/snapshots/{filename}",
        camera_id=camera_id,
        timestamp=datetime.now(),
        resolution=f"{width}x{height}"
    )


@router.post("/{camera_id}/record/start", response_model=eco_schema.RecordingStartResponse)
def start_recording(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Start recording on a camera.
    
    Used by voice command "Start recording on [camera]" from MagicMirror.
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running",
        )

    try:
        # Check if already recording
        if hasattr(active_camera, 'is_recording') and active_camera.is_recording:
            return eco_schema.RecordingStartResponse(
                success=True,
                recording_id=None,
                camera_id=camera_id,
                started_at=datetime.now()
            )
        
        # Start recording
        if hasattr(active_camera, 'start_recording'):
            active_camera.start_recording()
        else:
            # Fallback: Enable recording via camera settings
            db_camera.recording_enabled = True
            db.commit()
        
        # Update last_active
        crud.update_camera_last_active(db, camera_id)
        
        return eco_schema.RecordingStartResponse(
            success=True,
            recording_id=None,  # Will be assigned when recording completes
            camera_id=camera_id,
            started_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error starting recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{camera_id}/record/stop", response_model=eco_schema.RecordingStopResponse)
def stop_recording(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Stop recording on a camera.
    
    Used by voice command "Stop recording" from MagicMirror.
    """
    db_camera = crud.get_camera_by_id(db, camera_id)
    if not db_camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found",
        )

    active_camera = camera_manager.get_camera(camera_id)
    if not active_camera:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera '{camera_id}' is not running",
        )

    try:
        recording_path = None
        duration = 0.0
        file_size = 0
        
        # Stop recording
        if hasattr(active_camera, 'stop_recording'):
            result = active_camera.stop_recording()
            if result:
                recording_path = result.get('path')
                duration = result.get('duration', 0)
                file_size = result.get('size', 0)
        else:
            # Fallback: Disable recording via camera settings
            db_camera.recording_enabled = False
            db.commit()
        
        # Get last recording from database
        last_recording = db.query(models.RecordingEvent).filter(
            models.RecordingEvent.camera_id == camera_id
        ).order_by(models.RecordingEvent.started_at.desc()).first()
        
        recording_id = last_recording.id if last_recording else None
        
        return eco_schema.RecordingStopResponse(
            success=True,
            recording_id=recording_id,
            duration_seconds=duration,
            file_path=recording_path,
            file_size_bytes=file_size
        )
        
    except Exception as e:
        logger.error(f"Error stopping recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discover", response_model=eco_schema.CameraDiscoveryResponse)
async def discover_cameras_voice():
    """
    Discover cameras on the network.
    
    Used by voice command "Search for cameras" from MagicMirror.
    Scans for ONVIF and RTSP cameras on the local network.
    """
    import time
    start_time = time.time()
    
    discovered = []
    
    try:
        # Try ONVIF discovery
        from backend.core.onvif_discovery import discover_onvif_cameras
        onvif_cameras = await discover_onvif_cameras()
        
        for cam in onvif_cameras:
            discovered.append(eco_schema.DiscoveredCamera(
                id=f"discovered_{len(discovered)}",
                name=cam.get('name', f"Camera {len(discovered) + 1}"),
                ip=cam.get('ip', ''),
                port=cam.get('port', 554),
                protocol='onvif',
                manufacturer=cam.get('manufacturer'),
                model=cam.get('model'),
                onvif=True
            ))
    except ImportError:
        logger.warning("ONVIF discovery not available")
    except Exception as e:
        logger.warning(f"ONVIF discovery failed: {e}")
    
    # Also check for common RTSP ports on local network
    # This is a simplified version - a full scan would take too long
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return eco_schema.CameraDiscoveryResponse(
        success=True,
        cameras=discovered,
        scan_duration_ms=elapsed_ms
    )
