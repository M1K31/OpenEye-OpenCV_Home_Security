# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Backing up and restoring, over the API.

Every route here is admin-only. Listing backups reveals what a system holds and
when it was last working; creating one reads the whole database; restoring
replaces it. None of those belong to an ordinary user, and restore in
particular is the most destructive action the application offers.
"""

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.schemas import user as user_schema
from backend.core import backup as backup_module
from backend.core.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

# An OpenEye backup of a 9 MB database and 11 MB of galleries compresses to
# about 20 MB. The ceiling is generous enough for a much larger install and
# still refuses a file nobody meant to send — an upload is read into a temporary
# file before anything inspects it, so the limit is what stops a large upload
# filling the disk before it can be rejected.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024   # 2 GB
UPLOAD_CHUNK = 1024 * 1024


@router.get("/backups")
def list_backups(current_user: user_schema.User = Depends(require_admin)):
    """
    Every backup on hand, newest first.

    Includes the safety copies taken before a restore. Those are the only route
    back from a restore chosen by mistake, so hiding them would remove the
    recovery path at the moment it matters.
    """
    entries = backup_module.list_backups()
    return {
        "backups": entries,
        "directory": str(backup_module.backups_dir()),
        "total_bytes": sum(e["bytes"] for e in entries),
    }


@router.post("/backups")
def create_backup_now(current_user: user_schema.User = Depends(require_admin)):
    """Take a backup immediately, without waiting for the nightly run."""
    try:
        return backup_module.create_backup()
    except Exception as exc:
        logger.error("Backup failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Backup failed: {exc}")


@router.post("/backups/inspect")
async def inspect_uploaded_backup(
    file: UploadFile = File(...),
    current_user: user_schema.User = Depends(require_admin),
):
    """
    Describe an uploaded archive without restoring anything.

    So the operator sees what they are about to replace their data with — when
    it was taken and how many people and detections it holds — before agreeing
    to it, rather than after.
    """
    with _received(file) as path:
        try:
            return backup_module.inspect_backup(path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))


@router.post("/backups/restore")
async def restore_from_upload(
    file: UploadFile = File(...),
    current_user: user_schema.User = Depends(require_admin),
):
    """
    Replace the database and galleries with an uploaded backup.

    Everything recorded since that backup was taken is replaced. A safety copy
    of the current state is written first and its name returned.

    The running process keeps its own handle on the old database, so it goes on
    using it until restarted. That is reported rather than worked around:
    closing a live engine underneath in-flight requests trades a clear
    "restart to finish" for an unpredictable failure part-way through one.
    """
    with _received(file) as path:
        try:
            result = backup_module.restore_backup(path)
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error("Restore failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Restore failed: {exc}")

    logger.warning(
        "Database restored from an upload by %s — a restart is required",
        current_user.username)
    return result


@router.post("/backups/{name}/restore")
def restore_from_stored(
    name: str,
    current_user: user_schema.User = Depends(require_admin),
):
    """
    Restore one of the backups this system already holds.

    The name is matched against the listing rather than joined onto a path, so
    a crafted name cannot reach a file outside the backup directory.
    """
    match = next(
        (e for e in backup_module.list_backups() if e["name"] == name), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"No backup named {name}")

    try:
        result = backup_module.restore_backup(Path(match["path"]))
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    logger.warning("Database restored from %s by %s — a restart is required",
                   name, current_user.username)
    return result


class _received:
    """
    Stream an upload to a temporary file, and remove it afterwards.

    Read in chunks rather than with `await file.read()`, which would hold the
    whole archive in memory — a 2 GB upload would then cost 2 GB of resident
    memory on a machine that is also decoding video.
    """

    def __init__(self, upload: UploadFile):
        self._upload = upload
        self._path = None

    def __enter__(self) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
        self._path = Path(handle.name)
        written = 0
        try:
            while True:
                chunk = self._upload.file.read(UPLOAD_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="That file is larger than any OpenEye backup.",
                    )
                handle.write(chunk)
        except Exception:
            handle.close()
            self._path.unlink(missing_ok=True)
            raise
        handle.close()
        return self._path

    def __exit__(self, *exc_info):
        if self._path:
            self._path.unlink(missing_ok=True)
        return False
