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


def _confirm(policy, f, now=0.0, passes=None, camera=CAMERA, **kwargs):
    """Run the passes needed for a face to become eligible, returning the last."""
    settings = policy.settings
    passes = settings.required_consecutive_passes if passes is None else passes
    decision = None
    for i in range(passes):
        decision = policy.evaluate(f, camera, now=now + i, **kwargs)
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
            policy.evaluate(f, CAMERA, now=i, cluster_face_count=25,
                            cluster_is_trained=True).record_sighting
            for i in range(policy.settings.required_consecutive_passes)
        ]
        sighted = any(sightings)
        decision = policy.evaluate(f, CAMERA, now=3, cluster_face_count=25,
                                   cluster_is_trained=True)

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

    def test_a_mature_but_untrained_cluster_keeps_collecting(self):
        """
        The trap this guards against.

        Size means the cluster has enough faces to become a profile. Trained
        means it actually did. Stopping on size alone strands a cluster that was
        never promoted: it would hold exactly the faces it has now, forever, and
        the promotion that would have made stopping correct is the very thing
        that never ran.
        """
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0,
                            cluster_face_count=701, cluster_is_trained=False)

        assert decision.capture is True
        assert "not been trained" in decision.reason

    def test_an_unknown_trained_state_is_treated_as_untrained(self):
        """
        Absence of evidence is not evidence of promotion. A caller that cannot
        say whether the cluster was trained gets the safe answer — keep
        collecting — rather than a silent permanent stop.
        """
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0,
                            cluster_face_count=701, cluster_is_trained=None)

        assert decision.capture is True

    def test_a_trained_cluster_still_records_the_sighting(self):
        """Suppressing the likeness must never suppress the record of presence."""
        policy = CapturePolicy()

        f = face("Unknown")
        # A list, not any(): any() short-circuits on the first sighting and the
        # remaining passes never run. The 60s throttle means only the first pass
        # reports one, so the last decision alone would say False.
        sightings = [
            policy.evaluate(f, CAMERA, now=i, cluster_face_count=701,
                            cluster_is_trained=True).record_sighting
            for i in range(policy.settings.required_consecutive_passes)
        ]
        decision = policy.evaluate(f, CAMERA, now=3, cluster_face_count=701,
                                   cluster_is_trained=True)

        assert decision.capture is False
        assert any(sightings) is True

    def test_the_threshold_is_configurable(self):
        """
        A cluster of 10 counts as mature once the threshold says so. The first
        arrival now spends the hard-case allowance, so the maturity rule shows
        itself on the second — before this change it answered immediately.
        """
        policy = CapturePolicy(CaptureSettings(cluster_maturity=10))

        f = face("Unknown")
        _arrive(policy, f, now=0, cluster_face_count=10, cluster_is_trained=True)
        second = policy.evaluate(f, CAMERA, cluster_face_count=10,
                                 cluster_is_trained=True, now=5)

        assert second.capture is False
        assert "already holds 10 faces" in second.reason



def _arrive(policy, f, camera=CAMERA, now=0.0, **kwargs):
    """
    One arrival, after the persistence gate has been cleared.

    _confirm returns the LAST of its passes, which is right for a rule that
    suppresses on every pass but wrong for a once-per-day budget: the first pass
    spends the allowance and the rest report it as already spent.
    """
    for i in range(policy.settings.required_consecutive_passes - 1):
        policy.evaluate(f, camera, now=now + i, **kwargs)
    return policy.evaluate(f, camera,
                           now=now + policy.settings.required_consecutive_passes - 1,
                           **kwargs)


class TestUnrecognisedFacesInTrainedClusters:
    """
    A face inside a trained cluster that recognition still could not name.

    Refusing it was the remaining trap: a recognition failure on a trained
    cluster is evidence the training does not yet cover this angle or this
    light, so the moment more material would help was the moment collection
    stopped. It earns a capture on its own slow budget instead.
    """

    def test_an_unrecognised_face_in_a_trained_cluster_is_captured(self):
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0,
                            cluster_face_count=701, cluster_is_trained=True,
                            cluster_id=1)

        assert decision.capture is True
        assert "unrecognised face in a trained cluster" in decision.reason

    def test_it_is_budgeted_not_unlimited(self):
        policy = CapturePolicy()

        f = face("Unknown")
        first = _arrive(policy, f, now=0, cluster_face_count=701,
                        cluster_is_trained=True, cluster_id=1)
        # Within the sticky window, so the track survives and the budget — not
        # the persistence gate — is what answers.
        second = policy.evaluate(f, CAMERA, cluster_face_count=701,
                                 cluster_is_trained=True, cluster_id=1, now=10)

        assert first.capture is True
        assert second.capture is False
        assert "already holds" in second.reason

    def test_the_budget_renews_the_next_day(self):
        policy = CapturePolicy()

        f = face("Unknown")
        _arrive(policy, f, now=0, cluster_face_count=701,
                cluster_is_trained=True, cluster_id=1)
        later = _arrive(policy, f, now=86_401, cluster_face_count=701,
                        cluster_is_trained=True, cluster_id=1)

        assert later.capture is True

    def test_each_cluster_has_its_own_budget(self):
        """
        Every unrecognised face arrives called "Unknown", so a name-keyed budget
        would let the first cluster consume the allowance of all of them.
        """
        policy = CapturePolicy()

        f = face("Unknown")
        _arrive(policy, f, now=0, cluster_face_count=701,
                cluster_is_trained=True, cluster_id=1)
        other = policy.evaluate(f, CAMERA, cluster_face_count=40,
                                cluster_is_trained=True, cluster_id=2, now=10)

        assert other.capture is True

    def test_each_camera_has_its_own_budget(self):
        policy = CapturePolicy()

        f = face("Unknown")
        _arrive(policy, f, now=0, cluster_face_count=701,
                cluster_is_trained=True, cluster_id=1)
        elsewhere = policy.evaluate(f, "back_door",
                                    cluster_face_count=701,
                                    cluster_is_trained=True, cluster_id=1, now=10)

        assert elsewhere.capture is True

    def test_the_hard_case_budget_does_not_consume_the_refresh_budget(self):
        """The two allowances are separate; one must not exhaust the other."""
        policy = CapturePolicy()

        _arrive(policy, face("Unknown"), now=0, cluster_face_count=701,
                cluster_is_trained=True, cluster_id=1)
        named = _confirm(policy, face("unknown1", top=300), now=10)

        assert named.capture is True
        assert "refreshing an enrolled likeness" in named.reason

    def test_an_untrained_cluster_still_takes_the_untrained_path(self):
        policy = CapturePolicy()

        decision = _confirm(policy, face("Unknown"), now=0,
                            cluster_face_count=701, cluster_is_trained=False,
                            cluster_id=1)

        assert decision.capture is True
        assert "not been trained" in decision.reason

    def test_a_suppressed_hard_case_still_records_the_sighting(self):
        policy = CapturePolicy()

        f = face("Unknown")
        sightings = [
            policy.evaluate(f, CAMERA, now=i, cluster_face_count=701,
                            cluster_is_trained=True, cluster_id=1).record_sighting
            for i in range(policy.settings.required_consecutive_passes)
        ]
        assert any(sightings) is True



class TestSurvivingARestart:
    """
    The policy holds its state in memory, so quitting and reopening forgot that
    someone had already been captured today. On a server that is rare. In the
    desktop application, where restarting is a user action, "once a day" became
    "once a launch".

    Nothing new is stored to fix it: every capture already leaves a detection
    row, so the timestamp is read back rather than persisted again.
    """

    def test_a_seeded_capture_suppresses_the_next_one(self):
        policy = CapturePolicy()

        policy.seed_last_capture("Mikel", CAMERA, when=0.0)
        decision = _confirm(policy, face("Mikel"), now=60)

        assert decision.capture is False
        assert "already captured" in decision.reason

    def test_a_seed_older_than_the_interval_does_not_suppress(self):
        policy = CapturePolicy()

        policy.seed_last_capture("Mikel", CAMERA, when=0.0)
        decision = _confirm(policy, face("Mikel"), now=86_401)

        assert decision.capture is True

    def test_seeding_is_per_camera(self):
        policy = CapturePolicy()

        policy.seed_last_capture("Mikel", CAMERA, when=0.0)
        decision = _confirm(policy, face("Mikel"), now=60, camera="back_door")

        assert decision.capture is True

    def test_a_seed_never_moves_a_capture_backwards(self):
        """
        Seeding happens on first sighting after startup, which can be after a
        capture has already been made. A stale timestamp must not displace a
        newer one and re-open the daily allowance.
        """
        policy = CapturePolicy()

        recent = _confirm(policy, face("Mikel"), now=1000)
        assert recent.capture is True

        policy.seed_last_capture("Mikel", CAMERA, when=0.0)   # much older
        again = policy.evaluate(face("Mikel"), CAMERA, now=1010)

        assert again.capture is False


def test_the_dead_calendar_day_map_is_gone():
    """
    _last_capture_day was declared and never read anywhere in backend/ or
    tests/, left over from a calendar-day design that the rolling 24-hour
    interval replaced. A name that looks like policy and does nothing is the
    same defect already recorded against ENABLE_OBJECT_DETECTION.
    """
    assert not hasattr(CapturePolicy(), "_last_capture_day")



class TestBorderlineMatchesAreKeptForReview:
    """
    A detection with no image cannot be reviewed, because nobody can identify a
    face they cannot see. The policy previously ignored confidence entirely, so
    a 0.41 match and a 0.95 match were throttled identically — which left the
    detections most likely to need human correction among the least likely to
    have a photo.
    """

    def test_a_borderline_match_is_captured(self):
        policy = CapturePolicy()

        f = face("Mikel")
        f["confidence"] = 0.44
        decision = _confirm(policy, f, now=0)

        assert decision.capture is True
        assert "low-confidence match" in decision.reason

    def test_it_beats_the_daily_throttle(self):
        """The whole point: already captured today must not silence a doubt."""
        policy = CapturePolicy()

        confident = face("Mikel")
        confident["confidence"] = 0.95
        assert _confirm(policy, confident, now=0).capture is True

        doubtful = face("Mikel")
        doubtful["confidence"] = 0.44
        later = policy.evaluate(doubtful, CAMERA, now=30)

        assert later.capture is True
        assert "review" in later.reason

    def test_a_confident_match_is_unaffected(self):
        policy = CapturePolicy()

        f = face("Mikel")
        f["confidence"] = 0.92
        first = _confirm(policy, f, now=0)
        second = policy.evaluate(f, CAMERA, now=30)

        assert first.capture is True
        assert "refreshing an enrolled likeness" in first.reason
        assert second.capture is False

    def test_the_review_budget_is_bounded(self):
        """Reviewable, not unlimited: a changed appearance is borderline on
        every single pass."""
        policy = CapturePolicy()

        f = face("Mikel")
        f["confidence"] = 0.44
        first = _arrive(policy, f, now=0)
        immediately_after = policy.evaluate(f, CAMERA, now=30)

        assert first.capture is True
        assert immediately_after.capture is False

    def test_the_budget_renews_within_the_hour(self):
        policy = CapturePolicy()

        f = face("Mikel")
        f["confidence"] = 0.44
        _arrive(policy, f, now=0)
        later = _arrive(policy, f, now=3601)

        assert later.capture is True

    def test_a_cluster_labelled_row_is_not_treated_as_borderline(self):
        """
        Detections renamed by clustering carry confidence exactly 0.0 — they were
        never recognised, so that zero is not a confidence and must not be read
        as one. 701 rows on the reporting install look like this.
        """
        policy = CapturePolicy()

        f = face("unknown1")
        f["confidence"] = 0.0
        decision = _confirm(policy, f, now=0)

        assert "low-confidence match" not in decision.reason

    def test_a_detection_without_confidence_is_not_treated_as_borderline(self):
        policy = CapturePolicy()

        decision = _confirm(policy, face("Mikel"), now=0)

        assert "low-confidence match" not in decision.reason

    def test_the_threshold_is_configurable(self):
        policy = CapturePolicy(CaptureSettings(review_confidence=0.9))

        f = face("Mikel")
        f["confidence"] = 0.85
        decision = _confirm(policy, f, now=0)

        assert decision.capture is True
        assert "low-confidence match" in decision.reason



class TestUnconfirmedIdentitiesKeepEverything:
    """
    A face nobody has vouched for is the work still outstanding, and it cannot be
    done from a detection that kept no picture.

    Keyed on confirmation rather than on the name, deliberately. The system
    auto-names a cluster and trains it, which used to make it LOOK named and
    switch it to the economical rules — turning retention off at exactly the
    moment the identification work began.
    """

    def test_an_unconfirmed_identity_is_always_captured(self):
        policy = CapturePolicy()

        f = face("unknown1")
        first = _arrive(policy, f, now=0, person_confirmed=False)
        immediately_after = policy.evaluate(f, CAMERA, now=5, person_confirmed=False)

        assert first.capture is True
        assert immediately_after.capture is True
        assert "unconfirmed identity" in immediately_after.reason

    def test_the_daily_throttle_does_not_apply_to_it(self):
        policy = CapturePolicy()

        f = face("unknown1")
        _arrive(policy, f, now=0, person_confirmed=False)
        # Within the motion-sticky window, so the track survives and the
        # throttle — not the persistence gate — is what answers.
        later = policy.evaluate(f, CAMERA, now=10, person_confirmed=False)

        assert later.capture is True
        assert "already captured" not in later.reason

    def test_a_mature_cluster_does_not_silence_it(self):
        """The maturity stop assumes the person is settled. Nobody has said so."""
        policy = CapturePolicy()

        decision = _arrive(policy, face("unknown1"), now=0,
                           cluster_face_count=701, cluster_is_trained=True,
                           cluster_id=1, person_confirmed=False)

        assert decision.capture is True
        assert "unconfirmed identity" in decision.reason

    def test_a_confirmed_person_follows_the_ordinary_rules(self):
        policy = CapturePolicy()

        f = face("Mikel")
        first = _arrive(policy, f, now=0, person_confirmed=True)
        again = policy.evaluate(f, CAMERA, now=60, person_confirmed=True)

        assert first.capture is True
        assert again.capture is False
        assert "already captured for this person today" in again.reason

    def test_an_unknown_confirmation_state_changes_nothing(self):
        """
        None means no person record — an installation from before the migration.
        It must behave exactly as it did, not silently start hoarding.
        """
        policy = CapturePolicy()

        f = face("Mikel")
        _arrive(policy, f, now=0, person_confirmed=None)
        again = policy.evaluate(f, CAMERA, now=60, person_confirmed=None)

        assert again.capture is False

    def test_it_still_earns_confirmation_first(self):
        """
        Retention is not a licence to capture a single bad frame. The persistence
        gate still applies — that is what keeps door edges and wall patches out.
        """
        policy = CapturePolicy()

        first_pass = policy.evaluate(face("unknown1"), CAMERA, now=0,
                                     person_confirmed=False)

        assert first_pass.capture is False
        assert "of 3 passes" in first_pass.reason


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


# ------------------------------------------------------------- motion gate

class TestMotionGate:
    """
    Recognition ran on a timer alone, so an empty room was detected, encoded and
    matched every couple of seconds around the clock. This is the largest single
    saving in the whole feature, and also the one with the most obvious way to
    get it wrong — gate too tightly and a person standing still stops being
    identified, which would break access control silently.
    """

    def _detector(self, **kwargs):
        from datetime import datetime, timedelta
        from backend.core.face_detection import FaceDetector

        detector = FaceDetector.__new__(FaceDetector)
        detector.enabled = True
        detector.last_detection_time = None
        detector.requires_motion = kwargs.get("requires_motion", True)
        detector.motion_sticky_seconds = kwargs.get("motion_sticky_seconds", 30.0)
        detector._last_motion_time = None
        detector._skipped_since_motion = 0
        detector.face_manager = type("M", (), {"is_available": lambda self: True})()
        return detector, datetime, timedelta

    def test_no_motion_means_no_recognition(self):
        detector, _dt, _td = self._detector()
        assert detector.should_process_frame() is False

    def test_motion_enables_recognition(self):
        detector, _dt, _td = self._detector()
        detector.note_motion(True)
        assert detector.should_process_frame() is True

    def test_a_stationary_person_is_still_recognised(self):
        """
        The important one. Someone waiting at a door stops generating motion but
        is exactly who the access rules need identified.
        """
        detector, datetime, timedelta = self._detector(motion_sticky_seconds=30)
        detector.note_motion(True)
        detector._last_motion_time = datetime.now() - timedelta(seconds=20)

        assert detector.should_process_frame() is True

    def test_recognition_stops_once_the_room_has_been_still(self):
        detector, datetime, timedelta = self._detector(motion_sticky_seconds=30)
        detector.note_motion(True)
        detector._last_motion_time = datetime.now() - timedelta(seconds=45)

        assert detector.should_process_frame() is False

    def test_the_gate_can_be_turned_off_per_camera(self):
        """A camera whose motion detection is unreliable must still recognise."""
        detector, _dt, _td = self._detector(requires_motion=False)
        assert detector.should_process_frame() is True

    def test_motion_is_recorded_even_when_recognition_is_skipped(self):
        """
        Motion has to be tracked on every frame. Recording it only on frames
        that already passed the cooldown would sample the window at the very
        rate it is meant to gate.
        """
        detector, _dt, _td = self._detector()
        detector.note_motion(False)
        assert detector._last_motion_time is None

        detector.note_motion(True)
        assert detector._last_motion_time is not None
