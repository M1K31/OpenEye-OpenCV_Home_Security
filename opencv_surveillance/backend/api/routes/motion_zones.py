# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
API routes for Motion Zone management
Allows users to define and manage motion detection zones per camera
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from backend.database.session import get_db
from backend.database.models import MotionZone, Camera
from backend.api.schemas.motion import (
    MotionZoneCreate,
    MotionZoneUpdate,
    MotionZoneResponse,
    MotionZoneListResponse
)
from backend.core.auth import get_current_user


router = APIRouter()


@router.get("/cameras/{camera_id}/zones", response_model=MotionZoneListResponse)
def list_camera_zones(
    camera_id: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    List all motion zones for a specific camera

    - **camera_id**: Camera identifier
    - **include_inactive**: Include inactive zones in response (default: False)
    """
    # Verify camera exists
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )

    # Query zones
    query = db.query(MotionZone).filter(MotionZone.camera_id == camera_id)

    if not include_inactive:
        query = query.filter(MotionZone.is_active == True)

    zones = query.order_by(MotionZone.created_at.desc()).all()

    return MotionZoneListResponse(
        zones=zones,
        total=len(zones),
        camera_id=camera_id
    )


@router.post("/cameras/{camera_id}/zones", response_model=MotionZoneResponse, status_code=status.HTTP_201_CREATED)
def create_motion_zone(
    camera_id: str,
    zone_data: MotionZoneCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new motion detection zone for a camera

    - **camera_id**: Camera identifier
    - **zone_data**: Zone configuration (name, type, coordinates, etc.)
    """
    # Verify camera exists
    camera = db.query(Camera).filter(Camera.camera_id == camera_id).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera '{camera_id}' not found"
        )

    # Ensure camera_id matches URL parameter
    if zone_data.camera_id != camera_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera ID in URL must match camera_id in request body"
        )

    # Validate coordinates is valid JSON
    import json
    try:
        coords = json.loads(zone_data.coordinates)
        if not isinstance(coords, list) or len(coords) < 3:
            raise ValueError("Coordinates must be a JSON array with at least 3 points")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid coordinates format: {str(e)}"
        )

    # Create zone
    new_zone = MotionZone(
        camera_id=camera_id,
        name=zone_data.name,
        zone_type=zone_data.zone_type,
        coordinates=zone_data.coordinates,
        is_active=zone_data.is_active,
        is_exclusion_zone=zone_data.is_exclusion_zone,
        sensitivity_multiplier=zone_data.sensitivity_multiplier,
        color=zone_data.color,
        opacity=zone_data.opacity,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    db.add(new_zone)
    db.commit()
    db.refresh(new_zone)

    return new_zone


@router.get("/cameras/{camera_id}/zones/{zone_id}", response_model=MotionZoneResponse)
def get_motion_zone(
    camera_id: str,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a specific motion zone by ID

    - **camera_id**: Camera identifier
    - **zone_id**: Zone identifier
    """
    zone = db.query(MotionZone).filter(
        MotionZone.id == zone_id,
        MotionZone.camera_id == camera_id
    ).first()

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found for camera '{camera_id}'"
        )

    return zone


@router.put("/cameras/{camera_id}/zones/{zone_id}", response_model=MotionZoneResponse)
def update_motion_zone(
    camera_id: str,
    zone_id: int,
    zone_data: MotionZoneUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update an existing motion zone

    - **camera_id**: Camera identifier
    - **zone_id**: Zone identifier
    - **zone_data**: Updated zone configuration (only provided fields will be updated)
    """
    zone = db.query(MotionZone).filter(
        MotionZone.id == zone_id,
        MotionZone.camera_id == camera_id
    ).first()

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found for camera '{camera_id}'"
        )

    # Validate coordinates if provided
    if zone_data.coordinates is not None:
        import json
        try:
            coords = json.loads(zone_data.coordinates)
            if not isinstance(coords, list) or len(coords) < 3:
                raise ValueError("Coordinates must be a JSON array with at least 3 points")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid coordinates format: {str(e)}"
            )

    # Update fields (only if provided)
    update_data = zone_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(zone, field, value)

    zone.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(zone)

    return zone


@router.delete("/cameras/{camera_id}/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_motion_zone(
    camera_id: str,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Delete a motion zone

    - **camera_id**: Camera identifier
    - **zone_id**: Zone identifier
    """
    zone = db.query(MotionZone).filter(
        MotionZone.id == zone_id,
        MotionZone.camera_id == camera_id
    ).first()

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found for camera '{camera_id}'"
        )

    db.delete(zone)
    db.commit()

    return None


@router.post("/cameras/{camera_id}/zones/{zone_id}/toggle", response_model=MotionZoneResponse)
def toggle_zone_active(
    camera_id: str,
    zone_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Quick toggle of zone active status

    - **camera_id**: Camera identifier
    - **zone_id**: Zone identifier
    """
    zone = db.query(MotionZone).filter(
        MotionZone.id == zone_id,
        MotionZone.camera_id == camera_id
    ).first()

    if not zone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zone {zone_id} not found for camera '{camera_id}'"
        )

    zone.is_active = not zone.is_active
    zone.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(zone)

    return zone
