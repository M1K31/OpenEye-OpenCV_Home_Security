#!/usr/bin/env python3
"""
Migration: Add motion_percentage_threshold to cameras table

This migration adds a new field to control the minimum percentage of the frame
that must have motion before triggering a motion detection event.

Previously, the system would trigger on ANY motion (even 0.1%), which caused
excessive false positives. The motion_threshold field only controls the OpenCV
varThreshold parameter (pixel-level sensitivity), not the motion percentage.

New field:
- motion_percentage_threshold: Float (default 1.0) - Minimum percentage (0.0-100.0)
  of the frame that must have motion to trigger an event

Usage:
    python scripts/migrate_add_motion_percentage_threshold.py
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.session import engine, SessionLocal
from sqlalchemy import text, inspect
import sqlalchemy as sa


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_motion_percentage_threshold():
    """Add motion_percentage_threshold column to cameras table."""
    print("=" * 80)
    print("MIGRATION: Add motion_percentage_threshold to cameras")
    print("=" * 80)
    print()

    # Check if column already exists
    if check_column_exists("cameras", "motion_percentage_threshold"):
        print("✅ Column 'motion_percentage_threshold' already exists in cameras table")
        print("   No migration needed.")
        return

    print("Adding motion_percentage_threshold column to cameras table...")
    print()

    with engine.begin() as conn:
        # Add motion_percentage_threshold column (default 1.0%)
        print("1. Adding motion_percentage_threshold column...")
        conn.execute(
            text(
                """
                ALTER TABLE cameras 
                ADD COLUMN motion_percentage_threshold REAL DEFAULT 1.0
                """
            )
        )
        print("   ✅ Column added with default value 1.0")
        print()

        # Update existing cameras to have the default value
        print("2. Setting default value for existing cameras...")
        conn.execute(
            text(
                """
                UPDATE cameras 
                SET motion_percentage_threshold = 1.0 
                WHERE motion_percentage_threshold IS NULL
                """
            )
        )
        result = conn.execute(text("SELECT COUNT(*) FROM cameras"))
        camera_count = result.scalar()
        print(f"   ✅ Updated {camera_count} existing camera(s)")
        print()

    print("=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    print("  ✅ Added motion_percentage_threshold column to cameras table")
    print("  ✅ Set default value to 1.0% for all cameras")
    print()
    print("What this means:")
    print("  - Motion events will only trigger if >= 1.0% of frame has motion")
    print("  - This prevents false positives from tiny movements (like 0.1%)")
    print("  - You can adjust this per-camera in the settings UI")
    print("  - Range: 0.0 - 100.0 (percentage of frame area)")
    print()


def verify_migration():
    """Verify the migration was successful."""
    print("Verifying migration...")
    print()

    inspector = inspect(engine)

    # Check column exists
    columns = {col["name"]: col for col in inspector.get_columns("cameras")}

    if "motion_percentage_threshold" not in columns:
        print("❌ ERROR: motion_percentage_threshold column not found!")
        return False

    print("✅ Column structure verified:")
    col = columns["motion_percentage_threshold"]
    print(f"   - Name: {col['name']}")
    print(f"   - Type: {col['type']}")
    print(f"   - Nullable: {col.get('nullable', 'N/A')}")
    print(f"   - Default: {col.get('default', 'N/A')}")
    print()

    # Check values in database
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                """
                SELECT 
                    id, 
                    camera_id, 
                    motion_percentage_threshold 
                FROM cameras
                """
            )
        )
        cameras = result.fetchall()

        if cameras:
            print(f"✅ Found {len(cameras)} camera(s) with threshold values:")
            for cam in cameras:
                print(
                    f"   - {cam.camera_id}: {cam.motion_percentage_threshold}% threshold"
                )
        else:
            print("   No cameras found (this is OK for new installations)")

        print()
        return True

    finally:
        db.close()


def main():
    """Run the migration."""
    try:
        print("\n")
        add_motion_percentage_threshold()
        success = verify_migration()

        if success:
            print("=" * 80)
            print("✅ MIGRATION SUCCESSFUL")
            print("=" * 80)
            print()
            print("Next steps:")
            print("  1. Restart the backend server")
            print("  2. Update camera settings in the UI if needed")
            print("  3. Monitor motion detection logs")
            print()
            return 0
        else:
            print("=" * 80)
            print("❌ MIGRATION VERIFICATION FAILED")
            print("=" * 80)
            return 1

    except Exception as e:
        print("=" * 80)
        print("❌ MIGRATION FAILED")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
