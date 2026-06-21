"""Port resolution: bind == register, ECOSYSTEM_SERVICE_PORT wins."""

import importlib
import os

import pytest


def _resolver():
    # Imported lazily so monkeypatched env is read at call time.
    from backend.core import config
    importlib.reload(config)
    return config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in ("ECOSYSTEM_SERVICE_PORT", "OPENEYE_PORT", "PORT"):
        monkeypatch.delenv(var, raising=False)
    yield


def test_default_is_8200():
    assert _resolver().resolve_service_port() == 8200


def test_ecosystem_service_port_wins(monkeypatch):
    monkeypatch.setenv("ECOSYSTEM_SERVICE_PORT", "9100")
    monkeypatch.setenv("OPENEYE_PORT", "8000")
    monkeypatch.setenv("PORT", "8200")
    assert _resolver().resolve_service_port() == 9100


def test_openeye_port_fallback(monkeypatch):
    monkeypatch.setenv("OPENEYE_PORT", "8050")
    assert _resolver().resolve_service_port() == 8050


def test_invalid_value_skipped(monkeypatch):
    monkeypatch.setenv("ECOSYSTEM_SERVICE_PORT", "notaport")
    monkeypatch.setenv("OPENEYE_PORT", "8201")
    assert _resolver().resolve_service_port() == 8201
