# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Every API route must require credentials unless it is on PUBLIC_ROUTES.

Why this test exists
--------------------
Authorization used to be opt-in: each route author had to remember a
``Depends(get_current_active_user)`` parameter. A 2026-08-20 audit measured the
result across 283 routes — 208 protected, 20 guarded inside the handler, and 50
reachable with no credentials at all, including anonymous admin-account creation
and a face-detection history search that returns who was seen and when.

Fixing those 50 is worth little on its own, because nothing stops the 51st from
shipping the same way. This test is the part that lasts: a new route is
authenticated, or this test fails and someone has to justify the exception by
adding it to PUBLIC_ROUTES below.
"""

import pytest
from fastapi.routing import APIRoute, APIWebSocketRoute

from backend.main import app


# Routes that are public BY DESIGN. Each entry needs a reason, and adding one is
# a decision a reviewer should see in the diff.
PUBLIC_ROUTES = {
    # --- Authentication: you cannot present a token to obtain a token --------
    ("POST", "/api/token"),                    # username/password -> access token
    ("POST", "/api/token/refresh"),            # rotates a refresh token
    ("POST", "/api/auth/login-2fa"),           # second factor of an in-progress login
    ("POST", "/api/auth/check-2fa-status"),    # tells the client which form to show
    ("POST", "/api/auth/reset-password"),      # guarded by a TOTP code; 2FA accounts only

    # --- First-run setup: runs before any user exists -----------------------
    # Verified: /initialize refuses once an admin account is present, so this
    # cannot be used to seize an installed system.
    ("GET", "/api/setup/status"),
    ("POST", "/api/setup/initialize"),

    # --- Liveness: probed by the Docker HEALTHCHECK and the installer --------
    ("GET", "/api/health"),

    # --- SPA shell -----------------------------------------------------------
    # The login page itself is served from here; requiring auth would make it
    # impossible to reach a login form.
    ("GET", "/"),
    ("GET", "/api/"),
    ("GET", "/{full_path:path}"),

    # --- Ecosystem: authenticated INSIDE the handler -------------------------
    # These do not carry a FastAPI dependency, so the sweep below cannot see
    # their enforcement. Each was read and confirmed on 2026-08-20:
    #   /ecosystem/connect  bootstrap — establishes the shared secret, and must
    #                       be reachable before one exists.
    #   the other three     look up the supplied token against
    #                       EcosystemConnection.local_token and raise 401 when it
    #                       does not match.
    # Tracked separately: those tokens travel in the query string, which leaks
    # into proxy logs and browser history. See the audit's M-2.
    ("POST", "/api/ecosystem/connect"),
    ("GET", "/api/ecosystem/cameras"),
    ("GET", "/api/ecosystem/stream/{camera_id}"),
    ("GET", "/api/ecosystem/snapshot/{camera_id}"),

    # --- WebSockets: authenticated before accept() ---------------------------
    # A WebSocket route cannot express auth as a dependency the way an HTTP
    # route can. All three call an authenticate-then-accept helper and close the
    # socket with a policy-violation code when the token is missing or invalid.
    ("WEBSOCKET", "/api/audio/ws/{camera_id}"),
    ("WEBSOCKET", "/api/ecosystem/events"),
    ("WEBSOCKET", "/api/ws/statistics"),
}

# Prefixes served to the browser rather than to API clients: the built frontend,
# static assets and the OpenAPI docs.
PUBLIC_PREFIXES = (
    "/api/docs", "/api/redoc", "/openapi.json",
    "/assets", "/static", "/favicon", "/vite.svg",
    "/apple-touch-icon",
)


def _walk_routes(routes, prefix="", inherited_dependencies=()):
    """
    Yield (route, full_path, inherited_dependencies) for every route, including
    those reached through include_router().

    Iterating app.routes directly is no longer sufficient. Up to Starlette 0.49
    include_router() copied each child route into app.routes with its full path
    already applied, so a flat loop saw everything. Starlette 1.6 — the version
    both lock files pin — instead stores an opaque `_IncludedRouter` per include
    and resolves paths at request time.

    That change silently gutted the check below. Under the shipped dependency
    set, app.routes holds 12 plain routes and 30 `_IncludedRouter` objects, and
    a flat `isinstance` loop skips all 30: the test asserting every route is
    authenticated was passing while examining a small fraction of the surface.
    It reported nothing wrong because it was looking at almost nothing.

    Router-level dependencies are carried down as well. `include_router(...,
    dependencies=[Depends(get_current_active_user)])` records them on the
    include context rather than folding them into each child route's dependant,
    so a route protected at the router level looks unprotected if only its own
    dependant is inspected.
    """
    for route in routes:
        # Matched by name: the class is private and not importable.
        if type(route).__name__ == "_IncludedRouter":
            context = getattr(route, "include_context", None)
            child_router = getattr(route, "original_router", None)
            if child_router is None:
                continue
            yield from _walk_routes(
                child_router.routes,
                prefix + (getattr(context, "prefix", "") or ""),
                tuple(inherited_dependencies)
                + tuple(getattr(context, "dependencies", ()) or ()),
            )
        elif isinstance(route, (APIRoute, APIWebSocketRoute)):
            yield route, prefix + route.path, tuple(inherited_dependencies)


def _iter_api_routes():
    """Yield (method, path) for every HTTP and WebSocket route the app serves."""
    for route, path, _ in _walk_routes(app.routes):
        if isinstance(route, APIWebSocketRoute):
            yield "WEBSOCKET", path
        else:
            for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
                yield method, path


def _is_public(method: str, path: str) -> bool:
    if (method, path) in PUBLIC_ROUTES:
        return True
    return path.startswith(PUBLIC_PREFIXES)


def _has_auth_dependency(route, inherited_dependencies=()) -> bool:
    """
    True if any dependency in the route's resolved chain enforces identity.

    Checked by name rather than by identity because the project reaches these
    through several import paths (``auth.get_current_user``,
    ``get_current_active_user`` imported directly, the ecosystem HMAC
    dependency), and all of them are equally valid enforcement points.
    """
    enforcing = {
        "get_current_user",
        "get_current_active_user",
        "get_current_user_media",
        "role_checker",             # produced by auth.require_role([...])
        "require_ecosystem_auth",   # HMAC — how appEcosystem authenticates
    }
    def _callable_of(dependency):
        """
        The function a dependency will invoke.

        Two shapes turn up and they do not share an attribute name. A resolved
        `Dependant`, which is what route.dependant.dependencies holds, exposes
        `.call`. A raw `fastapi.params.Depends`, which is what include_router()
        records on the include context, exposes `.dependency`. Reading only
        `.call` silently treats every router-level dependency as absent — which
        made routers protected by `include_router(dependencies=[...])` look
        wide open.
        """
        return getattr(dependency, "call", None) or getattr(dependency, "dependency", None)

    candidates = list(route.dependant.dependencies) + list(inherited_dependencies)

    for dependency in candidates:
        call = _callable_of(dependency)
        if call is not None and getattr(call, "__name__", "") in enforcing:
            return True
        # Nested one level: dependencies declared on a sub-dependency.
        for nested in getattr(dependency, "dependencies", []) or []:
            nested_call = _callable_of(nested)
            if nested_call is not None and getattr(nested_call, "__name__", "") in enforcing:
                return True
    return False


def test_every_route_is_authenticated_or_explicitly_public():
    """No route may be reachable anonymously without being listed above."""
    unprotected = []

    for route, path, inherited in _walk_routes(app.routes):
        methods = (
            ["WEBSOCKET"]
            if isinstance(route, APIWebSocketRoute)
            else sorted(set(route.methods) - {"HEAD", "OPTIONS"})
        )
        for method in methods:
            if _is_public(method, path):
                continue
            if _has_auth_dependency(route, inherited):
                continue
            unprotected.append(f"{method} {path}")

    assert not unprotected, (
        "These routes are reachable without credentials:\n  "
        + "\n  ".join(sorted(unprotected))
        + "\n\nAdd an auth dependency, or — if the route is public by design — "
          "add it to PUBLIC_ROUTES in this file with a reason."
    )


def test_public_routes_list_has_no_stale_entries():
    """
    A PUBLIC_ROUTES entry that no longer matches a real route is dead
    permission. Renaming a path while leaving its allowlist entry behind would
    silently re-open the new path, so fail when an entry stops matching.
    """
    live = set(_iter_api_routes())
    stale = [entry for entry in PUBLIC_ROUTES if entry not in live]

    assert not stale, (
        "PUBLIC_ROUTES contains entries that match no route: "
        f"{sorted(stale)}. Remove them, or correct the path."
    )


@pytest.mark.parametrize(
    "method,path",
    [
        # --- Privilege escalation and account tampering ---------------------
        ("POST", "/api/users/sync"),         # created admin accounts anonymously
        ("POST", "/api/users/sync/bulk"),
        ("POST", "/api/users/"),             # open registration on an installed system
        # --- Personal and biometric data ------------------------------------
        ("GET", "/api/faces/search"),        # leaked who was seen, where and when
        ("GET", "/api/alpr/plates/"),        # ALPR reads are location history
        # --- Media served straight off disk ---------------------------------
        # These bypassed the recordings router entirely: they are declared on
        # `app`, so a per-router review never saw them. Snapshot names are
        # `{camera_id}_{YYYYmmdd_HHMMSS}.jpg` and enumerable by timestamp.
        ("GET", "/recordings/any.mp4"),
        ("GET", "/faces/any.jpg"),
        ("GET", "/api/snapshots/any.jpg"),
        ("GET", "/data/thumbnails/any.jpg"),
        # --- Control-plane and injection ------------------------------------
        ("POST", "/api/cameras/quick-add"),  # added AND started a camera anonymously
        ("POST", "/ecosystem/events"),       # injected alerts to every dashboard
        ("GET", "/api/system/info"),
        ("GET", "/api/analytics/summary"),
        ("POST", "/api/metrics/performance/reset"),
    ],
)
def test_audit_findings_stay_closed(client, method, path):
    """
    The specific routes the 2026-08-20 audit found open must refuse an anonymous
    caller. Kept separate from the sweep above so a regression names the finding
    it re-opens rather than appearing as one line in a list.

    503 counts as refusal: routes guarded by the ecosystem HMAC dependency answer
    503 when the optional appEcosystem package is absent, because the fallback
    dependency raises rather than passing the request through. That is the
    fail-closed behaviour we want on a standalone install — the request is still
    rejected without credentials.
    """
    response = client.request(method, path, json={})
    assert response.status_code in (401, 403, 503), (
        f"{method} {path} answered {response.status_code} without credentials; "
        "this route was closed by the 2026-08-20 authorization audit."
    )
