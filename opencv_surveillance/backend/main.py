# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
OpenEye Surveillance System - Main Application
Complete Phase 2 implementation with face recognition
"""

# Suppress pkg_resources deprecation warning from face_recognition_models (external package)
import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

# Apply pkg_resources patch BEFORE any imports that use face_recognition
from backend.core.pkg_resources_patch import patch_face_recognition_models
patch_face_recognition_models()

import uvicorn
import logging
import asyncio
import signal
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, WebSocket
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
    clusters,
    automations,
    two_way_audio,
    timeline,
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
from backend.core.two_way_audio_system import audio_manager

# Load environment variables from .env file
load_dotenv()

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
    version="3.5.6",  # Timeline Playback + UI improvements
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

# ============================================================================
# MOUNT STATIC FILES EARLY (before routes to ensure proper precedence)
# ============================================================================
# These mounts MUST be defined before the catch-all SPA route
# to ensure FastAPI routes requests to static files correctly

# Import centralized path manager
from backend.core.paths import paths

# All directories are auto-created by PathManager
# Mount recordings directory
app.mount(
    "/recordings",
    StaticFiles(directory=str(paths.recordings_dir)),
    name="recordings"
)

# Mount faces directory
app.mount(
    "/faces",
    StaticFiles(directory=str(paths.faces_dir)),
    name="faces"
)

# Mount snapshots directory (v3.5.6+: Primary endpoint under /api/)
app.mount(
    "/api/snapshots",
    StaticFiles(directory=str(paths.snapshots_dir)),
    name="snapshots_api"
)

# Mount snapshots directory (legacy paths for backward compatibility)
app.mount(
    "/data/snapshots",
    StaticFiles(directory=str(paths.snapshots_dir)),
    name="snapshots_data"
)

app.mount(
    "/legacy/snapshots",
    StaticFiles(directory=str(paths.snapshots_dir)),
    name="snapshots_legacy"
)

# Mount thumbnails directory
app.mount(
    "/data/thumbnails",
    StaticFiles(directory=str(paths.thumbnails_dir)),
    name="thumbnails"
)


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

        # Get configured paths from database (if they exist)
        # These will override PathManager defaults if set
        db_recordings_path = system_settings.get("recordings_path")
        db_faces_path = system_settings.get("faces_path")

        # Update PathManager with database settings if they exist
        if db_recordings_path or db_faces_path:
            logger.info("Applying custom paths from database settings...")
            paths.update_paths(
                recordings_dir=db_recordings_path,
                faces_dir=db_faces_path
            )

        logger.info(
            f"System settings loaded - Recordings: {paths.recordings_dir}, Faces: {paths.faces_dir}")
    finally:
        db.close()

    # PathManager automatically creates all required directories
    logger.info("Required directories handled by PathManager")

    # Initialize face recognition manager with configured path
    logger.info(
        f"Initializing face recognition with faces directory: {paths.faces_dir}")
    face_manager = get_face_manager(faces_folder=str(paths.faces_dir))
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

    # Static file directories are now mounted at application startup (before routes)
    # This ensures they take precedence over the catch-all SPA route
    logger.info("Static file directories already mounted during app initialization")
    logger.info(f"✓ Recordings directory: {paths.recordings_dir}")
    logger.info(f"✓ Faces directory: {paths.faces_dir}")
    logger.info(f"✓ Snapshots directory: {paths.snapshots_dir}")
    logger.info(f"✓ Legacy snapshots directory: {paths.snapshots_dir}")
    logger.info(f"✓ Thumbnails directory: {paths.thumbnails_dir}")

    logger.info("OpenEye Surveillance System started successfully!")
    logger.info(
        "Features enabled: Motion Detection, Face Recognition, Video Recording, Real-time WebSocket Updates"
    )


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

    # Step 1: Stop statistics broadcaster (WebSocket updates)
    try:
        logger.info("[1/7] Stopping statistics broadcaster...")
        broadcaster = get_broadcaster()
        
        # Set timeout for broadcaster stop
        stop_task = asyncio.create_task(broadcaster.stop())
        await asyncio.wait_for(stop_task, timeout=5.0)
        logger.info("✓ Statistics broadcaster stopped successfully")
    except asyncio.TimeoutError:
        logger.error("✗ Statistics broadcaster stop timed out after 5s")
    except Exception as e:
        logger.error(f"✗ Error stopping statistics broadcaster: {e}")

    # Step 2: Close all WebSocket connections
    try:
        logger.info("[2/7] Closing WebSocket connections...")
        from backend.core.websocket_manager import ws_manager
        
        # Close all connections gracefully
        if hasattr(ws_manager, 'disconnect_all'):
            await ws_manager.disconnect_all()
            logger.info("✓ All WebSocket connections closed")
        else:
            logger.warning("⚠ WebSocket manager doesn't have disconnect_all method")
    except Exception as e:
        logger.error(f"✗ Error closing WebSocket connections: {e}")

    # Step 3: Stop all cameras and release resources
    try:
        logger.info("[3/7] Stopping all cameras...")
        camera_count = len(camera_manager.cameras)
        
        for camera_id in list(camera_manager.cameras.keys()):
            try:
                camera_manager.remove_camera(camera_id)
                logger.debug(f"  Stopped camera: {camera_id}")
            except Exception as e:
                logger.error(f"  Error stopping camera {camera_id}: {e}")
        
        logger.info(f"✓ Stopped {camera_count} camera(s)")
    except Exception as e:
        logger.error(f"✗ Error stopping cameras: {e}")

    # Step 4: Face recognition uses stateless get_face_manager() - no cleanup needed
    logger.info("[4/7] Face recognition uses stateless manager - skipping")

    # Step 5: Stop cloud storage upload threads
    try:
        logger.info("[5/7] Stopping cloud storage threads...")
        from backend.core.cloud_storage_system import cloud_storage
        
        if hasattr(cloud_storage, 'stop_upload_worker'):
            cloud_storage.stop_upload_worker()
            logger.info("✓ Cloud storage threads stopped")
        else:
            logger.warning("⚠ Cloud storage doesn't have stop_upload_worker method")
    except Exception as e:
        logger.error(f"✗ Error stopping cloud storage: {e}")

    # Step 6: Close database connections
    try:
        logger.info("[6/7] Closing database connections...")
        from backend.database import engine
        
        if engine:
            engine.dispose()
            logger.info("✓ Database connections closed")
    except Exception as e:
        logger.error(f"✗ Error closing database: {e}")

    # Step 7: Cancel all remaining async tasks
    try:
        logger.info("[7/7] Canceling remaining async tasks...")
        tasks = [task for task in asyncio.all_tasks() if not task.done()]
        
        if tasks:
            logger.info(f"  Found {len(tasks)} pending task(s)")
            for task in tasks:
                task.cancel()
            
            # Wait for task cancellations with timeout
            await asyncio.wait(tasks, timeout=3.0)
            logger.info("✓ Async tasks canceled")
        else:
            logger.info("✓ No pending async tasks")
    except Exception as e:
        logger.error(f"✗ Error canceling async tasks: {e}")

    logger.info("=" * 60)
    logger.info("OpenEye Surveillance System shutdown complete")
    logger.info("=" * 60)


# Include all API routers (ONCE)
app.include_router(users.router, prefix="/api", tags=["Authentication"])

# Camera Discovery - MUST be before /api/cameras to avoid route conflicts
app.include_router(discovery.router, prefix="/api", tags=["Camera Discovery"])

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
    tags=["Advanced Analytics"])

# Motion Detection Events - NEW
app.include_router(
    motion_events.router,
    prefix="/api",
    tags=["Motion Detection Events"])

app.include_router(
    two_way_audio.router,
    prefix="/api/audio",
    tags=["Two-Way Audio"])

# WebSocket routes for real-time updates
app.include_router(websockets.router, prefix="/api", tags=["WebSockets"])

# System Settings
app.include_router(settings.router, prefix="/api", tags=["System Settings"])

# Automation Rules - Person-Based Automations
app.include_router(automations.router, prefix="/api", tags=["Automations"])

# Timeline Playback & Video Navigation
app.include_router(timeline.router, prefix="/api", tags=["Timeline & Playback"])

# First-Run Setup (with /api/setup prefix for consistency)
app.include_router(setup.router, prefix="/api/setup", tags=["First-Run Setup"])


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
            "version": "3.5.6",
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
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info")
