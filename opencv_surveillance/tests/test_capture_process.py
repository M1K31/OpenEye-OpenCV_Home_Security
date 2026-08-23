# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A capture crash must kill a worker, not the security system.

These tests use a fake capture rather than a camera, and one of them deliberately
segfaults a child process. That is the point: the in-process fixes closed every
crash path we could find, but the fault lives in C code Python cannot inspect, so
the only durable guarantee is that the crash happens somewhere disposable.

If the isolation is broken, `test_a_segfaulting_worker_does_not_kill_the_parent`
does not fail — the test runner dies. That is a louder signal than an assertion,
and an accurate reproduction of what used to happen to the server.
"""

import os
import time

import numpy as np
import pytest

from backend.core import capture_process
from backend.core.capture_process import CaptureClient
from tests import fake_capture


SEGFAULT_TESTS_ENABLED = os.getenv("OPENEYE_RUN_SEGFAULT_TESTS", "").lower() in ("1", "true", "yes")

needs_segfault = pytest.mark.skipif(
    not SEGFAULT_TESTS_ENABLED,
    reason=(
        "Deliberately crashes a child process. macOS files a crash report and "
        "shows a 'Python quit unexpectedly' dialog every time, which is "
        "indistinguishable at a glance from the production crash this project "
        "is fixing — it caused two false alarms on 2026-08-22. "
        "Run with OPENEYE_RUN_SEGFAULT_TESTS=1 when you want the containment "
        "proof; CI should set it."
    ),
)


def _configure_fake(monkeypatch, frames=1000, then="fail", size="48x64"):
    """
    Point the capture worker at the fake, via the environment.

    The child is spawned, so it re-imports everything by name — configuration
    has to travel through the environment, which the child inherits, rather than
    through patched objects, which it does not.
    """
    monkeypatch.setenv(capture_process.CAPTURE_FACTORY_ENV, "tests.fake_capture:open_fake")
    monkeypatch.setenv(fake_capture.FRAMES_ENV, str(frames))
    monkeypatch.setenv(fake_capture.THEN_ENV, then)
    monkeypatch.setenv(fake_capture.SIZE_ENV, size)


def _wait_for_frame(client, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ok, frame = client.read()
        if ok:
            return frame
        time.sleep(0.05)
    return None


def test_frames_cross_the_process_boundary(monkeypatch):
    """The parent receives real pixel data produced in the child."""
    _configure_fake(monkeypatch, frames=1000)
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    assert client.start()
    try:
        frame = _wait_for_frame(client)
        assert frame is not None, "no frame arrived from the capture worker"
        assert frame.shape == (48, 64, 3)
        assert frame.dtype == np.uint8
    finally:
        client.stop()


def test_read_only_returns_new_frames(monkeypatch):
    """A second read with no new frame reports nothing, rather than repeating."""
    _configure_fake(monkeypatch, frames=1000)
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=2)
    assert client.start()
    try:
        assert _wait_for_frame(client) is not None
        ok, _ = client.read()          # immediately again, before the next tick
        assert ok is False
    finally:
        client.stop()


@needs_segfault
def test_a_segfaulting_worker_does_not_kill_the_parent(monkeypatch):
    """
    The whole point. A SIGSEGV in capture must be survivable.

    Before this isolation existed, the equivalent crash ended the server: no
    shutdown lines, no traceback, just a process that was gone. Here the parent
    keeps running and can observe how the child died.
    """
    _configure_fake(monkeypatch, frames=3, then="segfault")
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    assert client.start()
    try:
        assert _wait_for_frame(client) is not None, "worker produced nothing before crashing"

        deadline = time.time() + 15
        while client.is_alive() and time.time() < deadline:
            time.sleep(0.1)

        assert not client.is_alive(), "worker was expected to crash and did not"

        exit_code = client._process.exitcode if client._process else None
        assert exit_code is not None and exit_code < 0, (
            f"expected death by signal, got exit code {exit_code}"
        )
        # Reaching this line at all is the assertion that matters: the parent
        # survived a SIGSEGV in capture.
    finally:
        client.stop()


@needs_segfault
def test_a_dead_worker_is_restarted(monkeypatch):
    """A crashed worker is replaced, which is what makes the crash survivable."""
    _configure_fake(monkeypatch, frames=3, then="segfault")
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    assert client.start()
    try:
        assert _wait_for_frame(client) is not None

        deadline = time.time() + 15
        while client.is_alive() and time.time() < deadline:
            time.sleep(0.1)
        assert not client.is_alive()

        assert client.needs_restart() is True
        client._next_restart_allowed = 0        # skip backoff for the test
        assert client.restart_if_needed() is True
        assert client.restart_count == 1
        assert client.is_alive(), "a replacement worker should be running"
    finally:
        client.stop()


def test_a_wedged_worker_counts_as_needing_restart(monkeypatch):
    """
    A worker that stops delivering is as bad as one that died.

    This is the 22:49 failure in miniature: the capture reported healthy and
    delivered nothing for fourteen hours. Liveness has to mean frames arriving.
    """
    _configure_fake(monkeypatch, frames=2, then="hang")
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    monkeypatch.setattr(CaptureClient, "STALL_TIMEOUT", 1.0)
    assert client.start()
    try:
        assert _wait_for_frame(client) is not None
        time.sleep(1.5)
        assert client.needs_restart() is True, (
            "a worker delivering no frames must be considered unhealthy"
        )
    finally:
        client.stop()


def test_stop_releases_shared_memory(monkeypatch):
    """Shared memory must not leak — a camera restarting all day would exhaust it."""
    _configure_fake(monkeypatch, frames=1000)
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    assert client.start()
    name = client._shm.name
    _wait_for_frame(client)
    client.stop()

    from multiprocessing.shared_memory import SharedMemory
    with pytest.raises(FileNotFoundError):
        SharedMemory(name=name)


def test_a_worker_that_never_opens_the_camera_is_eventually_restarted(monkeypatch):
    """
    A worker that produces nothing must not be left alive forever.

    needs_restart() previously returned False whenever no frame had ever
    arrived, to allow for a slow device open. That grace had no deadline, so a
    camera that failed to open left a worker running and useless with nothing to
    retry it — the exact "reports healthy, delivers nothing" shape this design
    is meant to eliminate.
    """
    _configure_fake(monkeypatch, frames=0, then="hang")
    monkeypatch.setattr(CaptureClient, "STALL_TIMEOUT", 1.0)
    client = CaptureClient(source="0", camera_id="test_cam", target_fps=30)
    assert client.start()
    try:
        assert client.needs_restart() is False, "should be given a startup grace"
        time.sleep(1.5)
        assert client.needs_restart() is True, (
            "a worker that never produced a frame must eventually be replaced"
        )
    finally:
        client.stop()
