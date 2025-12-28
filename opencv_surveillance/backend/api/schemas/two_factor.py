# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Two-Factor Authentication API Schemas
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class Enable2FAResponse(BaseModel):
    """Response when enabling 2FA"""
    secret: str = Field(..., description="TOTP secret key (save securely)")
    qr_code: str = Field(..., description="QR code as base64 data URI")
    backup_codes: List[str] = Field(..., description="10 backup codes for recovery")

    class Config:
        json_schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code": "data:image/png;base64,iVBORw0KGgo...",
                "backup_codes": [
                    "ABCD-1234-WXYZ",
                    "EFGH-5678-STUV",
                    "..."
                ]
            }
        }


class Verify2FARequest(BaseModel):
    """Request to verify and activate 2FA"""
    token: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP token")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "123456"
            }
        }


class Verify2FAResponse(BaseModel):
    """Response after verifying 2FA"""
    success: bool
    message: str
    two_factor_enabled: bool

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Two-factor authentication enabled successfully",
                "two_factor_enabled": True
            }
        }


class Disable2FARequest(BaseModel):
    """Request to disable 2FA"""
    password: str = Field(..., description="User's password for confirmation")

    class Config:
        json_schema_extra = {
            "example": {
                "password": "your-password"
            }
        }


class Disable2FAResponse(BaseModel):
    """Response after disabling 2FA"""
    success: bool
    message: str
    two_factor_enabled: bool

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Two-factor authentication disabled",
                "two_factor_enabled": False
            }
        }


class Login2FARequest(BaseModel):
    """Request to login with 2FA"""
    username: str
    password: str
    totp_token: Optional[str] = Field(None, min_length=6, max_length=6, description="6-digit TOTP token")
    backup_code: Optional[str] = Field(None, description="Backup code (alternative to TOTP)")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "your-password",
                "totp_token": "123456"
            }
        }


class Login2FAResponse(BaseModel):
    """Response after successful 2FA login"""
    access_token: str
    token_type: str = "bearer"
    requires_2fa: bool = Field(False, description="Whether 2FA token is required")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "requires_2fa": False
            }
        }


class TwoFactorStatus(BaseModel):
    """User's 2FA status"""
    two_factor_enabled: bool
    enrolled_at: Optional[datetime] = None
    backup_codes_remaining: Optional[int] = None

    class Config:
        json_schema_extra = {
            "example": {
                "two_factor_enabled": True,
                "enrolled_at": "2025-10-24T12:00:00",
                "backup_codes_remaining": 8
            }
        }
