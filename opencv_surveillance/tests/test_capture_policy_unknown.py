# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
An unknown face must keep an image, or the sighting cannot be acted on.

Reported 2026-08-23: the Detections page listed 50 Unknown entries with no
images. Investigation showed nothing had been deleted — every one of those rows
had `snapshot_path = NULL` from the moment it was written, and also no face
encoding and no cluster.

The cause was the persistence gate. An unknown face is tracked only by the
overlap of its bounding box between passes, and these never reached the three
consecutive passes required before a first capture, so no image was ever taken.

For a KNOWN person that outcome is fine: their profile already exists, and
"seen at 15:04" is useful on its own. For an UNKNOWN person it is a dead end —
the only thing that makes an unknown sighting worth keeping is the ability to
look at it and say who it is, and that needs a picture. Without one there is no
image to review, no encoding to cluster, and no route to a profile.

The gate still exists, because it is what stopped false positives filling the
gallery. It is simply lower for unknowns, who have no second chance.
"""

import pytest

from backend.core.capture_policy import CapturePolicy, CaptureSettings, MODE_SYSTEM_DEFAULT


def _face(name="Unknown", box=(100, 200, 180, 120), confidence=0.0):
    top, right, bottom, left = box
    return {
        "name": name,
        "confidence": confidence,
        "location": {"top": top, "right": right, "bottom": bottom, "left": left},
    }


def _evaluate(policy, face, **kw):
    return policy.evaluate(face, camera_id="cam1", mode=MODE_SYSTEM_DEFAULT, **kw)


def test_an_unknown_face_is_captured_on_first_sighting():
    """
    The fix. An unknown gets a picture immediately, so it can be identified.

    Previously it took three consecutive passes, which an unknown tracked only
    by box overlap frequently never accumulated — 50 sightings over a week
    produced not one image.
    """
    policy = CapturePolicy(CaptureSettings())
    decision = _evaluate(policy, _face())
    assert decision.capture is True, (
        f"an unknown must be photographed on first sighting; got: {decision.reason}"
    )


def test_a_known_face_still_has_to_persist():
    """
    The false-positive filter is unchanged for people who already have a profile.

    A known name is tracked by name rather than by position, so it accumulates
    passes reliably, and a missed capture costs nothing — the profile exists.
    """
    policy = CapturePolicy(CaptureSettings())
    decision = _evaluate(policy, _face(name="Mikel"), person_confirmed=True)
    assert decision.capture is False
    assert "passes" in decision.reason


def test_a_known_face_is_captured_once_it_persists():
    """The gate delays a known capture, it does not prevent it."""
    policy = CapturePolicy(CaptureSettings())
    face = _face(name="Mikel")
    for _ in range(CaptureSettings().required_consecutive_passes):
        decision = _evaluate(policy, face, person_confirmed=True)
    assert decision.capture is True


def test_an_unknown_sighting_always_carries_a_capture():
    """
    The invariant behind the report: an unknown sighting must never be recorded
    with nothing attached to it. A row with no image, no encoding and no cluster
    tells the operator only that something face-shaped appeared, which they can
    neither assign nor dismiss.
    """
    policy = CapturePolicy(CaptureSettings())
    for i in range(5):
        # Move the box each time, as a real subject would, which is exactly what
        # used to reset the track and prevent the capture.
        decision = _evaluate(policy, _face(box=(100 + i * 40, 200, 180, 120 + i * 40)))
        if decision.record_sighting:
            assert decision.capture is True, (
                "an unknown sighting was recorded with no capture, so it cannot "
                f"be acted on: {decision.reason}"
            )


def test_the_unknown_threshold_is_configurable():
    """An installation plagued by false positives can raise the bar again."""
    policy = CapturePolicy(CaptureSettings(unknown_required_passes=3))
    assert _evaluate(policy, _face()).capture is False
