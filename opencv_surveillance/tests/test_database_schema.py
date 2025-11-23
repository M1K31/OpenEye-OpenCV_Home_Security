# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Test to debug database schema creation
"""

import pytest
from sqlalchemy import inspect


def test_database_tables_created(db_session):
    """Check which tables are created in test database"""
    inspector = inspect(db_session.bind)
    tables = inspector.get_table_names()

    print("\n=== Tables created in test database ===")
    for table in sorted(tables):
        print(f"  - {table}")

    print("\n=== Checking for refresh_tokens table ===")
    if "refresh_tokens" in tables:
        print("  ✅ refresh_tokens table EXISTS")
    else:
        print("  ❌ refresh_tokens table MISSING")

    # Check Base.metadata
    from backend.database.session import Base
    print("\n=== Tables in Base.metadata ===")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")

    # Verify RefreshToken model
    from backend.database.models import RefreshToken
    print(f"\n=== RefreshToken model ===")
    print(f"  Table name: {RefreshToken.__tablename__}")
    print(f"  Mapped: {hasattr(RefreshToken, '__mapper__')}")

    assert "users" in tables, "Users table should exist"
