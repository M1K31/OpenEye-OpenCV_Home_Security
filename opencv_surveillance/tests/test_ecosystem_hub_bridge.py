"""Unit tests for OpenEye Phase 2 HubRuntime, capabilities, and federated push sink."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.core.ecosystem_hub_bridge import (
    _ensure_ecosystem_paths,
    build_openeye_capabilities,
    deliver_federated_push,
    start_openeye_hub,
    stop_openeye_hub,
)


def test_openeye_capabilities_validate_against_schema():
    _ensure_ecosystem_paths()
    from ecosystem_client.contracts import assert_valid_schema

    caps = build_openeye_capabilities()
    names = {c["capability"] for c in caps}
    assert {
        "camera.snapshot",
        "camera.record_clip",
        "automation.trigger_rule",
        "notify.deliver.openeye_push",
        "ecosystem.freeze",
    } <= names
    for partial in caps:
        full = dict(partial)
        full.setdefault("schema_version", 1)
        full.setdefault("provider", {"app": "openeye", "device_id": "test-openeye-01"})
        assert_valid_schema(full, "capability-manifest.v1")


def test_openeye_hub_off_mode_and_federated_push(monkeypatch):
    monkeypatch.setenv("ECOSYSTEM_HUB_ROLE", "off")
    _ensure_ecosystem_paths()
    from ecosystem_client.contracts import build_notification_envelope

    broadcasted: list[dict] = []

    async def _fake_broadcast(evt: dict):
        broadcasted.append(evt)

    dispatched: list[dict] = []

    async def _fake_dispatch(db, **kwargs):
        dispatched.append(kwargs)
        return {"delivered_via": ["telegram"], "suppressed": False, "suppressed_count": 0}

    app = SimpleNamespace(state=SimpleNamespace())

    async def _run():
        eco = await start_openeye_hub(app, service_port=8200)
        assert eco is not None
        assert app.state.ecosystem_hub.effective_mode == "standalone"
        app.state.ecosystem = eco

        env = build_notification_envelope(
            "notify.security",
            "aegissiem",
            "high",
            "Perimeter Intrusion Alert",
            "Correlated motion + SSH brute force",
            dedupe_key="corr:test:01",
            privacy="redacted",
        )
        res = await deliver_federated_push(
            env,
            db=object(),
            broadcast_fn=_fake_broadcast,
            dispatch_fn=_fake_dispatch,
        )
        assert res["status"] == "delivered"
        assert "ecosystem_ws" in res["delivered_via"]
        assert "telegram" in res["delivered_via"]
        assert len(broadcasted) == 1
        assert len(dispatched) == 1

        # Privacy guard: local_only envelopes must NOT dispatch to external providers.
        local_env = build_notification_envelope(
            "notify.system",
            "openeye",
            "medium",
            "Local Maintenance",
            "Local camera calibration",
            dedupe_key="local:test:01",
            privacy="local_only",
        )
        res_local = await deliver_federated_push(
            local_env,
            db=object(),
            broadcast_fn=_fake_broadcast,
            dispatch_fn=_fake_dispatch,
        )
        assert res_local["delivered_via"] == ["ecosystem_ws"]
        assert len(dispatched) == 1

        await stop_openeye_hub(app)
        assert app.state.ecosystem_hub is None

    asyncio.run(_run())
