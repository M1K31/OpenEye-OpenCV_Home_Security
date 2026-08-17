# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Password Reset API Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional

from backend.core.password_policy import validate_password


class PasswordResetRequest(BaseModel):
    """Request to reset password with 2FA verification"""
    username: str = Field(..., min_length=1, description="Username to reset password for")
    totp_code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code from authenticator app")
    # The floor and the character rules both come from password_policy, which
    # reads them from configuration. This field previously carried its own
    # min_length=4, which let a reset set a password that POST
    # /users/{id}/password would have refused at 8.
    new_password: str = Field(..., description="New password")

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return validate_password(v)

    @field_validator('totp_code')
    @classmethod
    def validate_totp_code(cls, v):
        """Ensure TOTP code is numeric"""
        if not v.isdigit():
            raise ValueError('TOTP code must be numeric')
        return v


class Check2FAStatusRequest(BaseModel):
    """Request to check if user has 2FA enabled"""
    username: str = Field(..., min_length=1, description="Username to check 2FA status for")


class Check2FAStatusResponse(BaseModel):
    """Response with user's 2FA status"""
    username: str
    two_factor_enabled: bool
    message: str


class PasswordResetResponse(BaseModel):
    """Response after password reset"""
    success: bool
    message: str
