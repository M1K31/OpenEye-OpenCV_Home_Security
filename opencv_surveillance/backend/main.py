# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
OpenEye Surveillance System - Main Application
Complete Phase 2 implementation with face recognition
"""

# CRITICAL: Set environment variables BEFORE any imports to prevent OpenMP conflicts
# Intel libiomp and LLVM libomp can be loaded simultaneously causing threadpoolctl warnings
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

# Suppress warnings for known issues (must be before other imports)
import warnings
# Suppress threadpoolctl warning about OpenMP conflict (informational only, not harmful)
warnings.filterwarnings("ignore", message=".*Found Intel OpenMP.*LLVM OpenMP.*", category=RuntimeWarning)
# Suppress pkg_resources deprecation warning from face_recognition_models (external package)
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

# Apply pkg_resources patch BEFORE any imports that use face_recognition
from backend.core.pkg_resources_patch import patch_face_recognition_models
patch_face_recognition_models()

import uvicorn
import logging
import asyncio
import signal
import sys
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
# Load configuration BEFORE importing any other backend.* module. auth.py,
# database.session and others read os.getenv(...) at import time; if this runs
# after those imports the values are ignored (it previously ran ~55 lines too
# late, so the installer's SECRET_KEY/JWT_SECRET_KEY never took effect). See
# audit F-02 addendum.
#
# This reads the data root's config.env, falling back to the legacy .env beside
# the code, with the real process environment always winning. It replaces a bare
# load_dotenv(), which looked for .env relative to the *working directory* — so
# a launch agent, login item or application bundle got no configuration at all
# and came up without a signing key.
from backend.core.config_loader import load_configuration
load_configuration()

from backend.database.session import engine, SessionLocal
from backend.core.auth import get_current_active_user, get_current_user_media
from backend.database.utils import get_db_context
from backend.database import models, alert_models
from backend.api.routes import (
    users,
    cameras,
    faces,
    face_history,
    alerts,
    integrations,
    recordings,
    analytics,
    discovery,
    setup,
    websockets,
    settings,
    motion_events,
    clusters,
    automations,
    two_way_audio,
    timeline,
    metrics,
    notification_providers,
    two_factor_auth,
    motion_zones,
    ptz,
    hardware,
    features,
    objects,  # v3.10.0: Object detection routes
    ecosystem,  # v3.11.0: Ecosystem integration (MagicMirror, mobile apps,
    network_discovery,  # v3.11.4: Network discovery with Fing integration
    scheduled_tasks,  # v3.12.0: Scheduled tasks (retraining, retroactive search)
    license_plates,  # v3.11.7: License plate recognition (ALPR)
    ai_providers,  # cloud AI provider keys + per-task routing
)
from backend.core.camera_manager import manager as camera_manager
from backend.core.websocket_manager import broadcast_statistics_update
from backend.core.face_recognition import get_face_manager
from backend.core.statistics_broadcaster import get_broadcaster
from backend.core.clustering_scheduler import get_clustering_scheduler
from backend.core.scheduled_tasks import get_scheduled_tasks_manager
from backend.middleware.rate_limiter import RateLimiter
from backend.middleware.endpoint_rate_limiter import EndpointRateLimiter
from backend.middleware.csrf_protection import CSRFProtection
from backend.middleware.security import (
    SecurityHeadersMiddleware,
    IPWhitelistMiddleware,
    SQLInjectionProtection,
)
from backend.middleware.performance import PerformanceMonitoringMiddleware
from backend.core.audit_logger import get_audit_logger
from backend.core.two_way_audio_system import audio_manager

# (.env is loaded above, before the backend imports.)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global shutdown flag
shutdown_in_progress = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_in_progress
    if shutdown_in_progress:
        logger.warning(f"Signal {signum} received but shutdown already in progress")
        return
    
    signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    logger.info(f"Received {signal_name}, initiating graceful shutdown...")
    shutdown_in_progress = True
    
    # Trigger FastAPI shutdown
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Initialize FastAPI application
app = FastAPI(
    title="OpenEye Surveillance System",
    description="OpenCV-powered surveillance system with face recognition, motion detection, and video recording",
    version="3.11.8",  # Face-Management Workflow & Stability
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS - Load allowed origins from environment
# v3.11.0: Added MagicMirror default port (8080) for ecosystem integration
# v3.11.1: Support for dynamic ecosystem origins and custom ports
CORS_ORIGINS_STR = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:3000,http://localhost:8080,"
    "http://127.0.0.1:8000,http://127.0.0.1:3000,http://127.0.0.1:8080"  # Dev defaults + MagicMirror
)
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

# Add MagicMirror port from environment if set
MAGICMIRROR_PORT = os.getenv("MAGICMIRROR_PORT")
if MAGICMIRROR_PORT:
    CORS_ORIGINS.extend([
        f"http://localhost:{MAGICMIRROR_PORT}",
        f"http://127.0.0.1:{MAGICMIRROR_PORT}"
    ])

# Ecosystem mode (audit F-08): a wildcard origin ('*') must never be combined
# with allow_credentials=True — that exposes the authenticated API to any
# website the user visits. Instead, the operator supplies an explicit regex of
# trusted origins. If ecosystem mode is enabled without a regex we FAIL SAFE:
# keep the strict allowlist rather than opening a credentialed wildcard.
CORS_ALLOW_ECOSYSTEM = os.getenv("CORS_ALLOW_ECOSYSTEM", "false").lower() == "true"
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None

allow_origin_regex = None
if CORS_ALLOW_ECOSYSTEM:
    if CORS_ORIGIN_REGEX:
        allow_origin_regex = CORS_ORIGIN_REGEX
        logger.warning(
            "CORS_ALLOW_ECOSYSTEM=true: allowing origins matching CORS_ORIGIN_REGEX=%s",
            CORS_ORIGIN_REGEX,
        )
    else:
        logger.critical(
            "CORS_ALLOW_ECOSYSTEM=true but CORS_ORIGIN_REGEX is unset. Refusing to "
            "enable a credentialed wildcard origin. Set CORS_ORIGIN_REGEX "
            r"(e.g. 'https://.*\.mydomain\.com') to allow ecosystem origins. "
            "Falling back to the strict CORS allowlist."
        )

logger.info(f"CORS origins configured: {CORS_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Phase 6: Add security middleware (all free and open source)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SQLInjectionProtection)

# v3.6.0: Enhanced security features
# Per-endpoint rate limiting (replaces global RateLimiter)
app.add_middleware(EndpointRateLimiter, custom_limits={
    "auth": (10, 60),  # 10 auth requests per minute
    "write": (30, 60),  # 30 write operations per minute
    "read": (100, 60),  # 100 read operations per minute
    "stream": (500, 60),  # 500 streaming requests per minute
})

# CSRF protection — DELIBERATELY NOT ENABLED (see docs/development/ADR-001-csrf.md).
# OpenEye authenticates every state-changing request with a bearer JWT sent in
# the Authorization header (not an ambient cookie), so classic CSRF does not
# apply: a cross-site request cannot attach the token. The CSRFProtection
# middleware is retained for a future cookie/session-based auth mode. If you add
# any cookie-based authentication, enable it here:
#     app.add_middleware(CSRFProtection)
_CSRF_ENABLED = os.getenv("ENABLE_CSRF_PROTECTION", "false").lower() == "true"
if _CSRF_ENABLED:
    app.add_middleware(CSRFProtection)
    logger.info("CSRF protection enabled (ENABLE_CSRF_PROTECTION=true)")

# Performance monitoring middleware
app.add_middleware(
    PerformanceMonitoringMiddleware,
    slow_request_threshold_ms=1000.0  # Log requests taking > 1 second
)

# Optional: IP whitelist (disabled by default for ease of use)
# To enable, uncomment and add your allowed IPs:
# app.add_middleware(IPWhitelistMiddleware, allowed_ips=["127.0.0.1", "192.168.1.100"])

# ============================================================================
# MOUNT STATIC FILES EARLY (before routes to ensure proper precedence)
# ============================================================================
# These mounts MUST be defined before the catch-all SPA route
# to ensure FastAPI routes requests to static files correctly

# Import centralized path manager
from backend.core.paths import paths

# Storage is served through routes that resolve the directory PER REQUEST, not
# through StaticFiles mounts bound at import.
#
# StaticFiles captures its `directory` argument the moment the mount is created,
# which is import time — before the startup event applies the storage paths saved
# in the database (see the update_paths call further down this file), and long
# before a user changes them in System Settings. Both of those call
# paths.update_paths(), and neither could reach a mount that had already
# memorised the old directory.
#
# That was not theoretical. The /faces mount bound to the environment's faces
# directory; startup then applied the database's `faces_path` and FaceManager was
# created afterwards, so it WROTE to a different directory than the mount SERVED
# from. Result: 17,699 face images on disk and every single one 404ing in the UI,
# which is what made person galleries look empty and "photos: 0" look like data
# loss. Snapshots escaped only because the startup call happens to omit
# snapshots_dir, so writer and reader stayed accidentally consistent.
#
# Resolving per request means the served directory always matches the one being
# written to, including after a runtime path change with no restart.


def _serve_from(base_dir_getter, relative_path: str):
    """
    Serve a file from a storage directory resolved at request time.

    base_dir_getter is a callable rather than a path so the CURRENT value of
    paths.* is read on every request; capturing the value here would rebuild the
    exact bug this replaces.
    """
    base = Path(str(base_dir_getter())).resolve()
    candidate = (base / relative_path).resolve()

    # Containment check. These paths come straight from the URL, so without it
    # "../../.." walks anywhere the process can read.
    if candidate != base and base not in candidate.parents:
        raise HTTPException(status_code=404, detail="Not found")

    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(str(candidate))


# Every route below serves real footage, face images or snapshots off disk, so
# each one requires an authenticated viewer.
#
# These were reachable anonymously until 2026-08-20. The 2026-08-02 audit secured
# the `recordings` ROUTER but not these, because they are declared on `app`
# rather than on a router and so were invisible to a per-router review. Guessing
# a name was not hard either — snapshots are written as
# `{camera_id}_{YYYYmmdd_HHMMSS}.jpg`, which is enumerable by timestamp.
#
# get_current_user_media (not get_current_active_user) is the right dependency
# here: <img> and <video> tags cannot send an Authorization header, so it also
# accepts the SameSite=Strict access_token cookie. See ADR-001.
@app.get("/recordings/{file_path:path}", include_in_schema=False)
def serve_recording_file(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.recordings_dir, file_path)


@app.get("/faces/{file_path:path}", include_in_schema=False)
def serve_face_file(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.faces_dir, file_path)


@app.get("/api/snapshots/{file_path:path}", include_in_schema=False)
def serve_snapshot_file(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.snapshots_dir, file_path)


# Legacy snapshot paths, kept because stored snapshot_path values in the database
# still carry them.
@app.get("/data/snapshots/{file_path:path}", include_in_schema=False)
def serve_snapshot_file_legacy_data(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.snapshots_dir, file_path)


@app.get("/legacy/snapshots/{file_path:path}", include_in_schema=False)
def serve_snapshot_file_legacy(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.snapshots_dir, file_path)


@app.get("/data/thumbnails/{file_path:path}", include_in_schema=False)
def serve_thumbnail_file(file_path: str, current_user=Depends(get_current_user_media)):
    return _serve_from(lambda: paths.thumbnails_dir, file_path)


def _log_storage_layout():
    """
    Log both roots and every storage location with a file count.

    Deliberately reports counts rather than just paths: a path that looks right
    but holds nothing is the shape this problem actually takes, and it reads as
    normal in a log full of directory names.
    """
    from backend.core.paths import APP_ROOT, DATA_ROOT, paths as storage
    from backend.database.session import SQLALCHEMY_DATABASE_URL

    def describe(path):
        try:
            target = Path(path)
            if not target.exists():
                return "MISSING"
            count = sum(1 for _ in target.rglob("*") if _.is_file())
            return f"{count} files"
        except OSError as e:
            return f"unreadable ({e})"

    logger.info("Storage layout:")
    logger.info(f"  app root  (shipped code) : {APP_ROOT}")
    logger.info(f"  data root (writable)     : {DATA_ROOT}")
    logger.info(f"  database                 : {SQLALCHEMY_DATABASE_URL}")
    for label, value in (
        ("faces", storage.faces_dir),
        ("recordings", storage.recordings_dir),
        ("snapshots", storage.snapshots_dir),
        ("thumbnails", storage.thumbnails_dir),
    ):
        inside = "" if str(value).startswith(str(DATA_ROOT)) else "  <- OUTSIDE THE DATA ROOT"
        logger.info(f"  {label:<24} : {value} ({describe(value)}){inside}")

    try:
        from backend.core.storage_migration import build_plan

        plan = build_plan()
        if not plan.is_noop:
            logger.warning(
                "Storage is split across locations. %s item(s) are not under the "
                "data root; run the storage migration to consolidate them.",
                len(plan.items),
            )
    except Exception as e:
        logger.debug(f"Could not evaluate migration state: {e}")


@app.on_event("startup")
async def startup_event():
    """
    On startup, create database tables and add default cameras.
    """
    logger.info("Starting OpenEye Surveillance System...")

    # Tables first, migrations second. This order matters and used to be the
    # other way round.
    #
    # No migration creates the `cameras` table — or most of the others. The base
    # schema comes from create_all(); the migration chain only applies
    # increments on top of it and assumes those tables already exist. Running
    # alembic first therefore failed on a fresh database ("no such table:
    # cameras"), the failure was swallowed as "non-critical", and
    # alembic_version was never stamped. Every later start repeated it, so the
    # chain could never advance and every column-adding migration silently did
    # nothing.
    logger.info("Ensuring database tables exist...")
    models.Base.metadata.create_all(bind=engine)
    alert_models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified successfully")

    logger.info("Running database migrations...")
    try:
        from alembic.config import Config
        from alembic import command
        from sqlalchemy import inspect as sa_inspect

        alembic_cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))

        inspector = sa_inspect(engine)
        tables = set(inspector.get_table_names())

        if "alembic_version" not in tables and tables:
            # create_all() just built the schema from the current models, so
            # every migration in the chain is already satisfied by definition.
            # Stamping records that fact; running the chain instead would try to
            # create tables that exist. This is the case that previously left an
            # install permanently unversioned.
            command.stamp(alembic_cfg, "head")
            logger.info("Database schema built from models; stamped at head")
        else:
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed successfully")
    except Exception as e:
        # Not "non-critical". A failed migration is precisely why schema changes
        # stop landing, and calling it harmless is how that went unnoticed
        # through several releases. The startup column-adder below is a backstop
        # for the columns it knows about, not a substitute for this working.
        logger.error(
            "DATABASE MIGRATION FAILED — schema changes will not be applied: %s", e)
        logger.error(
            "The application will continue, but any migration after the failure "
            "point has not run. This needs investigation.")
    
    # Add missing columns for audio recording (migration)
    logger.info("Checking for database schema updates...")
    try:
        from sqlalchemy import text, inspect
        inspector = inspect(engine)
        
        # Check if cameras table exists
        if 'cameras' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('cameras')]
            
            if 'audio_recording_enabled' not in columns:
                logger.info("Adding audio_recording_enabled column to cameras table...")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN audio_recording_enabled BOOLEAN DEFAULT 0"))
                    conn.commit()
                logger.info("✅ Added audio_recording_enabled column")
            
            if 'audio_device' not in columns:
                logger.info("Adding audio_device column to cameras table...")
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE cameras ADD COLUMN audio_device TEXT"))
                    conn.commit()
                logger.info("✅ Added audio_device column")

            # Capture policy (v3.12). These control what a recognised face
            # leaves behind — never whether it is recognised, and never whether
            # it triggers automation. Defaults match the shipped policy, so an
            # upgraded install starts behaving economically without any action.
            capture_columns = (
                ("face_capture_mode", "TEXT DEFAULT 'system_default'"),
                ("recognition_requires_motion", "BOOLEAN DEFAULT 1"),
                ("recognition_motion_window_seconds", "INTEGER DEFAULT 30"),
            )
            for column_name, definition in capture_columns:
                if column_name in columns:
                    continue
                logger.info(f"Adding {column_name} column to cameras table...")
                with engine.connect() as conn:
                    conn.execute(text(
                        f"ALTER TABLE cameras ADD COLUMN {column_name} {definition}"
                    ))
                    conn.commit()
                logger.info(f"✅ Added {column_name} column")

        # Cluster promotion (v3.12). Records when a cluster stopped being a
        # group of similar faces and became a profile the recogniser can name.
        #
        # Carried here as well as in alembic because create_all() only creates
        # missing TABLES — it will not add a column to a table that already
        # exists — and an install whose alembic history is behind never reaches
        # the migration. Without this the column silently never appears and
        # every cluster read fails on an unknown column.
        if 'face_clusters' in inspector.get_table_names():
            cluster_columns = [col['name'] for col in inspector.get_columns('face_clusters')]
            if 'trained_at' not in cluster_columns:
                logger.info("Adding trained_at column to face_clusters table...")
                with engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE face_clusters ADD COLUMN trained_at DATETIME"
                    ))
                    # Backfill from the two flags the promotion path sets
                    # together. Inference, not record — but it is the only
                    # evidence available for clusters promoted before this
                    # column existed, and it errs towards "already trained",
                    # which preserves behaviour instead of making established
                    # clusters suddenly resume collecting faces.
                    conn.execute(text(
                        "UPDATE face_clusters "
                        "SET trained_at = COALESCE(updated_at, created_at) "
                        "WHERE is_identified = 1 AND label IS NOT NULL AND label != ''"
                    ))
                    conn.commit()
                logger.info("✅ Added trained_at column and backfilled promoted clusters")

        # Storage thinning (v3.12). Recorded here as well as in alembic for the
        # same reason as trained_at: create_all() adds tables, never columns.
        if 'recording_events' in inspector.get_table_names():
            recording_columns = [c['name'] for c in inspector.get_columns('recording_events')]
            if 'media_state' not in recording_columns:
                logger.info("Adding media_state column to recording_events table...")
                with engine.connect() as conn:
                    conn.execute(text(
                        "ALTER TABLE recording_events ADD COLUMN media_state TEXT "
                        "DEFAULT 'present'"
                    ))
                    conn.execute(text(
                        "UPDATE recording_events SET media_state = 'present' "
                        "WHERE media_state IS NULL"
                    ))
                    conn.commit()
                logger.info("✅ Added media_state column")

        # Person identity (v3.12). Added at startup as well as in alembic for
        # the same reason as trained_at and media_state: create_all() creates
        # missing TABLES, so it makes `persons`, but it will never add
        # person_id to tables that already exist.
        for table, column in (("face_detection_events", "person_id"),
                              ("face_clusters", "person_id")):
            if table in inspector.get_table_names():
                columns = [c['name'] for c in inspector.get_columns(table)]
                if column not in columns:
                    logger.info("Adding %s column to %s table...", column, table)
                    with engine.connect() as conn:
                        conn.execute(text(
                            f"ALTER TABLE {table} ADD COLUMN {column} INTEGER"))
                        conn.commit()
                    logger.info("✅ Added %s to %s", column, table)
    except Exception as e:
        logger.warning(f"Schema migration check failed (non-critical): {e}")

    # Enable query profiling if configured
    import os
    if os.getenv("ENABLE_QUERY_PROFILING", "false").lower() == "true":
        logger.info("Enabling database query profiling...")
        from backend.middleware.query_profiler import enable_query_profiling
        slow_threshold = float(os.getenv("SLOW_QUERY_THRESHOLD_MS", "100"))
        enable_query_profiling(slow_query_threshold_ms=slow_threshold)
        logger.info(f"Query profiling enabled (threshold: {slow_threshold}ms)")

    # Initialize system settings with defaults
    # FIXED: Use context manager to prevent session leak (v3.6.0.1)
    with get_db_context() as db:
        from backend.database import crud

        crud.initialize_default_settings(db)
        settings_list = crud.get_all_system_settings(db)

        # Convert list to dictionary
        system_settings = {}
        for setting in settings_list:
            try:
                if setting.setting_type == "int":
                    system_settings[setting.setting_key] = int(
                        setting.setting_value)
                elif setting.setting_type == "float":
                    system_settings[setting.setting_key] = float(
                        setting.setting_value)
                elif setting.setting_type == "boolean":
                    system_settings[setting.setting_key] = (
                        setting.setting_value.lower() == "true"
                    )
                else:
                    system_settings[setting.setting_key] = setting.setting_value
            except (ValueError, AttributeError):
                system_settings[setting.setting_key] = setting.setting_value

        # Get configured paths from database (if they exist)
        # These will override PathManager defaults if set
        db_recordings_path = system_settings.get("recordings_path")
        db_faces_path = system_settings.get("faces_path")
        # snapshots_path was stored by the settings API but never applied here,
        # so snapshots alone followed the environment while recordings and faces
        # followed the database — the application read its own media from two
        # different roots depending on the type, which is how 16 GB of snapshots
        # ended up somewhere the rest of the storage was not.
        db_snapshots_path = system_settings.get("snapshots_path")

        # Update PathManager with database settings if they exist
        if db_recordings_path or db_faces_path or db_snapshots_path:
            logger.info("Applying custom paths from database settings...")
            paths.update_paths(
                recordings_dir=db_recordings_path,
                snapshots_dir=db_snapshots_path,
                faces_dir=db_faces_path
            )

        logger.info(
            f"System settings loaded - Recordings: {paths.recordings_dir}, Faces: {paths.faces_dir}")

    # Print the storage layout, with counts, every time.
    #
    # The reason this exists: for months this installation kept its database and
    # galleries beside the code while its snapshots sat somewhere else entirely,
    # and nothing ever said so. Each directory was resolved independently and
    # logged separately, so the split was invisible. A single block naming both
    # roots and what is actually in each makes that class of divergence obvious
    # the moment it happens, instead of after a user reports missing photos.
    _log_storage_layout()

    # PathManager automatically creates all required directories
    logger.info("Required directories handled by PathManager")

    # Initialize face recognition manager with configured path (uses PathManager default)
    logger.info(
        f"Initializing face recognition with faces directory: {paths.faces_dir}")
    face_manager = get_face_manager()  # Uses paths.faces_dir by default
    logger.info(
        f"Face recognition initialized: {len(face_manager.known_face_names)} known faces"
    )

    # Note: people left without encodings by the older code are NOT repaired
    # automatically here. The defects that created them are fixed going forward,
    # and rewriting existing galleries on every boot would modify a user's data
    # without them asking. POST /api/faces/repair-encodings does it on request.

    # Load existing cameras from database
    logger.info("Loading cameras from database...")
    # Load cameras SYNCHRONOUSLY here on the main thread. On macOS the camera open
    # goes through AVFoundation, which MUST be initialised on the process main thread
    # (the ASGI startup runs there) — opening it from a worker thread segfaults. The
    # per-camera open in camera_manager already bounds itself with a short retry loop,
    # so a missing/busy device delays startup by a few seconds at most rather than
    # blocking forever; unavailable cameras are reported and the server continues.
    # FIXED: Use context manager to prevent session leak (v3.6.0.1)
    with get_db_context() as db:
        from backend.database import crud

        db_cameras = crud.get_active_cameras(db)
        loaded_count = 0
        failed_cameras = []  # Track failed cameras for summary

        for db_camera in db_cameras:
            if not camera_manager.get_camera(db_camera.camera_id):
                try:
                    success, message = camera_manager.add_camera(
                        camera_id=db_camera.camera_id,
                        camera_type=db_camera.camera_type,
                        source=db_camera.source,
                        enable_face_detection=db_camera.face_detection_enabled,
                    )
                    if success:
                        loaded_count += 1
                        logger.info(
                            f"✓ Loaded camera '{db_camera.camera_id}' from database")
                    else:
                        failed_cameras.append({
                            "id": db_camera.camera_id,
                            "type": db_camera.camera_type,
                            "source": db_camera.source,
                            "reason": message
                        })
                        # Keep trying in the background. Without this a startup
                        # failure was permanent for the life of the process and
                        # a human had to click reconnect — which is no good for
                        # an appliance that boots before its camera is ready.
                        camera_manager.register_pending_camera(
                            camera_id=db_camera.camera_id,
                            camera_type=db_camera.camera_type,
                            source=db_camera.source,
                            enable_face_detection=db_camera.face_detection_enabled,
                            reason=message,
                        )
                except Exception as e:
                    failed_cameras.append({
                        "id": db_camera.camera_id,
                        "type": db_camera.camera_type,
                        "source": db_camera.source,
                        "reason": str(e)
                    })
                    camera_manager.register_pending_camera(
                        camera_id=db_camera.camera_id,
                        camera_type=db_camera.camera_type,
                        source=db_camera.source,
                        enable_face_detection=db_camera.face_detection_enabled,
                        reason=str(e),
                    )

        # Summary logging
        total_cameras = len(db_cameras)
        if failed_cameras:
            logger.warning("=" * 60)
            logger.warning(f"CAMERA STARTUP SUMMARY: {loaded_count}/{total_cameras} cameras loaded")
            camera_manager.start_pending_camera_retries()
            logger.warning("=" * 60)
            for cam in failed_cameras:
                logger.warning(f"  ✗ {cam['id']} ({cam['type']}): {cam['reason']}")
            logger.warning("-" * 60)
            logger.warning("Server will continue running. Unavailable cameras can be")
            logger.warning("reconnected via the web interface when devices are ready.")
            logger.warning("=" * 60)
        else:
            logger.info(f"✓ All {loaded_count} camera(s) loaded successfully")

    # Start statistics broadcaster
    logger.info("Starting statistics broadcaster...")
    broadcaster = get_broadcaster()
    await broadcaster.start()
    logger.info("Statistics broadcaster started successfully")

    # Start face clustering scheduler
    logger.info("Starting face clustering scheduler...")
    clustering_scheduler = get_clustering_scheduler()
    await clustering_scheduler.start()
    logger.info(
        f"Face clustering scheduler started successfully "
        f"(interval: {clustering_scheduler.interval_minutes}min, "
        f"threshold: {clustering_scheduler.min_faces_threshold} faces)"
    )

    # Start scheduled tasks manager (v3.12.0)
    logger.info("Starting scheduled tasks manager...")
    tasks_manager = get_scheduled_tasks_manager()
    await tasks_manager.start()
    stats = tasks_manager.get_statistics()
    logger.info(
        f"Scheduled tasks manager started successfully "
        f"({stats['enabled_tasks']} enabled tasks)"
    )

    # v3.6.0: Initialize audit logging
    logger.info("Initializing audit logging...")
    audit_logger = get_audit_logger()
    from backend.core.audit_logger import AuditEventType
    audit_logger.log_event(
        AuditEventType.SYSTEM_STARTUP,
        details={
            "version": "3.11.4",
            "cameras_loaded": loaded_count,
            "known_faces": len(face_manager.known_face_names)
        }
    )
    logger.info("Audit logging initialized")

    # Static file directories are now mounted at application startup (before routes)
    # This ensures they take precedence over the catch-all SPA route
    logger.info("Static file directories already mounted during app initialization")
    logger.info(f"✓ Recordings directory: {paths.recordings_dir}")
    logger.info(f"✓ Faces directory: {paths.faces_dir}")
    logger.info(f"✓ Snapshots directory: {paths.snapshots_dir}")
    logger.info(f"✓ Legacy snapshots directory: {paths.snapshots_dir}")
    logger.info(f"✓ Thumbnails directory: {paths.thumbnails_dir}")

    # Hardware-Aware Feature Auto-Configuration (v3.7.0)
    logger.info("🔍 Scanning hardware and configuring features...")
    try:
        from backend.core.feature_manager import get_feature_manager
        feature_manager = get_feature_manager()
        scan_result = feature_manager.scan_and_configure_features(
            scan_type="startup",
            scanned_by="system",
            notify_changes=False  # Don't notify on first startup
        )
        logger.info(
            f"✓ Hardware scan complete: {scan_result['hardware_tier']} tier "
            f"({scan_result['features_enabled']} features enabled, "
            f"{scan_result['features_disabled']} disabled)"
        )
        if scan_result.get('changes_detected'):
            logger.warning(f"Hardware changes detected: {scan_result.get('changes_summary')}")
    except Exception as e:
        logger.warning(f"Hardware scan failed (non-critical): {e}")
        logger.info("Features will use default configuration. Run manual scan to configure.")

    logger.info("OpenEye Surveillance System started successfully!")
    logger.info(
        "Features enabled: Motion Detection, Face Recognition, Video Recording, "
        "Real-time WebSocket Updates, Automated Face Clustering, Enhanced Security, "
        "Hardware-Aware Auto-Configuration (v3.7.0)"
    )

    # Register the app event loop so camera threads can dispatch notifications
    import asyncio as _asyncio
    from backend.core import notification_dispatch
    notification_dispatch.set_app_loop(_asyncio.get_running_loop())

    # Ecosystem integration (standalone no-op when registry unavailable)
    try:
        from ecosystem_client import EcosystemClient
        from backend.core.config import resolve_service_port
        eco = EcosystemClient(
            service_name="openeye",
            service_port=resolve_service_port(),  # same value the server binds
            health_endpoint="/api/health",
            priority=50,  # Fallback ecosystem manager
        )
        await eco.start()
        app.state.ecosystem = eco
        logger.info(f"Ecosystem client started in {eco.mode.value} mode")
    except Exception as e:
        logger.debug(f"Ecosystem client not available: {e}")
        app.state.ecosystem = None


@app.on_event("shutdown")
async def shutdown_event():
    """
    Enhanced shutdown sequence - ensures all resources are properly cleaned up.
    Addresses issue where daemon threads and processes remain running after shutdown.
    """
    global shutdown_in_progress
    shutdown_in_progress = True

    logger.info("=" * 60)
    logger.info("Shutting down OpenEye Surveillance System...")
    logger.info("=" * 60)

    # Ecosystem cleanup
    if getattr(app.state, "ecosystem", None):
        try:
            await app.state.ecosystem.stop()
        except Exception:
            pass

    # Step 1: Stop face clustering scheduler
    try:
        logger.info("[1/10] Stopping face clustering scheduler...")
        clustering_scheduler = get_clustering_scheduler()

        # Set timeout for scheduler stop
        stop_task = asyncio.create_task(clustering_scheduler.stop())
        await asyncio.wait_for(stop_task, timeout=5.0)
        logger.info("✓ Face clustering scheduler stopped successfully")
    except asyncio.TimeoutError:
        logger.error("✗ Face clustering scheduler stop timed out after 5s")
    except Exception as e:
        logger.error(f"✗ Error stopping face clustering scheduler: {e}")

    # Step 2: Stop scheduled tasks manager
    try:
        logger.info("[2/10] Stopping scheduled tasks manager...")
        tasks_manager = get_scheduled_tasks_manager()

        # Set timeout for manager stop
        stop_task = asyncio.create_task(tasks_manager.stop())
        await asyncio.wait_for(stop_task, timeout=5.0)
        logger.info("✓ Scheduled tasks manager stopped successfully")
    except asyncio.TimeoutError:
        logger.error("✗ Scheduled tasks manager stop timed out after 5s")
    except Exception as e:
        logger.error(f"✗ Error stopping scheduled tasks manager: {e}")

    # Step 3: Stop statistics broadcaster (WebSocket updates)
    try:
        logger.info("[3/10] Stopping statistics broadcaster...")
        broadcaster = get_broadcaster()

        # Set timeout for broadcaster stop
        stop_task = asyncio.create_task(broadcaster.stop())
        await asyncio.wait_for(stop_task, timeout=5.0)
        logger.info("✓ Statistics broadcaster stopped successfully")
    except asyncio.TimeoutError:
        logger.error("✗ Statistics broadcaster stop timed out after 5s")
    except Exception as e:
        logger.error(f"✗ Error stopping statistics broadcaster: {e}")

    # Step 3: Close all WebSocket connections
    try:
        logger.info("[3/9] Closing WebSocket connections...")
        from backend.core.websocket_manager import ws_manager

        # Close all connections gracefully
        if hasattr(ws_manager, 'disconnect_all'):
            await ws_manager.disconnect_all()
            logger.info("✓ All WebSocket connections closed")
        else:
            logger.warning("⚠ WebSocket manager doesn't have disconnect_all method")
    except Exception as e:
        logger.error(f"✗ Error closing WebSocket connections: {e}")

    # Step 4: Stop all cameras and release resources
    try:
        logger.info("[4/9] Stopping all cameras...")
        camera_count = len(camera_manager.cameras)

        for camera_id in list(camera_manager.cameras.keys()):
            try:
                camera_manager.remove_camera(camera_id)
                logger.debug(f"  Stopped camera: {camera_id}")
            except Exception as e:
                logger.error(f"  Error stopping camera {camera_id}: {e}")

        camera_manager.stop_pending_camera_retries()
        logger.info(f"✓ Stopped {camera_count} camera(s)")
    except Exception as e:
        logger.error(f"✗ Error stopping cameras: {e}")

    # Step 5: Face recognition uses stateless get_face_manager() - no cleanup needed
    logger.info("[5/9] Face recognition uses stateless manager - skipping")

    # Step 6: Stop two-way audio sessions
    try:
        logger.info("[6/9] Stopping two-way audio sessions...")
        await audio_manager.close_all()
        logger.info("✓ Two-way audio sessions stopped")
    except Exception as e:
        logger.error(f"✗ Error stopping audio sessions: {e}")

    # Step 7: Stop cloud storage upload threads
    #
    # cloud_storage_system defines CloudStorageManager but nothing in the
    # application ever constructs one — the only instantiation is inside that
    # module's `if __name__ == "__main__"` example. This step previously did
    # `from backend.core.cloud_storage_system import cloud_storage`, a name that
    # does not exist, so it raised ImportError on every shutdown and was hidden
    # by the except below.
    #
    # Rather than import a name that cannot exist, look for a manager the
    # application actually registered. When cloud storage is wired up it should
    # publish its manager on app.state, and this step will start doing real work
    # without further change.
    try:
        logger.info("[7/9] Stopping cloud storage threads...")
        storage_manager = getattr(app.state, "cloud_storage", None)
        if storage_manager is None:
            logger.info("✓ No cloud storage manager active - nothing to stop")
        elif hasattr(storage_manager, "stop_upload_worker"):
            storage_manager.stop_upload_worker()
            logger.info("✓ Cloud storage threads stopped")
        else:
            logger.warning("⚠ Cloud storage manager has no stop_upload_worker method")
    except Exception as e:
        logger.error(f"✗ Error stopping cloud storage: {e}")

    # Step 8: Close database connections
    #
    # Imported from backend.database.session, which is where the engine lives —
    # backend.database does not export it, so this step raised ImportError on
    # every shutdown and dispose() never ran. Connections were released by
    # process death instead of closed.
    #
    # Imported here rather than used from the module-level import at the top so
    # that a test can substitute the engine and observe dispose() being called.
    try:
        logger.info("[8/9] Closing database connections...")
        from backend.database.session import engine

        if engine:
            engine.dispose()
            logger.info("✓ Database connections closed")
    except Exception as e:
        logger.error(f"✗ Error closing database: {e}")

    # Step 9: Cancel all remaining async tasks
    try:
        logger.info("[9/9] Canceling remaining async tasks...")

        # Excluding this handler's own task is the whole point. asyncio
        # all_tasks() includes the coroutine doing the cancelling, so the
        # previous version cancelled itself and then awaited its own
        # cancellation. That raised CancelledError, which inherits from
        # BaseException rather than Exception, so the handler below never caught
        # it — every quit ended in a traceback, and anything after this step was
        # skipped.
        current = asyncio.current_task()
        tasks = [
            task for task in asyncio.all_tasks()
            if task is not current and not task.done()
        ]

        if tasks:
            logger.info(f"  Found {len(tasks)} pending task(s)")
            for task in tasks:
                task.cancel()

            # return_exceptions collects each task's CancelledError as a result
            # instead of re-raising it here. Cancelling is what was asked for, so
            # the tasks reporting that they were cancelled is success.
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=3.0)
            logger.info("✓ Async tasks canceled")
        else:
            logger.info("✓ No pending async tasks")
    except asyncio.TimeoutError:
        logger.warning("⚠ Some async tasks did not stop within 3s")
    except asyncio.CancelledError:
        # The loop is being torn down around us. Nothing left to clean up, and
        # propagating turns an orderly shutdown into a traceback.
        logger.info("✓ Shutdown interrupted by loop teardown")
    except Exception as e:
        logger.error(f"✗ Error canceling async tasks: {e}")

    # v3.6.0: Log shutdown event to audit log
    try:
        logger.info("Logging shutdown event to audit log...")
        audit_logger = get_audit_logger()
        from backend.core.audit_logger import AuditEventType
        audit_logger.log_event(AuditEventType.SYSTEM_SHUTDOWN)
        logger.info("✓ Shutdown event logged")
    except Exception as e:
        logger.error(f"✗ Error logging shutdown event: {e}")

    logger.info("=" * 60)
    logger.info("OpenEye Surveillance System shutdown complete")
    logger.info("=" * 60)


# Include all API routers (ONCE)
app.include_router(users.router, prefix="/api", tags=["Authentication"])

# v3.6.0: Two-Factor Authentication
app.include_router(two_factor_auth.router, prefix="/api/auth/2fa", tags=["Two-Factor Authentication"])

# Camera Discovery - MUST be before /api/cameras to avoid route conflicts
app.include_router(
    discovery.router,
    prefix="/api",
    dependencies=[Depends(get_current_active_user)], tags=["Camera Discovery"])

app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])

app.include_router(faces.router, prefix="/api", tags=["Face Recognition"])

app.include_router(
    face_history.router, prefix="/api/faces", tags=["Face Detection History"]
)

# Face Clustering - NEW for AI-powered face grouping
app.include_router(clusters.router, prefix="/api", tags=["Face Clustering"])

app.include_router(
    alerts.router,
    prefix="/api",
    tags=["Alerts & Notifications"])

app.include_router(
    integrations.router,
    prefix="/api",
    tags=["Smart Home Integrations"])

# Phase 6: New routers for advanced features
app.include_router(
    recordings.router,
    prefix="/api",
    tags=["Recordings & Playback"])

app.include_router(
    analytics.router,
    prefix="/api",
    dependencies=[Depends(get_current_active_user)], tags=["Advanced Analytics"])

# Motion Detection Events - NEW
app.include_router(
    motion_events.router,
    prefix="/api",
    tags=["Motion Detection Events"])

# Motion Detection Zones - v3.7.0
app.include_router(
    motion_zones.router,
    prefix="/api",
    tags=["Motion Detection Zones"])

app.include_router(
    two_way_audio.router,
    prefix="/api/audio",
    tags=["Two-Way Audio"])

# WebSocket routes for real-time updates
app.include_router(websockets.router, prefix="/api", tags=["WebSockets"])

# System Settings
app.include_router(settings.router, prefix="/api", tags=["System Settings"])

# Notification Provider Configuration
app.include_router(
    notification_providers.router,
    prefix="/api",
    dependencies=[Depends(get_current_active_user)], tags=["Notification Providers"])

# Automation Rules - Person-Based Automations
app.include_router(automations.router, prefix="/api", tags=["Automations"])

# Timeline Playback & Video Navigation
app.include_router(timeline.router, prefix="/api", tags=["Timeline & Playback"])

# Performance Metrics & Monitoring
app.include_router(
    metrics.router,
    prefix="/api",
    dependencies=[Depends(get_current_active_user)], tags=["Performance Metrics"])

# PTZ Control - Pan-Tilt-Zoom Camera Control
app.include_router(ptz.router, prefix="/api", tags=["PTZ Control"])

# Hardware Detection & Feature Management
app.include_router(hardware.router, prefix="/api", tags=["Hardware & Features"])

# Feature Management (Hardware-Aware Auto-Config)
app.include_router(features.router, prefix="/api", tags=["Feature Management"])

# v3.10.0: Object Detection - YOLO-based detection and identification
app.include_router(objects.router, prefix="/api/objects", tags=["Object Detection"])

# v3.11.0: Ecosystem Integration - MagicMirror, mobile apps, cross-app sync
app.include_router(ecosystem.router, prefix="/api", tags=["Ecosystem Integration"])

# v3.11.4: Network Discovery with Fing integration
app.include_router(
    network_discovery.router,
    prefix="/api",
    dependencies=[Depends(get_current_active_user)], tags=["Network Discovery"])

# v3.12.0: Scheduled Tasks - Model retraining, retroactive search, cleanup
app.include_router(scheduled_tasks.router, prefix="/api/scheduled-tasks", tags=["Scheduled Tasks"])

# v3.11.7: License Plate Recognition (ALPR)
app.include_router(
    license_plates.router,
    prefix="/api/alpr",
    dependencies=[Depends(get_current_active_user)], tags=["License Plate Recognition"])

# First-Run Setup (with /api/setup prefix for consistency)
app.include_router(setup.router, prefix="/api/setup", tags=["First-Run Setup"])
app.include_router(ai_providers.router, prefix="/api/ai", tags=["AI Providers"])


# index.html names every other file, and those names carry a content hash that
# changes on each build. A browser holding a stale index.html therefore asks for
# chunks that no longer exist and the app fails to load — after an update, on a
# machine where nothing is wrong. FileResponse sets an ETag but no Cache-Control,
# which leaves the decision to heuristic caching, and browsers guess "reuse".
#
# no-cache does not mean do not store; it means revalidate before use. The ETag
# makes that a 304 in the common case.
INDEX_HEADERS = {"Cache-Control": "no-cache, must-revalidate"}


@app.get("/")
async def read_root():
    """
    Serve the frontend index.html for the root route
    """
    frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
    index_file = frontend_path / "index.html"

    if index_file.exists():
        return FileResponse(index_file, headers=INDEX_HEADERS)
    else:
        # Fallback to API info if frontend not built
        return {
            "name": "OpenEye Surveillance System",
            "version": "3.11.4",
            "description": "OpenCV-powered surveillance with face recognition",
            "features": [
                "Motion Detection",
                "Face Recognition",
                "Video Recording",
                "Alert System",
                "Real-time motion detection",
                "Face recognition and identification",
                "Automatic video recording",
                "Multi-camera support",
                "Historical analytics",
                "REST API access",
            ],
            "documentation": "/api/docs",
            "status": "operational",
            "note": "Frontend not built. Build the React app or access API at /api/docs",
        }


@app.get("/api/")
async def api_root(request: Request):
    """
    API root endpoint - System information for ecosystem discovery.
    
    MagicMirror and other ecosystem apps use this endpoint to discover OpenEye
    and determine its capabilities.
    """
    # Calculate uptime
    from backend.api.routes.ecosystem import get_uptime_seconds
    
    # Get configured port (canonical resolver: bind == register)
    from backend.core.config import resolve_service_port
    openeye_port = str(resolve_service_port())

    # Build host URL from request or environment
    host_header = request.headers.get("host", f"localhost:{openeye_port}")
    scheme = request.url.scheme or "http"
    server_url = os.getenv("OPENEYE_HOST", f"{scheme}://{host_header}")
    
    return {
        "app_name": "OpenEye",
        "name": "OpenEye Surveillance System API",
        "version": "3.11.4",
        "description": "OpenCV-powered surveillance with face recognition",
        "capabilities": [
            "notifications",
            "users", 
            "integrations",
            "cameras",
            "events",
            "faces",
            "recordings"
        ],
        "uptime": get_uptime_seconds(),
        "status": "healthy",
        "server_url": server_url,
        "ecosystem": {
            "connect_endpoint": "/api/ecosystem/connect",
            "events_websocket": "/api/ecosystem/events",
            "status_endpoint": "/api/status"
        },
        "features": [
            "Motion Detection",
            "Face Recognition",
            "Video Recording",
            "Alert System",
            "Real-time motion detection",
            "Face recognition and identification",
            "Automatic video recording",
            "Multi-camera support",
            "Historical analytics",
            "REST API access",
            "Ecosystem Integration (v3.11.0)"
        ],
        "documentation": "/api/docs",
    }


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    """
    active_cameras = len(camera_manager.cameras)

    return {
        "status": "healthy",
        "active_cameras": active_cameras,
        "face_recognition": "available",
        "database": "connected",
    }


@app.post("/ecosystem/events")
async def ecosystem_webhook(
    request: Request,
    _auth: dict = Depends(ecosystem.require_ecosystem_auth),
):
    """
    Receive ecosystem events via webhook and broadcast to connected clients.

    Signed requests only. Until 2026-08-20 this was unauthenticated, and because
    it forwards the payload straight to broadcast_alert, any anonymous caller
    could push a fabricated alert to every logged-in dashboard. On a standalone
    install (no appEcosystem) the dependency answers 503, which is the correct
    outcome — there is no ecosystem to receive events from.
    """
    if getattr(app.state, "ecosystem", None):
        body = await request.json()
        await app.state.ecosystem.handle_webhook(body)
        # Also broadcast to OpenEye's WebSocket clients
        try:
            from backend.core.websocket_manager import broadcast_alert
            event_type = body.get("type", "ecosystem_event")
            await broadcast_alert(event_type, body.get("data", {}))
        except Exception:
            pass
    return {"status": "ok"}


@app.get("/api/system/info")
async def system_info(current_user=Depends(get_current_active_user)):
    """
    Get system information and statistics.

    Requires authentication: the response enumerates camera names, whether each
    is running or recording, and per-camera face statistics.
    """
    cameras_info = {}

    for camera_id, camera in camera_manager.cameras.items():
        cameras_info[camera_id] = {
            "type": camera.__class__.__name__,
            "is_running": camera.is_running,
            "is_recording": camera.recorder.is_recording,
            "face_detection_enabled": camera.face_detector.enabled,
            "face_statistics": camera.get_face_statistics(),
        }

    return {
        "cameras": cameras_info,
        "total_cameras": len(
            camera_manager.cameras)}


# ============================================================================
# MOUNT FRONTEND STATIC FILES
# ============================================================================
# Mount static files for frontend (must be last to not override API routes)
frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_path.exists():
    # Serve static assets (JS, CSS, images)
    app.mount(
        "/assets",
        StaticFiles(
            directory=str(
                frontend_path /
                "assets")),
        name="assets")

    @app.middleware("http")
    async def cache_hashed_assets(request, call_next):
        """
        Everything under /assets carries a content hash in its filename, so a
        given URL's bytes can never change. Those are safe to keep for a year;
        a new build produces new URLs rather than new contents at old ones.

        Applied here rather than by subclassing StaticFiles, whose
        file_response() signature is a Starlette internal.
        """
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Serve the React SPA for all non-API routes
        This enables client-side routing
        
        Note: Don't check for static file paths here! FastAPI's mounted
        StaticFiles will handle them automatically. Only intercept for SPA.
        """
        # Only intercept non-API, non-static routes for the SPA
        if full_path.startswith("api/"):
            # API routes are already handled by routers
            raise HTTPException(status_code=404, detail="Not found")

        index_file = frontend_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, headers=INDEX_HEADERS)
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    # Single resolved port used for both bind and ecosystem registration.
    from backend.core.config import resolve_service_port, SERVICE_BIND_HOST
    port = resolve_service_port()
    host = SERVICE_BIND_HOST

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info")
