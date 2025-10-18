#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database migration: Add automation_rules table

This migration creates a new table to store person-based automation rules.
These rules trigger actions (notifications, recordings, webhooks) when specific
people are detected by the face recognition system.

Run this script from the project root:
    python backend/database/migrations/add_automation_rules.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from backend.database.session import SQLALCHEMY_DATABASE_URL


def upgrade():
    """Add automation_rules table"""
    print("\n" + "="*60)
    print("Migration: Add automation_rules table")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Create automation_rules table
        print("📝 Creating automation_rules table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS automation_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                person_name TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                
                -- Conditions (JSON string)
                conditions TEXT,
                
                -- Actions (JSON array string)
                actions TEXT NOT NULL,
                
                -- Cooldown configuration
                cooldown_seconds INTEGER DEFAULT 300,
                last_triggered_at TIMESTAMP,
                
                -- Metadata
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                trigger_count INTEGER DEFAULT 0
            )
        """))
        
        # Create indexes for performance
        print("📝 Creating indexes...")
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_automation_person_name 
            ON automation_rules(person_name)
        """))
        print("   ✅ Index on person_name")
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_automation_enabled 
            ON automation_rules(enabled)
        """))
        print("   ✅ Index on enabled")
        
        conn.commit()
        
        print("\n✅ automation_rules table created successfully")
        print("\nTable schema:")
        print("  - Stores automation rules for specific people")
        print("  - Supports conditional triggers (cameras, time ranges)")
        print("  - Actions: notifications, recordings, webhooks")
        print("  - Cooldown period prevents spam")
        print("  - Tracks trigger count and last execution")
        print("\n" + "="*60 + "\n")


def downgrade():
    """Remove automation_rules table"""
    print("\n" + "="*60)
    print("Rollback: Remove automation_rules table")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🗑️  Dropping automation_rules table...")
        conn.execute(text("DROP TABLE IF EXISTS automation_rules"))
        conn.commit()
        
        print("✅ automation_rules table removed successfully")
        print("\n" + "="*60 + "\n")


def verify():
    """Verify the migration was successful"""
    print("\n" + "="*60)
    print("Verification: Check automation_rules table")
    print("="*60 + "\n")
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        # Check if table exists
        result = conn.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='automation_rules'
        """))
        
        if result.fetchone():
            print("✅ automation_rules table exists")
            
            # Check columns
            result = conn.execute(text("PRAGMA table_info(automation_rules)"))
            columns = result.fetchall()
            
            print(f"\n📊 Table has {len(columns)} columns:")
            for col in columns:
                print(f"   - {col[1]} ({col[2]})")
            
            # Check indexes
            result = conn.execute(text("PRAGMA index_list(automation_rules)"))
            indexes = result.fetchall()
            
            print(f"\n🔍 Table has {len(indexes)} indexes:")
            for idx in indexes:
                print(f"   - {idx[1]}")
            
            # Count rules
            result = conn.execute(text("SELECT COUNT(*) FROM automation_rules"))
            count = result.fetchone()[0]
            print(f"\n📈 Current rule count: {count}")
            
        else:
            print("❌ automation_rules table does NOT exist")
            return False
    
    print("\n" + "="*60 + "\n")
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Automation Rules Migration")
    parser.add_argument(
        "action",
        choices=["upgrade", "downgrade", "verify"],
        help="Migration action to perform"
    )
    
    args = parser.parse_args()
    
    try:
        if args.action == "upgrade":
            upgrade()
        elif args.action == "downgrade":
            downgrade()
        elif args.action == "verify":
            if not verify():
                sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}\n")
        sys.exit(1)
