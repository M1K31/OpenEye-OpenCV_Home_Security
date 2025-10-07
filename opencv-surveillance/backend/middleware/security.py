# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Enhanced Security Middleware
All security features are free and open source
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import re
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses
    Free and open source security best practices
    """
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP whitelist middleware for additional security
    Optional - disabled by default for ease of use
    """
    
    def __init__(self, app, allowed_ips: list = None):
        super().__init__(app)
        self.allowed_ips = allowed_ips or []
        self.enabled = len(self.allowed_ips) > 0
        
        if self.enabled:
            logger.info(f"IP whitelist enabled for: {', '.join(self.allowed_ips)}")
        else:
            logger.info("IP whitelist disabled - all IPs allowed")
    
    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        
        client_ip = request.client.host
        
        # Check if IP is whitelisted
        if client_ip not in self.allowed_ips:
            logger.warning(f"Access denied for IP: {client_ip}")
            raise HTTPException(
                status_code=403,
                detail="Access denied: IP not whitelisted"
            )
        
        return await call_next(request)


class SQLInjectionProtection(BaseHTTPMiddleware):
    """
    Basic SQL injection protection
    Free and open source - no external services required
    """
    
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(--|\#|\/\*)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)"
    ]
    
    def __init__(self, app):
        super().__init__(app)
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        logger.info("SQL injection protection enabled")
    
    def check_sql_injection(self, value: str) -> bool:
        """Check if string contains SQL injection patterns"""
        for pattern in self.patterns:
            if pattern.search(value):
                return True
        return False
    
    async def dispatch(self, request: Request, call_next):
        # Check query parameters
        for key, value in request.query_params.items():
            if self.check_sql_injection(str(value)):
                logger.warning(f"SQL injection attempt detected in query param: {key}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid input detected"
                )
        
        # Check path parameters
        if self.check_sql_injection(str(request.url.path)):
            logger.warning(f"SQL injection attempt detected in path: {request.url.path}")
            raise HTTPException(
                status_code=400,
                detail="Invalid request"
            )
        
        return await call_next(request)
