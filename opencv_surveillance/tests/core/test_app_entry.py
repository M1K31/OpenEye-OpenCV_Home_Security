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


class TestRuntimeState:
    """
    Where the application ended up has to be discoverable.

    The port moves when something already holds the preferred one — correct for
    a desktop app, but it left a user staring at a bookmark that pointed at a
    different, older instance while the real one ran elsewhere. That actually
    happened: two instances, the browser on the wrong one, and the camera
    apparently broken when it was working perfectly.
    """

    def test_it_records_the_url_and_port(self, tmp_path):
        path = app_entry.write_runtime_state(tmp_path, 8207)

        import json
        state = json.loads(path.read_text())
        assert state["port"] == 8207
        assert state["url"] == "http://localhost:8207"
        assert state["pid"] == os.getpid()

    def test_it_lands_in_the_data_root(self, tmp_path):
        assert app_entry.write_runtime_state(tmp_path, 8200) == tmp_path / "runtime.json"

    def test_an_unwritable_data_root_does_not_stop_startup(self, tmp_path):
        """Recording where we are is useful; failing to is not worth refusing to run."""
        unwritable = tmp_path / "missing" / "deeper"
        app_entry.write_runtime_state(unwritable, 8200)  # must not raise


class TestOpeningTheInterface:
    def test_the_browser_opens_only_for_an_application_launch(self, monkeypatch):
        """
        From a terminal or a service manager a browser appearing unbidden is an
        intrusion, so the flag the bundle sets is what gates it.
        """
        opened = []
        monkeypatch.setattr(app_entry, "_wait_until_serving", lambda port, timeout=60.0: True)

        import webbrowser
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))

        app_entry.open_ui_when_ready(8207)
        for _ in range(50):
            if opened:
                break
            import time as _t
            _t.sleep(0.02)

        assert opened == ["http://localhost:8207"]

    def test_it_does_not_open_a_browser_at_a_server_that_never_came_up(self, monkeypatch):
        """A connection error teaches the user the app is broken."""
        opened = []
        monkeypatch.setattr(app_entry, "_wait_until_serving", lambda port, timeout=60.0: False)

        import webbrowser
        monkeypatch.setattr(webbrowser, "open", lambda url: opened.append(url))

        app_entry.open_ui_when_ready(8207)
        import time as _t
        _t.sleep(0.2)

        assert opened == []
