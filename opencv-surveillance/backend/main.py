# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.

"""
OpenEye Surveillance System - Main Application
Complete Phase 2 implementation with face recognition
"""

import uvicorn
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.database.session import engine
from backend.database import models, alert_models
from backend.api.routes import users, cameras, faces, face_history, alerts
from backend.core.camera_manager import manager as camera_manager

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI application
app = FastAPI(
    title="OpenEye Surveillance System",
    description="OpenCV-powered surveillance system with face recognition, motion detection, and video recording",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    
    # Add default mock camera for testing
    if not camera_manager.get_camera("mock_cam_1"):
        logger.info("Adding default mock camera...")
        camera_manager.add_camera(
            camera_id="mock_cam_1",
            camera_type="mock",
            source="mock",
            enable_face_detection=True
        )
        logger.info("Default mock camera added successfully")
    
    logger.info("OpenEye Surveillance System started successfully!")
    logger.info("Features enabled: Motion Detection, Face Recognition, Video Recording")


@app.on_event("shutdown")
async def shutdown_event():
    """
    On shutdown, clean up resources.
    """
    logger.info("Shutting down OpenEye Surveillance System...")
    
    # Stop all cameras
    for camera_id in list(camera_manager.cameras.keys()):
        camera_manager.remove_camera(camera_id)
    
    logger.info("OpenEye Surveillance System shutdown complete")


# Include all API routers (ONCE)
app.include_router(
    users.router,
    prefix="/api",
    tags=["Authentication"]
)

app.include_router(
    cameras.router,
    prefix="/api",
    tags=["Cameras"]
)

app.include_router(
    faces.router,
    prefix="/api",
    tags=["Face Recognition"]
)

app.include_router(
    face_history.router,
    prefix="/api/faces",
    tags=["Face Detection History"]
)

app.include_router(
    alerts.router,
    prefix="/api",
    tags=["Alerts & Notifications"]
)


@app.get("/")
async def read_root():
    """
    Root endpoint - System information
    """
    return {
        "name": "OpenEye Surveillance System",
        "version": "2.0.0",
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
            "REST API access"
        ],
        "documentation": "/api/docs",
        "status": "operational"
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
        "database": "connected"
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
            "face_statistics": camera.get_face_statistics()
        }
    
    return {
        "cameras": cameras_info,
        "total_cameras": len(camera_manager.cameras)
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )