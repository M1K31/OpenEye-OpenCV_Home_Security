# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for notification provider API schemas
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.api.schemas.notifications import (
    EmailProviderConfig,
    SMSProviderConfig,
    PushProviderConfig,
    TelegramProviderConfig,
    DiscordProviderConfig,
    WebhookProviderConfig,
    NotificationProviderCreate,
    NotificationProviderUpdate,
    NotificationProviderResponse,
    NotificationProviderListResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    ProviderTemplate,
    ProviderTemplatesResponse,
)


class TestEmailProviderConfig:
    """Test EmailProviderConfig schema"""

    def test_valid_email_provider_config(self):
        """Test valid email provider configuration"""
        config = EmailProviderConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            username="user@example.com",
            password="secret123",
            from_email="noreply@example.com",
            use_tls=True,
        )

        assert config.smtp_host == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.username == "user@example.com"
        assert config.password == "secret123"
        assert config.from_email == "noreply@example.com"
        assert config.use_tls is True

    def test_email_config_defaults(self):
        """Test email config default values"""
        config = EmailProviderConfig(
            smtp_host="smtp.example.com",
            username="user",
            password="pass",
        )

        assert config.smtp_port == 587
        assert config.from_email is None
        assert config.use_tls is True

    def test_smtp_port_valid_range(self):
        """Test SMTP port validation with valid ports"""
        for port in [1, 25, 587, 465, 65535]:
            config = EmailProviderConfig(
                smtp_host="smtp.example.com",
                smtp_port=port,
                username="user",
                password="pass",
            )
            assert config.smtp_port == port

    def test_smtp_port_below_range(self):
        """Test SMTP port validation rejects port < 1"""
        with pytest.raises(ValidationError) as exc_info:
            EmailProviderConfig(
                smtp_host="smtp.example.com",
                smtp_port=0,
                username="user",
                password="pass",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("smtp_port",) for error in errors)
        assert any("1 and 65535" in error["msg"] for error in errors)

    def test_smtp_port_above_range(self):
        """Test SMTP port validation rejects port > 65535"""
        with pytest.raises(ValidationError) as exc_info:
            EmailProviderConfig(
                smtp_host="smtp.example.com",
                smtp_port=65536,
                username="user",
                password="pass",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("smtp_port",) for error in errors)
        assert any("1 and 65535" in error["msg"] for error in errors)


class TestSMSProviderConfig:
    """Test SMSProviderConfig schema"""

    def test_valid_sms_provider_config(self):
        """Test valid SMS provider configuration"""
        config = SMSProviderConfig(
            account_sid="AC123456789",
            auth_token="secret_token",
            from_number="+15551234567",
        )

        assert config.account_sid == "AC123456789"
        assert config.auth_token == "secret_token"
        assert config.from_number == "+15551234567"

    def test_from_number_e164_format(self):
        """Test from_number accepts valid E.164 format"""
        valid_numbers = ["+1555123456", "+442071234567", "+8613800138000"]

        for number in valid_numbers:
            config = SMSProviderConfig(
                account_sid="AC123",
                auth_token="token",
                from_number=number,
            )
            assert config.from_number == number

    def test_from_number_missing_plus(self):
        """Test from_number rejects numbers without leading +"""
        with pytest.raises(ValidationError) as exc_info:
            SMSProviderConfig(
                account_sid="AC123",
                auth_token="token",
                from_number="15551234567",  # Missing +
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("from_number",) for error in errors)
        assert any("E.164 format" in error["msg"] for error in errors)


class TestPushProviderConfig:
    """Test PushProviderConfig schema"""

    def test_valid_push_provider_config(self):
        """Test valid push provider configuration"""
        config = PushProviderConfig(
            fcm_server_key="AAAA1234567890:abcdefghijklmnop",
        )

        assert config.fcm_server_key == "AAAA1234567890:abcdefghijklmnop"


class TestTelegramProviderConfig:
    """Test TelegramProviderConfig schema"""

    def test_valid_telegram_provider_config(self):
        """Test valid Telegram provider configuration"""
        config = TelegramProviderConfig(
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
        )

        assert config.bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

    def test_bot_token_format_validation(self):
        """Test bot_token validation requires colon"""
        valid_tokens = [
            "123456:ABC",
            "987654321:XYZ123abc",
            "111:222",
        ]

        for token in valid_tokens:
            config = TelegramProviderConfig(bot_token=token)
            assert config.bot_token == token

    def test_bot_token_missing_colon(self):
        """Test bot_token rejects tokens without colon"""
        with pytest.raises(ValidationError) as exc_info:
            TelegramProviderConfig(bot_token="123456789ABC")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("bot_token",) for error in errors)
        assert any("Invalid Telegram bot token format" in error["msg"] for error in errors)


class TestDiscordProviderConfig:
    """Test DiscordProviderConfig schema"""

    def test_valid_discord_provider_config(self):
        """Test valid Discord provider configuration"""
        config = DiscordProviderConfig(
            webhook_url="https://discord.com/api/webhooks/123456789/abcdefg",
        )

        assert config.webhook_url == "https://discord.com/api/webhooks/123456789/abcdefg"

    def test_webhook_url_validation(self):
        """Test webhook_url validation requires Discord URL"""
        valid_urls = [
            "https://discord.com/api/webhooks/123/abc",
            "https://discord.com/api/webhooks/987654321/XYZ123abc456def",
        ]

        for url in valid_urls:
            config = DiscordProviderConfig(webhook_url=url)
            assert config.webhook_url == url

    def test_webhook_url_invalid_prefix(self):
        """Test webhook_url rejects non-Discord URLs"""
        invalid_urls = [
            "https://example.com/webhook",
            "http://discord.com/api/webhooks/123/abc",
            "discord.com/api/webhooks/123/abc",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                DiscordProviderConfig(webhook_url=url)

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("webhook_url",) for error in errors)
            assert any("Invalid Discord webhook URL" in error["msg"] for error in errors)


class TestWebhookProviderConfig:
    """Test WebhookProviderConfig schema"""

    def test_valid_webhook_provider_config(self):
        """Test valid webhook provider configuration"""
        config = WebhookProviderConfig(
            url="https://example.com/webhook",
            method="POST",
            headers={"Authorization": "Bearer token"},
            timeout=10,
        )

        assert config.url == "https://example.com/webhook"
        assert config.method == "POST"
        assert config.headers == {"Authorization": "Bearer token"}
        assert config.timeout == 10

    def test_webhook_config_defaults(self):
        """Test webhook config default values"""
        config = WebhookProviderConfig(url="https://example.com/webhook")

        assert config.method == "POST"
        assert config.headers is None
        assert config.timeout == 10

    def test_method_validation_valid_methods(self):
        """Test method validator accepts valid HTTP methods"""
        for method in ["GET", "POST", "PUT", "PATCH"]:
            config = WebhookProviderConfig(
                url="https://example.com/webhook",
                method=method,
            )
            assert config.method == method.upper()

    def test_method_validation_lowercase(self):
        """Test method validator converts to uppercase"""
        for method in ["get", "post", "put", "patch"]:
            config = WebhookProviderConfig(
                url="https://example.com/webhook",
                method=method,
            )
            assert config.method == method.upper()

    def test_method_validation_invalid_method(self):
        """Test method validator rejects invalid methods"""
        invalid_methods = ["DELETE", "HEAD", "OPTIONS", "TRACE"]

        for method in invalid_methods:
            with pytest.raises(ValidationError) as exc_info:
                WebhookProviderConfig(
                    url="https://example.com/webhook",
                    method=method,
                )

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("method",) for error in errors)
            assert any("GET, POST, PUT, or PATCH" in error["msg"] for error in errors)


class TestNotificationProviderCreate:
    """Test NotificationProviderCreate schema"""

    def test_valid_notification_provider_create(self):
        """Test valid notification provider creation"""
        provider = NotificationProviderCreate(
            provider_type="email",
            provider_name="Gmail",
            enabled=True,
            config={"smtp_host": "smtp.gmail.com", "username": "user"},
        )

        assert provider.provider_type == "email"
        assert provider.provider_name == "Gmail"
        assert provider.enabled is True
        assert provider.config["smtp_host"] == "smtp.gmail.com"

    def test_provider_create_defaults(self):
        """Test provider create default values"""
        provider = NotificationProviderCreate(
            provider_type="sms",
            provider_name="Twilio",
            config={},
        )

        assert provider.enabled is True

    def test_provider_type_validation_valid_types(self):
        """Test provider_type validation accepts valid types"""
        valid_types = ["email", "sms", "push", "telegram", "discord", "webhook"]

        for ptype in valid_types:
            provider = NotificationProviderCreate(
                provider_type=ptype,
                provider_name="Test",
                config={},
            )
            assert provider.provider_type == ptype

    def test_provider_type_validation_invalid_type(self):
        """Test provider_type validation rejects invalid types"""
        with pytest.raises(ValidationError) as exc_info:
            NotificationProviderCreate(
                provider_type="slack",  # Invalid
                provider_name="Slack",
                config={},
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("provider_type",) for error in errors)
        assert any("must be one of" in error["msg"] for error in errors)


class TestNotificationProviderUpdate:
    """Test NotificationProviderUpdate schema"""

    def test_valid_notification_provider_update(self):
        """Test valid notification provider update"""
        update = NotificationProviderUpdate(
            provider_name="Updated Name",
            enabled=False,
            config={"new_field": "value"},
        )

        assert update.provider_name == "Updated Name"
        assert update.enabled is False
        assert update.config == {"new_field": "value"}

    def test_notification_provider_update_all_optional(self):
        """Test all fields are optional for update"""
        update = NotificationProviderUpdate()

        assert update.provider_name is None
        assert update.enabled is None
        assert update.config is None


class TestNotificationProviderResponse:
    """Test NotificationProviderResponse schema"""

    def test_valid_notification_provider_response(self):
        """Test valid notification provider response"""
        now = datetime.now()
        response = NotificationProviderResponse(
            id=123,
            user_id=1,
            provider_type="email",
            provider_name="Gmail",
            enabled=True,
            last_tested_at=now,
            test_status="success",
            test_error=None,
            total_sent=100,
            total_failed=5,
            last_used_at=now,
            created_at=now,
            updated_at=now,
            config_summary={"smtp_host": "smtp.gmail.com", "username": "***"},
        )

        assert response.id == 123
        assert response.user_id == 1
        assert response.provider_type == "email"
        assert response.total_sent == 100
        assert response.total_failed == 5

    def test_notification_provider_response_optional_fields(self):
        """Test notification provider response with None optional fields"""
        now = datetime.now()
        response = NotificationProviderResponse(
            id=1,
            user_id=1,
            provider_type="sms",
            provider_name="Twilio",
            enabled=True,
            last_tested_at=None,
            test_status=None,
            test_error=None,
            total_sent=0,
            total_failed=0,
            last_used_at=None,
            created_at=now,
            updated_at=now,
            config_summary={},
        )

        assert response.last_tested_at is None
        assert response.test_status is None
        assert response.test_error is None
        assert response.last_used_at is None


class TestNotificationProviderListResponse:
    """Test NotificationProviderListResponse schema"""

    def test_valid_notification_provider_list_response(self):
        """Test valid notification provider list response"""
        now = datetime.now()
        providers = [
            NotificationProviderResponse(
                id=1,
                user_id=1,
                provider_type="email",
                provider_name="Gmail",
                enabled=True,
                last_tested_at=None,
                test_status=None,
                test_error=None,
                total_sent=10,
                total_failed=0,
                last_used_at=None,
                created_at=now,
                updated_at=now,
                config_summary={},
            ),
            NotificationProviderResponse(
                id=2,
                user_id=1,
                provider_type="sms",
                provider_name="Twilio",
                enabled=True,
                last_tested_at=None,
                test_status=None,
                test_error=None,
                total_sent=5,
                total_failed=1,
                last_used_at=None,
                created_at=now,
                updated_at=now,
                config_summary={},
            ),
        ]

        response = NotificationProviderListResponse(providers=providers, total=2)

        assert len(response.providers) == 2
        assert response.total == 2

    def test_empty_notification_provider_list(self):
        """Test empty notification provider list"""
        response = NotificationProviderListResponse(providers=[], total=0)

        assert len(response.providers) == 0
        assert response.total == 0


class TestTestNotificationRequest:
    """Test TestNotificationRequest schema"""

    def test_valid_test_notification_request(self):
        """Test valid test notification request"""
        request = TestNotificationRequest(
            recipient="user@example.com",
            subject="Test Email",
            message="This is a test message",
        )

        assert request.recipient == "user@example.com"
        assert request.subject == "Test Email"
        assert request.message == "This is a test message"

    def test_test_notification_request_defaults(self):
        """Test test notification request default values"""
        request = TestNotificationRequest(recipient="+15551234567")

        assert request.subject == "Test Notification"
        assert request.message == "This is a test notification from OpenEye."


class TestTestNotificationResponse:
    """Test TestNotificationResponse schema"""

    def test_valid_test_notification_response_success(self):
        """Test valid test notification response (success)"""
        response = TestNotificationResponse(
            success=True,
            message="Notification sent successfully",
            error=None,
            delivery_time=1.23,
        )

        assert response.success is True
        assert response.message == "Notification sent successfully"
        assert response.error is None
        assert response.delivery_time == 1.23

    def test_valid_test_notification_response_failure(self):
        """Test valid test notification response (failure)"""
        response = TestNotificationResponse(
            success=False,
            message="Failed to send notification",
            error="SMTP connection timeout",
            delivery_time=None,
        )

        assert response.success is False
        assert response.message == "Failed to send notification"
        assert response.error == "SMTP connection timeout"
        assert response.delivery_time is None


class TestProviderTemplate:
    """Test ProviderTemplate schema"""

    def test_valid_provider_template(self):
        """Test valid provider template"""
        template = ProviderTemplate(
            provider_type="email",
            display_name="Email (SMTP)",
            description="Send notifications via email",
            icon="email",
            config_fields=[
                {"name": "smtp_host", "type": "text", "required": True},
                {"name": "smtp_port", "type": "number", "required": False},
            ],
        )

        assert template.provider_type == "email"
        assert template.display_name == "Email (SMTP)"
        assert template.description == "Send notifications via email"
        assert template.icon == "email"
        assert len(template.config_fields) == 2


class TestProviderTemplatesResponse:
    """Test ProviderTemplatesResponse schema"""

    def test_valid_provider_templates_response(self):
        """Test valid provider templates response"""
        templates = [
            ProviderTemplate(
                provider_type="email",
                display_name="Email",
                description="Email provider",
                icon="email",
                config_fields=[],
            ),
            ProviderTemplate(
                provider_type="sms",
                display_name="SMS",
                description="SMS provider",
                icon="sms",
                config_fields=[],
            ),
        ]

        response = ProviderTemplatesResponse(templates=templates)

        assert len(response.templates) == 2
        assert response.templates[0].provider_type == "email"
        assert response.templates[1].provider_type == "sms"
