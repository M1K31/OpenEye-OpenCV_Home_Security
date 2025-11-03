#!/usr/bin/env python3
"""
Fix Recording Durations Script

This script fixes the duration_seconds mismatch issue where recordings show
incorrect duration due to dropped frames during encoding.

The issue: OpenCV VideoWriter records based on wall-clock time, but if frames
are dropped (due to slow encoding or busy system), the actual video file will
be shorter than the recorded time.

This script:
1. Reads all recordings from the database
2. Analyzes each video file to get actual duration
3. Updates the database with correct durations
4. Reports any issues found

Usage:
    python3 fix_recording_durations.py [--dry-run]
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from backend.database.session import SessionLocal
from backend.database.models import RecordingEvent
from backend.utils.video_utils import get_actual_video_duration, verify_video_integrity
from sqlalchemy import func


def fix_recording_durations(dry_run=False):
    """
    Fix all recording durations in the database.

    Args:
        dry_run: If True, only report issues without making changes
    """
    db = SessionLocal()

    try:
        # Get all recordings
        recordings = db.query(RecordingEvent).all()

        print(f"Found {len(recordings)} recordings in database\n")

        fixed_count = 0
        error_count = 0
        skipped_count = 0

        for recording in recordings:
            recording_id = recording.id or recording.recording_id
            filename = recording.filename
            stored_duration = recording.duration_seconds

            print(f"Recording {recording_id}: {filename}")
            print(f"  Stored duration: {stored_duration:.2f}s")

            # Find the video file
            # Try multiple possible paths
            possible_paths = [
                filename,  # Absolute path
                os.path.join("recordings", filename),  # Relative to project root
                os.path.join(backend_path, "recordings", filename),  # Relative to backend
                os.path.join(backend_path, filename),  # Directly in backend
            ]

            video_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    video_path = path
                    break

            if not video_path:
                print(f"  ❌ ERROR: Video file not found (tried: {possible_paths[0]})")
                error_count += 1
                print()
                continue

            # Get actual duration
            actual_duration = get_actual_video_duration(video_path)

            if actual_duration is None:
                print(f"  ❌ ERROR: Could not read video duration")
                error_count += 1
                print()
                continue

            print(f"  Actual duration: {actual_duration:.2f}s")

            # Calculate difference
            difference = abs(stored_duration - actual_duration)
            difference_percent = (difference / stored_duration * 100) if stored_duration > 0 else 0

            if difference < 0.5:  # Less than 0.5 seconds difference
                print(f"  ✓ Duration is accurate (difference: {difference:.2f}s)")
                skipped_count += 1
            else:
                print(f"  ⚠️  Duration mismatch: {difference:.2f}s ({difference_percent:.1f}% off)")

                if dry_run:
                    print(f"  [DRY RUN] Would update duration from {stored_duration:.2f}s to {actual_duration:.2f}s")
                else:
                    # Update database
                    recording.duration_seconds = actual_duration
                    db.commit()
                    print(f"  ✅ Updated duration to {actual_duration:.2f}s")

                fixed_count += 1

            # Verify video integrity
            verification = verify_video_integrity(video_path)
            if not verification["valid"]:
                print(f"  ⚠️  Video integrity issues: {', '.join(verification['issues'])}")
            elif verification["issues"]:
                print(f"  ⚠️  Minor issues: {', '.join(verification['issues'])}")

            print()

        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Total recordings: {len(recordings)}")
        print(f"Fixed: {fixed_count}")
        print(f"Skipped (accurate): {skipped_count}")
        print(f"Errors: {error_count}")

        if dry_run:
            print("\n[DRY RUN] No changes were made to the database")
        else:
            print(f"\n✅ Successfully updated {fixed_count} recordings")

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fix recording duration mismatches")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fixed without making changes"
    )

    args = parser.parse_args()

    print("OpenEye Recording Duration Fix Tool")
    print("="*60)
    print()

    if args.dry_run:
        print("Running in DRY RUN mode - no changes will be made\n")

    fix_recording_durations(dry_run=args.dry_run)
