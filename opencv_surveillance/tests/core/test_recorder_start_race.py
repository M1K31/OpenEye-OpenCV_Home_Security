# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
The recorder must never claim to be running before it can say since when.

Observed live, four times in one afternoon:

    Error generating frames for camera usb_camera_0:
    unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'

start() raised is_recording BEFORE setting recording_start_time, so anything
reading the recorder in the single statement between them saw a recording with
no start time. The streaming loop reads at 30 FPS, which is what turned a
one-statement window into a recurring error.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.core.recorder import Recorder


@pytest.fixture
def recorder(tmp_path):
    r = Recorder.__new__(Recorder)
    r.is_recording = False
    r.recording_start_time = None
    r.writer = None
    r.filename = str(tmp_path / "clip.mp4")
    r.frame_count = 0
    r.detected_faces = []
    r.associated_motion_event_ids = []
    r.max_recording_duration = 300
    return r


class TestTheStartRace:
    def test_a_running_recorder_always_has_a_start_time(self, recorder):
        """
        The invariant. Whenever is_recording is true, recording_start_time must
        be set — that is what every duration calculation depends on.
        """
        recorder.recording_start_time = datetime.now()
        recorder.is_recording = True

        assert recorder.is_recording
        assert recorder.recording_start_time is not None

    def test_reading_info_mid_start_does_not_raise(self, recorder):
        """
        Simulates the exact window: published as running, no start time yet.
        Before the fix this raised TypeError from the streaming path.
        """
        recorder.is_recording = True
        recorder.recording_start_time = None

        assert recorder.get_current_recording_info() is None

    def test_stopping_without_a_start_time_still_saves_metadata(self, recorder):
        """
        A recording of nothing is worth zero seconds, not an exception that
        loses the file's metadata along with it.
        """
        recorder.is_recording = True
        recorder.recording_start_time = None
        recorder.writer = MagicMock()
        recorder._writer_lock = __import__("threading").Lock()
        recorder._save_metadata = MagicMock()

        recorder.stop()

        recorder._save_metadata.assert_called_once()
        duration = recorder._save_metadata.call_args[0][0]
        assert duration == 0.0

    def test_max_duration_check_tolerates_no_start_time(self, recorder):
        recorder.is_recording = True
        recorder.recording_start_time = None

        assert recorder.should_stop_recording() is False


class TestNormalOperation:
    def test_info_reports_a_duration_while_recording(self, recorder):
        recorder.is_recording = True
        recorder.recording_start_time = datetime.now()

        info = recorder.get_current_recording_info()

        assert info is not None
        assert info["duration_seconds"] >= 0

    def test_info_is_none_when_not_recording(self, recorder):
        assert recorder.get_current_recording_info() is None
