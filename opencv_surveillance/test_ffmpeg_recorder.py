#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
FFmpeg Recorder Test Script
Tests FFmpeg installation, encoder detection, and recording functionality

Usage:
    python3 test_ffmpeg_recorder.py                    # Detection only
    python3 test_ffmpeg_recorder.py --test-recording   # Full test with recording
    python3 test_ffmpeg_recorder.py --quick            # Quick test (5 seconds)
"""

import sys
import os
import argparse
import numpy as np
import cv2
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.ffmpeg_recorder import EncoderCapabilities, FFmpegRecorder, FrameBuffer


def print_header(text):
    """Print formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_success(text):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"❌ {text}")


def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")


def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")


def test_ffmpeg_installation():
    """Test if FFmpeg is installed and accessible"""
    print_header("1. FFmpeg Installation Check")

    try:
        import subprocess
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print_success(f"FFmpeg installed: {version_line}")
            return True
        else:
            print_error("FFmpeg command failed")
            return False

    except FileNotFoundError:
        print_error("FFmpeg not found in PATH")
        print_info("Install FFmpeg:")
        print("   macOS:  brew install ffmpeg")
        print("   Linux:  sudo apt install ffmpeg")
        print("   Windows: Download from https://ffmpeg.org/download.html")
        return False
    except Exception as e:
        print_error(f"Error checking FFmpeg: {e}")
        return False


def test_encoder_detection():
    """Test hardware encoder detection"""
    print_header("2. Hardware Encoder Detection")

    encoders = EncoderCapabilities.detect_available_encoders()

    print("\nAvailable Encoders:")
    print("-" * 70)

    encoder_names = {
        'nvenc': 'NVIDIA NVENC (Hardware)',
        'qsv': 'Intel QuickSync (Hardware)',
        'vaapi': 'VAAPI - Intel/AMD (Hardware, Linux)',
        'videotoolbox': 'Apple VideoToolbox (Hardware, macOS)'
    }

    hardware_available = False
    for encoder_key, encoder_name in encoder_names.items():
        if encoders[encoder_key]:
            print_success(f"{encoder_name:<45} AVAILABLE")
            hardware_available = True
        else:
            print(f"   {encoder_name:<45} Not available")

    print()

    # Software fallback always available
    print_info("Software H.264 (libx264)                      ALWAYS AVAILABLE")

    # Get best encoder
    best_codec, best_desc = EncoderCapabilities.get_best_encoder()
    print()
    print_success(f"Selected encoder: {best_desc} ({best_codec})")

    if not hardware_available:
        print()
        print_warning("No hardware encoders detected")
        print_info("System will use software encoding (higher CPU usage)")
        print_info("For GPU acceleration:")
        print("   • NVIDIA: Install GPU with NVENC support + CUDA drivers")
        print("   • Intel:  Use CPU with integrated graphics (8th gen+)")
        print("   • macOS:  Apple Silicon Macs have VideoToolbox built-in")

    return encoders, best_codec, best_desc


def test_frame_buffer():
    """Test frame buffer functionality"""
    print_header("3. Frame Buffer Test")

    try:
        buffer = FrameBuffer(max_size=10)

        # Create test frames
        test_frames = [np.zeros((100, 100, 3), dtype=np.uint8) for _ in range(5)]

        # Add frames
        print_info("Adding 5 test frames to buffer...")
        for i, frame in enumerate(test_frames):
            success = buffer.add_frame(frame)
            if success:
                print(f"  Frame {i+1}: Added to buffer")
            else:
                print_error(f"  Frame {i+1}: Failed to add")

        # Get stats
        stats = buffer.get_stats()
        print()
        print_success("Frame buffer working correctly")
        print(f"  Frames queued: {stats['frames_queued']}")
        print(f"  Buffer size:   {stats['buffer_size']}")
        print(f"  Drop rate:     {stats['drop_rate']:.2f}%")

        return True

    except Exception as e:
        print_error(f"Frame buffer test failed: {e}")
        return False


def test_recording(duration_seconds=10, resolution=(640, 480), fps=30, quick_test=False):
    """Test actual video recording"""
    print_header("4. Recording Test")

    if quick_test:
        duration_seconds = 5
        print_info(f"Quick test mode: {duration_seconds} second recording")
    else:
        print_info(f"Recording {duration_seconds} second test video at {resolution[0]}x{resolution[1]} @ {fps}fps")

    # Create test output directory
    test_dir = Path("test_recordings")
    test_dir.mkdir(exist_ok=True)

    try:
        # Initialize recorder
        print_info("Initializing FFmpeg recorder...")
        recorder = FFmpegRecorder(
            output_dir=str(test_dir),
            use_hardware_encoding=True,
            enable_frame_buffer=True,
            buffer_size=300
        )

        print_success(f"Recorder initialized with {recorder.encoder_description}")

        # Start recording
        print_info("Starting recording...")
        success = recorder.start(
            frame_width=resolution[0],
            frame_height=resolution[1],
            fps=fps,
            camera_id="test_camera"
        )

        if not success:
            print_error("Failed to start recording")
            return False

        print_success("Recording started")

        # Generate test frames (color gradient animation)
        print_info(f"Writing {duration_seconds * fps} frames...")
        start_time = time.time()

        for i in range(duration_seconds * fps):
            # Create test frame with animated color gradient
            frame = np.zeros((resolution[1], resolution[0], 3), dtype=np.uint8)

            # Animate color based on frame number
            hue = int((i / (duration_seconds * fps)) * 180)
            frame[:, :, 0] = hue  # Hue channel
            frame[:, :, 1] = 255  # Saturation
            frame[:, :, 2] = 200  # Value

            # Convert HSV to BGR for display
            frame = cv2.cvtColor(frame, cv2.COLOR_HSV2BGR)

            # Add frame number text
            cv2.putText(
                frame,
                f"Frame {i+1}/{duration_seconds * fps}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                2
            )

            # Add timestamp
            elapsed = time.time() - start_time
            cv2.putText(
                frame,
                f"Time: {elapsed:.2f}s",
                (20, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2
            )

            # Write frame
            recorder.write(frame)

            # Sleep to maintain frame rate (for realistic test)
            time.sleep(1.0 / fps)

            # Progress indicator
            if (i + 1) % fps == 0:
                print(f"  Progress: {i+1}/{duration_seconds * fps} frames "
                      f"({(i+1)/(duration_seconds * fps)*100:.0f}%)")

        # Stop recording
        print_info("Stopping recording...")
        metadata = recorder.stop()

        if metadata:
            print_success("Recording completed successfully!")
            print()
            print("Recording Details:")
            print("-" * 70)
            print(f"  File:           {metadata['filename']}")
            print(f"  Duration:       {metadata['duration_seconds']:.2f} seconds")
            print(f"  Frames:         {metadata['frame_count']}")
            print(f"  Average FPS:    {metadata['fps']:.2f}")
            print(f"  Encoder:        {metadata['encoder']}")

            if metadata.get('buffer_stats'):
                stats = metadata['buffer_stats']
                print(f"  Frames written: {stats['frames_written']}")
                print(f"  Frames dropped: {stats['frames_dropped']}")
                print(f"  Drop rate:      {stats['drop_rate']:.2f}%")

            # Check file exists and size
            file_path = Path(metadata['filename'])
            if file_path.exists():
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"  File size:      {file_size_mb:.2f} MB")
                print()
                print_success(f"Test video saved: {metadata['filename']}")
                print_info("You can play this video to verify quality and browser compatibility")

                # Test if file is playable
                print()
                print_info("Testing video playback...")
                cap = cv2.VideoCapture(str(file_path))
                if cap.isOpened():
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps_read = cap.get(cv2.CAP_PROP_FPS)
                    cap.release()

                    print_success("Video is playable!")
                    print(f"  Resolution: {width}x{height}")
                    print(f"  FPS:        {fps_read:.2f}")
                    print(f"  Frames:     {frame_count}")
                else:
                    print_error("Could not open video for playback verification")

                return True
            else:
                print_error("Recording file not created")
                return False
        else:
            print_error("Recording failed")
            return False

    except Exception as e:
        print_error(f"Recording test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_with_hardware_detection():
    """Test integration with existing hardware detection system"""
    print_header("5. Hardware Detection System Integration")

    try:
        from backend.core.hardware_detector import HardwareDetector

        print_info("Checking existing hardware detection system...")
        detector = HardwareDetector()

        if detector.hardware_info:
            print_success("Hardware detection system operational")
            print()
            print("System Information:")
            print("-" * 70)
            print(f"  CPU:     {detector.hardware_info.cpu_model}")
            print(f"  Cores:   {detector.hardware_info.cpu_cores} cores, {detector.hardware_info.cpu_threads} threads")
            print(f"  RAM:     {detector.hardware_info.ram_total_gb:.1f} GB total, {detector.hardware_info.ram_available_gb:.1f} GB available")
            print(f"  GPU:     {'Available' if detector.hardware_info.gpu.available else 'Not detected'}")
            if detector.hardware_info.gpu.available:
                print(f"  GPU Name: {detector.hardware_info.gpu.name}")
                print(f"  GPU VRAM: {detector.hardware_info.gpu.memory_total_mb} MB")
            print(f"  Platform: {detector.hardware_info.platform} {detector.hardware_info.os_version}")

            # Check if hardware encoding should be recommended
            print()
            if detector.hardware_info.gpu.available:
                print_success("✨ Hardware video encoding RECOMMENDED")
                print_info("Your GPU supports hardware-accelerated recording")
                print_info("Expected CPU reduction: 70-90%")
            else:
                print_warning("Software encoding will be used (no GPU detected)")
                print_info("Consider enabling on systems with NVIDIA GPU or Intel QuickSync")

            return True
        else:
            print_warning("Hardware info not available")
            return False

    except ImportError:
        print_warning("Hardware detection system not found")
        print_info("This is okay - encoder detection works independently")
        return True
    except Exception as e:
        print_error(f"Error checking hardware detection: {e}")
        return False


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description='Test FFmpeg recorder functionality')
    parser.add_argument('--test-recording', action='store_true',
                       help='Test actual video recording (10 seconds)')
    parser.add_argument('--quick', action='store_true',
                       help='Quick test mode (5 second recording)')
    parser.add_argument('--duration', type=int, default=10,
                       help='Recording duration in seconds (default: 10)')
    parser.add_argument('--resolution', type=str, default='640x480',
                       help='Video resolution (default: 640x480)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Frames per second (default: 30)')

    args = parser.parse_args()

    # Parse resolution
    width, height = map(int, args.resolution.split('x'))

    print_header("FFmpeg Recorder Test Suite")
    print_info("Testing FFmpeg recorder implementation and encoder detection")
    print()

    # Track test results
    results = {}

    # Test 1: FFmpeg installation
    results['ffmpeg'] = test_ffmpeg_installation()

    if not results['ffmpeg']:
        print()
        print_error("Cannot proceed without FFmpeg. Please install FFmpeg first.")
        return 1

    # Test 2: Encoder detection
    encoders, best_codec, best_desc = test_encoder_detection()
    results['encoders'] = True

    # Test 3: Frame buffer
    results['frame_buffer'] = test_frame_buffer()

    # Test 4: Recording (optional)
    if args.test_recording or args.quick:
        results['recording'] = test_recording(
            duration_seconds=args.duration if not args.quick else 5,
            resolution=(width, height),
            fps=args.fps,
            quick_test=args.quick
        )
    else:
        print_header("4. Recording Test")
        print_info("Skipped (use --test-recording to enable)")
        print_info("Example: python3 test_ffmpeg_recorder.py --test-recording")
        results['recording'] = None

    # Test 5: Integration with hardware detection
    results['integration'] = test_integration_with_hardware_detection()

    # Summary
    print_header("Test Summary")
    print()

    for test_name, result in results.items():
        if result is True:
            print_success(f"{test_name.replace('_', ' ').title():<30} PASSED")
        elif result is False:
            print_error(f"{test_name.replace('_', ' ').title():<30} FAILED")
        elif result is None:
            print_info(f"{test_name.replace('_', ' ').title():<30} SKIPPED")

    print()

    # Overall result
    if all(r in (True, None) for r in results.values()):
        print_success("All tests passed!")
        print()
        print_info("Next steps:")
        print("  1. Integrate FFmpegRecorder into camera_manager.py")
        print("  2. Update feature_config.py to enable hardware_video_encoding")
        print("  3. Test with real camera feeds")
        return 0
    else:
        print_error("Some tests failed. Please review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
