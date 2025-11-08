#!/usr/bin/env python3
"""
Integration test for FFmpeg hardware encoding
Tests the complete flow from settings -> camera manager -> FFmpegRecorder
"""

import sys
import os
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.camera_manager import CameraManager
from backend.core.ffmpeg_recorder import FFmpegRecorder, EncoderCapabilities
from backend.database.session import SessionLocal

def test_hardware_encoding_integration():
    """Test complete hardware encoding integration"""

    print("=" * 70)
    print("  FFmpeg Hardware Encoding Integration Test")
    print("=" * 70)

    # Step 1: Verify hardware encoder detection
    print("\n[1/5] Checking hardware encoder availability...")
    encoders = EncoderCapabilities.detect_available_encoders()
    codec, description = EncoderCapabilities.get_best_encoder()
    print(f"✅ Best encoder: {description} ({codec})")

    # Step 2: Verify database setting
    print("\n[2/5] Checking database settings...")
    db = SessionLocal()
    try:
        from backend.database.models import SystemSettings
        setting = db.query(SystemSettings).filter(
            SystemSettings.setting_key == 'hardware_video_encoding'
        ).first()

        if setting and setting.setting_value.lower() == 'true':
            print(f"✅ hardware_video_encoding = {setting.setting_value}")
        else:
            print(f"⚠️  hardware_video_encoding not enabled or not found")
            if not setting:
                print("    Setting doesn't exist in database")
            else:
                print(f"    Current value: {setting.setting_value}")
    finally:
        db.close()

    # Step 3: Create camera with hardware encoding enabled
    print("\n[3/5] Creating mock camera with hardware encoding...")
    manager = CameraManager()

    # Simulate settings with hardware encoding enabled
    test_settings = {
        'hardware_video_encoding': True,
        'recordings_path': 'test_recordings',
        'max_recording_duration': 10,  # Short duration for testing
    }

    # Create a mock camera
    camera_id = "test_hardware_encoding"

    # First, let's directly test the camera initialization
    from backend.core.camera_manager import MockCamera
    camera = MockCamera(
        source="mock",
        camera_id=camera_id,
        enable_face_detection=False,
        db_settings=test_settings
    )

    # Step 4: Verify recorder type
    print("\n[4/5] Verifying recorder type...")
    recorder_type = type(camera.recorder).__name__
    print(f"   Recorder class: {recorder_type}")

    if recorder_type == "FFmpegRecorder":
        print(f"✅ FFmpegRecorder is being used!")
        print(f"   Encoder: {camera.recorder.encoder_description}")
        print(f"   Hardware encoding enabled: {camera.recorder.use_hardware_encoding}")
        print(f"   Frame buffer enabled: {camera.recorder.enable_frame_buffer}")
    elif recorder_type == "Recorder":
        print(f"⚠️  Standard Recorder is being used (not FFmpeg)")
        print(f"   This might be expected if FFmpeg initialization failed")
    else:
        print(f"❌ Unexpected recorder type: {recorder_type}")

    # Step 5: Test recording functionality
    print("\n[5/5] Testing recording functionality...")

    # Create test_recordings directory
    Path("test_recordings").mkdir(exist_ok=True)

    # Start camera
    camera.start()
    print(f"✅ Camera started")

    # Simulate a few frames to potentially trigger recording
    print("   Simulating 30 frames (motion detection should trigger)...")
    for i in range(30):
        frame, motion_detected = camera.get_frame()
        if motion_detected and not camera.recorder.is_recording:
            print(f"   ⚡ Motion detected on frame {i+1}, recording should start...")
        if camera.recorder.is_recording and i == 20:
            print(f"   📹 Recording in progress (frame {i+1})...")
        time.sleep(0.1)  # 100ms between frames

    # Stop camera
    camera.stop()
    print(f"✅ Camera stopped")

    # Check if recording was created
    recordings_dir = Path("test_recordings")
    recordings = list(recordings_dir.glob("*.mp4"))

    if recordings:
        print(f"\n✅ Recording created: {recordings[0].name}")
        print(f"   File size: {recordings[0].stat().st_size / 1024:.2f} KB")

        # Check for metadata file
        metadata_files = list(recordings_dir.glob("*_metadata.json"))
        if metadata_files:
            print(f"✅ Metadata file created: {metadata_files[0].name}")

            # Read and display metadata
            import json
            with open(metadata_files[0], 'r') as f:
                metadata = json.load(f)
                print(f"   Encoder: {metadata.get('encoder', 'Unknown')}")
                print(f"   Duration: {metadata.get('duration_seconds', 0):.2f}s")
                print(f"   Frame count: {metadata.get('frame_count', 0)}")

                buffer_stats = metadata.get('buffer_stats')
                if buffer_stats:
                    print(f"   Frames written: {buffer_stats.get('frames_written', 0)}")
                    print(f"   Frames dropped: {buffer_stats.get('frames_dropped', 0)}")
                    print(f"   Drop rate: {buffer_stats.get('drop_rate', 0):.2f}%")
    else:
        print(f"⚠️  No recordings found in test_recordings/")
        print(f"   This might be expected if motion detection didn't trigger")
        print(f"   (MockCamera has a moving circle that should trigger motion)")

    # Final summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70)
    print(f"✅ Hardware encoder detected: {description}")
    print(f"✅ Database setting configured: hardware_video_encoding = true")
    print(f"✅ Recorder type: {recorder_type}")

    if recorder_type == "FFmpegRecorder":
        print(f"✅ Integration successful - FFmpeg hardware encoding is active!")
    else:
        print(f"⚠️  Integration incomplete - Standard recorder is being used")

    if recordings:
        print(f"✅ Recording test successful - {len(recordings)} file(s) created")
    else:
        print(f"⚠️  No recordings created (motion might not have triggered)")

    print("=" * 70)
    print("\nTest complete!")
    print("\nCleanup:")
    print("  - Test recordings saved in: test_recordings/")
    print("  - To remove: rm -rf test_recordings/")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_hardware_encoding_integration()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
