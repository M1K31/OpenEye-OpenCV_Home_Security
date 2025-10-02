import cv2
import numpy as np
import time
from abc import ABC, abstractmethod
from .motion_detector import MotionDetector
from .recorder import Recorder

class Camera(ABC):
    def __init__(self, source):
        self.source = source
        self.capture = None
        self.is_running = False
        self.motion_detector = MotionDetector()
        self.motion_detected = False
        self.recorder = Recorder()
        self.last_motion_time = 0
        self.post_motion_cooldown = 5  # seconds to record after motion stops

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_frame(self):
        pass

class MockCamera(Camera):
    def __init__(self, source="mock"):
        super().__init__(source)
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
        processed_frame, self.motion_detected = self.motion_detector.detect(self.frame.copy())

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
    def __init__(self, source):
        super().__init__(source)

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

        processed_frame, self.motion_detected = self.motion_detector.detect(frame.copy())

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

    def add_camera(self, camera_id, camera_type, source):
        if camera_id in self.cameras:
            print(f"Camera with ID '{camera_id}' already exists.")
            return

        if camera_type == "rtsp":
            camera = RTSPCamera(source)
        elif camera_type == "mock":
            camera = MockCamera(source)
        else:
            print(f"Unknown camera type: {camera_type}")
            return

        camera.start()
        if camera.is_running:
            self.cameras[camera_id] = camera
            print(f"Camera '{camera_id}' added and started.")
        else:
            print(f"Failed to start camera '{camera_id}'.")

    def get_camera(self, camera_id):
        return self.cameras.get(camera_id)

    def remove_camera(self, camera_id):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()
            del self.cameras[camera_id]
            print(f"Camera '{camera_id}' removed.")

manager = CameraManager()