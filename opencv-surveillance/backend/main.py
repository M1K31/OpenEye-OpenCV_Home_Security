# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
OpenEye Surveillance System - Main Application
Complete Phase 2 implementation with face recognition
"""

import uvicorn
import logging
import asyncio
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

from backend.database.session import engine, SessionLocal
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
)
from backend.core.camera_manager import manager as camera_manager
from backend.core.websocket_manager import broadcast_statistics_update
from backend.core.face_recognition import get_face_manager
from backend.core.statistics_broadcaster import get_broadcaster
from backend.middleware.rate_limiter import RateLimiter
from backend.middleware.security import (
    SecurityHeadersMiddleware,
    IPWhitelistMiddleware,
    SQLInjectionProtection,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="OpenEye Surveillance System",
    description="OpenCV-powered surveillance system with face recognition, motion detection, and video recording",
    version="3.5.1.4",  # Path validation fix and settings enhancements
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 6: Add security middleware (all free and open source)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SQLInjectionProtection)
# Increased rate limit to 1000 requests/minute to handle rapid UI interactions (sliders, etc.)
app.add_middleware(RateLimiter, requests_per_minute=1000)

# Optional: IP whitelist (disabled by default for ease of use)
# To enable, uncomment and add your allowed IPs:
# app.add_middleware(IPWhitelistMiddleware, allowed_ips=["127.0.0.1", "192.168.1.100"])


@app.on_event("startup")
async def startup_event():
    """
    On startup, create database tables and add default cameras.
    """
    logger.info("Starting OpenEye Surveillance System...")

    # Create database tables
    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    alert_models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Initialize system settings with defaults
    db = SessionLocal()
    try:
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

        # Get configured paths
        recordings_path = system_settings.get("recordings_path", "recordings")
        faces_path = system_settings.get("faces_path", "faces")

        logger.info(
            f"System settings loaded - Recordings: {recordings_path}, Faces: {faces_path}")
    finally:
        db.close()

    # Create required directories based on system settings
    logger.info("Creating required directories...")
    required_dirs = [
        recordings_path,
        faces_path,
        "data",
        "data/snapshots",
        "data/thumbnails",
    ]
    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    logger.info("Required directories created successfully")

    # Initialize face recognition manager with configured path
    logger.info(
        f"Initializing face recognition with faces directory: {faces_path}")
    face_manager = get_face_manager(faces_folder=faces_path)
    logger.info(
        f"Face recognition initialized: {len(face_manager.known_face_names)} known faces"
    )

    # Load existing cameras from database
    logger.info("Loading cameras from database...")
    db = SessionLocal()
    try:
        from backend.database import crud

        db_cameras = crud.get_active_cameras(db)
        loaded_count = 0
        for db_camera in db_cameras:
            if not camera_manager.get_camera(db_camera.camera_id):
                try:
                    camera_manager.add_camera(
                        camera_id=db_camera.camera_id,
                        camera_type=db_camera.camera_type,
                        source=db_camera.source,
                        enable_face_detection=db_camera.face_detection_enabled,
                    )
                    loaded_count += 1
                    logger.info(
                        f"Loaded camera '{
                            db_camera.camera_id}' from database")
                except Exception as e:
                    logger.error(
                        f"Failed to load camera '{
                            db_camera.camera_id}': {e}")
        logger.info(f"Loaded {loaded_count} camera(s) from database")
    finally:
        db.close()

    # Start statistics broadcaster
    logger.info("Starting statistics broadcaster...")
    broadcaster = get_broadcaster()
    await broadcaster.start()
    logger.info("Statistics broadcaster started successfully")

    logger.info("OpenEye Surveillance System started successfully!")
    logger.info(
        "Features enabled: Motion Detection, Face Recognition, Video Recording, Real-time WebSocket Updates"
    )


@app.on_event("shutdown")
async def shutdown_event():
    """
    On shutdown, clean up resources.
    """
    logger.info("Shutting down OpenEye Surveillance System...")

    # Stop statistics broadcaster
    logger.info("Stopping statistics broadcaster...")
    broadcaster = get_broadcaster()
    await broadcaster.stop()

    # Stop all cameras
    for camera_id in list(camera_manager.cameras.keys()):
        camera_manager.remove_camera(camera_id)

    logger.info("OpenEye Surveillance System shutdown complete")


# Include all API routers (ONCE)
app.include_router(users.router, prefix="/api", tags=["Authentication"])

# Camera Discovery - MUST be before /api/cameras to avoid route conflicts
app.include_router(discovery.router, prefix="/api", tags=["Camera Discovery"])

app.include_router(cameras.router, prefix="/api/cameras", tags=["Cameras"])

app.include_router(faces.router, prefix="/api", tags=["Face Recognition"])

app.include_router(
    face_history.router, prefix="/api/faces", tags=["Face Detection History"]
)

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
    tags=["Advanced Analytics"])

# Motion Detection Events - NEW
app.include_router(
    motion_events.router,
    prefix="/api",
    tags=["Motion Detection Events"])

# WebSocket routes for real-time updates
app.include_router(websockets.router, prefix="/api", tags=["WebSockets"])

# System Settings
app.include_router(settings.router, prefix="/api", tags=["System Settings"])

# First-Run Setup
app.include_router(setup.router, tags=["First-Run Setup"])


@app.get("/")
async def read_root():
    """
    Serve the frontend index.html for the root route
    """
    frontend_path = Path(__file__).parent.parent / "frontend" / "dist"
    index_file = frontend_path / "index.html"

    if index_file.exists():
        return FileResponse(index_file)
    else:
        # Fallback to API info if frontend not built
        return {
            "name": "OpenEye Surveillance System",
            "version": "3.5.1.4",
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


@app.get("/api")
async def api_root():
    """
    API root endpoint - System information
    """
    return {
        "name": "OpenEye Surveillance System API",
        "version": "3.5.1.4",
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


@app.get("/api/system/info")
async def system_info():
    """
    Get system information and statistics
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
# MOUNT USER-CONFIGURED DATA DIRECTORIES
# ============================================================================
# Mount recordings, faces, and snapshots directories from user settings
# This allows users to configure custom storage locations

db = SessionLocal()
try:
    from backend.database import crud
    settings_list = crud.get_all_system_settings(db)
    system_settings = {s.setting_key: s.setting_value for s in settings_list}
    
    # Get all three user-configurable paths
    recordings_path_setting = system_settings.get("recordings_path", "recordings")
    faces_path_setting = system_settings.get("faces_path", "faces")
    snapshots_path_setting = system_settings.get("snapshots_path", "data/snapshots")
finally:
    db.close()

# 1. Mount RECORDINGS directory
recordings_path = Path(recordings_path_setting)
if recordings_path.exists():
    app.mount(
        "/recordings",
        StaticFiles(directory=str(recordings_path)),
        name="recordings"
    )
    logger.info(f"Mounted recordings directory: {recordings_path}")
else:
    logger.warning(f"Recordings directory not found: {recordings_path}")
    # Create it if it doesn't exist
    recordings_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created recordings directory: {recordings_path}")
    app.mount(
        "/recordings",
        StaticFiles(directory=str(recordings_path)),
        name="recordings"
    )

# 2. Mount FACES directory
faces_path = Path(faces_path_setting)
if faces_path.exists():
    app.mount(
        "/faces",
        StaticFiles(directory=str(faces_path)),
        name="faces"
    )
    logger.info(f"Mounted faces directory: {faces_path}")
else:
    logger.warning(f"Faces directory not found: {faces_path}")
    # Create it if it doesn't exist
    faces_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created faces directory: {faces_path}")
    app.mount(
        "/faces",
        StaticFiles(directory=str(faces_path)),
        name="faces"
    )

# 3. Mount SNAPSHOTS directory
snapshots_path = Path(snapshots_path_setting)
if snapshots_path.exists():
    app.mount(
        "/data/snapshots",
        StaticFiles(directory=str(snapshots_path)),
        name="snapshots"
    )
    logger.info(f"Mounted snapshots directory: {snapshots_path}")
else:
    logger.warning(f"Snapshots directory not found: {snapshots_path}")
    # Create it if it doesn't exist
    snapshots_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created snapshots directory: {snapshots_path}")
    app.mount(
        "/data/snapshots",
        StaticFiles(directory=str(snapshots_path)),
        name="snapshots"
    )

# Mount local data/snapshots as fallback for legacy files (if custom path is different)
if str(snapshots_path) != "data/snapshots":
    local_snapshots = Path("data/snapshots")
    if local_snapshots.exists():
        app.mount(
            "/legacy/snapshots",
            StaticFiles(directory=str(local_snapshots)),
            name="snapshots_local"
        )
        logger.info(f"Mounted local snapshots directory for legacy files: {local_snapshots}")

# Mount default data directories
data_path = Path("data")
if data_path.exists():
    # Serve thumbnails directory
    thumbnails_path = data_path / "thumbnails"
    if thumbnails_path.exists():
        app.mount(
            "/data/thumbnails",
            StaticFiles(directory=str(thumbnails_path)),
            name="thumbnails"
        )
        logger.info(f"Mounted thumbnails directory: {thumbnails_path}")

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

    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Serve the React SPA for all non-API routes
        This enables client-side routing
        """
        # Don't intercept API routes
        if full_path.startswith("api/"):
            return {"error": "Not found"}

        index_file = frontend_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not found"}


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info")
