# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Configuration must not depend on how the process was launched.

The failure these guard against is silent and severe: started without the shell
environment `start.sh` provides, the application comes up with no SECRET_KEY
(every user logged out) and no ECOSYSTEM_HMAC_SECRET (peer authentication fails
without an obvious error). Nothing raises.
"""

import os
import stat

import pytest

from backend.core import config_loader


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """These names must not leak in from the developer's own environment."""
    for name in ("OE_TEST_VALUE", "OE_TEST_OTHER", "SECRET_KEY", "JWT_SECRET_KEY",
                 "ECOSYSTEM_HMAC_SECRET", "ECOSYSTEM_REGISTRY_URL"):
        monkeypatch.delenv(name, raising=False)


def _write(path, **values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


class TestLoading:
    def test_reads_the_config_file_from_the_data_root(self, tmp_path):
        _write(tmp_path / "config.env", OE_TEST_VALUE="from-data-root")

        loaded = config_loader.load_configuration(tmp_path)

        assert os.environ["OE_TEST_VALUE"] == "from-data-root"
        assert tmp_path / "config.env" in loaded

    def test_missing_file_is_not_an_error(self, tmp_path, monkeypatch):
        from backend.core import paths

        # Point the legacy fallback somewhere empty too, otherwise this picks up
        # the checkout's own .env and the assertion means nothing.
        monkeypatch.setattr(paths, "APP_ROOT", tmp_path / "no-app-here")
        assert config_loader.load_configuration(tmp_path / "nothing-here") == []

    def test_does_not_depend_on_the_working_directory(self, tmp_path, monkeypatch):
        """A launch agent's working directory is arbitrary."""
        _write(tmp_path / "config.env", OE_TEST_VALUE="found-anyway")
        elsewhere = tmp_path / "unrelated"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        config_loader.load_configuration(tmp_path)

        assert os.environ["OE_TEST_VALUE"] == "found-anyway"


class TestPrecedence:
    def test_the_real_environment_wins(self, tmp_path, monkeypatch):
        """Docker -e and systemd Environment= must keep overriding the file."""
        monkeypatch.setenv("OE_TEST_VALUE", "from-environment")
        _write(tmp_path / "config.env", OE_TEST_VALUE="from-file")

        config_loader.load_configuration(tmp_path)

        assert os.environ["OE_TEST_VALUE"] == "from-environment"

    def test_data_root_config_beats_the_legacy_env(self, tmp_path, monkeypatch):
        from backend.core import paths

        legacy_root = tmp_path / "app"
        _write(legacy_root / ".env", OE_TEST_VALUE="legacy", OE_TEST_OTHER="only-legacy")
        _write(tmp_path / "data" / "config.env", OE_TEST_VALUE="current")
        monkeypatch.setattr(paths, "APP_ROOT", legacy_root)

        config_loader.load_configuration(tmp_path / "data")

        assert os.environ["OE_TEST_VALUE"] == "current"
        # The legacy file is still read, so an unmigrated install keeps working.
        assert os.environ["OE_TEST_OTHER"] == "only-legacy"

    def test_legacy_env_alone_still_works(self, tmp_path, monkeypatch):
        """An install that has not been migrated must not break."""
        from backend.core import paths

        legacy_root = tmp_path / "app"
        _write(legacy_root / ".env", OE_TEST_VALUE="legacy-only")
        monkeypatch.setattr(paths, "APP_ROOT", legacy_root)

        loaded = config_loader.load_configuration(tmp_path / "empty")

        assert os.environ["OE_TEST_VALUE"] == "legacy-only"
        assert loaded == [legacy_root / ".env"]


class TestSecrets:
    def test_secret_names_are_declared(self):
        """These are the values that must survive a migration."""
        assert set(config_loader.SECRET_KEYS) == {
            "SECRET_KEY", "JWT_SECRET_KEY", "ECOSYSTEM_HMAC_SECRET",
        }

    def test_secrets_load_from_the_config_file(self, tmp_path):
        _write(tmp_path / "config.env",
               SECRET_KEY="s", JWT_SECRET_KEY="j", ECOSYSTEM_HMAC_SECRET="h")

        config_loader.load_configuration(tmp_path)

        assert os.environ["SECRET_KEY"] == "s"
        assert os.environ["JWT_SECRET_KEY"] == "j"
        assert os.environ["ECOSYSTEM_HMAC_SECRET"] == "h"

    def test_permission_check_flags_a_readable_secrets_file(self, tmp_path):
        path = _write(tmp_path / "config.env", SECRET_KEY="s")
        os.chmod(path, 0o644)
        assert config_loader.check_permissions(path) is False

    def test_permission_check_accepts_owner_only(self, tmp_path):
        path = _write(tmp_path / "config.env", SECRET_KEY="s")
        os.chmod(path, 0o600)
        assert config_loader.check_permissions(path) is True

    def test_a_loose_secrets_file_still_loads_but_warns(self, tmp_path, caplog):
        """Refusing to start would be worse than loading and complaining."""
        path = _write(tmp_path / "config.env", SECRET_KEY="s")
        os.chmod(path, 0o644)

        with caplog.at_level("WARNING"):
            config_loader.load_configuration(tmp_path)

        assert os.environ["SECRET_KEY"] == "s"
        assert any("readable by other users" in r.message for r in caplog.records)

    def test_no_warning_when_the_file_holds_no_secrets(self, tmp_path, caplog):
        path = _write(tmp_path / "config.env", OE_TEST_VALUE="harmless")
        os.chmod(path, 0o644)

        with caplog.at_level("WARNING"):
            config_loader.load_configuration(tmp_path)

        assert not any("readable by other users" in r.message for r in caplog.records)

    def test_secure_permissions_restricts_the_file(self, tmp_path):
        path = _write(tmp_path / "config.env", SECRET_KEY="s")
        os.chmod(path, 0o644)

        config_loader.secure_permissions(path)

        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == 0o600
