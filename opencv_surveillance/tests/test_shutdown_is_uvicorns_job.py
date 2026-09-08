# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Importing the application must not hijack process signals.

backend/main.py registered a module-level SIGINT/SIGTERM handler at import time
whose body was `sys.exit(0)`. It was dead in every real deployment and wrong in
any case where it was not:

  * Dead, because uvicorn installs its own handlers when it starts serving in
    the main thread, replacing it. Measured: the SIGTERM handler is `handle_exit`
    — uvicorn's — while the server runs.
  * Wrong if it ever did fire, because sys.exit raises SystemExit, which unwinds
    immediately and never reaches @app.on_event("shutdown") — the handler that
    closes WebSockets, stops the audio manager and disposes the database engine.
    Bypassing it is exactly the resource leak it exists to prevent.

Worth recording how this was established, because the obvious test is wrong:
running uvicorn on a background thread shows the module handler still installed,
since Python refuses to install signal handlers off the main thread and
uvicorn's registration silently does not happen. That reading suggested the
handler was live. Running uvicorn in the MAIN thread, as deployment does, shows
it replaced.
"""

import signal

import pytest


def test_importing_the_app_installs_no_signal_handler():
    """
    Importing a module should not change process-wide signal disposition.

    conftest has already imported backend.main by the time this runs, so this
    observes the real post-import state.
    """
    import backend.main  # noqa: F401

    for sig in (signal.SIGINT, signal.SIGTERM):
        handler = signal.getsignal(sig)
        name = getattr(handler, "__name__", None)
        assert name != "signal_handler", (
            f"backend.main installed a {sig.name} handler at import. uvicorn "
            "owns these; a module-level handler either does nothing or bypasses "
            "the shutdown event."
        )


def test_the_module_no_longer_defines_one():
    import backend.main as main

    assert not hasattr(main, "signal_handler"), (
        "signal_handler is back; it bypasses @app.on_event('shutdown')"
    )


def test_the_shutdown_event_is_still_registered():
    """
    Removing the handler must not remove the actual cleanup.

    This is the half that does the work: closing WebSockets, stopping audio,
    disposing the database engine.
    """
    import backend.main as main

    assert main.app.router.on_shutdown, "no shutdown handler is registered"
    names = [getattr(fn, "__name__", "") for fn in main.app.router.on_shutdown]
    assert any("shutdown" in n for n in names), (
        f"expected a shutdown handler among {names}"
    )


def test_the_reloader_is_not_on_by_default():
    """
    An unconditional --reload is destructive on a source checkout.

    paths.is_source_checkout() resolves DATA_ROOT to the application directory,
    so recordings, snapshots and the database are written inside the tree the
    reloader watches: every captured event restarted the server mid-recording.
    """
    import pathlib
    import re

    source = pathlib.Path(__file__).resolve().parents[1] / "backend/main.py"
    text = source.read_text()

    assert not re.search(r"^\s*reload=True", text, re.M), (
        "uvicorn.run is called with reload=True unconditionally"
    )
    assert "OPENEYE_DEV_RELOAD" in text, (
        "the reloader should be opt-in via OPENEYE_DEV_RELOAD"
    )
    assert "reload_dirs" in text, (
        "when enabled, the watch must be confined to the code directory"
    )
