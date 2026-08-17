# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for authentication module
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException

from backend.core.auth import (
    create_access_token,
    authenticate_user,
    hash_password,
    get_current_user,
    get_current_active_user,
    require_role,
    create_tokens,
    refresh_access_token,
    SECRET_KEY,
    ALGORITHM,
)
from backend.api.schemas.user import User


class TestPasswordHashing:
    """Test password hashing functionality"""

    def test_hash_password_normal(self):
        """Test hashing a normal password"""
        password = "My_secure_password_123"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt hash format

    def test_hash_password_long_over_72_bytes(self):
        """Test hashing a password exceeding bcrypt's 72-byte limit"""
        # Create a password that's definitely over 72 bytes
        long_password = "a" * 100  # 100 characters = 100 bytes

        hashed = hash_password(long_password)

        assert hashed is not None
        assert isinstance(hashed, str)
        # Should not raise an exception - truncation happens transparently

    def test_hash_password_unicode(self):
        """Test hashing a password with unicode characters"""
        password = "Pāsswörd_with_ūnicode_🔒1"

        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)

    def test_hash_password_empty(self):
        """Test hashing an empty password"""
        password = ""

        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)

    def test_hash_password_consistency(self):
        """Test that same password produces different hashes (salt)"""
        password = "Test_password1"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Different hashes due to random salt
        assert hash1 != hash2


class TestAccessToken:
    """Test JWT access token creation"""

    def test_create_access_token_with_expiry(self):
        """Test creating access token with custom expiry"""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)

        token = create_access_token(data, expires_delta=expires_delta)

        assert token is not None
        assert isinstance(token, str)

        # Decode and verify
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_default_expiry(self):
        """Test creating access token with default 15-minute expiry"""
        data = {"sub": "testuser"}

        token = create_access_token(data)

        assert token is not None

        # Decode and verify default expiry
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

        # Check expiry is approximately 15 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = exp_time - now

        # Should be close to 15 minutes (allow 1 second tolerance)
        assert 14 * 60 < time_diff.total_seconds() < 16 * 60

    def test_create_access_token_additional_claims(self):
        """Test creating token with additional data claims"""
        data = {"sub": "testuser", "role": "admin", "email": "test@example.com"}

        token = create_access_token(data)

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["email"] == "test@example.com"


class TestAuthenticateUser:
    """Test user authentication"""

    @patch('backend.core.auth.crud.get_user_by_username')
    @patch('backend.core.auth.verify_password')
    def test_authenticate_user_success(self, mock_verify_password, mock_get_user):
        """Test successful user authentication"""
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_user.hashed_password = "hashed_password"

        mock_get_user.return_value = mock_user
        mock_verify_password.return_value = True

        result = authenticate_user(mock_db, "testuser", "correct_password")

        assert result == mock_user
        mock_get_user.assert_called_once_with(mock_db, username="testuser")
        mock_verify_password.assert_called_once_with("correct_password", "hashed_password")

    @patch('backend.core.auth.crud.get_user_by_username')
    def test_authenticate_user_invalid_username(self, mock_get_user):
        """Test authentication with non-existent username"""
        mock_db = MagicMock()
        mock_get_user.return_value = None

        result = authenticate_user(mock_db, "nonexistent", "password")

        assert result is False
        mock_get_user.assert_called_once_with(mock_db, username="nonexistent")

    @patch('backend.core.auth.crud.get_user_by_username')
    @patch('backend.core.auth.verify_password')
    def test_authenticate_user_invalid_password(self, mock_verify_password, mock_get_user):
        """Test authentication with incorrect password"""
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.hashed_password = "hashed_password"

        mock_get_user.return_value = mock_user
        mock_verify_password.return_value = False

        result = authenticate_user(mock_db, "testuser", "wrong_password")

        assert result is False
        mock_verify_password.assert_called_once_with("wrong_password", "hashed_password")


class TestGetCurrentUser:
    """Test get_current_user dependency"""

    @pytest.mark.asyncio
    @patch('backend.core.auth.crud.get_user_by_username')
    async def test_get_current_user_valid_token(self, mock_get_user):
        """Test getting current user with valid token"""
        mock_db = MagicMock()
        mock_user = MagicMock(spec=User)
        mock_user.username = "testuser"
        mock_user.id = 1

        mock_get_user.return_value = mock_user

        # Create valid token
        token = create_access_token({"sub": "testuser"})

        result = await get_current_user(token=token, db=mock_db)

        assert result == mock_user
        mock_get_user.assert_called_once_with(mock_db, username="testuser")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test get_current_user with malformed token"""
        mock_db = MagicMock()
        invalid_token = "invalid.token.here"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=invalid_token, db=mock_db)

        assert exc_info.value.status_code == 401
        assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub(self):
        """Test get_current_user with token missing 'sub' claim"""
        mock_db = MagicMock()

        # Create token without 'sub' claim
        token = jwt.encode({"user": "testuser"}, SECRET_KEY, algorithm=ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch('backend.core.auth.crud.get_user_by_username')
    async def test_get_current_user_user_not_found(self, mock_get_user):
        """Test get_current_user when user doesn't exist in database"""
        mock_db = MagicMock()
        mock_get_user.return_value = None

        token = create_access_token({"sub": "nonexistent_user"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=mock_db)

        assert exc_info.value.status_code == 401
        mock_get_user.assert_called_once_with(mock_db, username="nonexistent_user")

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test get_current_user with expired token"""
        mock_db = MagicMock()

        # Create expired token (expired 1 hour ago)
        expired_token = create_access_token(
            {"sub": "testuser"},
            expires_delta=timedelta(hours=-1)
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=expired_token, db=mock_db)

        assert exc_info.value.status_code == 401


class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency"""

    @pytest.mark.asyncio
    async def test_get_current_active_user_active(self):
        """Test with active user"""
        mock_user = MagicMock(spec=User)
        mock_user.is_active = True
        mock_user.username = "active_user"

        result = await get_current_active_user(current_user=mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_current_active_user_inactive(self):
        """Test with inactive user"""
        mock_user = MagicMock(spec=User)
        mock_user.is_active = False
        mock_user.username = "inactive_user"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user=mock_user)

        assert exc_info.value.status_code == 400
        assert "Inactive user" in exc_info.value.detail


class TestRequireRole:
    """Test role-based access control"""

    @pytest.mark.asyncio
    async def test_require_role_allowed(self):
        """Test role checker with allowed role"""
        mock_user = MagicMock(spec=User)
        mock_user.role = "admin"
        mock_user.is_active = True

        role_checker = require_role(["admin", "moderator"])
        result = await role_checker(current_user=mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_require_role_forbidden(self):
        """Test role checker with forbidden role"""
        mock_user = MagicMock(spec=User)
        mock_user.role = "viewer"
        mock_user.is_active = True

        role_checker = require_role(["admin"])

        with pytest.raises(HTTPException) as exc_info:
            await role_checker(current_user=mock_user)

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        assert "admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_multiple_allowed(self):
        """Test role checker with multiple allowed roles"""
        mock_user = MagicMock(spec=User)
        mock_user.role = "user"
        mock_user.is_active = True

        role_checker = require_role(["admin", "user", "moderator"])
        result = await role_checker(current_user=mock_user)

        assert result == mock_user


class TestCreateTokens:
    """Test token pair creation"""

    @patch('backend.core.auth.crud.create_refresh_token')
    def test_create_tokens_success(self, mock_create_refresh_token):
        """Test creating access and refresh token pair"""
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"

        tokens = create_tokens(
            db=mock_db,
            user=mock_user,
            device_info="Mozilla/5.0",
            ip_address="192.168.1.100"
        )

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert "expires_in" in tokens

        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 30 * 60  # 30 minutes in seconds

        # Verify access token is valid JWT
        payload = jwt.decode(tokens["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"

        # Verify refresh token was stored in database
        mock_create_refresh_token.assert_called_once()
        call_args = mock_create_refresh_token.call_args[1]
        assert call_args["user_id"] == 1
        assert call_args["device_info"] == "Mozilla/5.0"
        assert call_args["ip_address"] == "192.168.1.100"

    @patch('backend.core.auth.crud.create_refresh_token')
    def test_create_tokens_without_device_info(self, mock_create_refresh_token):
        """Test creating tokens without device info"""
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"

        tokens = create_tokens(db=mock_db, user=mock_user)

        assert tokens is not None
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Verify device_info is None
        call_args = mock_create_refresh_token.call_args[1]
        assert call_args["device_info"] is None
        assert call_args["ip_address"] is None


class TestRefreshAccessToken:
    """Test refresh token functionality"""

    @patch('backend.core.auth.crud.get_user')
    @patch('backend.core.auth.crud.get_refresh_token')
    @patch('backend.core.auth.crud.create_refresh_token')
    def test_refresh_access_token_success(
        self,
        mock_create_refresh_token,
        mock_get_refresh_token,
        mock_get_user
    ):
        """Test successful token refresh"""
        mock_db = MagicMock()

        # Mock refresh token record
        mock_token_record = MagicMock()
        mock_token_record.user_id = 1
        mock_token_record.revoked = False
        mock_token_record.expires_at = datetime.utcnow() + timedelta(days=1)

        # Mock user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.is_active = True

        mock_get_refresh_token.return_value = mock_token_record
        mock_get_user.return_value = mock_user

        tokens = refresh_access_token(
            db=mock_db,
            refresh_token="valid_refresh_token",
            device_info="Mozilla/5.0",
            ip_address="192.168.1.100"
        )

        # Verify old token was revoked
        assert mock_token_record.revoked is True
        mock_db.commit.assert_called()

        # Verify new tokens were created
        assert "access_token" in tokens
        assert "refresh_token" in tokens

    @patch('backend.core.auth.crud.get_refresh_token')
    def test_refresh_access_token_invalid_token(self, mock_get_refresh_token):
        """Test refresh with invalid token"""
        mock_db = MagicMock()
        mock_get_refresh_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(mock_db, "invalid_token")

        assert exc_info.value.status_code == 401
        assert "Invalid refresh token" in exc_info.value.detail

    @patch('backend.core.auth.crud.get_refresh_token')
    def test_refresh_access_token_revoked(self, mock_get_refresh_token):
        """Test refresh with revoked token"""
        mock_db = MagicMock()

        mock_token_record = MagicMock()
        mock_token_record.revoked = True
        mock_get_refresh_token.return_value = mock_token_record

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(mock_db, "revoked_token")

        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail

    @patch('backend.core.auth.crud.get_refresh_token')
    def test_refresh_access_token_expired(self, mock_get_refresh_token):
        """Test refresh with expired token"""
        mock_db = MagicMock()

        mock_token_record = MagicMock()
        mock_token_record.revoked = False
        mock_token_record.expires_at = datetime.utcnow() - timedelta(days=1)
        mock_get_refresh_token.return_value = mock_token_record

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(mock_db, "expired_token")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail

    @patch('backend.core.auth.crud.get_user')
    @patch('backend.core.auth.crud.get_refresh_token')
    def test_refresh_access_token_user_not_found(
        self,
        mock_get_refresh_token,
        mock_get_user
    ):
        """Test refresh when user doesn't exist"""
        mock_db = MagicMock()

        mock_token_record = MagicMock()
        mock_token_record.user_id = 999
        mock_token_record.revoked = False
        mock_token_record.expires_at = datetime.utcnow() + timedelta(days=1)

        mock_get_refresh_token.return_value = mock_token_record
        mock_get_user.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(mock_db, "token")

        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail

    @patch('backend.core.auth.crud.get_user')
    @patch('backend.core.auth.crud.get_refresh_token')
    def test_refresh_access_token_inactive_user(
        self,
        mock_get_refresh_token,
        mock_get_user
    ):
        """Test refresh when user is inactive"""
        mock_db = MagicMock()

        mock_token_record = MagicMock()
        mock_token_record.user_id = 1
        mock_token_record.revoked = False
        mock_token_record.expires_at = datetime.utcnow() + timedelta(days=1)

        mock_user = MagicMock()
        mock_user.is_active = False

        mock_get_refresh_token.return_value = mock_token_record
        mock_get_user.return_value = mock_user

        with pytest.raises(HTTPException) as exc_info:
            refresh_access_token(mock_db, "token")

        assert exc_info.value.status_code == 401
        assert "disabled" in exc_info.value.detail
