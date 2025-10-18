#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database migration: Add motion_detection_events table

This migration creates a new table to track all motion detection events,
including those without face detection. This allows the timeline to show
ALL activity, not just events where faces were detected.

Run this script from the project root:
    python backend/database/migrations/add_motion_detection_events.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from opencv_surveillance.backend.database.session import SQLALCHEMY_DATABASE_URL


def upgrade():
    """Add motion_detection_events table"""
    print("\n" + "="*60)
    print("Migration: Add motion_detection_events table")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Create motion_detection_events table
        print("📝 Creating motion_detection_events table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS motion_detection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Motion details
                motion_area INTEGER,
                motion_percentage REAL,
                contour_count INTEGER,
                
                -- Snapshot information
                snapshot_path TEXT,
                frame_width INTEGER,
                frame_height INTEGER,
                
                -- Recording linkage
                recording_id INTEGER,
                recording_path TEXT,
                
                -- Face detection context
                faces_detected INTEGER DEFAULT 0,
                face_detection_ids TEXT,
                
                -- Motion zone information
                triggered_zones TEXT,
                
                FOREIGN KEY (recording_id) REFERENCES recording_events (id)
            )
        """))
        
        # Create indexes for performance
        print("📝 Creating indexes...")
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_camera_id 
            ON motion_detection_events(camera_id)
        """))
        print("   ✅ Index on camera_id")
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_detected_at 
            ON motion_detection_events(detected_at)
        """))
        print("   ✅ Index on detected_at")
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_motion_recording_id 
            ON motion_detection_events(recording_id)
        """))
        print("   ✅ Index on recording_id")
        
        conn.commit()
        
        print("\n✅ motion_detection_events table created successfully")
        print("\nTable schema:")
        print("  - Tracks ALL motion events (with or without faces)")
        print("  - Links to recordings and face detections")
        print("  - Stores snapshot paths for timeline display")
        print("  - Captures motion metrics (area, percentage, contours)")


def downgrade():
    """Remove motion_detection_events table"""
    print("\n" + "="*60)
    print("Migration Rollback: Remove motion_detection_events table")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🗑️  Dropping motion_detection_events table...")
        conn.execute(text("DROP TABLE IF EXISTS motion_detection_events"))
        conn.commit()
        print("✅ motion_detection_events table dropped")


def verify():
    """Verify the migration was successful"""
    print("\n" + "="*60)
    print("Verifying migration...")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='motion_detection_events'
        """))
        table_exists = result.fetchone() is not None
        
        if table_exists:
            print("✅ Table 'motion_detection_events' exists")
            
            # Check indexes
            result = conn.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='motion_detection_events'
            """))
            indexes = [row[0] for row in result.fetchall()]
            print(f"✅ Found {len(indexes)} indexes: {', '.join(indexes)}")
            
            # Get column info
            result = conn.execute(text("PRAGMA table_info(motion_detection_events)"))
            columns = [row[1] for row in result.fetchall()]
            print(f"✅ Table has {len(columns)} columns")
            print(f"   Columns: {', '.join(columns)}")
            
            return True
        else:
            print("❌ Table 'motion_detection_events' does not exist")
            return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Motion Detection Events Migration")
    parser.add_argument(
        "action",
        choices=["upgrade", "downgrade", "verify"],
        default="upgrade",
        nargs="?",
        help="Migration action: upgrade (default), downgrade, or verify"
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
        
        print("\n" + "="*60)
        print("Migration complete!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
