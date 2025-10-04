# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.
import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from backend.database.session import engine
from backend.database import models
from backend.api.routes import users, cameras, faces
from backend.core.camera_manager import manager as camera_manager

# Load environment variables from .env file
load_dotenv()

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
    models.Base.metadata.create_all(bind=engine)

    if not camera_manager.get_camera("mock_cam_1"):
        camera_manager.add_camera(
            camera_id="mock_cam_1",
            camera_type="mock",
            source="mock",
            enable_face_detection=True
        )

# Include all routers
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(cameras.router, prefix="/api", tags=["cameras"])
app.include_router(faces.router, prefix="/api", tags=["faces"])

@app.get("/")
async def read_root():
    return {
        "message": "Welcome to OpenEye Surveillance System API",
        "version": "2.0.0",
        "features": ["Motion Detection", "Face Recognition", "Video Recording"]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)