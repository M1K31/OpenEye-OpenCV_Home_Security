"""Tests for OpenEye's optional ecosystem AI bridge."""

import asyncio

import pytest

# ecosystem_ai ships with the sibling appEcosystem project and is deliberately
# optional: backend/core/ecosystem_ai_bridge.py guards every import of it and
# returns None when it is missing, so OpenEye runs unchanged without it. It is
# therefore absent from requirements, and a bare module-level `import
# ecosystem_ai` here failed collection of this file on any machine that had not
# installed the sibling project — including CI, where it errored the whole run.
# Skip instead, so the suite reflects the module's own optional contract.
ecosystem_ai = pytest.importorskip("ecosystem_ai")

import backend.core.ecosystem_ai_bridge as bridge  # noqa: E402


class _FakeProfile:
    selected_model = "llama3.1:8b"


class _FakeClient:
    def __init__(self, profile=None):
        self._profile = profile or _FakeProfile()
        self.closed = False

    async def fetch(self):
        return self._profile

    async def aclose(self):
        self.closed = True


def test_shared_selected_model(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(bridge, "_make_profile_client", lambda: fake)
    assert asyncio.run(bridge.shared_selected_model()) == "llama3.1:8b"
    assert fake.closed is True


def test_shared_selected_model_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(bridge, "_make_profile_client", lambda: None)
    assert asyncio.run(bridge.shared_selected_model()) is None


def test_summarize_event_uses_router(monkeypatch):
    # No registry client -> falls back to default profile.
    monkeypatch.setattr(bridge, "_make_profile_client", lambda: None)

    class _Result:
        text = "Person at front door at 02:14."

    class _Router:
        async def chat(self, messages, **kw):
            return _Result()

    monkeypatch.setattr(ecosystem_ai, "build_router", lambda profile, tier=None: _Router())
    out = asyncio.run(bridge.summarize_event("Person detected, front door, 02:14"))
    assert out == "Person at front door at 02:14."


def test_summarize_event_none_on_failure(monkeypatch):
    monkeypatch.setattr(bridge, "_make_profile_client", lambda: None)

    def _boom(profile, tier=None):
        raise RuntimeError("no provider")

    monkeypatch.setattr(ecosystem_ai, "build_router", _boom)
    assert asyncio.run(bridge.summarize_event("x")) is None
