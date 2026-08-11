# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Storage paths must not depend on the process working directory.

This is guarded by tests because the failure mode leaves no trace. A
working-directory-relative path does not raise; it silently points at a
different place, SQLite creates an empty database there, and the application
comes up looking like a brand new install with every camera, face and recording
apparently gone. The app only ever worked because its start script happened to
cd into the app directory first — launch agents, systemd units and login items
do not.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core.paths import PROJECT_ROOT, resolve_under_project


class TestResolveUnderProject:
    def test_relative_paths_resolve_under_the_project_not_the_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert resolve_under_project("faces") == PROJECT_ROOT / "faces"

    def test_nested_relative_paths(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert resolve_under_project("data/snapshots") == PROJECT_ROOT / "data" / "snapshots"

    def test_absolute_paths_are_left_alone(self, tmp_path):
        assert resolve_under_project(tmp_path / "elsewhere") == tmp_path / "elsewhere"

    def test_result_is_stable_across_working_directories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = resolve_under_project("recordings")
        other = tmp_path / "somewhere_else"
        other.mkdir()
        monkeypatch.chdir(other)
        assert resolve_under_project("recordings") == first


class TestPathManagerHonoursTheProjectRoot:
    def test_relative_settings_do_not_follow_the_cwd(self, tmp_path, monkeypatch):
        """The stored settings on a real install are relative strings."""
        from backend.core.paths import PathManager

        monkeypatch.chdir(tmp_path)
        manager = PathManager()
        manager.update_paths(
            recordings_dir="recordings",
            snapshots_dir="data/snapshots",
            faces_dir="faces",
        )

        assert manager.faces_dir == PROJECT_ROOT / "faces"
        assert manager.recordings_dir == PROJECT_ROOT / "recordings"
        assert manager.snapshots_dir == PROJECT_ROOT / "data" / "snapshots"
        assert tmp_path not in manager.faces_dir.parents

    def test_absolute_settings_still_win(self, tmp_path):
        from backend.core.paths import PathManager

        manager = PathManager()
        target = tmp_path / "external_drive" / "faces"
        manager.update_paths(faces_dir=str(target))
        assert manager.faces_dir == target


class TestDatabaseUrlResolution:
    """
    Run in subprocesses: the URL is computed once at import, and the point of
    these tests is what happens under a different working directory and
    environment than the one the suite was started in.
    """

    def _url_from(self, cwd: Path, env_overrides: dict) -> str:
        env = {**os.environ, **env_overrides}
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        result = subprocess.run(
            [sys.executable, "-c",
             "from backend.database.session import SQLALCHEMY_DATABASE_URL as u; print(u)"],
            cwd=str(cwd), env=env, capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        return result.stdout.strip().splitlines()[-1]

    def test_default_database_does_not_follow_the_cwd(self, tmp_path):
        """The regression: 'sqlite:///./surveillance.db' meant whatever CWD was."""
        url = self._url_from(tmp_path, {"DATABASE_URL": ""})
        assert url == f"sqlite:///{PROJECT_ROOT / 'surveillance.db'}"
        assert str(tmp_path) not in url

    def test_configured_relative_path_resolves_under_the_app(self, tmp_path):
        url = self._url_from(tmp_path, {"DATABASE_URL": "sqlite:///./surveillance.db"})
        assert url == f"sqlite:///{PROJECT_ROOT / 'surveillance.db'}"

    def test_a_missing_configured_database_does_not_silently_start_empty(self, tmp_path):
        """
        Pointing at a nonexistent file must not quietly create one while a real
        database exists at the default location — that is indistinguishable from
        total data loss to the user.
        """
        if not (PROJECT_ROOT / "surveillance.db").exists():
            pytest.skip("no database at the default location to fall back to")

        missing = tmp_path / "not_here.db"
        url = self._url_from(tmp_path, {"DATABASE_URL": f"sqlite:///{missing}"})
        assert url == f"sqlite:///{PROJECT_ROOT / 'surveillance.db'}"
        assert str(missing) not in url

    def test_non_sqlite_urls_are_passed_through_untouched(self, tmp_path):
        dsn = "postgresql://user:pw@localhost:5432/openeye"
        assert self._url_from(tmp_path, {"DATABASE_URL": dsn}) == dsn


class TestAuditLogDirectory:
    def test_audit_logs_do_not_follow_the_cwd(self, tmp_path, monkeypatch):
        """Audit logs are written state, so they live under the data root."""
        from backend.core.audit_logger import AuditLogger
        from backend.core.paths import DATA_ROOT

        monkeypatch.chdir(tmp_path)
        assert AuditLogger().log_dir == DATA_ROOT / "logs" / "audit"


class TestDataRootSelection:
    """
    Where the application keeps what it writes.

    Separate from the application root because writable state beside the code is
    destroyed by any upgrade that replaces the code — and once the code ships
    inside a macOS bundle, that directory is not reliably writable at all.
    """

    def test_explicit_override_wins(self, tmp_path, monkeypatch):
        from backend.core.paths import default_data_root

        monkeypatch.setenv("OPENEYE_DATA_ROOT", str(tmp_path / "chosen"))
        assert default_data_root() == tmp_path / "chosen"

    def test_override_expands_the_home_shortcut(self, monkeypatch):
        from backend.core.paths import default_data_root

        monkeypatch.setenv("OPENEYE_DATA_ROOT", "~/openeye-data")
        assert default_data_root() == Path.home() / "openeye-data"

    def test_a_source_checkout_keeps_data_beside_the_code(self, tmp_path, monkeypatch):
        """Developers must see no change: today's behaviour is the checkout case."""
        from backend.core.paths import default_data_root, is_source_checkout

        monkeypatch.delenv("OPENEYE_DATA_ROOT", raising=False)
        checkout = tmp_path / "repo" / "opencv_surveillance"
        checkout.mkdir(parents=True)
        (tmp_path / "repo" / ".git").mkdir()

        assert is_source_checkout(checkout) is True
        assert default_data_root(checkout) == checkout

    def test_an_installed_tree_does_not_write_beside_the_code(self, tmp_path, monkeypatch):
        from backend.core.paths import default_data_root, is_source_checkout

        monkeypatch.delenv("OPENEYE_DATA_ROOT", raising=False)
        installed = tmp_path / "openeye" / "app"
        installed.mkdir(parents=True)

        assert is_source_checkout(installed) is False
        assert default_data_root(installed) != installed

    def test_linux_honours_xdg_data_home(self, tmp_path, monkeypatch):
        from backend.core import paths

        monkeypatch.delenv("OPENEYE_DATA_ROOT", raising=False)
        monkeypatch.setattr(paths.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        installed = tmp_path / "app"
        installed.mkdir()

        assert paths.default_data_root(installed) == tmp_path / "xdg" / "openeye"

    def test_linux_falls_back_to_local_share(self, tmp_path, monkeypatch):
        from backend.core import paths

        monkeypatch.delenv("OPENEYE_DATA_ROOT", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(paths.sys, "platform", "linux")
        installed = tmp_path / "app"
        installed.mkdir()

        assert paths.default_data_root(installed) == Path.home() / ".local" / "share" / "openeye"

    def test_macos_uses_application_support(self, tmp_path, monkeypatch):
        from backend.core import paths

        monkeypatch.delenv("OPENEYE_DATA_ROOT", raising=False)
        monkeypatch.setattr(paths.sys, "platform", "darwin")
        installed = tmp_path / "app"
        installed.mkdir()

        expected = Path.home() / "Library" / "Application Support" / "OpenEye"
        assert paths.default_data_root(installed) == expected


class TestResolveUnderDataRoot:
    def test_relative_paths_resolve_under_the_data_root(self, tmp_path, monkeypatch):
        from backend.core.paths import resolve_under_data_root

        monkeypatch.chdir(tmp_path)
        assert resolve_under_data_root("faces", tmp_path / "root") == tmp_path / "root" / "faces"

    def test_nested_relative_paths(self, tmp_path):
        from backend.core.paths import resolve_under_data_root

        got = resolve_under_data_root("data/snapshots", tmp_path / "root")
        assert got == tmp_path / "root" / "data" / "snapshots"

    def test_absolute_paths_are_left_alone(self, tmp_path):
        """An external drive stays where the user put it."""
        from backend.core.paths import resolve_under_data_root

        external = Path("/Volumes/Locker2/openeye/recordings")
        assert resolve_under_data_root(external, tmp_path / "root") == external

    def test_result_is_stable_across_working_directories(self, tmp_path, monkeypatch):
        from backend.core.paths import resolve_under_data_root

        root = tmp_path / "root"
        monkeypatch.chdir(tmp_path)
        first = resolve_under_data_root("recordings", root)
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.chdir(other)
        assert resolve_under_data_root("recordings", root) == first

    def test_shipped_and_written_content_resolve_differently(self, tmp_path):
        """The distinction the old code lacked entirely."""
        from backend.core.paths import resolve_under_data_root, resolve_under_project, APP_ROOT

        assert resolve_under_project("frontend/dist") == APP_ROOT / "frontend" / "dist"
        assert resolve_under_data_root("faces", tmp_path) == tmp_path / "faces"


class TestLegacyMediaAdoption:
    """
    An upgraded install must not appear to have lost its media.

    Resolving to a data root that does not exist yet, while thousands of files
    sit beside the code, produces no error at all — the galleries and recordings
    simply look gone. Same principle as the database fallback.
    """

    def _manager_with_roots(self, monkeypatch, app_root, data_root):
        from backend.core import paths

        monkeypatch.setattr(paths, "APP_ROOT", app_root)
        monkeypatch.setattr(paths, "DATA_ROOT", data_root)
        for name in ("OPENEYE_DATA_DIR", "OPENEYE_RECORDINGS_DIR",
                     "OPENEYE_SNAPSHOTS_DIR", "OPENEYE_THUMBNAILS_DIR",
                     "OPENEYE_FACES_DIR"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setattr(paths, "DEFAULT_DATA_DIR", data_root / "data")
        monkeypatch.setattr(paths, "DEFAULT_RECORDINGS_DIR", data_root / "recordings")
        monkeypatch.setattr(paths, "DEFAULT_SNAPSHOTS_DIR", data_root / "data" / "snapshots")
        monkeypatch.setattr(paths, "DEFAULT_THUMBNAILS_DIR", data_root / "data" / "thumbnails")
        monkeypatch.setattr(paths, "DEFAULT_FACES_DIR", data_root / "faces")
        return paths.PathManager()

    def test_populated_legacy_media_is_adopted(self, tmp_path, monkeypatch):
        app_root = tmp_path / "app"
        data_root = tmp_path / "data-root"
        legacy_faces = app_root / "faces" / "Mikel"
        legacy_faces.mkdir(parents=True)
        (legacy_faces / "a.jpg").write_bytes(b"x")
        (app_root / "recordings").mkdir(parents=True)
        (app_root / "recordings" / "clip.mp4").write_bytes(b"x")

        manager = self._manager_with_roots(monkeypatch, app_root, data_root)

        assert manager.faces_dir == app_root / "faces"
        assert manager.recordings_dir == app_root / "recordings"

    def test_empty_legacy_directories_are_ignored(self, tmp_path, monkeypatch):
        app_root = tmp_path / "app"
        data_root = tmp_path / "data-root"
        (app_root / "faces").mkdir(parents=True)

        manager = self._manager_with_roots(monkeypatch, app_root, data_root)

        assert manager.faces_dir == data_root / "faces"

    def test_a_populated_data_root_wins(self, tmp_path, monkeypatch):
        """Once migrated, the legacy directory must never pull it back."""
        app_root = tmp_path / "app"
        data_root = tmp_path / "data-root"
        (app_root / "faces").mkdir(parents=True)
        (app_root / "faces" / "stale.jpg").write_bytes(b"x")
        (data_root / "faces").mkdir(parents=True)
        (data_root / "faces" / "current.jpg").write_bytes(b"x")

        manager = self._manager_with_roots(monkeypatch, app_root, data_root)

        assert manager.faces_dir == data_root / "faces"

    def test_a_source_checkout_is_left_alone(self, tmp_path, monkeypatch):
        root = tmp_path / "checkout"
        (root / "faces").mkdir(parents=True)
        (root / "faces" / "a.jpg").write_bytes(b"x")

        manager = self._manager_with_roots(monkeypatch, root, root)

        assert manager.faces_dir == root / "faces"

    def test_adoption_survives_the_stored_settings_being_applied(self, tmp_path, monkeypatch):
        """
        The real upgrade path: settings hold relative strings and are applied at
        startup, after __init__. Adoption has to hold afterwards or it is
        pointless.
        """
        app_root = tmp_path / "app"
        data_root = tmp_path / "data-root"
        (app_root / "faces" / "Mikel").mkdir(parents=True)
        (app_root / "faces" / "Mikel" / "a.jpg").write_bytes(b"x")
        (app_root / "recordings").mkdir(parents=True)
        (app_root / "recordings" / "clip.mp4").write_bytes(b"x")

        manager = self._manager_with_roots(monkeypatch, app_root, data_root)
        manager.update_paths(recordings_dir="recordings", faces_dir="faces")

        assert manager.faces_dir == app_root / "faces"
        assert manager.recordings_dir == app_root / "recordings"
