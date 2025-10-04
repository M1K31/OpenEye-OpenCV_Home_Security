import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.session import Base


@pytest.fixture(scope="session")
def engine():
    # session-scoped engine for fast tests; use in-memory SQLite
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


@pytest.fixture
def db_session(engine):
    # create fresh schema for each test function
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def patch_hashing_if_needed(monkeypatch):
    """
    Optional fixture for CI environments where bcrypt/passlib isn't available.
    Use by naming `patch_hashing_if_needed` in your test signature. It will replace
    get_password_hash and verify_password with simple deterministic functions.
    """
    try:
        # try importing real functions; if present, do nothing
        from backend.core.security import get_password_hash as _get_hash  # noqa: F401
        from backend.core.security import verify_password as _verify  # noqa: F401
        return
    except Exception:
        import backend.database.crud as crud_mod
        import backend.core.auth as auth_mod

        monkeypatch.setattr(crud_mod, 'get_password_hash', lambda p: 'hashed-' + p)
        monkeypatch.setattr(auth_mod, 'verify_password', lambda plain, hashed: hashed == 'hashed-' + plain)
        return
