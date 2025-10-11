# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Video Quality Processor for OpenEye v3.5.0
Provides resolution, FPS, bitrate, and codec controls
"""
import cv2
import numpy as np
import time
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class VideoSettings:
    """Video quality settings configuration"""
    resolution: str = '1920x1080'
    fps_target: int = 15
    bitrate_kbps: int = 2000
    codec: str = 'h264'
    
    def get_resolution_tuple(self) -> Tuple[int, int]:
        """Parse resolution string to (width, height) tuple"""
        try:
            width, height = self.resolution.split('x')
            return (int(width), int(height))
        except:
            return (1920, 1080)  # Default fallback


class VideoProcessor:
    """
    Manages video quality settings for camera streams.
    
    Features:
    - Resolution control with aspect ratio preservation
    - FPS limiting via frame skip logic
    - Bitrate management (for recording)
    - Codec selection (H.264, H.265, MJPEG)
    - Dynamic quality adjustment
    """
    
    # Standard resolutions with aspect ratios
    STANDARD_RESOLUTIONS = {
        '3840x2160': (3840, 2160, '16:9'),  # 4K
        '2560x1440': (2560, 1440, '16:9'),  # 1440p
        '1920x1080': (1920, 1080, '16:9'),  # 1080p (default)
        '1280x720': (1280, 720, '16:9'),    # 720p
        '854x480': (854, 480, '16:9'),      # 480p
        '640x480': (640, 480, '4:3'),       # VGA
        '320x240': (320, 240, '4:3'),       # QVGA
    }
    
    # Codec mappings for OpenCV
    CODEC_FOURCC = {
        'h264': 'H264',
        'h265': 'HEVC',
        'mjpeg': 'MJPG',
        'xvid': 'XVID',
        'mp4v': 'MP4V'
    }
    
    def __init__(
        self,
        resolution: str = '1920x1080',
        fps_target: int = 15,
        bitrate_kbps: int = 2000,
        codec: str = 'h264'
    ):
        """
        Initialize video processor with quality settings.
        
        Args:
            resolution: Target resolution (e.g., '1920x1080')
            fps_target: Target frames per second (1-30)
            bitrate_kbps: Target bitrate in kbps (500-10000)
            codec: Video codec ('h264', 'h265', 'mjpeg')
        """
        self.settings = VideoSettings(
            resolution=resolution,
            fps_target=max(1, min(30, fps_target)),
            bitrate_kbps=max(500, min(10000, bitrate_kbps)),
            codec=codec.lower() if codec else 'h264'
        )
        
        # FPS control
        self.frame_interval = 1.0 / self.settings.fps_target
        self.last_frame_time = 0
        self.frames_processed = 0
        self.frames_skipped = 0
        
        # Performance tracking
        self.avg_processing_time = 0
        self.processing_times = []
        
    def update_settings(
        self,
        resolution: Optional[str] = None,
        fps_target: Optional[int] = None,
        bitrate_kbps: Optional[int] = None,
        codec: Optional[str] = None
    ):
        """
        Update video processing settings dynamically.
        
        Args:
            resolution: New target resolution
            fps_target: New target FPS
            bitrate_kbps: New target bitrate
            codec: New codec selection
        """
        if resolution is not None:
            self.settings.resolution = resolution
        
        if fps_target is not None:
            self.settings.fps_target = max(1, min(30, fps_target))
            self.frame_interval = 1.0 / self.settings.fps_target
        
        if bitrate_kbps is not None:
            self.settings.bitrate_kbps = max(500, min(10000, bitrate_kbps))
        
        if codec is not None:
            self.settings.codec = codec.lower()
    
    def should_process_frame(self) -> bool:
        """
        Determine if current frame should be processed based on FPS target.
        
        Returns:
            True if frame should be processed, False to skip
        """
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        
        if elapsed >= self.frame_interval:
            self.last_frame_time = current_time
            self.frames_processed += 1
            return True
        else:
            self.frames_skipped += 1
            return False
    
    def resize_frame(
        self,
        frame: np.ndarray,
        preserve_aspect: bool = True
    ) -> np.ndarray:
        """
        Resize frame to target resolution.
        
        Args:
            frame: Input frame
            preserve_aspect: Whether to preserve aspect ratio (adds letterboxing if needed)
            
        Returns:
            Resized frame
        """
        target_width, target_height = self.settings.get_resolution_tuple()
        
        # If already at target resolution, return as-is
        h, w = frame.shape[:2]
        if w == target_width and h == target_height:
            return frame
        
        if not preserve_aspect:
            # Simple resize to exact dimensions
            return cv2.resize(frame, (target_width, target_height))
        
        # Calculate scaling factor to fit within target dimensions
        scale_w = target_width / w
        scale_h = target_height / h
        scale = min(scale_w, scale_h)
        
        # Calculate new dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize to fit
        resized = cv2.resize(frame, (new_w, new_h))
        
        # If dimensions match target, return
        if new_w == target_width and new_h == target_height:
            return resized
        
        # Add letterboxing/pillarboxing to reach exact target dimensions
        canvas = np.zeros((target_height, target_width, 3), dtype=np.uint8)
        
        # Calculate positioning (center the resized frame)
        x_offset = (target_width - new_w) // 2
        y_offset = (target_height - new_h) // 2
        
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        return canvas
    
    def get_codec_fourcc(self) -> int:
        """
        Get OpenCV FourCC code for current codec.
        
        Returns:
            FourCC code for cv2.VideoWriter
        """
        codec_str = self.CODEC_FOURCC.get(
            self.settings.codec,
            self.CODEC_FOURCC['h264']
        )
        return cv2.VideoWriter_fourcc(*codec_str)
    
    def calculate_jpeg_quality(self) -> int:
        """
        Calculate JPEG quality based on bitrate setting.
        Maps bitrate to quality percentage for snapshots.
        
        Returns:
            JPEG quality (1-100)
        """
        # Map bitrate range (500-10000) to quality range (50-100)
        bitrate = self.settings.bitrate_kbps
        
        if bitrate <= 500:
            return 50
        elif bitrate >= 10000:
            return 100
        else:
            # Linear interpolation
            quality = 50 + ((bitrate - 500) / (10000 - 500)) * 50
            return int(quality)
    
    def estimate_bandwidth(self, frame: np.ndarray) -> float:
        """
        Estimate bandwidth usage in kbps based on current settings.
        
        Args:
            frame: Sample frame for calculation
            
        Returns:
            Estimated bandwidth in kbps
        """
        # Get frame dimensions
        h, w = frame.shape[:2]
        target_w, target_h = self.settings.get_resolution_tuple()
        
        # Calculate pixel count (after resize)
        pixels = target_w * target_h
        
        # Estimate bits per pixel based on codec
        if self.settings.codec == 'mjpeg':
            bpp = 8  # MJPEG is less efficient
        elif self.settings.codec == 'h265':
            bpp = 0.1  # H.265 is very efficient
        else:  # h264
            bpp = 0.2  # H.264 balance
        
        # Calculate bandwidth: pixels * bpp * fps / 1000
        bandwidth = (pixels * bpp * self.settings.fps_target) / 1000
        
        # Factor in target bitrate as upper limit
        return min(bandwidth, self.settings.bitrate_kbps)
    
    def get_recommended_resolution(
        self,
        available_bandwidth_kbps: float
    ) -> str:
        """
        Recommend optimal resolution based on available bandwidth.
        
        Args:
            available_bandwidth_kbps: Available bandwidth
            
        Returns:
            Recommended resolution string
        """
        # Resolution recommendations based on bandwidth
        bandwidth_map = {
            500: '640x480',
            1000: '854x480',
            2000: '1280x720',
            4000: '1920x1080',
            8000: '2560x1440',
            15000: '3840x2160'
        }
        
        for bandwidth, resolution in sorted(bandwidth_map.items()):
            if available_bandwidth_kbps <= bandwidth:
                return resolution
        
        return '3840x2160'  # Maximum if bandwidth is high
    
    def track_performance(self, processing_time: float):
        """
        Track frame processing performance.
        
        Args:
            processing_time: Time taken to process frame in seconds
        """
        self.processing_times.append(processing_time)
        
        # Keep only last 100 samples
        if len(self.processing_times) > 100:
            self.processing_times.pop(0)
        
        # Update average
        self.avg_processing_time = sum(self.processing_times) / len(self.processing_times)
    
    def get_statistics(self) -> dict:
        """
        Get video processing statistics.
        
        Returns:
            Dictionary with processing stats
        """
        total_frames = self.frames_processed + self.frames_skipped
        skip_rate = (self.frames_skipped / total_frames * 100) if total_frames > 0 else 0
        
        actual_fps = 1.0 / self.avg_processing_time if self.avg_processing_time > 0 else 0
        
        return {
            'settings': {
                'resolution': self.settings.resolution,
                'target_fps': self.settings.fps_target,
                'bitrate_kbps': self.settings.bitrate_kbps,
                'codec': self.settings.codec
            },
            'performance': {
                'frames_processed': self.frames_processed,
                'frames_skipped': self.frames_skipped,
                'skip_rate_percent': round(skip_rate, 2),
                'avg_processing_time_ms': round(self.avg_processing_time * 1000, 2),
                'actual_fps': round(actual_fps, 2)
            }
        }
    
    def get_settings(self) -> dict:
        """
        Get current video processing settings.
        
        Returns:
            Dictionary with current settings
        """
        return {
            'resolution': self.settings.resolution,
            'fps_target': self.settings.fps_target,
            'bitrate_kbps': self.settings.bitrate_kbps,
            'codec': self.settings.codec,
            'frame_interval': self.frame_interval,
            'jpeg_quality': self.calculate_jpeg_quality()
        }
    
    def reset_statistics(self):
        """Reset performance tracking statistics."""
        self.frames_processed = 0
        self.frames_skipped = 0
        self.processing_times = []
        self.avg_processing_time = 0
        self.last_frame_time = time.time()


# Preset configurations for common scenarios
VIDEO_PRESETS = {
    'ultra_quality': VideoSettings(
        resolution='1920x1080',
        fps_target=30,
        bitrate_kbps=10000,
        codec='h265'
    ),
    'high_quality': VideoSettings(
        resolution='1920x1080',
        fps_target=20,
        bitrate_kbps=5000,
        codec='h264'
    ),
    'balanced': VideoSettings(
        resolution='1280x720',
        fps_target=15,
        bitrate_kbps=2000,
        codec='h264'
    ),
    'low_bandwidth': VideoSettings(
        resolution='854x480',
        fps_target=10,
        bitrate_kbps=500,
        codec='h264'
    ),
    'minimal_bandwidth': VideoSettings(
        resolution='640x480',
        fps_target=5,
        bitrate_kbps=500,
        codec='mjpeg'
    )
}


def get_preset(preset_name: str) -> Optional[VideoSettings]:
    """
    Get video settings preset by name.
    
    Args:
        preset_name: Name of preset
        
    Returns:
        VideoSettings object or None if preset not found
    """
    return VIDEO_PRESETS.get(preset_name.lower())


def list_available_resolutions() -> list:
    """
    List all available standard resolutions.
    
    Returns:
        List of resolution strings
    """
    return list(VideoProcessor.STANDARD_RESOLUTIONS.keys())


def list_available_codecs() -> list:
    """
    List all available codecs.
    
    Returns:
        List of codec strings
    """
    return list(VideoProcessor.CODEC_FOURCC.keys())
