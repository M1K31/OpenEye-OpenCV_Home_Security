# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Discovery API Routes
Endpoints for discovering and auto-configuring cameras
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging

from backend.core.camera_discovery import discovery_service
from backend.core.camera_manager import manager as camera_manager

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
async def discover_usb_cameras():
    """
    Discover USB and built-in cameras connected to the system.
    
    Returns:
        List of discovered USB cameras with auto-configuration details
    """
    try:
        cameras = await discovery_service.discover_usb_cameras()
        
        return {
            "success": True,
            "count": len(cameras),
            "cameras": cameras,
            "message": f"Found {len(cameras)} USB camera(s)"
        }
    
    except Exception as e:
        logger.error(f"Error discovering USB cameras: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.post("/cameras/discover/network", status_code=200)
async def discover_network_cameras(
    request: DiscoveryRequest,
    background_tasks: BackgroundTasks
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
        raise HTTPException(
            status_code=409,
            detail="Network scan already in progress"
        )
    
    # Start discovery in background
    background_tasks.add_task(
        _run_network_discovery,
        request.subnet
    )
    
    return {
        "success": True,
        "message": "Network discovery started",
        "note": "This may take 30-60 seconds. Use /cameras/discover/status to check progress"
    }


async def _run_network_discovery(subnet: Optional[str]):
    """Background task for network discovery"""
    try:
        cameras = await discovery_service.discover_network_cameras(subnet)
        discovery_service.discovered_cameras = cameras
        logger.info(f"Network discovery completed. Found {len(cameras)} cameras")
    except Exception as e:
        logger.error(f"Network discovery failed: {e}")


@router.get("/cameras/discover/status", status_code=200)
async def get_discovery_status():
    """
    Get the status of ongoing camera discovery.
    
    Returns:
        Discovery status and any cameras found
    """
    status = discovery_service.get_discovery_status()
    
    return {
        "scanning": status['scanning'],
        "cameras_found": len(discovery_service.discovered_cameras),
        "cameras": discovery_service.discovered_cameras if not status['scanning'] else []
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
        result = await discovery_service.test_camera_connection({
            'camera_type': request.camera_type,
            'source': request.source
        })
        
        return result
    
    except Exception as e:
        logger.error(f"Error testing camera: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/cameras/quick-add", status_code=201)
async def quick_add_camera(request: QuickAddRequest):
    """
    Quickly add a discovered camera with auto-configured settings.
    
    Args:
        request: Camera configuration from discovery
    
    Returns:
        Success message with camera details
    """
    try:
        # Check if camera already exists
        if camera_manager.get_camera(request.camera_id):
            raise HTTPException(
                status_code=400,
                detail=f"Camera '{request.camera_id}' already exists"
            )
        
        # Test the camera connection first
        test_result = await discovery_service.test_camera_connection({
            'camera_type': request.camera_type,
            'source': request.source
        })
        
        if not test_result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=f"Camera test failed: {test_result.get('error', 'Unknown error')}"
            )
        
        # Add the camera
        camera_manager.add_camera(
            camera_id=request.camera_id,
            camera_type=request.camera_type,
            source=request.source
        )
        
        # Verify it's running
        camera = camera_manager.get_camera(request.camera_id)
        if not camera or not camera.is_running:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start camera '{request.camera_id}'"
            )
        
        return {
            "success": True,
            "message": f"Camera '{request.camera_id}' added successfully",
            "camera": {
                "camera_id": request.camera_id,
                "type": request.camera_type,
                "source": request.source,
                "status": "running"
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding camera: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add camera: {str(e)}")


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
            "instructions": "Simply click 'Scan for USB Cameras' - no configuration needed"
        },
        "network_discovery": {
            "description": "Scans local network for RTSP/IP cameras",
            "protocols": ["RTSP"],
            "ports_scanned": [554, 8554, 8080, 88],
            "duration": "30-60 seconds",
            "instructions": "Click 'Scan Network' to discover cameras on your local network",
            "note": "Most IP cameras require username/password authentication"
        },
        "compatible_cameras": {
            "usb": "Any USB webcam or built-in camera",
            "rtsp": "Most modern IP cameras (Hikvision, Dahua, Amcrest, Reolink, etc.)",
            "note": "Proprietary systems (Nest, Ring, Arlo) are not discoverable"
        },
        "common_credentials": {
            "note": "Try these if your camera requires authentication",
            "credentials": [
                {"username": "admin", "password": "admin"},
                {"username": "admin", "password": "12345"},
                {"username": "admin", "password": ""},
                {"username": "root", "password": "root"}
            ]
        }
    }
