# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Turning identified detections into something the recogniser can actually use.

A person in this system is only recognisable if two things exist: photos in
their gallery folder, and encodings derived from those photos. Several flows
used to produce a person with neither, or with photos but no encodings, leaving
a profile that looks populated in the UI while being permanently unrecognisable.

This module holds the one implementation of "make this person recognisable",
shared by the reassignment endpoints and by the startup repair, so the two can
never drift apart.
"""

import logging
import os
import re
import shutil
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.database import models

logger = logging.getLogger(__name__)


# Cluster labels the system generates for people it has not identified:
# "unknown", "unknown1", "unknown8". Training on these would teach the
# recogniser to recognise "not recognised", so every flow here skips them.
_AUTO_UNKNOWN_PATTERN = re.compile(r"^unknown\d*$", re.IGNORECASE)


def is_real_person_name(name: Optional[str]) -> bool:
    """True if `name` identifies an actual person rather than a placeholder."""
    clean = (name or "").strip()
    if not clean:
        return False
    return not _AUTO_UNKNOWN_PATTERN.match(clean)


def enrol_detections(db: Session, face_ids: List[int], person_name: str) -> dict:
    """
    Copy the given detections into a person's gallery and retrain them.

    Reassignment used to rewrite `person_name` on the detection rows and stop
    there. No image was copied into the person's folder and no encoding was
    produced, so building a person out of their detections created a profile
    that looked populated — the UI listed its detections — while holding zero
    photos and zero encodings. Such a person can never be recognised: the next
    time they appear they are detected as unknown and clustered as a stranger
    again.

    Assigning a face to someone is the user saying "this is them", so it should
    also be what teaches the system to recognise them.

    Reuses the cluster export path's snapshot resolver and per-person trainer
    rather than reimplementing either. Deliberately non-fatal: callers have
    usually already committed the reassignment, and failing to copy or train
    must not undo it.
    """
    clean = (person_name or "").strip()
    if not is_real_person_name(clean):
        return {"enrolled": 0, "trained": False, "reason": "not a real person"}

    copied = skipped = 0
    try:
        from backend.core.paths import paths
        from backend.core.face_clustering import _resolve_snapshot_path

        person_path = paths.faces_dir / clean
        person_path.mkdir(parents=True, exist_ok=True)
        from backend.core.gallery import iter_images
        existing = {f.name for f in iter_images(person_name)}

        faces = db.query(models.FaceDetectionEvent).filter(
            models.FaceDetectionEvent.id.in_(face_ids)
        ).all()

        for idx, face in enumerate(faces):
            src = _resolve_snapshot_path(face.snapshot_path)
            if not src or not os.path.exists(src):
                continue
            try:
                stamp = face.detected_at.strftime("%Y%m%d_%H%M%S")
                cam = (face.camera_id or "cam").replace("/", "_")
                dest_name = f"{stamp}_{cam}_{idx}.jpg"
                if dest_name in existing:
                    skipped += 1
                    continue
                shutil.copy2(src, person_path / dest_name)
                existing.add(dest_name)
                copied += 1
            except Exception as e:
                logger.warning("Could not copy %s into %s: %s",
                               face.snapshot_path, clean, e)
    except Exception as e:
        logger.warning("Enrolment copy step failed for '%s': %s", clean, e)
        return {"enrolled": 0, "trained": False, "reason": str(e)}

    if not copied:
        return {"enrolled": 0, "skipped": skipped, "trained": False,
                "reason": "no new snapshots to enrol"}

    return _train(clean, copied, skipped)


def _train(person_name: str, copied: int = 0, skipped: int = 0) -> dict:
    """Retrain one person and report on the encodings, not on the call."""
    try:
        from backend.core.face_recognition import get_face_manager
        result = get_face_manager().train_person(person_name)
        # train_person reports success even when it encoded nothing, which is
        # the case that matters here: photos on disk but no encoding produced
        # leaves the person just as unrecognisable as before.
        encodings = int(result.get("encodings_added") or 0)
        logger.info("Enrolled %s image(s) for '%s'; %s encoding(s)",
                    copied, person_name, encodings)
        return {"enrolled": copied, "skipped": skipped,
                "trained": encodings > 0, "encodings": encodings}
    except Exception as e:
        # Photos are on disk either way; training can be retried.
        logger.warning("Training failed for '%s': %s", person_name, e)
        return {"enrolled": copied, "skipped": skipped,
                "trained": False, "encodings": 0, "reason": str(e)}


def find_people_missing_encodings(db: Session) -> List[str]:
    """
    Names that the system treats as identified people but cannot recognise.

    Two sources, because a broken person can be missing either half. A person
    may have a gallery folder whose photos never encoded, or may exist only as
    detections attributed to them with no gallery at all.
    """
    from backend.core.paths import paths
    from backend.core.face_recognition import get_face_manager

    encoded = {n for n in get_face_manager().known_face_names}

    candidates = set()

    faces_dir = paths.faces_dir
    if faces_dir.exists():
        for entry in faces_dir.iterdir():
            if entry.is_dir() and not entry.name.startswith("."):
                candidates.add(entry.name)

    rows = db.query(models.FaceDetectionEvent.person_name).distinct().all()
    candidates.update(r[0] for r in rows if r[0])

    return sorted(
        name for name in candidates
        if is_real_person_name(name) and name not in encoded
    )


def repair_people_missing_encodings(db: Session, limit_per_person: int = 40) -> dict:
    """
    Make every identified person recognisable again, and do nothing otherwise.

    Runs on startup. Two defects left existing installs with people who had a
    profile but no encodings: reassignment never enrolled anything, and the
    trainer could not encode the tight 144x144 detection crops it was given.
    Both are fixed going forward, but neither fix repairs data already on disk —
    an upgraded install would keep its unrecognisable people forever.

    Cheap when there is nothing wrong: it compares names against the encodings
    already loaded in memory and returns immediately if none are missing. Only
    people who are actually broken cost any work.

    `limit_per_person` bounds how many detections are enrolled for a person with
    no gallery at all. A few dozen encodings is already more than recognition
    needs, and without a bound a person with thousands of detections would stall
    startup copying and encoding all of them.
    """
    from backend.core.paths import paths

    broken = find_people_missing_encodings(db)
    if not broken:
        return {"checked": 0, "repaired": [], "failed": []}

    logger.info("Face repair: %s person(s) have no encodings: %s",
                len(broken), ", ".join(broken))

    repaired, failed = [], []

    for name in broken:
        try:
            from backend.core.gallery import iter_images
            photos = [image.name for image in iter_images(name)]

            if photos:
                # Gallery exists but never encoded — retrain from what is there.
                result = _train(name, copied=len(photos))
            else:
                # No gallery at all; build one from the detections the user
                # already attributed to this person.
                face_ids = [
                    r[0] for r in db.query(models.FaceDetectionEvent.id)
                    .filter(models.FaceDetectionEvent.person_name == name)
                    .order_by(models.FaceDetectionEvent.detected_at.desc())
                    .limit(limit_per_person).all()
                ]
                if not face_ids:
                    continue
                result = enrol_detections(db, face_ids, name)

            (repaired if result.get("trained") else failed).append(
                {"person": name, **result}
            )
        except Exception as e:
            logger.warning("Face repair failed for '%s': %s", name, e)
            failed.append({"person": name, "reason": str(e)})

    logger.info("Face repair complete: %s repaired, %s still without encodings",
                len(repaired), len(failed))
    return {"checked": len(broken), "repaired": repaired, "failed": failed}
