# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Moving detections between people, and moving their training data with them.

Assignment used to relabel detection records and nothing else. `bulk-reassign`
set `person_name`, cleared `cluster_id`, and never touched the gallery or the
encodings — so after assigning 300 detections to Mikel, the installation held:

    unknown1   400 detections   701 gallery images   701 encodings
    Mikel      300 detections   205 gallery images   205 encodings

The same face trained under two identities. New faces matched whichever was
nearer, so the placeholder kept collecting: a loop that does not resolve on its
own, and the reason "unknown1 still shows 701" was reported as a bug.

The fix is to treat a person's `detected/` gallery as DERIVED from their
detections, and rebuild it whenever those change. That works because every
detection records its own snapshot, so the gallery can be regenerated exactly —
without needing to trace existing gallery files back to detections, which their
filenames do not permit.

Both sides are rebuilt and retrained, because a cluster genuinely can hold two
people and separating them must leave both correct. `uploaded/` is never
touched: those photographs were chosen by a person, and no automatic process
gets to remove them.
"""

from __future__ import annotations

import logging
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReassignmentPlan:
    target: str = ""
    detections_moved: int = 0
    people_affected: List[str] = field(default_factory=list)
    gallery_before: Dict[str, int] = field(default_factory=dict)
    gallery_after: Dict[str, int] = field(default_factory=dict)
    dry_run: bool = True
    notes: List[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [
            f"Reassign {self.detections_moved} detection(s) to '{self.target}'"
            + ("  [preview]" if self.dry_run else ""),
            "",
            f"  {'person':<14} {'gallery before':>15} {'gallery after':>14}",
        ]
        for person in sorted(set(self.people_affected)):
            lines.append(
                f"  {person:<14} {self.gallery_before.get(person, 0):>15} "
                f"{self.gallery_after.get(person, 0):>14}")
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


def rebuild_gallery(person_name: str, db, dry_run: bool = True) -> int:
    """
    Regenerate a person's detected/ gallery from their own detections.

    Returns the number of images the gallery holds afterwards.

    Only detected/ is rebuilt. uploaded/ is authored by a person and is never
    touched by anything automatic — that separation is the whole reason phase 3
    exists, and without it this function would silently delete the best training
    images a person has.

    Images whose detection has since been deleted or thinned away do not come
    back. That is the intended meaning of derived: the gallery reflects the
    detections, not the other way round.
    """
    from backend.core.face_clustering import _resolve_snapshot_path
    from backend.core.gallery import detected_dir, ensure_layout, images_in
    from backend.database.models import FaceDetectionEvent

    ensure_layout(person_name)
    target_dir = detected_dir(person_name)

    rows = db.query(FaceDetectionEvent).filter(
        FaceDetectionEvent.person_name == person_name,
        FaceDetectionEvent.snapshot_path.isnot(None),
    ).all()

    wanted: Dict[str, str] = {}
    for row in rows:
        source = _resolve_snapshot_path(row.snapshot_path)
        if not source:
            continue
        # Same naming the exporter uses, so a rebuild is stable: running it
        # twice produces the same filenames rather than a second copy of
        # everything.
        stamp = row.detected_at.strftime("%Y%m%d_%H%M%S") if row.detected_at else "00000000_000000"
        camera = (row.camera_id or "camera").replace("/", "_")
        wanted[f"{stamp}_{camera}_{row.id}.jpg"] = source

    if dry_run:
        return len(wanted)

    existing = {p.name: p for p in images_in(target_dir)}

    for name, path in existing.items():
        if name not in wanted:
            try:
                path.unlink()
            except OSError as e:
                logger.warning("Could not remove stale gallery image %s: %s", path, e)

    import os
    for name, source in wanted.items():
        destination = target_dir / name
        if destination.exists():
            continue
        try:
            if os.path.exists(source):
                shutil.copy2(source, destination)
        except Exception as e:
            logger.warning("Could not copy %s into %s: %s", source, person_name, e)

    return len(images_in(target_dir))


def _retrain(people: List[str]) -> None:
    """Retrain the given people. Runs on a worker thread."""
    from backend.core.face_recognition import get_face_manager

    manager = get_face_manager()
    for person in people:
        try:
            result = manager.train_person(person)
            logger.info("Retrained '%s' after reassignment: %s", person, result)
        except Exception as e:
            logger.error("Retraining '%s' failed: %s", person, e)


def reassign(db, face_ids: List[int], target_name: str,
             dry_run: bool = True, retrain: bool = True) -> ReassignmentPlan:
    """
    Move detections to a person, and move their training data with them.

    Args:
        db: database session
        face_ids: detections to move
        target_name: the person they belong to
        dry_run: report what would happen and change nothing
        retrain: retrain affected people in the background afterwards
    """
    from backend.core.gallery import count_images
    from backend.database.models import FaceDetectionEvent, Person

    plan = ReassignmentPlan(target=target_name, dry_run=dry_run)
    target = (target_name or "").strip()
    if not target:
        plan.notes.append("no target person given")
        return plan

    rows = db.query(FaceDetectionEvent).filter(
        FaceDetectionEvent.id.in_(face_ids)).all()
    if not rows:
        plan.notes.append("no matching detections")
        return plan

    # Everyone losing detections, plus the one gaining them. Both sides need
    # rebuilding: a cluster can hold two people, and separating them must leave
    # both correct rather than only the one being named.
    affected = {r.person_name for r in rows if r.person_name and r.person_name != "Unknown"}
    affected.add(target)
    plan.people_affected = sorted(affected)
    plan.detections_moved = len(rows)
    plan.gallery_before = {p: count_images(p) for p in plan.people_affected}

    if dry_run:
        # Predict each gallery by counting what would remain or arrive.
        moving = {r.id for r in rows}
        for person in plan.people_affected:
            if person == target:
                keeps = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.person_name == person,
                    FaceDetectionEvent.snapshot_path.isnot(None)).count()
                arriving = sum(1 for r in rows if r.snapshot_path)
                plan.gallery_after[person] = keeps + arriving
            else:
                remaining = db.query(FaceDetectionEvent).filter(
                    FaceDetectionEvent.person_name == person,
                    FaceDetectionEvent.snapshot_path.isnot(None),
                    ~FaceDetectionEvent.id.in_(moving)).count()
                plan.gallery_after[person] = remaining
        plan.notes.append("uploaded/ galleries are never touched")
        return plan

    person_row = db.query(Person).filter(Person.name == target).first()
    if person_row is None:
        # Assigning detections to a name IS a person being created by a human,
        # so it is confirmed from the outset — which switches it off the
        # keep-everything retention rule.
        person_row = Person(name=target, origin="user",
                            confirmed_at=datetime.utcnow())
        db.add(person_row)
        db.flush()
        plan.notes.append(f"created person '{target}'")

    db.query(FaceDetectionEvent).filter(
        FaceDetectionEvent.id.in_(face_ids)
    ).update(
        {
            "person_name": target,
            "person_id": person_row.id,
            # Cleared deliberately: this detection is no longer evidence about
            # whatever group it was in. Clustering will place it again on its
            # own merits, and can no longer rename it — a placeholder may not
            # overwrite a name a person chose.
            "cluster_id": None,
        },
        synchronize_session=False,
    )
    db.commit()

    for person in plan.people_affected:
        plan.gallery_after[person] = rebuild_gallery(person, db, dry_run=False)

    plan.dry_run = False
    logger.info("Reassigned %s detection(s) to '%s'; rebuilt %s",
                plan.detections_moved, target, ", ".join(plan.people_affected))

    if retrain:
        # Background, because re-encoding several hundred images takes a minute
        # or two and the caller is a click. The records are already correct;
        # this only catches the recogniser up.
        thread = threading.Thread(target=_retrain, args=(plan.people_affected,),
                                  daemon=True)
        thread.start()
        plan.notes.append("retraining both sides in the background")

    return plan
