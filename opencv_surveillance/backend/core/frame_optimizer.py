# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Frame Processing Optimizations
CPU-friendly optimizations for frame processing
"""

import cv2
import numpy as np
import time
from typing import Optional, Tuple, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationStats:
    """Statistics for optimization performance"""
    frames_processed: int = 0
    frames_skipped: int = 0
    frames_scaled: int = 0
    total_time_saved_ms: float = 0.0
    cpu_reduction_percent: float = 0.0


class AdaptiveFrameProcessor:
    """
    Adaptive Frame Rate Processor
    Skips frames when idle to reduce CPU usage
    """

    def __init__(
        self,
        idle_skip_factor: int = 5,
        active_skip_factor: int = 1,
        motion_threshold_seconds: float = 10.0
    ):
        """
        Initialize adaptive frame processor

        Args:
            idle_skip_factor: Skip N-1 out of N frames when idle (5 = process every 5th frame)
            active_skip_factor: Skip factor when motion detected (1 = process all frames)
            motion_threshold_seconds: Seconds after last motion to consider idle
        """
        self.idle_skip_factor = idle_skip_factor
        self.active_skip_factor = active_skip_factor
        self.motion_threshold_seconds = motion_threshold_seconds

        self.frame_counter = 0
        self.last_motion_time = 0.0
        self.is_active = False

        self.stats = OptimizationStats()

    def should_process_frame(self, motion_detected: bool = False) -> bool:
        """
        Determine if current frame should be processed

        Args:
            motion_detected: Whether motion was detected in previous frame

        Returns:
            True if frame should be processed
        """
        self.frame_counter += 1
        current_time = time.time()

        # Update activity state
        if motion_detected:
            self.last_motion_time = current_time
            self.is_active = True
        elif (current_time - self.last_motion_time) > self.motion_threshold_seconds:
            self.is_active = False

        # Determine skip factor based on activity
        skip_factor = self.active_skip_factor if self.is_active else self.idle_skip_factor

        # Should we process this frame?
        should_process = (self.frame_counter % skip_factor) == 0

        if should_process:
            self.stats.frames_processed += 1
        else:
            self.stats.frames_skipped += 1
            # Estimate time saved (avg ~30ms per frame for full processing)
            self.stats.total_time_saved_ms += 30

        return should_process

    def get_stats(self) -> Dict:
        """Get optimization statistics"""
        total_frames = self.stats.frames_processed + self.stats.frames_skipped

        if total_frames > 0:
            skip_percent = (self.stats.frames_skipped / total_frames) * 100
            self.stats.cpu_reduction_percent = skip_percent
        else:
            self.stats.cpu_reduction_percent = 0.0

        return {
            'frames_processed': self.stats.frames_processed,
            'frames_skipped': self.stats.frames_skipped,
            'skip_percent': self.stats.cpu_reduction_percent,
            'time_saved_seconds': self.stats.total_time_saved_ms / 1000.0,
            'is_active': self.is_active
        }

    def reset_stats(self):
        """Reset statistics"""
        self.stats = OptimizationStats()
        self.frame_counter = 0


class ResolutionScaler:
    """
    Frame Resolution Scaler
    Process at lower resolution, record at original
    """

    def __init__(
        self,
        processing_resolution: Optional[Tuple[int, int]] = None,
        auto_scale: bool = True,
        max_processing_width: int = 1280
    ):
        """
        Initialize resolution scaler

        Args:
            processing_resolution: Target resolution for processing (width, height)
            auto_scale: Automatically determine optimal scale factor
            max_processing_width: Maximum width for processing if auto_scale enabled
        """
        self.processing_resolution = processing_resolution
        self.auto_scale = auto_scale
        self.max_processing_width = max_processing_width

        self.original_resolution = None
        self.scale_factor = 1.0
        self.processing_size = None

        self.stats = OptimizationStats()

    def scale_frame_for_processing(self, frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Scale frame down for processing

        Args:
            frame: Original frame

        Returns:
            (scaled_frame, scale_factor)
        """
        if frame is None or frame.size == 0:
            return frame, 1.0

        original_height, original_width = frame.shape[:2]

        # Store original resolution
        if self.original_resolution is None:
            self.original_resolution = (original_width, original_height)

        # Determine target resolution
        if self.auto_scale:
            # Auto-scale to max width while maintaining aspect ratio
            if original_width > self.max_processing_width:
                scale_factor = self.max_processing_width / original_width
                target_width = self.max_processing_width
                target_height = int(original_height * scale_factor)
            else:
                # Already small enough
                return frame, 1.0
        elif self.processing_resolution:
            # Use specified resolution
            target_width, target_height = self.processing_resolution
            scale_factor = target_width / original_width
        else:
            # No scaling
            return frame, 1.0

        # Scale frame
        scaled_frame = cv2.resize(
            frame,
            (target_width, target_height),
            interpolation=cv2.INTER_LINEAR
        )

        # Update stats
        self.scale_factor = scale_factor
        self.processing_size = (target_width, target_height)
        self.stats.frames_scaled += 1

        # Calculate time saved (rough estimate based on pixel reduction)
        original_pixels = original_width * original_height
        scaled_pixels = target_width * target_height
        pixel_reduction = (original_pixels - scaled_pixels) / original_pixels

        # Estimate ~20ms saved per 50% pixel reduction
        time_saved = 20 * pixel_reduction
        self.stats.total_time_saved_ms += time_saved

        return scaled_frame, scale_factor

    def scale_coordinates(
        self,
        coordinates: Tuple[int, int, int, int],
        scale_factor: Optional[float] = None
    ) -> Tuple[int, int, int, int]:
        """
        Scale coordinates from processing resolution back to original

        Args:
            coordinates: (x1, y1, x2, y2) in processing resolution
            scale_factor: Scale factor (uses stored factor if None)

        Returns:
            (x1, y1, x2, y2) in original resolution
        """
        if scale_factor is None:
            scale_factor = self.scale_factor

        if scale_factor == 1.0:
            return coordinates

        x1, y1, x2, y2 = coordinates

        # Scale up coordinates
        x1_scaled = int(x1 / scale_factor)
        y1_scaled = int(y1 / scale_factor)
        x2_scaled = int(x2 / scale_factor)
        y2_scaled = int(y2 / scale_factor)

        return (x1_scaled, y1_scaled, x2_scaled, y2_scaled)

    def scale_point(
        self,
        point: Tuple[int, int],
        scale_factor: Optional[float] = None
    ) -> Tuple[int, int]:
        """
        Scale a single point from processing resolution to original

        Args:
            point: (x, y) in processing resolution
            scale_factor: Scale factor (uses stored factor if None)

        Returns:
            (x, y) in original resolution
        """
        if scale_factor is None:
            scale_factor = self.scale_factor

        if scale_factor == 1.0:
            return point

        x, y = point
        x_scaled = int(x / scale_factor)
        y_scaled = int(y / scale_factor)

        return (x_scaled, y_scaled)

    def get_stats(self) -> Dict:
        """Get optimization statistics"""
        if self.original_resolution and self.processing_size:
            orig_pixels = self.original_resolution[0] * self.original_resolution[1]
            proc_pixels = self.processing_size[0] * self.processing_size[1]
            pixel_reduction = ((orig_pixels - proc_pixels) / orig_pixels) * 100
        else:
            pixel_reduction = 0.0

        return {
            'original_resolution': self.original_resolution,
            'processing_resolution': self.processing_size,
            'scale_factor': self.scale_factor,
            'pixel_reduction_percent': pixel_reduction,
            'frames_scaled': self.stats.frames_scaled,
            'time_saved_seconds': self.stats.total_time_saved_ms / 1000.0
        }

    def reset_stats(self):
        """Reset statistics"""
        self.stats = OptimizationStats()


class FrameOptimizer:
    """
    Combined frame optimization system
    Manages both adaptive frame rate and resolution scaling
    """

    def __init__(
        self,
        enable_adaptive_frame_rate: bool = False,
        enable_resolution_scaling: bool = False,
        adaptive_config: Optional[Dict] = None,
        scaling_config: Optional[Dict] = None
    ):
        """
        Initialize frame optimizer

        Args:
            enable_adaptive_frame_rate: Enable adaptive frame rate
            enable_resolution_scaling: Enable resolution scaling
            adaptive_config: Configuration for adaptive frame rate
            scaling_config: Configuration for resolution scaling
        """
        self.enable_adaptive_frame_rate = enable_adaptive_frame_rate
        self.enable_resolution_scaling = enable_resolution_scaling

        # Initialize adaptive frame processor
        if adaptive_config:
            self.adaptive_processor = AdaptiveFrameProcessor(**adaptive_config)
        else:
            self.adaptive_processor = AdaptiveFrameProcessor()

        # Initialize resolution scaler
        if scaling_config:
            self.resolution_scaler = ResolutionScaler(**scaling_config)
        else:
            self.resolution_scaler = ResolutionScaler()

    def should_process_frame(self, motion_detected: bool = False) -> bool:
        """
        Check if frame should be processed

        Args:
            motion_detected: Whether motion was detected

        Returns:
            True if frame should be processed
        """
        if not self.enable_adaptive_frame_rate:
            return True

        return self.adaptive_processor.should_process_frame(motion_detected)

    def prepare_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Prepare frame for processing (scale if enabled)

        Args:
            frame: Original frame

        Returns:
            (processed_frame, scale_factor)
        """
        if not self.enable_resolution_scaling:
            return frame, 1.0

        return self.resolution_scaler.scale_frame_for_processing(frame)

    def scale_coordinates_to_original(
        self,
        coordinates: Tuple[int, int, int, int],
        scale_factor: Optional[float] = None
    ) -> Tuple[int, int, int, int]:
        """
        Scale coordinates from processing resolution back to original

        Args:
            coordinates: (x1, y1, x2, y2)
            scale_factor: Scale factor

        Returns:
            (x1, y1, x2, y2) in original resolution
        """
        if not self.enable_resolution_scaling:
            return coordinates

        return self.resolution_scaler.scale_coordinates(coordinates, scale_factor)

    def get_combined_stats(self) -> Dict:
        """Get combined optimization statistics"""
        stats = {
            'adaptive_frame_rate': {
                'enabled': self.enable_adaptive_frame_rate,
                **self.adaptive_processor.get_stats()
            } if self.enable_adaptive_frame_rate else {'enabled': False},

            'resolution_scaling': {
                'enabled': self.enable_resolution_scaling,
                **self.resolution_scaler.get_stats()
            } if self.enable_resolution_scaling else {'enabled': False}
        }

        # Calculate combined savings
        total_time_saved = 0.0
        if self.enable_adaptive_frame_rate:
            total_time_saved += self.adaptive_processor.stats.total_time_saved_ms / 1000.0
        if self.enable_resolution_scaling:
            total_time_saved += self.resolution_scaler.stats.total_time_saved_ms / 1000.0

        stats['combined'] = {
            'total_time_saved_seconds': total_time_saved,
            'estimated_cpu_reduction_percent': (
                self.adaptive_processor.stats.cpu_reduction_percent
                if self.enable_adaptive_frame_rate else 0.0
            )
        }

        return stats

    def reset_stats(self):
        """Reset all statistics"""
        self.adaptive_processor.reset_stats()
        self.resolution_scaler.reset_stats()


def create_optimizer_from_config(config: Dict) -> FrameOptimizer:
    """
    Create FrameOptimizer from configuration dictionary

    Args:
        config: Configuration dict with keys:
            - adaptive_frame_rate: bool
            - resolution_scaling: bool
            - idle_skip_factor: int
            - active_skip_factor: int
            - processing_resolution: tuple or None
            - max_processing_width: int

    Returns:
        FrameOptimizer instance
    """
    adaptive_config = {}
    if 'idle_skip_factor' in config:
        adaptive_config['idle_skip_factor'] = config['idle_skip_factor']
    if 'active_skip_factor' in config:
        adaptive_config['active_skip_factor'] = config['active_skip_factor']
    if 'motion_threshold_seconds' in config:
        adaptive_config['motion_threshold_seconds'] = config['motion_threshold_seconds']

    scaling_config = {}
    if 'processing_resolution' in config:
        scaling_config['processing_resolution'] = config['processing_resolution']
    if 'max_processing_width' in config:
        scaling_config['max_processing_width'] = config['max_processing_width']

    return FrameOptimizer(
        enable_adaptive_frame_rate=config.get('adaptive_frame_rate', False),
        enable_resolution_scaling=config.get('resolution_scaling', False),
        adaptive_config=adaptive_config if adaptive_config else None,
        scaling_config=scaling_config if scaling_config else None
    )
