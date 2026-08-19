# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Where a person's training photographs live, and which of them are disposable.

A gallery holds two kinds of image with different rules:

    detected/   exported from camera snapshots, automatically
    uploaded/   chosen and uploaded by a person, deliberately

Nothing distinguished them before — one flat folder — and that blocks the repair
that assignment needs. Rebuilding a person's gallery from their detections is the
only reliable way to move training data when detections are reassigned, because
gallery filenames cannot be traced back to the detections they came from. But a
blind rebuild would delete the uploaded photographs, which are the deliberately
chosen, better-quality images: exactly the wrong ones to lose.

So detected/ is derived and may be regenerated; uploaded/ is authored and must
never be touched by anything automatic.

Both are read for training. The split governs what may be DELETED, not what
counts — a person's face is their face however the picture arrived.

Flat layouts are still read. An installation that has not been migrated keeps
working, and images sitting directly in the person folder are treated as
uploaded — the safe reading, since anything not known to be derived must not be
deleted automatically.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterator, List

logger = logging.getLogger(__name__)

DETECTED = "detected"
UPLOADED = "uploaded"

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")

# What an export from a detection looks like: 20260815_212624_usb_camera_0_0.jpg
#
# Used ONLY to classify pre-existing files during migration, where nothing
# recorded their origin. Afterwards the folder is the fact. Anything that does
# not match is treated as uploaded, because the cost of misfiling a camera
# export is that it survives a rebuild, while the cost of misfiling somebody's
# chosen photograph is that it is deleted.
EXPORTED_NAME = re.compile(r"^\d{8}_\d{6}_.+_\d+\.(jpg|jpeg|png|webp)$", re.IGNORECASE)


def person_dir(person_name: str) -> Path:
    from backend.core.paths import paths
    return Path(paths.faces_dir) / person_name


def detected_dir(person_name: str) -> Path:
    return person_dir(person_name) / DETECTED


def uploaded_dir(person_name: str) -> Path:
    return person_dir(person_name) / UPLOADED


def iter_images(person_name: str) -> Iterator[Path]:
    """
    Every training image for a person, wherever it sits.

    Covers detected/, uploaded/, and any images left directly in the person
    folder by an installation that has not been migrated.
    """
    root = person_dir(person_name)
    if not root.is_dir():
        return

    for entry in root.iterdir():
        if entry.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            yield entry
        elif entry.is_dir() and entry.name in (DETECTED, UPLOADED):
            for image in entry.iterdir():
                if image.is_file() and image.suffix.lower() in IMAGE_SUFFIXES:
                    yield image


def count_images(person_name: str) -> int:
    return sum(1 for _ in iter_images(person_name))


def images_in(directory: Path) -> List[Path]:
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def ensure_layout(person_name: str) -> Path:
    """Create the person's folder and both subfolders. Returns the person folder."""
    root = person_dir(person_name)
    (root / DETECTED).mkdir(parents=True, exist_ok=True)
    (root / UPLOADED).mkdir(parents=True, exist_ok=True)
    return root


def migrate_person(person_name: str, dry_run: bool = True) -> dict:
    """
    Sort a flat gallery into detected/ and uploaded/.

    Classification is by filename, once, because nothing recorded the origin at
    the time. Anything that does not look like a camera export is treated as
    uploaded, so a misjudgement leaves a file undeletable rather than deleting
    one somebody chose.
    """
    root = person_dir(person_name)
    result = {"person": person_name, "to_detected": 0, "to_uploaded": 0, "already": 0}
    if not root.is_dir():
        return result

    loose = [p for p in root.iterdir()
             if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES]
    result["already"] = (len(images_in(root / DETECTED))
                         + len(images_in(root / UPLOADED)))

    for image in loose:
        target = DETECTED if EXPORTED_NAME.match(image.name) else UPLOADED
        if target == DETECTED:
            result["to_detected"] += 1
        else:
            result["to_uploaded"] += 1

        if not dry_run:
            destination = root / target / image.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                image.unlink()      # same file already sorted
            else:
                image.rename(destination)

    return result


def migrate_all(dry_run: bool = True) -> List[dict]:
    from backend.core.paths import paths

    faces = Path(paths.faces_dir)
    if not faces.is_dir():
        return []
    return [migrate_person(entry.name, dry_run=dry_run)
            for entry in sorted(faces.iterdir()) if entry.is_dir()]


def _cli() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sort flat face galleries into detected/ and uploaded/.")
    parser.add_argument("command", choices=["plan", "apply"])
    args = parser.parse_args()

    results = migrate_all(dry_run=args.command == "plan")
    if not results:
        print("No galleries found.")
        return 0

    print(f"  {'person':<14} {'-> detected':>12} {'-> uploaded':>12} {'already sorted':>15}")
    for r in results:
        print(f"  {r['person']:<14} {r['to_detected']:>12} {r['to_uploaded']:>12} "
              f"{r['already']:>15}")

    total_up = sum(r["to_uploaded"] for r in results)
    if total_up:
        print(f"\n  {total_up} file(s) did not look like camera exports and were "
              f"treated as uploaded — they will never be removed automatically.")
    if args.command == "plan":
        print("\nPreview only. Re-run with 'apply'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
