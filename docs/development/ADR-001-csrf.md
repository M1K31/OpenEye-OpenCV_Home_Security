# ADR-001 — CSRF protection posture

**Status:** Accepted
**Date:** 2026-07-24
**Owner:** Smart Industries LLC

## Context

An earlier audit flagged that `CSRFProtection` middleware existed in the codebase
but was commented out in `backend/main.py`, which reads as an accidental security
gap.

## Decision

CSRF protection is **intentionally not enabled** for the default deployment.

OpenEye authenticates every request with a **bearer JWT sent in the
`Authorization` header**, retrieved by the frontend from `localStorage`. It does
**not** use an ambient session cookie for authentication. Classic CSRF relies on
the browser automatically attaching credentials (cookies) to a forged cross-site
request; because our token is not a cookie, a cross-site page cannot attach it,
so the JSON API is not CSRF-exploitable.

The `CSRFProtection` middleware is **retained**, not deleted, and is now gated by
an environment flag:

```
ENABLE_CSRF_PROTECTION=true
```

## Consequences

- **If a future change introduces cookie-based authentication** (including an
  `HttpOnly` refresh cookie — see the deferred F-07 work to move the access token
  out of `localStorage`), CSRF protection **must** be enabled for state-changing
  routes at the same time. This ADR is the tripwire for that.
- The related `localStorage` token-storage risk (XSS token theft, audit F-07) is
  tracked separately and is **not** mitigated by CSRF; it requires the token
  storage change plus a strict Content-Security-Policy.

## References

- Audit finding F-02/F-07/F-08 — `docs/development/COMPREHENSIVE_AUDIT_2026-07-24.md`
- `backend/middleware/csrf_protection.py`
- `backend/main.py` (CSRF gating block)
