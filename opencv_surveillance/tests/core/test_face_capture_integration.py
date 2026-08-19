# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
The guarantee that makes the capture policy safe to ship.

Automation and capture used to be the same function call. These tests hold them
apart: whatever the policy decides about storing a likeness, the user's rules
still run. The failure being guarded against is silent — a door that stops
unlocking looks exactly like a successful reduction in captures.
"""

import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.core.capture_policy import MODE_ALL_FACES, CapturePolicy, CaptureSettings


@pytest.fixture
def camera(monkeypatch):
    """
    A Camera with only the collaborators _handle_detected_faces touches.

    Built by hand rather than constructed: the real __init__ opens devices and
    spins up processors, none of which this behaviour depends on.
    """
    from backend.core import camera_manager as cm

    class _StubCamera(cm.Camera):
        """Camera is abstract; these three are irrelevant to face handling."""

        def get_frame(self):  # pragma: no cover
            return None

        def start(self):  # pragma: no cover
            return None

        def stop(self):  # pragma: no cover
            return None

    cam = object.__new__(_StubCamera)
    cam.camera_id = "front_door"
    cam._last_unknown_automation_time = 0.0
    cam.unknown_automation_min_interval = 10.0
    cam._capture_policy = CapturePolicy(CaptureSettings())
    cam.face_capture_mode = "system_default"

    automations = []
    monkeypatch.setattr(
        cm, "process_face_detection",
        lambda **kwargs: automations.append(kwargs),
    )

    cam._save_face_snapshot = MagicMock(return_value="/data/snapshots/x.jpg")
    cam._create_face_detection_event = MagicMock(return_value=1)
    # Seeding reads the detections table to recover "already captured today"
    # across a restart. There is no database here, and these tests start from a
    # deliberately empty history, so it is a no-op.
    cam._seed_capture_history = lambda name: None

    # Confirmation state comes from the persons table, which is not present
    # here. None means "no record", which is what an installation from before
    # the person migration reports — and these tests assert the behaviour that
    # must be unchanged for exactly that case.
    cam._is_person_confirmed = lambda name: None

    # Returns (size, trained) — both, because size alone is not what stops
    # collection. Default trained=True so a test that only sets a size is
    # describing a well-established cluster, which is what these assert.
    cam._cluster_state_for = lambda face: (
        face.get("_cluster_size"),
        face.get("_cluster_trained", True),
    )

    return types.SimpleNamespace(cam=cam, automations=automations)


def face(name="Unknown", top=100, **extra):
    payload = {
        "name": name,
        "confidence": 0.9,
        "location": {"top": top, "left": 100, "bottom": top + 80, "right": 180},
        "encoding": "abc123",
    }
    payload.update(extra)
    return payload


class TestActingIsNeverSuppressed:
    def test_automation_fires_on_the_very_first_sighting(self, camera):
        """
        Before any capture is allowed. A known person must trigger their
        lighting and access rules immediately, not after three passes.
        """
        cam, automations = camera.cam, camera.automations

        cam._handle_detected_faces(np.zeros((480, 640, 3), np.uint8), [face("Mikel")])

        assert len(automations) == 1
        assert automations[0]["person_name"] == "Mikel"
        cam._save_face_snapshot.assert_not_called()  # not yet confirmed

    def test_automation_fires_every_pass_while_captures_are_suppressed(self, camera):
        cam, automations = camera.cam, camera.automations
        frame = np.zeros((480, 640, 3), np.uint8)

        for _ in range(10):
            cam._handle_detected_faces(frame, [face("Mikel")])

        assert len(automations) == 10          # the rules ran every time
        assert cam._save_face_snapshot.call_count == 1   # one likeness kept

    def test_a_mature_cluster_still_triggers_notification(self, camera):
        """
        The user's third example: identify and notify, add nothing to the
        cluster and do not retrain.

        "Add nothing" is now once a day rather than never. A trained cluster
        whose face recognition could not name gets one capture per camera per
        day, because a recognition failure on a trained cluster is evidence the
        training does not cover this angle or this light — the moment more
        material would help. What must not change is that identifying and
        notifying never depend on whether a likeness was kept.
        """
        cam, automations = camera.cam, camera.automations
        frame = np.zeros((480, 640, 3), np.uint8)
        subject = face("Unknown", _cluster_size=40)

        for _ in range(5):
            cam._handle_detected_faces(frame, [subject])

        assert len(automations) == 1  # unknown-person throttle, not suppression
        # One hard-case capture for the day, then nothing more.
        assert cam._save_face_snapshot.call_count == 1

    def test_unknown_automation_throttle_is_unchanged(self, camera):
        """That throttle is about automation rate and predates this work."""
        cam, automations = camera.cam, camera.automations
        frame = np.zeros((480, 640, 3), np.uint8)

        for _ in range(5):
            cam._handle_detected_faces(frame, [face("Unknown")])

        assert len(automations) == 1


class TestWhatGetsRecorded:
    def test_a_suppressed_capture_still_writes_a_sighting_without_an_encoding(self, camera):
        cam = camera.cam

        cam._handle_detected_faces(np.zeros((480, 640, 3), np.uint8), [face("Mikel")])

        cam._save_face_snapshot.assert_not_called()
        assert cam._create_face_detection_event.called
        _args, kwargs = cam._create_face_detection_event.call_args
        assert kwargs["store_encoding"] is False

    def test_a_confirmed_capture_stores_the_encoding(self, camera):
        cam = camera.cam
        frame = np.zeros((480, 640, 3), np.uint8)

        for _ in range(3):
            cam._handle_detected_faces(frame, [face("Mikel")])

        _args, kwargs = cam._create_face_detection_event.call_args
        assert kwargs["store_encoding"] is True
        cam._save_face_snapshot.assert_called_once()

    def test_sightings_are_throttled_so_rows_do_not_pile_up(self, camera):
        cam = camera.cam
        frame = np.zeros((480, 640, 3), np.uint8)

        for _ in range(50):
            cam._handle_detected_faces(frame, [face("Mikel")])

        # Far fewer rows than passes; the exact count is the policy's business.
        assert cam._create_face_detection_event.call_count < 5

    def test_all_faces_mode_captures_everything(self, camera):
        cam = camera.cam
        cam.face_capture_mode = MODE_ALL_FACES
        frame = np.zeros((480, 640, 3), np.uint8)

        for _ in range(3):
            cam._handle_detected_faces(frame, [face("Unknown")])

        assert cam._save_face_snapshot.call_count == 3

    def test_no_faces_is_a_no_op(self, camera):
        cam = camera.cam

        cam._handle_detected_faces(np.zeros((480, 640, 3), np.uint8), [])

        cam._save_face_snapshot.assert_not_called()
        cam._create_face_detection_event.assert_not_called()
        assert camera.automations == []
