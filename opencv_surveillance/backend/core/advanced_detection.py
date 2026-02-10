# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Advanced Detection Module

Provides license plate recognition, barcode/QR code detection,
and badge/name tag detection with preprocessing for enhanced accuracy.

Note: This module requires additional dependencies:
- pytesseract (for OCR/license plates)
- pyzbar (for barcodes/QR codes)
- easyocr (alternative OCR, optional)

Install with: pip install pytesseract pyzbar easyocr
"""

import cv2
import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from backend.core.image_preprocessing import get_preprocessor

logger = logging.getLogger(__name__)


class LicensePlateDetector:
    """
    License plate detection and recognition with preprocessing.

    v3.11.7 Enhancements:
    - EasyOCR support with GPU acceleration
    - Hardware-aware mode selection (GPU/CPU)
    - Cooldown to prevent duplicate detections
    - Configurable confidence thresholds
    - Integration with hardware detector
    """

    def __init__(
        self,
        enable_preprocessing: bool = True,
        use_gpu: bool = None,  # None = auto-detect
        cooldown_seconds: float = 3.0,
        min_confidence: float = 0.6
    ):
        """
        Initialize license plate detector

        Args:
            enable_preprocessing: Enable image preprocessing for better accuracy
            use_gpu: Force GPU (True) or CPU (False). None = auto-detect
            cooldown_seconds: Minimum time between processing same camera
            min_confidence: Minimum OCR confidence to accept (0.0-1.0)
        """
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = get_preprocessor() if enable_preprocessing else None
        self.ocr_available = False
        self.ocr_engine = None
        self.ocr_engine_name = None
        self.cooldown_seconds = cooldown_seconds
        self.min_confidence = min_confidence
        self.last_detection_time = {}  # camera_id -> timestamp
        self.enabled = False  # Disabled by default until explicitly enabled

        # Auto-detect GPU availability if not specified
        if use_gpu is None:
            use_gpu = self._detect_gpu_available()

        self.use_gpu = use_gpu

        # Try EasyOCR first (better accuracy, GPU support)
        try:
            import easyocr
            self.ocr_engine = easyocr.Reader(
                ['en'],
                gpu=self.use_gpu,
                verbose=False
            )
            self.ocr_available = True
            self.ocr_engine_name = "easyocr"
            mode = "GPU" if self.use_gpu else "CPU"
            logger.info(f"License plate detector initialized with EasyOCR ({mode} mode)")
        except ImportError:
            # Fallback to pytesseract (CPU only)
            try:
                import pytesseract
                self.ocr_engine = pytesseract
                self.ocr_available = True
                self.ocr_engine_name = "tesseract"
                logger.info("License plate detector initialized with Tesseract OCR (CPU fallback)")
            except ImportError:
                logger.warning(
                    "No OCR library available for license plate recognition. "
                    "Install easyocr (recommended) or pytesseract"
                )

    def _detect_gpu_available(self) -> bool:
        """Check if GPU is available for OCR acceleration"""
        try:
            import torch
            if torch.cuda.is_available():
                logger.info(f"GPU detected for ALPR: {torch.cuda.get_device_name(0)}")
                return True
        except ImportError:
            pass
        return False

    def set_enabled(self, enabled: bool):
        """Enable or disable the license plate detector"""
        self.enabled = enabled
        logger.info(f"License plate detector {'enabled' if enabled else 'disabled'}")

    def should_process_frame(self, camera_id: str) -> bool:
        """Check if enough time has passed since last detection for this camera"""
        if not self.enabled or not self.ocr_available:
            return False

        import time
        current_time = time.time()
        last_time = self.last_detection_time.get(camera_id, 0)

        if current_time - last_time >= self.cooldown_seconds:
            return True
        return False

    def _update_cooldown(self, camera_id: str):
        """Update the last detection time for a camera"""
        import time
        self.last_detection_time[camera_id] = time.time()

    def detect_license_plates(
        self,
        frame: np.ndarray,
        camera_id: str = "unknown"
    ) -> List[Dict]:
        """
        Detect and read license plates in frame

        Args:
            frame: Input frame (BGR)
            camera_id: Camera identifier for cooldown tracking

        Returns:
            List of detected plates with text, location, and confidence
        """
        if not self.ocr_available:
            logger.debug("OCR not available for license plate detection")
            return []

        if not self.should_process_frame(camera_id):
            return []

        import time
        start_time = time.time()

        try:
            # Apply preprocessing if available
            processed = frame
            if self.enable_preprocessing and self.preprocessor:
                try:
                    processed = self.preprocessor.preprocess_for_license_plate(frame)
                except Exception:
                    # Fall back to original frame if preprocessing fails
                    processed = frame

            plates = []

            # Method 1: Direct OCR on full frame with EasyOCR (better for GPU)
            if self.ocr_engine_name == "easyocr":
                results = self.ocr_engine.readtext(
                    frame,
                    allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                    paragraph=False
                )

                for (bbox, text, confidence) in results:
                    # Clean up the detected text
                    text = text.strip().upper().replace(' ', '').replace('-', '')

                    # Filter: license plates are typically 5-8 characters
                    if len(text) >= 5 and len(text) <= 8 and confidence >= self.min_confidence:
                        # Extract bounding box
                        x_coords = [int(p[0]) for p in bbox]
                        y_coords = [int(p[1]) for p in bbox]
                        x, y = min(x_coords), min(y_coords)
                        w, h = max(x_coords) - x, max(y_coords) - y

                        # Check aspect ratio (plates are wider than tall)
                        aspect_ratio = w / h if h > 0 else 0
                        if aspect_ratio > 1.5:  # Typical plate aspect ratio
                            plates.append({
                                'text': text,
                                'location': (x, y, w, h),
                                'confidence': float(confidence),
                                'ocr_engine': 'easyocr'
                            })

            # Method 2: Contour-based detection + Tesseract (CPU fallback)
            else:
                # Detect plate regions using contours
                plate_regions = self._detect_plate_regions(processed)

                for region in plate_regions:
                    x, y, w, h = region
                    # Extract plate ROI from original frame for better OCR
                    plate_roi = frame[y:y+h, x:x+w]

                    # OCR to read text
                    text, confidence = self._read_plate_text(plate_roi)

                    if text and confidence >= self.min_confidence:
                        plates.append({
                            'text': text,
                            'location': (x, y, w, h),
                            'confidence': confidence,
                            'ocr_engine': 'tesseract'
                        })

            # Update cooldown
            if plates:
                self._update_cooldown(camera_id)

            # Add processing time to results
            processing_time = (time.time() - start_time) * 1000
            for plate in plates:
                plate['processing_time_ms'] = processing_time

            return plates

        except Exception as e:
            logger.error(f"Error detecting license plates: {e}")
            return []

    def _detect_plate_regions(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect potential license plate regions using contours

        Args:
            frame: Preprocessed frame

        Returns:
            List of (x, y, w, h) regions
        """
        try:
            # Find contours
            contours, _ = cv2.findContours(
                frame,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by aspect ratio (license plates are typically wide rectangles)
                aspect_ratio = w / float(h) if h > 0 else 0
                if 2.0 < aspect_ratio < 6.0 and w > 80 and h > 20:
                    regions.append((x, y, w, h))

            return regions

        except Exception as e:
            logger.error(f"Error detecting plate regions: {e}")
            return []

    def _read_plate_text(self, plate_roi: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Read text from license plate ROI using OCR

        Args:
            plate_roi: Preprocessed plate region

        Returns:
            Tuple of (detected_text, confidence) or (None, 0.0)
        """
        if not self.ocr_available:
            return None, 0.0

        try:
            # OCR configuration for license plates
            # Tesseract config: treat as single line, alphanumeric only
            config = '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

            text = self.ocr_engine.image_to_string(plate_roi, config=config)
            text = text.strip().upper().replace(' ', '').replace('\n', '').replace('-', '')

            # Filter out noise (minimum 5 characters for valid plate)
            if len(text) >= 5 and len(text) <= 8:
                # Tesseract doesn't provide confidence per-string easily,
                # so estimate based on text quality
                confidence = 0.7 if text.isalnum() else 0.5
                return text, confidence

            return None, 0.0

        except Exception as e:
            logger.error(f"Error reading plate text: {e}")
            return None, 0.0


class BarcodeDetector:
    """
    Barcode and QR code detection with preprocessing
    """

    def __init__(self, enable_preprocessing: bool = True):
        """
        Initialize barcode detector

        Args:
            enable_preprocessing: Enable image preprocessing for better accuracy
        """
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = get_preprocessor() if enable_preprocessing else None
        self.decoder_available = False
        self.decoder = None

        # Try to import barcode library
        try:
            from pyzbar import pyzbar
            self.decoder = pyzbar
            self.decoder_available = True
            logger.info("Barcode detector initialized with pyzbar")
        except ImportError:
            logger.warning(
                "pyzbar not installed. Barcode detection unavailable. "
                "Install with: pip install pyzbar"
            )

    def detect_barcodes(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect and decode barcodes/QR codes in frame

        Args:
            frame: Input frame (BGR)

        Returns:
            List of detected barcodes with data and location
        """
        if not self.decoder_available:
            logger.debug("Barcode decoder not available")
            return []

        try:
            # Apply preprocessing
            processed = frame
            if self.enable_preprocessing and self.preprocessor:
                processed = self.preprocessor.preprocess_for_barcode(frame)

            # Detect and decode barcodes
            barcodes = self.decoder.decode(processed)

            results = []
            for barcode in barcodes:
                # Extract barcode data
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type

                # Get barcode location
                x, y, w, h = barcode.rect.left, barcode.rect.top, barcode.rect.width, barcode.rect.height

                results.append({
                    'data': barcode_data,
                    'type': barcode_type,
                    'location': (x, y, w, h),
                    'polygon': barcode.polygon  # Exact corners
                })

            return results

        except Exception as e:
            logger.error(f"Error detecting barcodes: {e}")
            return []


class BadgeDetector:
    """
    Name tag / badge text detection with preprocessing
    """

    def __init__(self, enable_preprocessing: bool = True):
        """
        Initialize badge detector

        Args:
            enable_preprocessing: Enable image preprocessing for better accuracy
        """
        self.enable_preprocessing = enable_preprocessing
        self.preprocessor = get_preprocessor() if enable_preprocessing else None
        self.ocr_available = False
        self.ocr_engine = None

        # Try to import OCR library
        try:
            import easyocr
            # Initialize with English language
            self.ocr_engine = easyocr.Reader(['en'], gpu=False)
            self.ocr_available = True
            logger.info("Badge detector initialized with EasyOCR")
        except ImportError:
            # Fallback to pytesseract
            try:
                import pytesseract
                self.ocr_engine = pytesseract
                self.ocr_available = True
                logger.info("Badge detector initialized with Tesseract OCR (fallback)")
            except ImportError:
                logger.warning(
                    "No OCR library available for badge detection. "
                    "Install easyocr or pytesseract"
                )

    def detect_name_tags(self, frame: np.ndarray, face_locations: List = None) -> List[Dict]:
        """
        Detect name tags/badges near detected faces

        Args:
            frame: Input frame (BGR)
            face_locations: List of face locations to search near

        Returns:
            List of detected badges with text and location
        """
        if not self.ocr_available:
            logger.debug("OCR not available for badge detection")
            return []

        try:
            # Apply preprocessing (use face preprocessing as it's similar)
            processed = frame
            if self.enable_preprocessing and self.preprocessor:
                processed = self.preprocessor.preprocess_for_face_recognition(frame)

            # If face locations provided, focus OCR on regions below faces
            # (badges are typically worn on chest area)
            if face_locations:
                badges = []
                for face_loc in face_locations:
                    badge_roi, offset = self._get_badge_roi(frame, face_loc)
                    badge_text = self._read_badge_text(badge_roi)

                    if badge_text:
                        x_offset, y_offset = offset
                        badges.append({
                            'text': badge_text,
                            'location': (x_offset, y_offset, badge_roi.shape[1], badge_roi.shape[0]),
                            'associated_face': face_loc
                        })

                return badges
            else:
                # Full frame OCR (slower)
                badge_text = self._read_badge_text(processed)
                if badge_text:
                    return [{
                        'text': badge_text,
                        'location': (0, 0, frame.shape[1], frame.shape[0]),
                        'associated_face': None
                    }]

            return []

        except Exception as e:
            logger.error(f"Error detecting badges: {e}")
            return []

    def _get_badge_roi(self, frame: np.ndarray, face_location: Tuple) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Get region of interest for badge based on face location

        Args:
            frame: Input frame
            face_location: (top, right, bottom, left) of face

        Returns:
            (badge_roi, (x_offset, y_offset))
        """
        top, right, bottom, left = face_location
        h, w = frame.shape[:2]

        # Badge is typically 1-2x face height below face
        badge_top = min(bottom, h - 1)
        badge_bottom = min(bottom + (bottom - top) * 2, h)
        badge_left = max(left - 20, 0)
        badge_right = min(right + 20, w)

        roi = frame[int(badge_top):int(badge_bottom), int(badge_left):int(badge_right)]
        return roi, (int(badge_left), int(badge_top))

    def _read_badge_text(self, badge_roi: np.ndarray) -> Optional[str]:
        """
        Read text from badge ROI using OCR

        Args:
            badge_roi: Badge region

        Returns:
            Detected text or None
        """
        if not self.ocr_available:
            return None

        try:
            # Use EasyOCR if available
            if hasattr(self.ocr_engine, 'readtext'):
                results = self.ocr_engine.readtext(badge_roi)
                if results:
                    # Combine all detected text
                    text = ' '.join([result[1] for result in results if result[2] > 0.5])
                    return text.strip()
            else:
                # Use Tesseract
                import pytesseract
                text = pytesseract.image_to_string(badge_roi)
                return text.strip()

            return None

        except Exception as e:
            logger.error(f"Error reading badge text: {e}")
            return None


# Global detector instances (lazy initialization)
_license_plate_detector: Optional[LicensePlateDetector] = None
_barcode_detector: Optional[BarcodeDetector] = None
_badge_detector: Optional[BadgeDetector] = None


def get_license_plate_detector() -> LicensePlateDetector:
    """Get or create global license plate detector instance"""
    global _license_plate_detector
    if _license_plate_detector is None:
        _license_plate_detector = LicensePlateDetector()
    return _license_plate_detector


def get_barcode_detector() -> BarcodeDetector:
    """Get or create global barcode detector instance"""
    global _barcode_detector
    if _barcode_detector is None:
        _barcode_detector = BarcodeDetector()
    return _barcode_detector


def get_badge_detector() -> BadgeDetector:
    """Get or create global badge detector instance"""
    global _badge_detector
    if _badge_detector is None:
        _badge_detector = BadgeDetector()
    return _badge_detector
