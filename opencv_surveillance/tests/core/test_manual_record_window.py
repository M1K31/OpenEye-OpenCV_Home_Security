"""Tests that drive the REAL MockCamera.get_frame() frame-processing loop to
verify the manual-record window (self.manual_record_until) is honored
correctly alongside normal motion-triggered recording.

These exercise the actual production method at backend/core/camera_manager.py
(MockCamera.get_frame, ~line 810) rather than reimplementing its logic, per
the review finding that the manual-record window was only verified by prose
walk-throughs.
"""
import time

import numpy as np
import pytest
from unittest.mock import MagicMock

from backend.core.camera_manager import MockCamera


def make_camera():
    """Build a real, lightweight MockCamera and swap in mocks for the
    collaborators that would otherwise touch disk/DB/CV algorithms.

    MockCamera's __init__ only constructs plain Python/numpy helper objects
    (no hardware, no network, no DB connection is opened), so we use the
    real constructor rather than __new__. We disable face detection and
    leave camera_id=None so the motion-event/snapshot helper methods
    (which touch disk and the DB) short-circuit to no-ops rather than
    needing further mocking.
    """
    cam = MockCamera(source="mock", camera_id=None, enable_face_detection=False)

    # Replace the recorder with a fully controlled mock.
    cam.recorder = MagicMock()
    cam.recorder.is_recording = False
    cam.recorder.should_stop_recording.return_value = False

    # Replace the motion detector so self.motion_detected is driven directly
    # by the test rather than depending on real background-subtraction
    # timing/behavior on synthetic frames.
    cam.motion_detector = MagicMock()

    return cam


def set_motion(cam, detected: bool):
    """Configure the mocked motion detector's next detect() result."""
    if detected:
        motion_areas = [{"area": 999999}]  # large enough to clear the % threshold
    else:
        motion_areas = []
    cam.motion_detector.detect.return_value = (
        cam.frame, detected, motion_areas, []
    )


def force_frame_processing(cam):
    """Ensure should_process_frame() returns True on the next call by
    resetting the FPS throttle, so get_frame() doesn't short-circuit."""
    cam.video_processor.last_frame_time = 0


def run_frame(cam, motion: bool):
    force_frame_processing(cam)
    set_motion(cam, motion)
    cam.is_running = True
    return cam.get_frame()


class TestManualRecordWindowOpenNoMotion:
    """Scenario 1: manual window open, no motion -> recording starts and is
    not stopped while the window remains open."""

    def test_recording_starts_without_motion(self):
        cam = make_camera()
        cam.manual_record_until = time.time() + 30  # window open for 30s
        cam.recorder.is_recording = False

        run_frame(cam, motion=False)

        cam.recorder.start.assert_called_once()
        cam.recorder.stop.assert_not_called()

    def test_recording_not_stopped_while_window_open(self):
        cam = make_camera()
        cam.manual_record_until = time.time() + 30
        cam.recorder.is_recording = True
        # Simulate motion having been stale for way longer than the cooldown
        cam.last_motion_time = time.time() - 999
        cam.post_motion_cooldown = 5

        run_frame(cam, motion=False)

        cam.recorder.stop.assert_not_called()


class TestManualRecordWindowExpired:
    """Scenario 2: window expired, no motion, post-motion cooldown elapsed
    -> normal stop behavior resumes."""

    def test_recording_stops_after_window_expires_and_cooldown_elapses(self):
        cam = make_camera()
        cam.manual_record_until = time.time() - 5  # window closed 5s ago
        cam.recorder.is_recording = True
        cam.post_motion_cooldown = 5
        cam.last_motion_time = time.time() - 999  # long past cooldown

        run_frame(cam, motion=False)

        cam.recorder.stop.assert_called_once()

    def test_recording_not_stopped_if_cooldown_has_not_elapsed(self):
        """Sanity check: even with the window expired, stop should NOT be
        called yet if we're still inside the post-motion cooldown."""
        cam = make_camera()
        cam.manual_record_until = time.time() - 5
        cam.recorder.is_recording = True
        cam.post_motion_cooldown = 5
        cam.last_motion_time = time.time()  # motion "just" happened

        run_frame(cam, motion=False)

        cam.recorder.stop.assert_not_called()


class TestDefaultBehaviorUnchanged:
    """Scenario 3: manual_record_until == 0 (default) -> original
    motion-triggered start/stop behavior is unchanged."""

    def test_motion_starts_recording(self):
        cam = make_camera()
        assert cam.manual_record_until == 0.0
        cam.recorder.is_recording = False

        run_frame(cam, motion=True)

        cam.recorder.start.assert_called_once()
        cam.recorder.stop.assert_not_called()

    def test_motion_cleared_and_cooldown_elapsed_stops_recording(self):
        cam = make_camera()
        assert cam.manual_record_until == 0.0
        cam.recorder.is_recording = True
        cam.post_motion_cooldown = 5
        cam.last_motion_time = time.time() - 999  # cooldown long elapsed

        run_frame(cam, motion=False)

        cam.recorder.stop.assert_called_once()

    def test_motion_cleared_but_cooldown_not_elapsed_keeps_recording(self):
        cam = make_camera()
        assert cam.manual_record_until == 0.0
        cam.recorder.is_recording = True
        cam.post_motion_cooldown = 5
        cam.last_motion_time = time.time()  # motion just stopped

        run_frame(cam, motion=False)

        cam.recorder.stop.assert_not_called()
