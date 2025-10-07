"""
Copyright (c) 2025 Mikel Smart
This file is part of OpenEye-OpenCV_Home_Security

First-run setup endpoints for admin account creation.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, validator
from backend.database.session import get_db
from backend.database.models import User
from backend.core.auth import hash_password
import re

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupInitializeRequest(BaseModel):
    """Request model for initializing admin account."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)  # No character limit, but we validate bytes

    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password meets security requirements."""
        errors = []
        
        if len(v) < 8:
            errors.append("Password must be at least 8 characters long")
        
        # Check byte length for bcrypt (72-byte limit)
        password_bytes = len(v.encode('utf-8'))
        if password_bytes > 72:
            errors.append(f"Password is too long ({password_bytes} bytes). Maximum is 72 bytes. Try using fewer special characters.")
        
        if not re.search(r'[A-Z]', v):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'[a-z]', v):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'\d', v):
            errors.append("Password must contain at least one number")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            errors.append("Password must contain at least one special character")
        
        if errors:
            raise ValueError(", ".join(errors))
        
        return v


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
        
        return {
            "setup_complete": admin_user is not None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check setup status: {str(e)}"
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
                detail="Setup has already been completed. Admin user exists."
            )
        
        # Check if username is taken
        existing_user = db.query(User).filter(User.username == request.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken"
            )
        
        # Check if email is taken
        existing_email = db.query(User).filter(User.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )
        
        # Create admin user
        hashed_pw = hash_password(request.password)
        admin_user = User(
            username=request.username,
            email=request.email,
            password=hashed_pw,
            role="admin",
            is_active=True
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
                "role": admin_user.role
            }
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        # Password validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize setup: {str(e)}"
        )
