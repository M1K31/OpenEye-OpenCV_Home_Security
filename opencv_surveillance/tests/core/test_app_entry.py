# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the packaged application's entry point.

A bundle launched from Finder or at login has no terminal, so a failure here is
invisible: the user double-clicks and nothing happens. These cover the parts
that would fail that way — port selection, log placement, and making the
advertised port match the listening one.
"""

import os
import socket

import pytest

from backend import app_entry


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("ECOSYSTEM_SERVICE_PORT", "OPENEYE_PORT", "PORT"):
        monkeypatch.delenv(name, raising=False)


class TestPortSelection:
    def test_it_takes_the_preferred_port_when_free(self):
        assert app_entry.choose_port(app_entry.DEFAULT_PORT) in range(
            app_entry.DEFAULT_PORT, app_entry.DEFAULT_PORT + 20
        )

    def test_it_steps_past_a_port_already_in_use(self):
        """
        A desktop app cannot refuse to start because something holds its port —
        there is no terminal in which to read the complaint.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
            taken.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            taken.bind(("0.0.0.0", 0))
            busy = taken.getsockname()[1]
            taken.listen(1)

            chosen = app_entry.choose_port(busy)

            assert chosen != busy
            assert chosen > busy

    def test_it_gives_up_gracefully_rather_than_looping(self):
        assert app_entry.choose_port(app_entry.DEFAULT_PORT, attempts=0) == app_entry.DEFAULT_PORT


class TestAdvertisedPort:
    def test_the_chosen_port_is_what_the_ecosystem_advertises(self):
        """
        ECOSYSTEM_SERVICE_PORT overrides everything when the client registers,
        and the registry never checks it — so a wrong value is published as fact
        and peers fail to reach a service that is running perfectly well.
        """
        app_entry.publish_port(8207)

        assert os.environ["ECOSYSTEM_SERVICE_PORT"] == "8207"
        assert os.environ["OPENEYE_PORT"] == "8207"

    def test_an_explicit_setting_is_left_alone(self, monkeypatch):
        """Someone behind a reverse proxy advertises the external port on purpose."""
        monkeypatch.setenv("ECOSYSTEM_SERVICE_PORT", "443")

        app_entry.publish_port(8207)

        assert os.environ["ECOSYSTEM_SERVICE_PORT"] == "443"


class TestLogging:
    def test_the_log_goes_under_the_data_root(self, tmp_path):
        log_path = app_entry.configure_logging(tmp_path)

        assert log_path == tmp_path / "logs" / "openeye-app.log"
        assert log_path.parent.is_dir()

    def test_an_oversized_log_is_rotated_rather_than_grown(self, tmp_path):
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_path = log_dir / "openeye-app.log"
        log_path.write_bytes(b"x" * (app_entry.LOG_MAX_BYTES + 1))

        app_entry.configure_logging(tmp_path)

        assert (log_dir / "openeye-app.log.1").exists()
