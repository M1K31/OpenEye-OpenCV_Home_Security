"""Ecosystem notification route tests."""
import os
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet

os.environ.setdefault("NOTIFICATION_ENCRYPTION_KEY", Fernet.generate_key().decode())


def _mk_provider(db_session):
    from backend.database.alert_models import NotificationProvider
    p = NotificationProvider(user_id=1, provider_type="discord",
                             provider_name="Ops", enabled=True)
    p.encrypted_config = p.encrypt_config(
        {"webhook_url": "https://discord.com/api/webhooks/1/x"})
    db_session.add(p); db_session.commit()


def test_send_delivers_via_enabled_providers(client, db_session):
    _mk_provider(db_session)
    with patch("backend.core.notification_dispatch.get_notification_service") as gns:
        gns.return_value.send_webhook = AsyncMock(return_value=(True, None))
        resp = client.post("/api/notifications/", json={
            "type": "security", "title": "Alert", "message": "Threat blocked",
            "source": "aegissiem"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["delivered_via"] == ["discord:Ops"]


def test_settings_persist_roundtrip(client, db_session):
    r1 = client.get("/api/notifications/settings")
    assert r1.status_code == 200               # defaults on first read

    payload = r1.json()
    payload["quiet_hours"]["enabled"] = True
    r2 = client.put("/api/notifications/settings", json=payload)
    assert r2.status_code == 200

    r3 = client.get("/api/notifications/settings")
    assert r3.json()["quiet_hours"]["enabled"] is True
