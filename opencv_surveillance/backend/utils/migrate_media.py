#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Media File Migration Utility

Migrates recordings, snapshots, and faces to new storage locations
with database path updates.

Usage:
    # Via Python module
    python -m backend.utils.migrate_media \
        --type snapshots \
        --source /old/path \
        --dest /new/path \
        --update-db

    # Via API (recommended)
    PUT /api/settings/paths?migrate=true
"""

# PEP 604 annotations (Path | str) are used below. This project supports Python
# 3.9 (the runtime venv and the CI matrix both include it), where that syntax is a
# TypeError at import time. Deferring annotation evaluation keeps the modern
# syntax readable while remaining importable on 3.9.
from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal
import shutil
import logging
from sqlalchemy.orm import Session

from backend.database.session import SessionLocal
from backend.database.models import MotionDetectionEvent, RecordingEvent
from backend.core.paths import paths

logger = logging.getLogger(__name__)

MediaType = Literal["recordings", "snapshots", "faces"]


class MigrationResult:
    """Results from a migration operation"""

    def __init__(self):
        self.files_found = 0
        self.files_moved = 0
        self.files_failed = 0
        self.db_records_updated = 0
        self.errors = []

    def to_dict(self) -> dict:
        return {
            "files_found": self.files_found,
            "files_moved": self.files_moved,
            "files_failed": self.files_failed,
            "db_records_updated": self.db_records_updated,
            "success": self.files_failed == 0,
            "errors": self.errors,
        }


def migrate_files(
    media_type: MediaType,
    source_dir: Path | str,
    dest_dir: Path | str,
    update_database: bool = True,
    dry_run: bool = False,
) -> MigrationResult:
    """
    Migrate media files from source to destination

    Args:
        media_type: Type of media (recordings, snapshots, faces)
        source_dir: Source directory path
        dest_dir: Destination directory path
        update_database: Whether to update database records
        dry_run: If True, don't actually move files (just report what would happen)

    Returns:
        MigrationResult with statistics

    Example:
        >>> result = migrate_files(
        ...     media_type="snapshots",
        ...     source_dir="/old/snapshots",
        ...     dest_dir="/new/snapshots",
        ...     update_database=True
        ... )
        >>> print(f"Moved {result.files_moved} files")
    """
    source_path = Path(source_dir).resolve()
    dest_path = Path(dest_dir).resolve()
    result = MigrationResult()

    logger.info(f"Starting {media_type} migration:")
    logger.info(f"  Source: {source_path}")
    logger.info(f"  Dest: {dest_path}")
    logger.info(f"  Update DB: {update_database}")
    logger.info(f"  Dry run: {dry_run}")

    # Validate paths
    if not source_path.exists():
        error = f"Source directory does not exist: {source_path}"
        logger.error(error)
        result.errors.append(error)
        return result

    if source_path == dest_path:
        logger.info("Source and destination are the same, nothing to migrate")
        return result

    # Create destination directory
    if not dry_run:
        dest_path.mkdir(parents=True, exist_ok=True)

    # Get list of files to migrate
    file_patterns = {
        "recordings": ["*.mp4", "*.avi", "*.mkv", "*.webm", "*_metadata.json"],
        "snapshots": ["*.jpg", "*.jpeg", "*.png"],
        "faces": ["*"],  # All files in faces directories
    }

    patterns = file_patterns.get(media_type, ["*"])
    files_to_migrate = []

    for pattern in patterns:
        files_to_migrate.extend(source_path.glob(pattern))

    # Filter out directories (for faces migration)
    files_to_migrate = [f for f in files_to_migrate if f.is_file()]

    result.files_found = len(files_to_migrate)
    logger.info(f"Found {result.files_found} files to migrate")

    # Migrate files
    for source_file in files_to_migrate:
        try:
            # Calculate relative path to preserve directory structure
            relative_path = source_file.relative_to(source_path)
            dest_file = dest_path / relative_path

            if not dry_run:
                # Create parent directory if needed
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                # Move file
                shutil.move(str(source_file), str(dest_file))
                logger.debug(f"Moved: {source_file.name} -> {dest_file}")

            result.files_moved += 1

        except Exception as e:
            error = f"Failed to move {source_file.name}: {str(e)}"
            logger.error(error)
            result.errors.append(error)
            result.files_failed += 1

    # Update database if requested
    if update_database and not dry_run:
        try:
            db = SessionLocal()
            try:
                if media_type == "snapshots":
                    result.db_records_updated = _update_snapshot_paths(
                        db, source_path, dest_path
                    )
                elif media_type == "recordings":
                    result.db_records_updated = _update_recording_paths(
                        db, source_path, dest_path
                    )
                logger.info(f"Updated {result.db_records_updated} database records")
            finally:
                db.close()
        except Exception as e:
            error = f"Database update failed: {str(e)}"
            logger.error(error)
            result.errors.append(error)

    logger.info(f"Migration complete: {result.to_dict()}")
    return result


def _update_snapshot_paths(
    db: Session, old_base: Path, new_base: Path
) -> int:
    """Update snapshot paths in MotionDetectionEvent table"""
    updated_count = 0

    # Get all events with snapshots
    events = db.query(MotionDetectionEvent).filter(
        MotionDetectionEvent.snapshot_path.isnot(None)
    ).all()

    for event in events:
        if not event.snapshot_path:
            continue

        # Resolve old path
        old_full_path = paths.resolve_path(event.snapshot_path)

        # Check if this path is under the old base
        try:
            relative_to_old = old_full_path.relative_to(old_base)

            # Calculate new path
            new_full_path = new_base / relative_to_old

            # Store as relative path
            event.snapshot_path = paths.get_relative_path(new_full_path)
            updated_count += 1

        except ValueError:
            # Path is not under old_base, skip it
            continue

    db.commit()
    return updated_count


def _update_recording_paths(
    db: Session, old_base: Path, new_base: Path
) -> int:
    """Update recording paths in RecordingEvent table"""
    updated_count = 0

    # Get all events with recordings
    events = db.query(RecordingEvent).filter(
        RecordingEvent.recording_path.isnot(None)
    ).all()

    for event in events:
        if not event.recording_path:
            continue

        # Resolve old path
        old_full_path = paths.resolve_path(event.recording_path)

        # Check if this path is under the old base
        try:
            relative_to_old = old_full_path.relative_to(old_base)

            # Calculate new path
            new_full_path = new_base / relative_to_old

            # Store as relative path
            event.recording_path = paths.get_relative_path(new_full_path)
            updated_count += 1

        except ValueError:
            # Path is not under old_base, skip it
            continue

    db.commit()
    return updated_count


# CLI Interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate media files to new storage location"
    )
    parser.add_argument(
        "--type",
        choices=["recordings", "snapshots", "faces"],
        required=True,
        help="Type of media to migrate",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source directory path",
    )
    parser.add_argument(
        "--dest",
        required=True,
        help="Destination directory path",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="Update database records with new paths",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without moving files",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run migration
    result = migrate_files(
        media_type=args.type,
        source_dir=args.source,
        dest_dir=args.dest,
        update_database=args.update_db,
        dry_run=args.dry_run,
    )

    # Print summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Files found:      {result.files_found}")
    print(f"Files moved:      {result.files_moved}")
    print(f"Files failed:     {result.files_failed}")
    print(f"DB records updated: {result.db_records_updated}")
    print(f"Success:          {result.success}")

    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")

    # Exit with error code if migration failed
    exit(0 if result.files_failed == 0 else 1)
