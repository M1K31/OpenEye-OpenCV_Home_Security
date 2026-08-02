# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Alert Management API Routes
Provides endpoints for configuring and viewing alerts
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

from backend.database.session import SessionLocal, get_db
from backend.database import alert_models
from backend.core.performance import paginate, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from backend.api.schemas.pagination import PaginatedResponse

router = APIRouter()


# Pydantic Models for API


class AlertConfigCreate(BaseModel):
    """Schema for creating/updating alert configuration"""

    user_id: int = 1  # Default to user 1 for now

    # Alert types
    motion_alerts_enabled: bool = True
    face_recognition_alerts_enabled: bool = True
    unknown_face_alerts_enabled: bool = True
    recording_alerts_enabled: bool = False

    # Channels
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = False
    webhook_enabled: bool = False

    # Contact info
    email_address: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    push_token: Optional[str] = None
    webhook_url: Optional[str] = None

    # Throttling
    min_seconds_between_alerts: int = 300

    # Quiet hours
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"


class AlertConfigResponse(AlertConfigCreate):
    """Schema for alert configuration response"""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotificationLogResponse(BaseModel):
    """Schema for notification log response"""

    id: int
    event_type: str
    camera_id: str
    channel: str
    recipient: str
    subject: Optional[str]
    message: str
    sent_successfully: bool
    error_message: Optional[str]
    created_at: datetime
    sent_at: Optional[datetime]

    class Config:
        from_attributes = True


class TestAlertRequest(BaseModel):
    """Schema for testing alert delivery"""

    alert_config_id: int
    channel: str  # "email", "sms", "push", or "webhook"
    message: Optional[str] = "This is a test alert from OpenEye"


# Dependency


# get_db is imported from backend.database.session rather than redefined here:
# FastAPI matches dependency_overrides by function identity, so a module-local
# copy is a *different* dependency and silently escapes any override (and used a
# separate session provider from the rest of the app).


# API Endpoints


@router.get("/alerts/config", response_model=List[AlertConfigResponse])
def get_alert_configurations(
        user_id: int = Query(
            1,
            description="User ID"),
        db: Session = Depends(get_db)):
    """
    Get alert configurations for a user

    Returns all alert configurations. For now, we use user_id=1 as default.
    """
    configs = (
        db.query(alert_models.AlertConfiguration)
        .filter(alert_models.AlertConfiguration.user_id == user_id)
        .all()
    )

    return configs


@router.post("/alerts/config",
             response_model=AlertConfigResponse,
             status_code=201)
def create_alert_configuration(
    config: AlertConfigCreate, db: Session = Depends(get_db)
):
    """
    Create a new alert configuration

    Creates alert settings for the user. If a configuration already exists,
    use the PUT endpoint to update it instead.
    """
    # Check if config already exists for this user
    existing = (
        db.query(alert_models.AlertConfiguration)
        .filter(alert_models.AlertConfiguration.user_id == config.user_id)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Alert configuration already exists for user {config.user_id}. Use PUT to update.",
        )

    # Create new configuration
    db_config = alert_models.AlertConfiguration(**config.model_dump())
    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    return db_config


@router.put("/alerts/config/{config_id}", response_model=AlertConfigResponse)
def update_alert_configuration(
    config_id: int, config: AlertConfigCreate, db: Session = Depends(get_db)
):
    """
    Update an existing alert configuration
    """
    db_config = (
        db.query(alert_models.AlertConfiguration)
        .filter(alert_models.AlertConfiguration.id == config_id)
        .first()
    )

    if not db_config:
        raise HTTPException(status_code=404,
                            detail="Alert configuration not found")

    # Update fields
    for key, value in config.model_dump().items():
        setattr(db_config, key, value)

    db_config.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_config)

    return db_config


@router.delete("/alerts/config/{config_id}", status_code=200)
def delete_alert_configuration(config_id: int, db: Session = Depends(get_db)):
    """
    Delete an alert configuration
    """
    db_config = (
        db.query(alert_models.AlertConfiguration)
        .filter(alert_models.AlertConfiguration.id == config_id)
        .first()
    )

    if not db_config:
        raise HTTPException(status_code=404,
                            detail="Alert configuration not found")

    db.delete(db_config)
    db.commit()

    return {"message": f"Alert configuration {config_id} deleted successfully"}


@router.get("/alerts/logs", response_model=PaginatedResponse[NotificationLogResponse])
def get_notification_logs(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Get notification logs with optional filters and pagination

    Returns a history of all sent notifications for debugging and tracking.

    Args:
        - **event_type**: Optional event type filter
        - **camera_id**: Optional camera ID filter
        - **channel**: Optional channel filter (email, sms, push, webhook)
        - **page**: Page number (default: 1)
        - **page_size**: Items per page (default: 50, max: 1000)

    Returns:
        PaginatedResponse with notification logs and pagination metadata

    Performance:
        Optimized COUNT queries: single query when no filters applied (v3.11.7)
    """
    from backend.core.performance import paginate_with_metadata

    # Build base and filtered queries
    base_query = db.query(alert_models.NotificationLog)
    query = db.query(alert_models.NotificationLog)

    # Track if any filters are applied
    has_filters = False

    # Apply filters
    if event_type:
        query = query.filter(alert_models.NotificationLog.event_type == event_type)
        has_filters = True

    if camera_id:
        query = query.filter(alert_models.NotificationLog.camera_id == camera_id)
        has_filters = True

    if channel:
        query = query.filter(alert_models.NotificationLog.channel == channel)
        has_filters = True

    # Order by most recent
    query = query.order_by(alert_models.NotificationLog.created_at.desc())

    # Apply optimized pagination (single COUNT when no filters)
    return paginate_with_metadata(
        query=query,
        base_query=base_query,
        page=page,
        page_size=page_size,
        has_filters=has_filters
    )


@router.post("/alerts/test", status_code=200)
async def test_alert(request: TestAlertRequest, db: Session = Depends(get_db)):
    """
    Send a test alert to verify notification settings

    Useful for testing if email, SMS, push, or webhook is configured correctly.
    """
    from backend.services.notification_service import get_notification_service

    # Get configuration
    config = (
        db.query(alert_models.AlertConfiguration)
        .filter(alert_models.AlertConfiguration.id == request.alert_config_id)
        .first()
    )

    if not config:
        raise HTTPException(status_code=404,
                            detail="Alert configuration not found")

    notification_service = get_notification_service()

    # Send test notification based on channel
    if request.channel == "email":
        if not config.email_enabled or not config.email_address:
            raise HTTPException(
                status_code=400, detail="Email not enabled or address not set"
            )

        success, error = await notification_service.send_email(
            to_address=config.email_address,
            subject="[OpenEye] Test Alert",
            body=request.message,
        )

    elif request.channel == "sms":
        if not config.sms_enabled or not config.phone_number:
            raise HTTPException(
                status_code=400,
                detail="SMS not enabled or phone number not set")

        success, error = notification_service.send_sms(
            to_number=config.phone_number, message=f"[OpenEye Test] {request.message}")

    elif request.channel == "push":
        if not config.push_enabled or not config.push_token:
            raise HTTPException(
                status_code=400, detail="Push not enabled or token not set"
            )

        success, error = await notification_service.send_push_notification(
            token=config.push_token, title="OpenEye Test Alert", body=request.message
        )

    elif request.channel == "webhook":
        if not config.webhook_enabled or not config.webhook_url:
            raise HTTPException(
                status_code=400, detail="Webhook not enabled or URL not set"
            )

        success, error = await notification_service.send_webhook(
            webhook_url=config.webhook_url,
            payload={
                "test": True,
                "message": request.message,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    else:
        raise HTTPException(
            status_code=400, detail=f"Invalid channel: {request.channel}"
        )

    if success:
        return {
            "success": True,
            "message": f"Test {request.channel} sent successfully",
            "channel": request.channel,
        }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test {request.channel}: {error}")


@router.get("/alerts/statistics")
def get_alert_statistics(
    days: int = Query(7, description="Number of days to analyze"),
    db: Session = Depends(get_db),
):
    """
    Get alert statistics for the specified time period
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total notifications sent
    total = (
        db.query(alert_models.NotificationLog)
        .filter(alert_models.NotificationLog.created_at >= cutoff)
        .count()
    )

    # Successful notifications
    successful = (
        db.query(alert_models.NotificationLog)
        .filter(
            alert_models.NotificationLog.created_at >= cutoff,
            alert_models.NotificationLog.sent_successfully.is_(True),
        )
        .count()
    )

    # Failed notifications
    failed = total - successful

    # By channel
    channels = {}
    for channel in ["email", "sms", "push", "webhook"]:
        count = (
            db.query(alert_models.NotificationLog)
            .filter(
                alert_models.NotificationLog.created_at >= cutoff,
                alert_models.NotificationLog.channel == channel,
            )
            .count()
        )
        channels[channel] = count

    # By event type
    event_types = {}
    for event_type in [
        "motion",
        "face_known",
        "face_unknown",
        "recording_started",
        "recording_stopped",
    ]:
        count = (
            db.query(alert_models.NotificationLog)
            .filter(
                alert_models.NotificationLog.created_at >= cutoff,
                alert_models.NotificationLog.event_type == event_type,
            )
            .count()
        )
        event_types[event_type] = count

    return {
        "period_days": days,
        "total_notifications": total,
        "successful": successful,
        "failed": failed,
        "success_rate": (successful / total * 100) if total > 0 else 0,
        "by_channel": channels,
        "by_event_type": event_types,
    }
