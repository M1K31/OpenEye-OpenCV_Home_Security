# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Give every existing person a row, and link what already refers to them.

Before this, a person existed only as a repeated string: a gallery folder name,
a cluster's label, and a person_name on each detection. Nothing tied those
together, which is why renaming had to sweep three stores and still missed rows,
and why "is this a real person or a placeholder?" was answered by pattern
matching the name.

This builds the missing rows from what is already there. It changes no
behaviour — person_name stays exactly as it is, and person_id is added
alongside — so the system works identically before and after. What it buys is
somewhere for the next phases to stand.

`plan()` reports what it would do and touches nothing. `apply()` writes.

    python -m backend.core.person_migration plan
    python -m backend.core.person_migration apply

ORIGIN IS INFERRED EXACTLY ONCE, HERE.

The auto-generated names follow ^unknown\\d+$, so that pattern identifies which
existing people the system named itself. That inference is unavoidable for
history — nothing recorded it at the time — but it happens only during this
migration. Afterwards origin is a stored fact, and the pattern is never
consulted again. A person genuinely called "unknown5" would be misfiled by this
one run and can be corrected afterwards; there is no way to do better with the
information that exists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Used ONCE, by this module, to seed origin for people who predate the column.
AUTO_NAME_PATTERN = re.compile(r"^unknown\d+$", re.IGNORECASE)

ORIGIN_CLUSTER = "cluster"
ORIGIN_USER = "user"


@dataclass
class PlannedPerson:
    name: str
    origin: str
    detections: int = 0
    clusters: List[int] = field(default_factory=list)
    gallery_files: Optional[int] = None
    already_exists: bool = False


@dataclass
class MigrationPlan:
    people: List[PlannedPerson] = field(default_factory=list)
    detections_to_link: int = 0
    clusters_to_link: int = 0
    unnamed_detections: int = 0
    dry_run: bool = True
    notes: List[str] = field(default_factory=list)

    def describe(self) -> str:
        lines = [
            "Person migration — %s" % ("preview, nothing changed" if self.dry_run else "applied"),
            "",
            f"  {'name':<14} {'origin':<9} {'detections':>10} {'clusters':>9} {'gallery':>8}",
        ]
        for person in self.people:
            gallery = "-" if person.gallery_files is None else str(person.gallery_files)
            marker = "  (exists)" if person.already_exists else ""
            lines.append(
                f"  {person.name:<14} {person.origin:<9} {person.detections:>10} "
                f"{len(person.clusters):>9} {gallery:>8}{marker}"
            )
        lines += [
            "",
            f"  people to create   {sum(1 for p in self.people if not p.already_exists)}",
            f"  detections to link {self.detections_to_link}",
            f"  clusters to link   {self.clusters_to_link}",
        ]
        if self.unnamed_detections:
            lines.append(
                f"  detections left unlinked: {self.unnamed_detections} "
                f'(person_name is "Unknown" — not a person, an absence of one)')
        lines.extend(f"  note: {n}" for n in self.notes)
        return "\n".join(lines)


def _gallery_counts() -> Dict[str, int]:
    """How many images each gallery folder holds, for cross-checking."""
    from pathlib import Path

    from backend.core.paths import paths

    counts: Dict[str, int] = {}
    faces_dir = Path(paths.faces_dir)
    if not faces_dir.is_dir():
        return counts
    for entry in faces_dir.iterdir():
        if entry.is_dir():
            counts[entry.name] = sum(1 for f in entry.iterdir() if f.is_file())
    return counts


def build_plan(db) -> MigrationPlan:
    """Work out which people exist and what refers to them. Reads only."""
    from backend.database.models import FaceCluster, FaceDetectionEvent, Person

    plan = MigrationPlan(dry_run=True)
    galleries = _gallery_counts()

    existing = {p.name: p for p in db.query(Person).all()}

    # Every name that appears anywhere. "Unknown" is deliberately excluded: it
    # is the absence of an identity, not an identity, and giving it a row would
    # make every unrecognised face in the system one person.
    names: Dict[str, PlannedPerson] = {}

    def entry_for(name: str) -> Optional[PlannedPerson]:
        clean = (name or "").strip()
        if not clean or clean == "Unknown":
            return None
        if clean not in names:
            names[clean] = PlannedPerson(
                name=clean,
                origin=ORIGIN_CLUSTER if AUTO_NAME_PATTERN.match(clean) else ORIGIN_USER,
                gallery_files=galleries.get(clean),
                already_exists=clean in existing,
            )
        return names[clean]

    for name, count in db.query(
            FaceDetectionEvent.person_name,
            __import__("sqlalchemy").func.count(FaceDetectionEvent.id)
    ).group_by(FaceDetectionEvent.person_name).all():
        person = entry_for(name)
        if person is None:
            if (name or "").strip() == "Unknown":
                plan.unnamed_detections += count
            continue
        person.detections += count
        plan.detections_to_link += count

    for cluster_id, label in db.query(FaceCluster.id, FaceCluster.label).all():
        person = entry_for(label)
        if person is not None:
            person.clusters.append(cluster_id)
            plan.clusters_to_link += 1

    # A gallery folder with no detections and no cluster is still a person —
    # somebody made it deliberately and uploaded photographs. Losing them here
    # would be the migration quietly deleting the most considered data present.
    for folder, count in galleries.items():
        person = entry_for(folder)
        if person is not None and person.detections == 0 and not person.clusters:
            plan.notes.append(
                f"'{folder}' has {count} gallery image(s) but no detections or "
                f"clusters — created by hand, kept as a user person")
            person.origin = ORIGIN_USER

    plan.people = sorted(names.values(), key=lambda p: -p.detections)
    return plan


def apply_plan(db, plan: MigrationPlan) -> MigrationPlan:
    """Create the rows and link what refers to them."""
    from backend.database.models import FaceCluster, FaceDetectionEvent, Person

    existing = {p.name: p for p in db.query(Person).all()}
    created = 0

    for planned in plan.people:
        person = existing.get(planned.name)
        if person is None:
            person = Person(
                name=planned.name,
                origin=planned.origin,
                # A user-created person is confirmed by definition — somebody
                # typed that name. A cluster-created one is not, until a human
                # says so, and that is precisely what keeps its snapshots.
                confirmed_at=datetime.utcnow() if planned.origin == ORIGIN_USER else None,
            )
            db.add(person)
            db.flush()
            existing[planned.name] = person
            created += 1

        db.query(FaceDetectionEvent).filter(
            FaceDetectionEvent.person_name == planned.name
        ).update({"person_id": person.id}, synchronize_session=False)

        db.query(FaceCluster).filter(
            FaceCluster.label == planned.name
        ).update({"person_id": person.id}, synchronize_session=False)

    db.commit()
    plan.dry_run = False
    plan.notes.append(f"created {created} person row(s)")
    logger.info("Person migration applied: %s people, %s detections, %s clusters",
                len(plan.people), plan.detections_to_link, plan.clusters_to_link)
    return plan


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Create person rows from existing names and link references.")
    parser.add_argument("command", choices=["plan", "apply"])
    args = parser.parse_args()

    from backend.database.utils import get_db_context

    with get_db_context() as db:
        plan = build_plan(db)
        if args.command == "apply":
            plan = apply_plan(db, plan)

    print(plan.describe())
    if plan.dry_run:
        print("\nPreview only. Re-run with 'apply' to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
