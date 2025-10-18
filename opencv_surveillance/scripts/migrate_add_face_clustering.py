#!/usr/bin/env python3
"""
Database Migration Script: Add Face Clustering Support
Version: 3.6.0
Date: October 16, 2025

This script adds the necessary database schema changes for the Face Clustering feature:
1. Creates face_clusters table
2. Adds face_encoding column to face_detection_events
3. Adds cluster_id column to face_detection_events
4. Creates indexes for performance
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from backend.database.session import SQLALCHEMY_DATABASE_URL, Base, engine
from backend.database.models import FaceCluster, FaceDetectionEvent
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database"""
    with engine.connect() as conn:
        if 'sqlite' in str(engine.url):
            result = conn.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            ))
        else:  # PostgreSQL
            result = conn.execute(text(
                f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')"
            ))
        return result.fetchone() is not None


def check_column_exists(engine, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    with engine.connect() as conn:
        if 'sqlite' in str(engine.url):
            result = conn.execute(text(f"PRAGMA table_info({table_name})"))
            columns = [row[1] for row in result.fetchall()]
            return column_name in columns
        else:  # PostgreSQL
            result = conn.execute(text(
                f"SELECT column_name FROM information_schema.columns "
                f"WHERE table_name='{table_name}' AND column_name='{column_name}'"
            ))
            return result.fetchone() is not None


def migrate_database():
    """Run the migration"""
    logger.info("=" * 70)
    logger.info("Face Clustering Database Migration v3.6.0")
    logger.info("=" * 70)
    logger.info(f"Database URL: {SQLALCHEMY_DATABASE_URL}")
    logger.info("")
    
    try:
        # Check if face_clusters table already exists
        if check_table_exists(engine, 'face_clusters'):
            logger.warning("⚠️  face_clusters table already exists, skipping table creation")
        else:
            logger.info("Creating face_clusters table...")
            with engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE face_clusters (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        label VARCHAR(255),
                        is_identified BOOLEAN DEFAULT 0,
                        face_count INTEGER DEFAULT 0,
                        avg_confidence FLOAT,
                        representative_encoding TEXT,
                        representative_snapshot_path VARCHAR(500),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen_at TIMESTAMP,
                        clustering_algorithm VARCHAR(50) DEFAULT 'dbscan',
                        clustering_params TEXT
                    )
                """))
                conn.commit()
            logger.info("✅ face_clusters table created")
        
        # Check and add face_encoding column
        if check_column_exists(engine, 'face_detection_events', 'face_encoding'):
            logger.warning("⚠️  face_encoding column already exists, skipping")
        else:
            logger.info("Adding face_encoding column to face_detection_events...")
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE face_detection_events ADD COLUMN face_encoding TEXT"
                ))
                conn.commit()
            logger.info("✅ face_encoding column added")
        
        # Check and add cluster_id column
        if check_column_exists(engine, 'face_detection_events', 'cluster_id'):
            logger.warning("⚠️  cluster_id column already exists, skipping")
        else:
            logger.info("Adding cluster_id column to face_detection_events...")
            with engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE face_detection_events ADD COLUMN cluster_id INTEGER"
                ))
                conn.commit()
            logger.info("✅ cluster_id column added")
        
        # Create indexes
        logger.info("Creating indexes...")
        with engine.connect() as conn:
            try:
                # Index on cluster_id for joins
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_face_detection_events_cluster_id "
                    "ON face_detection_events(cluster_id)"
                ))
                
                # Index on unknown faces with encodings (for clustering queries)
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_face_detection_events_unknown "
                    "ON face_detection_events(person_name, face_encoding) "
                    "WHERE person_name = 'Unknown' AND face_encoding IS NOT NULL"
                ))
                
                # Indexes on face_clusters
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_face_clusters_is_identified "
                    "ON face_clusters(is_identified)"
                ))
                
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_face_clusters_last_seen "
                    "ON face_clusters(last_seen_at DESC)"
                ))
                
                conn.commit()
                logger.info("✅ Indexes created")
            except Exception as e:
                logger.warning(f"⚠️  Some indexes may already exist: {e}")
        
        # Verify migration
        logger.info("")
        logger.info("Verifying migration...")
        
        # Check tables
        face_clusters_exists = check_table_exists(engine, 'face_clusters')
        logger.info(f"  face_clusters table: {'✅ EXISTS' if face_clusters_exists else '❌ MISSING'}")
        
        # Check columns
        face_encoding_exists = check_column_exists(engine, 'face_detection_events', 'face_encoding')
        cluster_id_exists = check_column_exists(engine, 'face_detection_events', 'cluster_id')
        
        logger.info(f"  face_encoding column: {'✅ EXISTS' if face_encoding_exists else '❌ MISSING'}")
        logger.info(f"  cluster_id column: {'✅ EXISTS' if cluster_id_exists else '❌ MISSING'}")
        
        # Count records
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM face_detection_events"))
            total_faces = result.fetchone()[0]
            
            result = conn.execute(text(
                "SELECT COUNT(*) FROM face_detection_events WHERE person_name = 'Unknown'"
            ))
            unknown_faces = result.fetchone()[0]
            
            result = conn.execute(text("SELECT COUNT(*) FROM face_clusters"))
            cluster_count = result.fetchone()[0]
        
        logger.info("")
        logger.info("Database Statistics:")
        logger.info(f"  Total face detections: {total_faces}")
        logger.info(f"  Unknown faces: {unknown_faces}")
        logger.info(f"  Face clusters: {cluster_count}")
        
        # Success
        logger.info("")
        logger.info("=" * 70)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 70)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Restart the backend server")
        logger.info("2. Test clustering with: POST /api/clusters/cluster")
        logger.info("3. View clusters with: GET /api/clusters/")
        logger.info("")
        
        return True
        
    except Exception as e:
        logger.error("")
        logger.error("=" * 70)
        logger.error("❌ Migration failed!")
        logger.error("=" * 70)
        logger.error(f"Error: {e}")
        logger.error("")
        logger.error("To rollback (if needed):")
        logger.error("1. Drop face_clusters table: DROP TABLE face_clusters;")
        logger.error("2. Remove columns: ALTER TABLE face_detection_events DROP COLUMN face_encoding;")
        logger.error("3. Remove columns: ALTER TABLE face_detection_events DROP COLUMN cluster_id;")
        logger.error("")
        return False


def rollback_migration():
    """Rollback the migration"""
    logger.info("=" * 70)
    logger.info("Rolling back Face Clustering migration...")
    logger.info("=" * 70)
    
    try:
        with engine.connect() as conn:
            # SQLite doesn't support DROP COLUMN, so we need to backup and recreate
            logger.info("⚠️  WARNING: SQLite doesn't support DROP COLUMN")
            logger.info("⚠️  Manual rollback required if needed")
            logger.info("")
            logger.info("To manually rollback:")
            logger.info("1. DROP TABLE face_clusters;")
            logger.info("2. Recreate face_detection_events without new columns")
            logger.info("")
            
            # We can at least drop the table
            conn.execute(text("DROP TABLE IF EXISTS face_clusters"))
            conn.commit()
            logger.info("✅ face_clusters table dropped")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Face Clustering Database Migration')
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback the migration'
    )
    
    args = parser.parse_args()
    
    if args.rollback:
        success = rollback_migration()
    else:
        success = migrate_database()
    
    sys.exit(0 if success else 1)
