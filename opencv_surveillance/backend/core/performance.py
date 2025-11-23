# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Performance Optimization Utilities

Provides pagination, caching, and performance monitoring for OpenEye
"""

from functools import lru_cache, wraps
from typing import TypeVar, Generic, List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import time
import logging
from backend.core.config import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response model

    Example:
        {
            "items": [...],
            "total": 1000,
            "page": 1,
            "page_size": 50,
            "pages": 20
        }
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    class Config:
        arbitrary_types_allowed = True


def paginate(
    query,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_page_size: int = MAX_PAGE_SIZE
) -> tuple:
    """
    Paginate a SQLAlchemy query

    Args:
        query: SQLAlchemy query object
        page: Page number (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size

    Returns:
        tuple: (items, total_count, total_pages)

    Example:
        items, total, pages = paginate(db.query(Model), page=1, page_size=50)
    """
    # Validate and clamp page size
    page_size = max(MIN_PAGE_SIZE, min(page_size, max_page_size))

    # Ensure page is at least 1
    page = max(1, page)

    # Get total count (efficient count query)
    total = query.count()

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1

    # Clamp page to valid range
    page = min(page, total_pages)

    # Calculate offset
    offset = (page - 1) * page_size

    # Execute paginated query
    items = query.offset(offset).limit(page_size).all()

    return items, total, total_pages


def timed_lru_cache(seconds: int = 60, maxsize: int = 128):
    """
    LRU cache with time-based expiration

    Args:
        seconds: Cache TTL in seconds
        maxsize: Maximum cache size

    Example:
        @timed_lru_cache(seconds=300, maxsize=64)
        def expensive_operation():
            ...
    """
    def decorator(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime

        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime

            return func(*args, **kwargs)

        wrapped_func.cache_info = func.cache_info
        wrapped_func.cache_clear = func.cache_clear
        return wrapped_func

    return decorator


def performance_monitor(threshold_ms: float = 1000.0):
    """
    Decorator to monitor function performance and log slow operations

    Args:
        threshold_ms: Log warning if execution exceeds this threshold (milliseconds)

    Example:
        @performance_monitor(threshold_ms=500)
        def slow_database_query():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                execution_time = (time.time() - start_time) * 1000
                if execution_time > threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__} took {execution_time:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"{func.__name__} completed in {execution_time:.2f}ms")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = (time.time() - start_time) * 1000
                if execution_time > threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__} took {execution_time:.2f}ms "
                        f"(threshold: {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"{func.__name__} completed in {execution_time:.2f}ms")

        # Return appropriate wrapper based on function type
        if hasattr(func, '__call__') and hasattr(func, '__await__'):
            return async_wrapper
        return sync_wrapper

    return decorator


class QueryOptimizer:
    """
    Query optimization utilities for common patterns
    """

    @staticmethod
    def optimize_large_result_set(query, batch_size: int = 1000):
        """
        Process large result sets in batches to avoid memory issues

        Args:
            query: SQLAlchemy query
            batch_size: Number of records per batch

        Yields:
            Batches of records

        Example:
            for batch in QueryOptimizer.optimize_large_result_set(query):
                process_batch(batch)
        """
        offset = 0
        while True:
            batch = query.limit(batch_size).offset(offset).all()
            if not batch:
                break
            yield batch
            offset += batch_size

    @staticmethod
    def selective_load(query, columns: list):
        """
        Load only specified columns to reduce memory usage

        Args:
            query: SQLAlchemy query
            columns: List of column objects to load

        Returns:
            Query with selective loading

        Example:
            query = QueryOptimizer.selective_load(
                db.query(Recording),
                [Recording.id, Recording.camera_id]
            )
        """
        return query.with_entities(*columns)


# Performance metrics storage (in-memory, could be extended to Redis/database)
class PerformanceMetrics:
    """Track performance metrics for monitoring"""

    def __init__(self):
        self.metrics = {}
        self.request_times = []
        self.max_stored_requests = 1000

    def record_request(self, endpoint: str, duration_ms: float, status_code: int):
        """Record API request metrics"""
        if endpoint not in self.metrics:
            self.metrics[endpoint] = {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0,
                "errors": 0
            }

        metrics = self.metrics[endpoint]
        metrics["count"] += 1
        metrics["total_time"] += duration_ms
        metrics["avg_time"] = metrics["total_time"] / metrics["count"]
        metrics["min_time"] = min(metrics["min_time"], duration_ms)
        metrics["max_time"] = max(metrics["max_time"], duration_ms)

        if status_code >= 400:
            metrics["errors"] += 1

        # Store recent request times (FIFO)
        self.request_times.append({
            "endpoint": endpoint,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow(),
            "status_code": status_code
        })

        # Limit stored requests
        if len(self.request_times) > self.max_stored_requests:
            self.request_times.pop(0)

    def get_metrics(self, endpoint: Optional[str] = None):
        """Get performance metrics"""
        if endpoint:
            return self.metrics.get(endpoint, {})
        return self.metrics

    def get_slow_endpoints(self, threshold_ms: float = 1000.0):
        """Get endpoints with average response time above threshold"""
        return {
            endpoint: metrics
            for endpoint, metrics in self.metrics.items()
            if metrics["avg_time"] > threshold_ms
        }

    def reset(self):
        """Reset all metrics"""
        self.metrics = {}
        self.request_times = []


# Global metrics instance
performance_metrics = PerformanceMetrics()
