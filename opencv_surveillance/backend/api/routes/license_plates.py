# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
License Plate Recognition API Routes (v3.11.7)

Provides endpoints for:
- Querying detected license plates
- Managing known/watchlist plates
- ALPR configuration and status
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from backend.database.session import get_db
from backend.database import models
from backend.core.performance import paginate_with_metadata
from backend.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class LicensePlateEventResponse(BaseModel):
    """Response schema for license plate detection events"""
    id: int
    camera_id: str
    detected_at: datetime
    plate_text: str
    plate_region: Optional[str] = None
    confidence: Optional[float] = None
    location: Optional[dict] = None
    snapshot_path: Optional[str] = None
    is_known_plate: bool = False
    known_plate_name: Optional[str] = None
    processing_time_ms: Optional[float] = None
    ocr_engine: Optional[str] = None

    class Config:
        from_attributes = True


class KnownPlateResponse(BaseModel):
    """Response schema for known license plates"""
    id: int
    plate_text: str
    label: str
    category: str
    notes: Optional[str] = None
    alert_on_arrival: bool = False
    alert_on_departure: bool = False
    created_at: datetime
    last_seen_at: Optional[datetime] = None
    times_seen: int = 0

    class Config:
        from_attributes = True


class KnownPlateCreate(BaseModel):
    """Schema for creating a known license plate"""
    plate_text: str = Field(..., min_length=3, max_length=10)
    label: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="neutral", pattern="^(allowed|alert|neutral)$")
    notes: Optional[str] = None
    alert_on_arrival: bool = False
    alert_on_departure: bool = False


class KnownPlateUpdate(BaseModel):
    """Schema for updating a known license plate"""
    label: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    alert_on_arrival: Optional[bool] = None
    alert_on_departure: Optional[bool] = None


class ALPRStatusResponse(BaseModel):
    """Response schema for ALPR system status"""
    enabled: bool
    ocr_available: bool
    ocr_engine: Optional[str] = None
    gpu_available: bool
    using_gpu: bool
    cooldown_seconds: float
    min_confidence: float
    total_detections_today: int
    known_plates_count: int


# ============================================================================
# ALPR SYSTEM STATUS AND CONFIGURATION
# ============================================================================
# NOTE: These routes MUST be defined BEFORE /plates/{event_id} to avoid
# FastAPI matching "status" as an event_id parameter.

@router.get("/plates/status", response_model=ALPRStatusResponse)
def get_alpr_status(db: Session = Depends(get_db)):
    """Get ALPR system status and configuration"""
    from backend.core.advanced_detection import get_license_plate_detector

    detector = get_license_plate_detector()

    # Count today's detections
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total_today = db.query(models.LicensePlateEvent).filter(
        models.LicensePlateEvent.detected_at >= today_start
    ).count()

    # Count known plates
    known_count = db.query(models.KnownLicensePlate).count()

    return ALPRStatusResponse(
        enabled=detector.enabled,
        ocr_available=detector.ocr_available,
        ocr_engine=detector.ocr_engine_name,
        gpu_available=detector._detect_gpu_available(),
        using_gpu=detector.use_gpu,
        cooldown_seconds=detector.cooldown_seconds,
        min_confidence=detector.min_confidence,
        total_detections_today=total_today,
        known_plates_count=known_count
    )


@router.post("/plates/enable", response_model=dict)
def enable_alpr(
    enabled: bool = Query(..., description="Enable or disable ALPR"),
):
    """Enable or disable the ALPR system"""
    from backend.core.advanced_detection import get_license_plate_detector

    detector = get_license_plate_detector()
    detector.set_enabled(enabled)

    return {
        "success": True,
        "enabled": detector.enabled,
        "message": f"ALPR {'enabled' if enabled else 'disabled'}"
    }


# ============================================================================
# LICENSE PLATE DETECTION EVENTS
# ============================================================================

@router.get("/plates/", response_model=dict)
def list_license_plate_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    plate_text: Optional[str] = Query(None, description="Search by plate text"),
    hours: int = Query(24, ge=1, le=720, description="Hours of history to return"),
    known_only: Optional[bool] = Query(None, description="Filter by known status"),
    category: Optional[str] = Query(None, description="Filter by known plate category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    """
    List license plate detection events with optional filters.

    Performance: Optimized COUNT queries when no filters applied.
    """
    # Build base and filtered queries
    base_query = db.query(models.LicensePlateEvent)
    query = db.query(models.LicensePlateEvent)

    # Time filter (always applied)
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    base_query = base_query.filter(models.LicensePlateEvent.detected_at >= cutoff_time)
    query = query.filter(models.LicensePlateEvent.detected_at >= cutoff_time)

    has_filters = False

    # Apply additional filters
    if camera_id:
        query = query.filter(models.LicensePlateEvent.camera_id == camera_id)
        has_filters = True

    if plate_text:
        query = query.filter(models.LicensePlateEvent.plate_text.ilike(f"%{plate_text}%"))
        has_filters = True

    if known_only is not None:
        query = query.filter(models.LicensePlateEvent.is_known_plate == known_only)
        has_filters = True

    if category:
        # Join with known plates to filter by category
        query = query.join(
            models.KnownLicensePlate,
            models.LicensePlateEvent.plate_text == models.KnownLicensePlate.plate_text,
            isouter=False
        ).filter(models.KnownLicensePlate.category == category)
        has_filters = True

    # Order by most recent
    query = query.order_by(models.LicensePlateEvent.detected_at.desc())

    # Use optimized pagination
    return paginate_with_metadata(
        query=query,
        base_query=base_query,
        page=page,
        page_size=page_size,
        has_filters=has_filters
    )


@router.get("/plates/{event_id}", response_model=LicensePlateEventResponse)
def get_license_plate_event(event_id: int, db: Session = Depends(get_db)):
    """Get details of a specific license plate detection event"""
    event = db.query(models.LicensePlateEvent).filter(
        models.LicensePlateEvent.id == event_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="License plate event not found")

    return LicensePlateEventResponse(
        id=event.id,
        camera_id=event.camera_id,
        detected_at=event.detected_at,
        plate_text=event.plate_text,
        plate_region=event.plate_region,
        confidence=event.confidence,
        location={
            "x": event.location_x,
            "y": event.location_y,
            "width": event.location_width,
            "height": event.location_height
        } if event.location_x else None,
        snapshot_path=event.snapshot_path,
        is_known_plate=event.is_known_plate,
        known_plate_name=event.known_plate_name,
        processing_time_ms=event.processing_time_ms,
        ocr_engine=event.ocr_engine
    )


# ============================================================================
# KNOWN LICENSE PLATES (WATCHLIST)
# ============================================================================

@router.get("/plates/known/", response_model=List[KnownPlateResponse])
def list_known_plates(
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
):
    """List all known/watchlist license plates"""
    query = db.query(models.KnownLicensePlate)

    if category:
        query = query.filter(models.KnownLicensePlate.category == category)

    plates = query.order_by(models.KnownLicensePlate.label).all()

    return [KnownPlateResponse.model_validate(p) for p in plates]


@router.post("/plates/known/", response_model=KnownPlateResponse, status_code=201)
def create_known_plate(plate: KnownPlateCreate, db: Session = Depends(get_db)):
    """Add a license plate to the known/watchlist"""
    # Normalize plate text
    plate_text = plate.plate_text.upper().replace(" ", "").replace("-", "")

    # Check if already exists
    existing = db.query(models.KnownLicensePlate).filter(
        models.KnownLicensePlate.plate_text == plate_text
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Plate '{plate_text}' is already in the known plates list"
        )

    # Create new known plate
    new_plate = models.KnownLicensePlate(
        plate_text=plate_text,
        label=plate.label,
        category=plate.category,
        notes=plate.notes,
        alert_on_arrival=plate.alert_on_arrival,
        alert_on_departure=plate.alert_on_departure,
    )

    db.add(new_plate)
    db.commit()
    db.refresh(new_plate)

    return KnownPlateResponse.model_validate(new_plate)


@router.put("/plates/known/{plate_id}", response_model=KnownPlateResponse)
def update_known_plate(
    plate_id: int,
    update: KnownPlateUpdate,
    db: Session = Depends(get_db)
):
    """Update a known license plate"""
    plate = db.query(models.KnownLicensePlate).filter(
        models.KnownLicensePlate.id == plate_id
    ).first()

    if not plate:
        raise HTTPException(status_code=404, detail="Known plate not found")

    # Update fields
    if update.label is not None:
        plate.label = update.label
    if update.category is not None:
        plate.category = update.category
    if update.notes is not None:
        plate.notes = update.notes
    if update.alert_on_arrival is not None:
        plate.alert_on_arrival = update.alert_on_arrival
    if update.alert_on_departure is not None:
        plate.alert_on_departure = update.alert_on_departure

    db.commit()
    db.refresh(plate)

    return KnownPlateResponse.model_validate(plate)


@router.delete("/plates/known/{plate_id}", status_code=204)
def delete_known_plate(plate_id: int, db: Session = Depends(get_db)):
    """Remove a license plate from the known/watchlist"""
    plate = db.query(models.KnownLicensePlate).filter(
        models.KnownLicensePlate.id == plate_id
    ).first()

    if not plate:
        raise HTTPException(status_code=404, detail="Known plate not found")

    db.delete(plate)
    db.commit()

    return None


