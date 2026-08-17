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
from datetime import date
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

    Holds only in-memory state. A restart begins counting passes again, which
    costs at most one extra confirmation delay and avoids any persistence
    concern.
    """

    def __init__(self, settings: Optional[CaptureSettings] = None):
        self.settings = settings or CaptureSettings()
        self._tracks: Dict[str, _Track] = {}
        self._last_capture: Dict[str, float] = {}
        self._last_sighting: Dict[str, float] = {}
        self._last_capture_day: Dict[str, date] = {}

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
        if known and self._captured_recently(name, camera_id, now):
            return CaptureDecision(False, sighting,
                                   "already captured for this person today")

        if track.consecutive < self.settings.required_consecutive_passes:
            return CaptureDecision(
                False, sighting,
                f"seen {track.consecutive} of "
                f"{self.settings.required_consecutive_passes} passes",
            )

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

    def _should_record_sighting(self, name: str, camera_id: str, now: float) -> bool:
        scope = self._scope(name, camera_id)
        last = self._last_sighting.get(scope)
        if last is not None and now - last < self.settings.sighting_interval_seconds:
            return False
        self._last_sighting[scope] = now
        return True
