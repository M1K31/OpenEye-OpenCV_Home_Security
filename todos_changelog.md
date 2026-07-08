# OpenEye — TODO / Changelog Tracker

Consolidated view of inline `TODO` markers (extracted from the code) and recent
changes. See [CHANGELOG.md](CHANGELOG.md) for the full release history.

## Open work (from inline TODOs)

### Integrations & notifications
- [ ] Load/save Home Assistant, HomeKit, and Google Nest integration config —
  `backend/api/routes/integrations.py:125,145,149,153`

### Automation engine
- [ ] Register with the face-detection event system — `backend/core/automation_engine.py:410`
- [ ] Fetch `recording_id` from the database when needed — `backend/core/camera_manager.py:567`

### Face recognition
- [ ] Make training feature toggles configurable — `backend/api/routes/faces.py:806`
- [ ] Compute real quality / encoding-quality scores (currently hardcoded `0.9`) —
  `backend/api/routes/faces.py:1042,1099`

### Hardware
- [ ] Implement statistics collection from running cameras — `backend/api/routes/hardware.py:408`

### Frontend / UX
- [ ] PTZ: fetch the current pan position (hardcoded `0`) — `frontend/src/components/PTZControl.jsx:183`
- [ ] Replace `alert()` with a proper notification component —
  `frontend/src/pages/HardwareDetectionPage.jsx:109`

## Open findings (install / test, 2026-06-28)
- [ ] **WebRTC silently disabled on macOS** — installer pulls **ffmpeg 8** but PyAV
  (`av`, via aiortc) needs **ffmpeg 7**, so `av` never builds and two-way audio is
  dropped. Install `ffmpeg@7` and build `av` against it, or surface a clear message.
- [ ] **Service not auto-started** non-interactively (by design) — document
  `OPENEYE_INSTALL_SERVICE=1` or auto-restart an existing service after reinstall.
- [ ] **DevOps:** set Docker Hub credentials/username for `docker-push.sh`.
- [ ] **RTSPCamera stop condition lacks `should_stop_recording()` max-duration cap**
  (pre-existing asymmetry) — MockCamera enforces a max recording duration on its
  manual-record window; the RTSP block does not.

## Recent changes (2026-07-07)
- Automation notifications are now live end to end: rule actions of type
  `notification` deliver through the central dispatch layer
  (`backend/core/notification_dispatch.py`), with optional per-action
  `providers` targeting and an opt-in `cooldown_seconds` to suppress repeat
  pings in high-traffic areas. Resolves
  `backend/core/automation_engine.py:113` (was: integrate with the real
  notification system).
- Automation `record` actions open a real manual-record window on both
  `MockCamera` and `RTSPCamera` blocks (camera-thread bridge). Resolves
  `backend/core/automation_engine.py:135` (was: integrate with the camera
  recording system).
- Ecosystem notification routes are real: `POST /api/notifications/` delivers
  via the configured providers (optionally scoped per rule); `GET`/`PUT
  /api/notifications/settings` persist to the database; Android push sends via
  FCM. Resolves `backend/api/routes/ecosystem.py:615` (route notifications to
  configured delivery methods), `:632` (load notification config from the
  database), and `:1377` (implement actual push-notification sending).
- Automations UI: provider multi-select and a cooldown field on notification
  actions, wired to the same `providers`/`cooldown_seconds` action config keys
  the backend reads.

## Recent changes (2026-06-28)
- Ecosystem auth installs from the public appEcosystem repo in CI + Docker (was a
  broken `COPY` of never-committed vendored dirs); CI green.
- Fixed the `auth ↔ crud` circular import that broke the E2E app import.
- E2E: import models before `create_all` (test DB tables now created).
- Docker publish: gha cache made best-effort; cosmetic DockerHub-description step
  is non-fatal.
- In-app "Ecosystem Setup" panel (System & Alerts) for the shared HMAC secret.
- Backend imports without `aiortc` (WebRTC optional, gated by `WEBRTC_AVAILABLE`).
