# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Nothing outside the capture-owning thread may call VideoCapture.read().

Background
----------
OpenEye segfaulted twice on 2026-08-19/20 with identical stacks:

    objc_msgSend
    -[CaptureDelegate grabImageUntilDate:]
    cv::VideoCapture::read()
    thread: com.apple.main-thread

OpenCV's AVFoundation backend keeps a pointer to the capture device. macOS
invalidates that object when the device goes away, and the next read() messages
freed memory. The process dies instantly — a segfault is not a Python exception,
so no try/except can contain it.

The trigger was not the unplug. In the 22:49 crash nobody touched the camera: it
had been failing for 50,177 seconds and a human simply opened the dashboard,
which starts the MJPEG stream calling read() from the request thread. The 00:17
crash is the same shape reached through the reconnect-then-stream path.

So the invariant these tests protect is:

  1. Exactly one thread ever touches the capture.
  2. Once reads start failing, we stop calling read() entirely rather than
     retrying into freed memory. capture.isOpened() cannot be used to decide
     this — it returned True throughout both crashes.
  3. Request handlers read a published frame and never reach the capture.
"""

import threading

import numpy as np
import pytest

from backend.core.camera_manager import RTSPCamera


class FakeCapture:
    """
    Stands in for cv2.VideoCapture, counting reads so a test can prove that no
    further read happened after the capture was declared dead.

    isOpened() deliberately keeps returning True after failure starts, because
    that is exactly what the real capture did during both crashes.
    """

    def __init__(self, fail_after=None):
        self.read_count = 0
        self.release_count = 0
        self.fail_after = fail_after
        self._frame = np.zeros((48, 64, 3), dtype=np.uint8)

    def isOpened(self):
        return True

    def read(self):
        self.read_count += 1
        if self.fail_after is not None and self.read_count > self.fail_after:
            return False, None
        return True, self._frame.copy()

    def release(self):
        self.release_count += 1

    def set(self, *_args):
        return True

    def get(self, *_args):
        return 0


@pytest.fixture
def camera(monkeypatch):
    """An RTSPCamera wired to a fake capture, with no background thread."""
    cam = RTSPCamera(source="0", camera_id="test_cam", enable_face_detection=False)
    cam.is_running = True
    # The capture loop normally claims ownership when it starts. No thread runs
    # here, so claim it for whichever thread the test body is on.
    cam._capture_owner_thread = threading.get_ident()

    # Hold the FPS limiter open. It normally drops most calls, which would make
    # "how many reads happened" depend on wall-clock timing — these tests are
    # about what happens when a read fails, not about frame pacing.
    monkeypatch.setattr(cam.video_processor, "should_process_frame", lambda: True)
    return cam


def test_reads_stop_after_the_capture_is_declared_dead(camera):
    """
    Once reads fail consistently, read() must not be called again.

    This is the whole fix: the crash happened because failing reads kept being
    retried against a capture whose device had been freed.
    """
    capture = FakeCapture(fail_after=0)  # fails immediately
    camera.capture = capture

    for _ in range(40):
        camera.get_frame()

    assert camera.is_capture_dead(), "capture was never declared dead"
    assert capture.read_count <= RTSPCamera.FATAL_AFTER_FAILURES, (
        f"read() was called {capture.read_count} times; it must stop after "
        f"{RTSPCamera.FATAL_AFTER_FAILURES} consecutive failures"
    )


def test_dead_capture_is_released_exactly_once(camera):
    """Release the freed device once — repeated releases are their own hazard."""
    capture = FakeCapture(fail_after=0)
    camera.capture = capture

    for _ in range(40):
        camera.get_frame()

    assert capture.release_count == 1, (
        f"expected exactly one release, got {capture.release_count}"
    )


def test_get_frame_refuses_to_run_off_the_owning_thread(camera):
    """
    A call from any other thread must return without touching the capture.

    Both crashes came through com.apple.main-thread — a request handler, not the
    capture loop. Enforcing ownership in code is what stops a third caller being
    added later without anyone noticing.
    """
    capture = FakeCapture()
    camera.capture = capture
    camera._capture_owner_thread = threading.get_ident() + 1  # some other thread

    result = camera.get_frame()

    assert result == (None, False)
    assert capture.read_count == 0, (
        "get_frame() read from the capture on a non-owning thread"
    )


def test_published_frame_is_served_without_touching_the_capture(camera):
    """A consumer reads the published frame and never reaches the capture."""
    capture = FakeCapture()
    camera.capture = capture

    camera.get_frame()  # produces and publishes one frame
    reads_after_produce = capture.read_count

    for _ in range(10):
        published = camera.get_published_frame()
        assert published is not None

    assert capture.read_count == reads_after_produce, (
        "reading the published frame reached the capture"
    )


def test_published_frame_reports_its_age(camera):
    """
    Consumers need to know a frame is stale, not just present.

    Without this the stream would happily serve a frozen image forever, which is
    the failure mode the operator spent two days diagnosing: a dead camera that
    looked perfectly healthy.
    """
    capture = FakeCapture()
    camera.capture = capture
    camera.get_frame()

    assert camera.seconds_since_last_frame() is not None
    assert camera.seconds_since_last_frame() < 5


def test_no_published_frame_before_the_first_capture(camera):
    """A camera that has never produced a frame publishes nothing."""
    assert camera.get_published_frame() is None
    assert camera.seconds_since_last_frame() is None


def test_reopen_requires_a_real_frame_before_declaring_success(camera, monkeypatch):
    """
    A capture that opens but never delivers must be treated as a failure.

    This is the "reconnect LIES" defect: the endpoint reopened a capture, never
    read from it, and returned 200. The UI then opened the stream against a
    capture bound to a dead device — which is precisely what killed the process
    at 00:17.
    """
    dead_on_arrival = FakeCapture(fail_after=0)
    monkeypatch.setattr(
        "backend.core.camera_manager.cv2.VideoCapture",
        lambda *_a, **_k: dead_on_arrival,
    )
    monkeypatch.setattr("backend.core.camera_manager.time.sleep", lambda _s: None)

    camera._mark_capture_dead("test setup")
    assert camera._reopen_capture() is False
    assert camera.is_capture_dead(), (
        "a capture that delivered no frame was accepted as working"
    )


def test_reopen_succeeds_and_revives_the_camera(camera, monkeypatch):
    """A capture that does deliver a frame clears the dead flag."""
    healthy = FakeCapture()
    monkeypatch.setattr(
        "backend.core.camera_manager.cv2.VideoCapture",
        lambda *_a, **_k: healthy,
    )
    monkeypatch.setattr("backend.core.camera_manager.time.sleep", lambda _s: None)

    camera._mark_capture_dead("test setup")
    assert camera._reopen_capture() is True
    assert not camera.is_capture_dead()
    assert healthy.read_count >= 1, "reopen returned success without reading a frame"


def test_no_route_module_calls_get_frame():
    """
    No HTTP route may call camera.get_frame().

    The original crash report named one caller, the MJPEG stream. Fixing it
    revealed seven, across three route modules — and the eighth would have been
    written next month by someone who had never heard of this bug. Route
    handlers use backend/core/live_frame.py instead.

    A static check rather than a runtime one: this must fail in review, not in
    production at 00:17 when the camera is unplugged.
    """
    import ast
    import pathlib

    routes_dir = pathlib.Path(__file__).resolve().parent.parent / "backend" / "api" / "routes"

    # Parsed rather than grepped, so prose that merely mentions get_frame — such
    # as the comments explaining why not to call it — is not a false positive.
    offenders = []
    for path in sorted(routes_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get_frame"
            ):
                offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, (
        "Route handlers must not call get_frame() — it reaches "
        "cv2.VideoCapture.read() from a request thread, which segfaults the "
        "process when the device is gone. Use "
        "backend.core.live_frame.get_live_frame() instead.\n  "
        + "\n  ".join(offenders)
    )


def test_a_dead_capture_is_retried_on_a_schedule(camera, monkeypatch):
    """
    A capture marked dead must still be retried, on a time-based backoff.

    Regression: marking the capture dead stopped _note_frame_failure() from
    running, so _consecutive_failures froze at 3. The reconnect trigger was
    `failures % RECONNECT_AFTER_FAILURES == 0`, and 3 % 20 is never 0 — so a
    camera that was unplugged went dead and stayed dead until the process was
    restarted. Confirmed against real hardware on 2026-08-22: the guard fired
    correctly and then nothing ever retried.

    Recovery must not depend on a counter that stops counting.
    """
    camera._mark_capture_dead("test")
    assert camera.is_capture_dead()

    attempts = {"n": 0}

    def _fake_reopen():
        attempts["n"] += 1
        return False          # still unplugged

    monkeypatch.setattr(camera, "_reopen_capture", _fake_reopen)

    # First call: the backoff has never been armed, so a retry is due now.
    assert camera._maybe_reopen_dead_capture() is True
    assert attempts["n"] == 1

    # Immediately after, the backoff must suppress a retry.
    assert camera._maybe_reopen_dead_capture() is False
    assert attempts["n"] == 1

    # Once the backoff elapses, it retries again.
    camera._next_reopen_attempt = 0
    assert camera._maybe_reopen_dead_capture() is True
    assert attempts["n"] == 2


def test_reopen_backoff_grows_and_is_capped(camera, monkeypatch):
    """Retrying an absent camera must not become a spin loop."""
    camera._mark_capture_dead("test")
    monkeypatch.setattr(camera, "_reopen_capture", lambda: False)

    delays = []
    for _ in range(8):
        camera._next_reopen_attempt = 0
        camera._maybe_reopen_dead_capture()
        delays.append(camera._reopen_backoff)

    assert delays == sorted(delays), "backoff should grow monotonically"
    assert max(delays) <= camera.RECONNECT_BACKOFF_MAX
