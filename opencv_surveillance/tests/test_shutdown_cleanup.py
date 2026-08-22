# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Shutdown must actually release the resources it claims to release.

Background
----------
The shutdown sequence is a deliberate nine-step teardown and reads as though it
works. Two of its steps had been failing on every single shutdown since the
names they import were moved:

    from backend.core.cloud_storage_system import cloud_storage   # no such name
    from backend.database import engine                           # lives in .session

Each step is wrapped in ``except Exception``, which turned a structural error
into a log line, so the process still exited and nobody noticed. The cost was
real: ``engine.dispose()`` never ran, so database connections were torn down by
process death rather than closed.

These tests assert the observable outcome — dispose was called, and no step
failed on an import — rather than the shape of the code, so a future refactor
that moves the engine again still has to keep shutdown working.
"""

import logging

import pytest

from backend import main as main_module


@pytest.mark.asyncio
async def test_shutdown_disposes_the_database_engine(monkeypatch):
    """engine.dispose() must actually be called during shutdown."""
    disposed = {"count": 0}

    class _Engine:
        def dispose(self):
            disposed["count"] += 1

    monkeypatch.setattr("backend.database.session.engine", _Engine())

    await main_module.shutdown_event()

    assert disposed["count"] == 1, (
        "engine.dispose() was not called during shutdown; database connections "
        "are being closed by process death instead of released cleanly"
    )


@pytest.mark.asyncio
async def test_shutdown_has_no_failing_imports(monkeypatch, caplog):
    """
    No shutdown step may fail on an ImportError.

    A step that cannot import what it needs is dead code pretending to be
    cleanup. Catching it here means the next rename is caught in CI rather than
    discovered months later in a shutdown log.
    """
    caplog.set_level(logging.ERROR)

    await main_module.shutdown_event()

    import_failures = [
        record.getMessage()
        for record in caplog.records
        if "cannot import name" in record.getMessage()
        or "ImportError" in record.getMessage()
        or "ModuleNotFoundError" in record.getMessage()
    ]

    assert not import_failures, (
        "shutdown steps failed on imports:\n  " + "\n  ".join(import_failures)
    )
