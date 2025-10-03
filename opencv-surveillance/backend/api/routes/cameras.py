# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import cv2
import asyncio

from backend.core.camera_manager import manager as camera_manager

router = APIRouter()

class CameraConfig(BaseModel):
    camera_id: str
    camera_type: str
    source: str

@router.post("/cameras/", status_code=201)
def add_camera(config: CameraConfig):
    """
    Adds a new camera to the system.
    - **camera_id**: A unique identifier for the camera (e.g., 'front-door').
    - **camera_type**: The type of camera ('rtsp' or 'mock').
    - **source**: The connection source (RTSP URL or 'mock' for a mock camera).
    """
    if camera_manager.get_camera(config.camera_id):
        raise HTTPException(status_code=400, detail=f"Camera with ID '{config.camera_id}' already exists.")

    camera_manager.add_camera(
        camera_id=config.camera_id,
        camera_type=config.camera_type,
        source=config.source
    )
    camera = camera_manager.get_camera(config.camera_id)
    if not camera or not camera.is_running:
        raise HTTPException(status_code=500, detail=f"Failed to start camera '{config.camera_id}'. Check logs for details.")

    return {"message": f"Camera '{config.camera_id}' added successfully."}


@router.get("/cameras/")
def list_cameras():
    """
    Returns a list of all active camera IDs.
    """
    return {"cameras": list(camera_manager.cameras.keys())}


@router.delete("/cameras/{camera_id}", status_code=200)
def remove_camera(camera_id: str):
    """
    Removes a camera from the system.
    """
    if not camera_manager.get_camera(camera_id):
        raise HTTPException(status_code=404, detail=f"Camera with ID '{camera_id}' not found.")

    camera_manager.remove_camera(camera_id)
    return {"message": f"Camera '{camera_id}' removed successfully."}

async def generate_frames(camera_id: str):
    """
    Generator function to yield frames from a camera as MJPEG.
    """
    camera = camera_manager.get_camera(camera_id)
    if not camera or not camera.is_running:
        print(f"Camera '{camera_id}' not found or not running.")
        return

    while True:
        frame, motion_detected = camera.get_frame()
        if frame is None:
            await asyncio.sleep(0.1)
            continue

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.03) # Limit frame rate

@router.get("/cameras/{camera_id}/stream")
def stream_video(camera_id: str):
    """
    Streams the video feed from a specified camera as an MJPEG stream.
    """
    camera = camera_manager.get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID '{camera_id}' not found.")

    return StreamingResponse(generate_frames(camera_id),
                             media_type='multipart/x-mixed-replace; boundary=frame')