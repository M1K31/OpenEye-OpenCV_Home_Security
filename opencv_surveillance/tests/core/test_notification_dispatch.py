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
