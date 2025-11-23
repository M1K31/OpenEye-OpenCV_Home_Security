# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for CSRF protection middleware
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, FastAPI

from backend.middleware.csrf_protection import CSRFProtection


class TestCSRFProtectionInit:
    """Test CSRFProtection initialization"""

    def test_init_default_values(self):
        """Test initialization with default values"""
        app = FastAPI()
        csrf = CSRFProtection(app)

        assert csrf.token_length == 32
        assert csrf.cookie_name == "csrf_token"
        assert csrf.header_name == "X-CSRF-Token"
        assert csrf.token_lifetime == 3600
        assert csrf.valid_tokens == {}

    def test_init_custom_values(self):
        """Test initialization with custom values"""
        app = FastAPI()
        csrf = CSRFProtection(
            app,
            token_length=64,
            cookie_name="custom_csrf",
            header_name="X-Custom-CSRF",
            token_lifetime=7200
        )

        assert csrf.token_length == 64
        assert csrf.cookie_name == "custom_csrf"
        assert csrf.header_name == "X-Custom-CSRF"
        assert csrf.token_lifetime == 7200


class TestIsExempt:
    """Test is_exempt method"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    def test_exempt_token_endpoint(self):
        """Test that /api/token is exempt"""
        assert self.csrf.is_exempt("/api/token") is True

    def test_exempt_login_endpoint(self):
        """Test that /api/auth/login is exempt"""
        assert self.csrf.is_exempt("/api/auth/login") is True

    def test_exempt_register_endpoint(self):
        """Test that /api/auth/register is exempt"""
        assert self.csrf.is_exempt("/api/auth/register") is True

    def test_exempt_docs_endpoint(self):
        """Test that /api/docs is exempt"""
        assert self.csrf.is_exempt("/api/docs") is True

    def test_exempt_redoc_endpoint(self):
        """Test that /api/redoc is exempt"""
        assert self.csrf.is_exempt("/api/redoc") is True

    def test_exempt_openapi_endpoint(self):
        """Test that /api/openapi.json is exempt"""
        assert self.csrf.is_exempt("/api/openapi.json") is True

    def test_exempt_websocket_endpoint(self):
        """Test that /ws/ paths are exempt"""
        assert self.csrf.is_exempt("/ws/statistics") is True
        assert self.csrf.is_exempt("/ws/camera_feed") is True

    def test_not_exempt_regular_endpoint(self):
        """Test that regular endpoints are not exempt"""
        assert self.csrf.is_exempt("/api/cameras/") is False
        assert self.csrf.is_exempt("/api/faces/") is False
        assert self.csrf.is_exempt("/api/recordings/") is False

    def test_exempt_path_prefix_matching(self):
        """Test that exempt paths use prefix matching"""
        # /api/token should match /api/token and /api/token/refresh
        assert self.csrf.is_exempt("/api/token") is True
        assert self.csrf.is_exempt("/api/token/refresh") is True


class TestGenerateToken:
    """Test token generation"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    def test_generate_token_creates_token(self):
        """Test that generate_token creates a valid token"""
        token = self.csrf.generate_token()

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_stores_token(self):
        """Test that generated token is stored"""
        token = self.csrf.generate_token()

        assert token in self.csrf.valid_tokens
        assert isinstance(self.csrf.valid_tokens[token], float)

    def test_generate_token_unique(self):
        """Test that each generated token is unique"""
        token1 = self.csrf.generate_token()
        token2 = self.csrf.generate_token()

        assert token1 != token2
        assert token1 in self.csrf.valid_tokens
        assert token2 in self.csrf.valid_tokens

    def test_generate_token_timestamp(self):
        """Test that token has current timestamp"""
        before = time.time()
        token = self.csrf.generate_token()
        after = time.time()

        assert before <= self.csrf.valid_tokens[token] <= after


class TestValidateToken:
    """Test token validation"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    def test_validate_token_valid(self):
        """Test validating a valid token"""
        token = self.csrf.generate_token()

        assert self.csrf.validate_token(token) is True

    def test_validate_token_empty_string(self):
        """Test validating empty string returns False"""
        assert self.csrf.validate_token("") is False

    def test_validate_token_none(self):
        """Test validating None returns False"""
        assert self.csrf.validate_token(None) is False

    def test_validate_token_nonexistent(self):
        """Test validating nonexistent token returns False"""
        assert self.csrf.validate_token("nonexistent_token") is False

    def test_validate_token_expired(self):
        """Test that expired token is invalid"""
        token = self.csrf.generate_token()

        # Manually set timestamp to expired time
        self.csrf.valid_tokens[token] = time.time() - self.csrf.token_lifetime - 1

        assert self.csrf.validate_token(token) is False

    def test_validate_token_expired_removes_token(self):
        """Test that validating expired token removes it from storage"""
        token = self.csrf.generate_token()

        # Manually set timestamp to expired time
        self.csrf.valid_tokens[token] = time.time() - self.csrf.token_lifetime - 1

        self.csrf.validate_token(token)

        # Token should be removed
        assert token not in self.csrf.valid_tokens

    def test_validate_token_not_yet_expired(self):
        """Test that token just before expiration is still valid"""
        token = self.csrf.generate_token()

        # Set timestamp to just before expiration (1 second left)
        self.csrf.valid_tokens[token] = time.time() - self.csrf.token_lifetime + 1

        assert self.csrf.validate_token(token) is True


class TestCleanupExpiredTokens:
    """Test cleanup of expired tokens"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app, token_lifetime=60)

    def test_cleanup_removes_expired_tokens(self):
        """Test that cleanup removes expired tokens"""
        # Create some tokens
        token1 = self.csrf.generate_token()
        token2 = self.csrf.generate_token()
        token3 = self.csrf.generate_token()

        # Make token1 and token2 expired
        self.csrf.valid_tokens[token1] = time.time() - 61
        self.csrf.valid_tokens[token2] = time.time() - 61
        # token3 stays fresh

        self.csrf.cleanup_expired_tokens()

        assert token1 not in self.csrf.valid_tokens
        assert token2 not in self.csrf.valid_tokens
        assert token3 in self.csrf.valid_tokens

    def test_cleanup_keeps_valid_tokens(self):
        """Test that cleanup keeps non-expired tokens"""
        token = self.csrf.generate_token()

        self.csrf.cleanup_expired_tokens()

        assert token in self.csrf.valid_tokens

    def test_cleanup_empty_dict(self):
        """Test that cleanup works with empty token dict"""
        self.csrf.cleanup_expired_tokens()

        assert self.csrf.valid_tokens == {}


@pytest.mark.asyncio
class TestDispatchGetRequests:
    """Test dispatch for GET requests"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    async def test_dispatch_get_sets_cookie_if_missing(self):
        """Test that GET request sets CSRF cookie if missing"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "GET"
        mock_request.cookies = {}  # No cookie

        # Mock response
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        # Should set cookie
        mock_response.set_cookie.assert_called_once()
        call_args = mock_response.set_cookie.call_args
        assert call_args[1]["key"] == "csrf_token"
        assert call_args[1]["httponly"] is True
        assert call_args[1]["samesite"] == "strict"
        assert call_args[1]["secure"] is True

    async def test_dispatch_get_does_not_set_cookie_if_present(self):
        """Test that GET request doesn't set cookie if already present"""
        # Mock request with existing cookie
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "GET"
        mock_request.cookies = {"csrf_token": "existing_token"}

        # Mock response
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        # Should not set cookie
        mock_response.set_cookie.assert_not_called()


@pytest.mark.asyncio
class TestDispatchProtectedMethods:
    """Test dispatch for protected methods (POST, PUT, DELETE, PATCH)"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    async def test_dispatch_post_valid_token(self):
        """Test POST request with valid token"""
        # Generate a valid token
        token = self.csrf.generate_token()

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {"X-CSRF-Token": token}
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        # Should allow request
        call_next.assert_called_once_with(mock_request)
        assert response == mock_response

    async def test_dispatch_put_valid_token(self):
        """Test PUT request with valid token"""
        token = self.csrf.generate_token()

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/cam1/"
        mock_request.method = "PUT"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {"X-CSRF-Token": token}
        mock_request.client.host = "192.168.1.100"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        assert response == mock_response

    async def test_dispatch_delete_valid_token(self):
        """Test DELETE request with valid token"""
        token = self.csrf.generate_token()

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/cam1/"
        mock_request.method = "DELETE"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {"X-CSRF-Token": token}
        mock_request.client.host = "192.168.1.100"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        assert response == mock_response

    async def test_dispatch_patch_valid_token(self):
        """Test PATCH request with valid token"""
        token = self.csrf.generate_token()

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/cam1/"
        mock_request.method = "PATCH"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {"X-CSRF-Token": token}
        mock_request.client.host = "192.168.1.100"

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        assert response == mock_response

    async def test_dispatch_post_missing_cookie(self):
        """Test POST request with missing cookie token"""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {}  # No cookie
        mock_request.headers = {"X-CSRF-Token": "some_token"}
        mock_request.client.host = "192.168.1.100"

        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await self.csrf.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403
        # When cookie is missing but header exists, validation check fails
        assert "CSRF token" in exc_info.value.detail

    async def test_dispatch_post_missing_header(self):
        """Test POST request with missing header token"""
        token = self.csrf.generate_token()

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {}  # No header
        mock_request.client.host = "192.168.1.100"

        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await self.csrf.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403
        # When header is missing but cookie exists, CSRF check fails
        assert "CSRF token" in exc_info.value.detail

    async def test_dispatch_post_mismatched_tokens(self):
        """Test POST request with mismatched tokens"""
        token1 = self.csrf.generate_token()
        token2 = self.csrf.generate_token()

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {"csrf_token": token1}
        mock_request.headers = {"X-CSRF-Token": token2}  # Different token
        mock_request.client.host = "192.168.1.100"

        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await self.csrf.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403
        assert "validation failed" in exc_info.value.detail

    async def test_dispatch_post_invalid_token(self):
        """Test POST request with invalid/nonexistent token"""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {"csrf_token": "invalid_token"}
        mock_request.headers = {"X-CSRF-Token": "invalid_token"}
        mock_request.client.host = "192.168.1.100"

        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await self.csrf.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403
        assert "validation failed" in exc_info.value.detail

    async def test_dispatch_post_expired_token(self):
        """Test POST request with expired token"""
        token = self.csrf.generate_token()

        # Make token expired
        self.csrf.valid_tokens[token] = time.time() - self.csrf.token_lifetime - 1

        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "POST"
        mock_request.cookies = {"csrf_token": token}
        mock_request.headers = {"X-CSRF-Token": token}
        mock_request.client.host = "192.168.1.100"

        call_next = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await self.csrf.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
class TestDispatchExemptPaths:
    """Test dispatch for exempt paths"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app)

    async def test_dispatch_post_login_exempt(self):
        """Test that POST to /api/auth/login is exempt"""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/auth/login"
        mock_request.method = "POST"
        mock_request.cookies = {}
        mock_request.headers = {}

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        # Should allow without CSRF check
        call_next.assert_called_once_with(mock_request)
        assert response == mock_response

    async def test_dispatch_post_token_exempt(self):
        """Test that POST to /api/token is exempt"""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/token"
        mock_request.method = "POST"
        mock_request.cookies = {}
        mock_request.headers = {}

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        assert response == mock_response

    async def test_dispatch_post_register_exempt(self):
        """Test that POST to /api/auth/register is exempt"""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/auth/register"
        mock_request.method = "POST"
        mock_request.cookies = {}
        mock_request.headers = {}

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.csrf.dispatch(mock_request, call_next)

        assert response == mock_response


@pytest.mark.asyncio
class TestDispatchPeriodicCleanup:
    """Test periodic cleanup trigger"""

    def setup_method(self):
        """Create CSRF instance for tests"""
        app = FastAPI()
        self.csrf = CSRFProtection(app, token_lifetime=60)

    async def test_dispatch_triggers_cleanup_periodically(self):
        """Test that cleanup is triggered when token count is divisible by 100"""
        # Create exactly 100 tokens to trigger cleanup
        for i in range(100):
            self.csrf.generate_token()

        # Make half of them expired
        expired_tokens = list(self.csrf.valid_tokens.keys())[:50]
        for token in expired_tokens:
            self.csrf.valid_tokens[token] = time.time() - 61

        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "GET"
        mock_request.cookies = {"csrf_token": "existing"}

        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # This should trigger cleanup (len % 100 == 0)
        await self.csrf.dispatch(mock_request, call_next)

        # Expired tokens should be removed (50 expired out of 100)
        # So we should have 50 valid tokens remaining
        assert len(self.csrf.valid_tokens) == 50
