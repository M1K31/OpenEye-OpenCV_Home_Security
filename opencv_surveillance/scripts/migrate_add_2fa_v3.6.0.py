#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Database Migration: Add 2FA Support to User Model
Version: 3.6.0
Date: 2025-10-24

Adds two-factor authentication fields to users table
"""

import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text, inspect
from backend.database.session import engine, SessionLocal
from backend.database.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_add_2fa_fields():
    """Add 2FA fields to users table"""
    logger.info("=" * 70)
    logger.info("DATABASE MIGRATION: Add 2FA Support")
    logger.info("=" * 70)

    db = SessionLocal()
    try:
        # Check if columns already exist
        if check_column_exists('users', 'totp_secret'):
            logger.info("✓ 2FA fields already exist, skipping migration")
            return

        logger.info("Adding 2FA fields to users table...")

        # Add 2FA fields
        with engine.begin() as conn:
            # TOTP secret (encrypted)
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN totp_secret VARCHAR"
            ))
            logger.info("✓ Added totp_secret column")

            # 2FA enabled flag
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT FALSE"
            ))
            logger.info("✓ Added two_factor_enabled column")

            # Backup codes (JSON array of hashed codes)
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN backup_codes VARCHAR"
            ))
            logger.info("✓ Added backup_codes column")

            # 2FA enrollment date
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN two_factor_enrolled_at TIMESTAMP"
            ))
            logger.info("✓ Added two_factor_enrolled_at column")

        logger.info("=" * 70)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"✗ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    try:
        migrate_add_2fa_fields()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
