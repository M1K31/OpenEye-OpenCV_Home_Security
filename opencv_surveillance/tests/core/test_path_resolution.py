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
        from backend.core.audit_logger import AuditLogger

        monkeypatch.chdir(tmp_path)
        assert AuditLogger().log_dir == PROJECT_ROOT / "logs" / "audit"
