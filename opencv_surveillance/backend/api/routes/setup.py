"""
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security

First-run setup endpoints for admin account creation.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from backend.database.session import get_db
from backend.database.models import User
from backend.core.auth import hash_password
from backend.core.password_policy import validate_password

router = APIRouter(tags=["setup"])


class SetupInitializeRequest(BaseModel):
    """Request model for initializing admin account."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(...)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate against the configured policy.

        These rules used to be written out here as literals, which made this the
        only endpoint enforcing them and left MIN_PASSWORD_LENGTH and the
        REQUIRE_* settings inert. The rules themselves are unchanged; they now
        come from one place, so tightening the configuration tightens every
        password path rather than none of them.

        Long passwords are still accepted rather than rejected: hash_password()
        truncates at bcrypt's 72-byte limit deliberately, for the sake of
        passwords that "just work".
        """
        return validate_password(v)


@router.get("/status")
async def check_setup_status():
    """
    Check if initial setup has been completed.
    Returns setup_complete: true if admin user exists, false otherwise.
    """
    try:
        db = next(get_db())

        # Check if any admin user exists
        admin_user = db.query(User).filter(User.role == "admin").first()

        return {"setup_complete": admin_user is not None}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check setup status: {str(e)}",
        )


@router.post("/initialize")
async def initialize_setup(request: SetupInitializeRequest):
    """
    Initialize the system by creating the first admin user.
    Can only be called once - will fail if admin already exists.
    """
    try:
        db = next(get_db())

        # Check if admin already exists
        existing_admin = db.query(User).filter(User.role == "admin").first()
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Setup has already been completed. Admin user exists.",
            )

        # Check if username is taken
        existing_user = db.query(User).filter(
            User.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken",
            )

        # Check if email is taken
        existing_email = db.query(User).filter(
            User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered",
            )

        # Create admin user
        hashed_pw = hash_password(request.password)
        admin_user = User(
            username=request.username,
            email=request.email,
            hashed_password=hashed_pw,
            role="admin",
            is_active=True,
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        return {
            "success": True,
            "message": "Admin account created successfully",
            "user": {
                "id": admin_user.id,
                "username": admin_user.username,
                "email": admin_user.email,
                "role": admin_user.role,
            },
        }

    except HTTPException:
        raise
    except ValueError as e:
        # Password validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize setup: {str(e)}",
        )
