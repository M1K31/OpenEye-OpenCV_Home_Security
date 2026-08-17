# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Debug test to trace database session usage
"""

import pytest


def test_session_identity(db_session):
    """Verify which database session is being used"""
    from sqlalchemy import inspect

    # Get the engine URL
    engine = db_session.bind
    print(f"\n=== Database Session Info ===")
    print(f"Engine: {engine}")
    print(f"URL: {engine.url}")
    print(f"Dialect: {engine.dialect.name}")

    # Check if it's in-memory SQLite
    if str(engine.url) == "sqlite:///:memory:":
        print("✅ Using in-memory test database")
    else:
        print(f"❌ Using file database: {engine.url}")

    # Check tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\nTables in this database: {len(tables)}")
    print(f"Has refresh_tokens: {'refresh_tokens' in tables}")


def test_user_session_binding(db_session, test_user):
    """Verify user object is bound to test session"""
    from sqlalchemy import inspect as sqlalchemy_inspect

    print(f"\n=== User Object Session Binding ===")
    print(f"User ID: {test_user.id}")
    print(f"User username: {test_user.username}")

    # Check which session the user is bound to
    user_state = sqlalchemy_inspect(test_user)
    print(f"User session: {user_state.session}")
    print(f"Test session: {db_session}")
    print(f"Same session: {user_state.session is db_session}")

    # Check the user session's engine
    if user_state.session:
        user_engine = user_state.session.bind
        test_engine = db_session.bind
        print(f"\nUser engine: {user_engine}")
        print(f"Test engine: {test_engine}")
        print(f"Same engine: {user_engine is test_engine}")
        print(f"User engine URL: {user_engine.url}")
        print(f"Test engine URL: {test_engine.url}")


def test_login_session_trace(client, test_user, db_session):
    """Trace which session is used during login"""
    print(f"\n=== Login Session Trace ===")
    print(f"Test database URL: {db_session.bind.url}")

    # Attempt login
    response = client.post(
        "/api/auth/login-2fa",
        json={"username": "testuser", "password": "Testpass123!"}
    )

    print(f"Response status: {response.status_code}")
    if response.status_code != 200:
        print(f"Response body: {response.json()}")
    else:
        print(f"Login successful!")
        data = response.json()
        print(f"Has access_token: {'access_token' in data}")
        print(f"Has refresh_token: {'refresh_token' in data}")
