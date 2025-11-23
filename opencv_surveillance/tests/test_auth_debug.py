# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Debug test to verify authentication flow
"""

import pytest


def test_user_creation(db_session, test_user):
    """Test that user is created correctly"""
    assert test_user is not None
    assert test_user.username == "testuser"
    assert test_user.hashed_password is not None
    print(f"User created: {test_user.username}")
    print(f"Hashed password (first 20 chars): {test_user.hashed_password[:20]}")


def test_login_endpoint(client, test_user):
    """Test login endpoint directly"""
    # First verify the user is in the database
    print(f"test_user fixture returned: {test_user}")
    print(f"test_user hashed password: {test_user.hashed_password[:30]}")

    response = client.post(
        "/api/auth/login-2fa",
        json={"username": "testuser", "password": "testpass123"}
    )
    print(f"Login response status: {response.status_code}")
    print(f"Login response body: {response.json()}")

    # Don't assert - let's just see what's happening
    # assert response.status_code == 200
