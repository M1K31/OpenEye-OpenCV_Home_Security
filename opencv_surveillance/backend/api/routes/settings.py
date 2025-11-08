# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
System Settings API Routes
Handles global system settings including storage paths and display preferences
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
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
    setting_type: str = Field(
        default="string", description="Type: string, int, float, boolean, json"
    )
    description: Optional[str] = Field(
        None, description="Description of the setting")


class SystemSettingResponse(SystemSettingBase):
    id: int
    updated_at: str

    class Config:
        from_attributes = True


class SystemSettingsUpdate(BaseModel):
    recordings_path: Optional[str] = Field(
        None, description="Path to recordings directory"
    )
    faces_path: Optional[str] = Field(
        None, description="Path to faces directory")
    snapshots_path: Optional[str] = Field(
        None, description="Path to motion detection snapshots directory"
    )
    display_mode: Optional[str] = Field(
        None, pattern="^(grid|vertical|horizontal|cycle)$"
    )
    cycle_interval: Optional[int] = Field(
        None, ge=1, le=60, description="Seconds between camera switches"
    )
    max_recording_duration: Optional[int] = Field(
        None, ge=30, le=1800, description="Max recording seconds"
    )
    theme: Optional[str] = Field(None, pattern="^(light|dark)$")

    # NEW: Hardware Video Encoding (v3.7.1+)
    hardware_video_encoding: Optional[bool] = Field(
        None, description="Enable FFmpeg hardware-accelerated video encoding (70-90% CPU reduction)"
    )

    # NEW: Apple HIG Accessibility Settings
    reduce_motion: Optional[bool] = Field(
        None, description="Reduce animations for accessibility (Apple HIG)"
    )
    use_8pt_grid: Optional[bool] = Field(
        None, description="Use 8pt grid spacing system (Apple HIG)"
    )
    enhanced_touch_targets: Optional[bool] = Field(
        None, description="Enhance touch targets to 44x44pt minimum (Apple HIG)"
    )
    show_focus_indicators: Optional[bool] = Field(
        None, description="Show keyboard focus indicators (Apple HIG)"
    )


class PathValidationResponse(BaseModel):
    path: str
    exists: bool
    is_directory: bool
    writable: bool
    absolute_path: str


class PathValidationRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Path to validate")
    create_if_missing: bool = Field(
        default=False, description="Create directory if it doesn't exist"
    )


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
    current_user: models.User = Depends(auth.get_current_user),
):
    """Get all system settings as a dictionary"""
    settings = crud.get_all_system_settings(db)

    # Convert to dictionary for easier frontend consumption
    settings_dict = {}
    for setting in settings:
        try:
            # Try to convert to appropriate type
            if setting.setting_type == "int":
                settings_dict[setting.setting_key] = int(setting.setting_value)
            elif setting.setting_type == "float":
                settings_dict[setting.setting_key] = float(
                    setting.setting_value)
            elif setting.setting_type == "boolean":
                settings_dict[setting.setting_key] = setting.setting_value.lower() in (
                    "true", "1", "yes", )
            elif setting.setting_type == "json":
                settings_dict[setting.setting_key] = json.loads(
                    setting.setting_value)
            else:
                settings_dict[setting.setting_key] = setting.setting_value
        except (ValueError, json.JSONDecodeError):
            settings_dict[setting.setting_key] = setting.setting_value

    return settings_dict


@router.get("/settings/{setting_key}", response_model=SystemSettingResponse)
async def get_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Get a specific system setting"""
    setting = crud.get_system_setting(db, setting_key)
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found",
        )
    return setting


@router.patch("/settings", response_model=Dict[str, Any])
async def update_settings(
    settings: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Update multiple system settings"""
    updated_settings = {}

    for key, value in settings.dict(exclude_unset=True).items():
        if value is not None:
            # Determine type
            setting_type = "string"
            if isinstance(value, int):
                setting_type = "int"
                value = str(value)
            elif isinstance(value, float):
                setting_type = "float"
                value = str(value)
            elif isinstance(value, bool):
                setting_type = "boolean"
                value = str(value)
            else:
                value = str(value)

            # Set the setting
            crud.set_system_setting(db, key, value, setting_type)
            updated_settings[key] = value

    return updated_settings


# ============================================================================
# PATH VALIDATION ENDPOINTS
# ============================================================================
# NOTE: This MUST come before /settings/{setting_key} to avoid path
# parameter matching!


@router.post("/settings/validate-path", response_model=PathValidationResponse)
async def validate_path(
    request: PathValidationRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
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
        except Exception:
            writable = False

    return PathValidationResponse(
        path=request.path,
        exists=exists,
        is_directory=is_directory,
        writable=writable,
        absolute_path=abs_path,
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
    current_user: models.User = Depends(auth.get_current_user),
):
    """Set or update a specific system setting"""
    db_setting = crud.set_system_setting(
        db,
        setting_key,
        setting.setting_value,
        setting.setting_type,
        setting.description,
    )
    return db_setting


@router.delete("/settings/{setting_key}")
async def delete_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Delete a system setting"""
    success = crud.delete_system_setting(db, setting_key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found",
        )
    return {"status": "deleted", "setting_key": setting_key}


# ============================================================================
# INITIALIZATION
# ============================================================================


@router.post("/settings/initialize")
async def initialize_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Initialize default system settings"""
    crud.initialize_default_settings(db)
    return {"status": "initialized", "message": "Default settings created"}


# ============================================================================
# STORAGE PATH MANAGEMENT
# ============================================================================


class StoragePathsResponse(BaseModel):
    """Storage path configuration and statistics"""

    recordings_dir: str = Field(..., description="Current recordings directory path")
    snapshots_dir: str = Field(..., description="Current snapshots directory path")
    faces_dir: str = Field(..., description="Current faces directory path")
    disk_usage: dict = Field(..., description="Disk usage statistics")


class StoragePathsUpdate(BaseModel):
    """Update storage paths with optional migration"""

    recordings_dir: Optional[str] = Field(None, description="New recordings directory")
    snapshots_dir: Optional[str] = Field(None, description="New snapshots directory")
    faces_dir: Optional[str] = Field(None, description="New faces directory")


@router.get("/settings/storage/paths", response_model=StoragePathsResponse)
async def get_storage_paths(
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Get current storage paths and disk usage

    Returns current configuration and statistics for all storage directories
    """
    from backend.core.paths import paths

    return StoragePathsResponse(
        recordings_dir=str(paths.recordings_dir),
        snapshots_dir=str(paths.snapshots_dir),
        faces_dir=str(paths.faces_dir),
        disk_usage=paths.get_all_disk_usage(),
    )


@router.put("/settings/storage/paths")
async def update_storage_paths(
    paths_update: StoragePathsUpdate,
    migrate: bool = False,
    current_user: models.User = Depends(auth.require_admin),
    db: Session = Depends(get_db),
):
    """
    Update storage paths with optional file migration

    - **recordings_dir**: New recordings directory path
    - **snapshots_dir**: New snapshots directory path
    - **faces_dir**: New faces directory path
    - **migrate**: If true, move existing files to new locations (default: false)

    **Admin only**

    Example:
        PUT /api/settings/storage/paths?migrate=true
        {
            "recordings_dir": "/mnt/storage/recordings",
            "snapshots_dir": "/mnt/storage/snapshots"
        }
    """
    from backend.core.paths import paths
    from backend.utils.migrate_media import migrate_files

    migration_results = {}

    # Migrate recordings if path changed
    if paths_update.recordings_dir and migrate:
        old_dir = paths.recordings_dir
        new_dir = paths_update.recordings_dir

        if old_dir != new_dir:
            result = migrate_files(
                media_type="recordings",
                source_dir=old_dir,
                dest_dir=new_dir,
                update_database=True,
                dry_run=False,
            )
            migration_results["recordings"] = result.to_dict()

    # Migrate snapshots if path changed
    if paths_update.snapshots_dir and migrate:
        old_dir = paths.snapshots_dir
        new_dir = paths_update.snapshots_dir

        if old_dir != new_dir:
            result = migrate_files(
                media_type="snapshots",
                source_dir=old_dir,
                dest_dir=new_dir,
                update_database=True,
                dry_run=False,
            )
            migration_results["snapshots"] = result.to_dict()

    # Migrate faces if path changed
    if paths_update.faces_dir and migrate:
        old_dir = paths.faces_dir
        new_dir = paths_update.faces_dir

        if old_dir != new_dir:
            result = migrate_files(
                media_type="faces",
                source_dir=old_dir,
                dest_dir=new_dir,
                update_database=False,  # Faces don't have DB records
                dry_run=False,
            )
            migration_results["faces"] = result.to_dict()

    # Update PathManager
    paths.update_paths(
        recordings_dir=paths_update.recordings_dir,
        snapshots_dir=paths_update.snapshots_dir,
        faces_dir=paths_update.faces_dir,
    )

    # Update database settings
    if paths_update.recordings_dir:
        crud.set_system_setting(
            db, "recordings_path", str(paths.recordings_dir), "string"
        )
    if paths_update.snapshots_dir:
        crud.set_system_setting(
            db, "snapshots_path", str(paths.snapshots_dir), "string"
        )
    if paths_update.faces_dir:
        crud.set_system_setting(
            db, "faces_path", str(paths.faces_dir), "string"
        )

    return {
        "status": "updated",
        "paths": {
            "recordings_dir": str(paths.recordings_dir),
            "snapshots_dir": str(paths.snapshots_dir),
            "faces_dir": str(paths.faces_dir),
        },
        "migration_results": migration_results if migrate else None,
    }


@router.post("/settings/storage/cleanup")
async def cleanup_orphaned_records(
    media_type: str = "all",
    dry_run: bool = True,
    current_user: models.User = Depends(auth.require_admin),
):
    """
    Clean up database records for missing media files

    - **media_type**: Type to clean ("snapshots", "recordings", "all")
    - **dry_run**: If true, only report what would be deleted (default: true)

    **Admin only**

    Example:
        POST /api/settings/storage/cleanup?media_type=snapshots&dry_run=false
    """
    from backend.utils.cleanup_orphaned_records import cleanup_orphaned_records as cleanup

    results = cleanup(media_type=media_type, dry_run=dry_run)

    return {
        "status": "completed" if not dry_run else "dry_run",
        "results": results,
    }
