"""
PTZ Control API Routes
Handles Pan-Tilt-Zoom camera control operations with automatic credential and
port resolution across ONVIF (TP-Link Tapo :2020, Hikvision/Dahua/Axis :80,
Reolink :8000, Generic :8080/:8899) and vendor HTTP CGI protocols.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json

from backend.database.session import get_db
from backend.database import crud
from backend.database.models import PTZPreset, PTZPatrolPattern
from backend.core.ptz_controller import get_ptz_controller, remove_ptz_controller, PTZController
from backend.core.camera_security import extract_camera_connection_info
from backend.core.auth import get_current_user
from pydantic import BaseModel, Field

router = APIRouter()


# ===== Pydantic Schemas =====

class PTZMoveRequest(BaseModel):
    """Request schema for PTZ absolute movement commands"""
    pan: float = Field(..., ge=-1.0, le=1.0, description="Pan position (-1.0 to 1.0)")
    tilt: float = Field(..., ge=-1.0, le=1.0, description="Tilt position (-1.0 to 1.0)")
    zoom: float = Field(0.0, ge=0.0, le=1.0, description="Zoom level (0.0 to 1.0)")
    speed: float = Field(0.5, ge=0.0, le=1.0, description="Movement speed (0.0 to 1.0)")


class PTZRelativeMoveRequest(BaseModel):
    """Request schema for PTZ relative step movement commands"""
    pan_delta: float = Field(0.0, ge=-1.0, le=1.0, description="Pan step (-1.0 to 1.0)")
    tilt_delta: float = Field(0.0, ge=-1.0, le=1.0, description="Tilt step (-1.0 to 1.0)")
    zoom_delta: float = Field(0.0, ge=-1.0, le=1.0, description="Zoom step (-1.0 to 1.0)")
    speed: float = Field(0.5, ge=0.0, le=1.0, description="Movement speed (0.0 to 1.0)")


class PTZContinuousMoveRequest(BaseModel):
    """Request schema for continuous PTZ movement"""
    pan_velocity: float = Field(..., ge=-1.0, le=1.0, description="Pan velocity (-1.0 to 1.0)")
    tilt_velocity: float = Field(..., ge=-1.0, le=1.0, description="Tilt velocity (-1.0 to 1.0)")
    zoom_velocity: float = Field(0.0, ge=-1.0, le=1.0, description="Zoom velocity (-1.0 to 1.0)")


class PTZConnectionRequest(BaseModel):
    """
    Request schema for PTZ connection.
    All fields are optional: when omitted, OpenEye automatically extracts the
    camera IP and decrypted credentials from the camera's stored RTSP source.
    """
    camera_ip: Optional[str] = Field(None, description="Camera IP address (auto-detected if omitted)")
    port: Optional[int] = Field(None, description="ONVIF/PTZ port (auto-probed if omitted or 0)")
    username: Optional[str] = Field(None, description="Camera username (auto-detected if omitted)")
    password: Optional[str] = Field(None, description="Camera password (auto-detected if omitted)")
    ptz_type: str = Field("auto", description="PTZ protocol type (auto, onvif, hikvision_isapi, dahua_cgi, reolink_api, axis_vapix)")


class PTZPresetCreate(BaseModel):
    """Request schema for creating PTZ preset"""
    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    preset_number: int = Field(..., ge=1, le=255, description="Preset slot number (1-255)")
    pan: float = Field(0.0, ge=-1.0, le=1.0, description="Pan position")
    tilt: float = Field(0.0, ge=-1.0, le=1.0, description="Tilt position")
    zoom: float = Field(0.0, ge=0.0, le=1.0, description="Zoom level")


class PTZPresetUpdate(BaseModel):
    """Request schema for updating PTZ preset"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Preset name")
    pan: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Pan position")
    tilt: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Tilt position")
    zoom: Optional[float] = Field(None, ge=0.0, le=1.0, description="Zoom level")


class PatrolPatternStep(BaseModel):
    """Single step in a patrol pattern"""
    preset_id: Optional[int] = Field(None, description="Preset ID to move to")
    pan: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Pan position (if not using preset)")
    tilt: Optional[float] = Field(None, ge=-1.0, le=1.0, description="Tilt position (if not using preset)")
    zoom: Optional[float] = Field(None, ge=0.0, le=1.0, description="Zoom level (if not using preset)")
    dwell_time: int = Field(5, ge=1, le=300, description="Time to stay at position (seconds)")


class PTZPatrolPatternCreate(BaseModel):
    """Request schema for creating patrol pattern"""
    name: str = Field(..., min_length=1, max_length=100, description="Pattern name")
    description: Optional[str] = Field(None, max_length=500, description="Pattern description")
    pattern_steps: List[PatrolPatternStep] = Field(..., min_items=2, description="Pattern steps (at least 2)")
    loop_enabled: bool = Field(True, description="Loop pattern continuously")
    interval_seconds: int = Field(10, ge=1, le=300, description="Default interval between positions")


class PTZPatrolPatternUpdate(BaseModel):
    """Request schema for updating patrol pattern"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    pattern_steps: Optional[List[PatrolPatternStep]] = Field(None, min_items=2)
    loop_enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(None, ge=1, le=300)


async def _ensure_ptz_connected(camera, controller: PTZController) -> bool:
    """
    Lazily auto-connect a camera's PTZ controller using credentials stored in
    `camera.source` if not already connected.
    """
    if controller.is_connected:
        return True
    if not camera or not camera.source:
        return False
    return await controller.auto_connect_from_source(camera.source)


# ===== PTZ Control Endpoints =====

@router.post("/cameras/{camera_id}/ptz/connect")
async def connect_ptz(
    camera_id: str,
    connection: Optional[PTZConnectionRequest] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Connect to PTZ camera. Automatically uses the camera's stored IP and
    decrypted credentials from SQLite when fields are omitted.
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    conn_req = connection or PTZConnectionRequest()
    stored_info = extract_camera_connection_info(camera.source)

    stored_ip = (stored_info.get("camera_ip") or "").strip()
    requested_ip = (conn_req.camera_ip or "").strip()
    target_ip = requested_ip or stored_ip
    vendor_hint = stored_info.get("vendor_hint", "generic")

    if not target_ip:
        raise HTTPException(
            status_code=400,
            detail="Camera IP address could not be determined from camera source; please provide camera_ip.",
        )

    # Connecting to a host other than the camera's stored address is an override.
    # The stored credentials belong to the stored host and must never be sent to
    # a caller-chosen one (that would exfiltrate them via SSRF), so an override
    # requires an administrator and credentials supplied in the request.
    host_overridden = bool(requested_ip) and requested_ip != stored_ip
    if host_overridden:
        if getattr(current_user, "role", None) != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only an administrator may connect PTZ to a host other than the camera's stored address.",
            )
        if not (conn_req.username and conn_req.password):
            raise HTTPException(
                status_code=400,
                detail="username and password must be supplied in the request when overriding the camera host; "
                       "the camera's stored credentials are not used for a different host.",
            )
        target_user = conn_req.username
        target_pass = conn_req.password
    else:
        # Same host as stored (or no override): stored credentials may fill in.
        target_user = conn_req.username if conn_req.username else stored_info.get("username", "")
        target_pass = conn_req.password if conn_req.password else stored_info.get("password", "")
    target_port = conn_req.port or 0

    controller = get_ptz_controller(camera_id, conn_req.ptz_type or "auto")
    success = await controller.connect(
        camera_ip=target_ip,
        port=target_port,
        username=target_user,
        password=target_pass,
        vendor_hint=vendor_hint,
    )

    if not success:
        raise HTTPException(
            status_code=502,
            detail=controller.last_error or f"Failed to connect to PTZ service at {target_ip}",
        )

    status = await controller.get_status()
    return {
        "message": "PTZ connected successfully",
        "camera_id": camera_id,
        "connected": True,
        "camera_ip": controller.camera_ip,
        "port": controller.port,
        "protocol": controller.active_protocol,
        "vendor_hint": controller.vendor_hint,
        "device_info": controller.device_info,
        "status": status,
    }


@router.post("/cameras/{camera_id}/ptz/disconnect")
async def disconnect_ptz(
    camera_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Disconnect PTZ camera"""
    remove_ptz_controller(camera_id)
    return {"message": "PTZ disconnected successfully", "camera_id": camera_id}


@router.post("/cameras/{camera_id}/ptz/move/absolute")
async def move_absolute(
    camera_id: str,
    move_request: PTZMoveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Move camera to absolute position (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    success = await controller.move_absolute(
        pan=move_request.pan,
        tilt=move_request.tilt,
        zoom=move_request.zoom,
        speed=move_request.speed
    )

    if not success:
        raise HTTPException(status_code=500, detail="PTZ move command failed")

    return {
        "message": "PTZ moved successfully",
        "position": {
            "pan": move_request.pan,
            "tilt": move_request.tilt,
            "zoom": move_request.zoom
        }
    }


@router.post("/cameras/{camera_id}/ptz/move/relative")
async def move_relative(
    camera_id: str,
    move_request: PTZRelativeMoveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Move camera by a relative step (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    success = await controller.move_relative(
        pan_delta=move_request.pan_delta,
        tilt_delta=move_request.tilt_delta,
        zoom_delta=move_request.zoom_delta,
        speed=move_request.speed,
    )

    if not success:
        raise HTTPException(status_code=500, detail="PTZ relative move command failed")

    return {
        "message": "PTZ relative move completed",
        "position": controller.current_position,
    }


@router.post("/cameras/{camera_id}/ptz/move/continuous")
async def move_continuous(
    camera_id: str,
    move_request: PTZContinuousMoveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Start continuous camera movement (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    success = await controller.move_continuous(
        pan_velocity=move_request.pan_velocity,
        tilt_velocity=move_request.tilt_velocity,
        zoom_velocity=move_request.zoom_velocity
    )

    if not success:
        raise HTTPException(status_code=500, detail="PTZ continuous move command failed")

    return {"message": "PTZ continuous move started"}


@router.post("/cameras/{camera_id}/ptz/stop")
async def stop_ptz(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Stop all PTZ movement."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        return {"message": "PTZ already stopped", "camera_id": camera_id}

    success = await controller.stop()
    if not success:
        raise HTTPException(status_code=500, detail="PTZ stop command failed")

    return {"message": "PTZ stopped successfully"}


@router.post("/cameras/{camera_id}/ptz/home")
async def goto_home_position(
    camera_id: str,
    speed: float = 0.5,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Move camera to its Home position (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    success = await controller.goto_home(speed=speed)
    if not success:
        raise HTTPException(status_code=500, detail="PTZ Home command failed")

    return {"message": "Moved to Home position", "position": controller.current_position}


@router.get("/cameras/{camera_id}/ptz/status")
async def get_ptz_status(
    camera_id: str,
    auto_connect: bool = Query(True, description="Automatically connect using stored camera credentials if disconnected"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get current PTZ status, discovered capabilities, and connection metadata.
    When `auto_connect=True` (the default), automatically connects using the
    camera's stored RTSP credentials so the UI requires zero manual setup.
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    stored_info = extract_camera_connection_info(camera.source)
    controller = get_ptz_controller(camera_id)

    if not controller.is_connected and auto_connect and stored_info.get("is_network_camera"):
        await controller.auto_connect_from_source(camera.source)

    if not controller.is_connected:
        default_port = 2020 if stored_info.get("vendor_hint") == "tapo" else 80
        return {
            "camera_id": camera_id,
            "connected": False,
            "camera_ip": stored_info.get("camera_ip", ""),
            "port": default_port,
            "vendor_hint": stored_info.get("vendor_hint", "generic"),
            "has_stored_credentials": bool(stored_info.get("username")),
            "last_error": controller.last_error,
            "status": None,
        }

    status = await controller.get_status()
    return {
        "camera_id": camera_id,
        "connected": controller.is_connected,
        "camera_ip": controller.camera_ip,
        "port": controller.port,
        "protocol": controller.active_protocol,
        "vendor_hint": controller.vendor_hint,
        "device_info": controller.device_info,
        "has_stored_credentials": bool(stored_info.get("username")),
        "status": status,
    }


# ===== Preset Endpoints =====

@router.get("/cameras/{camera_id}/ptz/presets")
async def list_presets(
    camera_id: str,
    sync_hardware: bool = Query(True, description="Import presets stored on the camera hardware if none exist in DB"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all PTZ presets for a camera (automatically importing hardware presets
    when the database has none yet).
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    presets = crud.get_ptz_presets_by_camera(db, camera_id)

    if not presets and sync_hardware:
        controller = get_ptz_controller(camera_id)
        if controller.is_connected:
            hw_presets = await controller.get_hardware_presets()
            for hw in hw_presets:
                existing = crud.get_ptz_preset_by_number(db, camera_id, hw["preset_number"])
                if not existing:
                    crud.create_ptz_preset(
                        db,
                        camera_id,
                        {
                            "name": hw["name"],
                            "preset_number": hw["preset_number"],
                            "pan": hw["pan"],
                            "tilt": hw["tilt"],
                            "zoom": hw["zoom"],
                        },
                    )
            if hw_presets:
                presets = crud.get_ptz_presets_by_camera(db, camera_id)

    return {
        "camera_id": camera_id,
        "presets": [
            {
                "id": preset.id,
                "name": preset.name,
                "preset_number": preset.preset_number,
                "pan": preset.pan,
                "tilt": preset.tilt,
                "zoom": preset.zoom,
                "thumbnail_path": preset.thumbnail_path,
                "created_at": preset.created_at.isoformat() if preset.created_at else None,
                "last_used_at": preset.last_used_at.isoformat() if preset.last_used_at else None,
                "usage_count": preset.usage_count
            }
            for preset in presets
        ],
        "total": len(presets)
    }


@router.post("/cameras/{camera_id}/ptz/presets")
async def create_preset(
    camera_id: str,
    preset: PTZPresetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new PTZ preset for a camera and save it to camera hardware."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    existing = crud.get_ptz_preset_by_number(db, camera_id, preset.preset_number)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Preset number {preset.preset_number} already exists for this camera"
        )

    controller = get_ptz_controller(camera_id)
    await _ensure_ptz_connected(camera, controller)

    preset_data = preset.dict()
    if controller.is_connected:
        pos = controller.current_position
        if preset_data.get("pan") == 0.0 and preset_data.get("tilt") == 0.0:
            preset_data["pan"] = pos.get("pan", 0.0)
            preset_data["tilt"] = pos.get("tilt", 0.0)
            preset_data["zoom"] = pos.get("zoom", 0.0)
        await controller.set_preset(preset.preset_number, preset.name)

    new_preset = crud.create_ptz_preset(db, camera_id, preset_data)

    return {
        "message": "Preset created successfully",
        "preset": {
            "id": new_preset.id,
            "name": new_preset.name,
            "preset_number": new_preset.preset_number,
            "pan": new_preset.pan,
            "tilt": new_preset.tilt,
            "zoom": new_preset.zoom
        }
    }


@router.get("/cameras/{camera_id}/ptz/presets/{preset_id}")
async def get_preset(
    camera_id: str,
    preset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific PTZ preset"""
    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    return {
        "id": preset.id,
        "name": preset.name,
        "preset_number": preset.preset_number,
        "pan": preset.pan,
        "tilt": preset.tilt,
        "zoom": preset.zoom,
        "thumbnail_path": preset.thumbnail_path,
        "created_at": preset.created_at.isoformat() if preset.created_at else None,
        "last_used_at": preset.last_used_at.isoformat() if preset.last_used_at else None,
        "usage_count": preset.usage_count
    }


@router.put("/cameras/{camera_id}/ptz/presets/{preset_id}")
async def update_preset(
    camera_id: str,
    preset_id: int,
    preset_update: PTZPresetUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a PTZ preset"""
    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    updated_preset = crud.update_ptz_preset(db, preset_id, preset_update.dict(exclude_unset=True))

    controller = get_ptz_controller(camera_id)
    if controller.is_connected and (preset_update.pan or preset_update.tilt or preset_update.zoom):
        await controller.set_preset(preset.preset_number, updated_preset.name)

    return {
        "message": "Preset updated successfully",
        "preset": {
            "id": updated_preset.id,
            "name": updated_preset.name,
            "preset_number": updated_preset.preset_number,
            "pan": updated_preset.pan,
            "tilt": updated_preset.tilt,
            "zoom": updated_preset.zoom
        }
    }


@router.delete("/cameras/{camera_id}/ptz/presets/{preset_id}")
async def delete_preset(
    camera_id: str,
    preset_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a PTZ preset"""
    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    crud.delete_ptz_preset(db, preset_id)

    return {"message": "Preset deleted successfully"}


@router.post("/cameras/{camera_id}/ptz/presets/{preset_id}/goto")
async def goto_preset(
    camera_id: str,
    preset_id: int,
    speed: float = 0.5,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Move camera to a saved preset position (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    success = await controller.goto_preset(preset.preset_number, speed)
    if not success:
        # Fallback to stored coordinates if hardware preset slot wasn't set
        success = await controller.move_absolute(preset.pan, preset.tilt, preset.zoom, speed)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to move to preset")

    crud.increment_preset_usage(db, preset_id)

    return {
        "message": "Moved to preset successfully",
        "preset": {
            "id": preset.id,
            "name": preset.name,
            "pan": preset.pan,
            "tilt": preset.tilt,
            "zoom": preset.zoom
        }
    }


# ===== Patrol Pattern Endpoints =====

@router.get("/cameras/{camera_id}/ptz/patrol-patterns")
async def list_patrol_patterns(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List all patrol patterns for a camera"""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    patterns = crud.get_patrol_patterns_by_camera(db, camera_id)

    return {
        "camera_id": camera_id,
        "patterns": [
            {
                "id": pattern.id,
                "name": pattern.name,
                "description": pattern.description,
                "pattern_steps": json.loads(pattern.pattern_steps),
                "is_active": pattern.is_active,
                "loop_enabled": pattern.loop_enabled,
                "interval_seconds": pattern.interval_seconds,
                "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
                "last_run_at": pattern.last_run_at.isoformat() if pattern.last_run_at else None,
                "run_count": pattern.run_count
            }
            for pattern in patterns
        ],
        "total": len(patterns)
    }


@router.post("/cameras/{camera_id}/ptz/patrol-patterns")
async def create_patrol_pattern(
    camera_id: str,
    pattern: PTZPatrolPatternCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new patrol pattern for a camera"""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    pattern_steps_dict = [step.dict() for step in pattern.pattern_steps]

    new_pattern = crud.create_patrol_pattern(
        db,
        camera_id,
        {
            "name": pattern.name,
            "description": pattern.description,
            "pattern_steps": json.dumps(pattern_steps_dict),
            "loop_enabled": pattern.loop_enabled,
            "interval_seconds": pattern.interval_seconds
        }
    )

    return {
        "message": "Patrol pattern created successfully",
        "pattern": {
            "id": new_pattern.id,
            "name": new_pattern.name,
            "description": new_pattern.description,
            "pattern_steps": pattern_steps_dict,
            "loop_enabled": new_pattern.loop_enabled,
            "interval_seconds": new_pattern.interval_seconds
        }
    }


@router.get("/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}")
async def get_patrol_pattern(
    camera_id: str,
    pattern_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific patrol pattern"""
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "pattern_steps": json.loads(pattern.pattern_steps),
        "is_active": pattern.is_active,
        "loop_enabled": pattern.loop_enabled,
        "interval_seconds": pattern.interval_seconds,
        "created_at": pattern.created_at.isoformat() if pattern.created_at else None,
        "last_run_at": pattern.last_run_at.isoformat() if pattern.last_run_at else None,
        "run_count": pattern.run_count
    }


@router.put("/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}")
async def update_patrol_pattern(
    camera_id: str,
    pattern_id: int,
    pattern_update: PTZPatrolPatternUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a patrol pattern"""
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    if pattern.is_active:
        await stop_patrol_pattern(camera_id, pattern_id, db, current_user)

    update_data = pattern_update.dict(exclude_unset=True)
    if "pattern_steps" in update_data and update_data["pattern_steps"]:
        update_data["pattern_steps"] = json.dumps([step.dict() for step in update_data["pattern_steps"]])

    updated_pattern = crud.update_patrol_pattern(db, pattern_id, update_data)

    return {
        "message": "Patrol pattern updated successfully",
        "pattern": {
            "id": updated_pattern.id,
            "name": updated_pattern.name,
            "description": updated_pattern.description,
            "pattern_steps": json.loads(updated_pattern.pattern_steps),
            "loop_enabled": updated_pattern.loop_enabled,
            "interval_seconds": updated_pattern.interval_seconds
        }
    }


@router.delete("/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}")
async def delete_patrol_pattern(
    camera_id: str,
    pattern_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a patrol pattern"""
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    if pattern.is_active:
        await stop_patrol_pattern(camera_id, pattern_id, db, current_user)

    crud.delete_patrol_pattern(db, pattern_id)

    return {"message": "Patrol pattern deleted successfully"}


@router.post("/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}/start")
async def start_patrol_pattern(
    camera_id: str,
    pattern_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Start executing a patrol pattern (auto-connects if needed)."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    controller = get_ptz_controller(camera_id)
    if not await _ensure_ptz_connected(camera, controller):
        raise HTTPException(status_code=400, detail=controller.last_error or "PTZ not connected")

    crud.update_patrol_pattern(db, pattern_id, {"is_active": True, "last_run_at": datetime.utcnow()})
    background_tasks.add_task(execute_patrol_pattern, camera_id, pattern_id)

    return {
        "message": "Patrol pattern started successfully",
        "pattern_id": pattern_id,
        "name": pattern.name
    }


@router.post("/cameras/{camera_id}/ptz/patrol-patterns/{pattern_id}/stop")
async def stop_patrol_pattern(
    camera_id: str,
    pattern_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Stop executing a patrol pattern"""
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
    crud.increment_patrol_run_count(db, pattern_id)

    return {
        "message": "Patrol pattern stopped successfully",
        "pattern_id": pattern_id
    }


# ===== Background Task: Execute Patrol Pattern =====

async def execute_patrol_pattern(camera_id: str, pattern_id: int):
    """Background task to execute patrol pattern"""
    from backend.database.session import SessionLocal

    db = SessionLocal()
    try:
        pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
        if not pattern:
            return

        controller = get_ptz_controller(camera_id)
        if not controller.is_connected:
            return

        pattern_steps = json.loads(pattern.pattern_steps)

        while pattern.is_active:
            pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
            if not pattern or not pattern.is_active:
                break

            for step in pattern_steps:
                pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
                if not pattern or not pattern.is_active:
                    break

                if "preset_id" in step and step["preset_id"]:
                    preset = crud.get_ptz_preset_by_id(db, step["preset_id"])
                    if preset:
                        await controller.goto_preset(preset.preset_number)
                        crud.increment_preset_usage(db, step["preset_id"])
                else:
                    await controller.move_absolute(
                        pan=step.get("pan", 0.0),
                        tilt=step.get("tilt", 0.0),
                        zoom=step.get("zoom", 0.5)
                    )

                dwell_time = step.get("dwell_time", pattern.interval_seconds)
                await asyncio.sleep(dwell_time)

            if not pattern.loop_enabled:
                crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
                crud.increment_patrol_run_count(db, pattern_id)
                break

    except Exception as e:
        print(f"Error executing patrol pattern {pattern_id}: {e}")
        crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
    finally:
        db.close()


# ============================================================================
# MULTI-VENDOR CAMERA EDGE AI & HARDWARE CONTROL ENDPOINTS
# ============================================================================

from backend.core.camera_edge_features import edge_manager


class EdgeSettingsUpdateRequest(BaseModel):
    """Request schema for updating camera Edge AI & Hardware controls"""
    edge_ai_enabled: Optional[bool] = None
    person_detection: Optional[bool] = None
    vehicle_detection: Optional[bool] = None
    pet_detection: Optional[bool] = None
    package_detection: Optional[bool] = None
    audio_alarm_detection: Optional[bool] = None
    motion_detection: Optional[bool] = None
    auto_tracking: Optional[bool] = None
    privacy_mode: Optional[bool] = None
    night_vision_mode: Optional[str] = Field(
        None, description="Night vision mode: auto, ir, color, off"
    )
    wdr_enabled: Optional[bool] = None
    status_led_enabled: Optional[bool] = None
    trigger_recording_on_edge_ai: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=2, le=300)


class SirenTriggerRequest(BaseModel):
    """Request schema for triggering or stopping the camera's built-in siren"""
    active: bool = Field(True, description="True to sound siren, False to stop")
    duration_seconds: int = Field(5, ge=1, le=60, description="Auto-stop duration in seconds")


class SimulatedEdgeEventRequest(BaseModel):
    """Request schema for testing/injecting a camera Edge AI detection event"""
    object_class: str = Field("person", description="person, vehicle, animal, package, or motion")
    object_subclass: Optional[str] = Field(None, description="Optional subclass (e.g. person, car, pet)")
    confidence: float = Field(0.95, ge=0.1, le=1.0)


@router.get("/cameras/{camera_id}/edge/capabilities")
async def get_camera_edge_capabilities(
    camera_id: str,
    refresh: bool = Query(False, description="Force re-probing hardware capabilities"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Probe and return a camera's built-in Edge AI and hardware capabilities
    (ONVIF Events, Imaging/Night Vision, PTZ Auto-Tracking, Privacy Mode, Siren,
    and vendor extensions for TP-Link Tapo, Hikvision, Dahua/Amcrest, Reolink, Axis).
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    edge_manager.ensure_background_worker()
    ctrl = edge_manager.get_controller(camera_id, camera.source)
    summary = await ctrl.probe_capabilities(force=refresh)
    return summary


@router.put("/cameras/{camera_id}/edge/settings")
async def update_camera_edge_settings(
    camera_id: str,
    settings_update: EdgeSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Update camera Edge AI event subscriptions and hardware settings (Smart Track,
    Privacy Mode, Night Vision Mode, On-Camera AI Switches). Persists settings and
    pushes supported changes directly to the camera hardware.
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    edge_manager.ensure_background_worker()
    ctrl = edge_manager.get_controller(camera_id, camera.source)
    await ctrl.probe_capabilities(force=False)

    updates = settings_update.dict(exclude_unset=True)
    result = await ctrl.apply_hardware_settings(updates)

    # Persist per-camera Edge AI config in SystemSettings so it survives restarts
    try:
        crud.set_system_setting(
            db,
            setting_key=f"edge_ai_config:{camera_id}",
            setting_value=json.dumps(ctrl.settings.to_dict()),
            setting_type="json",
            description=f"Edge AI and hardware settings for {camera_id}",
        )
    except Exception:
        pass

    return {
        "message": "Camera Edge AI & hardware settings updated",
        **result,
    }


@router.post("/cameras/{camera_id}/edge/siren")
async def trigger_camera_siren(
    camera_id: str,
    siren_req: SirenTriggerRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Trigger or silence the camera's built-in hardware siren/audio alarm."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    ctrl = edge_manager.get_controller(camera_id, camera.source)
    await ctrl.probe_capabilities(force=False)
    res = await ctrl.trigger_siren(
        active=siren_req.active,
        duration_seconds=siren_req.duration_seconds,
    )
    return {
        "message": "Siren activated" if siren_req.active else "Siren stopped",
        **res,
    }


@router.post("/cameras/{camera_id}/edge/poll")
async def poll_camera_edge_events_now(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Immediately poll the camera's Edge AI event stream and record any active detections."""
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    edge_manager.ensure_background_worker()
    ctrl = edge_manager.get_controller(camera_id, camera.source)
    await ctrl.probe_capabilities(force=False)
    events = await ctrl.poll_edge_ai_events_once()
    recorded = []
    for evt in events:
        recorded.append(await edge_manager.record_edge_detection_event(camera_id, evt, ctrl))

    return {
        "camera_id": camera_id,
        "polled_events": len(recorded),
        "events": recorded,
        "recent_events": ctrl.recent_events[:15],
    }


@router.post("/cameras/{camera_id}/edge/test-event")
async def trigger_test_edge_event(
    camera_id: str,
    req: SimulatedEdgeEventRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Simulate/verify an Edge AI detection pipeline event (captures live snapshot from
    the camera, records an `ObjectDetectionEvent` / `MotionDetectionEvent`, and
    verifies end-to-end integration with the Detections page and recordings).
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    ctrl = edge_manager.get_controller(camera_id, camera.source)
    evt = {
        "camera_id": camera_id,
        "object_class": req.object_class,
        "object_subclass": req.object_subclass or req.object_class,
        "confidence": req.confidence,
        "topic": f"onvif:RuleEngine/EdgeAI/{req.object_class.capitalize()}Detector",
        "vendor": ctrl.vendor_hint,
        "timestamp": datetime.utcnow().isoformat(),
    }
    recorded = await edge_manager.record_edge_detection_event(camera_id, evt, ctrl)
    ctrl.recent_events.insert(0, recorded)
    return {
        "message": f"Edge AI {req.object_class} detection recorded",
        "event": recorded,
    }

