# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Discovery API Routes
Endpoints for discovering and auto-configuring cameras
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
from sqlalchemy.orm import Session

from backend.core.camera_discovery import discovery_service
from backend.core.camera_manager import manager as camera_manager
from backend.database.session import get_db
from backend.database import crud

router = APIRouter()
logger = logging.getLogger(__name__)


class DiscoveryRequest(BaseModel):
    """Request model for network discovery"""

    subnet: Optional[str] = None  # e.g., "192.168.1.0/24"


class CameraTestRequest(BaseModel):
    """Request model for testing camera connection"""

    camera_type: str
    source: str


class QuickAddRequest(BaseModel):
    """Request model for quickly adding a discovered camera"""

    camera_id: str
    camera_type: str
    source: str
    name: Optional[str] = None
    enabled: bool = True


@router.post("/cameras/discover/usb", status_code=200)
async def discover_usb_cameras(db: Session = Depends(get_db)):
    """
    Discover USB and built-in cameras connected to the system.

    Returns:
        List of discovered USB cameras with auto-configuration details
        (excludes already-added cameras)
    """
    try:
        cameras = await discovery_service.discover_usb_cameras()

        # Filter out cameras that are already added
        # Get all existing camera sources from database
        existing_cameras = crud.get_all_cameras(db)
        existing_sources = {cam.source for cam in existing_cameras}

        # Filter USB cameras - check if source (index as string) already exists
        filtered_cameras = [
            cam for cam in cameras
            if str(cam.get('index', '')) not in existing_sources
        ]

        filtered_count = len(cameras) - len(filtered_cameras)
        message = f"Found {len(filtered_cameras)} USB camera(s)"
        if filtered_count > 0:
            message += f" ({filtered_count} already added)"

        return {
            "success": True,
            "count": len(filtered_cameras),
            "cameras": filtered_cameras,
            "message": message,
        }

    except Exception as e:
        logger.error(f"Error discovering USB cameras: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Discovery failed: {str(e)}")


@router.post("/cameras/discover/network", status_code=200)
async def discover_network_cameras(
    request: DiscoveryRequest, background_tasks: BackgroundTasks
):
    """
    Discover RTSP/IP cameras on the local network.

    This operation runs in the background as it may take 30-60 seconds.
    Use the /cameras/discover/status endpoint to check progress.

    Args:
        request: Optional subnet to scan (e.g., "192.168.1.0/24")

    Returns:
        Confirmation that discovery has started
    """
    if discovery_service.scanning:
        raise HTTPException(status_code=409,
                            detail="Network scan already in progress")

    # Start discovery in background
    background_tasks.add_task(_run_network_discovery, request.subnet)

    return {
        "success": True,
        "message": "Network discovery started",
        "note": "This may take 30-60 seconds. Use /cameras/discover/status to check progress",
    }


async def _run_network_discovery(subnet: Optional[str]):
    """Background task for network discovery"""
    try:
        cameras = await discovery_service.discover_network_cameras(subnet)
        discovery_service.discovered_cameras = cameras
        logger.info(
            f"Network discovery completed. Found {
                len(cameras)} cameras")
    except Exception as e:
        logger.error(f"Network discovery failed: {e}")


@router.get("/cameras/discover/status", status_code=200)
async def get_discovery_status(db: Session = Depends(get_db)):
    """
    Get the status of ongoing camera discovery.

    Returns:
        Discovery status and any cameras found (excludes already-added cameras)
    """
    status = discovery_service.get_discovery_status()

    # Get existing cameras to filter out
    existing_cameras = crud.get_all_cameras(db)
    existing_sources = {cam.source for cam in existing_cameras}

    # Filter discovered network cameras
    # Network cameras use RTSP URLs as source, check if any of the URLs match
    filtered_cameras = []
    if not status["scanning"]:
        for cam in discovery_service.discovered_cameras:
            # Check if any of the camera URLs are already in use
            urls = cam.get('urls', [])
            if not any(url in existing_sources for url in urls):
                filtered_cameras.append(cam)

    return {
        "scanning": status["scanning"],
        "cameras_found": len(filtered_cameras),
        "cameras": filtered_cameras,
    }


@router.post("/cameras/discover/test", status_code=200)
async def test_camera_connection(request: CameraTestRequest):
    """
    Test if a camera configuration works before adding it.

    Args:
        request: Camera configuration to test

    Returns:
        Test results with success status
    """
    try:
        result = await discovery_service.test_camera_connection(
            {"camera_type": request.camera_type, "source": request.source}
        )

        return result

    except Exception as e:
        logger.error(f"Error testing camera: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/cameras/quick-add", status_code=201)
async def quick_add_camera(
        request: QuickAddRequest,
        db: Session = Depends(get_db)):
    """
    Quickly add a discovered camera with auto-configured settings.

    Saves camera to database AND starts it in camera_manager for persistence.

    Args:
        request: Camera configuration from discovery
        db: Database session

    Returns:
        Success message with camera details
    """
    try:
        # Check if camera already exists in database
        existing_camera = crud.get_camera_by_id(db, request.camera_id)
        if existing_camera:
            raise HTTPException(
                status_code=400, detail=f"Camera '{
                    request.camera_id}' already exists")

        # Also check in-memory camera manager
        if camera_manager.get_camera(request.camera_id):
            raise HTTPException(
                status_code=400,
                detail=f"Camera '{request.camera_id}' is already running",
            )

        # Test the camera connection first
        test_result = await discovery_service.test_camera_connection(
            {"camera_type": request.camera_type, "source": request.source}
        )

        if not test_result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=f"Camera test failed: {
                    test_result.get(
                        'error',
                        'Unknown error')}",
            )

        # Save to database FIRST for persistence
        camera_data = {
            "camera_id": request.camera_id,
            "camera_type": request.camera_type,
            "source": request.source,
            "face_detection_enabled": True,  # Default settings
            "motion_detection_enabled": True,
            "recording_enabled": True,
            "is_active": True,
        }
        db_camera = crud.create_camera(db, camera_data)

        # Then add to camera_manager to start streaming
        try:
            camera_manager.add_camera(
                camera_id=request.camera_id,
                camera_type=request.camera_type,
                source=request.source,
            )

            # Verify it's running
            camera = camera_manager.get_camera(request.camera_id)
            if not camera or not camera.is_running:
                # If camera fails to start, remove from database
                crud.delete_camera(db, request.camera_id)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start camera '{request.camera_id}'",
                )
        except Exception as e:
            # If camera manager fails, remove from database
            crud.delete_camera(db, request.camera_id)
            raise HTTPException(
                status_code=500, detail=f"Error starting camera: {str(e)}"
            )

        return {
            "success": True,
            "message": f"Camera '{
                request.camera_id}' added successfully and saved to database",
            "camera": {
                "camera_id": request.camera_id,
                "type": request.camera_type,
                "source": request.source,
                "status": "running",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding camera: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add camera: {
                str(e)}")


@router.get("/cameras/discover/help", status_code=200)
async def get_discovery_help():
    """
    Get help information about camera discovery features.

    Returns:
        Helpful information about discovery methods and compatibility
    """
    return {
        "usb_discovery": {
            "description": "Automatically detects USB and built-in webcams",
            "platforms": ["Linux", "macOS", "Windows"],
            "instructions": "Simply click 'Scan for USB Cameras' - no configuration needed",
        },
        "network_discovery": {
            "description": "Scans local network for RTSP/IP cameras",
            "protocols": ["RTSP"],
            "ports_scanned": [554, 8554, 8080, 88],
            "duration": "30-60 seconds",
            "instructions": "Click 'Scan Network' to discover cameras on your local network",
            "note": "Most IP cameras require username/password authentication",
        },
        "compatible_cameras": {
            "usb": "Any USB webcam or built-in camera",
            "rtsp": "Most modern IP cameras (Hikvision, Dahua, Amcrest, Reolink, etc.)",
            "note": "Proprietary systems (Nest, Ring, Arlo) are not discoverable",
        },
        "common_credentials": {
            "note": "Try these if your camera requires authentication",
            "credentials": [
                {"username": "admin", "password": "admin"},
                {"username": "admin", "password": "12345"},
                {"username": "admin", "password": ""},
                {"username": "root", "password": "root"},
            ],
        },
    }
