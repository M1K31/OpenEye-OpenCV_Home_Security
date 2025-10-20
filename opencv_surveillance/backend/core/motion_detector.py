# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Enhanced Motion Detector with Advanced Lighting Compensation
Supports sensitivity, threshold, noise reduction, shadow detection, and lighting change mitigation
"""
import cv2
import numpy as np
import json
from typing import Optional, Dict, List, Tuple
from collections import deque
import time


class MotionDetector:
    """
    Enhanced motion detector with advanced lighting change mitigation.

    Features in v3.5.6:
    - MOG2 background subtraction with improved parameters
    - Lighting change detection and suppression
    - Temporal filtering to reduce flicker false positives
    - Adaptive learning rate for faster light adaptation
    - Shadow detection and filtering
    - Detection zone masking
    """

    # Sensitivity mapping: higher sensitivity = lower min_contour_area
    SENSITIVITY_MAP = {
        1: 5000,  # Very low - only large movements
        2: 3000,  # Low
        3: 1500,  # Below medium
        4: 800,  # Medium-low
        5: 500,  # Medium (default)
        6: 300,  # Medium-high
        7: 200,  # High
        8: 150,  # Very high
        9: 120,  # Ultra high
        10: 100,  # Maximum sensitivity
    }

    # Noise reduction mapping: (kernel_size, morph_iterations)
    NOISE_REDUCTION_MAP = {
        "low": ((3, 3), 1),
        "medium": ((5, 5), 2),
        "high": ((7, 7), 3),
    }

    def __init__(
        self,
        min_contour_area: int = 500,
        sensitivity: int = 5,
        var_threshold: int = 25,  # Reduced from 50 for better light adaptation
        noise_reduction: str = "medium",
        detect_shadows: bool = True,
        detection_zones: Optional[str] = None,
        lighting_compensation: bool = True,
    ):
        """
        Initializes the enhanced motion detector with lighting compensation.

        Args:
            min_contour_area: Minimum area for a contour to be considered motion (legacy)
            sensitivity: Motion sensitivity 1-10 (overrides min_contour_area if provided)
            var_threshold: Threshold on squared Mahalanobis distance (1-100, lower = more adaptive)
            noise_reduction: Noise reduction level ('low', 'medium', 'high')
            detect_shadows: Whether to detect and mark shadows
            detection_zones: JSON string defining detection zone grid (optional)
            lighting_compensation: Enable lighting change detection and suppression
        """
        # Use sensitivity to determine min_contour_area
        self.sensitivity = max(1, min(10, sensitivity))
        self.min_contour_area = self.SENSITIVITY_MAP.get(
            self.sensitivity, min_contour_area
        )

        # Get noise reduction parameters
        noise_reduction = noise_reduction.lower() if noise_reduction else "medium"
        self.blur_kernel, self.morph_iterations = self.NOISE_REDUCTION_MAP.get(
            noise_reduction, self.NOISE_REDUCTION_MAP["medium"]
        )

        # Lighting compensation settings
        self.lighting_compensation = lighting_compensation
        self.brightness_history = deque(maxlen=30)  # Track last 30 frames
        self.last_brightness = None
        self.brightness_change_threshold = 15  # Threshold for detecting sudden lighting changes

        # Temporal filtering for flicker reduction
        self.motion_history = deque(maxlen=3)  # Track last 3 frames
        self.temporal_filter_enabled = True

        # Create background subtractor with improved parameters for lighting changes
        # Lower varThreshold = faster adaptation to lighting changes
        # Higher history = better background model
        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=500,  # Increased for better background modeling
            varThreshold=var_threshold,  # Lower for better light adaptation
            detectShadows=detect_shadows
        )

        # Set learning rate dynamically
        # Higher learning rate = faster adaptation to changes
        self.base_learning_rate = 0.001  # Slow learning during normal operation
        self.fast_learning_rate = 0.05   # Fast learning during lighting changes
        self.current_learning_rate = self.base_learning_rate

        # Parse detection zones if provided
        self.detection_mask = None
        if detection_zones:
            try:
                self.detection_mask = self._create_detection_mask(
                    detection_zones)
            except Exception as e:
                print(f"Warning: Could not parse detection zones: {e}")
                self.detection_mask = None

    def _create_detection_mask(
            self, detection_zones_json: str) -> Optional[np.ndarray]:
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
            grid_width = zones_data.get("width", 8)
            grid_height = zones_data.get("height", 6)
            zones = zones_data.get("zones", [])

            if not zones or len(zones) != grid_height:
                return None

            # Create binary mask (will be resized to frame size during
            # detection)
            mask = np.zeros((grid_height, grid_width), dtype=np.uint8)

            for y, row in enumerate(zones):
                for x, enabled in enumerate(row):
                    if x < grid_width and enabled:
                        mask[y, x] = 255

            return mask

        except Exception as e:
            print(f"Error creating detection mask: {e}")
            return None

    def _detect_lighting_change(self, frame: np.ndarray) -> bool:
        """
        Detects sudden lighting changes in the scene.

        Args:
            frame: Current video frame

        Returns:
            True if significant lighting change detected, False otherwise
        """
        if not self.lighting_compensation:
            return False

        # Calculate average brightness of the frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        current_brightness = np.mean(gray)

        # Add to history
        self.brightness_history.append(current_brightness)

        # Check for sudden brightness change
        if self.last_brightness is not None:
            brightness_diff = abs(current_brightness - self.last_brightness)

            # Detect significant lighting change
            if brightness_diff > self.brightness_change_threshold:
                self.last_brightness = current_brightness
                return True

        self.last_brightness = current_brightness
        return False

    def _apply_temporal_filter(self, motion_detected: bool) -> bool:
        """
        Apply temporal filtering to reduce false positives from flicker.

        Requires motion to be detected in at least 2 out of last 3 frames.

        Args:
            motion_detected: Current frame motion detection result

        Returns:
            Filtered motion detection result
        """
        if not self.temporal_filter_enabled:
            return motion_detected

        # Add current detection to history
        self.motion_history.append(motion_detected)

        # Need at least 2 detections to fill history
        if len(self.motion_history) < 2:
            return False

        # Require majority vote: at least 2 out of 3 frames show motion
        motion_count = sum(self.motion_history)
        return motion_count >= 2

    def update_settings(
        self,
        sensitivity: Optional[int] = None,
        var_threshold: Optional[int] = None,
        noise_reduction: Optional[str] = None,
        detect_shadows: Optional[bool] = None,
        detection_zones: Optional[str] = None,
        lighting_compensation: Optional[bool] = None,
        brightness_change_threshold: Optional[int] = None,
    ):
        """
        Updates motion detection settings dynamically.

        Args:
            sensitivity: New sensitivity level (1-10)
            var_threshold: New detection threshold
            noise_reduction: New noise reduction level
            detect_shadows: Enable/disable shadow detection
            detection_zones: New detection zones JSON
            lighting_compensation: Enable/disable lighting compensation
            brightness_change_threshold: Threshold for detecting lighting changes (1-50)
        """
        if sensitivity is not None:
            self.sensitivity = max(1, min(10, sensitivity))
            self.min_contour_area = self.SENSITIVITY_MAP.get(
                self.sensitivity, 500)

        if noise_reduction is not None:
            noise_reduction = noise_reduction.lower()
            self.blur_kernel, self.morph_iterations = self.NOISE_REDUCTION_MAP.get(
                noise_reduction, self.NOISE_REDUCTION_MAP["medium"])

        # Note: var_threshold and detect_shadows require recreating the
        # background subtractor
        if var_threshold is not None or detect_shadows is not None:
            current_threshold = var_threshold if var_threshold is not None else 25
            current_shadows = detect_shadows if detect_shadows is not None else True

            self.back_sub = cv2.createBackgroundSubtractorMOG2(
                history=500,
                varThreshold=current_threshold,
                detectShadows=current_shadows,
            )

        if detection_zones is not None:
            self.detection_mask = self._create_detection_mask(detection_zones)

        if lighting_compensation is not None:
            self.lighting_compensation = lighting_compensation

        if brightness_change_threshold is not None:
            self.brightness_change_threshold = max(1, min(50, brightness_change_threshold))

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, bool, List[Dict]]:
        """
        Detects motion in a given frame with lighting change compensation.

        Args:
            frame: The video frame to process (numpy array)

        Returns:
            A tuple containing:
            - The frame with motion contours drawn on it
            - A boolean indicating if motion was detected
            - A list of motion areas with bounding boxes and areas
        """
        # Check for sudden lighting change
        lighting_change_detected = self._detect_lighting_change(frame)

        # Adjust learning rate based on lighting conditions
        if lighting_change_detected:
            # Fast adaptation during lighting changes
            learning_rate = self.fast_learning_rate
        else:
            # Normal learning rate
            learning_rate = self.base_learning_rate

        # Apply blur based on noise reduction setting
        blurred_frame = cv2.GaussianBlur(frame, self.blur_kernel, 0)

        # Apply background subtraction with adaptive learning rate
        fg_mask = self.back_sub.apply(blurred_frame, learningRate=learning_rate)

        # Apply detection zones mask if configured
        if self.detection_mask is not None:
            # Resize mask to match frame dimensions
            h, w = fg_mask.shape
            resized_mask = cv2.resize(
                self.detection_mask, (w, h), interpolation=cv2.INTER_NEAREST
            )
            fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=resized_mask)

        # Remove shadows (they appear as gray in MOG2 with detectShadows=True)
        # Shadow pixels typically have value 127, we want to treat them as background
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Clean up the mask with configurable iterations
        fg_mask = cv2.erode(fg_mask, None, iterations=self.morph_iterations)
        fg_mask = cv2.dilate(fg_mask, None, iterations=self.morph_iterations)

        # Find contours of moving objects
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

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
            motion_areas.append({"x": int(x), "y": int(
                y), "w": int(w), "h": int(h), "area": int(area)})

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
                1,
            )

        # Apply temporal filtering to reduce flicker false positives
        # BUT: Skip temporal filter during lighting changes to allow fast reset
        if not lighting_change_detected:
            motion_detected = self._apply_temporal_filter(motion_detected)
        else:
            # Clear motion history during lighting change
            self.motion_history.clear()
            # Suppress motion detection during lighting change
            motion_detected = False
            motion_areas = []

        return frame, motion_detected, motion_areas

    def get_settings(self) -> Dict:
        """
        Returns current motion detection settings.

        Returns:
            Dictionary with current settings
        """
        return {
            "sensitivity": self.sensitivity,
            "min_contour_area": self.min_contour_area,
            "blur_kernel": self.blur_kernel,
            "morph_iterations": self.morph_iterations,
            "has_detection_zones": self.detection_mask is not None,
            "lighting_compensation": self.lighting_compensation,
            "brightness_change_threshold": self.brightness_change_threshold,
            "temporal_filter_enabled": self.temporal_filter_enabled,
        }
