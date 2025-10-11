# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Image Quality Processor for OpenEye v3.5.0
Provides granular image adjustments: brightness, contrast, saturation, sharpness
"""
import cv2
import numpy as np
from typing import Optional, Tuple


class ImageProcessor:
    """
    Processes video frames with quality adjustments.
    
    Features:
    - Brightness adjustment (-100 to +100)
    - Contrast adjustment (0.5 to 3.0)
    - Saturation adjustment (0.0 to 2.0)
    - Sharpness enhancement (none, low, medium, high)
    - Noise reduction (0-100 strength)
    """
    
    # Sharpness kernel configurations
    SHARPNESS_KERNELS = {
        'none': None,
        'low': np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ], dtype=np.float32),
        'medium': np.array([
            [-1, -1, -1],
            [-1, 9, -1],
            [-1, -1, -1]
        ], dtype=np.float32),
        'high': np.array([
            [-1, -2, -1],
            [-2, 13, -2],
            [-1, -2, -1]
        ], dtype=np.float32)
    }
    
    def __init__(
        self,
        brightness: int = 0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: str = 'none',
        noise_reduction_strength: int = 0
    ):
        """
        Initialize image processor with quality settings.
        
        Args:
            brightness: Brightness adjustment (-100 to +100)
            contrast: Contrast multiplier (0.5 to 3.0)
            saturation: Saturation multiplier (0.0 to 2.0)
            sharpness: Sharpness level ('none', 'low', 'medium', 'high')
            noise_reduction_strength: Noise reduction strength (0-100)
        """
        self.brightness = max(-100, min(100, brightness))
        self.contrast = max(0.5, min(3.0, contrast))
        self.saturation = max(0.0, min(2.0, saturation))
        self.sharpness = sharpness.lower() if sharpness else 'none'
        self.noise_reduction_strength = max(0, min(100, noise_reduction_strength))
        
        # Get sharpness kernel
        self.sharpness_kernel = self.SHARPNESS_KERNELS.get(
            self.sharpness,
            self.SHARPNESS_KERNELS['none']
        )
    
    def update_settings(
        self,
        brightness: Optional[int] = None,
        contrast: Optional[float] = None,
        saturation: Optional[float] = None,
        sharpness: Optional[str] = None,
        noise_reduction_strength: Optional[int] = None
    ):
        """
        Update image processing settings dynamically.
        
        Args:
            brightness: New brightness value
            contrast: New contrast value
            saturation: New saturation value
            sharpness: New sharpness level
            noise_reduction_strength: New noise reduction strength
        """
        if brightness is not None:
            self.brightness = max(-100, min(100, brightness))
        
        if contrast is not None:
            self.contrast = max(0.5, min(3.0, contrast))
        
        if saturation is not None:
            self.saturation = max(0.0, min(2.0, saturation))
        
        if sharpness is not None:
            self.sharpness = sharpness.lower()
            self.sharpness_kernel = self.SHARPNESS_KERNELS.get(
                self.sharpness,
                self.SHARPNESS_KERNELS['none']
            )
        
        if noise_reduction_strength is not None:
            self.noise_reduction_strength = max(0, min(100, noise_reduction_strength))
    
    def adjust_brightness(self, frame: np.ndarray) -> np.ndarray:
        """
        Adjust frame brightness.
        
        Args:
            frame: Input frame
            
        Returns:
            Brightness-adjusted frame
        """
        if self.brightness == 0:
            return frame
        
        # Add brightness value to all pixels
        if self.brightness > 0:
            return cv2.add(frame, np.array([self.brightness]))
        else:
            return cv2.subtract(frame, np.array([abs(self.brightness)]))
    
    def adjust_contrast(self, frame: np.ndarray) -> np.ndarray:
        """
        Adjust frame contrast.
        
        Args:
            frame: Input frame
            
        Returns:
            Contrast-adjusted frame
        """
        if self.contrast == 1.0:
            return frame
        
        # Apply contrast using convertScaleAbs
        return cv2.convertScaleAbs(frame, alpha=self.contrast, beta=0)
    
    def adjust_saturation(self, frame: np.ndarray) -> np.ndarray:
        """
        Adjust frame saturation.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Saturation-adjusted frame (BGR)
        """
        if self.saturation == 1.0:
            return frame
        
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        
        # Adjust saturation channel
        hsv[:, :, 1] = hsv[:, :, 1] * self.saturation
        
        # Clip values to valid range
        hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
        
        # Convert back to BGR
        hsv = hsv.astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    def apply_sharpness(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply sharpness filter to frame.
        
        Args:
            frame: Input frame
            
        Returns:
            Sharpened frame
        """
        if self.sharpness_kernel is None:
            return frame
        
        # Apply sharpening kernel
        return cv2.filter2D(frame, -1, self.sharpness_kernel)
    
    def apply_noise_reduction(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction to frame.
        
        Args:
            frame: Input frame
            
        Returns:
            Noise-reduced frame
        """
        if self.noise_reduction_strength == 0:
            return frame
        
        # Map strength 0-100 to kernel size 3-21 (odd numbers only)
        kernel_size = int((self.noise_reduction_strength / 100) * 9) * 2 + 3
        kernel_size = min(kernel_size, 21)  # Cap at 21
        
        # Apply bilateral filter for noise reduction while preserving edges
        return cv2.bilateralFilter(frame, kernel_size, kernel_size * 2, kernel_size / 2)
    
    def process(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply all image quality adjustments to frame.
        
        Processing order:
        1. Noise reduction (if enabled)
        2. Brightness
        3. Contrast
        4. Saturation
        5. Sharpness
        
        Args:
            frame: Input frame
            
        Returns:
            Processed frame with all adjustments applied
        """
        # Apply noise reduction first
        if self.noise_reduction_strength > 0:
            frame = self.apply_noise_reduction(frame)
        
        # Apply brightness
        if self.brightness != 0:
            frame = self.adjust_brightness(frame)
        
        # Apply contrast
        if self.contrast != 1.0:
            frame = self.adjust_contrast(frame)
        
        # Apply saturation
        if self.saturation != 1.0:
            frame = self.adjust_saturation(frame)
        
        # Apply sharpness
        if self.sharpness != 'none':
            frame = self.apply_sharpness(frame)
        
        return frame
    
    def get_settings(self) -> dict:
        """
        Get current image processing settings.
        
        Returns:
            Dictionary with current settings
        """
        return {
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation,
            'sharpness': self.sharpness,
            'noise_reduction_strength': self.noise_reduction_strength
        }
    
    def has_adjustments(self) -> bool:
        """
        Check if any adjustments are active.
        
        Returns:
            True if any adjustment is non-default
        """
        return (
            self.brightness != 0 or
            self.contrast != 1.0 or
            self.saturation != 1.0 or
            self.sharpness != 'none' or
            self.noise_reduction_strength > 0
        )
