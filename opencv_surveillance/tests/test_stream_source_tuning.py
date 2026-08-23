# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Timings tuned for a USB device must not be applied to a network stream.

Background
----------
The capture recovery logic was written against a USB webcam, where a failed read
means the device is gone and a reopen completes in well under a second. Those
assumptions are wrong for RTSP:

* A network stall produces a handful of failed reads and then recovers by
  itself. Declaring the capture dead after three, as a local device requires,
  would release and reopen a perfectly healthy stream on every hiccup.

* A reopen needs a TCP connect, an RTSP handshake and then a keyframe before the
  first frame arrives — commonly several seconds. The two-second proof window
  used for a local device would judge every RTSP reopen a failure, discard a
  working capture and reconnect forever.

The second is the dangerous one: it does not degrade behaviour, it prevents
recovery outright.

The two backends are genuinely different. A numeric source opens through
AVFoundation on macOS; a URL opens through FFmpeg (CAP_FFMPEG). The
use-after-free that motivated the aggressive local timings lives in
AVFoundation's CaptureDelegate and has no counterpart in the FFmpeg path.
"""

import pytest

from backend.core.camera_manager import RTSPCamera


def _camera(source):
    return RTSPCamera(source=source, camera_id="c", enable_face_detection=False)


@pytest.mark.parametrize("source", ["0", "1", 0, 2])
def test_numeric_sources_are_local_devices(source):
    """A device index is a local capture, whatever its type."""
    assert _camera(source)._is_stream_source() is False


@pytest.mark.parametrize("source", [
    "rtsp://192.168.1.50:554/stream1",
    "http://camera.local/video.mjpg",
    "/dev/video0",
])
def test_urls_and_paths_are_stream_sources(source):
    """Anything that is not an index goes through FFmpeg and is treated as a stream."""
    assert _camera(source)._is_stream_source() is True


def test_a_local_device_keeps_the_aggressive_failure_threshold():
    """
    A vanished USB device must be released fast — that is the crash fix.

    Three failed reads is about a third of a second at the capture loop's
    cadence, well inside the six seconds that separated the first failed read
    from the segfault on 2026-08-20.
    """
    assert _camera("0")._fatal_after_failures() == 3


def test_a_stream_tolerates_far_more_consecutive_failures():
    """
    A network stall is not a disconnected device.

    Applying the local threshold to RTSP would tear down and rebuild a healthy
    stream on any brief interruption.
    """
    local = _camera("0")._fatal_after_failures()
    stream = _camera("rtsp://host/stream")._fatal_after_failures()
    assert stream > local
    assert stream >= 15, "a stream should ride out at least a second or two of stall"


def test_a_stream_gets_a_longer_reopen_proof_window():
    """
    The one that would break RTSP outright.

    An RTSP reopen must connect, handshake and wait for a keyframe. Judging it
    against the local device's two-second window would discard every working
    capture and reconnect forever.
    """
    local = _camera("0")._reopen_prove_seconds()
    stream = _camera("rtsp://host/stream")._reopen_prove_seconds()
    assert stream > local
    assert stream >= 8, "an RTSP handshake plus keyframe commonly exceeds 8s"


def test_thresholds_are_overridable_by_environment(monkeypatch):
    """An operator with an unusual network must be able to retune without a rebuild."""
    monkeypatch.setenv("OPENEYE_FATAL_AFTER_FAILURES_STREAM", "99")
    monkeypatch.setenv("OPENEYE_REOPEN_PROVE_SECONDS_STREAM", "42")
    cam = _camera("rtsp://host/stream")
    assert cam._fatal_after_failures() == 99
    assert cam._reopen_prove_seconds() == 42.0
