# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Two-way audio: the sounddevice backend.

Why this file exists
--------------------
Audio I/O moved from PyAudio to sounddevice. Both drive PortAudio, but PyAudio
publishes wheels for Windows only, so on macOS and Linux it compiled from source
against PortAudio's headers — and when those were missing, pip aborted the entire
install, taking all ~127 other dependencies with it. sounddevice ships
pure-Python wheels that never compile.

The two libraries do NOT agree on their callback contracts, and both differences
corrupt audio silently rather than raising:

1. PyAudio handed the capture callback an immutable `bytes` object. sounddevice
   reuses one buffer for every block, so a numpy view over it is overwritten by
   the next block while still queued.
2. PyAudio accepted a returned buffer of whatever length. sounddevice hands the
   playback callback a buffer that must be filled completely; a short write
   leaves the previous block's samples in the tail.

Neither shows up as an error — the first as crackle or repeated audio, the
second as a stutter. Two-way audio is verified by ear on real hardware, which
happens rarely, so these are pinned here where they run every time.

No audio device is required: the callbacks are called directly, exactly as
PortAudio calls them.
"""

import numpy as np
import pytest

from backend.core import two_way_audio_system as tas
from backend.core.two_way_audio_system import AudioConfig, BYTES_PER_SAMPLE


@pytest.fixture
def config():
    """Noise suppression off — its gate zeroes quiet buffers and would mask what
    these tests are actually checking."""
    return AudioConfig(
        sample_rate=16000,
        channels=1,
        chunk_size=4,
        enable_noise_suppression=False,
    )


@pytest.fixture
def capture(config, monkeypatch):
    monkeypatch.setattr(tas, "AUDIO_IO_AVAILABLE", True)
    return tas.AudioCapture(config)


@pytest.fixture
def playback(config, monkeypatch):
    monkeypatch.setattr(tas, "AUDIO_IO_AVAILABLE", True)
    return tas.AudioPlayback(config)


# ---------------------------------------------------------------------------
# Capture: the queued frame must not alias PortAudio's buffer
# ---------------------------------------------------------------------------

def test_captured_audio_survives_the_buffer_being_reused(capture):
    """
    The bug this prevents: queueing a view instead of a copy.

    PortAudio hands back the SAME buffer on every block. A numpy view over it
    stays valid only until the next block overwrites the memory — by which time
    the frame is sitting in the queue waiting to be streamed, so the listener
    hears the newest block in place of the one that was captured.
    """
    buffer = bytearray(np.array([100, 200, 300, 400], dtype=np.int16).tobytes())

    capture._audio_callback(buffer, 4, None, None)

    # PortAudio refills the same memory with the next block.
    buffer[:] = np.array([-1, -2, -3, -4], dtype=np.int16).tobytes()

    queued = capture.get_frame()
    assert queued is not None, "callback queued nothing"
    np.testing.assert_array_equal(
        queued,
        np.array([100, 200, 300, 400], dtype=np.int16),
        err_msg="queued frame aliased the reused buffer instead of copying it",
    )


def test_capture_callback_returns_nothing(capture):
    """
    sounddevice callbacks return None; PyAudio expected `(data, paContinue)`.
    Returning a tuple here raises inside PortAudio's callback thread.
    """
    buffer = bytearray(np.zeros(4, dtype=np.int16).tobytes())
    assert capture._audio_callback(buffer, 4, None, None) is None


def test_capture_callback_survives_a_bad_buffer(capture):
    """
    A raising callback would propagate into PortAudio's thread. The callback
    logs and continues instead, so one malformed block cannot end the stream.
    """
    capture._audio_callback(b"\x00", 4, None, None)  # odd length for int16


# ---------------------------------------------------------------------------
# Playback: the output buffer must be filled exactly
# ---------------------------------------------------------------------------

def _outdata(frames, channels=1):
    return bytearray(frames * channels * BYTES_PER_SAMPLE)


def test_short_frame_is_padded_with_silence(playback, config):
    """
    Nothing upstream enforces chunk_size — a queued frame is whatever the far
    end sent. A frame shorter than the block must be padded, or the tail keeps
    the previous block's samples and stutters.
    """
    playback.play_frame(np.array([111, 222], dtype=np.int16))  # 2 of 4 frames
    out = _outdata(4)

    playback._audio_callback(out, 4, None, None)

    assert np.frombuffer(bytes(out), dtype=np.int16).tolist() == [111, 222, 0, 0]


def test_oversized_frame_carries_over_instead_of_being_dropped(playback):
    """
    Queued frames rarely match the block size — WebRTC sends 320- or 960-sample
    frames against a 1024-sample block — so a frame that overruns the block is
    the normal case, not an edge case. Discarding the overrun would drop audio
    on almost every callback; it is held and emitted next block instead.
    """
    playback.play_frame(np.array([1, 2, 3, 4, 5, 6], dtype=np.int16))

    first = _outdata(4)
    playback._audio_callback(first, 4, None, None)
    assert len(first) == 4 * BYTES_PER_SAMPLE
    assert np.frombuffer(bytes(first), dtype=np.int16).tolist() == [1, 2, 3, 4]

    # The remaining two samples must lead the next block, then silence.
    second = _outdata(4)
    playback._audio_callback(second, 4, None, None)
    assert np.frombuffer(bytes(second), dtype=np.int16).tolist() == [5, 6, 0, 0]


def test_several_small_frames_fill_one_block(playback):
    """
    The mirror case: frames smaller than the block must be combined rather than
    padded individually, or every frame boundary inserts silence and the audio
    develops a periodic click.
    """
    playback.play_frame(np.array([1, 2], dtype=np.int16))
    playback.play_frame(np.array([3, 4], dtype=np.int16))

    out = _outdata(4)
    playback._audio_callback(out, 4, None, None)

    assert np.frombuffer(bytes(out), dtype=np.int16).tolist() == [1, 2, 3, 4]


def test_backlog_is_bounded_so_latency_cannot_grow_without_limit(playback, config):
    """
    A producer that outruns playback would otherwise build an ever-growing
    backlog, and in a conversation that delay never recovers. The oldest audio
    is dropped once the carry-over exceeds the cap.
    """
    from backend.core.two_way_audio_system import MAX_PLAYBACK_BACKLOG_BLOCKS

    block_samples = 4
    # Queue far more than the cap allows.
    for _ in range(20):
        playback.play_frame(np.arange(block_samples, dtype=np.int16))

    out = _outdata(block_samples)
    playback._audio_callback(out, block_samples, None, None)

    cap = block_samples * config.channels * BYTES_PER_SAMPLE * MAX_PLAYBACK_BACKLOG_BLOCKS
    assert len(playback._residual) <= cap, "backlog grew past the cap"


def test_empty_queue_produces_silence_not_stale_audio(playback):
    """With nothing to play the block must be zeroed, not left as it was."""
    out = _outdata(4)
    out[:] = np.array([9, 9, 9, 9], dtype=np.int16).tobytes()

    playback._audio_callback(out, 4, None, None)

    assert np.frombuffer(bytes(out), dtype=np.int16).tolist() == [0, 0, 0, 0]


def test_silence_accounts_for_channel_count(config, monkeypatch):
    """
    The silence buffer is sized frames x channels x 2. Dropping the channel
    count yields a half-length write on stereo — the classic version of this bug.
    """
    monkeypatch.setattr(tas, "AUDIO_IO_AVAILABLE", True)
    stereo = AudioConfig(channels=2, chunk_size=4, enable_noise_suppression=False)
    player = tas.AudioPlayback(stereo)

    out = _outdata(4, channels=2)
    player._audio_callback(out, 4, None, None)

    assert len(out) == 4 * 2 * BYTES_PER_SAMPLE


# ---------------------------------------------------------------------------
# Device listing: sounddevice's keys differ from PyAudio's
# ---------------------------------------------------------------------------

class _FakeDevices(list):
    """Stands in for sd.query_devices(), which returns a list of dicts."""


def test_device_listing_reads_sounddevice_key_names(capture, playback, monkeypatch):
    """
    PyAudio used maxInputChannels/defaultSampleRate; sounddevice uses
    max_input_channels/default_samplerate. Reading the old names raises KeyError
    the first time anyone opens the audio settings.
    """
    devices = _FakeDevices([
        {"name": "Mic", "max_input_channels": 2,
         "max_output_channels": 0, "default_samplerate": 48000.0},
        {"name": "Speaker", "max_input_channels": 0,
         "max_output_channels": 2, "default_samplerate": 44100.0},
    ])
    monkeypatch.setattr(tas, "sd", type("sd", (), {
        "query_devices": staticmethod(lambda: devices)})())

    inputs = capture.list_devices()
    outputs = playback.list_devices()

    assert inputs == [
        {"index": 0, "name": "Mic", "channels": 2, "sample_rate": 48000}
    ]
    assert outputs == [
        {"index": 1, "name": "Speaker", "channels": 2, "sample_rate": 44100}
    ]


# ---------------------------------------------------------------------------
# Degradation: a missing library must not take the application down
# ---------------------------------------------------------------------------

def test_capture_refuses_to_construct_without_the_library(config, monkeypatch):
    """
    On Linux without libportaudio2, sounddevice raises OSError at import and the
    module degrades. Constructing a capture object then has to fail with a
    message naming the fix, rather than an AttributeError on None.
    """
    monkeypatch.setattr(tas, "AUDIO_IO_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="sounddevice"):
        tas.AudioCapture(config)
    with pytest.raises(RuntimeError, match="sounddevice"):
        tas.AudioPlayback(config)


def test_manager_reports_the_missing_component_by_name(monkeypatch):
    """The operator has to learn WHICH piece is missing, not just that audio is off."""
    monkeypatch.setattr(tas, "AUDIO_IO_AVAILABLE", False)
    monkeypatch.setattr(tas, "WEBRTC_AVAILABLE", True)

    manager = tas.TwoWayAudioManager()

    assert manager.available is False
    assert manager.list_audio_devices()["error"] == "sounddevice not installed"
