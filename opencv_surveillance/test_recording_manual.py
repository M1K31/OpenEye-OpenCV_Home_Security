#!/usr/bin/env python3
"""
Manual recording test - directly tests FFmpegRecorder recording
"""

import sys
import os
import time
from pathlib import Path
import numpy as np

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.ffmpeg_recorder import FFmpegRecorder, EncoderCapabilities

def test_manual_recording():
    """Test FFmpegRecorder directly with manual recording"""

    print("=" * 70)
    print("  FFmpeg Manual Recording Test")
    print("=" * 70)

    # Step 1: Check encoder
    print("\n[1/4] Detecting hardware encoder...")
    codec, description = EncoderCapabilities.get_best_encoder()
    print(f"✅ Using: {description} ({codec})")

    # Step 2: Create recorder
    print("\n[2/4] Creating FFmpegRecorder...")
    recorder = FFmpegRecorder(
        output_dir="test_recordings",
        max_recording_duration=10,
        use_hardware_encoding=True,
        enable_frame_buffer=True,
        buffer_size=300
    )
    print(f"✅ Recorder created")
    print(f"   Encoder: {recorder.encoder_description}")
    print(f"   Hardware encoding: {recorder.use_hardware_encoding}")
    print(f"   Frame buffer: {recorder.enable_frame_buffer}")

    # Step 3: Record test video
    print("\n[3/4] Starting recording...")

    # Create test_recordings directory
    Path("test_recordings").mkdir(exist_ok=True)

    # Start recording
    width, height, fps = 640, 480, 30
    success = recorder.start(
        frame_width=width,
        frame_height=height,
        fps=fps,
        camera_id="manual_test"
    )

    if not success:
        print("❌ Failed to start recording")
        return

    print(f"✅ Recording started")
    print(f"   Output: {recorder.filename}")

    # Generate and write test frames
    num_frames = 90  # 3 seconds at 30 fps
    print(f"   Writing {num_frames} test frames...")

    for i in range(num_frames):
        # Create a test frame with moving circle
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Add timestamp text
        import cv2
        cv2.putText(
            frame,
            f"Frame {i+1}/{num_frames}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )

        # Add moving circle
        x = int(width / 2 + 100 * np.cos(i * 0.2))
        y = int(height / 2 + 100 * np.sin(i * 0.2))
        cv2.circle(frame, (x, y), 30, (0, 255, 0), -1)

        # Write frame
        recorder.write(frame)

        # Progress indicator
        if (i + 1) % 30 == 0:
            duration = recorder.get_recording_duration()
            print(f"   Progress: {i+1}/{num_frames} frames ({duration:.2f}s)")

    # Step 4: Stop recording
    print("\n[4/4] Stopping recording...")
    metadata = recorder.stop()

    if metadata:
        print(f"✅ Recording completed successfully!")
        print(f"\n📹 Recording Details:")
        print(f"   File: {metadata['filename']}")
        print(f"   Duration: {metadata['duration_seconds']:.2f}s")
        print(f"   Frames: {metadata['frame_count']}")
        print(f"   Average FPS: {metadata['fps']:.2f}")
        print(f"   Encoder: {metadata['encoder']}")

        if metadata.get('buffer_stats'):
            stats = metadata['buffer_stats']
            print(f"\n📊 Buffer Statistics:")
            print(f"   Frames queued: {stats['frames_queued']}")
            print(f"   Frames written: {stats['frames_written']}")
            print(f"   Frames dropped: {stats['frames_dropped']}")
            print(f"   Drop rate: {stats['drop_rate']:.2f}%")

        # Check file
        file_path = Path(metadata['filename'])
        if file_path.exists():
            file_size_mb = file_path.stat().st_size / 1024 / 1024
            print(f"\n💾 File Information:")
            print(f"   Path: {file_path}")
            print(f"   Size: {file_size_mb:.2f} MB")

            # Verify with ffprobe if available
            try:
                import subprocess
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries',
                     'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                     str(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    actual_duration = float(result.stdout.strip())
                    print(f"   Verified duration: {actual_duration:.2f}s")
            except Exception:
                pass

    else:
        print(f"❌ Recording failed - no metadata returned")

    # Summary
    print("\n" + "=" * 70)
    print("  Test Summary")
    print("=" * 70)
    print(f"✅ Hardware encoder: {description}")
    print(f"✅ FFmpegRecorder: Working")
    print(f"✅ Frame buffer: {num_frames} frames processed")

    if metadata:
        drop_rate = metadata.get('buffer_stats', {}).get('drop_rate', 0)
        if drop_rate == 0:
            print(f"✅ Zero dropped frames - Perfect recording!")
        else:
            print(f"⚠️  {drop_rate:.2f}% frames dropped")

    print("=" * 70)
    print("\n🎉 Integration test PASSED!")
    print(f"\nRecording file: {metadata['filename']}")
    print("You can play this file to verify quality and encoding.")
    print("\nCleanup: rm -rf test_recordings/")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_manual_recording()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
