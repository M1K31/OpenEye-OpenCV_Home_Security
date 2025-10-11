# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Enhanced Motion Detector with Granular Controls
Supports sensitivity, threshold, noise reduction, shadow detection, and detection zones
"""
import cv2
import numpy as np
import json
from typing import Optional, Dict, List, Tuple


class MotionDetector:
    """
    Enhanced motion detector with granular controls for sensitivity,
    threshold, noise reduction, and detection zones.
    
    New in v3.5.0:
    - Motion sensitivity slider (1-10)
    - Configurable detection threshold
    - Adjustable noise reduction
    - Shadow detection toggle
    - Detection zone masking
    """
    
    # Sensitivity mapping: higher sensitivity = lower min_contour_area
    SENSITIVITY_MAP = {
        1: 5000,   # Very low - only large movements
        2: 3000,   # Low
        3: 1500,   # Below medium
        4: 800,    # Medium-low
        5: 500,    # Medium (default)
        6: 300,    # Medium-high
        7: 200,    # High
        8: 150,    # Very high
        9: 120,    # Ultra high
        10: 100    # Maximum sensitivity
    }
    
    # Noise reduction mapping: (kernel_size, morph_iterations)
    NOISE_REDUCTION_MAP = {
        'low': ((3, 3), 1),
        'medium': ((5, 5), 2),
        'high': ((7, 7), 3)
    }
    
    def __init__(
        self,
        min_contour_area: int = 500,
        sensitivity: int = 5,
        var_threshold: int = 50,
        noise_reduction: str = 'medium',
        detect_shadows: bool = True,
        detection_zones: Optional[str] = None
    ):
        """
        Initializes the enhanced motion detector.
        
        Args:
            min_contour_area: Minimum area for a contour to be considered motion (legacy)
            sensitivity: Motion sensitivity 1-10 (overrides min_contour_area if provided)
            var_threshold: Threshold on squared Mahalanobis distance (1-100)
            noise_reduction: Noise reduction level ('low', 'medium', 'high')
            detect_shadows: Whether to detect and mark shadows
            detection_zones: JSON string defining detection zone grid (optional)
        """
        # Use sensitivity to determine min_contour_area
        self.sensitivity = max(1, min(10, sensitivity))
        self.min_contour_area = self.SENSITIVITY_MAP.get(self.sensitivity, min_contour_area)
        
        # Get noise reduction parameters
        noise_reduction = noise_reduction.lower() if noise_reduction else 'medium'
        self.blur_kernel, self.morph_iterations = self.NOISE_REDUCTION_MAP.get(
            noise_reduction, 
            self.NOISE_REDUCTION_MAP['medium']
        )
        
        # Create background subtractor with configurable parameters
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=var_threshold,
            detectShadows=detect_shadows
        )
        
        # Parse detection zones if provided
        self.detection_mask = None
        if detection_zones:
            try:
                self.detection_mask = self._create_detection_mask(detection_zones)
            except Exception as e:
                print(f"Warning: Could not parse detection zones: {e}")
                self.detection_mask = None
    
    def _create_detection_mask(self, detection_zones_json: str) -> Optional[np.ndarray]:
        """
        Creates a binary mask from detection zones JSON.
        
        Format: {"width": 8, "height": 6, "zones": [[1,1,1,0,0,0,0,0], ...]}
        Where 1 = enabled zone, 0 = disabled zone
        
        Args:
            detection_zones_json: JSON string defining zone grid
            
        Returns:
            Binary mask as numpy array or None if parsing fails
        """
        try:
            zones_data = json.loads(detection_zones_json)
            grid_width = zones_data.get('width', 8)
            grid_height = zones_data.get('height', 6)
            zones = zones_data.get('zones', [])
            
            if not zones or len(zones) != grid_height:
                return None
            
            # Create binary mask (will be resized to frame size during detection)
            mask = np.zeros((grid_height, grid_width), dtype=np.uint8)
            
            for y, row in enumerate(zones):
                for x, enabled in enumerate(row):
                    if x < grid_width and enabled:
                        mask[y, x] = 255
            
            return mask
            
        except Exception as e:
            print(f"Error creating detection mask: {e}")
            return None
    
    def update_settings(
        self,
        sensitivity: Optional[int] = None,
        var_threshold: Optional[int] = None,
        noise_reduction: Optional[str] = None,
        detect_shadows: Optional[bool] = None,
        detection_zones: Optional[str] = None
    ):
        """
        Updates motion detection settings dynamically.
        
        Args:
            sensitivity: New sensitivity level (1-10)
            var_threshold: New detection threshold
            noise_reduction: New noise reduction level
            detect_shadows: Enable/disable shadow detection
            detection_zones: New detection zones JSON
        """
        if sensitivity is not None:
            self.sensitivity = max(1, min(10, sensitivity))
            self.min_contour_area = self.SENSITIVITY_MAP.get(self.sensitivity, 500)
        
        if noise_reduction is not None:
            noise_reduction = noise_reduction.lower()
            self.blur_kernel, self.morph_iterations = self.NOISE_REDUCTION_MAP.get(
                noise_reduction,
                self.NOISE_REDUCTION_MAP['medium']
            )
        
        # Note: var_threshold and detect_shadows require recreating the background subtractor
        if var_threshold is not None or detect_shadows is not None:
            current_threshold = var_threshold if var_threshold is not None else 50
            current_shadows = detect_shadows if detect_shadows is not None else True
            
            self.back_sub = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=current_threshold,
                detectShadows=current_shadows
            )
        
        if detection_zones is not None:
            self.detection_mask = self._create_detection_mask(detection_zones)

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, bool, List[Dict]]:
        """
        Detects motion in a given frame with enhanced controls.

        Args:
            frame: The video frame to process (numpy array)

        Returns:
            A tuple containing:
            - The frame with motion contours drawn on it
            - A boolean indicating if motion was detected
            - A list of motion areas with bounding boxes and areas
        """
        # Apply blur based on noise reduction setting
        blurred_frame = cv2.GaussianBlur(frame, self.blur_kernel, 0)
        fg_mask = self.back_sub.apply(blurred_frame)
        
        # Apply detection zones mask if configured
        if self.detection_mask is not None:
            # Resize mask to match frame dimensions
            h, w = fg_mask.shape
            resized_mask = cv2.resize(self.detection_mask, (w, h), interpolation=cv2.INTER_NEAREST)
            fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=resized_mask)
        
        # Clean up the mask with configurable iterations
        fg_mask = cv2.erode(fg_mask, None, iterations=self.morph_iterations)
        fg_mask = cv2.dilate(fg_mask, None, iterations=self.morph_iterations)

        # Find contours of moving objects
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        motion_areas = []
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Ignore small contours based on sensitivity
            if area < self.min_contour_area:
                continue

            motion_detected = True
            
            # Get bounding box
            (x, y, w, h) = cv2.boundingRect(contour)
            
            # Store motion area info
            motion_areas.append({
                'x': int(x),
                'y': int(y),
                'w': int(w),
                'h': int(h),
                'area': int(area)
            })
            
            # Draw bounding box on frame
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            # Optionally draw area text
            cv2.putText(
                frame,
                f"{area}px",
                (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1
            )

        return frame, motion_detected, motion_areas
    
    def get_settings(self) -> Dict:
        """
        Returns current motion detection settings.
        
        Returns:
            Dictionary with current settings
        """
        return {
            'sensitivity': self.sensitivity,
            'min_contour_area': self.min_contour_area,
            'blur_kernel': self.blur_kernel,
            'morph_iterations': self.morph_iterations,
            'has_detection_zones': self.detection_mask is not None
        }