import cv2

class MotionDetector:
    """
    A class to detect motion in video frames using background subtraction.
    """
    def __init__(self, min_contour_area=500):
        """
        Initializes the motion detector.
        - min_contour_area: The minimum area for a contour to be considered motion.
        """
        # Use MOG2 background subtractor. It's effective for various lighting conditions.
        self.back_sub = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)
        self.min_contour_area = min_contour_area

    def detect(self, frame):
        """
        Detects motion in a given frame.

        Args:
            frame: The video frame to process.

        Returns:
            A tuple containing:
            - The frame with motion contours drawn on it.
            - A boolean indicating if motion was detected.
        """
        # Apply a blur to reduce noise, then apply the background subtractor
        blurred_frame = cv2.GaussianBlur(frame, (5, 5), 0)
        fg_mask = self.back_sub.apply(blurred_frame)

        # Clean up the mask to remove noise by eroding and dilating
        fg_mask = cv2.erode(fg_mask, None, iterations=2)
        fg_mask = cv2.dilate(fg_mask, None, iterations=2)

        # Find contours of moving objects
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = False
        for contour in contours:
            # Ignore small contours that are likely noise
            if cv2.contourArea(contour) < self.min_contour_area:
                continue

            motion_detected = True
            # Draw a bounding box around the detected motion
            (x, y, w, h) = cv2.boundingRect(contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return frame, motion_detected