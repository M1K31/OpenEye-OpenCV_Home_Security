# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Work out what could be freed from a storage volume, and what must never be.

This module only *plans*. It reads the filesystem and the database and returns
a description of what would happen; it deletes nothing and re-encodes nothing.
Enforcement is a separate step that consumes a plan, so the preview a user reads
and the action taken are computed by the same code rather than by two
implementations that can disagree.

Planning first is not ceremony here. This feature removes the user's own
footage irreversibly, and the cleanup that already shipped shows how quietly a
protection rule can be wrong: `_run_snapshot_cleanup` preserves any file whose
name contains "face", while every detection snapshot is named
`face_<camera>_<timestamp>.jpg` — so it protects the entire directory by
accident and would delete nothing, while never looking at `faces_dir`, where
the material that actually matters lives.

Protections here are therefore by path and by database reference, never by
filename pattern:

  * profile galleries — faces_dir/<person>/*, the training material; losing it
    degrades recognition permanently and silently
  * cluster representative snapshots — what the Faces UI shows for an unnamed
    person; lose it and the cluster survives but can no longer be identified

Everything else is governed by the user's own settings, all of which default to
off. An install that never opens the storage settings behaves exactly as it
does today.
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

VIDEO_SUFFIXES = {".mp4", ".avi", ".mkv", ".mov", ".m4v"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

ACTION_DELETE = "delete"
ACTION_TRANSCODE = "transcode"

REASON_RETENTION = "past its retention age"
REASON_FLOOR = "reclaiming space to meet the free-space floor"
REASON_TRANSCODE = "old enough to re-encode smaller"

# What a re-encode is assumed to save, used for the preview only. The real
# saving is whatever ffmpeg actually produces; this is deliberately conservative
# so a preview does not promise more than the run delivers.
TRANSCODE_SAVING_RATIO = 0.6


@dataclass
class ThinningSettings:
    """
    Every control is off by default.

    This deletes footage the user cannot get back, so an install that has never
    been configured must behave exactly as it does now. `0` means "never" for
    each age, rather than "immediately", because a zero that meant "delete
    everything" would be a catastrophic misreading of an unset field.
    """

    enabled: bool = False
    image_retention_days: int = 0        # 0 = keep forever
    video_retention_days: int = 0        # 0 = keep forever
    transcode_enabled: bool = False
    transcode_after_days: int = 30
    free_space_floor_gb: float = 0.0     # 0 = no floor

    def any_action_configured(self) -> bool:
        return self.enabled and (
            self.image_retention_days > 0
            or self.video_retention_days > 0
            or self.free_space_floor_gb > 0
            or (self.transcode_enabled and self.transcode_after_days > 0)
        )


@dataclass
class PlannedItem:
    path: Path
    action: str
    reason: str
    size_bytes: int
    modified: datetime

    @property
    def bytes_freed(self) -> int:
        if self.action == ACTION_DELETE:
            return self.size_bytes
        return int(self.size_bytes * TRANSCODE_SAVING_RATIO)


@dataclass
class ThinningPlan:
    items: List[PlannedItem] = field(default_factory=list)
    protected_count: int = 0
    protected_bytes: int = 0
    scanned_count: int = 0
    scanned_bytes: int = 0
    free_bytes_before: int = 0
    floor_bytes: int = 0
    settings: Optional[ThinningSettings] = None
    notes: List[str] = field(default_factory=list)

    @property
    def bytes_freed(self) -> int:
        return sum(i.bytes_freed for i in self.items)

    @property
    def free_bytes_after(self) -> int:
        return self.free_bytes_before + self.bytes_freed

    @property
    def meets_floor(self) -> bool:
        return self.free_bytes_after >= self.floor_bytes

    def by_action(self, action: str) -> List[PlannedItem]:
        return [i for i in self.items if i.action == action]

    def describe(self) -> str:
        def gb(n: int) -> str:
            return f"{n / 1024 ** 3:.2f} GB"

        lines = [
            "Storage thinning — preview (nothing has been changed)",
            f"  scanned    {self.scanned_count:>6} files   {gb(self.scanned_bytes)}",
            f"  protected  {self.protected_count:>6} files   {gb(self.protected_bytes)}",
            f"  delete     {len(self.by_action(ACTION_DELETE)):>6} files",
            f"  transcode  {len(self.by_action(ACTION_TRANSCODE)):>6} files",
            f"  would free {gb(self.bytes_freed)}",
            f"  free space {gb(self.free_bytes_before)} -> {gb(self.free_bytes_after)}",
        ]
        if self.floor_bytes:
            met = "met" if self.meets_floor else "NOT MET"
            lines.append(f"  floor      {gb(self.floor_bytes)} ({met})")
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


def protected_paths(db=None) -> Set[Path]:
    """
    Everything thinning must never touch.

    Resolved to absolute paths so a comparison cannot be defeated by a relative
    path or a symlink, and derived from the database rather than from names.
    """
    from backend.core.paths import paths

    protected: Set[Path] = set()

    # 1. Profile galleries, wholesale. This is the training material.
    faces_dir = Path(paths.faces_dir)
    if faces_dir.exists():
        for item in faces_dir.rglob("*"):
            if item.is_file():
                protected.add(item.resolve())

    # 2. Cluster representative snapshots. Without one, a cluster survives but
    #    can no longer be recognised well enough to name — unrecoverable.
    if db is not None:
        try:
            from backend.database.models import FaceCluster

            snapshots_dir = Path(paths.snapshots_dir)
            for (rep,) in db.query(FaceCluster.representative_snapshot_path).all():
                if not rep:
                    continue

                # These are stored as the URL the frontend fetches — e.g.
                # "/data/snapshots/face_cam_2026....jpg" — not as a filesystem
                # path. That string IS absolute, so treating it as a path
                # silently resolved to a location that does not exist, and the
                # representative went unprotected: precisely the quiet
                # protection failure this module exists to avoid.
                #
                # So always protect the file of that name under the real
                # snapshots directory, and additionally the literal path when it
                # happens to be a genuine one.
                protected.add((snapshots_dir / Path(rep).name).resolve())

                literal = Path(rep)
                if literal.is_absolute() and literal.exists():
                    protected.add(literal.resolve())
        except Exception as exc:  # a planning failure must never delete more
            logger.error("Could not read cluster representatives: %s", exc)
            raise

    return protected


def _iter_media(directory: Path, suffixes: Set[str]) -> Iterable[Path]:
    if not directory.exists():
        return
    for item in directory.rglob("*"):
        if item.is_file() and item.suffix.lower() in suffixes:
            yield item


def build_plan(
    settings: ThinningSettings,
    db=None,
    now: Optional[datetime] = None,
    free_bytes: Optional[int] = None,
) -> ThinningPlan:
    """
    Describe what thinning would do. Reads only.

    Args:
        settings: the user's controls; if nothing is configured the plan is empty
        db: session used to resolve protected database references
        now: injected clock, for tests
        free_bytes: injected free space, for tests
    """
    from backend.core.paths import paths

    now = now or datetime.now()
    plan = ThinningPlan(settings=settings)
    plan.floor_bytes = int(settings.free_space_floor_gb * 1024 ** 3)

    data_root = Path(paths.data_dir)
    if free_bytes is None:
        try:
            free_bytes = shutil.disk_usage(data_root).free
        except OSError as exc:
            logger.warning("Could not read free space for %s: %s", data_root, exc)
            free_bytes = 0
    plan.free_bytes_before = free_bytes

    if not settings.enabled:
        plan.notes.append("thinning is disabled; nothing would be changed")
        return plan
    if not settings.any_action_configured():
        plan.notes.append("thinning is enabled but no ages or floor are set")
        return plan

    protected = protected_paths(db)

    # Count everything protected that actually exists, not merely the protected
    # files that happened to be scanned. Profile galleries are protected by not
    # being scanned at all, so counting only skips reported "protected: 0" on an
    # install holding 702 gallery images — the opposite of the reassurance
    # someone needs before switching deletion on.
    for item in protected:
        try:
            if item.is_file():
                plan.protected_count += 1
                plan.protected_bytes += item.stat().st_size
        except OSError:
            continue

    sources = (
        (Path(paths.recordings_dir), VIDEO_SUFFIXES, settings.video_retention_days),
        (Path(paths.snapshots_dir), IMAGE_SUFFIXES, settings.image_retention_days),
        (Path(paths.thumbnails_dir), IMAGE_SUFFIXES, settings.image_retention_days),
    )

    candidates: List[PlannedItem] = []
    for directory, suffixes, retention_days in sources:
        is_video = suffixes is VIDEO_SUFFIXES
        for item in _iter_media(directory, suffixes):
            try:
                stat = item.stat()
            except OSError:
                continue

            plan.scanned_count += 1
            plan.scanned_bytes += stat.st_size

            if item.resolve() in protected:
                continue  # already counted above

            modified = datetime.fromtimestamp(stat.st_mtime)
            age = now - modified

            if retention_days > 0 and age > timedelta(days=retention_days):
                plan.items.append(PlannedItem(
                    item, ACTION_DELETE, REASON_RETENTION, stat.st_size, modified))
                continue

            if (is_video and settings.transcode_enabled
                    and settings.transcode_after_days > 0
                    and age > timedelta(days=settings.transcode_after_days)):
                plan.items.append(PlannedItem(
                    item, ACTION_TRANSCODE, REASON_TRANSCODE, stat.st_size, modified))
                continue

            # Still within its retention age. Eligible for the floor only, and
            # only once everything past its age has already been counted.
            candidates.append(PlannedItem(
                item, ACTION_DELETE, REASON_FLOOR, stat.st_size, modified))

    # The floor is an emergency, applied after the ordinary rules and only as
    # far as it needs to go: oldest first, stopping the moment the floor is met.
    if plan.floor_bytes and plan.free_bytes_after < plan.floor_bytes:
        for item in sorted(candidates, key=lambda i: i.modified):
            if plan.free_bytes_after >= plan.floor_bytes:
                break
            plan.items.append(item)
        if not plan.meets_floor:
            plan.notes.append(
                "the free-space floor cannot be met even after thinning "
                "everything eligible; protected material is never removed")

    return plan


# --------------------------------------------------------------------- preview
#
# Deliberately the only entry point that exists so far. Enforcement consumes a
# plan built by build_plan(), so what a user previews and what a run performs
# are produced by the same code rather than by two implementations that can
# drift apart.

def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Preview what storage thinning would remove. Changes nothing.")
    parser.add_argument("--image-days", type=int, default=0,
                        help="delete images older than this (0 = keep forever)")
    parser.add_argument("--video-days", type=int, default=0,
                        help="delete recordings older than this (0 = keep forever)")
    parser.add_argument("--transcode-days", type=int, default=0,
                        help="re-encode recordings older than this (0 = never)")
    parser.add_argument("--floor-gb", type=float, default=0.0,
                        help="keep at least this many GB free (0 = no floor)")
    parser.add_argument("--verbose", action="store_true",
                        help="list every affected file")
    args = parser.parse_args()

    settings = ThinningSettings(
        enabled=True,
        image_retention_days=args.image_days,
        video_retention_days=args.video_days,
        transcode_enabled=args.transcode_days > 0,
        transcode_after_days=args.transcode_days,
        free_space_floor_gb=args.floor_gb,
    )

    try:
        from backend.database.utils import get_db_context
        with get_db_context() as db:
            plan = build_plan(settings, db=db)
    except Exception as exc:
        # Without the database the cluster representatives cannot be resolved,
        # and a plan that cannot see its protections must not be presented as
        # if it could.
        print(f"Could not build a plan: {exc}")
        return 1

    print(plan.describe())
    if args.verbose:
        for item in sorted(plan.items, key=lambda i: i.modified):
            print(f"  {item.action:<9} {item.size_bytes / 1024**2:>8.1f} MB  "
                  f"{item.modified:%Y-%m-%d}  {item.path.name}  ({item.reason})")
    print("\nThis was a preview. No files were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
