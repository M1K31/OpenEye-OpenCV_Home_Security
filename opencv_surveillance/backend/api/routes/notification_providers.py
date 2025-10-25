# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API routes for notification provider configuration
Allows users to configure email, SMS, push, and other notification channels
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import time
from datetime import datetime

from backend.database.session import get_db
from backend.database.alert_models import NotificationProvider
from backend.api.schemas.notifications import (
    NotificationProviderCreate,
    NotificationProviderUpdate,
    NotificationProviderResponse,
    NotificationProviderListResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    ProviderTemplate,
    ProviderTemplatesResponse,
)
from backend.core.auth import get_current_active_user
from backend.api.schemas.user import User

router = APIRouter(prefix="/notification-providers", tags=["notification-providers"])
logger = logging.getLogger(__name__)


def mask_config(provider_type: str, config: dict) -> dict:
    """
    Mask sensitive fields in configuration for API responses

    Args:
        provider_type: Type of provider
        config: Decrypted configuration

    Returns:
        Configuration with sensitive fields masked
    """
    masked = config.copy()

    # Define sensitive fields by provider type
    sensitive_fields = {
        "email": ["password"],
        "sms": ["auth_token"],
        "push": ["fcm_server_key"],
        "telegram": ["bot_token"],
        "discord": [],  # Webhook URL can be shown
        "webhook": []  # URL and headers can be shown
    }

    # Mask sensitive fields
    for field in sensitive_fields.get(provider_type, []):
        if field in masked:
            masked[field] = "***HIDDEN***"

    return masked


def provider_to_response(provider: NotificationProvider) -> NotificationProviderResponse:
    """
    Convert database model to response schema

    Args:
        provider: NotificationProvider database model

    Returns:
        NotificationProviderResponse
    """
    config = provider.get_config()
    config_summary = mask_config(provider.provider_type, config)

    return NotificationProviderResponse(
        id=provider.id,
        user_id=provider.user_id,
        provider_type=provider.provider_type,
        provider_name=provider.provider_name,
        enabled=provider.enabled,
        last_tested_at=provider.last_tested_at,
        test_status=provider.test_status,
        test_error=provider.test_error,
        total_sent=provider.total_sent,
        total_failed=provider.total_failed,
        last_used_at=provider.last_used_at,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
        config_summary=config_summary
    )


@router.get("/templates", response_model=ProviderTemplatesResponse)
def get_provider_templates():
    """
    Get templates for all supported notification provider types

    Returns configuration field definitions for the frontend
    """
    templates = [
        ProviderTemplate(
            provider_type="email",
            display_name="Email (SMTP)",
            description="Send email notifications via SMTP server (Gmail, Outlook, custom server)",
            icon="📧",
            config_fields=[
                {"name": "smtp_host", "label": "SMTP Host", "type": "text", "placeholder": "smtp.gmail.com", "required": True},
                {"name": "smtp_port", "label": "SMTP Port", "type": "number", "placeholder": "587", "default": 587, "required": True},
                {"name": "username", "label": "Username/Email", "type": "text", "placeholder": "your-email@gmail.com", "required": True},
                {"name": "password", "label": "Password", "type": "password", "placeholder": "App-specific password", "required": True, "sensitive": True},
                {"name": "from_email", "label": "From Email (optional)", "type": "text", "placeholder": "noreply@yourdomain.com", "required": False},
                {"name": "use_tls", "label": "Use TLS", "type": "checkbox", "default": True, "required": False},
            ]
        ),
        ProviderTemplate(
            provider_type="sms",
            display_name="SMS (Twilio)",
            description="Send SMS text messages via Twilio",
            icon="📱",
            config_fields=[
                {"name": "account_sid", "label": "Account SID", "type": "text", "placeholder": "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "required": True},
                {"name": "auth_token", "label": "Auth Token", "type": "password", "placeholder": "Your Twilio Auth Token", "required": True, "sensitive": True},
                {"name": "from_number", "label": "From Phone Number", "type": "text", "placeholder": "+15551234567", "required": True},
            ]
        ),
        ProviderTemplate(
            provider_type="push",
            display_name="Push Notifications (FCM)",
            description="Send push notifications via Firebase Cloud Messaging",
            icon="🔔",
            config_fields=[
                {"name": "fcm_server_key", "label": "FCM Server Key", "type": "password", "placeholder": "Your Firebase Server Key", "required": True, "sensitive": True},
            ]
        ),
        ProviderTemplate(
            provider_type="telegram",
            display_name="Telegram Bot",
            description="Send messages via Telegram bot",
            icon="✈️",
            config_fields=[
                {"name": "bot_token", "label": "Bot Token", "type": "password", "placeholder": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz", "required": True, "sensitive": True},
            ]
        ),
        ProviderTemplate(
            provider_type="discord",
            display_name="Discord Webhook",
            description="Send messages to Discord channel via webhook",
            icon="💬",
            config_fields=[
                {"name": "webhook_url", "label": "Webhook URL", "type": "text", "placeholder": "https://discord.com/api/webhooks/...", "required": True},
            ]
        ),
        ProviderTemplate(
            provider_type="webhook",
            display_name="Custom Webhook",
            description="Send HTTP requests to custom webhook endpoint",
            icon="🔗",
            config_fields=[
                {"name": "url", "label": "Webhook URL", "type": "text", "placeholder": "https://your-server.com/webhook", "required": True},
                {"name": "method", "label": "HTTP Method", "type": "select", "options": ["POST", "PUT", "PATCH"], "default": "POST", "required": True},
                {"name": "timeout", "label": "Timeout (seconds)", "type": "number", "default": 10, "required": False},
            ]
        ),
    ]

    return ProviderTemplatesResponse(templates=templates)


@router.get("/", response_model=NotificationProviderListResponse)
def list_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    List all notification providers for the current user
    """
    providers = db.query(NotificationProvider).filter(
        NotificationProvider.user_id == current_user.id
    ).all()

    provider_responses = [provider_to_response(p) for p in providers]

    return NotificationProviderListResponse(
        providers=provider_responses,
        total=len(provider_responses)
    )


@router.get("/{provider_id}", response_model=NotificationProviderResponse)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific notification provider
    """
    provider = db.query(NotificationProvider).filter(
        NotificationProvider.id == provider_id,
        NotificationProvider.user_id == current_user.id
    ).first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification provider not found"
        )

    return provider_to_response(provider)


@router.post("/", response_model=NotificationProviderResponse, status_code=status.HTTP_201_CREATED)
def create_provider(
    request: NotificationProviderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new notification provider

    Configuration is automatically encrypted before storage
    """
    try:
        # Create new provider
        provider = NotificationProvider(
            user_id=current_user.id,
            provider_type=request.provider_type,
            provider_name=request.provider_name,
            enabled=request.enabled,
            test_status="not_tested"
        )

        # Encrypt and store configuration
        provider.set_config(request.config)

        db.add(provider)
        db.commit()
        db.refresh(provider)

        logger.info(f"Created notification provider: {provider.provider_name} ({provider.provider_type})")

        return provider_to_response(provider)

    except Exception as e:
        logger.error(f"Error creating notification provider: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification provider: {str(e)}"
        )


@router.put("/{provider_id}", response_model=NotificationProviderResponse)
def update_provider(
    provider_id: int,
    request: NotificationProviderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an existing notification provider
    """
    provider = db.query(NotificationProvider).filter(
        NotificationProvider.id == provider_id,
        NotificationProvider.user_id == current_user.id
    ).first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification provider not found"
        )

    try:
        # Update fields
        if request.provider_name is not None:
            provider.provider_name = request.provider_name

        if request.enabled is not None:
            provider.enabled = request.enabled

        if request.config is not None:
            # Re-encrypt with new configuration
            provider.set_config(request.config)
            # Reset test status when config changes
            provider.test_status = "not_tested"
            provider.test_error = None

        db.commit()
        db.refresh(provider)

        logger.info(f"Updated notification provider: {provider.provider_name}")

        return provider_to_response(provider)

    except Exception as e:
        logger.error(f"Error updating notification provider: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification provider: {str(e)}"
        )


@router.delete("/{provider_id}")
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a notification provider
    """
    provider = db.query(NotificationProvider).filter(
        NotificationProvider.id == provider_id,
        NotificationProvider.user_id == current_user.id
    ).first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification provider not found"
        )

    try:
        provider_name = provider.provider_name
        db.delete(provider)
        db.commit()

        logger.info(f"Deleted notification provider: {provider_name}")

        return {"success": True, "message": f"Provider '{provider_name}' deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting notification provider: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notification provider: {str(e)}"
        )


@router.post("/{provider_id}/test", response_model=TestNotificationResponse)
async def test_provider(
    provider_id: int,
    request: TestNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Test a notification provider by sending a test message

    Updates the provider's test_status based on the result
    """
    provider = db.query(NotificationProvider).filter(
        NotificationProvider.id == provider_id,
        NotificationProvider.user_id == current_user.id
    ).first()

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification provider not found"
        )

    try:
        # Get decrypted configuration
        config = provider.get_config()

        # Import appropriate notifier
        from backend.core.alert_notification_system import (
            EmailNotifier, SMSNotifier, PushNotifier,
            TelegramNotifier, WebhookNotifier, Notification,
            NotificationChannel, AlertPriority
        )

        # Create test notification
        from uuid import uuid4
        test_notification = Notification(
            id=str(uuid4()),
            alert_rule_id="test",
            channel=NotificationChannel(provider.provider_type),
            recipient=request.recipient,
            subject=request.subject or "Test Notification",
            body=request.message or "This is a test notification from OpenEye.",
            priority=AlertPriority.LOW,
            timestamp=datetime.utcnow()
        )

        # Initialize appropriate notifier
        start_time = time.time()
        success = False

        if provider.provider_type == "email":
            notifier = EmailNotifier(
                smtp_host=config['smtp_host'],
                smtp_port=config['smtp_port'],
                username=config['username'],
                password=config['password'],
                from_email=config.get('from_email', config['username']),
                use_tls=config.get('use_tls', True)
            )
            success = await notifier.send(test_notification)

        elif provider.provider_type == "sms":
            notifier = SMSNotifier(
                account_sid=config['account_sid'],
                auth_token=config['auth_token'],
                from_number=config['from_number']
            )
            success = await notifier.send(test_notification)

        elif provider.provider_type == "push":
            notifier = PushNotifier(
                fcm_server_key=config['fcm_server_key']
            )
            success = await notifier.send(test_notification)

        elif provider.provider_type == "telegram":
            notifier = TelegramNotifier(
                bot_token=config['bot_token']
            )
            success = await notifier.send(test_notification)

        elif provider.provider_type == "webhook":
            notifier = WebhookNotifier(
                webhook_url=config['url'],
                headers=config.get('headers'),
                timeout=config.get('timeout', 10)
            )
            success = await notifier.send(test_notification)

        elif provider.provider_type == "discord":
            # Discord uses webhook notifier
            notifier = WebhookNotifier(
                webhook_url=config['webhook_url'],
                timeout=10
            )
            # Override to send Discord-formatted payload
            import requests
            response = requests.post(
                config['webhook_url'],
                json={"content": f"**{request.subject}**\n{request.message}"},
                timeout=10
            )
            success = response.status_code == 204

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider type: {provider.provider_type}"
            )

        delivery_time = time.time() - start_time

        # Update provider test status
        provider.last_tested_at = datetime.utcnow()
        if success:
            provider.test_status = "success"
            provider.test_error = None
        else:
            provider.test_status = "failed"
            provider.test_error = test_notification.error or "Unknown error"

        db.commit()

        return TestNotificationResponse(
            success=success,
            message="Test notification sent successfully!" if success else "Failed to send test notification",
            error=test_notification.error if not success else None,
            delivery_time=delivery_time
        )

    except Exception as e:
        logger.error(f"Error testing notification provider: {e}")

        # Update provider test status
        provider.last_tested_at = datetime.utcnow()
        provider.test_status = "failed"
        provider.test_error = str(e)
        db.commit()

        return TestNotificationResponse(
            success=False,
            message="Test failed",
            error=str(e)
        )
