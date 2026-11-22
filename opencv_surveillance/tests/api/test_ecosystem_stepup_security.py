"""Step-up and peer identity for the ecosystem policy routes (security review of PR #8).

- A stored bearer ecosystem token identifies a connected app, not a human admin
  and not a verified peer: it must not get admin or the step-up exemption.
- A step-up factor must be the authenticated caller's own; a client cannot pick
  the operator_id, and there is no shared "admin" fallback.
"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api.routes import ecosystem as eco
from backend.database import models


def _request(headers=None):
    scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]}
    from starlette.requests import Request
    return Request(scope)


def _caller_for_token(db_session, token):
    return asyncio.get_event_loop().run_until_complete(
        eco._get_caller_identity(_request({"Authorization": f"Bearer {token}"}), db_session)
    )


def test_bearer_ecosystem_token_is_not_admin_and_not_peer(db_session):
    db_session.add(models.EcosystemConnection(
        app_name="aegissiem", host="http://127.0.0.1:8089", local_token="eco-tok-1", is_active=True,
    ))
    db_session.commit()

    caller = _caller_for_token(db_session, "eco-tok-1")
    assert caller["auth_method"] == "ecosystem_token"
    assert caller["principal"] == "aegissiem"
    assert caller["is_admin"] is False
    assert caller["is_peer"] is False


def test_bearer_ecosystem_token_cannot_pass_step_up(db_session):
    db_session.add(models.EcosystemConnection(
        app_name="aegissiem", host="http://127.0.0.1:8089", local_token="eco-tok-2", is_active=True,
    ))
    db_session.commit()
    caller = _caller_for_token(db_session, "eco-tok-2")
    # A connected app is not admin, so a privileged policy action is refused;
    # it never reaches the peer exemption.
    with pytest.raises(HTTPException) as exc:
        eco._verify_step_up(caller, {}, _request())
    assert exc.value.status_code == 403


def test_step_up_is_bound_to_the_caller(monkeypatch):
    issued = []

    class FakeStepUp:
        def verify_step_up_token(self, token, required_scope=None):
            # A token for someone else must not be accepted for this caller.
            return {"sub": "someone_else", "amr": "totp"} if token == "other-token" else None

        def verify_totp_and_issue_token(self, operator_id, code, scope=None):
            issued.append(operator_id)
            return {"step_up_token": "fresh"} if operator_id == "mikel" and code == "123456" else None

    monkeypatch.setattr(eco, "get_step_up_auth", lambda: FakeStepUp())
    caller = {"principal": "mikel", "is_admin": True, "is_peer": False}

    # Another operator's token is refused.
    with pytest.raises(HTTPException):
        eco._verify_step_up(caller, {"step_up_token": "other-token"}, _request())

    # A client-chosen operator_id does not redirect the TOTP check.
    operator, method, _ = eco._verify_step_up(
        caller, {"totp_code": "123456", "operator_id": "someone_else"}, _request()
    )
    assert operator == "mikel" and method == "totp"
    assert issued == ["mikel"]       # only the caller's own identity was checked


def test_hmac_verification_failure_is_not_swallowed(monkeypatch, db_session):
    # A signature header that does not verify must 401, not fall through to the
    # bearer path. (Here authenticate_request raises, as it does on a bad sig.)
    import ecosystem_auth.middleware as mw
    import ecosystem_auth.tokens as tok

    async def boom(request, creds):
        raise HTTPException(status_code=401, detail="bad signature")

    monkeypatch.setattr(mw, "authenticate_request", boom)
    headers = {tok.SIGNATURE_HEADER: "deadbeef", "Authorization": "Bearer eco-tok-x"}
    with pytest.raises(HTTPException) as exc:
        asyncio.get_event_loop().run_until_complete(
            eco._get_caller_identity(_request(headers), db_session)
        )
    assert exc.value.status_code == 401
