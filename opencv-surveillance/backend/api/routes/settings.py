# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
System Settings API Routes
Handles global system settings including storage paths and display preferences
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import os
import json

from backend.database import crud, models
from backend.database.session import SessionLocal
from backend.core import auth

router = APIRouter()


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================

class SystemSettingBase(BaseModel):
    setting_key: str = Field(..., description="Unique key for the setting")
    setting_value: str = Field(..., description="Value of the setting")
    setting_type: str = Field(default='string', description="Type: string, int, float, boolean, json")
    description: Optional[str] = Field(None, description="Description of the setting")


class SystemSettingResponse(SystemSettingBase):
    id: int
    updated_at: str

    class Config:
        from_attributes = True


class SystemSettingsUpdate(BaseModel):
    recordings_path: Optional[str] = Field(None, description="Path to recordings directory")
    faces_path: Optional[str] = Field(None, description="Path to faces directory")
    display_mode: Optional[str] = Field(None, pattern="^(grid|vertical|horizontal|cycle)$")
    cycle_interval: Optional[int] = Field(None, ge=1, le=60, description="Seconds between camera switches")
    max_recording_duration: Optional[int] = Field(None, ge=30, le=1800, description="Max recording seconds")
    theme: Optional[str] = Field(None, pattern="^(light|dark)$")


class PathValidationResponse(BaseModel):
    path: str
    exists: bool
    is_directory: bool
    writable: bool
    absolute_path: str


class PathValidationRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Path to validate")
    create_if_missing: bool = Field(default=False, description="Create directory if it doesn't exist")


# ============================================================================
# DEPENDENCY: DATABASE SESSION
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# SYSTEM SETTINGS ENDPOINTS
# ============================================================================

@router.get("/settings", response_model=Dict[str, Any])
async def get_all_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get all system settings as a dictionary"""
    settings = crud.get_all_system_settings(db)
    
    # Convert to dictionary for easier frontend consumption
    settings_dict = {}
    for setting in settings:
        try:
            # Try to convert to appropriate type
            if setting.setting_type == 'int':
                settings_dict[setting.setting_key] = int(setting.setting_value)
            elif setting.setting_type == 'float':
                settings_dict[setting.setting_key] = float(setting.setting_value)
            elif setting.setting_type == 'boolean':
                settings_dict[setting.setting_key] = setting.setting_value.lower() in ('true', '1', 'yes')
            elif setting.setting_type == 'json':
                settings_dict[setting.setting_key] = json.loads(setting.setting_value)
            else:
                settings_dict[setting.setting_key] = setting.setting_value
        except (ValueError, json.JSONDecodeError):
            settings_dict[setting.setting_key] = setting.setting_value
    
    return settings_dict


@router.get("/settings/{setting_key}", response_model=SystemSettingResponse)
async def get_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Get a specific system setting"""
    setting = crud.get_system_setting(db, setting_key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found"
        )
    return setting


@router.patch("/settings", response_model=Dict[str, Any])
async def update_settings(
    settings: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Update multiple system settings"""
    updated_settings = {}
    
    for key, value in settings.dict(exclude_unset=True).items():
        if value is not None:
            # Determine type
            setting_type = 'string'
            if isinstance(value, int):
                setting_type = 'int'
                value = str(value)
            elif isinstance(value, float):
                setting_type = 'float'
                value = str(value)
            elif isinstance(value, bool):
                setting_type = 'boolean'
                value = str(value)
            else:
                value = str(value)
            
            # Set the setting
            db_setting = crud.set_system_setting(db, key, value, setting_type)
            updated_settings[key] = value
    
    return updated_settings


# ============================================================================
# PATH VALIDATION ENDPOINTS
# ============================================================================
# NOTE: This MUST come before /settings/{setting_key} to avoid path parameter matching!

@router.post("/settings/validate-path", response_model=PathValidationResponse)
async def validate_path(
    request: PathValidationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Validate if a path exists and is writable"""
    # Convert to absolute path
    abs_path = os.path.abspath(request.path)
    
    # Check if path exists
    exists = os.path.exists(abs_path)
    is_directory = os.path.isdir(abs_path) if exists else False
    
    # Check if writable
    writable = False
    if exists and is_directory:
        writable = os.access(abs_path, os.W_OK)
    elif request.create_if_missing:
        try:
            os.makedirs(abs_path, exist_ok=True)
            exists = True
            is_directory = True
            writable = os.access(abs_path, os.W_OK)
        except Exception as e:
            writable = False
    
    return PathValidationResponse(
        path=request.path,
        exists=exists,
        is_directory=is_directory,
        writable=writable,
        absolute_path=abs_path
    )


# ============================================================================
# GENERIC SETTINGS ENDPOINTS (WITH PATH PARAMETERS)
# ============================================================================
# NOTE: These must come AFTER specific routes like /validate-path!

@router.post("/settings/{setting_key}")
async def set_setting(
    setting_key: str,
    setting: SystemSettingBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Set or update a specific system setting"""
    db_setting = crud.set_system_setting(
        db,
        setting_key,
        setting.setting_value,
        setting.setting_type,
        setting.description
    )
    return db_setting


@router.delete("/settings/{setting_key}")
async def delete_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Delete a system setting"""
    success = crud.delete_system_setting(db, setting_key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found"
        )
    return {"status": "deleted", "setting_key": setting_key}


# ============================================================================
# INITIALIZATION
# ============================================================================

@router.post("/settings/initialize")
async def initialize_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Initialize default system settings"""
    crud.initialize_default_settings(db)
    return {"status": "initialized", "message": "Default settings created"}
