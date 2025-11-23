"""
v3.10.0: Object Detection API Routes
Endpoints for YOLO-based object detection and identification
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from backend.database import crud
from backend.database.session import get_db
from backend.core.auth import get_current_user
from backend.database.models import User
from backend.api.schemas.pagination import PaginatedResponse, PaginationMetadata

router = APIRouter()


# ============================================================================
# PYDANTIC SCHEMAS
# ============================================================================


class ObjectDetectionEventResponse(BaseModel):
    """Response schema for object detection events"""
    id: int
    camera_id: str
    object_class: str  # vehicle, animal, package, person
    object_subclass: Optional[str]  # car, dog, backpack, etc.
    confidence: float
    detected_at: datetime
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    snapshot_path: Optional[str]
    identified_object_id: Optional[int]
    identified_object_name: Optional[str] = None  # Populated via join

    class Config:
        from_attributes = True


class IdentifiedObjectResponse(BaseModel):
    """Response schema for identified objects"""
    id: int
    object_id: str
    name: str
    object_class: str
    object_subclass: Optional[str]
    description: Optional[str]
    representative_image_path: Optional[str]
    detection_count: int
    first_seen_at: Optional[datetime]
    last_seen_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IdentifiedObjectCreate(BaseModel):
    """Schema for creating identified objects"""
    object_id: str = Field(..., description="Unique identifier (e.g., 'johns_tesla')")
    name: str = Field(..., description="Display name (e.g., 'John's Tesla')")
    object_class: str = Field(..., description="Object class: vehicle, animal, package")
    object_subclass: Optional[str] = Field(None, description="Subclass (car, dog, etc.)")
    description: Optional[str] = Field(None, description="User notes")
    features: Optional[str] = Field(None, description="JSON object features")
    notification_config: Optional[str] = Field(None, description="JSON notification config")


class IdentifiedObjectUpdate(BaseModel):
    """Schema for updating identified objects"""
    name: Optional[str] = None
    description: Optional[str] = None
    object_subclass: Optional[str] = None
    features: Optional[str] = None
    notification_config: Optional[str] = None
    is_active: Optional[bool] = None


class ObjectDetectionStatistics(BaseModel):
    """Statistics for object detections"""
    total_detections: int
    by_class: dict  # {"vehicle": 10, "animal": 5, ...}
    by_camera: dict  # {"front_door": 8, "backyard": 7, ...}
    identified_objects: int
    unidentified_objects: int


# ============================================================================
# OBJECT DETECTION EVENT ENDPOINTS
# ============================================================================


@router.get(
    "/detections/history",
    response_model=PaginatedResponse[ObjectDetectionEventResponse],
    summary="Get object detection history"
)
async def get_object_detection_history(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    object_class: Optional[str] = Query(None, description="Filter by class (vehicle/animal/package/person)"),
    identified_object_id: Optional[int] = Query(None, description="Filter by identified object"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get paginated object detection history with filtering

    Supports filtering by:
    - camera_id: Show detections from specific camera
    - object_class: Filter by object type (vehicle, animal, package, person)
    - identified_object_id: Show detections of specific identified object
    """
    # Calculate skip
    skip = (page - 1) * page_size

    # Get total count
    total = crud.count_object_detection_events(
        db=db,
        camera_id=camera_id,
        object_class=object_class,
        identified_object_id=identified_object_id
    )

    # Get detections
    detections = crud.get_object_detection_events(
        db=db,
        camera_id=camera_id,
        object_class=object_class,
        identified_object_id=identified_object_id,
        skip=skip,
        limit=page_size
    )

    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size
    has_more = page < total_pages

    # Convert to response models
    detection_responses = []
    for detection in detections:
        response = ObjectDetectionEventResponse.from_orm(detection)
        # Add identified object name if available
        if detection.identified_object:
            response.identified_object_name = detection.identified_object.name
        detection_responses.append(response)

    return PaginatedResponse(
        data=detection_responses,
        pagination=PaginationMetadata(
            total=total,
            filtered=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_more=has_more
        )
    )


@router.get(
    "/detections/statistics",
    response_model=ObjectDetectionStatistics,
    summary="Get object detection statistics"
)
async def get_object_detection_statistics(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregated statistics for object detections

    Returns counts by:
    - Object class (vehicle, animal, package, person)
    - Camera
    - Identified vs unidentified
    """
    # Get all detections (or filtered by camera)
    all_detections = crud.get_object_detection_events(
        db=db,
        camera_id=camera_id,
        skip=0,
        limit=10000  # Large limit to get all for statistics
    )

    # Aggregate statistics
    by_class = {"vehicle": 0, "animal": 0, "package": 0, "person": 0}
    by_camera = {}
    identified_count = 0
    unidentified_count = 0

    for detection in all_detections:
        # Count by class
        if detection.object_class in by_class:
            by_class[detection.object_class] += 1

        # Count by camera
        if detection.camera_id not in by_camera:
            by_camera[detection.camera_id] = 0
        by_camera[detection.camera_id] += 1

        # Count identified vs unidentified
        if detection.identified_object_id:
            identified_count += 1
        else:
            unidentified_count += 1

    return ObjectDetectionStatistics(
        total_detections=len(all_detections),
        by_class=by_class,
        by_camera=by_camera,
        identified_objects=identified_count,
        unidentified_objects=unidentified_count
    )


# ============================================================================
# IDENTIFIED OBJECT ENDPOINTS
# ============================================================================


@router.get(
    "/identified",
    response_model=List[IdentifiedObjectResponse],
    summary="List identified objects"
)
async def list_identified_objects(
    object_class: Optional[str] = Query(None, description="Filter by class (vehicle/animal/package)"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all identified objects (e.g., "John's Tesla", "My Dog Rex")

    Returns objects that have been identified by the user for tracking
    """
    objects = crud.get_identified_objects(
        db=db,
        object_class=object_class,
        is_active=is_active,
        skip=0,
        limit=1000
    )

    return [IdentifiedObjectResponse.from_orm(obj) for obj in objects]


@router.post(
    "/identified",
    response_model=IdentifiedObjectResponse,
    status_code=201,
    summary="Create identified object"
)
async def create_identified_object(
    object_data: IdentifiedObjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new identified object for tracking

    Examples:
    - Vehicle: {object_id: "johns_tesla", name: "John's Tesla", object_class: "vehicle", object_subclass: "car"}
    - Animal: {object_id: "my_dog_rex", name: "My Dog Rex", object_class: "animal", object_subclass: "dog"}
    - Package: {object_id: "delivery_box", name: "Delivery Box", object_class: "package"}
    """
    # Check if object_id already exists
    existing = crud.get_identified_object_by_id(db, object_data.object_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Object with ID '{object_data.object_id}' already exists"
        )

    # Validate object_class
    valid_classes = ["vehicle", "animal", "package"]
    if object_data.object_class not in valid_classes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid object_class. Must be one of: {valid_classes}"
        )

    # Create object
    db_object = crud.create_identified_object(
        db=db,
        object_data=object_data.dict()
    )

    return IdentifiedObjectResponse.from_orm(db_object)


@router.get(
    "/identified/{object_id}",
    response_model=IdentifiedObjectResponse,
    summary="Get identified object details"
)
async def get_identified_object(
    object_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific identified object"""
    db_object = crud.get_identified_object_by_id(db, object_id)
    if not db_object:
        raise HTTPException(status_code=404, detail="Object not found")

    return IdentifiedObjectResponse.from_orm(db_object)


@router.put(
    "/identified/{object_id}",
    response_model=IdentifiedObjectResponse,
    summary="Update identified object"
)
async def update_identified_object(
    object_id: str,
    update_data: IdentifiedObjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an identified object's information"""
    # Only include non-None fields
    update_dict = {k: v for k, v in update_data.dict().items() if v is not None}

    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")

    db_object = crud.update_identified_object(db, object_id, update_dict)
    if not db_object:
        raise HTTPException(status_code=404, detail="Object not found")

    return IdentifiedObjectResponse.from_orm(db_object)


@router.delete(
    "/identified/{object_id}",
    status_code=204,
    summary="Delete identified object"
)
async def delete_identified_object(
    object_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an identified object (soft delete by setting is_active=False)"""
    success = crud.delete_identified_object(db, object_id)
    if not success:
        raise HTTPException(status_code=404, detail="Object not found")

    return None


@router.get(
    "/identified/{object_id}/detections",
    response_model=PaginatedResponse[ObjectDetectionEventResponse],
    summary="Get detections for identified object"
)
async def get_identified_object_detections(
    object_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all detection events for a specific identified object"""
    # Get the identified object
    db_object = crud.get_identified_object_by_id(db, object_id)
    if not db_object:
        raise HTTPException(status_code=404, detail="Object not found")

    # Get detections using primary key
    skip = (page - 1) * page_size
    total = crud.count_object_detection_events(
        db=db,
        identified_object_id=db_object.id
    )

    detections = crud.get_object_detection_events(
        db=db,
        identified_object_id=db_object.id,
        skip=skip,
        limit=page_size
    )

    # Calculate pagination
    total_pages = (total + page_size - 1) // page_size
    has_more = page < total_pages

    # Convert to response
    detection_responses = [
        ObjectDetectionEventResponse.from_orm(d) for d in detections
    ]

    return PaginatedResponse(
        data=detection_responses,
        pagination=PaginationMetadata(
            total=total,
            filtered=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_more=has_more
        )
    )
