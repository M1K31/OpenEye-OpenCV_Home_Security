# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import json
import bcrypt

from backend.database import crud
from backend.database.session import SessionLocal
from backend.api.schemas import user as user_schema
from backend.api.schemas import two_factor as twofa_schema
from backend.core import auth
from backend.core.two_factor_auth import get_2fa_system
from backend.core.audit_logger import get_audit_logger, AuditEventType
from datetime import timedelta

router = APIRouter()
audit_logger = get_audit_logger()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/users/", response_model=user_schema.User)
def create_user(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered")
    return crud.create_user(db=db, user=user)


@router.post("/token")
def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Check if user has 2FA enabled
    if user.two_factor_enabled:
        # Return error indicating 2FA is required
        # Frontend should then prompt for TOTP token and call /auth/login-2fa
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Two-factor authentication required. Use /auth/login-2fa endpoint.",
            headers={"X-Requires-2FA": "true"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Log successful login
    audit_logger.log_login(user.username, "unknown", success=True)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/login-2fa", response_model=twofa_schema.Login2FAResponse)
def login_with_2fa(
    request: twofa_schema.Login2FARequest,
    db: Session = Depends(get_db)
):
    """
    Login with two-factor authentication

    Args:
    - username: Username
    - password: Password
    - totp_token: 6-digit TOTP token (OR)
    - backup_code: Backup recovery code

    Returns:
    - access_token: JWT access token
    - token_type: Bearer
    """
    # Authenticate username and password
    user = auth.authenticate_user(db, request.username, request.password)
    if not user:
        audit_logger.log_login(request.username, "unknown", success=False, reason="Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if 2FA is enabled
    if not user.two_factor_enabled:
        # User doesn't have 2FA - proceed with normal login
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        audit_logger.log_login(user.username, "unknown", success=True)
        return twofa_schema.Login2FAResponse(
            access_token=access_token,
            token_type="bearer",
            requires_2fa=False
        )

    # 2FA is enabled - verify TOTP token or backup code
    twofa = get_2fa_system()

    if request.totp_token:
        # Verify TOTP token
        is_valid = twofa.verify_token(user.totp_secret, request.totp_token)
        if not is_valid:
            audit_logger.log_login(request.username, "unknown", success=False, reason="Invalid 2FA token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP token"
            )

    elif request.backup_code:
        # Verify backup code
        if not user.backup_codes:
            audit_logger.log_login(request.username, "unknown", success=False, reason="No backup codes")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No backup codes available"
            )

        # Load backup codes
        try:
            backup_codes = json.loads(user.backup_codes)
        except:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error loading backup codes"
            )

        # Check if backup code matches any hashed code
        code_found = False
        for i, hashed_code in enumerate(backup_codes):
            if bcrypt.checkpw(request.backup_code.encode(), hashed_code.encode()):
                code_found = True
                # Remove used backup code
                backup_codes.pop(i)
                user.backup_codes = json.dumps(backup_codes)
                db.commit()
                break

        if not code_found:
            audit_logger.log_login(request.username, "unknown", success=False, reason="Invalid backup code")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid backup code"
            )

    else:
        # Neither TOTP token nor backup code provided
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either totp_token or backup_code must be provided"
        )

    # 2FA verified successfully - create token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    # Log successful 2FA login
    audit_logger.log_login(user.username, "unknown", success=True)

    return twofa_schema.Login2FAResponse(
        access_token=access_token,
        token_type="bearer",
        requires_2fa=False
    )


@router.get("/users/me", response_model=user_schema.User)
def read_users_me(
    current_user: user_schema.User = Depends(
        auth.get_current_user)):
    return current_user
