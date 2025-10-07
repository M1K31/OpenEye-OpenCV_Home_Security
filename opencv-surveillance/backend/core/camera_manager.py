# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Manager - MODIFIED to include face detection
This replaces your existing camera_manager.py
"""

import cv2
import numpy as np
import time
from abc import ABC, abstractmethod
from .motion_detector import MotionDetector
from .recorder import Recorder
from .face_detection import FaceDetector  # NEW IMPORT
import asyncio
from backend.core.alert_manager import get_alert_manager

class Camera(ABC):
    def __init__(self, source, enable_face_detection=True):  # MODIFIED: Added face detection param
        self.source = source
        self.capture = None
        self.is_running = False
        self.motion_detector = MotionDetector()
        self.motion_detected = False
        self.recorder = Recorder()
        self.last_motion_time = 0
        self.post_motion_cooldown = 5  # seconds to record after motion stops

        # NEW: Face detection integration
        self.face_detector = FaceDetector(enabled=enable_face_detection)
        self.last_faces_detected = []

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_frame(self):
        pass

    # NEW METHODS for face detection
    def enable_face_detection(self, enabled: bool):
        """Enable or disable face detection for this camera"""
        self.face_detector.set_enabled(enabled)

    def get_face_statistics(self):
        """Get face detection statistics"""
        return self.face_detector.get_statistics()


class MockCamera(Camera):
    def __init__(self, source="mock", enable_face_detection=True):  # MODIFIED
        super().__init__(source, enable_face_detection)
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

        # Create a blank frame with a timestamp
        self.frame.fill(0)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        cv2.putText(self.frame, f"Mock Camera", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(self.frame, timestamp, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Add a moving circle for visual feedback
        seconds = int(time.time())
        x = int(self.width / 2 + 100 * np.cos(seconds))
        y = int(self.height / 2 + 100 * np.sin(seconds))
        cv2.circle(self.frame, (x, y), 20, (0, 255, 0), -1)

        clean_frame = self.frame.copy()

        # Motion detection
        processed_frame, self.motion_detected = self.motion_detector.detect(self.frame.copy())

        # NEW: Trigger motion alert if motion detected
        if self.motion_detected:
            try:
                alert_manager = get_alert_manager()
                camera_id = getattr(self, 'camera_id', 'mock_cam')
                asyncio.create_task(alert_manager.trigger_motion_alert(
                    camera_id=camera_id,
                    event_data={'timestamp': time.time()}
                ))
            except Exception as e:
                print(f"Error triggering motion alert: {e}")

        # NEW: Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = self.face_detector.process_frame(
                processed_frame,
                self.motion_detected
            )

        # Recording logic
        if self.motion_detected:
            self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                self.recorder.start(self.width, self.height)

        if self.recorder.is_recording:
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (self.width - 30, 30), 10, (0, 0, 255), -1)
            self.recorder.write(clean_frame) # Write the clean frame to file

            if not self.motion_detected and (time.time() - self.last_motion_time > self.post_motion_cooldown):
                self.recorder.stop()

        return processed_frame, self.motion_detected


class RTSPCamera(Camera):
    def __init__(self, source, enable_face_detection=True):  # MODIFIED
        super().__init__(source, enable_face_detection)

    def start(self):
        print(f"Connecting to RTSP stream: {self.source}")
        self.capture = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
        if not self.capture.isOpened():
            print(f"Error: Could not open RTSP stream: {self.source}")
            self.is_running = False
            return
        self.is_running = True
        print("RTSP camera started.")

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

        ret, frame = self.capture.read()
        if not ret:
            print("Error: Failed to grab frame from RTSP stream.")
            return None, False

        # Motion detection
        processed_frame, self.motion_detected = self.motion_detector.detect(frame.copy())

        # NEW: Trigger motion alert if motion detected
        if self.motion_detected:
            try:
                alert_manager = get_alert_manager()
                camera_id = getattr(self, 'camera_id', 'rtsp_cam')
                asyncio.create_task(alert_manager.trigger_motion_alert(
                    camera_id=camera_id,
                    event_data={'timestamp': time.time()}
                ))
            except Exception as e:
                print(f"Error triggering motion alert: {e}")

        # NEW: Face detection
        if self.face_detector.enabled:
            processed_frame, self.last_faces_detected = self.face_detector.process_frame(
                processed_frame,
                self.motion_detected
            )

        # Recording logic
        if self.motion_detected:
            self.last_motion_time = time.time()
            if not self.recorder.is_recording:
                height, width, _ = frame.shape
                self.recorder.start(width, height)

        if self.recorder.is_recording:
            height, width, _ = frame.shape
            # Add recording indicator to the processed frame for streaming
            cv2.circle(processed_frame, (width - 30, 30), 10, (0, 0, 255), -1)
            self.recorder.write(frame) # Write the original, clean frame to file

            if not self.motion_detected and (time.time() - self.last_motion_time > self.post_motion_cooldown):
                self.recorder.stop()

        return processed_frame, self.motion_detected


class CameraManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CameraManager, cls).__new__(cls)
            cls._instance.cameras = {}
        return cls._instance

    def add_camera(self, camera_id, camera_type, source, enable_face_detection=True):  # MODIFIED
        if camera_id in self.cameras:
            print(f"Camera with ID '{camera_id}' already exists.")
            return

        if camera_type == "rtsp":
            camera = RTSPCamera(source, enable_face_detection)
        elif camera_type == "mock":
            camera = MockCamera(source, enable_face_detection)
        else:
            print(f"Unknown camera type: {camera_type}")
            return

        camera.start()
        if camera.is_running:
            self.cameras[camera_id] = camera
            print(f"Camera '{camera_id}' added and started (face detection: {enable_face_detection}).")
        else:
            print(f"Failed to start camera '{camera_id}'.")

    def get_camera(self, camera_id):
        return self.cameras.get(camera_id)

    def remove_camera(self, camera_id):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()
            del self.cameras[camera_id]
            print(f"Camera '{camera_id}' removed.")

    # NEW METHOD
    def get_all_face_detections(self):
        """Get face detections from all cameras"""
        all_detections = {}
        for camera_id, camera in self.cameras.items():
            all_detections[camera_id] = {
                'recent_faces': camera.last_faces_detected,
                'statistics': camera.get_face_statistics()
            }
        return all_detections


manager = CameraManager()