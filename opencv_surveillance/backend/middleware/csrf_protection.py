# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
CSRF Protection Middleware
Protects against Cross-Site Request Forgery attacks
"""

import secrets
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class CSRFProtection(BaseHTTPMiddleware):
    """
    CSRF protection using double-submit cookie pattern
    Free and open source - no external services required

    How it works:
    1. Generate CSRF token on first request
    2. Set token in cookie
    3. Client must include token in X-CSRF-Token header for state-changing requests
    4. Validate token matches cookie
    """

    # Methods that require CSRF protection
    PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

    # Paths exempt from CSRF protection
    EXEMPT_PATHS = {
        "/api/token",  # OAuth2 token endpoint
        "/api/auth/login",  # Login endpoint
        "/api/auth/register",  # Registration endpoint
        "/api/docs",  # API documentation
        "/api/redoc",  # API documentation
        "/api/openapi.json",  # OpenAPI schema
        "/ws/",  # WebSocket endpoints
    }

    def __init__(
        self,
        app,
        token_length: int = 32,
        cookie_name: str = "csrf_token",
        header_name: str = "X-CSRF-Token",
        token_lifetime: int = 3600  # 1 hour
    ):
        """
        Initialize CSRF protection

        Args:
            app: FastAPI application
            token_length: Length of CSRF tokens in bytes
            cookie_name: Name of CSRF cookie
            header_name: Name of CSRF header
            token_lifetime: Token lifetime in seconds
        """
        super().__init__(app)
        self.token_length = token_length
        self.cookie_name = cookie_name
        self.header_name = header_name
        self.token_lifetime = token_lifetime

        # Store valid tokens with timestamps
        self.valid_tokens: Dict[str, float] = {}

        logger.info("CSRF protection enabled")

    def is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection"""
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return True
        return False

    def generate_token(self) -> str:
        """Generate a secure CSRF token"""
        token = secrets.token_urlsafe(self.token_length)
        self.valid_tokens[token] = time.time()
        return token

    def validate_token(self, token: str) -> bool:
        """
        Validate CSRF token

        Args:
            token: Token to validate

        Returns:
            True if valid, False otherwise
        """
        if not token:
            return False

        # Check if token exists and is not expired
        if token in self.valid_tokens:
            timestamp = self.valid_tokens[token]
            if time.time() - timestamp < self.token_lifetime:
                return True
            else:
                # Remove expired token
                del self.valid_tokens[token]

        return False

    def cleanup_expired_tokens(self):
        """Remove expired tokens from storage"""
        now = time.time()
        expired_tokens = [
            token for token, timestamp in self.valid_tokens.items()
            if now - timestamp > self.token_lifetime
        ]
        for token in expired_tokens:
            del self.valid_tokens[token]

    async def dispatch(self, request: Request, call_next):
        """Process each request with CSRF protection"""

        path = request.url.path
        method = request.method

        # Periodically cleanup expired tokens (every 100 requests)
        if len(self.valid_tokens) % 100 == 0:
            self.cleanup_expired_tokens()

        # Skip CSRF check for safe methods and exempt paths
        if method not in self.PROTECTED_METHODS or self.is_exempt(path):
            response = await call_next(request)

            # Generate token for GET requests if not present
            if method == "GET" and self.cookie_name not in request.cookies:
                token = self.generate_token()
                response.set_cookie(
                    key=self.cookie_name,
                    value=token,
                    httponly=True,
                    samesite="strict",
                    secure=True,  # Require HTTPS in production
                    max_age=self.token_lifetime
                )

            return response

        # For protected methods, validate CSRF token
        cookie_token = request.cookies.get(self.cookie_name)
        header_token = request.headers.get(self.header_name)

        # Check if both tokens exist
        if not cookie_token or not header_token:
            logger.warning(
                f"CSRF validation failed for {request.client.host} "
                f"on {method} {path}: Missing token"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF token missing. Please refresh the page."
            )

        # Validate that tokens match and are valid
        if cookie_token != header_token or not self.validate_token(cookie_token):
            logger.warning(
                f"CSRF validation failed for {request.client.host} "
                f"on {method} {path}: Invalid or mismatched token"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF token validation failed. Please refresh the page."
            )

        # Token is valid, process request
        response = await call_next(request)
        return response
