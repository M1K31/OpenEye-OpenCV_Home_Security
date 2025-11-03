#!/usr/bin/env python3
"""
Test script for motion zone-based detection (v3.6.2)

Tests:
1. Zone loading from database
2. Point-in-polygon detection
3. Inclusion/exclusion zone filtering
4. Zone statistics updates
"""

import sys
import os
import json
import numpy as np
import cv2
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database.session import SessionLocal
from backend.database.models import Camera as CameraModel, MotionZone
from backend.core.motion_detector import MotionDetector


def create_test_camera(db, camera_id="test_zone_camera"):
    """Create a test camera in the database."""
    # Check if camera already exists
    existing = db.query(CameraModel).filter(CameraModel.camera_id == camera_id).first()
    if existing:
        db.delete(existing)
        db.commit()

    camera = CameraModel(
        camera_id=camera_id,
        camera_type="mock",
        source="mock",
        motion_detection_enabled=True
    )
    db.add(camera)
    db.commit()
    print(f"✅ Created test camera: {camera_id}")
    return camera


def create_test_zones(db, camera_id):
    """Create test zones for motion detection."""
    # Clear existing zones
    db.query(MotionZone).filter(MotionZone.camera_id == camera_id).delete()
    db.commit()

    # Zone 1: Inclusion zone in the center (30% to 70% of frame)
    inclusion_zone = MotionZone(
        camera_id=camera_id,
        name="Center Inclusion Zone",
        zone_type="polygon",
        coordinates=json.dumps([
            {"x": 0.3, "y": 0.3},
            {"x": 0.7, "y": 0.3},
            {"x": 0.7, "y": 0.7},
            {"x": 0.3, "y": 0.7}
        ]),
        is_active=True,
        is_exclusion_zone=False,
        sensitivity_multiplier=1.0,
        color="#00FF00",
        opacity=0.3
    )

    # Zone 2: Exclusion zone in top-left corner
    exclusion_zone = MotionZone(
        camera_id=camera_id,
        name="Corner Exclusion Zone",
        zone_type="polygon",
        coordinates=json.dumps([
            {"x": 0.0, "y": 0.0},
            {"x": 0.2, "y": 0.0},
            {"x": 0.2, "y": 0.2},
            {"x": 0.0, "y": 0.2}
        ]),
        is_active=True,
        is_exclusion_zone=True,
        sensitivity_multiplier=1.0,
        color="#FF0000",
        opacity=0.3
    )

    db.add(inclusion_zone)
    db.add(exclusion_zone)
    db.commit()

    print(f"✅ Created 2 test zones for camera: {camera_id}")
    print(f"   - Inclusion zone: Center (30-70%)")
    print(f"   - Exclusion zone: Top-left corner (0-20%)")

    return [inclusion_zone, exclusion_zone]


def create_test_frame_with_motion(width=640, height=480, motion_region="center"):
    """
    Create a test frame with simulated motion.

    Args:
        width: Frame width
        height: Frame height
        motion_region: Where to place motion - "center", "corner", or "both"

    Returns:
        Tuple of (frame1, frame2) with motion between them
    """
    # Create base frame (background) - darker for better contrast
    frame1 = np.ones((height, width, 3), dtype=np.uint8) * 30
    frame2 = frame1.copy()

    if motion_region in ["center", "both"]:
        # Add significant motion in center (should be detected in inclusion zone)
        # Make it larger and brighter for easier detection
        center_x, center_y = width // 2, height // 2
        cv2.rectangle(frame2,
                     (center_x - 100, center_y - 100),
                     (center_x + 100, center_y + 100),
                     (255, 255, 255),
                     -1)

    if motion_region in ["corner", "both"]:
        # Add significant motion in top-left corner (should be filtered by exclusion zone)
        cv2.rectangle(frame2, (10, 10), (120, 120), (255, 255, 255), -1)

    return frame1, frame2


def test_zone_loading():
    """Test 1: Verify zones load correctly from database."""
    print("\n" + "="*60)
    print("TEST 1: Zone Loading from Database")
    print("="*60)

    db = SessionLocal()
    try:
        camera_id = "test_zone_camera"

        # Create test camera and zones
        camera = create_test_camera(db, camera_id)
        zones = create_test_zones(db, camera_id)

        # Create motion detector and load zones
        detector = MotionDetector(sensitivity=8, var_threshold=16)  # High sensitivity
        detector.load_polygon_zones(camera_id, db)

        # Verify zones loaded
        assert len(detector.polygon_zones) == 2, f"Expected 2 zones, got {len(detector.polygon_zones)}"

        inclusion_zones = [z for z in detector.polygon_zones if not z['is_exclusion_zone']]
        exclusion_zones = [z for z in detector.polygon_zones if z['is_exclusion_zone']]

        assert len(inclusion_zones) == 1, "Should have 1 inclusion zone"
        assert len(exclusion_zones) == 1, "Should have 1 exclusion zone"

        print("✅ PASSED: Zones loaded correctly")
        print(f"   - Loaded {len(detector.polygon_zones)} zones")
        print(f"   - {len(inclusion_zones)} inclusion zone(s)")
        print(f"   - {len(exclusion_zones)} exclusion zone(s)")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False
    finally:
        db.close()


def test_motion_in_inclusion_zone():
    """Test 2: Verify motion in inclusion zone is detected."""
    print("\n" + "="*60)
    print("TEST 2: Motion in Inclusion Zone")
    print("="*60)

    db = SessionLocal()
    try:
        camera_id = "test_zone_camera"

        # Setup
        camera = create_test_camera(db, camera_id)
        zones = create_test_zones(db, camera_id)

        detector = MotionDetector(sensitivity=8, var_threshold=16)  # High sensitivity
        detector.load_polygon_zones(camera_id, db)

        # Create frames with motion in center (inclusion zone)
        frame1, frame2 = create_test_frame_with_motion(motion_region="center")

        # Train background model with first frame
        for _ in range(20):
            detector.detect(frame1)

        # Detect motion with second frame multiple times (for temporal filter)
        motion_detected = False
        motion_areas = []
        for i in range(5):
            _, detected, areas = detector.detect(frame2)
            if detected:
                motion_detected = True
                motion_areas = areas
                print(f"   - Motion detected on attempt {i+1}: {len(areas)} areas")
                break

        assert motion_detected, "Motion should be detected in inclusion zone"
        assert len(motion_areas) > 0, "Should have motion areas"

        print("✅ PASSED: Motion in inclusion zone detected")
        print(f"   - Motion detected: {motion_detected}")
        print(f"   - Motion areas: {len(motion_areas)}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_motion_in_exclusion_zone():
    """Test 3: Verify motion in exclusion zone is filtered out."""
    print("\n" + "="*60)
    print("TEST 3: Motion in Exclusion Zone (Should be Filtered)")
    print("="*60)

    db = SessionLocal()
    try:
        camera_id = "test_zone_camera"

        # Setup
        camera = create_test_camera(db, camera_id)
        zones = create_test_zones(db, camera_id)

        detector = MotionDetector(sensitivity=8, var_threshold=16)  # High sensitivity
        detector.load_polygon_zones(camera_id, db)

        # Create frames with motion in corner (exclusion zone)
        frame1, frame2 = create_test_frame_with_motion(motion_region="corner")

        # Train background model
        for _ in range(20):
            detector.detect(frame1)

        # Detect motion
        _, motion_detected, motion_areas = detector.detect(frame2)

        # Motion should be filtered out by exclusion zone
        assert not motion_detected or len(motion_areas) == 0, "Motion in exclusion zone should be filtered"

        print("✅ PASSED: Motion in exclusion zone filtered correctly")
        print(f"   - Motion detected: {motion_detected}")
        print(f"   - Motion areas: {len(motion_areas)}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_zone_statistics_update():
    """Test 4: Verify zone statistics are updated."""
    print("\n" + "="*60)
    print("TEST 4: Zone Statistics Update")
    print("="*60)

    db = SessionLocal()
    try:
        camera_id = "test_zone_camera"

        # Setup
        camera = create_test_camera(db, camera_id)
        zones = create_test_zones(db, camera_id)

        # Get initial statistics
        inclusion_zone = db.query(MotionZone).filter(
            MotionZone.camera_id == camera_id,
            MotionZone.is_exclusion_zone == False
        ).first()

        initial_count = inclusion_zone.motion_events_count

        # Create detector with database session
        detector = MotionDetector(sensitivity=8, var_threshold=16)  # High sensitivity
        detector.load_polygon_zones(camera_id, db)

        # Create frames with motion in center
        frame1, frame2 = create_test_frame_with_motion(motion_region="center")

        # Train background model
        for _ in range(20):
            detector.detect(frame1)

        # Detect motion multiple times (for temporal filter + statistics update)
        motion_detected = False
        for i in range(5):
            _, detected, areas = detector.detect(frame2)
            if detected:
                motion_detected = True
                print(f"   - Motion detected on attempt {i+1}")
                break

        # Refresh zone from database
        db.refresh(inclusion_zone)

        # Check if statistics were updated
        assert inclusion_zone.motion_events_count > initial_count, "Motion event count should increase"
        assert inclusion_zone.last_motion_at is not None, "Last motion time should be set"

        print("✅ PASSED: Zone statistics updated correctly")
        print(f"   - Initial count: {initial_count}")
        print(f"   - Final count: {inclusion_zone.motion_events_count}")
        print(f"   - Last motion: {inclusion_zone.last_motion_at}")

        return True

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def cleanup_test_data():
    """Clean up test data from database."""
    print("\n" + "="*60)
    print("CLEANUP: Removing test data")
    print("="*60)

    db = SessionLocal()
    try:
        # Delete test camera and zones (zones will cascade delete)
        db.query(CameraModel).filter(CameraModel.camera_id == "test_zone_camera").delete()
        db.commit()
        print("✅ Test data cleaned up")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    finally:
        db.close()


def main():
    """Run all zone detection tests."""
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*10 + "MOTION ZONE DETECTION TESTS (v3.6.2)" + " "*11 + "║")
    print("╚" + "="*58 + "╝")

    results = []

    # Run tests
    results.append(("Zone Loading", test_zone_loading()))
    results.append(("Motion in Inclusion Zone", test_motion_in_inclusion_zone()))
    results.append(("Motion in Exclusion Zone", test_motion_in_exclusion_zone()))
    results.append(("Zone Statistics Update", test_zone_statistics_update()))

    # Cleanup
    cleanup_test_data()

    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")

    print("\n" + "="*60)
    print(f"RESULTS: {passed}/{total} tests passed")
    print("="*60)

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
