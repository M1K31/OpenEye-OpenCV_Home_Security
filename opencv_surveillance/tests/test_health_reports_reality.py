# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The health endpoint must be able to fail.

It previously answered with string literals:

    "face_recognition": "available",
    "database": "connected",

checking neither. The Dockerfile's HEALTHCHECK curls this endpoint, so a
container whose database had gone reported itself healthy indefinitely and
nothing restarted it. A health check that cannot fail is not a health check —
it is a constant that looks like one.

Two states are distinguished deliberately, and the difference matters for
orchestration:

  unhealthy  the database is unreachable -> 503, so `curl -f` fails and the
             container is restarted
  degraded   an optional feature is absent -> still 200, because that is a
             supported configuration and restarting would not fix it

Getting that backwards in either direction is a real fault: a 503 for missing
face recognition would restart-loop every install that chose not to have it,
and a 200 for a dead database is the bug being fixed.
"""

from unittest.mock import patch

import pytest


def test_a_working_system_reports_healthy(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("healthy", "degraded")
    assert body["database"] == "connected"


def test_the_database_is_actually_checked(client):
    """
    The finding itself: the answer must depend on the database.

    If this passes with the probe removed, the endpoint is reporting a
    constant again.
    """
    with patch("backend.main.get_db_context", side_effect=RuntimeError("no database")):
        response = client.get("/api/health")

    assert response.status_code == 503, (
        "a dead database still reported success; the Dockerfile HEALTHCHECK "
        "would never restart the container"
    )
    body = response.json()
    assert body["status"] == "unhealthy"
    assert body["database"] == "unreachable"


def test_a_dead_database_does_not_leak_detail(client):
    """
    This endpoint is unauthenticated (it is in PUBLIC_ROUTES).

    It should say the database is unreachable, not why — exception text carries
    file paths and connection strings.
    """
    secret = "postgresql://admin:hunter2@10.0.0.5:5432/openeye"
    with patch("backend.main.get_db_context", side_effect=RuntimeError(secret)):
        response = client.get("/api/health")

    assert secret not in response.text
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_missing_face_recognition_is_degraded_not_unhealthy(client):
    """
    An optional feature being absent is a supported configuration.

    Answering 503 here would restart-loop every deployment that deliberately
    installs without dlib — which, since b56d4f1, is the default for a
    developer `pip install`.
    """
    with patch("backend.core.face_recognition.FACE_RECOGNITION_AVAILABLE", False):
        response = client.get("/api/health")

    assert response.status_code == 200, (
        "a missing optional feature must not fail the health check"
    )
    body = response.json()
    assert body["status"] == "degraded"
    assert body["face_recognition"] == "not_installed"
    assert body["database"] == "connected"


def test_the_database_outranks_the_optional_feature(client):
    """Both wrong is still unhealthy, not degraded."""
    with patch("backend.main.get_db_context", side_effect=RuntimeError("gone")), \
         patch("backend.core.face_recognition.FACE_RECOGNITION_AVAILABLE", False):
        response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"


def test_it_stays_cheap(client):
    """
    One database round-trip per call, no more.

    scripts/health-watch.sh exists because this endpoint was once seen taking
    24-40 seconds, and a health check that hangs cannot be told apart from the
    outage it is meant to detect.

    Asserted by COUNTING the database accesses rather than timing the call. The
    first version of this test measured wall-clock and passed alone while
    failing inside the full suite on a loaded machine — measuring the machine,
    not the endpoint. Direct measurement puts the call at a median of 29 ms; the
    property worth defending is that it makes one cheap query, and that does not
    flake.
    """
    import backend.main as main

    real = main.get_db_context
    calls = []

    def counting_context(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    with patch.object(main, "get_db_context", counting_context):
        response = client.get("/api/health")

    assert response.status_code == 200
    assert len(calls) == 1, (
        f"the health check opened {len(calls)} database contexts; it should "
        "make exactly one cheap probe"
    )


def test_it_needs_no_authentication(client):
    """Orchestration cannot log in; this must stay reachable without a token."""
    assert client.get("/api/health").status_code in (200, 503)
