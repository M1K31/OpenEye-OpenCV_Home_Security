# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for cleanup_orphaned_records module
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from backend.utils.cleanup_orphaned_records import (
    CleanupResult,
    cleanup_orphaned_snapshots,
    cleanup_orphaned_recordings,
    cleanup_orphaned_records,
)


class TestCleanupResult:
    """Test CleanupResult class"""

    def test_initialization(self):
        """Test CleanupResult initialization"""
        result = CleanupResult()

        assert result.total_records == 0
        assert result.orphaned_records == 0
        assert result.cleaned_records == 0
        assert result.errors == []

    def test_to_dict_success(self):
        """Test to_dict with successful cleanup"""
        result = CleanupResult()
        result.total_records = 100
        result.orphaned_records = 10
        result.cleaned_records = 10

        data = result.to_dict()

        assert data["total_records"] == 100
        assert data["orphaned_records"] == 10
        assert data["cleaned_records"] == 10
        assert data["success"] is True
        assert data["errors"] == []

    def test_to_dict_with_errors(self):
        """Test to_dict with errors"""
        result = CleanupResult()
        result.total_records = 100
        result.orphaned_records = 10
        result.cleaned_records = 5
        result.errors.append("Failed to delete some records")

        data = result.to_dict()

        assert data["success"] is False
        assert len(data["errors"]) == 1
        assert "Failed to delete" in data["errors"][0]


class TestCleanupOrphanedSnapshots:
    """Test cleanup_orphaned_snapshots function"""

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_no_orphaned_snapshots(self, mock_paths):
        """Test when all snapshots exist"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.snapshot_path = "data/snapshots/camera1/snapshot1.jpg"

        mock_event2 = MagicMock()
        mock_event2.id = 2
        mock_event2.snapshot_path = "data/snapshots/camera1/snapshot2.jpg"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths - all exist
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_paths.resolve_path.return_value = mock_path

        # Run cleanup
        result = cleanup_orphaned_snapshots(mock_db, dry_run=True)

        assert result.total_records == 2
        assert result.orphaned_records == 0
        assert result.cleaned_records == 0
        assert len(result.errors) == 0

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_orphaned_snapshots_dry_run(self, mock_paths):
        """Test orphaned snapshots in dry run mode"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.snapshot_path = "data/snapshots/camera1/snapshot1.jpg"

        mock_event2 = MagicMock()
        mock_event2.id = 2
        mock_event2.snapshot_path = "data/snapshots/camera1/snapshot2.jpg"

        # Mock query for finding events
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths - one missing, one exists
        def mock_resolve(path):
            mock_path = MagicMock()
            mock_path.exists.return_value = (path == "data/snapshots/camera1/snapshot1.jpg")
            return mock_path

        mock_paths.resolve_path.side_effect = mock_resolve

        # Run cleanup in dry run mode
        result = cleanup_orphaned_snapshots(mock_db, dry_run=True)

        assert result.total_records == 2
        assert result.orphaned_records == 1
        assert result.cleaned_records == 0  # Dry run, nothing deleted

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_orphaned_snapshots_with_deletion(self, mock_paths):
        """Test orphaned snapshots with actual deletion"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.snapshot_path = "data/snapshots/camera1/snapshot1.jpg"

        mock_event2 = MagicMock()
        mock_event2.id = 2
        mock_event2.snapshot_path = "data/snapshots/camera1/snapshot2.jpg"

        # Mock query for finding events
        mock_find_query = MagicMock()
        mock_find_query.filter.return_value.all.return_value = [mock_event1, mock_event2]

        # Mock query for deletion
        mock_delete_query = MagicMock()
        mock_delete_query.filter.return_value.delete.return_value = 1

        # Configure mock_db.query to return different mocks
        mock_db.query.side_effect = [mock_find_query, mock_delete_query]

        # Mock paths - one missing, one exists
        def mock_resolve(path):
            mock_path = MagicMock()
            mock_path.exists.return_value = (path == "data/snapshots/camera1/snapshot1.jpg")
            return mock_path

        mock_paths.resolve_path.side_effect = mock_resolve

        # Run cleanup with deletion
        result = cleanup_orphaned_snapshots(mock_db, dry_run=False)

        assert result.total_records == 2
        assert result.orphaned_records == 1
        assert result.cleaned_records == 1
        mock_db.commit.assert_called_once()

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_orphaned_snapshots_deletion_error(self, mock_paths):
        """Test handling of deletion errors"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.snapshot_path = "data/snapshots/camera1/snapshot1.jpg"

        # Mock query for finding events
        mock_find_query = MagicMock()
        mock_find_query.filter.return_value.all.return_value = [mock_event]

        # Mock query for deletion that raises error
        mock_delete_query = MagicMock()
        mock_delete_query.filter.return_value.delete.side_effect = Exception("Database error")

        mock_db.query.side_effect = [mock_find_query, mock_delete_query]

        # Mock path - file missing
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_paths.resolve_path.return_value = mock_path

        # Run cleanup
        result = cleanup_orphaned_snapshots(mock_db, dry_run=False)

        assert result.orphaned_records == 1
        assert result.cleaned_records == 0
        assert len(result.errors) == 1
        assert "Failed to delete" in result.errors[0]
        mock_db.rollback.assert_called_once()

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_snapshot_with_none_path(self, mock_paths):
        """Test event with None snapshot_path"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with None path
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.snapshot_path = None

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Run cleanup
        result = cleanup_orphaned_snapshots(mock_db, dry_run=True)

        assert result.total_records == 1
        assert result.orphaned_records == 0
        # resolve_path should not be called for None paths
        mock_paths.resolve_path.assert_not_called()


class TestCleanupOrphanedRecordings:
    """Test cleanup_orphaned_recordings function"""

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_no_orphaned_recordings(self, mock_paths):
        """Test when all recordings exist"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.recording_path = "recordings/camera1/video1.mp4"

        mock_event2 = MagicMock()
        mock_event2.id = 2
        mock_event2.recording_path = "recordings/camera1/video2.mp4"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths - all exist
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_paths.resolve_path.return_value = mock_path

        # Run cleanup
        result = cleanup_orphaned_recordings(mock_db, dry_run=True)

        assert result.total_records == 2
        assert result.orphaned_records == 0
        assert result.cleaned_records == 0

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_orphaned_recordings_dry_run(self, mock_paths):
        """Test orphaned recordings in dry run mode"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.recording_path = "recordings/camera1/video1.mp4"

        mock_event2 = MagicMock()
        mock_event2.id = 2
        mock_event2.recording_path = "recordings/camera1/video2.mp4"

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event1, mock_event2]
        mock_db.query.return_value = mock_query

        # Mock paths - both missing
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_paths.resolve_path.return_value = mock_path

        # Run cleanup
        result = cleanup_orphaned_recordings(mock_db, dry_run=True)

        assert result.total_records == 2
        assert result.orphaned_records == 2
        assert result.cleaned_records == 0

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_orphaned_recordings_with_deletion(self, mock_paths):
        """Test orphaned recordings with actual deletion"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock events
        mock_event1 = MagicMock()
        mock_event1.id = 1
        mock_event1.recording_path = "recordings/camera1/video1.mp4"

        # Mock query for finding events
        mock_find_query = MagicMock()
        mock_find_query.filter.return_value.all.return_value = [mock_event1]

        # Mock query for deletion
        mock_delete_query = MagicMock()
        mock_delete_query.filter.return_value.delete.return_value = 1

        mock_db.query.side_effect = [mock_find_query, mock_delete_query]

        # Mock path - file missing
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_paths.resolve_path.return_value = mock_path

        # Run cleanup
        result = cleanup_orphaned_recordings(mock_db, dry_run=False)

        assert result.total_records == 1
        assert result.orphaned_records == 1
        assert result.cleaned_records == 1
        mock_db.commit.assert_called_once()

    @patch('backend.utils.cleanup_orphaned_records.paths')
    def test_recording_with_none_path(self, mock_paths):
        """Test event with None recording_path"""
        # Create mock database session
        mock_db = MagicMock()

        # Create mock event with None path
        mock_event = MagicMock()
        mock_event.id = 1
        mock_event.recording_path = None

        # Mock query
        mock_query = MagicMock()
        mock_query.filter.return_value.all.return_value = [mock_event]
        mock_db.query.return_value = mock_query

        # Run cleanup
        result = cleanup_orphaned_recordings(mock_db, dry_run=True)

        assert result.total_records == 1
        assert result.orphaned_records == 0
        mock_paths.resolve_path.assert_not_called()


class TestCleanupOrphanedRecords:
    """Test main cleanup_orphaned_records function"""

    @patch('backend.utils.cleanup_orphaned_records.SessionLocal')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_snapshots')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_recordings')
    def test_cleanup_snapshots_only(self, mock_cleanup_rec, mock_cleanup_snap, mock_session):
        """Test cleaning only snapshots"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock cleanup results
        snapshot_result = CleanupResult()
        snapshot_result.total_records = 10
        snapshot_result.orphaned_records = 3
        snapshot_result.cleaned_records = 3

        mock_cleanup_snap.return_value = snapshot_result

        # Run cleanup
        results = cleanup_orphaned_records(media_type="snapshots", dry_run=False)

        # Verify only snapshots cleaned
        mock_cleanup_snap.assert_called_once_with(mock_db, False)
        mock_cleanup_rec.assert_not_called()

        assert "snapshots" in results
        assert "recordings" not in results
        assert results["summary"]["total_orphaned"] == 3
        assert results["summary"]["total_cleaned"] == 3
        assert results["summary"]["dry_run"] is False

        mock_db.close.assert_called_once()

    @patch('backend.utils.cleanup_orphaned_records.SessionLocal')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_snapshots')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_recordings')
    def test_cleanup_recordings_only(self, mock_cleanup_rec, mock_cleanup_snap, mock_session):
        """Test cleaning only recordings"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock cleanup results
        recording_result = CleanupResult()
        recording_result.total_records = 20
        recording_result.orphaned_records = 5
        recording_result.cleaned_records = 5

        mock_cleanup_rec.return_value = recording_result

        # Run cleanup
        results = cleanup_orphaned_records(media_type="recordings", dry_run=False)

        # Verify only recordings cleaned
        mock_cleanup_rec.assert_called_once_with(mock_db, False)
        mock_cleanup_snap.assert_not_called()

        assert "recordings" in results
        assert "snapshots" not in results
        assert results["summary"]["total_orphaned"] == 5
        assert results["summary"]["total_cleaned"] == 5

    @patch('backend.utils.cleanup_orphaned_records.SessionLocal')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_snapshots')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_recordings')
    def test_cleanup_all(self, mock_cleanup_rec, mock_cleanup_snap, mock_session):
        """Test cleaning both snapshots and recordings"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock cleanup results
        snapshot_result = CleanupResult()
        snapshot_result.total_records = 10
        snapshot_result.orphaned_records = 3
        snapshot_result.cleaned_records = 3

        recording_result = CleanupResult()
        recording_result.total_records = 20
        recording_result.orphaned_records = 5
        recording_result.cleaned_records = 5

        mock_cleanup_snap.return_value = snapshot_result
        mock_cleanup_rec.return_value = recording_result

        # Run cleanup
        results = cleanup_orphaned_records(media_type="all", dry_run=True)

        # Verify both cleaned
        mock_cleanup_snap.assert_called_once_with(mock_db, True)
        mock_cleanup_rec.assert_called_once_with(mock_db, True)

        assert "snapshots" in results
        assert "recordings" in results
        assert results["summary"]["total_orphaned"] == 8  # 3 + 5
        assert results["summary"]["total_cleaned"] == 8  # 3 + 5
        assert results["summary"]["dry_run"] is True

    @patch('backend.utils.cleanup_orphaned_records.SessionLocal')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_snapshots')
    def test_cleanup_ensures_db_close(self, mock_cleanup_snap, mock_session):
        """Test that database connection is always closed"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock cleanup to raise exception
        mock_cleanup_snap.side_effect = Exception("Test error")

        # Run cleanup - should handle exception and still close db
        with pytest.raises(Exception):
            cleanup_orphaned_records(media_type="snapshots", dry_run=True)

        # Verify db.close() was called despite exception
        mock_db.close.assert_called_once()

    @patch('backend.utils.cleanup_orphaned_records.SessionLocal')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_snapshots')
    @patch('backend.utils.cleanup_orphaned_records.cleanup_orphaned_recordings')
    def test_cleanup_dry_run_default(self, mock_cleanup_rec, mock_cleanup_snap, mock_session):
        """Test that dry_run defaults to True"""
        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock cleanup results
        snapshot_result = CleanupResult()
        mock_cleanup_snap.return_value = snapshot_result

        recording_result = CleanupResult()
        mock_cleanup_rec.return_value = recording_result

        # Run cleanup without specifying dry_run
        results = cleanup_orphaned_records(media_type="all")

        # Verify dry_run=True was passed
        mock_cleanup_snap.assert_called_once_with(mock_db, True)
        mock_cleanup_rec.assert_called_once_with(mock_db, True)
        assert results["summary"]["dry_run"] is True
