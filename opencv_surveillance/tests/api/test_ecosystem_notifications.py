"""Ecosystem notification route tests."""
import os
from typing import Optional
from unittest.mock import AsyncMock, patch

from cryptography.fernet import Fernet

os.environ.setdefault("NOTIFICATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ECOSYSTEM_HMAC_SECRET", "test-ecosystem-hmac-secret")


def _auth_headers(method: str, url: str, body: Optional[dict] = None) -> dict:
    """Build valid X-Ecosystem-* HMAC headers the same way real ecosystem
    clients (ecosystem_client.Peer) authenticate against require_ecosystem_auth."""
    from ecosystem_auth.tokens import sign_request, get_ecosystem_secret

    secret = get_ecosystem_secret()
    return sign_request(method, url, secret, body=body)


def _mk_provider(db_session):
    from backend.database.alert_models import NotificationProvider
    p = NotificationProvider(user_id=1, provider_type="discord",
                             provider_name="Ops", enabled=True)
    p.encrypted_config = p.encrypt_config(
        {"webhook_url": "https://discord.com/api/webhooks/1/x"})
    db_session.add(p); db_session.commit()


def test_send_delivers_via_enabled_providers(client, db_session):
    _mk_provider(db_session)
    body = {"type": "security", "title": "Alert", "message": "Threat blocked",
            "source": "aegissiem"}
    headers = _auth_headers("POST", "/api/notifications/", body)
    with patch("backend.core.notification_dispatch.get_notification_service") as gns:
        gns.return_value.send_webhook = AsyncMock(return_value=(True, None))
        resp = client.post("/api/notifications/", json=body, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["delivered_via"] == ["discord:Ops"]


def test_send_unauthenticated_rejected(client, db_session):
    """POST /api/notifications/ without ecosystem auth must be rejected."""
    resp = client.post("/api/notifications/", json={
        "type": "security", "title": "Alert", "message": "Threat blocked",
        "source": "aegissiem"})
    assert resp.status_code == 401


def test_settings_persist_roundtrip(client, db_session):
    r1 = client.get("/api/notifications/settings")
    assert r1.status_code == 200               # defaults on first read

    payload = r1.json()
    payload["quiet_hours"]["enabled"] = True
    headers = _auth_headers("PUT", "/api/notifications/settings", payload)
    r2 = client.put("/api/notifications/settings", json=payload, headers=headers)
    assert r2.status_code == 200

    r3 = client.get("/api/notifications/settings")
    assert r3.json()["quiet_hours"]["enabled"] is True
