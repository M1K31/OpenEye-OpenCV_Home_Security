# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.
import uvicorn
import logging
from fastapi import FastAPI
from dotenv import load_dotenv

from backend.database.session import engine
from backend.database import models, alert_models
from backend.api.routes import users, cameras, faces, face_history, alerts
from backend.core.camera_manager import manager as camera_manager

# Load environment variables from .env file
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenEye Surveillance System",
    description="OpenCV-powered surveillance with face recognition",
    version="2.0.0"
)

@app.on_event("startup")
def startup_event():
    """
    On startup, create database tables and add a default mock camera.
    """
    # Create database tables
    logger.info("Creating database tables...")
    models.Base.metadata.create_all(bind=engine)
    alert_models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    if not camera_manager.get_camera("mock_cam_1"):
        camera_manager.add_camera(
            camera_id="mock_cam_1",
            camera_type="mock",
            source="mock",
            enable_face_detection=True
        )
        logger.info("Default mock camera added")

# Include all routers
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
    return {
        "message": "Welcome to OpenEye Surveillance System API",
        "version": "2.0.0",
        "features": ["Motion Detection", "Face Recognition", "Video Recording", "Alert System"]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)