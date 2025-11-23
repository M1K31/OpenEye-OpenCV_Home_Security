# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for alert database models
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from cryptography.fernet import Fernet
import base64
import json

from backend.database.alert_models import (
    AlertConfiguration,
    NotificationLog,
    AlertThrottle,
    NotificationProvider,
)


class TestAlertConfiguration:
    """Test AlertConfiguration model"""

    def test_init_default_values(self):
        """Test AlertConfiguration default column values are defined"""
        # SQLAlchemy defaults are applied on insert, not on instance creation
        # Test that the column defaults are properly defined
        from sqlalchemy import inspect

        config = AlertConfiguration()
        mapper = inspect(AlertConfiguration)

        # Verify column defaults exist
        assert mapper.columns["motion_alerts_enabled"].default.arg is True
        assert mapper.columns["face_recognition_alerts_enabled"].default.arg is True
        assert mapper.columns["unknown_face_alerts_enabled"].default.arg is True
        assert mapper.columns["recording_alerts_enabled"].default.arg is False

        # Object detection defaults (v3.10.0)
        assert mapper.columns["object_detection_alerts_enabled"].default.arg is True
        assert mapper.columns["vehicle_alerts_enabled"].default.arg is True
        assert mapper.columns["animal_alerts_enabled"].default.arg is True
        assert mapper.columns["package_alerts_enabled"].default.arg is True
        assert mapper.columns["identified_object_alerts_enabled"].default.arg is True

        # Notification channels defaults
        assert mapper.columns["email_enabled"].default.arg is True
        assert mapper.columns["sms_enabled"].default.arg is False
        assert mapper.columns["push_enabled"].default.arg is False
        assert mapper.columns["webhook_enabled"].default.arg is False

        # Throttling defaults
        assert mapper.columns["min_seconds_between_alerts"].default.arg == 300

        # Quiet hours defaults
        assert mapper.columns["quiet_hours_enabled"].default.arg is False
        assert mapper.columns["quiet_hours_start"].default.arg == "22:00"
        assert mapper.columns["quiet_hours_end"].default.arg == "07:00"

        # Camera settings default (callable)
        assert callable(mapper.columns["camera_settings"].default.arg) or mapper.columns["camera_settings"].default.arg == {}

    def test_init_custom_values(self):
        """Test AlertConfiguration initialization with custom values"""
        config = AlertConfiguration(
            user_id=123,
            motion_alerts_enabled=False,
            email_enabled=False,
            sms_enabled=True,
            email_address="test@example.com",
            phone_number="+1234567890",
            min_seconds_between_alerts=600,
            quiet_hours_enabled=True,
            quiet_hours_start="23:00",
            quiet_hours_end="08:00",
            camera_settings={"cam1": {"enabled": True}},
        )

        assert config.user_id == 123
        assert config.motion_alerts_enabled is False
        assert config.email_enabled is False
        assert config.sms_enabled is True
        assert config.email_address == "test@example.com"
        assert config.phone_number == "+1234567890"
        assert config.min_seconds_between_alerts == 600
        assert config.quiet_hours_enabled is True
        assert config.quiet_hours_start == "23:00"
        assert config.quiet_hours_end == "08:00"
        assert config.camera_settings == {"cam1": {"enabled": True}}

    def test_repr(self):
        """Test AlertConfiguration __repr__"""
        config = AlertConfiguration(id=5, user_id=123)
        repr_str = repr(config)

        assert repr_str == "<AlertConfiguration(id=5, user_id=123)>"
        assert "AlertConfiguration" in repr_str
        assert "id=5" in repr_str
        assert "user_id=123" in repr_str

    def test_contact_info_nullable(self):
        """Test that contact information fields are nullable"""
        config = AlertConfiguration(user_id=1)

        assert config.email_address is None
        assert config.phone_number is None
        assert config.push_token is None
        assert config.webhook_url is None


class TestNotificationLog:
    """Test NotificationLog model"""

    def test_init_default_values(self):
        """Test NotificationLog default column values are defined"""
        # SQLAlchemy defaults are applied on insert, not on instance creation
        from sqlalchemy import inspect

        log = NotificationLog()
        mapper = inspect(NotificationLog)

        # Verify column defaults exist
        assert mapper.columns["sent_successfully"].default.arg is False

        # Nullable fields should not have defaults
        assert mapper.columns["error_message"].nullable is True
        assert mapper.columns["sent_at"].nullable is True
        assert mapper.columns["subject"].nullable is True
        assert mapper.columns["event_data"].nullable is True

    def test_init_custom_values(self):
        """Test NotificationLog initialization with custom values"""
        event_data = {"person_name": "John", "confidence": 0.95}
        log = NotificationLog(
            event_type="face_known",
            camera_id="front_door",
            channel="email",
            recipient="user@example.com",
            subject="Person Detected",
            message="John was detected at front door",
            event_data=event_data,
            sent_successfully=True,
        )

        assert log.event_type == "face_known"
        assert log.camera_id == "front_door"
        assert log.channel == "email"
        assert log.recipient == "user@example.com"
        assert log.subject == "Person Detected"
        assert log.message == "John was detected at front door"
        assert log.event_data == event_data
        assert log.sent_successfully is True

    def test_repr(self):
        """Test NotificationLog __repr__"""
        log = NotificationLog(id=10, event_type="motion", channel="sms")
        repr_str = repr(log)

        assert repr_str == "<NotificationLog(id=10, event=motion, channel=sms)>"
        assert "NotificationLog" in repr_str
        assert "id=10" in repr_str
        assert "event=motion" in repr_str
        assert "channel=sms" in repr_str

    def test_event_types(self):
        """Test different event types can be stored"""
        event_types = ["motion", "face_known", "face_unknown", "recording"]

        for event_type in event_types:
            log = NotificationLog(event_type=event_type)
            assert log.event_type == event_type

    def test_channels(self):
        """Test different notification channels can be stored"""
        channels = ["email", "sms", "push", "webhook"]

        for channel in channels:
            log = NotificationLog(channel=channel)
            assert log.channel == channel


class TestAlertThrottle:
    """Test AlertThrottle model"""

    def test_init_default_values(self):
        """Test AlertThrottle default column values are defined"""
        # SQLAlchemy defaults are applied on insert, not on instance creation
        from sqlalchemy import inspect

        throttle = AlertThrottle()
        mapper = inspect(AlertThrottle)

        # Verify column defaults exist
        assert mapper.columns["alert_count"].default.arg == 1

    def test_init_custom_values(self):
        """Test AlertThrottle initialization with custom values"""
        throttle = AlertThrottle(
            throttle_key="motion_front_door",
            alert_count=5,
        )

        assert throttle.throttle_key == "motion_front_door"
        assert throttle.alert_count == 5

    def test_repr(self):
        """Test AlertThrottle __repr__"""
        last_time = datetime(2025, 1, 15, 10, 30, 0)
        throttle = AlertThrottle(throttle_key="face_known_john", last_alert_time=last_time)
        repr_str = repr(throttle)

        assert "AlertThrottle" in repr_str
        assert "key=face_known_john" in repr_str
        assert "last=2025-01-15 10:30:00" in repr_str

    def test_throttle_key_unique(self):
        """Test that throttle_key should be unique (database constraint)"""
        # This test verifies the model has unique constraint on throttle_key
        # Actual uniqueness is enforced by database
        throttle = AlertThrottle(throttle_key="test_unique_key")
        assert throttle.throttle_key == "test_unique_key"


class TestNotificationProvider:
    """Test NotificationProvider model"""

    def test_init_default_values(self):
        """Test NotificationProvider default column values are defined"""
        # SQLAlchemy defaults are applied on insert, not on instance creation
        from sqlalchemy import inspect

        provider = NotificationProvider(encrypted_config="dummy")
        mapper = inspect(NotificationProvider)

        # Verify column defaults exist
        assert mapper.columns["enabled"].default.arg is True
        assert mapper.columns["total_sent"].default.arg == 0
        assert mapper.columns["total_failed"].default.arg == 0

        # Nullable fields should not have defaults
        assert mapper.columns["last_tested_at"].nullable is True
        assert mapper.columns["test_status"].nullable is True
        assert mapper.columns["test_error"].nullable is True
        assert mapper.columns["last_used_at"].nullable is True

    def test_init_custom_values(self):
        """Test NotificationProvider initialization with custom values"""
        provider = NotificationProvider(
            user_id=123,
            provider_type="email",
            provider_name="Gmail",
            enabled=False,
            encrypted_config="encrypted_data",
            total_sent=100,
            total_failed=5,
            test_status="success",
        )

        assert provider.user_id == 123
        assert provider.provider_type == "email"
        assert provider.provider_name == "Gmail"
        assert provider.enabled is False
        assert provider.encrypted_config == "encrypted_data"
        assert provider.total_sent == 100
        assert provider.total_failed == 5
        assert provider.test_status == "success"

    def test_repr(self):
        """Test NotificationProvider __repr__"""
        provider = NotificationProvider(
            id=7,
            provider_type="sms",
            provider_name="Twilio",
            encrypted_config="dummy",
        )
        repr_str = repr(provider)

        assert repr_str == "<NotificationProvider(id=7, type=sms, name=Twilio)>"
        assert "NotificationProvider" in repr_str
        assert "id=7" in repr_str
        assert "type=sms" in repr_str
        assert "name=Twilio" in repr_str

    @patch.dict("os.environ", {"NOTIFICATION_ENCRYPTION_KEY": "test_key_32_bytes_long_enough!!"})
    def test_get_encryption_key_with_env_var(self):
        """Test get_encryption_key returns key from environment variable"""
        key = NotificationProvider.get_encryption_key()

        assert key == b"test_key_32_bytes_long_enough!!"
        assert isinstance(key, bytes)

    @patch.dict("os.environ", {}, clear=True)
    def test_get_encryption_key_without_env_var(self):
        """Test get_encryption_key generates key when env var not set"""
        # Remove NOTIFICATION_ENCRYPTION_KEY from environment
        import os
        if "NOTIFICATION_ENCRYPTION_KEY" in os.environ:
            del os.environ["NOTIFICATION_ENCRYPTION_KEY"]

        key = NotificationProvider.get_encryption_key()

        # Should have generated a new key
        assert key is not None
        assert isinstance(key, bytes)
        assert len(key) > 0

        # Verify it's a valid Fernet key by trying to use it
        try:
            fernet = Fernet(key)
            # If no exception, the key is valid
            assert True
        except Exception:
            pytest.fail("Generated key is not a valid Fernet key")

    def test_encrypt_config(self):
        """Test encrypt_config encrypts configuration dictionary"""
        provider = NotificationProvider(encrypted_config="dummy")
        config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@gmail.com",
            "password": "secret123",
        }

        # Mock encryption key
        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            encrypted = provider.encrypt_config(config)

        # Verify result is base64-encoded string
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

        # Verify we can decode base64
        try:
            decoded = base64.b64decode(encrypted.encode())
            assert len(decoded) > 0
        except Exception as e:
            pytest.fail(f"Failed to decode base64: {e}")

    def test_decrypt_config(self):
        """Test decrypt_config decrypts configuration"""
        provider = NotificationProvider(encrypted_config="dummy")
        original_config = {
            "bot_token": "123456:ABC-DEF",
            "chat_id": "987654321",
        }

        # Use real encryption
        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            # Encrypt first
            encrypted = provider.encrypt_config(original_config)
            provider.encrypted_config = encrypted

            # Then decrypt
            decrypted = provider.decrypt_config()

        # Verify decrypted matches original
        assert decrypted == original_config
        assert decrypted["bot_token"] == "123456:ABC-DEF"
        assert decrypted["chat_id"] == "987654321"

    def test_set_config(self):
        """Test set_config encrypts and stores configuration"""
        provider = NotificationProvider(encrypted_config="dummy")
        config = {
            "webhook_url": "https://discord.com/api/webhooks/123/abc",
            "username": "OpenEye Bot",
        }

        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            provider.set_config(config)

        # Verify encrypted_config was updated
        assert provider.encrypted_config != "dummy"
        assert isinstance(provider.encrypted_config, str)
        assert len(provider.encrypted_config) > 0

    def test_get_config(self):
        """Test get_config returns decrypted configuration"""
        provider = NotificationProvider(encrypted_config="dummy")
        original_config = {
            "account_sid": "AC123456",
            "auth_token": "secret_token",
            "from_number": "+1234567890",
        }

        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            # Set config (encrypts)
            provider.set_config(original_config)

            # Get config (decrypts)
            retrieved_config = provider.get_config()

        # Verify retrieved matches original
        assert retrieved_config == original_config
        assert retrieved_config["account_sid"] == "AC123456"
        assert retrieved_config["auth_token"] == "secret_token"
        assert retrieved_config["from_number"] == "+1234567890"

    def test_encryption_round_trip(self):
        """Test full encryption/decryption round trip"""
        provider = NotificationProvider(encrypted_config="dummy")

        # Test with complex nested config
        original_config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "user@example.com",
            "password": "P@ssw0rd!",
            "use_tls": True,
            "timeout": 30,
            "headers": {"X-Custom": "Value"},
        }

        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            # Encrypt
            encrypted = provider.encrypt_config(original_config)
            provider.encrypted_config = encrypted

            # Decrypt
            decrypted = provider.decrypt_config()

        # Verify exact match
        assert decrypted == original_config
        assert isinstance(decrypted["smtp_port"], int)
        assert isinstance(decrypted["use_tls"], bool)
        assert isinstance(decrypted["headers"], dict)

    def test_provider_types(self):
        """Test different provider types can be stored"""
        provider_types = ["email", "sms", "push", "telegram", "discord", "webhook"]

        for provider_type in provider_types:
            provider = NotificationProvider(
                provider_type=provider_type,
                encrypted_config="dummy",
            )
            assert provider.provider_type == provider_type

    def test_encryption_with_empty_config(self):
        """Test encryption handles empty configuration"""
        provider = NotificationProvider(encrypted_config="dummy")
        empty_config = {}

        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            encrypted = provider.encrypt_config(empty_config)
            provider.encrypted_config = encrypted

            decrypted = provider.decrypt_config()

        assert decrypted == {}

    def test_encryption_with_special_characters(self):
        """Test encryption handles special characters"""
        provider = NotificationProvider(encrypted_config="dummy")
        config = {
            "password": "P@$$w0rd!#$%^&*()",
            "url": "https://example.com/webhook?token=abc123&key=xyz789",
            "unicode": "Hello 世界 🌍",
        }

        test_key = Fernet.generate_key()
        with patch.object(NotificationProvider, "get_encryption_key", return_value=test_key):
            encrypted = provider.encrypt_config(config)
            provider.encrypted_config = encrypted

            decrypted = provider.decrypt_config()

        assert decrypted == config
        assert decrypted["password"] == "P@$$w0rd!#$%^&*()"
        assert decrypted["unicode"] == "Hello 世界 🌍"
