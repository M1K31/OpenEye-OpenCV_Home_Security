#!/usr/bin/env python3
"""
Diagnostic script to check camera status
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.camera_manager import manager as camera_manager
from backend.database.session import SessionLocal
from backend.database import crud

def main():
    print("=" * 60)
    print("OpenEye Camera Diagnostics")
    print("=" * 60)
    
    # Check database cameras
    print("\n[1] DATABASE CAMERAS:")
    print("-" * 60)
    db = SessionLocal()
    try:
        cameras = crud.get_cameras(db)
        if cameras:
            for cam in cameras:
                print(f"  Camera ID: {cam.camera_id}")
                print(f"    Type: {cam.camera_type}")
                print(f"    Source: {cam.source}")
                print(f"    Active (DB): {cam.is_active}")
                print(f"    Face Detection: {cam.face_detection_enabled}")
                print()
        else:
            print("  No cameras in database")
    finally:
        db.close()
    
    # Check active cameras in memory
    print("\n[2] ACTIVE CAMERAS IN MEMORY:")
    print("-" * 60)
    if camera_manager.cameras:
        for camera_id, camera in camera_manager.cameras.items():
            print(f"  Camera ID: {camera_id}")
            print(f"    Running: {camera.is_running}")
            print(f"    Type: {camera.camera_type}")
            
            # Try to get a frame
            frame, motion = camera.get_frame()
            print(f"    Frame Available: {frame is not None}")
            if frame is not None:
                print(f"    Frame Shape: {frame.shape}")
            print()
    else:
        print("  No active cameras in memory")
    
    # Check camera endpoints
    print("\n[3] CAMERA STREAM ENDPOINTS:")
    print("-" * 60)
    for camera_id in camera_manager.cameras.keys():
        print(f"  http://localhost:8000/api/cameras/{camera_id}/stream")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
