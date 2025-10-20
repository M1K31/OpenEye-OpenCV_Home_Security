#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Database Cleanup Utility

Removes database records for missing media files (orphaned records).

Usage:
    # Dry run (show what would be deleted)
    python -m backend.utils.cleanup_orphaned_records --dry-run

    # Actually delete orphaned records
    python -m backend.utils.cleanup_orphaned_records --confirm

    # Clean specific media type
    python -m backend.utils.cleanup_orphaned_records --type snapshots --confirm
"""

from pathlib import Path
from typing import Literal, Optional
import logging
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal
from backend.database.models import MotionDetectionEvent, RecordingEvent
from backend.core.paths import paths

logger = logging.getLogger(__name__)

MediaType = Literal["snapshots", "recordings", "all"]


class CleanupResult:
    """Results from a cleanup operation"""

    def __init__(self):
        self.total_records = 0
        self.orphaned_records = 0
        self.cleaned_records = 0
        self.errors = []

    def to_dict(self) -> dict:
        return {
            "total_records": self.total_records,
            "orphaned_records": self.orphaned_records,
            "cleaned_records": self.cleaned_records,
            "success": len(self.errors) == 0,
            "errors": self.errors,
        }


def cleanup_orphaned_snapshots(
    db: Session, dry_run: bool = True
) -> CleanupResult:
    """
    Remove database records for missing snapshot files

    Args:
        db: Database session
        dry_run: If True, don't actually delete records

    Returns:
        CleanupResult with statistics
    """
    result = CleanupResult()

    # Get all motion events with snapshots
    events = db.query(MotionDetectionEvent).filter(
        MotionDetectionEvent.snapshot_path.isnot(None)
    ).all()

    result.total_records = len(events)
    logger.info(f"Checking {result.total_records} snapshot records...")

    orphaned_ids = []

    for event in events:
        if not event.snapshot_path:
            continue

        # Resolve path
        full_path = paths.resolve_path(event.snapshot_path)

        # Check if file exists
        if not full_path.exists():
            logger.debug(f"Orphaned snapshot: {event.snapshot_path} (ID: {event.id})")
            orphaned_ids.append(event.id)
            result.orphaned_records += 1

    logger.info(f"Found {result.orphaned_records} orphaned snapshot records")

    # Delete orphaned records if not dry run
    if not dry_run and orphaned_ids:
        try:
            deleted = db.query(MotionDetectionEvent).filter(
                MotionDetectionEvent.id.in_(orphaned_ids)
            ).delete(synchronize_session=False)

            db.commit()
            result.cleaned_records = deleted
            logger.info(f"Deleted {deleted} orphaned snapshot records")

        except Exception as e:
            db.rollback()
            error = f"Failed to delete orphaned records: {str(e)}"
            logger.error(error)
            result.errors.append(error)

    return result


def cleanup_orphaned_recordings(
    db: Session, dry_run: bool = True
) -> CleanupResult:
    """
    Remove database records for missing recording files

    Args:
        db: Database session
        dry_run: If True, don't actually delete records

    Returns:
        CleanupResult with statistics
    """
    result = CleanupResult()

    # Get all recording events
    events = db.query(RecordingEvent).filter(
        RecordingEvent.recording_path.isnot(None)
    ).all()

    result.total_records = len(events)
    logger.info(f"Checking {result.total_records} recording records...")

    orphaned_ids = []

    for event in events:
        if not event.recording_path:
            continue

        # Resolve path
        full_path = paths.resolve_path(event.recording_path)

        # Check if file exists
        if not full_path.exists():
            logger.debug(f"Orphaned recording: {event.recording_path} (ID: {event.id})")
            orphaned_ids.append(event.id)
            result.orphaned_records += 1

    logger.info(f"Found {result.orphaned_records} orphaned recording records")

    # Delete orphaned records if not dry run
    if not dry_run and orphaned_ids:
        try:
            deleted = db.query(RecordingEvent).filter(
                RecordingEvent.id.in_(orphaned_ids)
            ).delete(synchronize_session=False)

            db.commit()
            result.cleaned_records = deleted
            logger.info(f"Deleted {deleted} orphaned recording records")

        except Exception as e:
            db.rollback()
            error = f"Failed to delete orphaned records: {str(e)}"
            logger.error(error)
            result.errors.append(error)

    return result


def cleanup_orphaned_records(
    media_type: MediaType = "all", dry_run: bool = True
) -> dict:
    """
    Clean up orphaned database records for missing media files

    Args:
        media_type: Type of media to clean ("snapshots", "recordings", "all")
        dry_run: If True, don't actually delete records

    Returns:
        Combined results dict with statistics

    Example:
        >>> result = cleanup_orphaned_records(media_type="snapshots", dry_run=False)
        >>> print(f"Cleaned {result['snapshots']['cleaned_records']} records")
    """
    logger.info(f"Starting cleanup: type={media_type}, dry_run={dry_run}")

    db = SessionLocal()
    results = {}

    try:
        if media_type in ["snapshots", "all"]:
            logger.info("Cleaning orphaned snapshot records...")
            results["snapshots"] = cleanup_orphaned_snapshots(db, dry_run).to_dict()

        if media_type in ["recordings", "all"]:
            logger.info("Cleaning orphaned recording records...")
            results["recordings"] = cleanup_orphaned_recordings(db, dry_run).to_dict()

    finally:
        db.close()

    # Calculate totals
    total_orphaned = sum(
        r.get("orphaned_records", 0) for r in results.values()
    )
    total_cleaned = sum(
        r.get("cleaned_records", 0) for r in results.values()
    )

    results["summary"] = {
        "total_orphaned": total_orphaned,
        "total_cleaned": total_cleaned,
        "dry_run": dry_run,
    }

    logger.info(f"Cleanup complete: {results['summary']}")
    return results


# CLI Interface
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Clean up orphaned database records for missing media files"
    )
    parser.add_argument(
        "--type",
        choices=["snapshots", "recordings", "all"],
        default="all",
        help="Type of media to clean (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete orphaned records (opposite of --dry-run)",
    )

    args = parser.parse_args()

    # Determine dry_run mode
    dry_run = not args.confirm if args.confirm else args.dry_run

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Run cleanup
    results = cleanup_orphaned_records(
        media_type=args.type,
        dry_run=dry_run,
    )

    # Print results
    print("\n" + "=" * 60)
    print("Cleanup Results")
    print("=" * 60)

    if "snapshots" in results:
        print("\nSnapshots:")
        print(f"  Total records:     {results['snapshots']['total_records']}")
        print(f"  Orphaned records:  {results['snapshots']['orphaned_records']}")
        print(f"  Cleaned records:   {results['snapshots']['cleaned_records']}")

    if "recordings" in results:
        print("\nRecordings:")
        print(f"  Total records:     {results['recordings']['total_records']}")
        print(f"  Orphaned records:  {results['recordings']['orphaned_records']}")
        print(f"  Cleaned records:   {results['recordings']['cleaned_records']}")

    print("\nSummary:")
    print(f"  Total orphaned:    {results['summary']['total_orphaned']}")
    print(f"  Total cleaned:     {results['summary']['total_cleaned']}")
    print(f"  Dry run:           {results['summary']['dry_run']}")

    if dry_run:
        print("\n⚠️  This was a DRY RUN - no records were actually deleted")
        print("   Run with --confirm to actually delete orphaned records")
    else:
        print("\n✅ Orphaned records have been deleted")

    # Print errors if any
    all_errors = []
    for result_type, result_data in results.items():
        if result_type != "summary" and result_data.get("errors"):
            all_errors.extend(result_data["errors"])

    if all_errors:
        print("\nErrors:")
        for error in all_errors:
            print(f"  ❌ {error}")

    # Exit with error code if there were errors
    exit(0 if not all_errors else 1)
