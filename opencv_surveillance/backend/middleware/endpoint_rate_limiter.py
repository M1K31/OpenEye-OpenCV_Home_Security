# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Per-Endpoint Rate Limiting Middleware
Provides granular rate limiting for different API endpoints
"""

import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from collections import defaultdict
from typing import Dict, Tuple
import asyncio
import logging
import re

logger = logging.getLogger(__name__)


class EndpointRateLimiter(BaseHTTPMiddleware):
    """
    Per-endpoint rate limiting middleware with configurable limits per route
    Free and open source - no external services required
    """

    # Default rate limits for different endpoint categories
    DEFAULT_LIMITS = {
        # Authentication endpoints - stricter limits
        "auth": (10, 60),  # 10 requests per minute

        # Password reset - very strict (5 attempts per hour per IP)
        "password_reset": (5, 3600),  # 5 requests per hour

        # 2FA verification - strict (10 attempts per 5 minutes)
        "2fa_verify": (10, 300),  # 10 requests per 5 minutes

        # Write operations - moderate limits
        "write": (30, 60),  # 30 requests per minute

        # Read operations - generous limits
        "read": (100, 60),  # 100 requests per minute

        # Streaming endpoints - very generous limits
        "stream": (500, 60),  # 500 requests per minute

        # WebSocket - no limit (handled separately)
        "websocket": (999999, 60),
    }

    # Endpoint pattern mappings
    ENDPOINT_PATTERNS = {
        # Authentication endpoints (strictest)
        r"^/api/(token|auth/login|auth/register)": "auth",

        # Password reset - very strict (must be before general auth)
        r"^/api/auth/reset-password": "password_reset",

        # 2FA verification - strict
        r"^/api/auth/2fa/verify": "2fa_verify",

        # Write operations (moderate) - only for specific operations
        r"^/api/(cameras|faces|alerts|recordings)/.*/(delete|update)": "write",

        # Streaming endpoints (generous)
        r"^/api/cameras/.*/stream": "stream",
        r"^/api/recordings/\d+/(download|stream)": "stream",  # Fixed: Match API recordings endpoints
        r"^/recordings/": "stream",  # Legacy static file mount

        # WebSocket (no limit)
        r"^/ws/": "websocket",

        # Everything else defaults based on HTTP method (see get_endpoint_category)
        # GET → "read", POST/PUT/DELETE/PATCH → "write"
    }

    def __init__(
        self,
        app,
        custom_limits: Dict[str, Tuple[int, int]] = None,
        cleanup_interval: int = 60
    ):
        """
        Initialize per-endpoint rate limiter

        Args:
            app: FastAPI application
            custom_limits: Override default limits {category: (requests, seconds)}
            cleanup_interval: Cleanup interval in seconds
        """
        super().__init__(app)

        # Merge custom limits with defaults
        self.limits = self.DEFAULT_LIMITS.copy()
        if custom_limits:
            self.limits.update(custom_limits)

        # Compile regex patterns
        self.compiled_patterns = [
            (re.compile(pattern), category)
            for pattern, category in self.ENDPOINT_PATTERNS.items()
        ]

        # Track requests: {(client_ip, endpoint_category): [timestamps]}
        self.request_counts: Dict[Tuple[str, str], list] = defaultdict(list)
        self.cleanup_interval = cleanup_interval

        # Start cleanup task
        asyncio.create_task(self.cleanup_old_requests())

        logger.info("Per-endpoint rate limiter initialized")
        logger.info(f"Rate limits: {self.limits}")

    def get_endpoint_category(self, path: str, method: str) -> str:
        """
        Determine the rate limit category for an endpoint

        Args:
            path: Request path
            method: HTTP method

        Returns:
            Category name (auth, write, read, stream, websocket)
        """
        # Static content (snapshots, faces, recordings, frontend assets) is served
        # in large bursts — a face-review/gallery page loads hundreds of thumbnails
        # at once — and must NOT be throttled by the API read limit (that produced
        # cascades of failed images). Serve it without rate limiting.
        _STATIC_PREFIXES = (
            "/data/", "/api/snapshots", "/faces/", "/recordings/",
            "/assets/", "/static/",
        )
        _STATIC_SUFFIXES = (
            ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
            ".css", ".js", ".woff", ".woff2", ".mp4", ".map",
        )
        if path.startswith(_STATIC_PREFIXES) or path.endswith(_STATIC_SUFFIXES):
            return "static"

        # Check patterns
        for pattern, category in self.compiled_patterns:
            if pattern.match(path):
                return category

        # Default based on HTTP method
        if method in ["POST", "PUT", "DELETE", "PATCH"]:
            return "write"
        else:
            return "read"

    async def dispatch(self, request: Request, call_next):
        """Process each request with per-endpoint rate limiting"""

        # Get client identifier and endpoint info
        client_ip = request.client.host
        path = request.url.path
        method = request.method

        # Determine endpoint category
        category = self.get_endpoint_category(path, method)

        # Get rate limit for this category
        requests_limit, window_seconds = self.limits.get(
            category,
            self.DEFAULT_LIMITS["read"]
        )

        # Skip rate limiting for websockets (handled separately) and static assets
        # (galleries load hundreds of images at once — never throttle those).
        if category in ("websocket", "static"):
            return await call_next(request)

        # Create tracking key
        tracking_key = (client_ip, category)

        # Get current timestamp
        now = time.time()

        # Clean old requests for this client+category
        self.request_counts[tracking_key] = [
            timestamp
            for timestamp in self.request_counts[tracking_key]
            if now - timestamp < window_seconds
        ]

        # Check rate limit
        current_count = len(self.request_counts[tracking_key])
        if current_count >= requests_limit:
            logger.warning(
                f"Rate limit exceeded for {client_ip} on {category} "
                f"({current_count}/{requests_limit} requests)"
            )
            # Return a real 429 response. Raising HTTPException here would NOT be
            # caught by FastAPI's exception handlers (this is a BaseHTTPMiddleware,
            # outside the route/exception layer) and would surface to the client as
            # a misleading 500 Internal Server Error.
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded for {category} endpoints. "
                              f"Limit: {requests_limit} requests per {window_seconds} seconds."
                },
                headers={"Retry-After": str(window_seconds)},
            )

        # Add current request
        self.request_counts[tracking_key].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(requests_limit)
        response.headers["X-RateLimit-Remaining"] = str(
            requests_limit - len(self.request_counts[tracking_key])
        )
        response.headers["X-RateLimit-Category"] = category

        return response

    async def cleanup_old_requests(self):
        """Periodically clean up old request records"""
        while True:
            await asyncio.sleep(self.cleanup_interval)

            now = time.time()

            # Clean up old records
            keys_to_remove = []
            for key, timestamps in self.request_counts.items():
                client_ip, category = key
                window_seconds = self.limits.get(
                    category,
                    self.DEFAULT_LIMITS["read"]
                )[1]

                # Remove timestamps older than window
                self.request_counts[key] = [
                    t for t in timestamps if now - t < window_seconds
                ]

                # If no recent requests, remove entry
                if not self.request_counts[key]:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.request_counts[key]

            if keys_to_remove:
                logger.debug(f"Cleaned up {len(keys_to_remove)} stale rate limit entries")
