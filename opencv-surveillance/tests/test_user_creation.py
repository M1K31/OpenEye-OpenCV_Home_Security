# Auto-generated test for user creation and authentication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from backend.database import models, crud
from backend.database.session import Base
from backend.api.schemas import user as user_schema
from backend.core import auth
from backend.core.security import verify_password


# use `db_session` fixture from tests/conftest.py


def test_create_and_authenticate_user(db_session, patch_hashing_if_needed):
    db = db_session
    # create a user schema (use real hashing backend)
    user_in = user_schema.UserCreate(username="testuser", email="test@example.com", password="secret")
    created = crud.create_user(db=db, user=user_in)

    assert created.id is not None
    assert created.username == "testuser"
    assert created.email == "test@example.com"
    assert created.hashed_password != "secret"
    assert verify_password("secret", created.hashed_password)

    # authenticate via auth.authenticate_user
    authed = auth.authenticate_user(db, "testuser", "secret")
    assert authed is not False
    assert authed.username == "testuser"

    # wrong password should fail
    bad = auth.authenticate_user(db, "testuser", "wrong")
    assert bad is False

    # token creation
    token = auth.create_access_token({"sub": authed.username})
    assert isinstance(token, str)
