# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for password reset API schemas
"""

import pytest
from pydantic import ValidationError

from backend.core.password_policy import password_failures
from backend.api.schemas.password_reset import (
    PasswordResetRequest,
    Check2FAStatusRequest,
    Check2FAStatusResponse,
    PasswordResetResponse,
)


class TestPasswordResetRequest:
    """Test PasswordResetRequest schema"""

    def test_valid_password_reset_request(self):
        """Test valid password reset request"""
        request = PasswordResetRequest(
            username="admin",
            totp_code="123456",
            new_password="Newpassword123!",
        )

        assert request.username == "admin"
        assert request.totp_code == "123456"
        assert request.new_password == "Newpassword123!"

    def test_totp_code_must_be_numeric(self):
        """Test that TOTP code must be numeric"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="ABC123",  # Contains non-numeric characters
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("totp_code",)
        assert "TOTP code must be numeric" in errors[0]["msg"]

    def test_totp_code_with_special_characters(self):
        """Test TOTP code with special characters is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="12-456",  # Contains dash
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "TOTP code must be numeric" in errors[0]["msg"]

    def test_totp_code_length_validation(self):
        """Test TOTP code must be exactly 6 digits"""
        # Too short
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="12345",  # Only 5 digits
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("totp_code",)

        # Too long
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="1234567",  # 7 digits
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("totp_code",)

    def test_username_required(self):
        """Test username field is required"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                totp_code="123456",
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_username_min_length(self):
        """Test username must have minimum length of 1"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="",  # Empty string
                totp_code="123456",
                new_password="Newpassword123!",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_new_password_required(self):
        """Test new_password field is required"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="123456",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("new_password",) for error in errors)

    def test_short_password_is_rejected(self):
        """A password under the configured minimum is refused."""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetRequest(
                username="admin",
                totp_code="123456",
                new_password="Ab1!",
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("new_password",) for error in errors)

    def test_reset_enforces_the_same_policy_as_every_other_path(self):
        """
        The reason this file exists in its current form.

        This schema used to carry min_length=4 and no character rules, so
        POST /auth/reset-password would set a four-character password that
        POST /users/{id}/password refused at eight. The test that lived here
        asserted "1234" was valid, which is how the gap survived: it was
        written down as intended behaviour.

        The floor now comes from password_policy, which reads it from
        configuration, so tightening the configuration tightens this path too.
        """
        weak = "1234"
        assert password_failures(weak), "test premise: this must violate the policy"

        with pytest.raises(ValidationError):
            PasswordResetRequest(
                username="admin", totp_code="123456", new_password=weak)

        ok = "Str0ng!Passw0rd"
        assert not password_failures(ok)
        request = PasswordResetRequest(
            username="admin", totp_code="123456", new_password=ok)
        assert request.new_password == ok

    def test_totp_code_all_zeros(self):
        """Test TOTP code with all zeros (valid numeric)"""
        request = PasswordResetRequest(
            username="admin",
            totp_code="000000",
            new_password="Newpassword1!",
        )

        assert request.totp_code == "000000"


class TestCheck2FAStatusRequest:
    """Test Check2FAStatusRequest schema"""

    def test_valid_check_2fa_status_request(self):
        """Test valid 2FA status check request"""
        request = Check2FAStatusRequest(username="admin")

        assert request.username == "admin"

    def test_username_required(self):
        """Test username field is required"""
        with pytest.raises(ValidationError) as exc_info:
            Check2FAStatusRequest()

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_username_min_length(self):
        """Test username must have minimum length of 1"""
        with pytest.raises(ValidationError) as exc_info:
            Check2FAStatusRequest(username="")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("username",) for error in errors)

    def test_valid_with_long_username(self):
        """Test valid request with long username"""
        long_username = "a" * 100
        request = Check2FAStatusRequest(username=long_username)

        assert request.username == long_username


class TestCheck2FAStatusResponse:
    """Test Check2FAStatusResponse schema"""

    def test_valid_check_2fa_status_response(self):
        """Test valid 2FA status response"""
        response = Check2FAStatusResponse(
            username="admin",
            two_factor_enabled=True,
            message="2FA is enabled for this user",
        )

        assert response.username == "admin"
        assert response.two_factor_enabled is True
        assert response.message == "2FA is enabled for this user"

    def test_two_factor_disabled(self):
        """Test response with 2FA disabled"""
        response = Check2FAStatusResponse(
            username="user1",
            two_factor_enabled=False,
            message="2FA is not enabled",
        )

        assert response.username == "user1"
        assert response.two_factor_enabled is False
        assert response.message == "2FA is not enabled"

    def test_all_fields_required(self):
        """Test that all fields are required"""
        with pytest.raises(ValidationError) as exc_info:
            Check2FAStatusResponse()

        errors = exc_info.value.errors()
        assert len(errors) == 3  # username, two_factor_enabled, message
        field_names = {error["loc"][0] for error in errors}
        assert "username" in field_names
        assert "two_factor_enabled" in field_names
        assert "message" in field_names


class TestPasswordResetResponse:
    """Test PasswordResetResponse schema"""

    def test_valid_password_reset_response_success(self):
        """Test valid password reset response (success)"""
        response = PasswordResetResponse(
            success=True,
            message="Password reset successfully",
        )

        assert response.success is True
        assert response.message == "Password reset successfully"

    def test_valid_password_reset_response_failure(self):
        """Test valid password reset response (failure)"""
        response = PasswordResetResponse(
            success=False,
            message="Invalid TOTP code",
        )

        assert response.success is False
        assert response.message == "Invalid TOTP code"

    def test_all_fields_required(self):
        """Test that all fields are required"""
        with pytest.raises(ValidationError) as exc_info:
            PasswordResetResponse()

        errors = exc_info.value.errors()
        assert len(errors) == 2  # success, message
        field_names = {error["loc"][0] for error in errors}
        assert "success" in field_names
        assert "message" in field_names

    def test_empty_message_allowed(self):
        """Test that empty message string is allowed"""
        response = PasswordResetResponse(
            success=True,
            message="",
        )

        assert response.success is True
        assert response.message == ""
