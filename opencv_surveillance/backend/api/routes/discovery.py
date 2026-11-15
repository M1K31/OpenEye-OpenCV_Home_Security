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
import time
from sqlalchemy.orm import Session

from backend.core.camera_discovery import discovery_service
from backend.core.camera_manager import manager as camera_manager
from backend.core.camera_security import (
    inject_rtsp_credentials,
    redact_url_credentials,
    strip_url_credentials,
)
from backend.core.camera_validation import validate_camera_source
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
    username: Optional[str] = None
    password: Optional[str] = None


class QuickAddRequest(BaseModel):
    """Request model for quickly adding a discovered camera"""

    camera_id: str
    camera_type: str
    source: str
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
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
        result = await discovery_service.discover_usb_cameras_detailed()
        cameras = result["cameras"]

        # Filter out cameras that are already added
        existing_cameras = crud.get_cameras(db)
        existing_sources = {cam.source for cam in existing_cameras}

        filtered_cameras = [
            cam
            for cam in cameras
            if str(cam.get("index", "")) not in existing_sources
        ]

        filtered_count = len(cameras) - len(filtered_cameras)
        message = f"Found {len(filtered_cameras)} USB camera(s)"
        if filtered_count > 0:
            message += f" ({filtered_count} already added)"

        if result["permission_denied"]:
            message = (
                "No cameras could be opened, but the system reports "
                f"{len(result['platform_cameras'])} attached. "
                "Camera permission appears to be denied."
            )

        return {
            "success": True,
            "count": len(filtered_cameras),
            "cameras": filtered_cameras,
            "message": message,
            "warnings": result["warnings"],
            "permission_denied": result["permission_denied"],
        }

    except Exception as e:
        logger.error(f"Error discovering USB cameras: {e}")
        raise HTTPException(
            status_code=500, detail=f"Discovery failed: {str(e)}"
        )


@router.post("/cameras/discover/network", status_code=200)
async def discover_network_cameras(
    request: DiscoveryRequest, background_tasks: BackgroundTasks
):
    """
    Discover RTSP/IP cameras on the local network.

    This operation runs in the background. Use /cameras/discover/status to
    stream incremental and final discovery results.
    """
    if discovery_service.scanning:
        scan_start = getattr(discovery_service, "_scan_start_time", 0)
        if time.time() - scan_start > 120:  # 2 minute timeout
            logger.warning("Network scan appears stuck, auto-resetting...")
            discovery_service.scanning = False
        else:
            raise HTTPException(
                status_code=409, detail="Network scan already in progress"
            )

    discovery_service.scanning = True
    discovery_service.discovered_cameras = []
    discovery_service._scan_start_time = time.time()
    background_tasks.add_task(_run_network_discovery, request.subnet)

    return {
        "success": True,
        "message": "Network discovery started",
        "note": "Check /cameras/discover/status for live progress",
    }


@router.post("/cameras/discover/network/cancel", status_code=200)
async def cancel_network_discovery():
    """
    Cancel an ongoing network discovery scan.
    """
    was_scanning = discovery_service.scanning
    discovery_service.scanning = False
    discovery_service._scan_start_time = 0

    return {
        "success": True,
        "was_scanning": was_scanning,
        "message": (
            "Network scan cancelled"
            if was_scanning
            else "No scan was in progress"
        ),
    }


async def _run_network_discovery(subnet: Optional[str]):
    """Background task for network discovery"""
    try:
        cameras = await discovery_service.discover_network_cameras(subnet)
        discovery_service.discovered_cameras = cameras
        logger.info(
            f"Network discovery completed. Found {len(cameras)} cameras"
        )
    except Exception as e:
        logger.error(f"Network discovery failed: {e}")
    finally:
        discovery_service.scanning = False
        discovery_service._scan_start_time = 0


@router.get("/cameras/discover/status", status_code=200)
async def get_discovery_status(db: Session = Depends(get_db)):
    """
    Get the status of ongoing or completed camera discovery.

    Returns incremental and final cameras found (excluding already-added cameras,
    matching even when stored cameras have embedded credentials).
    """
    status = discovery_service.get_discovery_status()

    existing_cameras = crud.get_cameras(db)
    existing_sources = set()
    for cam in existing_cameras:
        if cam.source:
            existing_sources.add(cam.source)
            stripped = strip_url_credentials(cam.source)
            if stripped:
                existing_sources.add(stripped)

    filtered_cameras = []
    for cam in list(discovery_service.discovered_cameras):
        urls = cam.get("urls", [])
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
    """
    try:
        final_source = request.source
        if request.camera_type != "usb" and (request.username or request.password):
            final_source = inject_rtsp_credentials(
                request.source,
                username=request.username,
                password=request.password,
            )

        if request.camera_type in ("rtsp", "rtmp", "onvif", "usb", "mock"):
            validate_camera_source(final_source, request.camera_type)

        result = await discovery_service.test_camera_connection(
            {
                "camera_type": request.camera_type,
                "source": final_source,
            }
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing camera: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/cameras/quick-add", status_code=201)
async def quick_add_camera(
    request: QuickAddRequest, db: Session = Depends(get_db)
):
    """
    Quickly add a discovered camera with auto-configured settings.

    Injects URL-encoded credentials if provided, encrypts the source URL at rest
    in SQLite, and starts the stream in camera_manager.
    """
    try:
        existing_camera = crud.get_camera_by_id(db, request.camera_id)
        if existing_camera:
            raise HTTPException(
                status_code=400,
                detail=f"Camera '{request.camera_id}' already exists",
            )

        if camera_manager.get_camera(request.camera_id):
            raise HTTPException(
                status_code=400,
                detail=f"Camera '{request.camera_id}' is already running",
            )

        final_source = request.source
        if request.camera_type != "usb" and (request.username or request.password):
            final_source = inject_rtsp_credentials(
                request.source,
                username=request.username,
                password=request.password,
            )

        validate_camera_source(final_source, request.camera_type)

        test_result = await discovery_service.test_camera_connection(
            {"camera_type": request.camera_type, "source": final_source}
        )

        if not test_result.get("success"):
            error_msg = test_result.get("error", "Unknown error")
            raise HTTPException(
                status_code=400,
                detail=f"Camera test failed: {error_msg}",
            )

        # Save to database FIRST for persistence (EncryptedCameraSource encrypts at rest)
        camera_data = {
            "camera_id": request.camera_id,
            "camera_type": request.camera_type,
            "source": final_source,
            "face_detection_enabled": True,
            "motion_detection_enabled": True,
            "recording_enabled": True,
            "is_active": True,
        }
        crud.create_camera(db, camera_data)

        try:
            camera_manager.add_camera(
                camera_id=request.camera_id,
                camera_type=request.camera_type,
                source=final_source,
            )

            camera = camera_manager.get_camera(request.camera_id)
            if not camera or not camera.is_running:
                crud.delete_camera(db, request.camera_id)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to start camera '{request.camera_id}'",
                )
        except HTTPException:
            raise
        except Exception as e:
            crud.delete_camera(db, request.camera_id)
            raise HTTPException(
                status_code=500, detail=f"Error starting camera: {str(e)}"
            )

        return {
            "success": True,
            "message": f"Camera '{request.camera_id}' added successfully and saved to database",
            "camera": {
                "camera_id": request.camera_id,
                "type": request.camera_type,
                "source": redact_url_credentials(final_source),
                "status": "running",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding camera: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to add camera: {str(e)}"
        )


@router.get("/cameras/discover/help", status_code=200)
async def get_discovery_help():
    """
    Get help information about camera discovery features.
    """
    return {
        "usb_discovery": {
            "description": "Automatically detects USB and built-in webcams",
            "platforms": ["Linux", "macOS", "Windows"],
            "instructions": "Simply click 'Scan for USB Cameras' - no configuration needed",
        },
        "network_discovery": {
            "description": "Scans local network for RTSP/IP/ONVIF cameras using ARP-prioritized probing",
            "protocols": ["RTSP", "ONVIF"],
            "ports_scanned": [554, 8554, 8080, 88, 2020],
            "duration": "1-15 seconds",
            "instructions": "Click 'Scan Network' to discover cameras on your local network",
            "note": "Credentials are URL-encoded and encrypted at rest using Fernet",
        },
        "compatible_cameras": {
            "usb": "Any USB webcam, built-in camera, or Apple Continuity Camera",
            "rtsp": "TP-Link Tapo, Hikvision, Dahua, Amcrest, Reolink, Axis, Ubiquiti UniFi, Foscam, Generic ONVIF",
            "note": "Cloud-only cameras without local RTSP (Ring, Arlo) are not discoverable",
        },
        "common_credentials": {
            "note": "For TP-Link Tapo, use the Camera Account created in the Tapo app (Settings -> Advanced -> Camera Account)",
            "credentials": [
                {"username": "admin", "password": "admin"},
                {"username": "admin", "password": "12345"},
                {"username": "admin", "password": ""},
                {"username": "root", "password": "root"},
            ],
        },
    }


@router.get("/cameras/relay/status", status_code=200)
async def get_stream_relay_status():
    """
    Get the status of the optional RTSP/WebRTC stream relay (go2rtc or MediaMTX).
    """
    from backend.core.stream_relay import stream_relay

    return stream_relay.get_status()

