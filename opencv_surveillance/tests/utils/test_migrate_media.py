# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for migrate_media module
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from backend.utils.migrate_media import (
    MigrationResult,
    migrate_files,
    _update_snapshot_paths,
    _update_recording_paths,
)


class TestMigrationResult:
    """Test MigrationResult class"""

    def test_initialization(self):
        """Test MigrationResult initialization"""
        result = MigrationResult()

        assert result.files_found == 0
        assert result.files_moved == 0
        assert result.files_failed == 0
        assert result.db_records_updated == 0
        assert result.errors == []

    def test_to_dict_success(self):
        """Test to_dict with successful migration"""
        result = MigrationResult()
        result.files_found = 100
        result.files_moved = 100
        result.files_failed = 0
        result.db_records_updated = 50

        data = result.to_dict()

        assert data["files_found"] == 100
        assert data["files_moved"] == 100
        assert data["files_failed"] == 0
        assert data["db_records_updated"] == 50
        assert data["success"] is True
        assert data["errors"] == []

    def test_to_dict_with_failures(self):
        """Test to_dict with some failed files"""
        result = MigrationResult()
        result.files_found = 100
        result.files_moved = 95
        result.files_failed = 5
        result.errors.append("Failed to move file1.mp4")
        result.errors.append("Failed to move file2.mp4")

        data = result.to_dict()

        assert data["files_failed"] == 5
        assert data["success"] is False
        assert len(data["errors"]) == 2


class TestMigrateFiles:
    """Test migrate_files function"""

    def test_source_directory_not_exists(self):
        """Test migration when source directory doesn't exist"""
        result = migrate_files(
            media_type="snapshots",
            source_dir="/nonexistent/source",
            dest_dir="/some/dest",
            update_database=False,
            dry_run=False
        )

        assert result.files_found == 0
        assert result.files_moved == 0
        assert len(result.errors) == 1
        assert "does not exist" in result.errors[0]

    def test_source_equals_destination(self):
        """Test when source and destination are the same"""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = migrate_files(
                media_type="recordings",
                source_dir=tmpdir,
                dest_dir=tmpdir,
                update_database=False,
                dry_run=False
            )

            assert result.files_found == 0
            assert result.files_moved == 0
            assert len(result.errors) == 0

    def test_migrate_snapshots_dry_run(self):
        """Test snapshot migration in dry run mode"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test snapshot files
                source_path = Path(source_dir)
                (source_path / "snapshot1.jpg").write_text("fake image 1")
                (source_path / "snapshot2.png").write_text("fake image 2")
                (source_path / "snapshot3.jpeg").write_text("fake image 3")

                result = migrate_files(
                    media_type="snapshots",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=False,
                    dry_run=True
                )

                assert result.files_found == 3
                assert result.files_moved == 3  # Counted but not actually moved
                assert result.files_failed == 0

                # Verify files NOT actually moved (dry run)
                assert (source_path / "snapshot1.jpg").exists()
                assert not (Path(dest_dir) / "snapshot1.jpg").exists()

    def test_migrate_recordings_actual_move(self):
        """Test recording migration with actual file movement"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test recording files
                source_path = Path(source_dir)
                (source_path / "video1.mp4").write_text("fake video 1")
                (source_path / "video2.avi").write_text("fake video 2")
                (source_path / "video1_metadata.json").write_text('{"duration": 10}')

                result = migrate_files(
                    media_type="recordings",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=False,
                    dry_run=False
                )

                assert result.files_found == 3
                assert result.files_moved == 3
                assert result.files_failed == 0

                # Verify files actually moved
                dest_path = Path(dest_dir)
                assert (dest_path / "video1.mp4").exists()
                assert (dest_path / "video2.avi").exists()
                assert (dest_path / "video1_metadata.json").exists()

                # Verify source files removed
                assert not (source_path / "video1.mp4").exists()

    def test_migrate_faces_with_subdirectories(self):
        """Test face migration preserving directory structure

        Note: Current implementation uses glob() which is non-recursive.
        This test verifies that files at the top level are migrated.
        Subdirectory support would require rglob() or ** pattern.
        """
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create files at top level (glob pattern is non-recursive)
                source_path = Path(source_dir)
                (source_path / "face1.jpg").write_text("face 1")
                (source_path / "face2.jpg").write_text("face 2")

                result = migrate_files(
                    media_type="faces",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=False,
                    dry_run=False
                )

                assert result.files_found == 2
                assert result.files_moved == 2
                assert result.files_failed == 0

                # Verify files moved
                dest_path = Path(dest_dir)
                assert (dest_path / "face1.jpg").exists()
                assert (dest_path / "face2.jpg").exists()

    def test_migrate_handles_file_move_error(self):
        """Test handling of file move errors"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create a file
                source_path = Path(source_dir)
                (source_path / "test.jpg").write_text("test")

                # Mock shutil.move to raise error
                with patch('shutil.move', side_effect=PermissionError("Permission denied")):
                    result = migrate_files(
                        media_type="snapshots",
                        source_dir=source_dir,
                        dest_dir=dest_dir,
                        update_database=False,
                        dry_run=False
                    )

                    assert result.files_found == 1
                    assert result.files_moved == 0
                    assert result.files_failed == 1
                    assert len(result.errors) == 1
                    assert "Failed to move" in result.errors[0]

    @patch('backend.utils.migrate_media.SessionLocal')
    @patch('backend.utils.migrate_media._update_snapshot_paths')
    def test_migrate_with_database_update(self, mock_update_paths, mock_session):
        """Test migration with database update"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test file
                source_path = Path(source_dir)
                (source_path / "snapshot1.jpg").write_text("fake image")

                # Mock database session
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                mock_update_paths.return_value = 5

                result = migrate_files(
                    media_type="snapshots",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=True,
                    dry_run=False
                )

                assert result.files_moved == 1
                assert result.db_records_updated == 5
                mock_update_paths.assert_called_once()
                mock_db.close.assert_called_once()

    @patch('backend.utils.migrate_media.SessionLocal')
    @patch('backend.utils.migrate_media._update_recording_paths')
    def test_migrate_recordings_with_database_update(self, mock_update_paths, mock_session):
        """Test recording migration with database update"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test file
                source_path = Path(source_dir)
                (source_path / "video1.mp4").write_text("fake video")

                # Mock database session
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                mock_update_paths.return_value = 3

                result = migrate_files(
                    media_type="recordings",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=True,
                    dry_run=False
                )

                assert result.db_records_updated == 3
                mock_update_paths.assert_called_once()

    @patch('backend.utils.migrate_media.SessionLocal')
    def test_migrate_database_update_error(self, mock_session):
        """Test handling of database update errors"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test file
                source_path = Path(source_dir)
                (source_path / "snapshot1.jpg").write_text("fake image")

                # Mock database session to raise error
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                mock_session.side_effect = Exception("Database connection error")

                result = migrate_files(
                    media_type="snapshots",
                    source_dir=source_dir,
                    dest_dir=dest_dir,
                    update_database=True,
                    dry_run=False
                )

                # Files should still be moved even if DB update fails
                assert result.files_moved == 1
                assert result.db_records_updated == 0
                assert len(result.errors) == 1
                assert "Database update failed" in result.errors[0]

    def test_migrate_no_database_update_in_dry_run(self):
        """Test that database is not updated in dry run mode"""
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                source_path = Path(source_dir)
                (source_path / "snapshot1.jpg").write_text("fake image")

                with patch('backend.utils.migrate_media.SessionLocal') as mock_session:
                    result = migrate_files(
                        media_type="snapshots",
                        source_dir=source_dir,
                        dest_dir=dest_dir,
                        update_database=True,
                        dry_run=True
                    )

                    # Database should not be accessed in dry run
                    mock_session.assert_not_called()
                    assert result.db_records_updated == 0


class TestUpdateSnapshotPaths:
    """Test _update_snapshot_paths function"""

    @patch('backend.utils.migrate_media.paths')
    def test_update_snapshot_paths_success(self, mock_paths):
        """Test successful snapshot path updates"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.snapshot_path = "old/snapshots/camera1/snap1.jpg"

        mock_event2 = MagicMock()
        mock_event2.snapshot_path = "old/snapshots/camera1/snap2.jpg"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths module
        def mock_resolve(path):
            return Path("/base") / path

        def mock_relative(path):
            return str(path.relative_to("/base"))

        mock_paths.resolve_path.side_effect = mock_resolve
        mock_paths.get_relative_path.side_effect = mock_relative

        # Run update
        old_base = Path("/base/old/snapshots")
        new_base = Path("/base/new/snapshots")

        count = _update_snapshot_paths(mock_db, old_base, new_base)

        assert count == 2
        mock_db.commit.assert_called_once()

    @patch('backend.utils.migrate_media.paths')
    def test_update_snapshot_paths_with_none(self, mock_paths):
        """Test update with None snapshot paths"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with None path
        mock_event = MagicMock()
        mock_event.snapshot_path = None

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Run update
        count = _update_snapshot_paths(
            mock_db,
            Path("/old"),
            Path("/new")
        )

        assert count == 0
        mock_paths.resolve_path.assert_not_called()

    @patch('backend.utils.migrate_media.paths')
    def test_update_snapshot_paths_skip_different_base(self, mock_paths):
        """Test that paths not under old_base are skipped"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with path not under old_base
        mock_event = MagicMock()
        mock_event.snapshot_path = "different/location/snap.jpg"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Mock resolve_path to return path outside old_base
        mock_paths.resolve_path.return_value = Path("/completely/different/snap.jpg")

        # Run update
        count = _update_snapshot_paths(
            mock_db,
            Path("/old/base"),
            Path("/new/base")
        )

        assert count == 0
        mock_db.commit.assert_called_once()


class TestUpdateRecordingPaths:
    """Test _update_recording_paths function"""

    @patch('backend.utils.migrate_media.paths')
    def test_update_recording_paths_success(self, mock_paths):
        """Test successful recording path updates"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.recording_path = "old/recordings/camera1/video1.mp4"

        mock_event2 = MagicMock()
        mock_event2.recording_path = "old/recordings/camera1/video2.mp4"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths module
        def mock_resolve(path):
            return Path("/base") / path

        def mock_relative(path):
            return str(path.relative_to("/base"))

        mock_paths.resolve_path.side_effect = mock_resolve
        mock_paths.get_relative_path.side_effect = mock_relative

        # Run update
        old_base = Path("/base/old/recordings")
        new_base = Path("/base/new/recordings")

        count = _update_recording_paths(mock_db, old_base, new_base)

        assert count == 2
        mock_db.commit.assert_called_once()

    @patch('backend.utils.migrate_media.paths')
    def test_update_recording_paths_with_none(self, mock_paths):
        """Test update with None recording paths"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with None path
        mock_event = MagicMock()
        mock_event.recording_path = None

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Run update
        count = _update_recording_paths(
            mock_db,
            Path("/old"),
            Path("/new")
        )

        assert count == 0
        mock_paths.resolve_path.assert_not_called()

    @patch('backend.utils.migrate_media.paths')
    def test_update_recording_paths_skip_different_base(self, mock_paths):
        """Test that paths not under old_base are skipped"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with path not under old_base
        mock_event = MagicMock()
        mock_event.recording_path = "different/location/video.mp4"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Mock resolve_path to return path outside old_base
        mock_paths.resolve_path.return_value = Path("/completely/different/video.mp4")

        # Run update
        count = _update_recording_paths(
            mock_db,
            Path("/old/base"),
            Path("/new/base")
        )

        assert count == 0
        mock_db.commit.assert_called_once()
