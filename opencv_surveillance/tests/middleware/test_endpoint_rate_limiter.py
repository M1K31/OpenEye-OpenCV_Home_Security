# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for per-endpoint rate limiting middleware
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, FastAPI
from fastapi.responses import JSONResponse

from backend.middleware.endpoint_rate_limiter import EndpointRateLimiter


class TestEndpointRateLimiterInit:
    """Test EndpointRateLimiter initialization"""

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def test_init_default_limits(self, mock_create_task):
        """Test initialization with default limits"""
        app = FastAPI()
        limiter = EndpointRateLimiter(app, enabled=True)

        assert limiter.limits == EndpointRateLimiter.DEFAULT_LIMITS
        assert "auth" in limiter.limits
        assert "password_reset" in limiter.limits
        assert "2fa_verify" in limiter.limits
        assert "write" in limiter.limits
        assert "read" in limiter.limits
        assert "stream" in limiter.limits
        assert "websocket" in limiter.limits

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def test_init_custom_limits(self, mock_create_task):
        """Test initialization with custom limits"""
        app = FastAPI()
        custom_limits = {
            "auth": (5, 30),  # Override default
            "custom": (100, 60),  # Add new category
        }

        limiter = EndpointRateLimiter(app, custom_limits=custom_limits, enabled=True)

        # Custom limits should override defaults
        assert limiter.limits["auth"] == (5, 30)
        assert limiter.limits["custom"] == (100, 60)

        # Defaults should still be present
        assert "read" in limiter.limits
        assert "write" in limiter.limits

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def test_init_cleanup_task_created(self, mock_create_task):
        """Test that cleanup task is created on initialization"""
        app = FastAPI()
        limiter = EndpointRateLimiter(app, cleanup_interval=120, enabled=True)

        assert limiter.cleanup_interval == 120
        mock_create_task.assert_called_once()


class TestGetEndpointCategory:
    """Test endpoint category determination"""

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def setup_method(self, method, mock_create_task):
        """Create limiter instance for tests"""
        app = FastAPI()
        self.limiter = EndpointRateLimiter(app, enabled=True)

    def test_auth_endpoint_login(self):
        """Test auth category for login endpoint"""
        category = self.limiter.get_endpoint_category("/api/auth/login", "POST")
        assert category == "auth"

    def test_auth_endpoint_token(self):
        """Test auth category for token endpoint"""
        category = self.limiter.get_endpoint_category("/api/token", "POST")
        assert category == "auth"

    def test_auth_endpoint_register(self):
        """Test auth category for register endpoint"""
        category = self.limiter.get_endpoint_category("/api/auth/register", "POST")
        assert category == "auth"

    def test_password_reset_endpoint(self):
        """Test password_reset category"""
        category = self.limiter.get_endpoint_category("/api/auth/reset-password", "POST")
        assert category == "password_reset"

    def test_2fa_verify_endpoint(self):
        """Test 2fa_verify category"""
        category = self.limiter.get_endpoint_category("/api/auth/2fa/verify", "POST")
        assert category == "2fa_verify"

    def test_stream_camera_endpoint(self):
        """Test stream category for camera stream"""
        category = self.limiter.get_endpoint_category("/api/cameras/cam1/stream", "GET")
        assert category == "stream"

    def test_stream_recording_download(self):
        """Test stream category for recording download"""
        category = self.limiter.get_endpoint_category("/api/recordings/123/download", "GET")
        assert category == "stream"

    def test_stream_recording_stream(self):
        """Test stream category for recording stream"""
        category = self.limiter.get_endpoint_category("/api/recordings/456/stream", "GET")
        assert category == "stream"

    def test_legacy_recordings_are_static(self):
        """
        Legacy recording files are served as static media, which is exempt from rate
        limiting rather than merely generous ("stream").

        Media is fetched with HTTP range requests, so a single video can issue many
        requests while seeking — and a page of snapshots issues dozens at once. Under
        the API read limit that produced cascades of broken images/video, so static
        file paths and media suffixes short-circuit to the exempt "static" category.
        """
        category = self.limiter.get_endpoint_category("/recordings/video.mp4", "GET")
        assert category == "static"

    def test_websocket_endpoint(self):
        """Test websocket category"""
        category = self.limiter.get_endpoint_category("/ws/statistics", "GET")
        assert category == "websocket"

    def test_write_endpoint_post(self):
        """Test write category for POST method"""
        category = self.limiter.get_endpoint_category("/api/cameras/", "POST")
        assert category == "write"

    def test_write_endpoint_put(self):
        """Test write category for PUT method"""
        category = self.limiter.get_endpoint_category("/api/alerts/123/", "PUT")
        assert category == "write"

    def test_write_endpoint_delete(self):
        """Test write category for DELETE method"""
        category = self.limiter.get_endpoint_category("/api/faces/john/", "DELETE")
        assert category == "write"

    def test_write_endpoint_patch(self):
        """Test write category for PATCH method"""
        category = self.limiter.get_endpoint_category("/api/cameras/cam1/", "PATCH")
        assert category == "write"

    def test_read_endpoint_get(self):
        """Test read category for GET method (default)"""
        category = self.limiter.get_endpoint_category("/api/cameras/", "GET")
        assert category == "read"

    def test_read_endpoint_options(self):
        """Test read category for OPTIONS method"""
        category = self.limiter.get_endpoint_category("/api/cameras/", "OPTIONS")
        assert category == "read"


@pytest.mark.asyncio
class TestDispatch:
    """Test rate limiting dispatch logic"""

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def setup_method(self, method, mock_create_task):
        """Create limiter instance for tests"""
        app = FastAPI()
        self.limiter = EndpointRateLimiter(
            app,
            enabled=True,
            custom_limits={
                "auth": (3, 60),  # Only 3 requests per minute for testing
                "read": (5, 60),  # 5 requests per minute for read
            }
        )

    async def test_dispatch_within_limit(self):
        """Test request within rate limit is allowed"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "GET"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make request
        response = await self.limiter.dispatch(mock_request, call_next)

        # Request should be allowed
        call_next.assert_called_once_with(mock_request)
        assert response == mock_response

        # Check rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Category" in response.headers
        assert response.headers["X-RateLimit-Category"] == "read"

    async def test_dispatch_exceeds_limit(self):
        """Test request exceeding rate limit is blocked"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.101"
        mock_request.url.path = "/api/auth/login"
        mock_request.method = "POST"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make requests up to limit (3 for auth category)
        for i in range(3):
            await self.limiter.dispatch(mock_request, call_next)

        # Fourth request should be blocked.
        # The limiter RETURNS a 429 response rather than raising HTTPException:
        # an exception raised inside a BaseHTTPMiddleware is not handled by FastAPI's
        # exception handlers, so it surfaced to clients as a 500 instead of a 429.
        blocked = await self.limiter.dispatch(mock_request, call_next)

        assert blocked.status_code == 429
        assert b"Rate limit exceeded" in blocked.body
        assert "Retry-After" in blocked.headers

    async def test_dispatch_different_clients_separate_limits(self):
        """Test that different clients have separate rate limits"""
        # Create two requests from different IPs
        mock_request1 = MagicMock(spec=Request)
        mock_request1.client.host = "192.168.1.100"
        mock_request1.url.path = "/api/auth/login"
        mock_request1.method = "POST"

        mock_request2 = MagicMock(spec=Request)
        mock_request2.client.host = "192.168.1.101"
        mock_request2.url.path = "/api/auth/login"
        mock_request2.method = "POST"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Client 1 makes 3 requests (reaches limit)
        for i in range(3):
            await self.limiter.dispatch(mock_request1, call_next)

        # Client 1 blocked
        blocked = await self.limiter.dispatch(mock_request1, call_next)
        assert blocked.status_code == 429

        # But Client 2 should still be allowed
        response = await self.limiter.dispatch(mock_request2, call_next)
        assert response == mock_response

    async def test_dispatch_different_categories_separate_limits(self):
        """Test that different categories have separate rate limits"""
        # Mock request for auth (limit: 3)
        mock_auth_request = MagicMock(spec=Request)
        mock_auth_request.client.host = "192.168.1.100"
        mock_auth_request.url.path = "/api/auth/login"
        mock_auth_request.method = "POST"

        # Mock request for read (limit: 5)
        mock_read_request = MagicMock(spec=Request)
        mock_read_request.client.host = "192.168.1.100"  # Same IP
        mock_read_request.url.path = "/api/cameras/"
        mock_read_request.method = "GET"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make 3 auth requests (reaches limit)
        for i in range(3):
            await self.limiter.dispatch(mock_auth_request, call_next)

        # Auth category blocked
        blocked = await self.limiter.dispatch(mock_auth_request, call_next)
        assert blocked.status_code == 429

        # But read category should still work (separate counter)
        response = await self.limiter.dispatch(mock_read_request, call_next)
        assert response == mock_response

    async def test_dispatch_websocket_unlimited(self):
        """Test that websocket endpoints are not rate limited"""
        # Mock websocket request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.url.path = "/ws/statistics"
        mock_request.method = "GET"

        # Mock call_next
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # Should be able to make many websocket requests
        for i in range(100):
            response = await self.limiter.dispatch(mock_request, call_next)
            assert response == mock_response

    async def test_dispatch_old_requests_cleaned(self):
        """Test that old requests are cleaned from the window"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.url.path = "/api/auth/login"
        mock_request.method = "POST"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make requests up to limit
        for i in range(3):
            await self.limiter.dispatch(mock_request, call_next)

        # Should be blocked now (at limit)
        blocked = await self.limiter.dispatch(mock_request, call_next)
        assert blocked.status_code == 429

        # Manually replace one recent timestamp with an old one (beyond window)
        tracking_key = ("192.168.1.100", "auth")
        old_time = time.time() - 61  # 61 seconds ago (window is 60 seconds)
        self.limiter.request_counts[tracking_key][0] = old_time

        # Make a new request - old timestamp should be cleaned, allowing this request
        response = await self.limiter.dispatch(mock_request, call_next)
        assert response == mock_response

        # Verify old timestamp was removed (all remaining timestamps should be recent)
        assert all(
            time.time() - t < 60
            for t in self.limiter.request_counts[tracking_key]
        )

    async def test_dispatch_rate_limit_headers(self):
        """Test that rate limit headers are set correctly"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"
        mock_request.url.path = "/api/cameras/"
        mock_request.method = "GET"

        # Mock call_next
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make first request
        response = await self.limiter.dispatch(mock_request, call_next)

        assert response.headers["X-RateLimit-Limit"] == "5"  # Custom limit
        assert response.headers["X-RateLimit-Remaining"] == "4"  # 5 - 1
        assert response.headers["X-RateLimit-Category"] == "read"


@pytest.mark.asyncio
class TestCleanupOldRequests:
    """Test periodic cleanup of old request records"""

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    @patch("backend.middleware.endpoint_rate_limiter.asyncio.sleep")
    async def test_cleanup_removes_old_entries(self, mock_sleep, mock_create_task):
        """Test that cleanup removes old request entries"""
        # Create limiter
        app = FastAPI()
        limiter = EndpointRateLimiter(app, cleanup_interval=30, enabled=True)

        # Add some old and new entries
        now = time.time()
        limiter.request_counts[("192.168.1.100", "read")] = [
            now - 120,  # Old (outside window)
            now - 10,   # Recent
            now - 5,    # Recent
        ]
        limiter.request_counts[("192.168.1.101", "write")] = [
            now - 150,  # Old (outside window)
        ]
        limiter.request_counts[("192.168.1.102", "auth")] = [
            now - 5,    # Recent
        ]

        # Mock sleep to run cleanup once
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        # Run cleanup
        try:
            await limiter.cleanup_old_requests()
        except asyncio.CancelledError:
            pass

        # Check that old entries were cleaned
        assert len(limiter.request_counts[("192.168.1.100", "read")]) == 2
        assert ("192.168.1.101", "write") not in limiter.request_counts  # Removed empty entry
        assert len(limiter.request_counts[("192.168.1.102", "auth")]) == 1

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    @patch("backend.middleware.endpoint_rate_limiter.asyncio.sleep")
    async def test_cleanup_runs_periodically(self, mock_sleep, mock_create_task):
        """Test that cleanup runs at the specified interval"""
        # Create limiter
        app = FastAPI()
        limiter = EndpointRateLimiter(app, cleanup_interval=60, enabled=True)

        # Mock sleep to run 3 times then cancel
        mock_sleep.side_effect = [None, None, None, asyncio.CancelledError()]

        # Run cleanup
        try:
            await limiter.cleanup_old_requests()
        except asyncio.CancelledError:
            pass

        # Should have slept 3 times with cleanup_interval
        assert mock_sleep.call_count == 4  # 3 successful + 1 cancelled
        for call in mock_sleep.call_args_list[:3]:
            assert call[0][0] == 60  # cleanup_interval


class TestEndpointPatterns:
    """Test endpoint pattern matching edge cases"""

    @patch("backend.middleware.endpoint_rate_limiter.asyncio.create_task")
    def setup_method(self, method, mock_create_task):
        """Create limiter instance for tests"""
        app = FastAPI()
        self.limiter = EndpointRateLimiter(app, enabled=True)

    def test_pattern_precedence_password_reset(self):
        """Test that more specific patterns take precedence"""
        # Password reset should match before general auth
        category = self.limiter.get_endpoint_category("/api/auth/reset-password", "POST")
        assert category == "password_reset"

        # But regular auth should still work
        category = self.limiter.get_endpoint_category("/api/auth/login", "POST")
        assert category == "auth"

    def test_pattern_case_sensitive(self):
        """Test that patterns are case-sensitive"""
        # Lowercase should match
        category = self.limiter.get_endpoint_category("/api/auth/login", "POST")
        assert category == "auth"

        # Uppercase should not match (falls back to method-based)
        category = self.limiter.get_endpoint_category("/API/AUTH/LOGIN", "POST")
        assert category == "write"  # POST defaults to write
