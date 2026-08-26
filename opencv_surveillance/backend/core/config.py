# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Centralized Configuration Module

All configurable constants and settings for the OpenEye backend.
This module provides a single source of truth for:
- Authentication and security settings
- Performance and pagination settings
- Rate limiting and retry logic
- Feature toggles and system limits

Usage:
    from backend.core.config import (
        ACCESS_TOKEN_EXPIRE_MINUTES,
        DEFAULT_PAGE_SIZE,
        MAX_2FA_ATTEMPTS
    )

Environment Variables:
    Most settings can be overridden via environment variables.
    See .env.example for available options.
"""

import os

# The one place the application version is written.
#
# It had been hardcoded in seven: the FastAPI app, three API responses,
# the sidebar, package.json and deploy.sh — and they had drifted to four
# different numbers, with the deploy script about to publish an OLDER tag
# than the released one against newer code. Everything that reports a
# version now reads it from here.
APP_VERSION = "3.11.9"
from typing import List

# ============================================================================
# AUTHENTICATION & SECURITY
# ============================================================================

# JWT Token Settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Two-Factor Authentication
MAX_2FA_ATTEMPTS = int(os.getenv("MAX_2FA_ATTEMPTS", "5"))
LOCKOUT_DURATION_MINUTES = int(os.getenv("LOCKOUT_DURATION_MINUTES", "30"))
ATTEMPT_RESET_MINUTES = int(os.getenv("ATTEMPT_RESET_MINUTES", "15"))

# Password Requirements
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))
MAX_PASSWORD_LENGTH = int(os.getenv("MAX_PASSWORD_LENGTH", "128"))
REQUIRE_UPPERCASE = os.getenv("REQUIRE_UPPERCASE", "true").lower() == "true"
REQUIRE_LOWERCASE = os.getenv("REQUIRE_LOWERCASE", "true").lower() == "true"
REQUIRE_DIGIT = os.getenv("REQUIRE_DIGIT", "true").lower() == "true"
REQUIRE_SPECIAL_CHAR = os.getenv("REQUIRE_SPECIAL_CHAR", "true").lower() == "true"

# Session Settings
SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
MAX_CONCURRENT_SESSIONS = int(os.getenv("MAX_CONCURRENT_SESSIONS", "5"))

# ============================================================================
# PERFORMANCE & PAGINATION
# ============================================================================

# Pagination
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "50"))
MAX_PAGE_SIZE = int(os.getenv("MAX_PAGE_SIZE", "1000"))
MIN_PAGE_SIZE = int(os.getenv("MIN_PAGE_SIZE", "1"))

# Query Performance
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "100"))
ENABLE_QUERY_PROFILING = os.getenv("ENABLE_QUERY_PROFILING", "false").lower() == "true"

# Request Limits
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "100"))
MAX_UPLOAD_FILES = int(os.getenv("MAX_UPLOAD_FILES", "50"))
MAX_CONCURRENT_UPLOADS = int(os.getenv("MAX_CONCURRENT_UPLOADS", "3"))

# ============================================================================
# RATE LIMITING
# ============================================================================

# Per-endpoint rate limits (requests per minute)
RATE_LIMIT_AUTH = int(os.getenv("RATE_LIMIT_AUTH", "10"))      # Login, token refresh
RATE_LIMIT_WRITE = int(os.getenv("RATE_LIMIT_WRITE", "30"))    # POST, PUT, DELETE
RATE_LIMIT_READ = int(os.getenv("RATE_LIMIT_READ", "100"))     # GET
RATE_LIMIT_STREAM = int(os.getenv("RATE_LIMIT_STREAM", "500")) # Video/WebSocket

# Global rate limit (requests per minute per IP)
GLOBAL_RATE_LIMIT = int(os.getenv("GLOBAL_RATE_LIMIT", "1000"))

# Rate limit storage
RATE_LIMIT_STORAGE = os.getenv("RATE_LIMIT_STORAGE", "memory")  # "memory" or "redis"
RATE_LIMIT_REDIS_URL = os.getenv("RATE_LIMIT_REDIS_URL", "redis://localhost:6379/0")

# ============================================================================
# CAMERA & VIDEO SETTINGS
# ============================================================================

# Camera Defaults
DEFAULT_FPS = int(os.getenv("DEFAULT_FPS", "15"))
DEFAULT_RESOLUTION_WIDTH = int(os.getenv("DEFAULT_RESOLUTION_WIDTH", "1920"))
DEFAULT_RESOLUTION_HEIGHT = int(os.getenv("DEFAULT_RESOLUTION_HEIGHT", "1080"))

# Video Recording
MAX_RECORDING_DURATION_SECONDS = int(os.getenv("MAX_RECORDING_DURATION_SECONDS", "3600"))  # 1 hour
RECORDING_SEGMENT_DURATION_SECONDS = int(os.getenv("RECORDING_SEGMENT_DURATION_SECONDS", "300"))  # 5 minutes
RECORDING_BUFFER_FRAMES = int(os.getenv("RECORDING_BUFFER_FRAMES", "150"))  # 10 seconds at 15fps

# Video Streaming
STREAM_QUALITY = os.getenv("STREAM_QUALITY", "high")  # "low", "medium", "high"
STREAM_BUFFER_SIZE = int(os.getenv("STREAM_BUFFER_SIZE", "1024"))  # KB
STREAM_TIMEOUT_SECONDS = int(os.getenv("STREAM_TIMEOUT_SECONDS", "30"))

# Camera Connection
CAMERA_CONNECT_TIMEOUT_SECONDS = int(os.getenv("CAMERA_CONNECT_TIMEOUT_SECONDS", "10"))
CAMERA_READ_TIMEOUT_SECONDS = int(os.getenv("CAMERA_READ_TIMEOUT_SECONDS", "5"))
CAMERA_RECONNECT_ATTEMPTS = int(os.getenv("CAMERA_RECONNECT_ATTEMPTS", "3"))
CAMERA_RECONNECT_DELAY_SECONDS = int(os.getenv("CAMERA_RECONNECT_DELAY_SECONDS", "5"))

# ============================================================================
# FACE RECOGNITION & DETECTION
# ============================================================================

# Face Detection
FACE_DETECTION_MODEL = os.getenv("FACE_DETECTION_MODEL", "hog")  # "hog" or "cnn"
FACE_DETECTION_UPSAMPLE = int(os.getenv("FACE_DETECTION_UPSAMPLE", "1"))
FACE_RECOGNITION_TOLERANCE = float(os.getenv("FACE_RECOGNITION_TOLERANCE", "0.6"))
FACE_MIN_SIZE_PIXELS = int(os.getenv("FACE_MIN_SIZE_PIXELS", "80"))

# Face Clustering
CLUSTERING_DBSCAN_EPS = float(os.getenv("CLUSTERING_DBSCAN_EPS", "0.5"))
CLUSTERING_MIN_SAMPLES = int(os.getenv("CLUSTERING_MIN_SAMPLES", "3"))
CLUSTERING_SCHEDULER_INTERVAL_MINUTES = int(os.getenv("CLUSTERING_SCHEDULER_INTERVAL_MINUTES", "60"))
CLUSTERING_MIN_THRESHOLD = int(os.getenv("CLUSTERING_MIN_THRESHOLD", "10"))

# Face Image Requirements
MIN_FACE_IMAGE_SIZE_KB = int(os.getenv("MIN_FACE_IMAGE_SIZE_KB", "10"))
MAX_FACE_IMAGE_SIZE_KB = int(os.getenv("MAX_FACE_IMAGE_SIZE_KB", "5120"))  # 5MB
ALLOWED_FACE_IMAGE_FORMATS = os.getenv("ALLOWED_FACE_IMAGE_FORMATS", "jpg,jpeg,png").split(",")

# ============================================================================
# MOTION DETECTION
# ============================================================================

# Motion Detection Sensitivity
MOTION_THRESHOLD = int(os.getenv("MOTION_THRESHOLD", "25"))
MOTION_MIN_AREA_PIXELS = int(os.getenv("MOTION_MIN_AREA_PIXELS", "500"))
MOTION_BLUR_SIZE = int(os.getenv("MOTION_BLUR_SIZE", "21"))
MOTION_HISTORY_FRAMES = int(os.getenv("MOTION_HISTORY_FRAMES", "500"))

# Motion Recording
MOTION_RECORDING_PRE_BUFFER_SECONDS = int(os.getenv("MOTION_RECORDING_PRE_BUFFER_SECONDS", "5"))
MOTION_RECORDING_POST_BUFFER_SECONDS = int(os.getenv("MOTION_RECORDING_POST_BUFFER_SECONDS", "10"))

# ============================================================================
# STORAGE & RETENTION
# ============================================================================

# Recording Retention
RECORDING_RETENTION_DAYS = int(os.getenv("RECORDING_RETENTION_DAYS", "30"))
SNAPSHOT_RETENTION_DAYS = int(os.getenv("SNAPSHOT_RETENTION_DAYS", "7"))
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "90"))

# Storage Limits
MAX_STORAGE_GB = int(os.getenv("MAX_STORAGE_GB", "500"))
WARNING_STORAGE_THRESHOLD_PERCENT = int(os.getenv("WARNING_STORAGE_THRESHOLD_PERCENT", "80"))

# Cleanup Settings
CLEANUP_SCHEDULER_INTERVAL_HOURS = int(os.getenv("CLEANUP_SCHEDULER_INTERVAL_HOURS", "24"))
ENABLE_AUTO_CLEANUP = os.getenv("ENABLE_AUTO_CLEANUP", "true").lower() == "true"

# ============================================================================
# NOTIFICATION SETTINGS
# ============================================================================

# Alert Throttling
ALERT_THROTTLE_MINUTES = int(os.getenv("ALERT_THROTTLE_MINUTES", "5"))
MAX_ALERTS_PER_HOUR = int(os.getenv("MAX_ALERTS_PER_HOUR", "60"))

# Notification Retry
NOTIFICATION_MAX_RETRIES = int(os.getenv("NOTIFICATION_MAX_RETRIES", "3"))
NOTIFICATION_RETRY_DELAY_SECONDS = int(os.getenv("NOTIFICATION_RETRY_DELAY_SECONDS", "60"))

# Notification Queue
NOTIFICATION_QUEUE_SIZE = int(os.getenv("NOTIFICATION_QUEUE_SIZE", "1000"))
NOTIFICATION_WORKER_THREADS = int(os.getenv("NOTIFICATION_WORKER_THREADS", "2"))

# ============================================================================
# WEBSOCKET SETTINGS
# ============================================================================

# WebSocket Configuration
WEBSOCKET_PING_INTERVAL_SECONDS = int(os.getenv("WEBSOCKET_PING_INTERVAL_SECONDS", "30"))
WEBSOCKET_PING_TIMEOUT_SECONDS = int(os.getenv("WEBSOCKET_PING_TIMEOUT_SECONDS", "10"))
WEBSOCKET_MAX_CONNECTIONS = int(os.getenv("WEBSOCKET_MAX_CONNECTIONS", "100"))

# Statistics Broadcasting
STATISTICS_BROADCAST_INTERVAL_SECONDS = int(os.getenv("STATISTICS_BROADCAST_INTERVAL_SECONDS", "2"))

# ============================================================================
# CORS SETTINGS
# ============================================================================

# CORS Origins
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost:8200,http://localhost:8000,http://localhost:3000,http://localhost:5173")
CORS_ORIGINS: List[str] = [origin.strip() for origin in CORS_ORIGINS_STR.split(",")]
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = ["*"]

# ============================================================================
# LOGGING SETTINGS
# ============================================================================

# Log Levels
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
API_LOG_LEVEL = os.getenv("API_LOG_LEVEL", "INFO")
DATABASE_LOG_LEVEL = os.getenv("DATABASE_LOG_LEVEL", "WARNING")

# Log Formats
LOG_FORMAT = os.getenv("LOG_FORMAT", "json")  # "json" or "text"
LOG_INCLUDE_TIMESTAMP = os.getenv("LOG_INCLUDE_TIMESTAMP", "true").lower() == "true"

# Audit Logging
ENABLE_AUDIT_LOGGING = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true"
AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", "logs/audit.jsonl")

# ============================================================================
# FEATURE TOGGLES
# ============================================================================

# Core Features
ENABLE_FACE_RECOGNITION = os.getenv("ENABLE_FACE_RECOGNITION", "true").lower() == "true"
ENABLE_MOTION_DETECTION = os.getenv("ENABLE_MOTION_DETECTION", "true").lower() == "true"
ENABLE_RECORDING = os.getenv("ENABLE_RECORDING", "true").lower() == "true"
ENABLE_OBJECT_DETECTION = os.getenv("ENABLE_OBJECT_DETECTION", "false").lower() == "true"

# Advanced Features
ENABLE_FACE_CLUSTERING = os.getenv("ENABLE_FACE_CLUSTERING", "true").lower() == "true"
ENABLE_TWO_FACTOR_AUTH = os.getenv("ENABLE_TWO_FACTOR_AUTH", "true").lower() == "true"
ENABLE_AUTOMATIONS = os.getenv("ENABLE_AUTOMATIONS", "true").lower() == "true"
ENABLE_CLOUD_STORAGE = os.getenv("ENABLE_CLOUD_STORAGE", "false").lower() == "true"

# Experimental Features
ENABLE_HARDWARE_ACCELERATION = os.getenv("ENABLE_HARDWARE_ACCELERATION", "false").lower() == "true"
ENABLE_DISTRIBUTED_PROCESSING = os.getenv("ENABLE_DISTRIBUTED_PROCESSING", "false").lower() == "true"

# ============================================================================
# DEVELOPMENT & DEBUG SETTINGS
# ============================================================================

# Environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")  # "development", "staging", "production"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
TESTING = os.getenv("TESTING", "false").lower() == "true"

# Development Helpers
ENABLE_SWAGGER_UI = os.getenv("ENABLE_SWAGGER_UI", "true").lower() == "true"
ENABLE_REDOC = os.getenv("ENABLE_REDOC", "true").lower() == "true"
RELOAD_ON_CHANGE = os.getenv("RELOAD_ON_CHANGE", "true").lower() == "true"

# Security (Development vs Production)
CSRF_PROTECTION_ENABLED = os.getenv("CSRF_PROTECTION_ENABLED", "false").lower() == "true"
IP_WHITELIST_ENABLED = os.getenv("IP_WHITELIST_ENABLED", "false").lower() == "true"
IP_WHITELIST = os.getenv("IP_WHITELIST", "").split(",") if os.getenv("IP_WHITELIST") else []

# ============================================================================
# SERVICE / ECOSYSTEM NETWORKING
# ============================================================================

# Canonical service port. A SINGLE resolved value is used for both the server
# bind and the ecosystem registration, so the registry never advertises a port
# the server is not actually listening on. ECOSYSTEM_SERVICE_PORT always wins so
# the facilitator/user can relocate the service without breaking comms.
DEFAULT_SERVICE_PORT = 8200
SERVICE_BIND_HOST = os.getenv("OPENEYE_BIND_HOST", "0.0.0.0")


def resolve_service_port() -> int:
    """Resolve the canonical OpenEye service port (bind == register).

    Precedence: ECOSYSTEM_SERVICE_PORT -> OPENEYE_PORT -> PORT -> default.
    """
    for var in ("ECOSYSTEM_SERVICE_PORT", "OPENEYE_PORT", "PORT"):
        val = os.getenv(var)
        if val:
            try:
                return int(val)
            except ValueError:
                continue
    return DEFAULT_SERVICE_PORT


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

