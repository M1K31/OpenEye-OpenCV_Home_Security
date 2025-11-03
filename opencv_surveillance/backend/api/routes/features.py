"""
Feature Management API Routes
Hardware-aware feature enable/disable system
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
from pydantic import BaseModel

from backend.database.session import get_db
from backend.core.auth import get_current_user
from backend.core.feature_manager import get_feature_manager

router = APIRouter()


# ===== Pydantic Schemas =====

class FeatureToggleRequest(BaseModel):
    """Request to toggle a feature on/off"""
    enabled: bool


class HardwareScanRequest(BaseModel):
    """Request to trigger hardware scan"""
    scan_type: str = "manual"


# ===== API Endpoints =====

@router.get("/features/states")
async def get_feature_states(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get all feature states with hardware compatibility info

    Returns detailed information about each feature:
    - Current enabled/disabled state
    - Hardware compatibility
    - Reasons for incompatibility
    - User overrides
    """
    feature_manager = get_feature_manager()
    states = feature_manager.get_feature_states(db)

    return {
        "features": states,
        "total": len(states)
    }


@router.post("/features/{feature_id}/toggle")
async def toggle_feature(
    feature_id: str,
    request: FeatureToggleRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Toggle a feature on/off

    Marks the change as a user override.
    Shows warnings if enabling a feature that's not hardware compatible.
    """
    try:
        feature_manager = get_feature_manager()
        result = feature_manager.toggle_feature(
            db=db,
            feature_id=feature_id,
            enabled=request.enabled,
            user_override=True
        )

        return {
            "success": True,
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error toggling feature: {str(e)}")


@router.post("/hardware/scan")
async def trigger_hardware_scan(
    request: HardwareScanRequest = HardwareScanRequest(),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Manually trigger hardware scan and feature reconfiguration

    This will:
    1. Scan current hardware
    2. Detect changes from last scan
    3. Auto-enable compatible features
    4. Auto-disable incompatible features (unless user override)
    5. Record scan history

    Args:
        scan_type: Type of scan (manual, startup, scheduled)
    """
    try:
        feature_manager = get_feature_manager()
        result = feature_manager.scan_and_configure_features(
            scan_type=request.scan_type,
            scanned_by=current_user.get('username', 'unknown'),
            notify_changes=True
        )

        return {
            "success": True,
            "message": "Hardware scan completed",
            **result
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during hardware scan: {str(e)}"
        )


@router.get("/hardware/scan/history")
async def get_scan_history(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get hardware scan history

    Shows past hardware scans, detected changes, and actions taken.

    Args:
        limit: Maximum number of scan records to return (default 10)
    """
    feature_manager = get_feature_manager()
    history = feature_manager.get_scan_history(db, limit=limit)

    return {
        "scans": history,
        "total": len(history)
    }


@router.get("/hardware/scan/latest")
async def get_latest_scan(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
) -> Dict:
    """
    Get the most recent hardware scan

    Returns details of the last hardware scan performed.
    """
    feature_manager = get_feature_manager()
    history = feature_manager.get_scan_history(db, limit=1)

    if not history:
        return {
            "scan": None,
            "message": "No hardware scans found. Run a scan to configure features."
        }

    return {
        "scan": history[0]
    }
