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

## Open findings (clean-install test, 2026-07-14)
- [ ] **Run the prod venv from the internal disk** — OpenEye's `venv/` lives on the
  external volume (`/Volumes/Locker2`); a force-unmount while mmap'd C-extensions
  (opencv/av/portaudio) are resident kills the backend with an unrecoverable SIGBUS
  (`KERN_MEMORY_ERROR`, "backing vnode was force unmounted" — observed 2026-07-14).
  Same crash class AegisSIEM/AFS/registry already fixed: build the venv at
  `~/.local/share/openeye/venv` and point the launcher at it.
- [ ] **No launchd service by default** — after the SIGBUS crash nothing restarted
  OpenEye (no KeepAlive). Pair the internal-venv move with `OPENEYE_INSTALL_SERVICE=1`
  as the recommended install.

## Recent changes (2026-07-14)
- **Installer's generated `start.sh` used port 8000 (AFS's port) + `--reload`** —
  every fresh install produced a launcher that collided with AI-for-Survival
  (`EADDRINUSE`) or silently ran on the wrong port. Template now uses OpenEye's
  documented **8200** without the dev reload flag.
- **SQL-injection middleware 500'd hashed frontend chunks** — Vite emits names like
  `TwoFactorSettings--CHBeorH.js`; the `(--|#|/*)` heuristic flagged the path, and
  raising `HTTPException` inside `BaseHTTPMiddleware` surfaced as a 500 (breaking the
  2FA settings page). Static mounts are now exempt from the path heuristic (query
  params still checked everywhere) and rejections return real 400s. 3 new tests.

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
- [ ] **RTSPCamera frame loop has no direct manual-record tests** — the 7 loop tests
  in `tests/core/test_manual_record_window.py` drive `MockCamera.get_frame()`; the
  RTSP block (`camera_manager.py:~1093-1124`) carries identical, line-reviewed edits
  but its duplicated logic can drift without coverage.
- [ ] **Dispatcher test gaps** — DB-commit failure/rollback path and
  target-by-`str(id)` matching in `notification_dispatch.py` are untested.
- [ ] **Two virtualenvs (`venv` prod, `.venv` dev)** — `venv` (used by `start.sh`)
  ships without pytest; tests only run from `.venv`. Consolidate or document
  (e.g. a `requirements-dev.txt` installable into `venv`).

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

## 🔭 Open follow-ups (flagged 2026-07-21)

- [ ] **`main` lacks the `.env` security fix.** Commit `2440686` (writes the
  secrets file at 0600 instead of 0644, and preserves it across reinstalls) is on
  `fix/camera-discovery-and-ws-rce` by an explicit owner decision. `main` still
  ships the world-readable `.env` until that branch merges. **Deliberate — do not
  cherry-pick it separately.**
- [ ] **AI features are not wired.** `backend/core/ecosystem_ai_bridge.py` defines
  `summarize_event()` and `shared_selected_model()`, but neither is called — the
  docstring says "not wired by default". The AI provider key + per-task routing
  endpoints exist (`/api/ai/providers`), so once OpenEye does real LLM work the
  configuration surface is already there.
- [x] **Frontend panel for AI providers built.** `frontend/src/pages/
  AIProviderSettingsPage.jsx` (+ `.css`), routed at `/system/ai-providers` in
  `App.jsx`, using the universal `Button/TextField/Card` components and
  `apiClient`. Matches AegisSIEM/AFS. (2026-07-21)
- [ ] **Runs from a code snapshot.** The service runs `~/.local/share/openeye/app`,
  not the repo, so repo edits require re-running `scripts/install-local.sh` — a
  restart alone silently keeps the old code.

Ecosystem-wide context is recorded in `appEcosystem/todos_changelog.md`.

## 🐧 Linux smoke test — 2026-07-22

Ran `setup-production.sh` in `debian:bookworm-slim`. Found and fixed a
silent-failure chain in `aed3282`; the underlying cause is the native-dep
requirement, which is inherent to this project.

**Fixed — the install lied about success.** `setup-production.sh` has no
`set -e`, and its two heaviest steps sent both stdout and exit status to
`/dev/null`:

    npm install > /dev/null 2>&1
    npm run build > /dev/null 2>&1
    echo "  ✓ Frontend built successfully"

On a box without npm this printed success, exited 0, and produced no `dist/`.
`verify_installation` saw the missing `dist/index.html` but downgraded it to a
yellow warning; the summary still said "Setup Complete!" pointing at a UI that
does not exist. The `pip install -r requirements.txt` step had the same shape,
so a failed dlib/OpenCV build surfaced only later as
`ModuleNotFoundError: face_recognition_models` with no cause shown — which is
exactly what the container's first (pre-fix) run produced. Both now capture a
log, check status, show the tail on failure, verify the artifact actually
exists, and the summary refuses to claim success (exit 1) when a required piece
is missing. Verified: on a bare box the fixed script stops at phase 3 and points
to `./install-deps.sh`.

### Still open / notes

- [ ] **`setup-production.sh` does not run `install-deps.sh`.** The native libs
  (dlib→cmake+build-essential, OpenCV, ffmpeg, portaudio) are a separate manual
  step. Consider either invoking it, or making the pip-failure message the
  single source of truth (currently done). A fully green run needs those libs
  present — a bare `python3+npm` box cannot build the backend.
- [ ] **No `apk`/Alpine branch in `install-deps.sh`.** `detect_platform()` falls
  through to `PKG_MGR="none"`; an Alpine user gets no system deps and must
  install them by hand. dlib on musl is its own adventure — may be out of scope,
  but the installer should at least say so.
- [x] **Full green Linux run** — with native deps present, `setup-production.sh`
  completes: "Setup Complete!", exit 0, venv + frontend build verified. (2026-07-22)
- [x] **Standalone backend could not import (fixed, `d228e7d`).** Even after a
  green install the backend died on `import backend.main` with
  `ModuleNotFoundError: ecosystem_auth`. `routes/ecosystem.py` imported it at
  top level and `main.py` registers that router unconditionally, so a
  standalone install (a *supported* config) had no working API. Guarded the
  import — endpoints needing it now return 503 when appEcosystem is absent,
  unchanged when present. Also: `setup-production.sh` never installed the shared
  packages (only `install-local.sh` did); it now does, from the sibling repo.
  A standalone end-to-end re-run confirming `import backend.main` succeeds was
  in progress at time of writing.
- [ ] **`uninstall.sh` systemd branch** is correctly guarded (`if [ -f … ]`),
  unlike AegisSIEM's was — but still unrun on Linux.
- **Doc-policy note:** `todos_changelog.md` is *tracked* here (whitelisted in
  `.gitignore:112`) and in LogAnalysis, but *ignored* in appEcosystem. One
  convention is wrong under the no-dev-`.md` policy — owner call which.
