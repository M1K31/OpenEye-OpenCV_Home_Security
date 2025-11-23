# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for video_utils module
"""

import pytest
import os
import tempfile
import numpy as np
import cv2
from unittest.mock import patch, MagicMock
from backend.utils.video_utils import (
    get_actual_video_duration,
    get_video_info,
    get_video_info_ffprobe,
    verify_video_integrity
)


@pytest.fixture
def temp_video_file():
    """Create a temporary test video file"""
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()

    # Create a simple test video with OpenCV
    # 10 frames at 10 FPS = 1 second duration
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(temp_path, fourcc, 10.0, (640, 480))

    # Write 10 frames
    for i in range(10):
        # Create a simple frame (gradient pattern)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:, :] = (i * 25, 128, 255 - i * 25)  # Change colors per frame
        out.write(frame)

    out.release()

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def empty_file():
    """Create an empty file"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    temp_path = temp_file.name
    temp_file.close()

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestGetActualVideoDuration:
    """Test get_actual_video_duration function"""

    def test_nonexistent_file(self):
        """Test with non-existent file"""
        result = get_actual_video_duration("/nonexistent/video.mp4")
        assert result is None

    @patch('cv2.VideoCapture')
    def test_valid_video_file(self, mock_capture):
        """Test with valid video file"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 10.0,
            cv2.CAP_PROP_FRAME_COUNT: 10
        }.get(prop, 0)
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            duration = get_actual_video_duration(temp_file.name)

            # Should be exactly 1 second (10 frames at 10 FPS)
            assert duration is not None
            assert duration == 1.0

    def test_empty_file(self, empty_file):
        """Test with empty file"""
        duration = get_actual_video_duration(empty_file)
        assert duration is None

    @patch('cv2.VideoCapture')
    def test_opencv_fails_to_open(self, mock_capture):
        """Test when OpenCV fails to open the file"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            result = get_actual_video_duration(temp_file.name)
            assert result is None

    @patch('cv2.VideoCapture')
    def test_invalid_fps(self, mock_capture):
        """Test when FPS is invalid (0 or negative)"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: 0 if prop == cv2.CAP_PROP_FPS else 100
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            result = get_actual_video_duration(temp_file.name)
            assert result is None

    @patch('cv2.VideoCapture')
    def test_exception_handling(self, mock_capture):
        """Test exception handling"""
        mock_capture.side_effect = Exception("Test error")

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            result = get_actual_video_duration(temp_file.name)
            assert result is None


class TestGetVideoInfo:
    """Test get_video_info function"""

    def test_nonexistent_file(self):
        """Test with non-existent file"""
        result = get_video_info("/nonexistent/video.mp4")
        assert result is None

    @patch('cv2.VideoCapture')
    @patch('os.path.getsize')
    def test_valid_video_file(self, mock_getsize, mock_capture):
        """Test with valid video file"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 10.0,
            cv2.CAP_PROP_FRAME_COUNT: 10,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480
        }.get(prop, 0)
        mock_capture.return_value = mock_cap
        mock_getsize.return_value = 1024000  # 1MB

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info(temp_file.name)

            assert info is not None
            assert "fps" in info
            assert "frame_count" in info
            assert "width" in info
            assert "height" in info
            assert "duration_seconds" in info
            assert "file_size_bytes" in info
            assert "bitrate_kbps" in info

            # Verify values
            assert info["fps"] == 10.0
            assert info["frame_count"] == 10
            assert info["width"] == 640
            assert info["height"] == 480
            assert info["duration_seconds"] == 1.0
            assert info["file_size_bytes"] == 1024000
            assert info["bitrate_kbps"] > 0

    def test_empty_file(self, empty_file):
        """Test with empty file"""
        info = get_video_info(empty_file)
        assert info is None

    @patch('cv2.VideoCapture')
    def test_opencv_fails_to_open(self, mock_capture):
        """Test when OpenCV fails to open the file"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            result = get_video_info(temp_file.name)
            assert result is None

    @patch('cv2.VideoCapture')
    def test_zero_duration_calculation(self, mock_capture):
        """Test when duration calculation results in 0"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 0,  # Invalid FPS
            cv2.CAP_PROP_FRAME_COUNT: 100,
            cv2.CAP_PROP_FRAME_WIDTH: 640,
            cv2.CAP_PROP_FRAME_HEIGHT: 480
        }.get(prop, 0)
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info(temp_file.name)

            assert info is not None
            assert info["duration_seconds"] == 0
            assert info["bitrate_kbps"] == 0

    @patch('cv2.VideoCapture')
    def test_exception_handling(self, mock_capture):
        """Test exception handling"""
        mock_capture.side_effect = Exception("Test error")

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            result = get_video_info(temp_file.name)
            assert result is None


class TestGetVideoInfoFFprobe:
    """Test get_video_info_ffprobe function"""

    def test_nonexistent_file(self):
        """Test with non-existent file"""
        result = get_video_info_ffprobe("/nonexistent/video.mp4")
        assert result is None

    @patch('subprocess.run')
    def test_ffprobe_success(self, mock_run):
        """Test successful ffprobe execution"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "nb_frames": "300"
                }
            ],
            "format": {
                "duration": "10.0",
                "size": "1024000",
                "bit_rate": "819200"
            }
        }
        '''
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            assert info is not None
            assert info["fps"] == 30.0
            assert info["frame_count"] == 300
            assert info["width"] == 1920
            assert info["height"] == 1080
            assert info["duration_seconds"] == 10.0
            assert info["file_size_bytes"] == 1024000
            assert info["bitrate_kbps"] == 819.2
            assert info["codec"] == "h264"

    @patch('subprocess.run')
    def test_ffprobe_fractional_fps(self, mock_run):
        """Test ffprobe with fractional FPS"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''
        {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "24000/1001",
                    "nb_frames": "240"
                }
            ],
            "format": {
                "duration": "10.0",
                "size": "1024000",
                "bit_rate": "819200"
            }
        }
        '''
        mock_run.return_value = mock_result

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            assert info is not None
            # 24000/1001 ≈ 23.976 (NTSC framerate)
            assert 23.9 < info["fps"] < 24.0

    @patch('subprocess.run')
    @patch('backend.utils.video_utils.get_video_info')
    def test_ffprobe_not_found(self, mock_get_video_info, mock_run):
        """Test fallback to OpenCV when ffprobe not found"""
        mock_run.side_effect = FileNotFoundError("ffprobe not found")
        mock_get_video_info.return_value = {
            "fps": 30.0,
            "frame_count": 300,
            "width": 1920,
            "height": 1080,
            "duration_seconds": 10.0,
            "file_size_bytes": 1024000,
            "bitrate_kbps": 819.2
        }

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            # Should fall back to OpenCV method
            assert info is not None
            assert "fps" in info
            assert "width" in info
            mock_get_video_info.assert_called_once()

    @patch('subprocess.run')
    @patch('backend.utils.video_utils.get_video_info')
    def test_ffprobe_timeout(self, mock_get_video_info, mock_run):
        """Test fallback when ffprobe times out"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=['ffprobe'], timeout=5)
        mock_get_video_info.return_value = {
            "fps": 30.0,
            "frame_count": 300,
            "width": 1920,
            "height": 1080,
            "duration_seconds": 10.0,
            "file_size_bytes": 1024000,
            "bitrate_kbps": 819.2
        }

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            # Should fall back to OpenCV method
            assert info is not None
            assert "fps" in info
            mock_get_video_info.assert_called_once()

    @patch('subprocess.run')
    @patch('backend.utils.video_utils.get_video_info')
    def test_ffprobe_invalid_json(self, mock_get_video_info, mock_run):
        """Test fallback when ffprobe returns invalid JSON"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "invalid json {"
        mock_run.return_value = mock_result
        mock_get_video_info.return_value = {
            "fps": 30.0,
            "frame_count": 300,
            "width": 1920,
            "height": 1080,
            "duration_seconds": 10.0,
            "file_size_bytes": 1024000,
            "bitrate_kbps": 819.2
        }

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            # Should fall back to OpenCV method
            assert info is not None
            assert "fps" in info
            mock_get_video_info.assert_called_once()

    @patch('subprocess.run')
    @patch('backend.utils.video_utils.get_video_info')
    def test_ffprobe_no_video_stream(self, mock_get_video_info, mock_run):
        """Test fallback when no video stream found"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '''
        {
            "streams": [
                {
                    "codec_type": "audio",
                    "codec_name": "aac"
                }
            ],
            "format": {}
        }
        '''
        mock_run.return_value = mock_result
        mock_get_video_info.return_value = {
            "fps": 30.0,
            "frame_count": 300,
            "width": 1920,
            "height": 1080,
            "duration_seconds": 10.0,
            "file_size_bytes": 1024000,
            "bitrate_kbps": 819.2
        }

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            # Should fall back to OpenCV method
            assert info is not None
            assert "fps" in info
            mock_get_video_info.assert_called_once()

    @patch('subprocess.run')
    @patch('backend.utils.video_utils.get_video_info')
    def test_ffprobe_nonzero_exit_code(self, mock_get_video_info, mock_run):
        """Test fallback when ffprobe exits with error"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        mock_get_video_info.return_value = {
            "fps": 30.0,
            "frame_count": 300,
            "width": 1920,
            "height": 1080,
            "duration_seconds": 10.0,
            "file_size_bytes": 1024000,
            "bitrate_kbps": 819.2
        }

        with tempfile.NamedTemporaryFile(suffix='.mp4') as temp_file:
            info = get_video_info_ffprobe(temp_file.name)

            # Should fall back to OpenCV method
            assert info is not None
            assert "fps" in info
            mock_get_video_info.assert_called_once()


class TestVerifyVideoIntegrity:
    """Test verify_video_integrity function"""

    def test_nonexistent_file(self):
        """Test with non-existent file"""
        result = verify_video_integrity("/nonexistent/video.mp4")

        assert result["valid"] is False
        assert result["exists"] is False
        assert "File does not exist" in result["issues"]

    def test_empty_file(self, empty_file):
        """Test with empty file"""
        result = verify_video_integrity(empty_file)

        assert result["valid"] is False
        assert result["exists"] is True
        assert result["readable"] is False
        assert "File is empty (0 bytes)" in result["issues"]

    @patch('cv2.VideoCapture')
    def test_valid_video_file(self, mock_capture):
        """Test with valid video file"""
        # Create a mock frame (fake numpy array)
        import numpy as np
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 10.0,
            cv2.CAP_PROP_FRAME_COUNT: 10
        }.get(prop, 0)
        mock_cap.read.return_value = (True, fake_frame)  # Successful frame read
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is True
            assert result["exists"] is True
            assert result["readable"] is True
            assert result["has_frames"] is True
            assert result["frame_count"] == 10
            assert 0.8 < result["duration"] < 1.2
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_video_cannot_open(self, mock_capture):
        """Test when video cannot be opened"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is False
            assert result["exists"] is True
            assert result["readable"] is False
            assert "Unable to open video file" in result["issues"]
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_zero_frames(self, mock_capture):
        """Test video with zero frames"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 0  # All properties return 0
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is False
            assert result["readable"] is True
            assert result["has_frames"] is False
            assert "Video has 0 frames" in result["issues"]
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_cannot_read_first_frame(self, mock_capture):
        """Test when first frame cannot be read"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 100
        }.get(prop, 0)
        mock_cap.read.return_value = (False, None)  # Cannot read frame
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is False
            assert "Unable to read first frame" in result["issues"]
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_low_frame_count(self, mock_capture):
        """Test video with very low frame count"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 5  # Less than 10
        }.get(prop, 0)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            # Should still be valid, but have a warning
            assert result["valid"] is True  # Not a critical issue
            assert "Very low frame count (5 frames)" in result["issues"]
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_invalid_fps(self, mock_capture):
        """Test video with invalid FPS"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 0,  # Invalid
            cv2.CAP_PROP_FRAME_COUNT: 100
        }.get(prop, 0)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is True  # Not critical
            assert "Invalid FPS value" in result["issues"]
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_low_fps(self, mock_capture):
        """Test video with suspiciously low FPS"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 3.0,  # Very low
            cv2.CAP_PROP_FRAME_COUNT: 100
        }.get(prop, 0)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is True  # Not critical
            assert any("low FPS" in issue for issue in result["issues"])
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_small_file_warning(self, mock_capture):
        """Test warning for suspiciously small file"""
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            cv2.CAP_PROP_FPS: 30.0,
            cv2.CAP_PROP_FRAME_COUNT: 100
        }.get(prop, 0)
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))
        mock_capture.return_value = mock_cap

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'abc')  # Less than 1KB
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is True  # Not critical
            assert any("suspiciously small" in issue for issue in result["issues"])
        finally:
            os.unlink(temp_path)

    @patch('cv2.VideoCapture')
    def test_exception_during_verification(self, mock_capture):
        """Test exception handling during verification"""
        mock_capture.side_effect = Exception("Test error")

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b'fake video data')
            temp_path = temp_file.name

        try:
            result = verify_video_integrity(temp_path)

            assert result["valid"] is False
            assert any("Error during verification" in issue for issue in result["issues"])
        finally:
            os.unlink(temp_path)
