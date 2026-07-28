#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database migration: Add event_type column to face_detection_events

Adds an event_type column to distinguish face detection events from
motion-only events (where motion was detected but no face was found).

Run this script from the project root:
    python backend/database/migrations/add_event_type_column.py
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from backend.database.session import SQLALCHEMY_DATABASE_URL


def upgrade():
    """Add event_type column to face_detection_events"""
    print("\n" + "=" * 60)
    print("Migration: Add event_type column to face_detection_events")
    print("=" * 60 + "\n")

    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(face_detection_events)"))
        columns = [row[1] for row in result.fetchall()]

        if "event_type" in columns:
            print("Column 'event_type' already exists — skipping")
            return

        print("Adding event_type column...")
        conn.execute(text("""
            ALTER TABLE face_detection_events
            ADD COLUMN event_type TEXT NOT NULL DEFAULT 'face_detected'
        """))

        print("Creating index on event_type...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_face_event_type
            ON face_detection_events(event_type)
        """))

        conn.commit()
        print("Done")


def downgrade():
    """SQLite doesn't support DROP COLUMN before 3.35.0; recreate table if needed"""
    print("Downgrade: event_type column removal requires SQLite >= 3.35.0")
    print("For older SQLite, manually recreate the table without the column.")


def verify():
    """Verify the migration"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(face_detection_events)"))
        columns = [row[1] for row in result.fetchall()]

        if "event_type" in columns:
            print("event_type column exists")
            return True
        else:
            print("event_type column NOT found")
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add event_type column migration")
    parser.add_argument(
        "action",
        choices=["upgrade", "downgrade", "verify"],
        default="upgrade",
        nargs="?",
    )

    args = parser.parse_args()

    try:
        if args.action == "upgrade":
            upgrade()
            verify()
        elif args.action == "downgrade":
            downgrade()
        elif args.action == "verify":
            verify()
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
