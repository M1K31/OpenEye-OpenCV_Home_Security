"""Ecosystem notification route tests."""
import os
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.fernet import Fernet

# Same optional-sibling contract as backend/api/routes/ecosystem.py: ecosystem_auth
# ships with appEcosystem and OpenEye runs without it. Every test in this file
# signs its requests through _auth_headers below, so without the package they all
# fail at call time rather than being skipped. Skip the module instead, matching
# how the routes themselves treat the dependency as optional.
pytest.importorskip("ecosystem_auth")

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
    """
    Both reads are signed, not just the write.

    GET /api/notifications/settings carries require_ecosystem_auth exactly as
    the PUT does, so an unsigned read is refused with
    `{"detail": "Missing ecosystem authentication"}`. The unsigned GETs here
    asserted 200 and never failed only because this whole module is skipped
    wherever ecosystem_auth is absent — which includes the development machine.
    The test therefore ran for the first time in a container that has the
    package, and failed immediately.
    """
    url = "/api/notifications/settings"

    r1 = client.get(url, headers=_auth_headers("GET", url))
    assert r1.status_code == 200               # defaults on first read

    payload = r1.json()
    payload["quiet_hours"]["enabled"] = True
    r2 = client.put(url, json=payload, headers=_auth_headers("PUT", url, payload))
    assert r2.status_code == 200

    r3 = client.get(url, headers=_auth_headers("GET", url))
    assert r3.json()["quiet_hours"]["enabled"] is True
