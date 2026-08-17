# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
A guard against config.py drifting back into a facade.

81 of the constants in config.py were defined and read by nothing. Some of them
looked exactly like security controls — IP_WHITELIST_ENABLED, the RATE_LIMIT_*
family, SESSION_TIMEOUT_MINUTES — so an operator could set them, believe the
system was hardened, and be wrong. A setting that looks like a control but is
inert is worse than an absent one, because it ends the search for a real one.

This test does not demand that the backlog be cleared. It pins the known-inert
set, so the number can only go down: wiring one up or deleting it makes this
test tell you to remove it from the list, and adding a NEW unread constant fails
the build. The list is the debt, written down where it cannot be forgotten.

Each entry is either *wire it up* or *delete it*. Nothing stays in the middle.
"""

import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "backend" / "core" / "config.py"
BACKEND = CONFIG.parent.parent

# Known inert as of 2026-08-17. SHRINK THIS LIST — never add to it.
KNOWN_INERT = {
    "ALERT_THROTTLE_MINUTES",
    "ALLOWED_FACE_IMAGE_FORMATS",
    "API_LOG_LEVEL",
    "AUDIT_LOG_FILE",
    "CAMERA_READ_TIMEOUT_SECONDS",
    "CAMERA_RECONNECT_DELAY_SECONDS",
    "CLEANUP_SCHEDULER_INTERVAL_HOURS",
    "CLUSTERING_DBSCAN_EPS",
    "CLUSTERING_MIN_SAMPLES",
    "CLUSTERING_MIN_THRESHOLD",
    "CLUSTERING_SCHEDULER_INTERVAL_MINUTES",
    "CORS_ALLOW_CREDENTIALS",
    "CORS_ALLOW_HEADERS",
    "CORS_ALLOW_METHODS",
    "DATABASE_LOG_LEVEL",
    "DEFAULT_RESOLUTION_HEIGHT",
    "DEFAULT_RESOLUTION_WIDTH",
    "ENABLE_AUDIT_LOGGING",
    "ENABLE_AUTO_CLEANUP",
    "ENABLE_CLOUD_STORAGE",
    "ENABLE_DISTRIBUTED_PROCESSING",
    "ENABLE_FACE_CLUSTERING",
    "ENABLE_HARDWARE_ACCELERATION",
    "ENABLE_OBJECT_DETECTION",
    "ENABLE_REDOC",
    "ENABLE_SWAGGER_UI",
    "FACE_DETECTION_MODEL",
    "FACE_DETECTION_UPSAMPLE",
    "FACE_MIN_SIZE_PIXELS",
    "FACE_RECOGNITION_TOLERANCE",
    "GLOBAL_RATE_LIMIT",
    "IP_WHITELIST",
    "IP_WHITELIST_ENABLED",
    "LOG_FORMAT",
    "LOG_LEVEL",
    "LOG_INCLUDE_TIMESTAMP",
    "LOG_RETENTION_DAYS",
    "MAX_ALERTS_PER_HOUR",
    "MAX_CONCURRENT_SESSIONS",
    "MAX_CONCURRENT_UPLOADS",
    "MAX_FACE_IMAGE_SIZE_KB",
    "MAX_RECORDING_DURATION_SECONDS",
    "MAX_REQUEST_SIZE_MB",
    "MAX_STORAGE_GB",
    "MAX_UPLOAD_FILES",
    "MIN_FACE_IMAGE_SIZE_KB",
    "MOTION_BLUR_SIZE",
    "MOTION_HISTORY_FRAMES",
    "MOTION_MIN_AREA_PIXELS",
    "MOTION_RECORDING_POST_BUFFER_SECONDS",
    "MOTION_RECORDING_PRE_BUFFER_SECONDS",
    "MOTION_THRESHOLD",
    "NOTIFICATION_MAX_RETRIES",
    "NOTIFICATION_QUEUE_SIZE",
    "NOTIFICATION_RETRY_DELAY_SECONDS",
    "NOTIFICATION_WORKER_THREADS",
    "RATE_LIMIT_AUTH",
    "RATE_LIMIT_READ",
    "RATE_LIMIT_REDIS_URL",
    "RATE_LIMIT_STORAGE",
    "RATE_LIMIT_STREAM",
    "RATE_LIMIT_WRITE",
    "RECORDING_BUFFER_FRAMES",
    "RECORDING_RETENTION_DAYS",
    "RECORDING_SEGMENT_DURATION_SECONDS",
    "RELOAD_ON_CHANGE",
    "SESSION_TIMEOUT_MINUTES",
    "SNAPSHOT_RETENTION_DAYS",
    "STATISTICS_BROADCAST_INTERVAL_SECONDS",
    "STREAM_BUFFER_SIZE",
    "STREAM_QUALITY",
    "STREAM_TIMEOUT_SECONDS",
    "WARNING_STORAGE_THRESHOLD_PERCENT",
    "WEBSOCKET_MAX_CONNECTIONS",
    "WEBSOCKET_PING_INTERVAL_SECONDS",
    "WEBSOCKET_PING_TIMEOUT_SECONDS",
}


def _defined_constants(text):
    return set(re.findall(r"^\s*([A-Z][A-Z0-9_]{3,})\s*[:=]", text, re.M))


def _is_read_somewhere(name, config_text):
    """Count uses excluding the constant's own definition line.

    The exclusion matters: `X = os.getenv("X")` mentions X twice on one line, so
    a naive count reports every setting as used and the whole facade hides.
    """
    for path in BACKEND.rglob("*.py"):
        text = config_text if path == CONFIG else path.read_text(errors="ignore")
        for line in text.splitlines():
            if path == CONFIG and re.match(r"^\s*" + name + r"\s*[:=]", line):
                continue
            if re.search(r"\b" + name + r"\b", line):
                return True
    return False


def test_no_new_unread_configuration_settings():
    config_text = CONFIG.read_text()
    unread = {n for n in _defined_constants(config_text)
              if not _is_read_somewhere(n, config_text)}

    new = unread - KNOWN_INERT
    assert not new, (
        "New configuration settings are defined but never read: "
        + ", ".join(sorted(new))
        + ". Either read the setting where it belongs, or delete it. A setting "
          "that does nothing still looks to an operator like it does something."
    )


def test_the_inert_list_has_no_stale_entries():
    """Wiring one up (or deleting it) should require removing it from the list."""
    config_text = CONFIG.read_text()
    defined = _defined_constants(config_text)

    now_read = {n for n in KNOWN_INERT if n in defined and _is_read_somewhere(n, config_text)}
    gone = {n for n in KNOWN_INERT if n not in defined}

    assert not now_read, (
        "These are now read and should be removed from KNOWN_INERT: "
        + ", ".join(sorted(now_read)))
    assert not gone, (
        "These no longer exist and should be removed from KNOWN_INERT: "
        + ", ".join(sorted(gone)))


def test_password_policy_settings_are_actually_enforced():
    """The part of the facade already repaired, pinned so it cannot regress."""
    config_text = CONFIG.read_text()
    for name in ("MIN_PASSWORD_LENGTH", "MAX_PASSWORD_LENGTH", "REQUIRE_UPPERCASE",
                 "REQUIRE_LOWERCASE", "REQUIRE_DIGIT", "REQUIRE_SPECIAL_CHAR"):
        assert _is_read_somewhere(name, config_text), f"{name} is not read anywhere"
        assert name not in KNOWN_INERT
