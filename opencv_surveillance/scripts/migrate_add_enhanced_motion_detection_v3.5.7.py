#!/usr/bin/env python3
"""
Migration: Add Enhanced Motion Detection Parameters (v3.5.7)

This migration adds new fields to the cameras table for enhanced motion detection:
- Grayscale-first processing
- HSV-based shadow detection
- Separate erosion/dilation controls
- Motion persistence/cooldown
- Lighting compensation controls

New fields:
- shadow_detection_method: String (default 'dual') - Shadow removal method (binary, hsv, dual)
- erosion_iterations: Integer (nullable) - Custom erosion iterations
- dilation_iterations: Integer (nullable) - Custom dilation iterations
- motion_persistence_frames: Integer (default 2) - Frames to maintain motion state
- use_grayscale: Boolean (default True) - Convert to grayscale before processing
- lighting_compensation_enabled: Boolean (default True) - Enable lighting change detection
- brightness_change_threshold: Integer (default 15) - Threshold for lighting changes

Usage:
    python scripts/migrate_add_enhanced_motion_detection_v3.5.7.py
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


def add_enhanced_motion_detection_columns():
    """Add enhanced motion detection columns to cameras table."""
    print("=" * 80)
    print("MIGRATION: Add Enhanced Motion Detection Parameters (v3.5.7)")
    print("=" * 80)
    print()

    new_columns = {
        "shadow_detection_method": ("TEXT", "dual"),
        "erosion_iterations": ("INTEGER", 2),  # Recommended: 2 for shadow mitigation
        "dilation_iterations": ("INTEGER", 3),  # Recommended: 3 for shadow mitigation
        "motion_persistence_frames": ("INTEGER", 2),
        "use_grayscale": ("INTEGER", 1),  # SQLite uses 0/1 for boolean
        "lighting_compensation_enabled": ("INTEGER", 1),
        "brightness_change_threshold": ("INTEGER", 15),
    }

    added_columns = []
    skipped_columns = []

    with engine.begin() as conn:
        for column_name, (column_type, default_value) in new_columns.items():
            # Check if column already exists
            if check_column_exists("cameras", column_name):
                print(f"⏭️  Column '{column_name}' already exists - skipping")
                skipped_columns.append(column_name)
                continue

            print(f"Adding column '{column_name}'...")

            # Build ALTER TABLE statement
            if default_value is None:
                sql = f"ALTER TABLE cameras ADD COLUMN {column_name} {column_type}"
            else:
                if isinstance(default_value, str):
                    sql = f"ALTER TABLE cameras ADD COLUMN {column_name} {column_type} DEFAULT '{default_value}'"
                else:
                    sql = f"ALTER TABLE cameras ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"

            conn.execute(text(sql))
            print(f"   ✅ Added '{column_name}' (type: {column_type}, default: {default_value})")
            added_columns.append(column_name)

        print()

    print("=" * 80)
    print("MIGRATION COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    if added_columns:
        print(f"  ✅ Added {len(added_columns)} new column(s):")
        for col in added_columns:
            print(f"     - {col}")
    if skipped_columns:
        print(f"  ⏭️  Skipped {len(skipped_columns)} existing column(s):")
        for col in skipped_columns:
            print(f"     - {col}")
    print()
    print("New Features Enabled:")
    print("  🎯 Grayscale-first processing for better performance")
    print("  🌑 Dual shadow detection (binary + HSV)")
    print("  🔧 Separate erosion/dilation controls")
    print("  ⏱️  Motion persistence to prevent flickering")
    print("  💡 Enhanced lighting compensation")
    print()


def verify_migration():
    """Verify the migration was successful."""
    print("Verifying migration...")
    print()

    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("cameras")}

    expected_columns = [
        "shadow_detection_method",
        "erosion_iterations",
        "dilation_iterations",
        "motion_persistence_frames",
        "use_grayscale",
        "lighting_compensation_enabled",
        "brightness_change_threshold",
    ]

    all_present = True
    for col_name in expected_columns:
        if col_name not in columns:
            print(f"❌ ERROR: Column '{col_name}' not found!")
            all_present = False
        else:
            col = columns[col_name]
            print(f"✅ {col_name}: {col['type']}")

    print()

    if all_present:
        # Check values in database
        db = SessionLocal()
        try:
            result = db.execute(
                text(
                    """
                    SELECT
                        camera_id,
                        shadow_detection_method,
                        motion_persistence_frames,
                        use_grayscale,
                        lighting_compensation_enabled
                    FROM cameras
                    LIMIT 5
                    """
                )
            )
            cameras = result.fetchall()

            if cameras:
                print(f"✅ Sample camera settings ({len(cameras)} shown):")
                for cam in cameras:
                    print(f"   - {cam.camera_id}:")
                    print(f"     Shadow method: {cam.shadow_detection_method}")
                    print(f"     Persistence: {cam.motion_persistence_frames} frames")
                    print(f"     Grayscale: {'Yes' if cam.use_grayscale else 'No'}")
                    print(f"     Lighting comp: {'Yes' if cam.lighting_compensation_enabled else 'No'}")
            else:
                print("   No cameras found (this is OK for new installations)")

            print()
            return True

        finally:
            db.close()

    return all_present


def main():
    """Run the migration."""
    try:
        print("\n")
        add_enhanced_motion_detection_columns()
        success = verify_migration()

        if success:
            print("=" * 80)
            print("✅ MIGRATION SUCCESSFUL")
            print("=" * 80)
            print()
            print("Next steps:")
            print("  1. Restart the backend server")
            print("  2. New cameras will use enhanced detection by default")
            print("  3. Existing cameras will use new defaults automatically")
            print("  4. Fine-tune settings per camera in the UI if needed")
            print()
            print("Recommended Settings for Shadow Mitigation:")
            print("  - shadow_detection_method: 'dual' (best accuracy)")
            print("  - use_grayscale: True (better performance)")
            print("  - motion_persistence_frames: 2-3 (reduces flickering)")
            print("  - lighting_compensation_enabled: True (handles light changes)")
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
