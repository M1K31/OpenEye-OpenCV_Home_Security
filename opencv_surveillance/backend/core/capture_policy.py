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
            return CaptureDecision(
                False, sighting,
                f"cluster already holds {cluster_face_count} faces",
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

    def _captured_recently(self, name: str, camera_id: str, now: float) -> bool:
        last = self._last_capture.get(self._scope(name, camera_id))
        if last is None:
            return False
        return now - last < self.settings.known_capture_interval_seconds

    def _note_capture(self, name: str, camera_id: str, now: float) -> None:
        self._last_capture[self._scope(name, camera_id)] = now

    def _should_record_sighting(self, name: str, camera_id: str, now: float) -> bool:
        scope = self._scope(name, camera_id)
        last = self._last_sighting.get(scope)
        if last is not None and now - last < self.settings.sighting_interval_seconds:
            return False
        self._last_sighting[scope] = now
        return True
