# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Password Reset API Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class PasswordResetRequest(BaseModel):
    """Request to reset password with 2FA verification"""
    username: str = Field(..., min_length=1, description="Username to reset password for")
    totp_code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code from authenticator app")
    new_password: str = Field(..., min_length=4, description="New password (minimum 4 characters)")

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
