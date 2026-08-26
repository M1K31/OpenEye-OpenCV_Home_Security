# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Back up and restore what cannot be replaced.

What is in a backup, and what is not
------------------------------------
The database and the face galleries, and nothing else. Measured on a live
install:

    database      9 MB        identities, events, cameras, settings
    faces/       11 MB   841 files, the galleries and encodings
    snapshots/  6.5 GB 17,696 files
    recordings/ 3.5 GB  1,486 files

The first two are irreplaceable and small. The other two are bulk media already
governed by retention rules — they are *meant* to expire, and a single backup
including snapshots would be two thirds of the data root, so keeping several
would be impractical.

The database and the galleries have to travel together. The database records
that a person exists; the gallery holds the photographs and the encodings that
let the recogniser find them. Restoring one without the other reproduces exactly
the mismatch this codebase has spent a week removing — a person who exists in
one place and not the other.

A detection whose snapshot is missing degrades on its own: the interface
already handles an image that will not load.

The database is copied with SQLite's online backup API rather than by copying
the file. A running application holds it open with WAL alongside, and copying
those three files by hand can capture a torn state; the online API takes a
consistent snapshot of a live database, which is the whole reason it exists.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Written into every archive so a restore can tell an OpenEye backup from any
# other tar file it is handed, and so a future format change can be detected
# rather than silently mis-restored.
MANIFEST_NAME = "openeye-backup.json"
MANIFEST_FORMAT = 1

# The names inside the archive. Fixed, so restore knows where to look.
DB_MEMBER = "surveillance.db"
FACES_MEMBER = "faces"

# Tables a file must have before it is allowed to replace a live database.
# Not a schema check — a backup from an older version is still a legitimate
# thing to restore — just enough to establish this is an OpenEye database and
# not some other SQLite file.
REQUIRED_TABLES = ("persons", "face_detection_events", "cameras")


def _data_root() -> Path:
    from backend.core.paths import DATA_ROOT
    return Path(DATA_ROOT)


def backups_dir() -> Path:
    """Where scheduled backups are kept."""
    directory = _data_root() / "backups"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _database_path() -> Path:
    """
    The live database file, derived from the configured URL.

    Read from DATABASE_URL rather than assumed, so a relocated data root or a
    custom path is backed up rather than a file that is not in use.
    """
    from backend.database.session import SQLALCHEMY_DATABASE_URL

    url = SQLALCHEMY_DATABASE_URL
    if not url.startswith("sqlite"):
        raise RuntimeError(
            "Backup supports SQLite only; this install uses "
            f"{url.split(':', 1)[0]}. Use that database's own backup tooling."
        )
    # sqlite:////abs/path  or  sqlite:///relative/path
    path = url.split("sqlite:///", 1)[1]
    return Path(path if path.startswith("/") else path).resolve()


# ---------------------------------------------------------------------------
# Creating
# ---------------------------------------------------------------------------

def create_backup(destination: Optional[Path] = None,
                  prefix: str = "openeye-backup") -> Dict:
    """
    Write one archive containing the database and the face galleries.

    Safe to run while the application is serving: the database goes through
    SQLite's online backup API, and the galleries are ordinary files that the
    application only appends to.

    `prefix` separates a scheduled backup from the safety copy a restore takes,
    so the two can never be confused for one another — see restore_backup.
    """
    started = datetime.now()
    target_dir = Path(destination) if destination else backups_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Never overwrite an existing archive.
    #
    # The stamp is per-second, and a restore takes its safety copy immediately
    # before reading the archive it is restoring. Taken within the same second,
    # the safety copy landed on the very file being restored — so the restore
    # then put back the state it was supposed to replace, and the copy meant to
    # make the operation reversible destroyed the thing it was protecting.
    stamp = started.strftime("%Y%m%d-%H%M%S")
    archive = target_dir / f"{prefix}-{stamp}.tar.gz"
    attempt = 1
    while archive.exists():
        attempt += 1
        archive = target_dir / f"{prefix}-{stamp}-{attempt}.tar.gz"

    db_path = _database_path()
    faces = _data_root() / "faces"

    with tempfile.TemporaryDirectory() as workspace:
        work = Path(workspace)
        staged_db = work / DB_MEMBER

        # Consistent snapshot of a live database.
        source = sqlite3.connect(str(db_path))
        try:
            destination_db = sqlite3.connect(str(staged_db))
            try:
                with destination_db:
                    source.backup(destination_db)
            finally:
                destination_db.close()
        finally:
            source.close()

        counts = _summarise(staged_db)
        manifest = {
            "format": MANIFEST_FORMAT,
            "created_at": started.isoformat(),
            "database_bytes": staged_db.stat().st_size,
            "contents": counts,
        }
        (work / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

        with tarfile.open(archive, "w:gz") as tar:
            tar.add(staged_db, arcname=DB_MEMBER)
            tar.add(work / MANIFEST_NAME, arcname=MANIFEST_NAME)
            if faces.is_dir():
                tar.add(faces, arcname=FACES_MEMBER)

    result = {
        "path": str(archive),
        "bytes": archive.stat().st_size,
        "seconds": round((datetime.now() - started).total_seconds(), 2),
        "contents": manifest["contents"],
    }
    logger.info("Backup written: %s (%.1f MB, %ss)",
                archive.name, result["bytes"] / 1e6, result["seconds"])
    return result


def _summarise(db_path: Path) -> Dict[str, int]:
    """A few row counts, so a backup can be described without opening it."""
    counts: Dict[str, int] = {}
    connection = sqlite3.connect(str(db_path))
    try:
        for table in REQUIRED_TABLES:
            try:
                counts[table] = connection.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                counts[table] = -1
    finally:
        connection.close()
    return counts


def list_backups(directory: Optional[Path] = None) -> List[Dict]:
    """Every backup on hand, newest first."""
    target = Path(directory) if directory else backups_dir()
    if not target.is_dir():
        return []

    entries = []
    # Safety copies are listed too. One is taken immediately before every
    # restore, and it is the only route back from a restore chosen by mistake —
    # so leaving it out of the list would hide the recovery path at the exact
    # moment somebody needs it.
    for pattern, kind in (("openeye-backup-*.tar.gz", "scheduled"),
                          ("openeye-pre-restore-*.tar.gz", "pre-restore")):
        for path in target.glob(pattern):
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append({
                "name": path.name,
                "path": str(path),
                "kind": kind,
                "bytes": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return sorted(entries, key=lambda e: e["created_at"], reverse=True)


def prune_backups(keep: int, directory: Optional[Path] = None) -> List[str]:
    """
    Keep the newest `keep` backups and remove the rest.

    A backup nobody prunes fills a disk, and a full disk is how a surveillance
    system stops recording — so retention is part of the feature, not a
    refinement of it.
    """
    if keep < 1:
        raise ValueError("keep at least one backup")

    # Only scheduled backups are pruned. A safety copy is the record of what
    # was replaced by a restore, and expiring it on the ordinary rotation would
    # quietly remove the one thing that makes a restore reversible.
    scheduled = [e for e in list_backups(directory) if e["kind"] == "scheduled"]

    removed = []
    for entry in scheduled[keep:]:
        try:
            Path(entry["path"]).unlink()
            removed.append(entry["name"])
        except OSError as exc:
            logger.warning("Could not remove old backup %s: %s", entry["name"], exc)
    if removed:
        logger.info("Pruned %d old backup(s)", len(removed))
    return removed


# ---------------------------------------------------------------------------
# Inspecting, before trusting
# ---------------------------------------------------------------------------

def inspect_backup(archive: Path) -> Dict:
    """
    Describe an archive without unpacking it anywhere it could do harm.

    Called before a restore so the operator sees what they are about to replace
    their data with, and so a file that is not an OpenEye backup is refused
    before anything is destroyed.
    """
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(f"no such backup: {archive}")

    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
        if MANIFEST_NAME not in names:
            raise ValueError(
                "This file is not an OpenEye backup — it has no manifest.")
        if DB_MEMBER not in names:
            raise ValueError(
                "This backup contains no database and cannot be restored.")

        manifest = json.loads(tar.extractfile(MANIFEST_NAME).read())

    if manifest.get("format") != MANIFEST_FORMAT:
        raise ValueError(
            f"This backup is format {manifest.get('format')}, and this version "
            f"reads format {MANIFEST_FORMAT}."
        )

    return {
        "created_at": manifest.get("created_at"),
        "contents": manifest.get("contents", {}),
        "bytes": archive.stat().st_size,
        "includes_faces": any(n.startswith(FACES_MEMBER) for n in names),
    }


def _safe_members(tar: tarfile.TarFile, destination: Path):
    """
    Yield only members that land inside `destination`.

    A tar archive can name `../../etc/whatever`, and extractall will happily
    follow it. This archive is chosen by whoever is restoring, but a restore is
    exactly the moment someone is handling a file they were sent by somebody
    else, so the archive is treated as untrusted regardless of who supplied it.
    Symlinks and links are refused outright rather than resolved.
    """
    destination = destination.resolve()
    for member in tar.getmembers():
        if member.issym() or member.islnk():
            logger.warning("Refusing link in backup: %s", member.name)
            continue
        resolved = (destination / member.name).resolve()
        if not str(resolved).startswith(str(destination) + os.sep) and resolved != destination:
            logger.warning("Refusing path outside the target: %s", member.name)
            continue
        yield member


# ---------------------------------------------------------------------------
# Restoring
# ---------------------------------------------------------------------------

def restore_backup(archive: Path) -> Dict:
    """
    Replace the database and galleries with those in `archive`.

    Everything recorded since the backup was taken is replaced. A safety copy
    of the current state is written FIRST and its location returned, because a
    restore is usually chosen when something has already gone wrong, and a
    restore chosen by mistake at that moment should not be the end of it.

    The application keeps the database open, so the running process goes on
    using the old file until it is restarted. That is reported rather than
    worked around: closing a live engine underneath request handlers trades a
    clear "restart to finish" for an unpredictable failure mid-request.
    """
    archive = Path(archive)
    details = inspect_backup(archive)          # refuses anything unsuitable

    db_path = _database_path()
    faces = _data_root() / "faces"

    # Its own prefix, so it is recognisable as what it is and can never collide
    # with the archive being restored.
    safety = create_backup(prefix="openeye-pre-restore")
    logger.info("Safety copy taken before restore: %s", safety["path"])

    with tempfile.TemporaryDirectory() as workspace:
        work = Path(workspace)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(work, members=_safe_members(tar, work))

        staged_db = work / DB_MEMBER
        if not staged_db.is_file():
            raise ValueError("The backup's database was not extractable.")
        # Prove it opens and holds what it should before replacing anything.
        _verify_database(staged_db)

        # WAL and shared-memory files belong to the OLD database. Left behind,
        # SQLite would try to replay them against the restored file.
        for suffix in ("-wal", "-shm"):
            companion = Path(str(db_path) + suffix)
            if companion.exists():
                companion.unlink()

        shutil.copy2(staged_db, db_path)

        restored_faces = work / FACES_MEMBER
        if restored_faces.is_dir():
            if faces.exists():
                shutil.rmtree(faces)
            shutil.move(str(restored_faces), str(faces))

    logger.info("Restored from %s", archive.name)
    return {
        "restored_from": str(archive),
        "backup_created_at": details["created_at"],
        "contents": details["contents"],
        "safety_copy": safety["path"],
        "restart_required": True,
    }


def _verify_database(path: Path) -> None:
    """Refuse a file that is not a usable OpenEye database."""
    try:
        connection = sqlite3.connect(str(path))
    except sqlite3.Error as exc:
        raise ValueError(f"The backup's database will not open: {exc}") from exc

    try:
        present = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
    except sqlite3.DatabaseError as exc:
        raise ValueError(
            f"The backup's database is not readable: {exc}") from exc
    finally:
        connection.close()

    missing = [t for t in REQUIRED_TABLES if t not in present]
    if missing:
        raise ValueError(
            "This does not look like an OpenEye database — it is missing: "
            + ", ".join(missing)
        )
