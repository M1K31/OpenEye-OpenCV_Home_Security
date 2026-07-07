# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Pydantic schemas for notification provider configuration
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime


# Email Provider Configuration

class EmailProviderConfig(BaseModel):
    """Email (SMTP) provider configuration"""
    smtp_host: str = Field(..., description="SMTP server hostname")
    smtp_port: int = Field(587, description="SMTP server port")
    username: str = Field(..., description="SMTP username")
    password: str = Field(..., description="SMTP password")
    from_email: Optional[str] = Field(None, description="From email address (defaults to username)")
    use_tls: bool = Field(True, description="Use TLS encryption")
    to_email: Optional[str] = Field(None, description="Notification recipient (defaults to from_email/username)")

    @validator('smtp_port')
    def validate_port(cls, v):
        if not (1 <= v <= 65535):
            raise ValueError('Port must be between 1 and 65535')
        return v


# SMS Provider Configuration

class SMSProviderConfig(BaseModel):
    """SMS (Twilio) provider configuration"""
    account_sid: str = Field(..., description="Twilio Account SID")
    auth_token: str = Field(..., description="Twilio Auth Token")
    from_number: str = Field(..., description="Twilio phone number (E.164 format)")

    @validator('from_number')
    def validate_phone(cls, v):
        if not v.startswith('+'):
            raise ValueError('Phone number must be in E.164 format (e.g., +15551234567)')
        return v


# Push Notification Provider Configuration

class PushProviderConfig(BaseModel):
    """Push notification (FCM) provider configuration"""
    fcm_server_key: str = Field(..., description="Firebase Cloud Messaging Server Key")


# Telegram Provider Configuration

class TelegramProviderConfig(BaseModel):
    """Telegram Bot provider configuration"""
    bot_token: str = Field(..., description="Telegram Bot Token")
    chat_id: Optional[str] = Field(None, description="Telegram chat id to deliver notifications to")

    @validator('bot_token')
    def validate_token(cls, v):
        if ':' not in v:
            raise ValueError('Invalid Telegram bot token format')
        return v


# Discord Provider Configuration

class DiscordProviderConfig(BaseModel):
    """Discord Webhook provider configuration"""
    webhook_url: str = Field(..., description="Discord Webhook URL")

    @validator('webhook_url')
    def validate_url(cls, v):
        if not v.startswith('https://discord.com/api/webhooks/'):
            raise ValueError('Invalid Discord webhook URL')
        return v


# Generic Webhook Provider Configuration

class WebhookProviderConfig(BaseModel):
    """Generic webhook provider configuration"""
    url: str = Field(..., description="Webhook URL")
    method: str = Field("POST", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom HTTP headers")
    timeout: int = Field(10, description="Request timeout in seconds")

    @validator('method')
    def validate_method(cls, v):
        if v.upper() not in ['GET', 'POST', 'PUT', 'PATCH']:
            raise ValueError('Method must be GET, POST, PUT, or PATCH')
        return v.upper()


# Provider Creation/Update Requests

class NotificationProviderCreate(BaseModel):
    """Create a new notification provider"""
    provider_type: str = Field(..., description="Provider type: email, sms, push, telegram, discord, webhook")
    provider_name: str = Field(..., description="User-friendly name")
    enabled: bool = Field(True, description="Enable this provider")
    config: Dict[str, Any] = Field(..., description="Provider configuration (will be encrypted)")

    @validator('provider_type')
    def validate_provider_type(cls, v):
        valid_types = ['email', 'sms', 'push', 'telegram', 'discord', 'webhook']
        if v not in valid_types:
            raise ValueError(f'Provider type must be one of: {", ".join(valid_types)}')
        return v


class NotificationProviderUpdate(BaseModel):
    """Update an existing notification provider"""
    provider_name: Optional[str] = Field(None, description="User-friendly name")
    enabled: Optional[bool] = Field(None, description="Enable/disable provider")
    config: Optional[Dict[str, Any]] = Field(None, description="Provider configuration (will be encrypted)")


# Provider Response (without sensitive data)

class NotificationProviderResponse(BaseModel):
    """Notification provider response (credentials masked)"""
    id: int
    user_id: int
    provider_type: str
    provider_name: str
    enabled: bool

    # Test status
    last_tested_at: Optional[datetime]
    test_status: Optional[str]
    test_error: Optional[str]

    # Usage stats
    total_sent: int
    total_failed: int
    last_used_at: Optional[datetime]

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Masked config (show fields but hide values)
    config_summary: Dict[str, str] = Field(..., description="Configuration summary with masked credentials")

    class Config:
        from_attributes = True


# Provider List Response

class NotificationProviderListResponse(BaseModel):
    """List of notification providers"""
    providers: List[NotificationProviderResponse]
    total: int


# Test Notification Request

class TestNotificationRequest(BaseModel):
    """Test notification provider"""
    recipient: str = Field(..., description="Test recipient (email, phone, chat_id, etc.)")
    subject: Optional[str] = Field("Test Notification", description="Test subject/title")
    message: Optional[str] = Field("This is a test notification from OpenEye.", description="Test message body")


# Test Notification Response

class TestNotificationResponse(BaseModel):
    """Test notification result"""
    success: bool
    message: str
    error: Optional[str] = None
    delivery_time: Optional[float] = Field(None, description="Delivery time in seconds")


# Provider Templates (for frontend)

class ProviderTemplate(BaseModel):
    """Template for a notification provider type"""
    provider_type: str
    display_name: str
    description: str
    icon: str
    config_fields: List[Dict[str, Any]]


class ProviderTemplatesResponse(BaseModel):
    """List of available provider templates"""
    templates: List[ProviderTemplate]
