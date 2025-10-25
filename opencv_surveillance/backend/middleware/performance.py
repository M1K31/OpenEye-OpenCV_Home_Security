# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Performance Monitoring Middleware

Tracks API endpoint performance and provides metrics
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.core.performance import performance_metrics
import time
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Monitor API endpoint performance

    Tracks:
    - Request duration
    - Response status codes
    - Slow endpoints
    - Error rates
    """

    def __init__(self, app, slow_request_threshold_ms: float = 1000.0):
        super().__init__(app)
        self.slow_request_threshold_ms = slow_request_threshold_ms
        logger.info(
            f"Performance monitoring enabled (slow threshold: {slow_request_threshold_ms}ms)"
        )

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Extract endpoint path
        endpoint = request.url.path

        # Record metrics
        performance_metrics.record_request(
            endpoint=endpoint,
            duration_ms=duration_ms,
            status_code=response.status_code
        )

        # Log slow requests
        if duration_ms > self.slow_request_threshold_ms:
            logger.warning(
                f"Slow request: {request.method} {endpoint} "
                f"took {duration_ms:.2f}ms (status: {response.status_code})"
            )

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response


class DatabaseQueryLogger(BaseHTTPMiddleware):
    """
    Log database query performance

    Useful for identifying N+1 queries and slow database operations
    """

    def __init__(self, app, log_queries: bool = False):
        super().__init__(app)
        self.log_queries = log_queries

        if log_queries:
            logger.info("Database query logging enabled")
        else:
            logger.info("Database query logging disabled (set LOG_QUERIES=true to enable)")

    async def dispatch(self, request: Request, call_next):
        if not self.log_queries:
            return await call_next(request)

        # This is a placeholder - actual query logging would require
        # SQLAlchemy event listeners
        # See: https://docs.sqlalchemy.org/en/14/core/events.html

        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Log if request took longer than threshold
        if duration_ms > 500:
            logger.debug(
                f"Database-heavy request: {request.url.path} "
                f"took {duration_ms:.2f}ms"
            )

        return response
