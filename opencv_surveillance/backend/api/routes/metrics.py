# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Performance Metrics API Routes
Provides real-time performance monitoring and analysis
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime

from backend.core.performance import performance_metrics
from backend.middleware.query_profiler import get_query_profiler

router = APIRouter()


@router.get("/metrics/performance")
def get_performance_metrics(
    endpoint: Optional[str] = Query(None, description="Filter by specific endpoint"),
    min_avg_time: Optional[float] = Query(None, description="Filter endpoints with avg time >= this value (ms)"),
):
    """
    Get performance metrics for all API endpoints

    Returns:
    - Request count per endpoint
    - Average/min/max response times
    - Error counts
    - Request rate

    **Query Parameters:**
    - **endpoint**: Filter by specific endpoint path
    - **min_avg_time**: Only show endpoints with average time >= this value

    **Example Response:**
    ```json
    {
      "endpoints": {
        "/api/recordings/": {
          "count": 1523,
          "avg_time": 45.2,
          "min_time": 12.3,
          "max_time": 234.1,
          "errors": 3
        }
      },
      "total_requests": 5431,
      "timestamp": "2025-10-23T12:34:56"
    }
    ```
    """
    if endpoint:
        # Get metrics for specific endpoint
        metrics = performance_metrics.get_metrics(endpoint)
        return {
            "endpoint": endpoint,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Get all metrics
    all_metrics = performance_metrics.get_metrics()

    # Apply filtering if requested
    if min_avg_time is not None:
        all_metrics = {
            ep: m for ep, m in all_metrics.items()
            if m.get("avg_time", 0) >= min_avg_time
        }

    # Calculate total requests
    total_requests = sum(m.get("count", 0) for m in all_metrics.values())

    return {
        "endpoints": all_metrics,
        "total_requests": total_requests,
        "endpoint_count": len(all_metrics),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics/performance/slow")
def get_slow_endpoints(
    threshold_ms: float = Query(1000.0, description="Threshold in milliseconds (default: 1000)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum endpoints to return"),
):
    """
    Get slowest API endpoints

    Returns endpoints with average response time above the threshold,
    ordered by average response time (slowest first).

    **Query Parameters:**
    - **threshold_ms**: Minimum average time to be considered slow (default: 1000ms)
    - **limit**: Maximum number of endpoints to return (default: 10)

    **Example Response:**
    ```json
    {
      "slow_endpoints": {
        "/api/faces/cluster": {
          "avg_time": 1523.4,
          "count": 12,
          "max_time": 2340.1
        }
      },
      "threshold_ms": 1000.0,
      "count": 3
    }
    ```
    """
    slow_endpoints = performance_metrics.get_slow_endpoints(threshold_ms=threshold_ms)

    # Sort by average time (slowest first) and limit
    sorted_endpoints = dict(
        sorted(
            slow_endpoints.items(),
            key=lambda x: x[1].get("avg_time", 0),
            reverse=True
        )[:limit]
    )

    return {
        "slow_endpoints": sorted_endpoints,
        "threshold_ms": threshold_ms,
        "count": len(sorted_endpoints),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics/performance/summary")
def get_performance_summary():
    """
    Get high-level performance summary

    Returns aggregated statistics across all endpoints:
    - Total requests tracked
    - Number of unique endpoints
    - Overall average response time
    - Total error count
    - Slowest endpoint

    **Example Response:**
    ```json
    {
      "total_requests": 15234,
      "unique_endpoints": 42,
      "overall_avg_time": 87.3,
      "total_errors": 23,
      "slowest_endpoint": {
        "path": "/api/faces/cluster",
        "avg_time": 1523.4
      }
    }
    ```
    """
    all_metrics = performance_metrics.get_metrics()

    if not all_metrics:
        return {
            "total_requests": 0,
            "unique_endpoints": 0,
            "overall_avg_time": 0,
            "total_errors": 0,
            "slowest_endpoint": None,
            "timestamp": datetime.utcnow().isoformat()
        }

    total_requests = sum(m.get("count", 0) for m in all_metrics.values())
    total_errors = sum(m.get("errors", 0) for m in all_metrics.values())

    # Calculate weighted average response time
    total_time = sum(m.get("total_time", 0) for m in all_metrics.values())
    overall_avg_time = total_time / total_requests if total_requests > 0 else 0

    # Find slowest endpoint
    slowest = max(
        all_metrics.items(),
        key=lambda x: x[1].get("avg_time", 0)
    )

    return {
        "total_requests": total_requests,
        "unique_endpoints": len(all_metrics),
        "overall_avg_time": round(overall_avg_time, 2),
        "total_errors": total_errors,
        "error_rate_percent": round((total_errors / total_requests * 100), 2) if total_requests > 0 else 0,
        "slowest_endpoint": {
            "path": slowest[0],
            "avg_time": round(slowest[1].get("avg_time", 0), 2),
            "count": slowest[1].get("count", 0)
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/metrics/performance/reset")
def reset_performance_metrics():
    """
    Reset all performance metrics

    Clears all collected performance data. Use this after deployment
    or when you want to start fresh metrics collection.

    **Warning**: This action cannot be undone.

    **Example Response:**
    ```json
    {
      "message": "Performance metrics reset successfully",
      "previous_request_count": 1523,
      "timestamp": "2025-10-23T12:34:56"
    }
    ```
    """
    # Get current metrics before reset
    all_metrics = performance_metrics.get_metrics()
    previous_count = sum(m.get("count", 0) for m in all_metrics.values())

    # Reset metrics
    performance_metrics.reset()

    return {
        "message": "Performance metrics reset successfully",
        "previous_request_count": previous_count,
        "previous_endpoint_count": len(all_metrics),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics/performance/recent")
def get_recent_requests(
    limit: int = Query(100, ge=1, le=1000, description="Number of recent requests to return"),
):
    """
    Get most recent API requests with timing information

    Returns a list of the most recent requests tracked by the
    performance monitoring system.

    **Query Parameters:**
    - **limit**: Number of requests to return (default: 100, max: 1000)

    **Example Response:**
    ```json
    {
      "requests": [
        {
          "endpoint": "/api/recordings/",
          "duration_ms": 45.2,
          "timestamp": "2025-10-23T12:34:56",
          "status_code": 200
        }
      ],
      "count": 100
    }
    ```
    """
    # Get recent requests from metrics
    recent = performance_metrics.request_times[-limit:] if hasattr(performance_metrics, 'request_times') else []

    return {
        "requests": [
            {
                "endpoint": req.get("endpoint"),
                "duration_ms": round(req.get("duration_ms", 0), 2),
                "timestamp": req.get("timestamp").isoformat() if req.get("timestamp") else None,
                "status_code": req.get("status_code")
            }
            for req in recent
        ],
        "count": len(recent),
        "limit": limit,
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# DATABASE QUERY PROFILING ENDPOINTS
# ============================================================================

@router.get("/metrics/queries/statistics")
def get_query_statistics():
    """
    Get database query profiling statistics

    Returns overall statistics about database query performance:
    - Total queries executed
    - Average query time
    - Number of slow queries logged
    - Profiling status

    **Note**: Query profiling must be enabled in main.py

    **Example Response**:
    ```json
    {
      "enabled": true,
      "total_queries": 1523,
      "avg_query_time_ms": 23.4,
      "slow_query_count": 12,
      "slow_query_threshold_ms": 100.0
    }
    ```
    """
    profiler = get_query_profiler()
    stats = profiler.get_statistics()

    return {
        **stats,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/metrics/queries/slow")
def get_slow_queries(
    limit: int = Query(50, ge=1, le=500, description="Maximum queries to return"),
):
    """
    Get list of slow database queries

    Returns recent slow queries that exceeded the threshold.
    Useful for identifying performance bottlenecks.

    **Query Parameters:**
    - **limit**: Maximum number of queries to return (default: 50, max: 500)

    **Example Response**:
    ```json
    {
      "slow_queries": [
        {
          "statement": "SELECT * FROM recording_events WHERE...",
          "duration_ms": 234.5,
          "timestamp": 1698765432.123,
          "parameters": "{'camera_id': 'front_door'}"
        }
      ],
      "count": 12
    }
    ```
    """
    profiler = get_query_profiler()

    if not profiler.enabled:
        return {
            "slow_queries": [],
            "count": 0,
            "message": "Query profiling is not enabled. Set ENABLE_QUERY_PROFILING=true to enable.",
            "timestamp": datetime.utcnow().isoformat()
        }

    slow_queries = profiler.get_slow_queries(limit=limit)

    return {
        "slow_queries": slow_queries,
        "count": len(slow_queries),
        "threshold_ms": profiler.slow_query_threshold_ms,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/metrics/queries/reset")
def reset_query_statistics():
    """
    Reset query profiling statistics

    Clears all collected query profiling data including slow queries.

    **Warning**: This action cannot be undone.

    **Example Response**:
    ```json
    {
      "message": "Query profiling statistics reset successfully",
      "previous_query_count": 1523,
      "timestamp": "2025-10-23T12:34:56"
    }
    ```
    """
    profiler = get_query_profiler()
    stats = profiler.get_statistics()
    previous_count = stats['total_queries']

    profiler.reset()

    return {
        "message": "Query profiling statistics reset successfully",
        "previous_query_count": previous_count,
        "previous_slow_query_count": stats['slow_query_count'],
        "timestamp": datetime.utcnow().isoformat()
    }
