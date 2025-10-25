# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
SQLAlchemy Query Profiling Middleware

Logs slow database queries for performance optimization.
Enable by setting environment variable: ENABLE_QUERY_PROFILING=true
"""

import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine
from typing import Optional

logger = logging.getLogger(__name__)


class QueryProfiler:
    """
    SQLAlchemy query profiler for performance monitoring

    Tracks query execution times and logs slow queries.
    """

    def __init__(self, slow_query_threshold_ms: float = 100.0):
        """
        Initialize query profiler

        Args:
            slow_query_threshold_ms: Log queries slower than this (milliseconds)
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.enabled = False
        self.query_count = 0
        self.total_query_time = 0.0
        self.slow_queries = []
        self.max_slow_queries = 100  # Keep last 100 slow queries

    def enable(self):
        """Enable query profiling"""
        if self.enabled:
            logger.warning("Query profiling is already enabled")
            return

        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Record query start time"""
            conn.info.setdefault('query_start_time', []).append(time.time())
            conn.info.setdefault('query_statement', []).append(statement)

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Calculate and log query execution time"""
            if 'query_start_time' not in conn.info:
                return

            # Calculate duration
            start_time = conn.info['query_start_time'].pop(-1)
            duration_ms = (time.time() - start_time) * 1000

            # Update statistics
            self.query_count += 1
            self.total_query_time += duration_ms

            # Log slow queries
            if duration_ms > self.slow_query_threshold_ms:
                self._log_slow_query(statement, duration_ms, parameters)

        self.enabled = True
        logger.info(
            f"Query profiling enabled (slow query threshold: {self.slow_query_threshold_ms}ms)"
        )

    def _log_slow_query(self, statement: str, duration_ms: float, parameters):
        """Log a slow query with details"""
        # Clean up statement for logging
        statement_clean = ' '.join(statement.split())
        if len(statement_clean) > 500:
            statement_clean = statement_clean[:500] + '...'

        logger.warning(
            f"SLOW QUERY ({duration_ms:.2f}ms): {statement_clean}"
        )

        # Store for API access
        slow_query = {
            'statement': statement_clean,
            'duration_ms': round(duration_ms, 2),
            'timestamp': time.time(),
            'parameters': str(parameters)[:200] if parameters else None
        }

        self.slow_queries.append(slow_query)

        # Keep only last N slow queries
        if len(self.slow_queries) > self.max_slow_queries:
            self.slow_queries.pop(0)

    def get_statistics(self) -> dict:
        """Get profiling statistics"""
        avg_query_time = (
            self.total_query_time / self.query_count
            if self.query_count > 0
            else 0
        )

        return {
            'enabled': self.enabled,
            'total_queries': self.query_count,
            'total_query_time_ms': round(self.total_query_time, 2),
            'avg_query_time_ms': round(avg_query_time, 2),
            'slow_query_count': len(self.slow_queries),
            'slow_query_threshold_ms': self.slow_query_threshold_ms,
        }

    def get_slow_queries(self, limit: Optional[int] = None) -> list:
        """
        Get list of slow queries

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slow query dictionaries
        """
        queries = self.slow_queries.copy()
        if limit:
            queries = queries[-limit:]
        return queries

    def reset(self):
        """Reset profiling statistics"""
        self.query_count = 0
        self.total_query_time = 0.0
        self.slow_queries = []
        logger.info("Query profiling statistics reset")


# Global profiler instance
query_profiler = QueryProfiler(slow_query_threshold_ms=100.0)


def enable_query_profiling(slow_query_threshold_ms: float = 100.0):
    """
    Enable query profiling globally

    Args:
        slow_query_threshold_ms: Log queries slower than this (milliseconds)

    Example:
        # In main.py or startup script
        from backend.middleware.query_profiler import enable_query_profiling
        enable_query_profiling(slow_query_threshold_ms=100)
    """
    global query_profiler
    query_profiler.slow_query_threshold_ms = slow_query_threshold_ms
    query_profiler.enable()


def get_query_profiler() -> QueryProfiler:
    """Get the global query profiler instance"""
    return query_profiler
