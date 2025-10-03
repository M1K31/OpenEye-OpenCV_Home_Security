# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye.
import cv2
import os
import time
from datetime import datetime

class Recorder:
    """
    Handles video recording to a file.
    """
    def __init__(self, output_dir="recordings"):
        self.output_dir = output_dir
        self.is_recording = False
        self.writer = None
        self.filename = ""

        # Create the output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def start(self, frame_width, frame_height, fps=20):
        """
        Starts a new recording session.
        """
        if self.is_recording:
            print("Already recording.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(self.output_dir, f"motion_{timestamp}.mp4")

        # Using 'mp4v' codec for MP4 files.
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(self.filename, fourcc, fps, (frame_width, frame_height))

        if not self.writer.isOpened():
            print(f"Error: Could not open video writer for {self.filename}")
            return

        self.is_recording = True
        print(f"Started recording to {self.filename}")

    def write(self, frame):
        """
        Writes a frame to the current recording.
        """
        if self.is_recording and self.writer:
            self.writer.write(frame)

    def stop(self):
        """
        Stops the current recording session and releases the writer.
        """
        if not self.is_recording:
            return

        self.is_recording = False
        if self.writer:
            self.writer.release()
            self.writer = None
            print(f"Stopped recording. Video saved to {self.filename}")
        self.filename = ""