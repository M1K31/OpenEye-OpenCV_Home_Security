# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Image Preprocessing for Enhanced Detection Accuracy

Provides preprocessing techniques for face recognition, license plate recognition,
and barcode/QR code detection to improve accuracy in challenging conditions.

Techniques:
- Histogram equalization (contrast normalization)
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Gamma correction (brightness adjustment)
- Bilateral filtering (noise reduction with edge preservation)
- Adaptive thresholding (binarization)
- Image deskewing (rotation correction)
"""

import cv2
import numpy as np
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """
    Image preprocessing for enhanced detection accuracy
    """

    def __init__(self):
        """Initialize preprocessor with default settings"""
        # Histogram equalization settings
        self.enable_histogram_eq = True

        # CLAHE settings
        self.clahe_clip_limit = 2.0
        self.clahe_tile_size = (8, 8)

        # Gamma correction settings
        self.auto_gamma = True
        self.gamma_value = 1.0

        # Bilateral filter settings
        self.enable_bilateral = True
        self.bilateral_d = 9
        self.bilateral_sigma_color = 75
        self.bilateral_sigma_space = 75

    def preprocess_for_face_recognition(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for face recognition

        Optimized for:
        - Varying lighting conditions
        - Low-light scenarios
        - Slight noise

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            Preprocessed image
        """
        if image is None or image.size == 0:
            logger.warning("Empty image passed to face preprocessing")
            return image

        try:
            # Convert to grayscale if needed for processing
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Step 1: Bilateral filtering to reduce noise while preserving edges
            if self.enable_bilateral:
                gray = cv2.bilateralFilter(
                    gray,
                    self.bilateral_d,
                    self.bilateral_sigma_color,
                    self.bilateral_sigma_space
                )

            # Step 2: CLAHE (Contrast Limited Adaptive Histogram Equalization) for contrast normalization
            # CLAHE is better than standard histogram equalization for varying lighting conditions
            # It's adaptive and less prone to over-enhancement
            # CLAHE was introduced in OpenCV 2.4.0 (2012), so it's available on all supported systems
            # Fallback to standard histogram equalization if CLAHE is unavailable (shouldn't happen)
            if self.enable_histogram_eq:
                try:
                    clahe = cv2.createCLAHE(
                        clipLimit=self.clahe_clip_limit,
                        tileGridSize=self.clahe_tile_size
                    )
                    gray = clahe.apply(gray)
                except (AttributeError, cv2.error) as e:
                    # Fallback to standard histogram equalization for very old OpenCV versions
                    # This should not occur with OpenCV >= 2.4.0 (project requires >= 4.8.1)
                    logger.warning(f"CLAHE not available, falling back to standard histogram equalization: {e}")
                    gray = cv2.equalizeHist(gray)

            # Step 3: Gamma correction for low-light enhancement
            if self.auto_gamma:
                gamma = self._calculate_optimal_gamma(gray)
                gray = self._adjust_gamma(gray, gamma)
            elif self.gamma_value != 1.0:
                gray = self._adjust_gamma(gray, self.gamma_value)

            # Convert back to BGR if input was color
            if len(image.shape) == 3:
                result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                result = gray

            return result

        except Exception as e:
            logger.error(f"Error in face preprocessing: {e}")
            return image

    def preprocess_for_license_plate(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for license plate recognition

        Optimized for:
        - Varying lighting (day/night)
        - Reflections and glare
        - Rotated plates
        - Low contrast

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            Preprocessed image
        """
        if image is None or image.size == 0:
            logger.warning("Empty image passed to license plate preprocessing")
            return image

        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Step 1: Bilateral filter to reduce noise
            gray = cv2.bilateralFilter(gray, 11, 17, 17)

            # Step 2: CLAHE for adaptive contrast enhancement
            clahe = cv2.createCLAHE(
                clipLimit=self.clahe_clip_limit,
                tileGridSize=self.clahe_tile_size
            )
            gray = clahe.apply(gray)

            # Step 3: Adaptive thresholding for better binarization
            # This helps with varying lighting conditions
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2
            )

            # Step 4: Morphological operations to enhance plate characters
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

            return binary

        except Exception as e:
            logger.error(f"Error in license plate preprocessing: {e}")
            return image

    def preprocess_for_barcode(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for barcode/QR code detection

        Optimized for:
        - Low resolution
        - Poor lighting
        - Rotated barcodes
        - Noise and blur

        Args:
            image: Input image (BGR or grayscale)

        Returns:
            Preprocessed image
        """
        if image is None or image.size == 0:
            logger.warning("Empty image passed to barcode preprocessing")
            return image

        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # Step 1: Increase contrast with CLAHE
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)

            # Step 2: Despeckle - remove small noise
            gray = cv2.medianBlur(gray, 3)

            # Step 3: Sharpen the image for better edge detection
            kernel = np.array([[-1, -1, -1],
                             [-1,  9, -1],
                             [-1, -1, -1]])
            gray = cv2.filter2D(gray, -1, kernel)

            # Step 4: Adaptive thresholding
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                2
            )

            # Step 5: Deskew if needed (detect and correct rotation)
            # This is optional but helps with rotated barcodes
            angle = self._detect_skew(binary)
            if abs(angle) > 0.5:  # Only deskew if angle > 0.5 degrees
                binary = self._deskew_image(binary, angle)

            return binary

        except Exception as e:
            logger.error(f"Error in barcode preprocessing: {e}")
            return image

    def _adjust_gamma(self, image: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        """
        Adjust image gamma (brightness)

        gamma < 1: Brighten dark images
        gamma > 1: Darken bright images
        gamma = 1: No change

        Args:
            image: Input grayscale image
            gamma: Gamma value

        Returns:
            Gamma-corrected image
        """
        # Build lookup table for gamma correction
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255
            for i in range(256)
        ]).astype("uint8")

        # Apply gamma correction using the lookup table
        return cv2.LUT(image, table)

    def _calculate_optimal_gamma(self, image: np.ndarray) -> float:
        """
        Calculate optimal gamma value based on image brightness

        Args:
            image: Input grayscale image

        Returns:
            Optimal gamma value
        """
        # Calculate mean brightness
        mean_brightness = np.mean(image)

        # Calculate optimal gamma
        # Dark images (mean < 85): gamma < 1 (brighten)
        # Normal images (85 <= mean <= 170): gamma ≈ 1
        # Bright images (mean > 170): gamma > 1 (darken)

        if mean_brightness < 85:
            # Dark image - brighten
            gamma = 0.5 + (mean_brightness / 170)
        elif mean_brightness > 170:
            # Bright image - darken slightly
            gamma = 1.0 + ((mean_brightness - 170) / 170) * 0.5
        else:
            # Normal brightness
            gamma = 1.0

        # Clamp gamma to reasonable range
        gamma = max(0.4, min(2.0, gamma))

        return gamma

    def _detect_skew(self, image: np.ndarray) -> float:
        """
        Detect image skew angle using Hough Line Transform

        Args:
            image: Binary image

        Returns:
            Skew angle in degrees
        """
        try:
            # Detect edges
            edges = cv2.Canny(image, 50, 150, apertureSize=3)

            # Detect lines using Hough Transform
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

            if lines is None or len(lines) == 0:
                return 0.0

            # Calculate angles of detected lines
            angles = []
            for line in lines:
                rho, theta = line[0]
                angle = np.degrees(theta) - 90
                # Filter out nearly vertical/horizontal lines
                if -45 < angle < 45:
                    angles.append(angle)

            if not angles:
                return 0.0

            # Return median angle
            return np.median(angles)

        except Exception as e:
            logger.debug(f"Error detecting skew: {e}")
            return 0.0

    def _deskew_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate image to correct skew

        Args:
            image: Input image
            angle: Rotation angle in degrees

        Returns:
            Deskewed image
        """
        try:
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)

            # Create rotation matrix
            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            # Rotate image
            rotated = cv2.warpAffine(
                image,
                M,
                (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )

            return rotated

        except Exception as e:
            logger.error(f"Error deskewing image: {e}")
            return image

    def batch_preprocess(
        self,
        images: list,
        mode: str = "face"
    ) -> list:
        """
        Preprocess multiple images

        Args:
            images: List of images
            mode: Preprocessing mode ('face', 'license_plate', or 'barcode')

        Returns:
            List of preprocessed images
        """
        preprocessed = []

        for img in images:
            if mode == "face":
                preprocessed.append(self.preprocess_for_face_recognition(img))
            elif mode == "license_plate":
                preprocessed.append(self.preprocess_for_license_plate(img))
            elif mode == "barcode":
                preprocessed.append(self.preprocess_for_barcode(img))
            else:
                logger.warning(f"Unknown preprocessing mode: {mode}")
                preprocessed.append(img)

        return preprocessed


# Global preprocessor instance
_preprocessor: Optional[ImagePreprocessor] = None


def get_preprocessor() -> ImagePreprocessor:
    """Get or create global preprocessor instance"""
    global _preprocessor

    if _preprocessor is None:
        _preprocessor = ImagePreprocessor()

    return _preprocessor
