#!/usr/bin/env python3
"""
Database Migration: Add Notification Providers Table

This migration adds the `notification_providers` table to support
in-app configuration of email, SMS, push, and other notification channels.

Includes automated encryption key setup.

Version: 3.7.0
Date: 2025-01-24
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database.session import engine, SessionLocal
from backend.database.alert_models import NotificationProvider
from sqlalchemy import inspect, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def setup_encryption_key():
    """Setup encryption key by calling the setup script"""
    logger.info("\n" + "=" * 70)
    logger.info("Step 1: Setting up encryption key")
    logger.info("=" * 70)

    try:
        # Import the setup function
        from setup_notification_encryption import setup_encryption_key as setup_key
        key = setup_key()
        return key
    except Exception as e:
        logger.error(f"Failed to setup encryption key: {e}")
        logger.info("\nYou can manually run:")
        logger.info("  python3 scripts/setup_notification_encryption.py")
        return None


def migrate():
    """Run the migration"""
    logger.info("=" * 70)
    logger.info("Database Migration: Add Notification Providers Table")
    logger.info("=" * 70)

    # Step 1: Setup encryption key (if needed)
    setup_encryption_key()

    # Step 2: Create database table
    logger.info("\n" + "=" * 70)
    logger.info("Step 2: Creating database table")
    logger.info("=" * 70)

    if table_exists("notification_providers"):
        logger.warning("⚠️  Table 'notification_providers' already exists!")
        logger.info("Migration skipped - database is up to date.")
        return

    try:
        logger.info("Creating 'notification_providers' table...")

        # Create table using SQLAlchemy model
        NotificationProvider.__table__.create(engine)

        logger.info("✅ Table 'notification_providers' created successfully!")

        # Verify table creation
        if table_exists("notification_providers"):
            logger.info("✅ Table created successfully!")

            logger.info("\n" + "=" * 70)
            logger.info("✅ Migration Completed Successfully!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("Next Steps:")
            logger.info("  1. Restart the backend server")
            logger.info("  2. Navigate to Settings → Notifications")
            logger.info("  3. Configure your notification providers")
            logger.info("")
            logger.info("Available Notification Types:")
            logger.info("  📧 Email (SMTP)      - Gmail, Outlook, custom servers")
            logger.info("  📱 SMS (Twilio)      - Text message notifications")
            logger.info("  🔔 Push (FCM)        - Firebase Cloud Messaging")
            logger.info("  ✈️  Telegram Bot     - Telegram messages")
            logger.info("  💬 Discord Webhook   - Discord channel notifications")
            logger.info("  🔗 Custom Webhook    - Any HTTP endpoint")
            logger.info("=" * 70)

        else:
            logger.error("❌ Table creation failed - table not found after creation")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    migrate()
