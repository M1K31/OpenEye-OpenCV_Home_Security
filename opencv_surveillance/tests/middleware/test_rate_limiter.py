# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for legacy global rate limiter middleware
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, FastAPI

from backend.middleware.rate_limiter import RateLimiter


class TestRateLimiterInit:
    """Test RateLimiter initialization"""

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    def test_init_default_limit(self, mock_create_task):
        """Test initialization with default limit"""
        app = FastAPI()
        limiter = RateLimiter(app)

        assert limiter.requests_per_minute == 60
        assert limiter.cleanup_interval == 60
        assert len(limiter.request_counts) == 0
        mock_create_task.assert_called_once()

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    def test_init_custom_limit(self, mock_create_task):
        """Test initialization with custom limit"""
        app = FastAPI()
        limiter = RateLimiter(app, requests_per_minute=100)

        assert limiter.requests_per_minute == 100
        assert limiter.cleanup_interval == 60
        mock_create_task.assert_called_once()


@pytest.mark.asyncio
class TestDispatch:
    """Test rate limiting dispatch logic"""

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    def setup_method(self, method, mock_create_task):
        """Create limiter instance for tests"""
        app = FastAPI()
        self.limiter = RateLimiter(app, requests_per_minute=5)

    async def test_dispatch_first_request(self):
        """Test first request is allowed"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make request
        response = await self.limiter.dispatch(mock_request, call_next)

        # Verify request allowed
        call_next.assert_called_once_with(mock_request)
        assert response == mock_response

        # Verify rate limit headers
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Remaining"] == "4"

    async def test_dispatch_within_limit(self):
        """Test multiple requests within limit are allowed"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make 3 requests (limit is 5)
        for i in range(3):
            response = await self.limiter.dispatch(mock_request, call_next)
            assert response == mock_response

        # Verify last response headers
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert response.headers["X-RateLimit-Remaining"] == "2"  # 5 - 3 = 2

    async def test_dispatch_at_limit(self):
        """Test request at exact limit is allowed"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make exactly 5 requests (at limit)
        for i in range(5):
            response = await self.limiter.dispatch(mock_request, call_next)
            assert response == mock_response

        # Last response should show 0 remaining
        assert response.headers["X-RateLimit-Remaining"] == "0"

    async def test_dispatch_exceeds_limit(self):
        """Test request exceeding limit is blocked"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make 5 requests (at limit)
        for i in range(5):
            await self.limiter.dispatch(mock_request, call_next)

        # 6th request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await self.limiter.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "60"

    async def test_dispatch_different_clients_separate_limits(self):
        """Test that different clients have separate rate limits"""
        # Create two requests from different IPs
        mock_request1 = MagicMock(spec=Request)
        mock_request1.client.host = "192.168.1.100"

        mock_request2 = MagicMock(spec=Request)
        mock_request2.client.host = "192.168.1.101"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Client 1 makes 5 requests (reaches limit)
        for i in range(5):
            await self.limiter.dispatch(mock_request1, call_next)

        # Client 1 should be blocked
        with pytest.raises(HTTPException):
            await self.limiter.dispatch(mock_request1, call_next)

        # But Client 2 should still be allowed
        response = await self.limiter.dispatch(mock_request2, call_next)
        assert response == mock_response
        assert response.headers["X-RateLimit-Remaining"] == "4"

    async def test_dispatch_cleans_old_requests(self):
        """Test that old requests are cleaned from the window"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Make 5 requests (at limit)
        for i in range(5):
            await self.limiter.dispatch(mock_request, call_next)

        # Should be blocked now
        with pytest.raises(HTTPException):
            await self.limiter.dispatch(mock_request, call_next)

        # Manually replace one timestamp with an old one (beyond 60 second window)
        old_time = time.time() - 61
        self.limiter.request_counts["192.168.1.100"][0] = old_time

        # Make a new request - old timestamp should be cleaned, allowing this request
        response = await self.limiter.dispatch(mock_request, call_next)
        assert response == mock_response

        # Verify old timestamp was removed
        assert all(
            time.time() - t < 60
            for t in self.limiter.request_counts["192.168.1.100"]
        )

    async def test_dispatch_tracks_request_count(self):
        """Test that request counts are tracked correctly"""
        # Mock request
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Initially no requests
        assert len(self.limiter.request_counts["192.168.1.100"]) == 0

        # Make 3 requests
        for i in range(3):
            await self.limiter.dispatch(mock_request, call_next)

        # Should have 3 timestamps
        assert len(self.limiter.request_counts["192.168.1.100"]) == 3


@pytest.mark.asyncio
class TestCleanupOldRequests:
    """Test periodic cleanup of old request records"""

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    @patch("backend.middleware.rate_limiter.asyncio.sleep")
    async def test_cleanup_removes_old_entries(self, mock_sleep, mock_create_task):
        """Test that cleanup removes old request entries"""
        # Create limiter
        app = FastAPI()
        limiter = RateLimiter(app, requests_per_minute=60)

        # Add some old and new entries
        now = time.time()
        limiter.request_counts["192.168.1.100"] = [
            now - 120,  # Old (beyond 60 second window)
            now - 10,   # Recent
            now - 5,    # Recent
        ]
        limiter.request_counts["192.168.1.101"] = [
            now - 150,  # Old (beyond window)
        ]
        limiter.request_counts["192.168.1.102"] = [
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
        assert len(limiter.request_counts["192.168.1.100"]) == 2  # Old one removed
        assert "192.168.1.101" not in limiter.request_counts  # Removed empty entry
        assert len(limiter.request_counts["192.168.1.102"]) == 1  # Recent kept

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    @patch("backend.middleware.rate_limiter.asyncio.sleep")
    async def test_cleanup_runs_periodically(self, mock_sleep, mock_create_task):
        """Test that cleanup runs at the specified interval"""
        # Create limiter
        app = FastAPI()
        limiter = RateLimiter(app, requests_per_minute=60)

        # Mock sleep to run 3 times then cancel
        mock_sleep.side_effect = [None, None, None, asyncio.CancelledError()]

        # Run cleanup
        try:
            await limiter.cleanup_old_requests()
        except asyncio.CancelledError:
            pass

        # Should have slept 3 times with cleanup_interval (60)
        assert mock_sleep.call_count == 4  # 3 successful + 1 cancelled
        for call in mock_sleep.call_args_list[:3]:
            assert call[0][0] == 60  # cleanup_interval

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    @patch("backend.middleware.rate_limiter.asyncio.sleep")
    async def test_cleanup_removes_client_with_no_recent_requests(self, mock_sleep, mock_create_task):
        """Test that clients with no recent requests are removed"""
        # Create limiter
        app = FastAPI()
        limiter = RateLimiter(app, requests_per_minute=60)

        # Add client with only old requests
        now = time.time()
        limiter.request_counts["192.168.1.100"] = [
            now - 120,
            now - 90,
            now - 70,
        ]

        # Mock sleep to run cleanup once
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        # Run cleanup
        try:
            await limiter.cleanup_old_requests()
        except asyncio.CancelledError:
            pass

        # Client entry should be completely removed
        assert "192.168.1.100" not in limiter.request_counts

    @patch("backend.middleware.rate_limiter.asyncio.create_task")
    @patch("backend.middleware.rate_limiter.asyncio.sleep")
    async def test_cleanup_keeps_recent_requests(self, mock_sleep, mock_create_task):
        """Test that recent requests are kept"""
        # Create limiter
        app = FastAPI()
        limiter = RateLimiter(app, requests_per_minute=60)

        # Add client with only recent requests
        now = time.time()
        limiter.request_counts["192.168.1.100"] = [
            now - 10,
            now - 5,
            now - 2,
        ]

        # Mock sleep to run cleanup once
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        # Run cleanup
        try:
            await limiter.cleanup_old_requests()
        except asyncio.CancelledError:
            pass

        # All recent requests should be kept
        assert len(limiter.request_counts["192.168.1.100"]) == 3
