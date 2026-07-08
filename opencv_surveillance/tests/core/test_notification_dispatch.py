"""Unit tests for backend.core.notification_dispatch."""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from cryptography.fernet import Fernet

# Stable encryption key BEFORE importing alert_models-dependent code
os.environ.setdefault("NOTIFICATION_ENCRYPTION_KEY", Fernet.generate_key().decode())

from backend.database.alert_models import NotificationProvider
from backend.core import notification_dispatch as nd


@pytest.fixture(autouse=True)
def _reset_cooldown_state():
    nd._last_sent.clear()
    nd._suppressed.clear()
    yield
    nd._last_sent.clear()
    nd._suppressed.clear()


@pytest.fixture
def providers_db(db_session):
    """Two enabled + one disabled provider in the test DB."""
    rows = []
    for ptype, name, cfg, enabled in [
        ("discord", "Family Discord", {"webhook_url": "https://discord.com/api/webhooks/1/x"}, True),
        ("telegram", "My Bot", {"bot_token": "123:abc", "chat_id": "42"}, True),
        ("webhook", "Disabled Hook", {"url": "https://example.com/hook"}, False),
    ]:
        p = NotificationProvider(user_id=1, provider_type=ptype, provider_name=name, enabled=enabled)
        p.encrypted_config = p.encrypt_config(cfg)
        db_session.add(p)
        rows.append(p)
    db_session.commit()
    return db_session


@pytest.fixture
def mock_service(monkeypatch):
    svc = MagicMock()
    svc.send_webhook = AsyncMock(return_value=(True, None))
    svc.send_email = AsyncMock(return_value=(True, None))
    monkeypatch.setattr(nd, "get_notification_service", lambda: svc)
    return svc


@pytest.mark.asyncio
async def test_fan_out_to_all_enabled(providers_db, mock_service):
    result = await nd.dispatch_notification(providers_db, message="hi")
    assert sorted(result["delivered_via"]) == ["discord:Family Discord", "telegram:My Bot"]
    assert result["suppressed"] is False
    assert mock_service.send_webhook.await_count == 2  # discord + telegram


@pytest.mark.asyncio
async def test_targeting_intersects_enabled(providers_db, mock_service):
    result = await nd.dispatch_notification(
        providers_db, message="hi", target_providers=["discord", "Disabled Hook"]
    )
    # Disabled Hook is enabled=False -> excluded even though targeted
    assert result["delivered_via"] == ["discord:Family Discord"]


@pytest.mark.asyncio
async def test_provider_failure_isolated(providers_db, mock_service):
    async def fail_first(url, payload):
        if "discord.com" in url:
            raise RuntimeError("boom")
        return (True, None)
    mock_service.send_webhook = AsyncMock(side_effect=fail_first)
    result = await nd.dispatch_notification(providers_db, message="hi")
    assert result["delivered_via"] == ["telegram:My Bot"]  # discord failed, telegram still sent


@pytest.mark.asyncio
async def test_telegram_without_chat_id_skipped(db_session, mock_service):
    p = NotificationProvider(user_id=1, provider_type="telegram", provider_name="NoChat", enabled=True)
    p.encrypted_config = p.encrypt_config({"bot_token": "123:abc"})
    db_session.add(p); db_session.commit()
    result = await nd.dispatch_notification(db_session, message="hi")
    assert result["delivered_via"] == []


def test_redact_url_hides_path_secrets():
    from backend.services.notification_service import _redact_url
    assert _redact_url("https://api.telegram.org/bot123:SECRET/sendMessage") == "https://api.telegram.org/..."
    assert "SECRET" not in _redact_url("https://discord.com/api/webhooks/1/SECRET")
    # Invalid URL should not raise exception
    result = _redact_url("not a url")
    assert isinstance(result, str) and len(result) > 0


@pytest.mark.asyncio
async def test_cooldown_suppresses_then_annotates(providers_db, mock_service, monkeypatch):
    t = {"now": 1000.0}
    monkeypatch.setattr(nd.time, "monotonic", lambda: t["now"])
    key = ("rule", 1, "cam1", "John")

    r1 = await nd.dispatch_notification(providers_db, message="seen",
                                        cooldown_key=key, cooldown_seconds=60)
    assert r1["suppressed"] is False and len(r1["delivered_via"]) == 2

    r2 = await nd.dispatch_notification(providers_db, message="seen",
                                        cooldown_key=key, cooldown_seconds=60)
    assert r2 == {"delivered_via": [], "suppressed": True, "suppressed_count": 0}

    t["now"] += 61  # window expires
    r3 = await nd.dispatch_notification(providers_db, message="seen",
                                        cooldown_key=key, cooldown_seconds=60)
    assert r3["suppressed"] is False and r3["suppressed_count"] == 1
    # the delivered message carries the suppressed annotation
    sent_texts = [c.args[1] for c in mock_service.send_webhook.await_args_list]
    assert any("(+1 earlier events suppressed)" in str(p) for p in sent_texts)


@pytest.mark.asyncio
async def test_cooldown_zero_never_suppresses(providers_db, mock_service):
    key = ("rule", 2, "cam1", "John")
    for _ in range(3):
        r = await nd.dispatch_notification(providers_db, message="x",
                                           cooldown_key=key, cooldown_seconds=0)
        assert r["suppressed"] is False


@pytest.mark.asyncio
async def test_cooldown_not_stamped_when_all_providers_fail(providers_db, mock_service, monkeypatch):
    """If every provider fails, the cooldown window must never open — a
    subsequent event with the same key must not be suppressed, since nothing
    was ever actually delivered."""
    t = {"now": 2000.0}
    monkeypatch.setattr(nd.time, "monotonic", lambda: t["now"])
    key = ("rule", 3, "cam1", "Jane")

    mock_service.send_webhook = AsyncMock(return_value=(False, "err"))

    r1 = await nd.dispatch_notification(providers_db, message="fail",
                                        cooldown_key=key, cooldown_seconds=60)
    assert r1["delivered_via"] == []
    assert r1["suppressed"] is False

    # Cooldown window was never opened (mark_sent not called) -> immediately
    # following dispatch with the same key is NOT suppressed.
    t["now"] += 1  # well within the 60s window if it had been (wrongly) opened
    r2 = await nd.dispatch_notification(providers_db, message="fail again",
                                        cooldown_key=key, cooldown_seconds=60)
    assert r2["suppressed"] is False
    assert r2["delivered_via"] == []


def test_dispatch_from_thread_schedules_on_loop(monkeypatch):
    """dispatch_from_thread returns True when a running loop is registered,
    False (never raises) when no loop is available."""
    import asyncio, threading

    calls = []
    async def fake_dispatch(**kwargs):
        calls.append(kwargs)
    monkeypatch.setattr(nd, "_dispatch_with_own_session", fake_dispatch)

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        nd.set_app_loop(loop)
        assert nd.dispatch_from_thread(message="hi") is True
        import time as _t
        for _ in range(50):
            if calls:
                break
            _t.sleep(0.05)
        assert calls and calls[0]["message"] == "hi"

        nd.set_app_loop(None)
        assert nd.dispatch_from_thread(message="hi") is False
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()
