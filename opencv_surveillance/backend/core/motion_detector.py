# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Enhanced Motion Detector with Advanced Lighting Compensation
Supports sensitivity, threshold, noise reduction, shadow detection, and lighting change mitigation

v3.5.7 Enhancements:
- Grayscale-first processing for improved performance
- HSV-based shadow detection option
- Separate erosion/dilation iteration controls
- Motion persistence/cooldown to prevent rapid flickering
- Enhanced shadow removal with dual methods (binary + HSV)
"""
import cv2
import logging
import numpy as np
import json
import os
from typing import Optional, Dict, List, Tuple
from collections import deque
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class MotionDetector:
    """
    Enhanced motion detector with advanced lighting change mitigation.

    Features in v3.5.7:
    - MOG2 background subtraction with improved parameters
    - Grayscale-first processing for better performance
    - Lighting change detection and suppression
    - Temporal filtering to reduce flicker false positives
    - Adaptive learning rate for faster light adaptation
    - Dual shadow detection (binary threshold + HSV-based)
    - Detection zone masking
    - Motion persistence/cooldown
    - Separate erosion/dilation controls
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

    # Noise reduction mapping: (kernel_size, erode_iterations, dilate_iterations)
    NOISE_REDUCTION_MAP = {
        "low": ((3, 3), 1, 1),
        "medium": ((5, 5), 2, 2),
        "high": ((7, 7), 3, 3),
    }

    # Shadow detection methods
    SHADOW_DETECTION_METHODS = ["binary", "hsv", "dual"]

    def __init__(
        self,
        min_contour_area: int = 500,
        sensitivity: int = 5,
        var_threshold: int = 25,  # Reduced from 50 for better light adaptation
        noise_reduction: str = "medium",
        detect_shadows: bool = True,
        detection_zones: Optional[str] = None,
        lighting_compensation: bool = True,
        shadow_detection_method: str = "dual",
        erosion_iterations: Optional[int] = None,
        dilation_iterations: Optional[int] = None,
        motion_persistence_frames: int = 2,
        use_grayscale: bool = True,
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
            shadow_detection_method: Shadow removal method ('binary', 'hsv', 'dual')
            erosion_iterations: Custom erosion iterations (overrides noise_reduction default)
            dilation_iterations: Custom dilation iterations (overrides noise_reduction default)
            motion_persistence_frames: Frames to maintain motion state (prevents rapid flickering)
            use_grayscale: Convert to grayscale before processing (recommended)
        """
        # Use sensitivity to determine min_contour_area
        self.sensitivity = max(1, min(10, sensitivity))
        self.min_contour_area = self.SENSITIVITY_MAP.get(
            self.sensitivity, min_contour_area
        )

        # Get noise reduction parameters
        noise_reduction = noise_reduction.lower() if noise_reduction else "medium"
        self.blur_kernel, default_erode, default_dilate = self.NOISE_REDUCTION_MAP.get(
            noise_reduction, self.NOISE_REDUCTION_MAP["medium"]
        )

        # Allow custom erosion/dilation iterations
        self.erosion_iterations = erosion_iterations if erosion_iterations is not None else default_erode
        self.dilation_iterations = dilation_iterations if dilation_iterations is not None else default_dilate

        # Shadow detection settings
        self.shadow_detection_method = shadow_detection_method if shadow_detection_method in self.SHADOW_DETECTION_METHODS else "dual"

        # Performance optimization
        self.use_grayscale = use_grayscale

        # Motion persistence settings (prevent rapid on/off flickering)
        self.motion_persistence_frames = max(0, motion_persistence_frames)
        self.motion_cooldown_counter = 0

        # Lighting compensation settings
        self.lighting_compensation = lighting_compensation
        self.brightness_history = deque(maxlen=30)  # Track last 30 frames
        self.last_brightness = None
        self.brightness_change_threshold = 15  # Threshold for detecting sudden lighting changes
        # After a lighting change, keep suppressing motion + using the fast
        # learning rate for this many frames so MOG2 fully re-learns the new
        # lighting before motion resumes. A single-frame suppression left the
        # FOLLOWING frames reading the whole scene as foreground → short false
        # "light shift" recordings. Tunable. See todos_changelog.md (2026-07-25).
        self.lighting_settle_frames = 15
        self._lighting_settle_counter = 0
        # A brightness shift is only treated as a lighting change when the
        # foreground covers at least this fraction of the frame. A real light
        # shift is scene-wide; a moving object (even a large/close one, which
        # also shifts average brightness) is localized and must NOT be
        # suppressed. Tunable. See todos_changelog.md (2026-07-25).
        self.lighting_area_fraction = 0.5

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

        # Polygon-based zones (v3.6.2+)
        self.polygon_zones = []  # List of zone dictionaries with polygon coordinates
        # Rasterised zone polygons, keyed by (zone id, frame width, frame height).
        # Cleared whenever zones are reloaded so stale geometry cannot linger.
        self._zone_mask_cache = {}
        self.camera_id = None  # Camera ID for loading zones from database
        self.db_session = None  # Database session for zone updates

        # Warmup period - suppress motion detection while background model initializes
        # This prevents false positives during startup when the background model is learning
        self.frame_count = 0
        self.warmup_frames = 60  # ~2-4 seconds at 15-30 fps

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

    def load_polygon_zones(self, camera_id: str, db_session=None):
        """
        Load polygon-based motion zones from database for a camera.

        Args:
            camera_id: Camera identifier
            db_session: SQLAlchemy database session (optional)
        """
        self.camera_id = camera_id
        self.db_session = db_session

        if db_session is None:
            # No database session provided, skip loading
            return

        try:
            from backend.database.models import MotionZone

            # Query active zones for this camera.
            #
            # ORDER BY id is not cosmetic: without it the database may return
            # zones in any order, and anything that depends on which zone is seen
            # first becomes non-deterministic between runs. The filtering loop no
            # longer short-circuits on the first match, but a stable order still
            # makes logs, statistics and reproduction consistent.
            zones = db_session.query(MotionZone).filter(
                MotionZone.camera_id == camera_id,
                MotionZone.is_active == True
            ).order_by(MotionZone.id).all()

            # Zone geometry is about to change, so rasterised masks keyed by the
            # old geometry must not survive.
            self._zone_mask_cache = {}

            # Convert to internal format
            self.polygon_zones = []
            for zone in zones:
                try:
                    # Parse coordinates JSON
                    coords = json.loads(zone.coordinates)

                    # Validate coordinates
                    if not coords or len(coords) < 3:
                        continue

                    self.polygon_zones.append({
                        'id': zone.id,
                        'name': zone.name,
                        'coordinates': coords,  # List of {x, y} normalized 0.0-1.0
                        'is_exclusion_zone': zone.is_exclusion_zone,
                        'sensitivity_multiplier': zone.sensitivity_multiplier,
                        'color': zone.color
                    })
                except Exception as e:
                    print(f"Error loading zone {zone.id}: {e}")
                    continue

            print(f"Loaded {len(self.polygon_zones)} polygon zones for camera {camera_id}")

        except Exception as e:
            print(f"Error loading polygon zones: {e}")
            self.polygon_zones = []

    # How much of a contour must fall inside a zone for that zone to claim it.
    #
    # Asymmetric on purpose. An exclusion zone should catch motion that merely
    # clips it — the point of "ignore the road" is that a car half in frame is
    # still the road — so a small fraction is enough. An inclusion zone should
    # require a more convincing share before it reports motion, or a person
    # walking past the edge of the watched area triggers it.
    EXCLUSION_OVERLAP_THRESHOLD = float(
        os.environ.get("OPENEYE_ZONE_EXCLUDE_OVERLAP", "0.15"))
    INCLUSION_OVERLAP_THRESHOLD = float(
        os.environ.get("OPENEYE_ZONE_INCLUDE_OVERLAP", "0.30"))

    def _zone_mask(self, zone: Dict, frame_width: int, frame_height: int):
        """
        Rasterise a zone polygon to a mask, cached per zone id and frame size.

        Rebuilding this for every contour on every frame would be wasteful; zone
        geometry only changes when zones are reloaded, and the cache is dropped
        at that point.
        """
        key = (zone.get('id'), frame_width, frame_height)
        cached = self._zone_mask_cache.get(key)
        if cached is not None:
            return cached

        pts = np.array(
            [[int(p['x'] * frame_width), int(p['y'] * frame_height)]
             for p in zone['coordinates']],
            dtype=np.int32,
        )
        mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
        cv2.fillPoly(mask, [pts], 255)
        self._zone_mask_cache[key] = mask
        return mask

    def _contour_zone_overlap(
        self,
        contour: np.ndarray,
        zone: Dict,
        frame_width: int,
        frame_height: int
    ) -> float:
        """
        Fraction of the contour's area that falls inside the zone (0.0 - 1.0).

        This replaces a centroid test that was documented as checking whether a
        contour "intersects" a zone but actually asked only whether its centre
        point was inside. The two are very different for real motion. A person
        straddling the edge of an exclusion zone whose centroid lands just
        outside was NOT excluded, so an ignored area still raised alerts; a large
        blob overlapping an inclusion zone whose centroid landed outside was NOT
        kept, so watched areas missed motion. A single contour spanning two
        separate moving objects could have a centroid in neither zone.

        Measuring actual overlap makes the behaviour describable: "how much of
        this motion is in the zone", which is what the thresholds above express.
        """
        try:
            zone_mask = self._zone_mask(zone, frame_width, frame_height)

            contour_mask = np.zeros((frame_height, frame_width), dtype=np.uint8)
            cv2.drawContours(contour_mask, [contour], -1, 255, thickness=cv2.FILLED)

            contour_area = int(np.count_nonzero(contour_mask))
            if contour_area == 0:
                return 0.0

            overlap = int(np.count_nonzero(cv2.bitwise_and(contour_mask, zone_mask)))
            return overlap / contour_area

        except Exception as e:
            logger.warning("Zone overlap check failed for zone %s: %s",
                           zone.get('id'), e)
            return 0.0

    def _check_contour_in_zone(
        self,
        contour: np.ndarray,
        zone: Dict,
        frame_width: int,
        frame_height: int
    ) -> bool:
        """
        Whether a contour overlaps a zone enough for that zone to claim it.

        Kept as a boolean helper for callers that do not care about the amount;
        the threshold depends on whether the zone excludes or includes.
        """
        threshold = (self.EXCLUSION_OVERLAP_THRESHOLD
                     if zone.get('is_exclusion_zone')
                     else self.INCLUSION_OVERLAP_THRESHOLD)
        return self._contour_zone_overlap(
            contour, zone, frame_width, frame_height) >= threshold

    def _filter_motion_by_zones(
        self,
        contours: List,
        frame_width: int,
        frame_height: int,
        base_min_contour_area: int
    ) -> Tuple[List, List[int]]:
        """
        Filter motion contours based on polygon zones and apply zone-specific sensitivity.

        Logic:
        - If exclusion zones exist: remove contours in exclusion zones
        - If inclusion zones exist: keep only contours in inclusion zones
        - Apply sensitivity_multiplier per zone to adjust min_contour_area threshold
        - If no zones: keep all contours

        Args:
            contours: List of motion contours
            frame_width: Frame width in pixels
            frame_height: Frame height in pixels
            base_min_contour_area: Base minimum contour area (will be adjusted by zone sensitivity)

        Returns:
            Tuple of (filtered_contours, triggered_zone_ids)
        """
        if not self.polygon_zones:
            # No zones configured, keep all contours that meet base threshold
            return [c for c in contours if cv2.contourArea(c) >= base_min_contour_area], []

        # Separate inclusion and exclusion zones
        inclusion_zones = [z for z in self.polygon_zones if not z['is_exclusion_zone']]
        exclusion_zones = [z for z in self.polygon_zones if z['is_exclusion_zone']]

        filtered_contours = []
        triggered_zone_ids = []

        for contour in contours:
            contour_area = cv2.contourArea(contour)

            # Check exclusion zones first
            in_exclusion_zone = False
            for zone in exclusion_zones:
                if self._check_contour_in_zone(contour, zone, frame_width, frame_height):
                    in_exclusion_zone = True
                    break

            if in_exclusion_zone:
                continue  # Skip this contour

            # Check inclusion zones.
            #
            # EVERY overlapping zone gets a say. The previous version broke out of
            # this loop after the first zone the contour touched, regardless of
            # whether that zone accepted it — so if the first zone rejected the
            # contour on its sensitivity multiplier, no other zone was ever
            # consulted, even one that would have accepted. "First" was whatever
            # order the database happened to return (the query has no ORDER BY),
            # which made the outcome vary between runs for the same scene. That
            # non-determinism is what "zones do not ALWAYS respect the settings"
            # looked like from outside.
            if inclusion_zones:
                accepted = False
                for zone in inclusion_zones:
                    if not self._check_contour_in_zone(
                            contour, zone, frame_width, frame_height):
                        continue

                    # Apply zone's sensitivity multiplier to threshold
                    # Lower multiplier = more sensitive (lower threshold)
                    # Higher multiplier = less sensitive (higher threshold)
                    zone_multiplier = zone.get('sensitivity_multiplier', 1.0)
                    adjusted_threshold = base_min_contour_area * zone_multiplier

                    if contour_area >= adjusted_threshold:
                        accepted = True
                        # Record every zone that claims this motion, not just the
                        # first: a reviewer asking "which zones fired" wants all
                        # of them, and zone statistics should not under-count.
                        triggered_zone_ids.append(zone['id'])

                if accepted:
                    filtered_contours.append(contour)
            else:
                # No inclusion zones, apply base threshold
                if contour_area >= base_min_contour_area:
                    filtered_contours.append(contour)

        # Remove duplicate zone IDs
        triggered_zone_ids = list(set(triggered_zone_ids))

        return filtered_contours, triggered_zone_ids

    def _update_zone_statistics(self, triggered_zone_ids: List[int]):
        """
        Update statistics for triggered zones in the database.

        Args:
            triggered_zone_ids: List of zone IDs that detected motion
        """
        if not self.db_session or not triggered_zone_ids:
            return

        try:
            from backend.database.models import MotionZone

            # Update each triggered zone
            for zone_id in triggered_zone_ids:
                zone = self.db_session.query(MotionZone).filter(
                    MotionZone.id == zone_id
                ).first()

                if zone:
                    zone.motion_events_count += 1
                    zone.last_motion_at = datetime.utcnow()

            # Commit changes
            self.db_session.commit()

        except Exception as e:
            print(f"Error updating zone statistics: {e}")
            if self.db_session:
                self.db_session.rollback()

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

        # Reference the rolling average BEFORE adding the current sample, so a
        # GRADUAL drift (clouds, dimmer, auto-exposure) is caught too — testing
        # only the per-frame delta missed slow shifts that still confuse the
        # background model and produced false "motion".
        avg_ref = (
            sum(self.brightness_history) / len(self.brightness_history)
            if self.brightness_history
            else current_brightness
        )
        self.brightness_history.append(current_brightness)

        changed = False
        if self.last_brightness is not None:
            sudden = abs(current_brightness - self.last_brightness) > self.brightness_change_threshold
            gradual = abs(current_brightness - avg_ref) > self.brightness_change_threshold
            changed = sudden or gradual

        self.last_brightness = current_brightness
        return changed

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

    def _remove_shadows_hsv(self, frame: np.ndarray, fg_mask: np.ndarray) -> np.ndarray:
        """
        Remove shadows using HSV color space analysis.

        Shadows typically have:
        - Similar hue to the background
        - Lower saturation
        - Lower value (brightness)

        This method is more sophisticated than simple binary thresholding.

        Args:
            frame: Original frame in BGR format
            fg_mask: Foreground mask from background subtraction

        Returns:
            Shadow-filtered foreground mask
        """
        # Convert frame to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Create a mask for potential shadow regions
        # Shadows have low saturation (grayscale-ish) and medium-low value
        # Adjust these thresholds based on your environment
        lower_shadow = np.array([0, 0, 50])    # H, S, V lower bounds
        upper_shadow = np.array([180, 50, 200])  # H, S, V upper bounds

        shadow_mask = cv2.inRange(hsv, lower_shadow, upper_shadow)

        # Remove detected shadows from foreground mask
        # Only remove if both conditions are met:
        # 1. Pixel is marked as foreground (fg_mask)
        # 2. Pixel matches shadow characteristics (shadow_mask)
        shadow_regions = cv2.bitwise_and(fg_mask, shadow_mask)

        # Remove shadows from the foreground mask
        result = cv2.subtract(fg_mask, shadow_regions)

        return result

    def _remove_shadows_dual(self, frame: np.ndarray, fg_mask: np.ndarray) -> np.ndarray:
        """
        Remove shadows using both binary thresholding and HSV analysis.

        This combines the speed of binary thresholding with the accuracy of HSV analysis.

        Args:
            frame: Original frame in BGR format
            fg_mask: Foreground mask from background subtraction

        Returns:
            Shadow-filtered foreground mask
        """
        # First pass: Binary threshold to remove MOG2's gray shadow markers
        _, binary_filtered = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Second pass: HSV-based shadow removal for remaining shadows
        hsv_filtered = self._remove_shadows_hsv(frame, binary_filtered)

        return hsv_filtered

    def update_settings(
        self,
        sensitivity: Optional[int] = None,
        var_threshold: Optional[int] = None,
        noise_reduction: Optional[str] = None,
        detect_shadows: Optional[bool] = None,
        detection_zones: Optional[str] = None,
        lighting_compensation: Optional[bool] = None,
        brightness_change_threshold: Optional[int] = None,
        shadow_detection_method: Optional[str] = None,
        erosion_iterations: Optional[int] = None,
        dilation_iterations: Optional[int] = None,
        motion_persistence_frames: Optional[int] = None,
        use_grayscale: Optional[bool] = None,
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
            shadow_detection_method: Shadow removal method ('binary', 'hsv', 'dual')
            erosion_iterations: Custom erosion iterations
            dilation_iterations: Custom dilation iterations
            motion_persistence_frames: Frames to maintain motion state
            use_grayscale: Convert to grayscale before processing
        """
        if sensitivity is not None:
            self.sensitivity = max(1, min(10, sensitivity))
            self.min_contour_area = self.SENSITIVITY_MAP.get(
                self.sensitivity, 500)

        if noise_reduction is not None:
            noise_reduction = noise_reduction.lower()
            self.blur_kernel, default_erode, default_dilate = self.NOISE_REDUCTION_MAP.get(
                noise_reduction, self.NOISE_REDUCTION_MAP["medium"])
            # Only update iterations if not explicitly set
            if erosion_iterations is None:
                self.erosion_iterations = default_erode
            if dilation_iterations is None:
                self.dilation_iterations = default_dilate

        if erosion_iterations is not None:
            self.erosion_iterations = max(0, erosion_iterations)

        if dilation_iterations is not None:
            self.dilation_iterations = max(0, dilation_iterations)

        if shadow_detection_method is not None:
            if shadow_detection_method in self.SHADOW_DETECTION_METHODS:
                self.shadow_detection_method = shadow_detection_method

        if motion_persistence_frames is not None:
            self.motion_persistence_frames = max(0, motion_persistence_frames)

        if use_grayscale is not None:
            self.use_grayscale = use_grayscale

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

    def detect(self, frame: np.ndarray, draw_boxes: bool = True) -> Tuple[np.ndarray, bool, List[Dict], List[int]]:
        """
        Detects motion in a given frame with lighting change compensation.

        v3.5.7 Enhancements:
        - Grayscale-first processing for better performance
        - Dual shadow removal (binary + HSV)
        - Separate erosion/dilation controls
        - Motion persistence/cooldown

        v3.11.7 Enhancements:
        - Zone-specific sensitivity multiplier applied
        - Returns triggered zone IDs for motion event tracking

        Args:
            frame: The video frame to process (numpy array)
            draw_boxes: Whether to draw green bounding boxes on detected motion (default: True)

        Returns:
            A tuple containing:
            - The frame with motion contours drawn on it (if draw_boxes=True)
            - A boolean indicating if motion was detected
            - A list of motion areas with bounding boxes and areas
            - A list of triggered zone IDs (empty if no zones configured)
        """
        # Increment frame counter
        self.frame_count += 1

        # Store original frame for drawing (we'll process a grayscale version)
        original_frame = frame.copy()

        # WARMUP PERIOD: Suppress motion detection while background model initializes
        # The MOG2 algorithm needs time to learn the "normal" background
        if self.frame_count <= self.warmup_frames:
            # Still apply background subtraction to train the model, but don't report motion
            if self.use_grayscale:
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                blurred_frame = cv2.GaussianBlur(gray_frame, self.blur_kernel, 0)
            else:
                blurred_frame = cv2.GaussianBlur(frame, self.blur_kernel, 0)
            # Apply with higher learning rate during warmup for faster initialization
            self.back_sub.apply(blurred_frame, learningRate=0.1)
            return original_frame, False, [], []

        # STEP 1: PRE-PROCESSING - Convert to grayscale first for better performance
        if self.use_grayscale:
            # Convert to grayscale before any processing
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Apply blur to grayscale
            blurred_frame = cv2.GaussianBlur(gray_frame, self.blur_kernel, 0)
        else:
            # Original color-based processing
            blurred_frame = cv2.GaussianBlur(frame, self.blur_kernel, 0)

        # Candidate lighting change from brightness (sudden or gradual). This is
        # only a HINT — it is confirmed below using the foreground area fraction,
        # so a large moving object (which also shifts average brightness) is not
        # mistaken for a scene-wide lighting change and suppressed.
        brightness_shift = self._detect_lighting_change(original_frame)

        # "Settling" = still within a window opened by a CONFIRMED lighting change
        # on a previous frame. Motion stays suppressed and MOG2 keeps the fast
        # learning rate for the WHOLE window so it fully re-adapts.
        settling = self._lighting_settle_counter > 0

        # STEP 2: BACKGROUND SUBTRACTION - Adjust learning rate based on lighting conditions
        if settling:
            # Fast adaptation during (and just after) lighting changes
            learning_rate = self.fast_learning_rate
            self._lighting_settle_counter -= 1
        else:
            # Normal learning rate
            learning_rate = self.base_learning_rate

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

        # STEP 3: SHADOW REMOVAL - Use configured method
        if self.shadow_detection_method == "binary":
            # Original binary threshold method (fastest)
            _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        elif self.shadow_detection_method == "hsv":
            # HSV-based shadow removal (more accurate)
            fg_mask = self._remove_shadows_hsv(original_frame, fg_mask)
        elif self.shadow_detection_method == "dual":
            # Dual method (best of both worlds)
            fg_mask = self._remove_shadows_dual(original_frame, fg_mask)

        # STEP 4: MORPHOLOGICAL OPERATIONS - Clean up the mask with separate erosion/dilation
        if self.erosion_iterations > 0:
            fg_mask = cv2.erode(fg_mask, None, iterations=self.erosion_iterations)
        if self.dilation_iterations > 0:
            fg_mask = cv2.dilate(fg_mask, None, iterations=self.dilation_iterations)

        # STEP 4.5: CONFIRM LIGHTING CHANGE (scene-wide test). A genuine light
        # shift lights up most of the frame as foreground; a moving object stays
        # localized. Only then open the settle window + suppress — this is what
        # keeps large real motion from being wrongly suppressed.
        if brightness_shift and fg_mask.size:
            fg_fraction = float(np.count_nonzero(fg_mask)) / fg_mask.size
            if fg_fraction > self.lighting_area_fraction:
                self._lighting_settle_counter = self.lighting_settle_frames
                settling = True

        # STEP 5: CONTOUR DETECTION - Find contours of moving objects
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # STEP 5.5: ZONE-BASED FILTERING (v3.6.2+)
        # Filter contours based on polygon zones if configured
        # Zone filtering now also applies sensitivity_multiplier and area threshold
        frame_height, frame_width = original_frame.shape[:2]
        triggered_zone_ids = []

        # Filter by zones (applies zone-specific sensitivity) or by base threshold
        contours, triggered_zone_ids = self._filter_motion_by_zones(
            contours, frame_width, frame_height, self.min_contour_area
        )

        motion_detected = False
        motion_areas = []

        for contour in contours:
            area = cv2.contourArea(contour)

            # Contours have already been filtered by area threshold in _filter_motion_by_zones
            motion_detected = True

            # Get bounding box
            (x, y, w, h) = cv2.boundingRect(contour)

            # Store motion area info
            motion_areas.append({"x": int(x), "y": int(
                y), "w": int(w), "h": int(h), "area": int(area)})

            # Only draw bounding boxes if draw_boxes is True
            if draw_boxes:
                # Draw bounding box on original frame
                cv2.rectangle(original_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # Optionally draw area text
                cv2.putText(
                    original_frame,
                    f"{area}px",
                    (x, y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )

        # STEP 6: TEMPORAL FILTERING - Apply temporal filter to reduce flicker
        # BUT: while settling from a lighting change, suppress motion for the
        # whole window (not just the single change frame) so the scene-wide
        # brightness shift is not reported as motion.
        if not settling:
            motion_detected = self._apply_temporal_filter(motion_detected)
        else:
            # Clear motion history and suppress motion for the settle window
            self.motion_history.clear()
            motion_detected = False
            motion_areas = []
            triggered_zone_ids = []

        # STEP 7: MOTION PERSISTENCE - Implement cooldown to prevent rapid on/off flickering
        if motion_detected:
            # Reset cooldown when motion is detected
            self.motion_cooldown_counter = self.motion_persistence_frames
        elif self.motion_cooldown_counter > 0:
            # Maintain motion state during cooldown period
            self.motion_cooldown_counter -= 1
            motion_detected = True  # Keep motion active during cooldown

        # STEP 8: ZONE STATISTICS UPDATE (v3.6.2+)
        # Update database statistics for zones that detected motion
        if motion_detected and triggered_zone_ids:
            self._update_zone_statistics(triggered_zone_ids)

        return original_frame, motion_detected, motion_areas, triggered_zone_ids

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
            "erosion_iterations": self.erosion_iterations,
            "dilation_iterations": self.dilation_iterations,
            "has_detection_zones": self.detection_mask is not None,
            "lighting_compensation": self.lighting_compensation,
            "brightness_change_threshold": self.brightness_change_threshold,
            "temporal_filter_enabled": self.temporal_filter_enabled,
            "shadow_detection_method": self.shadow_detection_method,
            "motion_persistence_frames": self.motion_persistence_frames,
            "use_grayscale": self.use_grayscale,
        }
