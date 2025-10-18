#!/usr/bin/env python3
"""Test script to verify motion event creation"""

from datetime import datetime
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, '/Volumes/Storage/Dev/GitHubProjects/OpenEye-OpenCV_Home_Security/opencv-surveillance')

from opencv_surveillance.backend.database.session import SessionLocal
from opencv_surveillance.backend.database.models import MotionDetectionEvent

def test_motion_event_creation():
    """Test creating a motion event directly"""
    
    try:
        db = SessionLocal()
        
        # Create a test motion event
        motion_event = MotionDetectionEvent(
            camera_id="usb_camera_0",
            motion_area=1000,
            motion_percentage=5.5,
            contour_count=3,
            snapshot_path="test_snapshot.jpg",
            frame_width=640,
            frame_height=480,
        )
        
        db.add(motion_event)
        db.commit()
        db.refresh(motion_event)
        
        print(f"✅ Successfully created motion event with ID: {motion_event.id}")
        print(f"   Camera: {motion_event.camera_id}")
        print(f"   Motion area: {motion_event.motion_area}")
        print(f"   Motion percentage: {motion_event.motion_percentage}%")
        print(f"   Contour count: {motion_event.contour_count}")
        print(f"   Detected at: {motion_event.detected_at}")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating motion event: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing motion event creation...")
    test_motion_event_creation()
