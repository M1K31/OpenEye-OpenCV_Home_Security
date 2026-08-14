# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for what a recognised face leaves behind.

The rule underneath all of these: suppressing a capture must never suppress the
act. Automation and notification are not this module's business, so what is
asserted here is that a suppressed face still produces a sighting, and that the
expensive parts — the snapshot and the encoding that feeds clustering and
training — are the only things withheld.

Time is injected everywhere rather than slept, so a "once a day" rule is a test
that runs in microseconds.
"""

import pytest

from backend.core.capture_policy import (
    MODE_ALL_FACES,
    MODE_SYSTEM_DEFAULT,
    CapturePolicy,
    CaptureSettings,
)

CAMERA = "front_door"


def face(name="Unknown", top=100, left=100, size=80):
    return {
        "name": name,
        "location": {"top": top, "left": left,
                     "bottom": top + size, "right": left + size},
    }


def _confirm(policy, f, now=0.0, passes=None, **kwargs):
    """Run the passes needed for a face to become eligible, returning the last."""
    settings = policy.settings
    passes = settings.required_consecutive_passes if passes is None else passes
    decision = None
    for i in range(passes):
        decision = policy.evaluate(f, CAMERA, now=now + i, **kwargs)
    return decision


# ------------------------------------------------------- persistence gate

class TestPersistence:
    def test_a_face_is_not_captured_on_first_sight(self):
        policy = CapturePolicy()
        decision = policy.evaluate(face("Unknown"), CAMERA, now=0)

        assert decision.capture is False
        assert "1 of 3 passes" in decision.reason

    def test_it_is_captured_once_it_persists(self):
        policy = CapturePolicy()
        decision = _confirm(policy, face("Unknown"))

        assert decision.capture is True

    def test_a_transient_detection_never_captures(self):
        """
        A door edge or patch of wall appears once and is gone. Most of the
        stored detections on existing installs are exactly this.
        """
        policy = CapturePolicy()

        for i in range(10):
            # Each appears somewhere unrelated, so nothing continues a track.
            decision = policy.evaluate(face("Unknown", top=i * 300, left=i * 300),
                                       CAMERA, now=i)
            assert decision.capture is False

    def test_a_gap_resets_the_count(self):
        policy = CapturePolicy()
        f = face("Unknown")

        policy.evaluate(f, CAMERA, now=0)
        policy.evaluate(f, CAMERA, now=1)
        # Long enough that this is a new visit, not a continuation.
        decision = policy.evaluate(f, CAMERA, now=1000)

        assert decision.capture is False

    def test_a_moving_person_stays_one_track(self):
        """Movement between passes must not look like a different face."""
        policy = CapturePolicy()

        policy.evaluate(face("Unknown", top=100, left=100), CAMERA, now=0)
        policy.evaluate(face("Unknown", top=110, left=115), CAMERA, now=2)
        decision = policy.evaluate(face("Unknown", top=125, left=130), CAMERA, now=4)

        assert decision.capture is True


# ------------------------------------------------------------ known people

class TestKnownPeople:
    def test_an_enrolled_person_is_captured_once_then_suppressed(self):
        policy = CapturePolicy()

        first = _confirm(policy, face("Mikel"), now=0)
        assert first.capture is True
        assert "refreshing" in first.reason

        later = policy.evaluate(face("Mikel"), CAMERA, now=60)
        assert later.capture is False
        assert "today" in later.reason

    def test_the_likeness_is_refreshed_the_next_day(self):
        """The point of capturing at all: the profile must stay current."""
        policy = CapturePolicy()

        _confirm(policy, face("Mikel"), now=0)
        tomorrow = 24 * 60 * 60 + 60
        decision = _confirm(policy, face("Mikel"), now=tomorrow)

        assert decision.capture is True

    def test_each_camera_captures_the_person_separately(self):
        """
        Per camera, deliberately: a different door means different lighting and
        angle, and where someone was seen matters as much as the likeness.
        """
        policy = CapturePolicy()

        assert _confirm(policy, face("Mikel"), now=0).capture is True

        # The person is already confirmed, so the other camera captures at once
        # and is then subject to its own daily limit.
        back = policy.evaluate(face("Mikel"), "back_door", now=10)
        assert back.capture is True
        assert policy.evaluate(face("Mikel"), "back_door", now=11).capture is False


# -------------------------------------------------------- clustered unknowns

class TestClusteredUnknowns:
    def test_a_mature_cluster_stops_collecting_likenesses(self):
        """
        The case that motivated the feature: someone recognisable enough to
        notify about, who should not keep growing a cluster or retraining.
        """
        policy = CapturePolicy()

        f = face("Unknown")
        # A list, not any(): any() short-circuits on the first sighting and the
        # remaining passes never run, so the face is never actually confirmed.
        sightings = [
            policy.evaluate(f, CAMERA, now=i, cluster_face_count=25).record_sighting
            for i in range(policy.settings.required_consecutive_passes)
        ]
        sighted = any(sightings)
        decision = policy.evaluate(f, CAMERA, now=3, cluster_face_count=25)

        assert decision.capture is False
        assert "25 faces" in decision.reason
        # The likeness is withheld; the record that they were here is not.
        assert sighted is True

    def test_an_immature_cluster_still_collects(self):
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0, cluster_face_count=5)

        assert decision.capture is True

    def test_a_face_matching_no_cluster_is_captured(self):
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0, cluster_face_count=None)

        assert decision.capture is True
        assert "new or under-represented" in decision.reason

    def test_the_threshold_is_configurable(self):
        policy = CapturePolicy(CaptureSettings(cluster_maturity=10))

        assert _confirm(policy, face("Unknown"), now=0, cluster_face_count=10).capture is False


# ------------------------------------------------------------- camera mode

class TestCameraMode:
    def test_all_faces_overrides_every_suppression(self):
        policy = CapturePolicy()

        first = policy.evaluate(face("Unknown"), CAMERA, mode=MODE_ALL_FACES, now=0)
        assert first.capture is True  # not even the persistence gate applies

        known = policy.evaluate(face("Mikel"), CAMERA, mode=MODE_ALL_FACES, now=1)
        assert known.capture is True

        clustered = policy.evaluate(face("Unknown"), CAMERA, mode=MODE_ALL_FACES,
                                    cluster_face_count=500, now=2)
        assert clustered.capture is True

    def test_the_default_mode_applies_the_policy(self):
        policy = CapturePolicy()
        assert policy.evaluate(face("Unknown"), CAMERA,
                               mode=MODE_SYSTEM_DEFAULT, now=0).capture is False


# ---------------------------------------------------------- sighting rows

class TestSightings:
    def test_a_suppressed_capture_still_records_a_sighting(self):
        """Where an unknown person was seen must survive the throttling."""
        policy = CapturePolicy()

        decision = policy.evaluate(face("Unknown"), CAMERA, now=0)

        assert decision.capture is False
        assert decision.record_sighting is True

    def test_sightings_are_throttled(self):
        policy = CapturePolicy()

        assert policy.evaluate(face("Mikel"), CAMERA, now=0).record_sighting is True
        assert policy.evaluate(face("Mikel"), CAMERA, now=30).record_sighting is False
        assert policy.evaluate(face("Mikel"), CAMERA, now=61).record_sighting is True

    def test_different_people_are_throttled_separately(self):
        policy = CapturePolicy()

        assert policy.evaluate(face("Mikel"), CAMERA, now=0).record_sighting is True
        assert policy.evaluate(face("Yala"), CAMERA, now=1).record_sighting is True

    def test_ten_minutes_of_presence_produces_ten_rows(self):
        """The concrete trade that was agreed: 300 passes become 10 rows."""
        policy = CapturePolicy()
        f = face("Unknown")

        sightings = sum(
            1 for pass_index in range(300)
            if policy.evaluate(f, CAMERA, now=pass_index * 2).record_sighting
        )

        assert sightings == 10


# ------------------------------------------------------------ housekeeping

class TestHousekeeping:
    def test_tracks_do_not_accumulate_forever(self):
        policy = CapturePolicy()

        for i in range(200):
            policy.evaluate(face("Unknown", top=i * 200, left=i * 200),
                            CAMERA, now=i * 100)

        assert len(policy._tracks) < 10
