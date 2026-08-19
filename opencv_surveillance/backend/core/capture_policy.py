# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Deciding what to keep from a recognised face, without changing what it triggers.

Every recognised face used to produce a JPEG on disk and a database row carrying
a face encoding, and the same code path also fired the user's automation rules.
That coupling is the important part: throttling captures naively would have
throttled automations with them, so lights would stop changing and access would
stop being granted — quietly, because fewer captures looks like success.

So this module answers one narrow question — *should this face contribute a
likeness?* — and deliberately answers nothing about whether to act on it.
Recognition and automation run at full rate regardless of what is decided here.

What a likeness costs, and why suppressing one is worth it: a snapshot file, a
stored encoding, and a share of every future clustering and training run, since
that work scales with how many encodings exist. What a suppressed face still
produces: the automation, the notification, and a lightweight sighting row
recording who was seen, where, and when.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Capture modes, stored per camera.
MODE_SYSTEM_DEFAULT = "system_default"
MODE_ALL_FACES = "all_faces"

UNKNOWN_NAME = "Unknown"


@dataclass
class CaptureSettings:
    """Tunables, system-wide unless a camera overrides the mode."""

    # Consecutive detection passes a face must survive before its first capture.
    # Transient mis-detections — a door edge, a patch of wall — do not persist;
    # a person trivially does. This is the direct remedy for the false positives
    # that make up most of the stored detections on existing installs.
    required_consecutive_passes: int = 3

    # Once a cluster holds this many faces it has a usable profile, and further
    # likenesses buy nothing while still costing clustering and training time.
    cluster_maturity: int = 25

    # A person already enrolled needs an occasional fresh likeness so their
    # profile stays current, not one every couple of seconds.
    known_capture_interval_seconds: int = 24 * 60 * 60

    # Sighting rows are cheap and are what keeps the events page, per-person
    # history and unknown-person location tracking meaningful. Throttled, not
    # removed.
    sighting_interval_seconds: int = 60

    # How long after motion recognition keeps running. Sticky rather than
    # instantaneous so someone standing still at a door is still identified.
    motion_sticky_seconds: int = 30

    # A face inside a trained cluster that recognition still could not name gets
    # a capture on this budget. Same shape as the refresh interval, and separate
    # from it so neither allowance can exhaust the other — a subject the
    # recogniser keeps failing on is exactly who needs new material, and would
    # otherwise be competing with the people it recognises perfectly well.
    hard_case_interval_seconds: int = 24 * 60 * 60

    # Below this confidence a match is not trusted enough to act on without a
    # human looking, so it must leave an image behind for them to look AT.
    #
    # Recognition admits a match at distance <= 0.6, i.e. confidence >= 0.40, so
    # this covers the 0.40-0.55 band: matched, but not convincingly.
    review_confidence: float = 0.55

    # Borderline matches get their own budget, and a shorter one than the daily
    # refresh. A review queue needs enough examples to be worth opening, and a
    # person whose appearance has changed is borderline on every pass — one
    # image a day would take a week to become reviewable. Bounded at 24 per
    # person per camera per day.
    review_capture_interval_seconds: int = 60 * 60


@dataclass
class CaptureDecision:
    """Why a face was or was not captured. The reason is for logs and tests."""

    capture: bool
    record_sighting: bool
    reason: str


@dataclass
class _Track:
    """A face being followed across consecutive passes on one camera."""

    consecutive: int = 0
    last_seen: float = 0.0
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)


class CapturePolicy:
    """
    Per-camera capture bookkeeping.

    State is in memory, but not all of it is allowed to be forgotten. Pass
    counts are: they describe one continuous visit, and a visit does not survive
    a restart, so beginning again costs at most one extra confirmation.

    Capture times are different. Forgetting them turns "once a day" into "once a
    launch", which matters in the desktop application where restarting is a user
    action rather than a rare event. They are seeded back from the detections
    table on first use — see seed_last_capture — so nothing new is stored and the
    history that already exists is simply read.
    """

    def __init__(self, settings: Optional[CaptureSettings] = None):
        self.settings = settings or CaptureSettings()
        self._tracks: Dict[str, _Track] = {}
        self._last_capture: Dict[str, float] = {}
        self._last_sighting: Dict[str, float] = {}

    # ---------------------------------------------------------------- tracking

    @staticmethod
    def _overlaps(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> bool:
        """
        Whether two face boxes are plausibly the same face one pass apart.

        Generous on purpose: a person walking moves noticeably between passes,
        and treating that as a new face would reset the confirmation count and
        mean real people were never captured at all.
        """
        at, ar, ab, al = a
        bt, br, bb, bl = b
        if ar <= bl or br <= al or ab <= bt or bb <= at:
            return False

        overlap = (min(ar, br) - max(al, bl)) * (min(ab, bb) - max(at, bt))
        smaller = min(max(1, (ar - al) * (ab - at)), max(1, (br - bl) * (bb - bt)))
        return overlap / smaller >= 0.2

    def _track_key(self, face: dict, box: Tuple[int, int, int, int], now: float) -> str:
        """
        Find the track this face continues, or start a new one.

        A named person is tracked by name, which survives large movements
        between passes. An unknown face has only its position to go on.
        """
        name = (face.get("name") or UNKNOWN_NAME).strip()
        if name != UNKNOWN_NAME:
            return f"name:{name}"

        gap = self.settings.motion_sticky_seconds
        for key, track in self._tracks.items():
            if not key.startswith("box:"):
                continue
            if now - track.last_seen > gap:
                continue
            if self._overlaps(track.box, box):
                return key

        return f"box:{now:.3f}"

    def _prune(self, now: float) -> None:
        """Forget tracks nothing has continued, so the dictionary cannot grow."""
        stale = self.settings.motion_sticky_seconds * 2
        for key in [k for k, t in self._tracks.items() if now - t.last_seen > stale]:
            del self._tracks[key]

    # ---------------------------------------------------------------- decision

    def evaluate(
        self,
        face: dict,
        camera_id: str,
        mode: str = MODE_SYSTEM_DEFAULT,
        cluster_face_count: Optional[int] = None,
        cluster_is_trained: Optional[bool] = None,
        cluster_id: Optional[int] = None,
        person_is_known: Optional[bool] = None,
        person_confirmed: Optional[bool] = None,
        now: Optional[float] = None,
    ) -> CaptureDecision:
        """
        Decide what this recognised face should leave behind.

        Never decides whether to act on it. Automation and notification have
        already run, or will run, independently of anything returned here.

        Args:
            face: the detection, as produced by recognition
            camera_id: which camera saw it
            mode: this camera's capture mode
            cluster_face_count: size of the cluster this face matches, if any
            cluster_is_trained: whether that cluster has been promoted into a
                trained profile — None when unknown, which is treated as
                untrained
            cluster_id: which cluster this face matched, used to budget hard
                cases per cluster rather than per the literal name 'Unknown'
            person_is_known: whether the name corresponds to an enrolled person
            person_confirmed: whether a human has vouched for this identity. An
                unconfirmed, system-named person keeps every likeness, because
                those are the faces somebody still has to identify — and a face
                cannot be identified from a record that kept no picture of it.
            now: injected clock, for tests
        """
        now = time.time() if now is None else now
        name = (face.get("name") or UNKNOWN_NAME).strip() or UNKNOWN_NAME
        location = face.get("location") or {}
        box = (
            int(location.get("top", 0)), int(location.get("right", 0)),
            int(location.get("bottom", 0)), int(location.get("left", 0)),
        )

        self._prune(now)

        key = self._track_key(face, box, now)
        track = self._tracks.get(key)
        if track is None or now - track.last_seen > self.settings.motion_sticky_seconds:
            track = _Track()
            self._tracks[key] = track
        track.consecutive += 1
        track.last_seen = now
        track.box = box

        sighting = self._should_record_sighting(name, camera_id, now)

        # An explicit override captures everything, including unconfirmed faces.
        if mode == MODE_ALL_FACES:
            self._note_capture(name, camera_id, now)
            return CaptureDecision(True, sighting, "camera set to capture all faces")

        known = person_is_known if person_is_known is not None else name != UNKNOWN_NAME

        # Checked before the persistence gate on purpose. Someone enrolled whose
        # likeness is already current needs no capture at all, so making them
        # re-earn confirmation on every visit would be wasted bookkeeping and
        # would report a misleading reason — "unconfirmed" rather than the truth,
        # which is that we simply have a recent enough photograph of them.
        # A match the recogniser is unsure about needs a human to look, and a
        # human cannot identify a face they cannot see. The policy did not read
        # confidence at all: a 0.41 match and a 0.95 match were throttled
        # identically, so the detections most likely to need correction were
        # among the least likely to have a photo.
        #
        # Suppression exists to avoid storing the hundredth identical likeness of
        # someone already well recorded. A face the recogniser doubts is the
        # opposite case, so the daily throttle should not silence it.
        confidence = face.get("confidence")
        borderline = (
            known and confidence is not None
            and 0 < confidence < self.settings.review_confidence
        )

        # Neither a doubtful match nor an unconfirmed identity is silenced by
        # "already captured today". Both describe work still outstanding, and
        # the daily throttle exists for people whose likeness is already
        # settled.
        if (known and not borderline and person_confirmed is not False
                and self._captured_recently(name, camera_id, now)):
            return CaptureDecision(False, sighting,
                                   "already captured for this person today")

        if track.consecutive < self.settings.required_consecutive_passes:
            return CaptureDecision(
                False, sighting,
                f"seen {track.consecutive} of "
                f"{self.settings.required_consecutive_passes} passes",
            )

        # An identity nobody has vouched for keeps everything.
        #
        # The suppression rules below all assume the person is settled: their
        # likeness is current, their cluster is well represented, there is
        # nothing left to decide. None of that is true of a face the system
        # named itself and a human has not yet confirmed — that is precisely the
        # work still outstanding, and it cannot be done from a detection with no
        # picture attached.
        #
        # Deliberately keyed on confirmation rather than on the name. The system
        # auto-names a cluster and trains it, which used to make it LOOK named
        # and silently switch it to the economical rules — turning off retention
        # exactly when the identification work began.
        if person_confirmed is False:
            self._note_capture(name, camera_id, now)
            return CaptureDecision(
                True, sighting, "unconfirmed identity — keeping every likeness")

        if borderline:
            # After the persistence gate on purpose. A doubtful match should not
            # bypass confirmation as well as the throttle — that would let a
            # single bad frame put an image in the review queue.
            scope = self._review_name(name)
            if not self._captured_recently(
                    scope, camera_id, now,
                    interval=self.settings.review_capture_interval_seconds):
                self._note_capture(scope, camera_id, now)
                self._note_capture(name, camera_id, now)
                return CaptureDecision(
                    True, sighting,
                    f"low-confidence match ({confidence:.0%}) — kept for review")
            if self._captured_recently(name, camera_id, now):
                return CaptureDecision(False, sighting,
                                       "already captured for this person today")

        if known:
            self._note_capture(name, camera_id, now)
            return CaptureDecision(True, sighting, "refreshing an enrolled likeness")

        if cluster_face_count is not None and cluster_face_count >= self.settings.cluster_maturity:
            # Size alone is not a reason to stop. Stopping is only correct once
            # the cluster has been promoted into a trained profile, because from
            # then on the person is recognised by name and refreshed on the
            # normal per-day-per-camera schedule — there is a route by which
            # their likeness stays current.
            #
            # An untrained cluster has no such route. If collection stopped here
            # it would hold exactly the faces it has now, forever, and never
            # become a profile: promotion is what training does, and training is
            # what has not happened. So keep collecting, and say so — a mature
            # cluster that is still untrained means clustering or training is
            # not running, which is worth knowing.
            if cluster_is_trained:
                # A trained cluster whose face recognition could not name is not
                # a stranger. It is a subject the recogniser is failing on, in
                # this light or at this angle — and that failure is an argument
                # FOR collecting, not against it. Refusing here would withhold
                # the material that would fix the very thing going wrong.
                #
                # Budgeted per cluster, not per name: every unrecognised face
                # arrives called "Unknown", so a name-keyed budget would let one
                # cluster consume the allowance of all of them.
                #
                # Safe only because the gallery is bounded — without the dedupe
                # and cap, a permanently unrecognisable subject could grow it
                # without limit through this branch.
                scope = self._hard_case_name(cluster_id)
                if not self._captured_recently(
                        scope, camera_id, now,
                        interval=self.settings.hard_case_interval_seconds):
                    self._note_capture(scope, camera_id, now)
                    return CaptureDecision(
                        True, sighting,
                        f"unrecognised face in a trained cluster of "
                        f"{cluster_face_count}",
                    )
                return CaptureDecision(
                    False, sighting,
                    f"cluster already holds {cluster_face_count} faces",
                )
            self._note_capture(name, camera_id, now)
            return CaptureDecision(
                True, sighting,
                f"cluster holds {cluster_face_count} faces but has not been "
                f"trained into a profile yet",
            )

        self._note_capture(name, camera_id, now)
        return CaptureDecision(True, sighting, "new or under-represented face")

    # ----------------------------------------------------------------- helpers

    @staticmethod
    def _scope(name: str, camera_id: str) -> str:
        """
        Capture limits are per person *per camera*.

        A person arriving at a different door should still leave a likeness
        there — different cameras see different lighting and angles, and the
        record of where they were seen matters as much as the likeness itself.
        """
        return f"{name}@{camera_id}"

    @staticmethod
    def _hard_case_name(cluster_id: Optional[int]) -> str:
        """
        A budget scope for faces a trained cluster failed to recognise.

        Keyed on the cluster rather than the name, because every such face
        arrives called "Unknown" and a name-keyed budget would be shared by all
        of them at once.
        """
        return f"\x00hardcase:{cluster_id if cluster_id is not None else 'none'}"

    @staticmethod
    def _review_name(name: str) -> str:
        """A budget scope for borderline matches, separate from the refresh."""
        return f"\x00review:{name}"

    def _captured_recently(self, name: str, camera_id: str, now: float,
                           interval: Optional[float] = None) -> bool:
        last = self._last_capture.get(self._scope(name, camera_id))
        if last is None:
            return False
        if interval is None:
            interval = self.settings.known_capture_interval_seconds
        return now - last < interval

    def _note_capture(self, name: str, camera_id: str, now: float) -> None:
        self._last_capture[self._scope(name, camera_id)] = now

    def seed_last_capture(self, name: str, camera_id: str, when: float) -> None:
        """
        Tell the policy about a capture it did not make.

        All of this policy's state lives in memory, so a restart forgot that
        someone had already been captured today and the first sighting after
        startup captured again. On a server that is rare; in the desktop
        application, where quitting and reopening is a user action, "once a day"
        quietly became "once a launch".

        The detections table already records every capture, so nothing new needs
        storing — the history is simply read back on first use. Only ever moves
        the timestamp forward, so a stale seed cannot displace a capture made
        since.
        """
        scope = self._scope(name, camera_id)
        # Compared against None, not against 0.0. Using zero as the "nothing
        # recorded" default makes it indistinguishable from a real timestamp of
        # zero, and — more to the point — means a seed is silently dropped
        # whenever nothing has been recorded yet, which is precisely the case
        # seeding exists to handle.
        existing = self._last_capture.get(scope)
        if existing is None or when > existing:
            self._last_capture[scope] = when

    def _should_record_sighting(self, name: str, camera_id: str, now: float) -> bool:
        scope = self._scope(name, camera_id)
        last = self._last_sighting.get(scope)
        if last is not None and now - last < self.settings.sighting_interval_seconds:
            return False
        self._last_sighting[scope] = now
        return True
