# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Manager - Enhanced with Granular Controls (v3.5.0)
Integrates motion detection, image processing, and video quality processors
"""

import cv2
import numpy as np
import time
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from .motion_detector import MotionDetector
from .image_processor import ImageProcessor
from .video_processor import VideoProcessor, VideoSettings
from .recorder import Recorder
from .face_detection import FaceDetector
import asyncio
from backend.core.alert_manager import get_alert_manager
from backend.core.automation_engine import process_face_detection
from backend.database.session import SessionLocal
from backend.database.models import Camera as CameraModel
from backend.database.utils import get_db_context


class Camera(ABC):
    """
    Enhanced Camera base class with granular controls.

    New in v3.5.0:
    - Image quality processor integration
    - Video quality processor integration
    - Database settings loading
    - Dynamic settings reload
    """

    def __init__(
        self,
        source: str,
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        self.source = source
        self.camera_id = camera_id
        self.capture = None
        self.is_running = False
        self.motion_detected = False
        self.last_motion_time = 0
        self.post_motion_cooldown = 5  # Default, can be overridden from DB
        self.last_faces_detected = []
        self.current_motion_event_id = None  # Track current motion event for face linking

        # Load settings from database or use defaults
        settings = db_settings or {}

        # Initialize Motion Detector with granular controls (v3.5.7 enhanced - recommended defaults)
        self.motion_detector = MotionDetector(
            min_contour_area=settings.get("min_contour_area", 500),
            sensitivity=settings.get("motion_sensitivity", 5),
            var_threshold=settings.get("motion_threshold", 50),
            noise_reduction=settings.get("noise_reduction", "medium"),
            detect_shadows=settings.get("detect_shadows", True),
            detection_zones=settings.get("detection_zones"),
            lighting_compensation=settings.get("lighting_compensation_enabled", True),
            shadow_detection_method=settings.get("shadow_detection_method", "dual"),
            erosion_iterations=settings.get("erosion_iterations", 2),  # Recommended: 2
            dilation_iterations=settings.get("dilation_iterations", 3),  # Recommended: 3
            motion_persistence_frames=settings.get("motion_persistence_frames", 2),
            use_grayscale=settings.get("use_grayscale", True),
        )

        # Initialize Image Processor with quality controls
        self.image_processor = ImageProcessor(
            brightness=settings.get(
                "brightness", 0), contrast=settings.get(
                "contrast", 1.0), saturation=settings.get(
                "saturation", 1.0), sharpness=settings.get(
                    "sharpness", "none"), noise_reduction_strength=settings.get(
                        "noise_reduction_strength", 0), )

        # Initialize Video Processor with quality settings
        video_settings = VideoSettings(
            resolution=settings.get("resolution", "1920x1080"),
            fps_target=settings.get("fps_target", 15),
            bitrate_kbps=settings.get("bitrate_kbps", 2000),
            codec=settings.get("codec", "h264"),
        )
        self.video_processor = VideoProcessor(video_settings)

        # Initialize Recorder and Face Detector with system settings
        # Get system settings for paths and durations
        recordings_path = settings.get("recordings_path", "recordings")
        max_recording_duration = settings.get("max_recording_duration", 300)
        faces_path = settings.get("faces_path", "faces")
        snapshots_path = settings.get("snapshots_path", "data/snapshots")

        self.recorder = Recorder(
            output_dir=recordings_path,
            max_recording_duration=max_recording_duration)
        self.face_detector = FaceDetector(
            enabled=enable_face_detection, faces_dir=faces_path
        )
        
        # Store snapshots path for motion detection
        self.snapshots_path = snapshots_path

        # Store motion percentage threshold (minimum % of frame with motion to trigger event)
        self.motion_percentage_threshold = settings.get("motion_percentage_threshold", 1.0)

        # Store settings for later updates
        self._db_settings = settings

        # Override post_motion_cooldown if provided in settings
        if "post_motion_cooldown" in settings:
            self.post_motion_cooldown = settings["post_motion_cooldown"]

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_frame(self):
        pass

    # Face detection methods
    def enable_face_detection(self, enabled: bool):
        """Enable or disable face detection for this camera"""
        self.face_detector.set_enabled(enabled)

    def get_face_statistics(self):
        """Get face detection statistics"""
        return self.face_detector.get_statistics()

    # NEW: Settings management methods
    def update_motion_settings(
        self,
        sensitivity: Optional[int] = None,
        var_threshold: Optional[int] = None,
        noise_reduction: Optional[str] = None,
        detect_shadows: Optional[bool] = None,
        detection_zones: Optional[str] = None,
        shadow_detection_method: Optional[str] = None,
        erosion_iterations: Optional[int] = None,
        dilation_iterations: Optional[int] = None,
        motion_persistence_frames: Optional[int] = None,
        use_grayscale: Optional[bool] = None,
        lighting_compensation: Optional[bool] = None,
        brightness_change_threshold: Optional[int] = None,
    ):
        """Update motion detection settings dynamically (v3.5.7 enhanced)"""
        self.motion_detector.update_settings(
            sensitivity=sensitivity,
            var_threshold=var_threshold,
            noise_reduction=noise_reduction,
            detect_shadows=detect_shadows,
            detection_zones=detection_zones,
            shadow_detection_method=shadow_detection_method,
            erosion_iterations=erosion_iterations,
            dilation_iterations=dilation_iterations,
            motion_persistence_frames=motion_persistence_frames,
            use_grayscale=use_grayscale,
            lighting_compensation=lighting_compensation,
            brightness_change_threshold=brightness_change_threshold,
        )

    def update_image_settings(
        self,
        brightness: Optional[int] = None,
        contrast: Optional[float] = None,
        saturation: Optional[float] = None,
        sharpness: Optional[str] = None,
        noise_reduction_strength: Optional[int] = None,
    ):
        """Update image quality settings dynamically"""
        self.image_processor.update_settings(
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            sharpness=sharpness,
            noise_reduction_strength=noise_reduction_strength,
        )

    def update_video_settings(
        self,
        resolution: Optional[str] = None,
        fps_target: Optional[int] = None,
        bitrate_kbps: Optional[int] = None,
        codec: Optional[str] = None,
    ):
        """Update video quality settings dynamically"""
        self.video_processor.update_settings(
            resolution=resolution,
            fps_target=fps_target,
            bitrate_kbps=bitrate_kbps,
            codec=codec,
        )

    def get_all_settings(self) -> Dict[str, Any]:
        """Get all current camera settings"""
        return {
            "motion": self.motion_detector.get_settings(),
            "image": self.image_processor.get_settings(),
            "video": self.video_processor.get_settings(),
            "post_motion_cooldown": self.post_motion_cooldown,
        }

    def reload_settings_from_db(self):
        """Reload settings from database"""
        if not self.camera_id:
            return

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                db_camera = (
                    db.query(CameraModel)
                    .filter(CameraModel.camera_id == self.camera_id)
                    .first()
                )

                if db_camera:
                    # Update motion settings (v3.5.7 enhanced - recommended defaults)
                    self.update_motion_settings(
                        sensitivity=db_camera.motion_sensitivity,
                        var_threshold=db_camera.motion_threshold,
                        noise_reduction=db_camera.noise_reduction,
                        detect_shadows=db_camera.detect_shadows,
                        detection_zones=db_camera.detection_zones,
                        shadow_detection_method=getattr(db_camera, 'shadow_detection_method', 'dual'),
                        erosion_iterations=getattr(db_camera, 'erosion_iterations', 2),
                        dilation_iterations=getattr(db_camera, 'dilation_iterations', 3),
                        motion_persistence_frames=getattr(db_camera, 'motion_persistence_frames', 2),
                        use_grayscale=getattr(db_camera, 'use_grayscale', True),
                        lighting_compensation=getattr(db_camera, 'lighting_compensation_enabled', True),
                        brightness_change_threshold=getattr(db_camera, 'brightness_change_threshold', 15),
                    )

                    # Update motion percentage threshold
                    self.motion_percentage_threshold = db_camera.motion_percentage_threshold

                    # Update image settings
                    self.update_image_settings(
                        brightness=db_camera.brightness,
                        contrast=db_camera.contrast,
                        saturation=db_camera.saturation,
                        sharpness=db_camera.sharpness,
                        noise_reduction_strength=db_camera.noise_reduction_strength,
                    )

                    # Update video settings
                    self.update_video_settings(
                        resolution=db_camera.resolution,
                        fps_target=db_camera.fps_target,
                        bitrate_kbps=db_camera.bitrate_kbps,
                        codec=db_camera.codec,
                    )

                    # Update other settings
                    self.post_motion_cooldown = db_camera.post_motion_cooldown

                    print(
                        f"Settings reloaded for camera '{
                            self.camera_id}' from database")
                # Session automatically closed by context manager
        except Exception as e:
            print(f"Error reloading settings from database: {e}")

    def _save_motion_snapshot(
        self, frame: np.ndarray, motion_areas: list
    ) -> Optional[str]:
        """
        Save a motion detection snapshot to disk.

        Args:
            frame: The frame with motion detected
            motion_areas: List of motion area dictionaries

        Returns:
            Path to the saved snapshot or None if save failed
        """
        try:
            # Create snapshots directory if it doesn't exist
            # Use custom path from settings or default
            snapshots_dir = Path(self.snapshots_path)
            snapshots_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            camera_name = self.camera_id or "unknown"
            filename = f"motion_{camera_name}_{timestamp}.jpg"
            snapshot_path = snapshots_dir / filename

            # Save the frame
            success = cv2.imwrite(str(snapshot_path), frame)

            if success:
                return str(snapshot_path)
            else:
                print(f"Failed to save snapshot to {snapshot_path}")
                return None

        except Exception as e:
            print(f"Error saving motion snapshot: {e}")
            return None

    def _create_motion_event(
        self,
        frame: np.ndarray,
        motion_areas: list,
        snapshot_path: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create a MotionDetectionEvent in the database.

        Args:
            frame: The frame where motion was detected
            motion_areas: List of motion area dictionaries
            snapshot_path: Path to the saved snapshot (optional)

        Returns:
            The ID of the created motion event or None if creation failed
        """
        if not self.camera_id:
            return None

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                # Calculate total motion area and percentage
                frame_area = frame.shape[0] * frame.shape[1]
                total_motion_area = sum(area.get("area", 0)
                                        for area in motion_areas)
                motion_percentage = (total_motion_area /
                                     frame_area * 100) if frame_area > 0 else 0

                # Get recording path if currently recording
                recording_path = None
                if self.recorder.is_recording and hasattr(self.recorder, "filename"):
                    recording_path = self.recorder.filename

                # Create motion event
                motion_event = MotionDetectionEvent(
                    camera_id=self.camera_id,
                    motion_area=total_motion_area,
                    motion_percentage=motion_percentage,
                    contour_count=len(motion_areas),
                    snapshot_path=snapshot_path,
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    recording_path=recording_path,
                )

                db.add(motion_event)
                db.commit()
                db.refresh(motion_event)

                event_id = motion_event.id
                # Session automatically closed by context manager

                print(
                    f"Created motion event {event_id} for camera {
                        self.camera_id}: {
                        motion_percentage:.1f}% motion, {
                        len(motion_areas)} contours")
                return event_id

        except Exception as e:
            print(f"Error creating motion event in database: {e}")
            return None

    def _update_motion_event_faces(self, motion_event_id: int, face_count: int):
        """
        Update a motion event with the number of faces detected.

        Args:
            motion_event_id: ID of the motion event to update
            face_count: Number of faces detected
        """
        if not motion_event_id:
            return

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                motion_event = db.query(MotionDetectionEvent).filter(
                    MotionDetectionEvent.id == motion_event_id
                ).first()

                if motion_event:
                    motion_event.faces_detected = face_count
                    db.commit()
                    print(
                        f"Updated motion event {motion_event_id} with {face_count} faces detected")
                # Session automatically closed by context manager
        except Exception as e:
            print(f"Error updating motion event with faces: {e}")

    def _save_face_snapshot(self, frame: np.ndarray, face_location: dict) -> Optional[str]:
        """
        Save a face detection snapshot to disk.

        Args:
            frame: The frame with the detected face
            face_location: Dictionary with top, right, bottom, left coordinates

        Returns:
            Path to the saved snapshot or None if save failed
        """
        try:
            # Create snapshots directory if it doesn't exist
            snapshots_dir = Path(self.snapshots_path)
            snapshots_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            camera_name = self.camera_id or "unknown"
            filename = f"face_{camera_name}_{timestamp}.jpg"
            snapshot_path = snapshots_dir / filename

            # Crop face region with some padding
            top = max(0, face_location.get("top", 0) - 20)
            right = min(frame.shape[1], face_location.get("right", frame.shape[1]) + 20)
            bottom = min(frame.shape[0], face_location.get("bottom", frame.shape[0]) + 20)
            left = max(0, face_location.get("left", 0) - 20)

            face_crop = frame[top:bottom, left:right]

            # Save the cropped face
            success = cv2.imwrite(str(snapshot_path), face_crop)

            if success:
                return str(snapshot_path)
            else:
                print(f"Failed to save face snapshot to {snapshot_path}")
                return None
        except Exception as e:
            print(f"Error saving face snapshot: {e}")
            return None

    def _create_face_detection_event(
        self,
        frame: np.ndarray,
        face: dict,
        snapshot_path: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create a FaceDetectionEvent in the database with face encoding for clustering.

        Args:
            frame: The frame where the face was detected
            face: Dictionary with face detection data (name, confidence, location, encoding)
            snapshot_path: Path to the saved face snapshot (optional)

        Returns:
            The ID of the created face detection event or None if creation failed
        """
        if not self.camera_id:
            return None

        try:
            # FIX v3.6.0.1: Use context manager to prevent session leak
            with get_db_context() as db:
                # Get recording path if currently recording
                recording_path = None
                recording_id = None
                if self.recorder.is_recording and hasattr(self.recorder, "filename"):
                    recording_path = self.recorder.filename
                    # TODO: Get recording_id from database if needed

                location = face.get("location", {})

                # Create face detection event
                face_event = FaceDetectionEvent(
                    camera_id=self.camera_id,
                    person_name=face.get("name", "Unknown"),
                    confidence=face.get("confidence", 0.0),
                    detected_at=datetime.now(),
                    location_top=location.get("top", 0),
                    location_right=location.get("right", 0),
                    location_bottom=location.get("bottom", 0),
                    location_left=location.get("left", 0),
                    snapshot_path=snapshot_path,
                    recording_path=recording_path,
                    recording_id=recording_id,
                    motion_detected=face.get("motion_detected", False),
                    frame_width=frame.shape[1],
                    frame_height=frame.shape[0],
                    face_encoding=face.get("encoding"),  # Base64 encoded face encoding for clustering
                )

                db.add(face_event)
                db.commit()
                db.refresh(face_event)

                event_id = face_event.id
                person_name = face.get("name", "Unknown")
                confidence = face.get("confidence", 0.0)
                detected_at = face_event.detected_at
                # Session automatically closed by context manager

                print(
                    f"Created face detection event {event_id} for camera {self.camera_id}: "
                    f"{person_name} (confidence: {confidence:.2f})"
                )

                # Trigger automation rules for identified persons (not Unknown)
                if person_name != "Unknown":
                    try:
                        process_face_detection(
                            person_name=person_name,
                            camera_id=self.camera_id,
                            confidence=confidence,
                            detected_at=detected_at
                        )
                    except Exception as e:
                        print(f"Error processing automation rules for {person_name}: {e}")

                return event_id

        except Exception as e:
            print(f"Error creating face detection event in database: {e}")
            return None


class MockCamera(Camera):
    """Enhanced MockCamera with granular controls"""

    def __init__(
        self,
        source: str = "mock",
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(source, camera_id, enable_face_detection, db_settings)
        self.width = 640
        self.height = 480
        self.frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def start(self):
        self.is_running = True
        print("Mock camera started.")

    def stop(self):
        if self.recorder.is_recording:
            self.recorder.stop()
        self.is_running = False
        print("Mock camera stopped.")

    def get_frame(self):
        if not self.is_running:
            return None, False

        # Check if we should process this frame based on FPS target
        if not self.video_processor.should_process_frame():
            return None, False

        # Create a blank frame with a timestamp
        self.frame.fill(0)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cv2.putText(
            self.frame,
            f"Mock Camera",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            self.frame,
            timestamp,
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        # Add a moving circle for visual feedback
        seconds = int(time.time())
        x = int(self.width / 2 + 100 * np.cos(seconds))
        y = int(self.height / 2 + 100 * np.sin(seconds))
        cv2.circle(self.frame, (x, y), 20, (0, 255, 0), -1)

        # Store clean frame for recording
        clean_frame = self.frame.copy()

        # Apply video processing (resolution adjustment if needed)
        processed_frame = self.video_processor.process_frame(clean_frame)

        # Apply image quality adjustments
        if self.image_processor.has_adjustments():
            processed_frame = self.image_processor.process(processed_frame)

        # Motion detection on processed frame
        processed_frame, self.motion_detected, motion_areas = (
            self.motion_detector.detect(processed_frame)
        )

        # Check motion percentage threshold before triggering event
        if self.motion_detected and motion_areas:
            # Calculate motion percentage
            frame_area = processed_frame.shape[0] * processed_frame.shape[1]
            total_motion_area = sum(area.get("area", 0) for area in motion_areas)
            motion_percentage = (total_motion_area / frame_area * 100) if frame_area > 0 else 0
            
            # Only trigger if motion percentage exceeds threshold
            if motion_percentage < self.motion_percentage_threshold:
                # Motion detected but below threshold - ignore it
                self.motion_detected = False
                motion_areas = []

        # Trigger motion alert if motion detected
        if self.motion_detected:
            # Save snapshot and create database record
            snapshot_path = self._save_motion_snapshot(
                processed_frame, motion_areas)
            self.current_motion_event_id = self._create_motion_event(
                processed_frame, motion_areas, snapshot_path
            )

            try:
                alert_manager = get_alert_manager()
                camera_id = self.camera_id or "mock_cam"
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            alert_manager.trigger_motion_alert(
                                camera_id=camera_id,
                                event_data={
                                    "timestamp": time.time(),
                                    "motion_areas": motion_areas,
                                    "motion_event_id": self.current_motion_event_id,
                                    "snapshot_path": snapshot_path,
                                },
                            ),
                            loop,
                        )
                except RuntimeError:
                    # No event loop running, skip alert
                    pass
            except Exception as e:
                print(f"Error triggering motion alert: {e}")
        else:
            # Clear motion event when no motion detected
            self.current_motion_event_id = None

        # Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = (
                self.face_detector.process_frame(
                    processed_frame, self.motion_detected))

            # Save face detection events to database
            if self.last_faces_detected:
                for face in self.last_faces_detected:
                    # Save face snapshot
                    face_snapshot_path = self._save_face_snapshot(
                        processed_frame, face.get("location", {})
                    )

                    # Create face detection event in database with encoding
                    face_event_id = self._create_face_detection_event(
                        processed_frame, face, face_snapshot_path
                    )

            # Update motion event with face count if faces detected
            if self.last_faces_detected and self.current_motion_event_id:
                self._update_motion_event_faces(
                    self.current_motion_event_id, len(
                        self.last_faces_detected)
                )

            # Log faces to recorder if recording
            if self.recorder.is_recording and self.last_faces_detected:
                for face in self.last_faces_detected:
                    self.recorder.add_face_detection(face)

        # Recording logic
        if self.motion_detected:
            self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                self.recorder.start(self.width, self.height)

        if self.recorder.is_recording:
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (self.width - 30, 30),
                       10, (0, 0, 255), -1)
            self.recorder.write(clean_frame)  # Write clean frame to file

            # Stop recording if: no motion for cooldown period OR max duration
            # exceeded
            if (
                not self.motion_detected
                and (time.time() - self.last_motion_time > self.post_motion_cooldown)
            ) or self.recorder.should_stop_recording():
                self.recorder.stop()

        return processed_frame, self.motion_detected


class RTSPCamera(Camera):
    """Enhanced RTSPCamera with granular controls"""

    def __init__(
        self,
        source: str,
        camera_id: str = None,
        enable_face_detection: bool = True,
        db_settings: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(source, camera_id, enable_face_detection, db_settings)

    def start(self):
        # Detect if source is a USB device index (integer or numeric string)
        try:
            # Try to convert to int - if successful, it's a USB device
            device_index = int(self.source)
            print(f"Connecting to USB camera at index: {device_index}")
            # Use default backend for USB cameras (no CAP_FFMPEG)
            self.capture = cv2.VideoCapture(device_index)
        except (ValueError, TypeError):
            # Not a number, assume it's an RTSP URL or device path
            print(f"Connecting to RTSP stream: {self.source}")
            self.capture = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

        if not self.capture.isOpened():
            print(f"Error: Could not open camera source: {self.source}")
            self.is_running = False
            return
        self.is_running = True
        print("Camera started successfully.")

    def stop(self):
        if self.recorder.is_recording:
            self.recorder.stop()
        if self.is_running and self.capture:
            self.capture.release()
        self.is_running = False
        print("RTSP camera stopped.")

    def get_frame(self):
        if not self.is_running or not self.capture.isOpened():
            return None, False

        # Check if we should process this frame based on FPS target
        if not self.video_processor.should_process_frame():
            return None, False

        ret, frame = self.capture.read()
        if not ret:
            print("Error: Failed to grab frame from RTSP stream.")
            return None, False

        # Store clean frame for recording
        clean_frame = frame.copy()

        # Apply video processing (resolution adjustment if needed)
        processed_frame = self.video_processor.process_frame(frame)

        # Apply image quality adjustments
        if self.image_processor.has_adjustments():
            processed_frame = self.image_processor.process(processed_frame)

        # Motion detection on processed frame
        processed_frame, self.motion_detected, motion_areas = (
            self.motion_detector.detect(processed_frame)
        )

        # Check motion percentage threshold before triggering event
        if self.motion_detected and motion_areas:
            # Calculate motion percentage
            frame_area = processed_frame.shape[0] * processed_frame.shape[1]
            total_motion_area = sum(area.get("area", 0) for area in motion_areas)
            motion_percentage = (total_motion_area / frame_area * 100) if frame_area > 0 else 0
            
            # Only trigger if motion percentage exceeds threshold
            if motion_percentage < self.motion_percentage_threshold:
                # Motion detected but below threshold - ignore it
                self.motion_detected = False
                motion_areas = []

        # Trigger motion alert if motion detected
        if self.motion_detected:
            print(f"🔴 [RTSP] MOTION DETECTED! Camera: {self.camera_id}")
            # Save snapshot and create database record
            snapshot_path = self._save_motion_snapshot(
                processed_frame, motion_areas)
            print(f"📸 [RTSP] Snapshot saved: {snapshot_path}")
            self.current_motion_event_id = self._create_motion_event(
                processed_frame, motion_areas, snapshot_path
            )
            print(f"✅ [RTSP] Motion event created: ID={self.current_motion_event_id}")

            try:
                alert_manager = get_alert_manager()
                camera_id = self.camera_id or "rtsp_cam"
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            alert_manager.trigger_motion_alert(
                                camera_id=camera_id,
                                event_data={
                                    "timestamp": time.time(),
                                    "motion_areas": motion_areas,
                                    "motion_event_id": self.current_motion_event_id,
                                    "snapshot_path": snapshot_path,
                                },
                            ),
                            loop,
                        )
                except RuntimeError:
                    # No event loop running, skip alert
                    pass
            except Exception as e:
                print(f"Error triggering motion alert: {e}")
        else:
            # Clear motion event when no motion detected
            self.current_motion_event_id = None

        # Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = (
                self.face_detector.process_frame(
                    processed_frame, self.motion_detected))

            # Save face detection events to database
            if self.last_faces_detected:
                for face in self.last_faces_detected:
                    # Save face snapshot
                    face_snapshot_path = self._save_face_snapshot(
                        processed_frame, face.get("location", {})
                    )

                    # Create face detection event in database with encoding
                    face_event_id = self._create_face_detection_event(
                        processed_frame, face, face_snapshot_path
                    )

            # Update motion event with face count if faces detected
            if self.last_faces_detected and self.current_motion_event_id:
                self._update_motion_event_faces(
                    self.current_motion_event_id, len(
                        self.last_faces_detected)
                )

            # Log faces to recorder if recording
            if self.recorder.is_recording and self.last_faces_detected:
                for face in self.last_faces_detected:
                    self.recorder.add_face_detection(face)

        # Recording logic
        if self.motion_detected:
            self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                height, width, _ = clean_frame.shape
                self.recorder.start(width, height)

        if self.recorder.is_recording:
            height, width, _ = clean_frame.shape
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (width - 30, 30), 10, (0, 0, 255), -1)
            # Write original clean frame to file
            self.recorder.write(clean_frame)

            if not self.motion_detected and (
                time.time() - self.last_motion_time > self.post_motion_cooldown
            ):
                self.recorder.stop()

        return processed_frame, self.motion_detected


class CameraManager:
    """
    Enhanced Camera Manager with database integration.

    New in v3.5.0:
    - Loads camera settings from database
    - Passes settings to processor instances
    - Supports dynamic settings reload
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance.cameras = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def _load_camera_settings(
            self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Load camera settings from database and merge with system settings"""
        try:
            # FIXED: Use context manager to prevent session leak (v3.6.0.1)
            with get_db_context() as db:
                # Load system settings
                from backend.database.crud import get_all_system_settings

                settings_list = get_all_system_settings(db)

                # Convert list to dictionary
                system_settings = {}
                for setting in settings_list:
                    try:
                        if setting.setting_type == "int":
                            system_settings[setting.setting_key] = int(
                                setting.setting_value
                            )
                        elif setting.setting_type == "float":
                            system_settings[setting.setting_key] = float(
                                setting.setting_value
                            )
                        elif setting.setting_type == "boolean":
                            system_settings[setting.setting_key] = (
                                setting.setting_value.lower() == "true"
                            )
                        else:
                            system_settings[setting.setting_key] = setting.setting_value
                    except (ValueError, AttributeError):
                        system_settings[setting.setting_key] = setting.setting_value

                # Load camera-specific settings
                db_camera = (
                    db.query(CameraModel).filter(
                        CameraModel.camera_id == camera_id).first())

                if db_camera:
                    settings = {
                        # Motion detection settings
                        "min_contour_area": db_camera.min_contour_area,
                        "motion_sensitivity": db_camera.motion_sensitivity,
                        "motion_threshold": db_camera.motion_threshold,
                        "noise_reduction": db_camera.noise_reduction,
                        "detect_shadows": db_camera.detect_shadows,
                        "detection_zones": db_camera.detection_zones,
                        # Image quality settings
                        "brightness": db_camera.brightness,
                        "contrast": db_camera.contrast,
                        "saturation": db_camera.saturation,
                        "sharpness": db_camera.sharpness,
                        "noise_reduction_strength": db_camera.noise_reduction_strength,
                        # Video quality settings
                        "resolution": db_camera.resolution,
                        "fps_target": db_camera.fps_target,
                        "bitrate_kbps": db_camera.bitrate_kbps,
                        "codec": db_camera.codec,
                        # Recording settings
                        "post_motion_cooldown": db_camera.post_motion_cooldown,
                        # System settings (paths, max duration, display mode)
                        "recordings_path": system_settings.get(
                            "recordings_path", "recordings"
                        ),
                        "faces_path": system_settings.get("faces_path", "faces"),
                        "snapshots_path": system_settings.get("snapshots_path", "data/snapshots"),
                        "max_recording_duration": int(
                            system_settings.get("max_recording_duration", 300)
                        ),
                        "display_mode": system_settings.get("display_mode", "grid"),
                        "cycle_interval": int(system_settings.get("cycle_interval", 10)),
                    }

                    return settings

                return None

        except Exception as e:
            print(f"Error loading camera settings from database: {e}")
            return None

    def add_camera(
        self,
        camera_id: str,
        camera_type: str,
        source: str,
        enable_face_detection: bool = True,
    ):
        """Add a camera with settings loaded from database"""
        with self._lock:
            if camera_id in self.cameras:
                print(f"Camera with ID '{camera_id}' already exists.")
                return

            # Load settings from database
            db_settings = self._load_camera_settings(camera_id)
            if db_settings:
                print(
                    f"Loaded settings for camera '{camera_id}' from database")
            else:
                print(f"Using default settings for camera '{camera_id}'")

            # Create camera with appropriate type
            if camera_type == "rtsp":
                camera = RTSPCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            elif camera_type == "usb":
                # USB cameras use RTSP camera class with device index or path
                camera = RTSPCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            elif camera_type == "mock":
                camera = MockCamera(
                    source, camera_id, enable_face_detection, db_settings
                )
            else:
                print(f"Unknown camera type: {camera_type}")
                return

            # Start camera
            camera.start()
            if camera.is_running:
                camera.recorder.camera_id = camera_id
                self.cameras[camera_id] = camera
                print(
                    f"Camera '{camera_id}' added and started (face detection: {enable_face_detection}).")
            else:
                print(f"Failed to start camera '{camera_id}'.")

    def get_camera(self, camera_id: str):
        """Get camera instance by ID"""
        with self._lock:
            return self.cameras.get(camera_id)

    def remove_camera(self, camera_id: str):
        """Remove and stop a camera"""
        with self._lock:
            if camera_id in self.cameras:
                self.cameras[camera_id].stop()
                del self.cameras[camera_id]
                print(f"Camera '{camera_id}' removed.")

    def reload_camera_settings(self, camera_id: str):
        """Reload settings from database for a specific camera"""
        with self._lock:
            camera = self.cameras.get(camera_id)
            if camera:
                camera.reload_settings_from_db()
            else:
                print(f"Camera '{camera_id}' not found.")

    def get_camera_settings(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """Get current settings for a camera"""
        with self._lock:
            camera = self.cameras.get(camera_id)
            if camera:
                return camera.get_all_settings()
            return None

    def get_all_face_detections(self):
        """Get face detections from all cameras"""
        with self._lock:
            all_detections = {}
            for camera_id, camera in self.cameras.items():
                all_detections[camera_id] = {
                    "recent_faces": camera.last_faces_detected,
                    "statistics": camera.get_face_statistics(),
                }
            return all_detections


manager = CameraManager()
