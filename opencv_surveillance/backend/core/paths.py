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
import sys
import logging

logger = logging.getLogger(__name__)

# Get project root (opencv_surveillance directory)
# Structure: opencv_surveillance/backend/core/paths.py
# __file__ = opencv_surveillance/backend/core/paths.py
# parent = opencv_surveillance/backend/core
# parent.parent = opencv_surveillance/backend
# parent.parent.parent = opencv_surveillance
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# APP_ROOT is the preferred name. It holds *shipped* content — backend/,
# frontend/dist/, alembic/, model files — and is replaced wholesale on upgrade.
# PROJECT_ROOT remains as an alias so existing imports keep working.
APP_ROOT = PROJECT_ROOT

def is_source_checkout(app_root: Path = APP_ROOT) -> bool:
    """
    True when running from a working copy rather than an installed application.

    A checkout keeps its data beside the code, which is what developers expect
    and what every existing test assumes. An installed application must not, so
    this is the switch that decides which default applies.

    The marker is a `.git` directory at the app root or just above it. An
    installed tree has no `.git` — `scripts/sync-app.sh` never copies one — while
    a checkout always does. Deliberately not keyed on `requirements.txt` or
    `tests/`, since the installed tree carries the former.
    """
    return (app_root / ".git").exists() or (app_root.parent / ".git").exists()


def default_data_root(app_root: Path = APP_ROOT) -> Path:
    """
    Where this installation keeps everything it writes.

    Separate from the application root on purpose. Writable state that lives
    beside the code is destroyed by any upgrade that replaces the code, and once
    the code ships inside a macOS bundle that directory is not reliably writable
    at all.

    Order: an explicit override always wins, then a container mount, then the
    platform convention, and a working copy keeps today's behaviour.
    """
    override = (os.getenv("OPENEYE_DATA_ROOT") or "").strip()
    if override:
        return Path(os.path.normpath(os.path.expanduser(override)))

    if is_source_checkout(app_root):
        return app_root

    # Containers keep their data beside the code, because that is where the
    # volumes are mounted. The shipped compose file mounts /app/data,
    # /app/recordings and /app/faces, so the application directory is not
    # ephemeral there the way it is for a desktop install — the mounts are what
    # make the data survive, not the location.
    #
    # Falling through to the platform default here was a real regression: it
    # resolved to a home directory no volume covers, so every database write,
    # recording and face landed in the container's writable layer and vanished
    # on the next restart, silently. /data is honoured first for anyone using
    # that convention, and OPENEYE_DATA_ROOT above overrides either.
    if os.path.exists("/.dockerenv") or os.getenv("OPENEYE_IN_CONTAINER"):
        return Path("/data") if os.path.isdir("/data") else app_root

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "OpenEye"

    xdg = (os.getenv("XDG_DATA_HOME") or "").strip()
    base = Path(os.path.expanduser(xdg)) if xdg else home / ".local" / "share"
    return base / "openeye"


DATA_ROOT = default_data_root()

# Default storage locations. These hang off the data root, not the application
# root: in a source checkout the two are the same directory, so developers see
# no change, while an installed application keeps its media somewhere an upgrade
# will not overwrite.
DEFAULT_DATA_DIR = DATA_ROOT / "data"
DEFAULT_RECORDINGS_DIR = DATA_ROOT / "recordings"
DEFAULT_SNAPSHOTS_DIR = DEFAULT_DATA_DIR / "snapshots"
DEFAULT_THUMBNAILS_DIR = DEFAULT_DATA_DIR / "thumbnails"
# NOTE: Faces dir is at the root, not under data/ (per CLAUDE.md directory structure)
DEFAULT_FACES_DIR = DATA_ROOT / "faces"


def resolve_under_project(value: "str | Path") -> Path:
    """
    Resolve a path to *shipped* content against the application root.

    For read-only assets that travel with a release. Anything the application
    writes belongs under the data root instead — see resolve_under_data_root.

    Relative values are resolved against the application root, never against the
    process working directory. `Path("faces").resolve()` silently means
    "faces, relative to wherever this process happened to be started", which is
    how the gallery ended up in one directory while the configuration named
    another.
    """
    path = Path(value)
    if not path.is_absolute():
        path = APP_ROOT / path
    return Path(os.path.normpath(str(path)))


def resolve_under_data_root(value: "str | Path", data_root: Path | None = None) -> Path:
    """
    Resolve a path to *writable* state against the data root.

    The counterpart to resolve_under_project, and the one almost every caller
    wants: databases, galleries, recordings, snapshots, logs. The stored settings
    on an existing install are relative ("faces", "recordings",
    "data/snapshots"), so this is what decides where they land.
    """
    path = Path(value)
    if not path.is_absolute():
        path = (data_root or DATA_ROOT) / path
    return Path(os.path.normpath(str(path)))


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
        self.data_dir = resolve_under_data_root(
            os.getenv("OPENEYE_DATA_DIR", str(DEFAULT_DATA_DIR))
        )

        self.recordings_dir = resolve_under_data_root(
            os.getenv("OPENEYE_RECORDINGS_DIR", str(DEFAULT_RECORDINGS_DIR))
        )

        self.snapshots_dir = resolve_under_data_root(
            os.getenv("OPENEYE_SNAPSHOTS_DIR", str(DEFAULT_SNAPSHOTS_DIR))
        )

        self.thumbnails_dir = resolve_under_data_root(
            os.getenv("OPENEYE_THUMBNAILS_DIR", str(DEFAULT_THUMBNAILS_DIR))
        )

        self.faces_dir = resolve_under_data_root(
            os.getenv("OPENEYE_FACES_DIR", str(DEFAULT_FACES_DIR))
        )

        # Installs that predate the data root keep their media beside the code.
        # Adopt it rather than starting against empty directories.
        self._adopt_legacy_locations()

        # Log configured paths
        logger.info("PathManager initialized:")
        logger.info(f"  App root (shipped code): {APP_ROOT}")
        logger.info(f"  Data root (writable):    {DATA_ROOT}")
        logger.info(f"  Data dir: {self.data_dir}")
        logger.info(f"  Recordings: {self.recordings_dir}")
        logger.info(f"  Snapshots: {self.snapshots_dir}")
        logger.info(f"  Thumbnails: {self.thumbnails_dir}")
        logger.info(f"  Faces: {self.faces_dir}")

        # Create directories if they don't exist
        self.ensure_directories()

    @staticmethod
    def _has_content(path: Path) -> bool:
        try:
            return path.is_dir() and any(path.iterdir())
        except OSError:
            return False

    def _adopt_legacy_locations(self):
        """
        Keep using media that predates the data root, instead of starting empty.

        An install upgraded to a build that separates the data root from the
        application root will resolve its media to a directory that does not
        exist yet, while thousands of files sit beside the code where the old
        resolution put them. Nothing would error: the galleries, recordings and
        snapshots would simply appear to be gone.

        So where the configured directory holds nothing and the pre-data-root
        location holds something, use the latter and say so loudly. This is the
        same principle the database applies in database/session.py, and it keeps
        an install working until the storage migration moves the files properly.
        """
        if DATA_ROOT == APP_ROOT:
            return  # A source checkout; the two locations are the same.

        legacy = {
            "faces_dir": APP_ROOT / "faces",
            "recordings_dir": APP_ROOT / "recordings",
            "snapshots_dir": APP_ROOT / "data" / "snapshots",
            "thumbnails_dir": APP_ROOT / "data" / "thumbnails",
        }

        for attribute, legacy_path in legacy.items():
            configured = getattr(self, attribute)
            if self._has_content(configured) or not self._has_content(legacy_path):
                continue

            logger.critical(
                "%s is empty but media is present at %s. Using the existing "
                "location. Run the storage migration to move it under %s.",
                configured, legacy_path, DATA_ROOT,
            )
            setattr(self, attribute, legacy_path)

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

        Stores paths relative to DATA_ROOT when possible, otherwise absolute.
        This keeps stored settings portable if the installation is moved.

        Relative to the *data* root specifically: these strings are read back by
        resolve_under_data_root, so measuring them against the application root
        would silently change what an existing stored setting means.

        Args:
            absolute_path: Absolute path to convert

        Returns:
            Relative path string (e.g., "data/snapshots/file.jpg")
            or absolute path if outside project root
        """
        path = Path(absolute_path).resolve()
        try:
            relative = path.relative_to(DATA_ROOT)
            return str(relative)
        except ValueError:
            # Path is outside project root, store as absolute
            logger.warning(f"Path outside data root, storing absolute: {path}")
            return str(path)

    def resolve_path(self, stored_path: str) -> Path:
        """
        Resolve stored path to absolute path

        Args:
            stored_path: Path string from database (relative or absolute)

        Returns:
            Absolute Path object
        """
        return resolve_under_data_root(stored_path)

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
            self.recordings_dir = resolve_under_data_root(recordings_dir)
            logger.info(f"Updated recordings path: {self.recordings_dir}")

        if snapshots_dir:
            self.snapshots_dir = resolve_under_data_root(snapshots_dir)
            logger.info(f"Updated snapshots path: {self.snapshots_dir}")

        if faces_dir:
            self.faces_dir = resolve_under_data_root(faces_dir)
            logger.info(f"Updated faces path: {self.faces_dir}")

        # Re-check for pre-data-root media. This is the path that actually runs
        # on an upgraded install: the stored settings are relative strings
        # ("faces", "recordings"), applied at startup *after* __init__, so
        # without this the adoption done there would be silently overwritten.
        self._adopt_legacy_locations()

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


