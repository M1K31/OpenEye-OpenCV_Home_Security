# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from __future__ import annotations

"""
Centralized Path Management System

Provides consistent path resolution across the application with:
- Environment variable support for custom storage locations
- Automatic directory creation
- Relative/absolute path conversion for database storage
- Type-safe path operations
"""

from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

# Get project root (opencv_surveillance directory)
# Structure: opencv_surveillance/backend/core/paths.py
# __file__ = opencv_surveillance/backend/core/paths.py
# parent = opencv_surveillance/backend/core
# parent.parent = opencv_surveillance/backend
# parent.parent.parent = opencv_surveillance
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Default paths (within opencv_surveillance/)
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "recordings"
DEFAULT_SNAPSHOTS_DIR = DEFAULT_DATA_DIR / "snapshots"
DEFAULT_THUMBNAILS_DIR = DEFAULT_DATA_DIR / "thumbnails"
# NOTE: Faces dir is at project root, not under data/ (per CLAUDE.md directory structure)
DEFAULT_FACES_DIR = PROJECT_ROOT / "faces"


class PathManager:
    """
    Centralized path management with environment variable support

    Environment Variables:
    - OPENEYE_DATA_DIR: Base data directory
    - OPENEYE_RECORDINGS_DIR: Recordings storage
    - OPENEYE_SNAPSHOTS_DIR: Motion detection snapshots
    - OPENEYE_THUMBNAILS_DIR: Thumbnail cache
    - OPENEYE_FACES_DIR: Face recognition training data

    Example:
        >>> from backend.core.paths import paths
        >>> snapshot_path = paths.snapshots_dir / "motion_cam1_123.jpg"
        >>> paths.ensure_directories()
    """

    def __init__(self):
        # Allow override via environment variables
        self.data_dir = Path(
            os.getenv("OPENEYE_DATA_DIR", str(DEFAULT_DATA_DIR))
        ).resolve()

        self.recordings_dir = Path(
            os.getenv("OPENEYE_RECORDINGS_DIR", str(DEFAULT_RECORDINGS_DIR))
        ).resolve()

        self.snapshots_dir = Path(
            os.getenv("OPENEYE_SNAPSHOTS_DIR", str(DEFAULT_SNAPSHOTS_DIR))
        ).resolve()

        self.thumbnails_dir = Path(
            os.getenv("OPENEYE_THUMBNAILS_DIR", str(DEFAULT_THUMBNAILS_DIR))
        ).resolve()

        self.faces_dir = Path(
            os.getenv("OPENEYE_FACES_DIR", str(DEFAULT_FACES_DIR))
        ).resolve()

        # Log configured paths
        logger.info("PathManager initialized:")
        logger.info(f"  Project root: {PROJECT_ROOT}")
        logger.info(f"  Data dir: {self.data_dir}")
        logger.info(f"  Recordings: {self.recordings_dir}")
        logger.info(f"  Snapshots: {self.snapshots_dir}")
        logger.info(f"  Thumbnails: {self.thumbnails_dir}")
        logger.info(f"  Faces: {self.faces_dir}")

        # Create directories if they don't exist
        self.ensure_directories()

    def ensure_directories(self):
        """Create all required directories if they don't exist"""
        directories = [
            ("Data", self.data_dir),
            ("Recordings", self.recordings_dir),
            ("Snapshots", self.snapshots_dir),
            ("Thumbnails", self.thumbnails_dir),
            ("Faces", self.faces_dir),
        ]

        for name, dir_path in directories:
            if not dir_path.exists():
                logger.info(f"Creating {name} directory: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)
            else:
                logger.debug(f"{name} directory exists: {dir_path}")

    def get_relative_path(self, absolute_path: Path | str) -> str:
        """
        Convert absolute path to relative (for database storage)

        Stores paths relative to PROJECT_ROOT when possible, otherwise absolute.
        This allows the database to remain portable if the project is moved.

        Args:
            absolute_path: Absolute path to convert

        Returns:
            Relative path string (e.g., "data/snapshots/file.jpg")
            or absolute path if outside project root
        """
        path = Path(absolute_path).resolve()
        try:
            relative = path.relative_to(PROJECT_ROOT)
            return str(relative)
        except ValueError:
            # Path is outside project root, store as absolute
            logger.warning(f"Path outside project root, storing absolute: {path}")
            return str(path)

    def resolve_path(self, stored_path: str) -> Path:
        """
        Resolve stored path to absolute path

        Args:
            stored_path: Path string from database (relative or absolute)

        Returns:
            Absolute Path object
        """
        path = Path(stored_path)
        if path.is_absolute():
            return path
        else:
            return (PROJECT_ROOT / path).resolve()

    def update_paths(
        self,
        recordings_dir: str | Path | None = None,
        snapshots_dir: str | Path | None = None,
        faces_dir: str | Path | None = None,
    ):
        """
        Update storage paths (typically called from settings API)

        Args:
            recordings_dir: New recordings directory
            snapshots_dir: New snapshots directory
            faces_dir: New faces directory
        """
        if recordings_dir:
            self.recordings_dir = Path(recordings_dir).resolve()
            logger.info(f"Updated recordings path: {self.recordings_dir}")

        if snapshots_dir:
            self.snapshots_dir = Path(snapshots_dir).resolve()
            logger.info(f"Updated snapshots path: {self.snapshots_dir}")

        if faces_dir:
            self.faces_dir = Path(faces_dir).resolve()
            logger.info(f"Updated faces path: {self.faces_dir}")

        # Ensure new directories exist
        self.ensure_directories()

    def get_disk_usage(self, directory: Path) -> dict:
        """
        Get disk usage statistics for a directory

        Args:
            directory: Directory to analyze

        Returns:
            {
                "total_files": int,
                "total_size_bytes": int,
                "total_size_mb": float,
                "total_size_gb": float
            }
        """
        if not directory.exists():
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "total_size_gb": 0.0
            }

        total_size = 0
        total_files = 0

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_files += 1
                total_size += file_path.stat().st_size

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
        }

    def get_all_disk_usage(self) -> dict:
        """
        Get disk usage for all storage directories

        Returns:
            {
                "recordings": {...},
                "snapshots": {...},
                "faces": {...},
                "total_size_gb": float
            }
        """
        recordings_usage = self.get_disk_usage(self.recordings_dir)
        snapshots_usage = self.get_disk_usage(self.snapshots_dir)
        faces_usage = self.get_disk_usage(self.faces_dir)

        total_gb = (
            recordings_usage["total_size_gb"]
            + snapshots_usage["total_size_gb"]
            + faces_usage["total_size_gb"]
        )

        return {
            "recordings": recordings_usage,
            "snapshots": snapshots_usage,
            "faces": faces_usage,
            "total_size_gb": round(total_gb, 2),
        }


# Global singleton instance
paths = PathManager()


# Convenience functions for backward compatibility
def get_project_root() -> Path:
    """Get the project root directory"""
    return PROJECT_ROOT


def get_recordings_dir() -> Path:
    """Get the recordings directory"""
    return paths.recordings_dir


def get_snapshots_dir() -> Path:
    """Get the snapshots directory"""
    return paths.snapshots_dir


def get_faces_dir() -> Path:
    """Get the faces directory"""
    return paths.faces_dir
