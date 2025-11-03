"""
Video Utilities

Helper functions for video file analysis and optimization
"""

import cv2
import os
import subprocess
import json
from typing import Optional, Dict, Any


def get_actual_video_duration(video_path: str) -> Optional[float]:
    """
    Get the actual duration of a video file by reading it with OpenCV.

    This returns the true playback duration, not the wall-clock recording time.

    Args:
        video_path: Path to the video file

    Returns:
        Duration in seconds, or None if unable to read
    """
    if not os.path.exists(video_path):
        return None

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        cap.release()

        if fps > 0 and frame_count > 0:
            # Calculate actual duration
            duration = frame_count / fps
            return duration

        return None
    except Exception as e:
        print(f"Error reading video duration for {video_path}: {e}")
        return None


def get_video_info(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive video file information using OpenCV.

    Args:
        video_path: Path to the video file

    Returns:
        Dictionary with video properties, or None if unable to read
    """
    if not os.path.exists(video_path):
        return None

    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None

        # Get all properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        cap.release()

        # Calculate duration
        duration = frame_count / fps if fps > 0 else 0

        # Get file size
        file_size = os.path.getsize(video_path)

        return {
            "fps": fps,
            "frame_count": int(frame_count),
            "width": width,
            "height": height,
            "duration_seconds": duration,
            "file_size_bytes": file_size,
            "bitrate_kbps": (file_size * 8) / (duration * 1000) if duration > 0 else 0
        }
    except Exception as e:
        print(f"Error getting video info for {video_path}: {e}")
        return None


def get_video_info_ffprobe(video_path: str) -> Optional[Dict[str, Any]]:
    """
    Get video information using ffprobe (more accurate than OpenCV).

    This requires ffmpeg/ffprobe to be installed on the system.
    Falls back to OpenCV method if ffprobe is not available.

    Args:
        video_path: Path to the video file

    Returns:
        Dictionary with video properties, or None if unable to read
    """
    if not os.path.exists(video_path):
        return None

    try:
        # Try using ffprobe for more accurate results
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            data = json.loads(result.stdout)

            # Extract video stream info
            video_stream = next(
                (s for s in data.get('streams', []) if s.get('codec_type') == 'video'),
                None
            )

            if video_stream:
                # Get format info
                format_info = data.get('format', {})

                # Parse FPS
                fps_str = video_stream.get('r_frame_rate', '0/1')
                fps_parts = fps_str.split('/')
                fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 0

                return {
                    "fps": fps,
                    "frame_count": int(video_stream.get('nb_frames', 0)),
                    "width": int(video_stream.get('width', 0)),
                    "height": int(video_stream.get('height', 0)),
                    "duration_seconds": float(format_info.get('duration', 0)),
                    "file_size_bytes": int(format_info.get('size', 0)),
                    "bitrate_kbps": int(format_info.get('bit_rate', 0)) / 1000,
                    "codec": video_stream.get('codec_name', 'unknown')
                }
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        # ffprobe not available or failed, fall back to OpenCV
        print(f"ffprobe failed for {video_path}, falling back to OpenCV: {e}")

    # Fallback to OpenCV method
    return get_video_info(video_path)


def verify_video_integrity(video_path: str) -> Dict[str, Any]:
    """
    Verify video file integrity and check for common issues.

    Args:
        video_path: Path to the video file

    Returns:
        Dictionary with verification results
    """
    result = {
        "valid": False,
        "exists": False,
        "readable": False,
        "has_frames": False,
        "frame_count": 0,
        "duration": 0,
        "issues": []
    }

    # Check file exists
    if not os.path.exists(video_path):
        result["issues"].append("File does not exist")
        return result

    result["exists"] = True

    # Check file size
    file_size = os.path.getsize(video_path)
    if file_size == 0:
        result["issues"].append("File is empty (0 bytes)")
        return result

    if file_size < 1024:  # Less than 1 KB
        result["issues"].append(f"File is suspiciously small ({file_size} bytes)")

    # Try to read video
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            result["issues"].append("Unable to open video file")
            return result

        result["readable"] = True

        # Get properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        result["frame_count"] = frame_count

        if frame_count == 0:
            result["issues"].append("Video has 0 frames")
            cap.release()
            return result

        result["has_frames"] = True

        # Calculate duration
        if fps > 0:
            result["duration"] = frame_count / fps

        # Try to read first frame
        ret, frame = cap.read()
        if not ret or frame is None:
            result["issues"].append("Unable to read first frame")

        cap.release()

        # Check for low frame count
        if frame_count < 10:
            result["issues"].append(f"Very low frame count ({frame_count} frames)")

        # Check for FPS issues
        if fps <= 0:
            result["issues"].append("Invalid FPS value")
        elif fps < 5:
            result["issues"].append(f"Suspiciously low FPS ({fps})")

        # If no critical issues, mark as valid
        critical_issues = [
            "File does not exist",
            "File is empty (0 bytes)",
            "Unable to open video file",
            "Video has 0 frames",
            "Unable to read first frame"
        ]

        has_critical_issue = any(issue in result["issues"] for issue in critical_issues)
        result["valid"] = not has_critical_issue

    except Exception as e:
        result["issues"].append(f"Error during verification: {str(e)}")

    return result
