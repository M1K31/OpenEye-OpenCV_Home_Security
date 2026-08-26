# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Backing up and restoring what cannot be replaced.

A backup carries the database and the face galleries. They travel together
because they describe the same thing from two sides: the database records that
a person exists, the gallery holds the photographs and encodings that let the
recogniser find them. Restoring one without the other reproduces the mismatch
this codebase spent a week removing.

Restore is destructive by definition, so most of what follows is about refusing
to do it. An archive is treated as untrusted whatever its provenance — a restore
is exactly the moment somebody handles a file they were given by someone else,
often while something has already gone wrong.
"""

import json
import sqlite3
import tarfile
import tempfile
from pathlib import Path

import pytest

from backend.core import backup as backup_module


@pytest.fixture
def install(tmp_path, monkeypatch):
    """A self-contained data root: a database, some galleries, nothing live."""
    root = tmp_path / "data"
    root.mkdir(exist_ok=True)

    db = root / "surveillance.db"
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE persons (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE face_detection_events (id INTEGER PRIMARY KEY, person_name TEXT);
        CREATE TABLE cameras (id INTEGER PRIMARY KEY, camera_id TEXT);
        INSERT INTO persons (name) VALUES ('Mikel'), ('Yaleska');
        INSERT INTO face_detection_events (person_name) VALUES ('Mikel');
        INSERT INTO cameras (camera_id) VALUES ('front');
        """
    )
    connection.commit()
    connection.close()

    faces = root / "faces"
    (faces / "Mikel" / "detected").mkdir(parents=True, exist_ok=True)
    (faces / "Mikel" / "detected" / "a.jpg").write_bytes(b"original")

    monkeypatch.setattr(backup_module, "_data_root", lambda: root)
    monkeypatch.setattr(backup_module, "_database_path", lambda: db)
    return {"root": root, "db": db, "faces": faces}


def _people(db_path):
    connection = sqlite3.connect(db_path)
    try:
        return sorted(r[0] for r in connection.execute("SELECT name FROM persons"))
    finally:
        connection.close()


class TestCreating:
    def test_a_backup_holds_the_database_and_the_galleries(self, install):
        result = backup_module.create_backup()

        with tarfile.open(result["path"], "r:gz") as tar:
            names = tar.getnames()

        assert backup_module.DB_MEMBER in names
        assert any(n.startswith(backup_module.FACES_MEMBER) for n in names)
        assert backup_module.MANIFEST_NAME in names

    def test_it_records_what_it_contains(self, install):
        result = backup_module.create_backup()
        assert result["contents"]["persons"] == 2
        assert result["contents"]["face_detection_events"] == 1

    def test_the_live_database_is_left_alone(self, install):
        before = install["db"].read_bytes()
        backup_module.create_backup()
        assert install["db"].read_bytes() == before

    def test_a_backup_can_be_taken_while_the_database_is_open(self, install):
        """
        The reason for the online backup API rather than copying the file.

        A running application holds the database open with a write-ahead log
        beside it; copying those files by hand can capture a torn state.
        """
        holder = sqlite3.connect(install["db"])
        holder.execute("INSERT INTO persons (name) VALUES ('Yalena')")
        holder.commit()
        try:
            result = backup_module.create_backup()
        finally:
            holder.close()

        assert result["contents"]["persons"] == 3


class TestRetention:
    def test_only_the_newest_are_kept(self, install):
        import time
        for _ in range(4):
            backup_module.create_backup()
            time.sleep(1.05)   # the filename carries a one-second stamp

        removed = backup_module.prune_backups(keep=2)

        assert len(removed) == 2
        assert len(backup_module.list_backups()) == 2

    def test_it_refuses_to_keep_none(self, install):
        # "Keep zero" is never what somebody means, and would delete every
        # backup at the moment they are most likely to need one.
        with pytest.raises(ValueError):
            backup_module.prune_backups(keep=0)

    def test_backups_are_listed_newest_first(self, install):
        import time
        backup_module.create_backup()
        time.sleep(1.05)
        backup_module.create_backup()

        listed = backup_module.list_backups()
        assert listed[0]["created_at"] >= listed[1]["created_at"]


class TestRestoring:
    def test_it_puts_back_what_was_there(self, install):
        archive = backup_module.create_backup()["path"]

        # Everything changes after the backup.
        connection = sqlite3.connect(install["db"])
        connection.execute("DELETE FROM persons WHERE name='Yaleska'")
        connection.commit()
        connection.close()
        (install["faces"] / "Mikel" / "detected" / "a.jpg").write_bytes(b"changed")

        backup_module.restore_backup(archive)

        assert _people(install["db"]) == ["Mikel", "Yaleska"]
        assert (install["faces"] / "Mikel" / "detected" / "a.jpg").read_bytes() == b"original"

    def test_a_safety_copy_is_taken_first(self, install):
        """
        A restore is usually chosen because something has already gone wrong.
        Choosing it by mistake at that moment should not be the end of it.
        """
        archive = backup_module.create_backup()["path"]

        connection = sqlite3.connect(install["db"])
        connection.execute("INSERT INTO persons (name) VALUES ('Mikayla')")
        connection.commit()
        connection.close()

        result = backup_module.restore_backup(archive)

        assert "Mikayla" not in _people(install["db"]), "restore did not take effect"
        # ...but it is still recoverable.
        safety = Path(result["safety_copy"])
        assert safety.is_file()
        with tarfile.open(safety, "r:gz") as tar:
            with tempfile.TemporaryDirectory() as tmp:
                tar.extract(backup_module.DB_MEMBER, tmp)
                assert "Mikayla" in _people(Path(tmp) / backup_module.DB_MEMBER)

    def test_it_says_a_restart_is_needed(self, install):
        # The running process keeps its own handle on the old file. Saying so
        # is better than closing a live engine underneath request handlers.
        archive = backup_module.create_backup()["path"]
        assert backup_module.restore_backup(archive)["restart_required"] is True

    def test_stale_write_ahead_files_are_removed(self, install):
        """
        A leftover -wal belongs to the database being replaced. Left in place,
        SQLite would try to replay it against the restored file.
        """
        archive = backup_module.create_backup()["path"]
        wal = Path(str(install["db"]) + "-wal")
        wal.write_bytes(b"stale")

        backup_module.restore_backup(archive)

        assert not wal.exists()


class TestRefusing:
    def test_a_file_that_is_not_a_backup(self, install, tmp_path):
        stranger = tmp_path / "holiday-photos.tar.gz"
        with tarfile.open(stranger, "w:gz") as tar:
            payload = tmp_path / "beach.jpg"
            payload.write_bytes(b"not a database")
            tar.add(payload, arcname="beach.jpg")

        with pytest.raises(ValueError, match="not an OpenEye backup"):
            backup_module.inspect_backup(stranger)

    def test_a_backup_from_a_format_this_version_cannot_read(self, install, tmp_path):
        archive = tmp_path / "future.tar.gz"
        manifest = tmp_path / backup_module.MANIFEST_NAME
        manifest.write_text(json.dumps({"format": 99}))
        db = tmp_path / backup_module.DB_MEMBER
        db.write_bytes(b"")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(manifest, arcname=backup_module.MANIFEST_NAME)
            tar.add(db, arcname=backup_module.DB_MEMBER)

        with pytest.raises(ValueError, match="format"):
            backup_module.inspect_backup(archive)

    def test_a_database_that_is_not_ours(self, install, tmp_path):
        """
        A valid SQLite file is not necessarily an OpenEye database, and
        replacing a live one with somebody's address book should fail before
        anything is destroyed rather than after.
        """
        foreign = tmp_path / "foreign.db"
        connection = sqlite3.connect(foreign)
        connection.execute("CREATE TABLE contacts (id INTEGER)")
        connection.commit()
        connection.close()

        with pytest.raises(ValueError, match="missing"):
            backup_module._verify_database(foreign)

    def test_a_corrupt_database_is_rejected(self, install, tmp_path):
        broken = tmp_path / "broken.db"
        broken.write_bytes(b"this is not a database at all, not even close")

        with pytest.raises(ValueError):
            backup_module._verify_database(broken)


class TestTheArchiveIsUntrusted:
    """
    A tar can name a path outside where it is being unpacked, and extractall
    will follow it. The archive is chosen by whoever is restoring, but that is
    exactly the moment somebody handles a file they were sent.
    """

    def test_a_path_escaping_the_target_is_refused(self, tmp_path):
        archive = tmp_path / "evil.tar.gz"
        payload = tmp_path / "payload"
        payload.write_bytes(b"pwned")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(payload, arcname="../../escaped.txt")

        destination = tmp_path / "unpack"
        destination.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            kept = list(backup_module._safe_members(tar, destination))

        assert kept == [], "a path traversing out of the target was accepted"

    def test_links_are_refused(self, tmp_path):
        """
        A symlink in an archive can point anywhere on the filesystem, and
        writing through it writes there.
        """
        archive = tmp_path / "links.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            info = tarfile.TarInfo("shortcut")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tar.addfile(info)

        destination = tmp_path / "unpack"
        destination.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            kept = list(backup_module._safe_members(tar, destination))

        assert kept == []

    def test_ordinary_members_still_pass(self, tmp_path):
        # The guard must not be so strict that a real backup cannot restore.
        archive = tmp_path / "fine.tar.gz"
        payload = tmp_path / "surveillance.db"
        payload.write_bytes(b"x")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(payload, arcname="surveillance.db")

        destination = tmp_path / "unpack"
        destination.mkdir()
        with tarfile.open(archive, "r:gz") as tar:
            kept = [m.name for m in backup_module._safe_members(tar, destination)]

        assert kept == ["surveillance.db"]


class TestTheSafetyCopyCannotDestroyWhatItProtects:
    """
    A bug this file caught before the feature shipped.

    Archive names carried a per-second timestamp, and a restore takes its safety
    copy immediately before reading the archive it is restoring. Within the same
    second the two names collided: the safety copy was written over the archive
    being restored, so the restore put back the state it was meant to replace,
    and the copy that made the operation reversible destroyed the thing it was
    protecting.
    """

    def test_a_safety_copy_never_lands_on_the_archive_being_restored(self, install):
        archive = Path(backup_module.create_backup()["path"])

        connection = sqlite3.connect(install["db"])
        connection.execute("DELETE FROM persons WHERE name='Yaleska'")
        connection.commit()
        connection.close()

        # Taken in the same second as the archive, which is what collided.
        result = backup_module.restore_backup(archive)

        assert Path(result["safety_copy"]) != archive
        assert _people(install["db"]) == ["Mikel", "Yaleska"], (
            "the archive was overwritten by its own safety copy"
        )

    def test_two_backups_in_the_same_second_do_not_collide(self, install):
        first = backup_module.create_backup()["path"]
        second = backup_module.create_backup()["path"]
        assert first != second
        assert Path(first).is_file() and Path(second).is_file()

    def test_a_safety_copy_is_listed_so_it_can_be_restored_from(self, install):
        # Otherwise the only way back from a mistaken restore is invisible.
        archive = backup_module.create_backup()["path"]
        backup_module.restore_backup(archive)

        kinds = {e["kind"] for e in backup_module.list_backups()}
        assert "pre-restore" in kinds

    def test_rotation_does_not_expire_safety_copies(self, install):
        import time
        archive = backup_module.create_backup()["path"]
        backup_module.restore_backup(archive)
        time.sleep(1.05)
        for _ in range(3):
            backup_module.create_backup()
            time.sleep(1.05)

        backup_module.prune_backups(keep=1)

        remaining = backup_module.list_backups()
        assert any(e["kind"] == "pre-restore" for e in remaining), (
            "the record of what a restore replaced was rotated away"
        )
