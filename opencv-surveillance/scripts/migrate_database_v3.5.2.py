#!/usr/bin/env python3
"""
Database Migration Script - v3.5.2
Applies schema changes:
1. Add recording_id column to face_detection_events
2. Rename last_active to last_active_at in cameras table
"""

import sys
import os
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from database.session import get_db, engine
from sqlalchemy import text, inspect


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database():
    """Apply database migrations"""
    print("=" * 60)
    print("OpenEye Database Migration - v3.5.2")
    print("=" * 60)
    
    db = next(get_db())
    
    try:
        # Migration 1: Add recording_id to face_detection_events
        print("\n[1/2] Checking face_detection_events.recording_id...")
        if not check_column_exists('face_detection_events', 'recording_id'):
            print("  → Adding recording_id column...")
            db.execute(text("""
                ALTER TABLE face_detection_events 
                ADD COLUMN recording_id INTEGER REFERENCES recording_events(id)
            """))
            print("  → Creating index on recording_id...")
            db.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_face_detection_events_recording_id 
                ON face_detection_events(recording_id)
            """))
            db.commit()
            print("  ✅ recording_id column added and indexed")
        else:
            print("  ℹ️  recording_id column already exists - skipping")
        
        # Migration 2: Rename last_active to last_active_at in cameras
        print("\n[2/2] Checking cameras.last_active_at...")
        if not check_column_exists('cameras', 'last_active_at'):
            if check_column_exists('cameras', 'last_active'):
                print("  → Renaming last_active to last_active_at...")
                db.execute(text("""
                    ALTER TABLE cameras 
                    RENAME COLUMN last_active TO last_active_at
                """))
                db.commit()
                print("  ✅ Column renamed successfully")
            else:
                print("  ⚠️  Neither last_active nor last_active_at exists - skipping")
        else:
            print("  ℹ️  last_active_at column already exists - skipping")
        
        print("\n" + "=" * 60)
        print("✅ Database migration completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def verify_migrations():
    """Verify migrations were applied correctly"""
    print("\n" + "=" * 60)
    print("Verifying Migrations")
    print("=" * 60)
    
    inspector = inspect(engine)
    
    # Check face_detection_events
    print("\n[face_detection_events table]")
    columns = {col['name']: col for col in inspector.get_columns('face_detection_events')}
    if 'recording_id' in columns:
        print(f"  ✅ recording_id: {columns['recording_id']['type']}")
    else:
        print("  ❌ recording_id: MISSING")
    
    # Check cameras
    print("\n[cameras table]")
    columns = {col['name']: col for col in inspector.get_columns('cameras')}
    if 'last_active_at' in columns:
        print(f"  ✅ last_active_at: {columns['last_active_at']['type']}")
    else:
        print("  ❌ last_active_at: MISSING")
    
    if 'last_active' in columns:
        print("  ⚠️  last_active: STILL EXISTS (should be renamed)")
    
    # Check indexes
    print("\n[Indexes]")
    indexes = inspector.get_indexes('face_detection_events')
    recording_id_indexed = any('recording_id' in idx['column_names'] for idx in indexes)
    if recording_id_indexed:
        print("  ✅ recording_id is indexed")
    else:
        print("  ❌ recording_id index MISSING")
    
    print("\n" + "=" * 60)


if __name__ == '__main__':
    try:
        migrate_database()
        verify_migrations()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
