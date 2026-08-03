"""
PTZ Control API Routes
Handles Pan-Tilt-Zoom camera control operations
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json

from backend.database.session import get_db
from backend.database import crud
from backend.database.models import PTZPreset, PTZPatrolPattern
from backend.core.ptz_controller import get_ptz_controller, remove_ptz_controller
from backend.core.auth import get_current_user
from pydantic import BaseModel, Field

router = APIRouter()


# ===== Pydantic Schemas =====

class PTZMoveRequest(BaseModel):
    """Request schema for PTZ movement commands"""
    pan: float = Field(..., ge=-1.0, le=1.0, description="Pan position (-1.0 to 1.0)")
    tilt: float = Field(..., ge=-1.0, le=1.0, description="Tilt position (-1.0 to 1.0)")
    zoom: float = Field(..., ge=0.0, le=1.0, description="Zoom level (0.0 to 1.0)")
    speed: float = Field(0.5, ge=0.0, le=1.0, description="Movement speed (0.0 to 1.0)")


class PTZContinuousMoveRequest(BaseModel):
    """Request schema for continuous PTZ movement"""
    pan_velocity: float = Field(..., ge=-1.0, le=1.0, description="Pan velocity (-1.0 to 1.0)")
    tilt_velocity: float = Field(..., ge=-1.0, le=1.0, description="Tilt velocity (-1.0 to 1.0)")
    zoom_velocity: float = Field(..., ge=-1.0, le=1.0, description="Zoom velocity (-1.0 to 1.0)")


class PTZConnectionRequest(BaseModel):
    """Request schema for PTZ connection"""
    camera_ip: str = Field(..., description="Camera IP address")
    port: int = Field(80, description="ONVIF port")
    username: str = Field("", description="Camera username")
    password: str = Field("", description="Camera password")
    ptz_type: str = Field("onvif", description="PTZ protocol type")


class PTZPresetCreate(BaseModel):
    """Request schema for creating PTZ preset"""
    name: str = Field(..., min_length=1, max_length=100, description="Preset name")
    preset_number: int = Field(..., ge=1, le=255, description="Preset slot number (1-255)")
    pan: float = Field(..., ge=-1.0, le=1.0, description="Pan position")
    tilt: float = Field(..., ge=-1.0, le=1.0, description="Tilt position")
    zoom: float = Field(..., ge=0.0, le=1.0, description="Zoom level")


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


# ===== PTZ Control Endpoints =====

@router.post("/cameras/{camera_id}/ptz/connect")
async def connect_ptz(
    camera_id: str,
    connection: PTZConnectionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Connect to PTZ camera
    """
    # Verify camera exists
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Get PTZ controller
    controller = get_ptz_controller(camera_id, connection.ptz_type)

    # Attempt connection
    success = await controller.connect(
        camera_ip=connection.camera_ip,
        port=connection.port,
        username=connection.username,
        password=connection.password
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to connect to PTZ camera")

    return {
        "message": "PTZ connected successfully",
        "camera_id": camera_id,
        "connected": True
    }


@router.post("/cameras/{camera_id}/ptz/disconnect")
async def disconnect_ptz(
    camera_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Disconnect PTZ camera
    """
    remove_ptz_controller(camera_id)
    return {"message": "PTZ disconnected successfully", "camera_id": camera_id}


@router.post("/cameras/{camera_id}/ptz/move/absolute")
async def move_absolute(
    camera_id: str,
    move_request: PTZMoveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Move camera to absolute position
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        raise HTTPException(status_code=400, detail="PTZ not connected")

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


@router.post("/cameras/{camera_id}/ptz/move/continuous")
async def move_continuous(
    camera_id: str,
    move_request: PTZContinuousMoveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Start continuous camera movement
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        raise HTTPException(status_code=400, detail="PTZ not connected")

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
    """
    Stop all PTZ movement
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        raise HTTPException(status_code=400, detail="PTZ not connected")

    success = await controller.stop()

    if not success:
        raise HTTPException(status_code=500, detail="PTZ stop command failed")

    return {"message": "PTZ stopped successfully"}


@router.get("/cameras/{camera_id}/ptz/status")
async def get_ptz_status(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get current PTZ status and position
    Returns connected: false instead of error if PTZ not connected
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    controller = get_ptz_controller(camera_id)

    # Return disconnected status instead of throwing error
    if not controller.is_connected:
        return {
            "camera_id": camera_id,
            "connected": False,
            "status": None
        }

    status = await controller.get_status()

    if status is None:
        # Return connected but unable to get status
        return {
            "camera_id": camera_id,
            "connected": True,
            "status": None
        }

    return {
        "camera_id": camera_id,
        "connected": controller.is_connected,
        "status": status
    }


# ===== Preset Endpoints =====

@router.get("/cameras/{camera_id}/ptz/presets")
async def list_presets(
    camera_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all PTZ presets for a camera
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

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
    """
    Create a new PTZ preset for a camera
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Check if preset number already exists for this camera
    existing = crud.get_ptz_preset_by_number(db, camera_id, preset.preset_number)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Preset number {preset.preset_number} already exists for this camera"
        )

    # Create preset in database
    new_preset = crud.create_ptz_preset(db, camera_id, preset.dict())

    # If PTZ is connected, save to camera hardware
    controller = get_ptz_controller(camera_id)
    if controller.is_connected:
        await controller.set_preset(preset.preset_number, preset.name)

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
    """
    Get a specific PTZ preset
    """
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
    """
    Update a PTZ preset
    """
    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    # Update preset
    updated_preset = crud.update_ptz_preset(db, preset_id, preset_update.dict(exclude_unset=True))

    # If PTZ is connected and position changed, update hardware
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
    """
    Delete a PTZ preset
    """
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
    """
    Move camera to a saved preset position
    """
    preset = crud.get_ptz_preset_by_id(db, preset_id)
    if not preset or preset.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Preset not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        raise HTTPException(status_code=400, detail="PTZ not connected")

    # Move to preset
    success = await controller.goto_preset(preset.preset_number, speed)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to move to preset")

    # Update usage tracking
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
    """
    List all patrol patterns for a camera
    """
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
    """
    Create a new patrol pattern for a camera
    """
    camera = crud.get_camera_by_id(db, camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Validate pattern steps
    pattern_steps_dict = [step.dict() for step in pattern.pattern_steps]

    # Create pattern in database
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
    """
    Get a specific patrol pattern
    """
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
    """
    Update a patrol pattern
    """
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    # Stop pattern if it's currently running
    if pattern.is_active:
        await stop_patrol_pattern(camera_id, pattern_id, db, current_user)

    # Build update dict
    update_data = pattern_update.dict(exclude_unset=True)
    if "pattern_steps" in update_data and update_data["pattern_steps"]:
        update_data["pattern_steps"] = json.dumps([step.dict() for step in update_data["pattern_steps"]])

    # Update pattern
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
    """
    Delete a patrol pattern
    """
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    # Stop pattern if it's currently running
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
    """
    Start executing a patrol pattern
    """
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    controller = get_ptz_controller(camera_id)
    if not controller.is_connected:
        raise HTTPException(status_code=400, detail="PTZ not connected")

    # Mark pattern as active
    crud.update_patrol_pattern(db, pattern_id, {"is_active": True, "last_run_at": datetime.utcnow()})

    # Start patrol in background
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
    """
    Stop executing a patrol pattern
    """
    pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
    if not pattern or pattern.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Patrol pattern not found")

    # Mark pattern as inactive
    crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
    crud.increment_patrol_run_count(db, pattern_id)

    return {
        "message": "Patrol pattern stopped successfully",
        "pattern_id": pattern_id
    }


# ===== Background Task: Execute Patrol Pattern =====

async def execute_patrol_pattern(camera_id: str, pattern_id: int):
    """
    Background task to execute patrol pattern
    """
    from backend.database.session import SessionLocal

    db = SessionLocal()
    try:
        pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
        if not pattern:
            return

        controller = get_ptz_controller(camera_id)
        if not controller.is_connected:
            return

        # Parse pattern steps
        pattern_steps = json.loads(pattern.pattern_steps)

        # Execute pattern
        while pattern.is_active:
            # Reload pattern to check if still active
            pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
            if not pattern or not pattern.is_active:
                break

            for step in pattern_steps:
                # Check if pattern still active before each step
                pattern = crud.get_patrol_pattern_by_id(db, pattern_id)
                if not pattern or not pattern.is_active:
                    break

                # Move to position
                if "preset_id" in step and step["preset_id"]:
                    # Use preset
                    preset = crud.get_ptz_preset_by_id(db, step["preset_id"])
                    if preset:
                        await controller.goto_preset(preset.preset_number)
                        crud.increment_preset_usage(db, step["preset_id"])
                else:
                    # Use direct coordinates
                    await controller.move_absolute(
                        pan=step.get("pan", 0.0),
                        tilt=step.get("tilt", 0.0),
                        zoom=step.get("zoom", 0.5)
                    )

                # Dwell at position
                dwell_time = step.get("dwell_time", pattern.interval_seconds)
                await asyncio.sleep(dwell_time)

            # Check if loop is enabled
            if not pattern.loop_enabled:
                crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
                crud.increment_patrol_run_count(db, pattern_id)
                break

    except Exception as e:
        print(f"Error executing patrol pattern {pattern_id}: {e}")
        crud.update_patrol_pattern(db, pattern_id, {"is_active": False})
    finally:
        db.close()
