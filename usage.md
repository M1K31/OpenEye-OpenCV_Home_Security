# OpenEye — Usage Guide

Practical guide to installing, running, and using OpenEye, plus consuming its API.
The backend serves on port **8200** by default (UI + REST under `/api`). Full
endpoint reference: [docs/API_REFERENCE.md](docs/API_REFERENCE.md). Docker:
[DOCKER.md](DOCKER.md).

---

## 1. Install & lifecycle

```bash
cd opencv_surveillance
./scripts/install-local.sh                 # system deps (opencv/ffmpeg) + venv + build the React frontend
OPENEYE_NONINTERACTIVE=1 ./scripts/install-local.sh   # unattended (keeps existing venv, skips prompts)
OPENEYE_INSTALL_SERVICE=1 OPENEYE_NONINTERACTIVE=1 ./scripts/install-local.sh   # also install the auto-start service
```

Run:

```bash
./start.sh                                  # generated launcher (uvicorn backend.main:app :8200)
# or directly:
venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8200
```

- **Auto-start service:** macOS launchd (`com.smartindustries.openeye`) / Linux
  systemd — opt in with `OPENEYE_INSTALL_SERVICE=1`.
- **Uninstall:** `./scripts/install-local.sh` writes an uninstall path; remove the
  launchd agent / systemd unit and the project venv. See
  [docs/UNINSTALL_GUIDE.md](docs/UNINSTALL_GUIDE.md).
- **WebRTC (two-way audio)** is optional. The backend runs without `aiortc`; the
  installer tries to build it (needs **ffmpeg 7** — note ffmpeg 8 won't build `av`).

> The frontend is built during install. If `/` returns *"Frontend not built"*, run
> `cd frontend && npm install && npm run build`.

---

## 2. First run, login, recovery

1. Open `http://localhost:8200`. With no admin yet, you're redirected to **`/setup`**.
2. **Create Admin Account** → "Get Started" → set a username + password (8–72 chars,
   upper + lower + number + special).
3. Log in. Sessions use JWT.
4. **Forgot the admin password?** Use the password reset flow / `create_admin_user.py`.

---

## 3. Consuming the API

Interactive docs live at **`http://localhost:8200/api/docs`** (Swagger). Most routes
require an authenticated session (`auth.get_current_user`).

```bash
# Health (public)
curl -fsS http://localhost:8200/api/health

# Log in -> JWT (then send it as a Bearer token / cookie)
curl -fsS -X POST http://localhost:8200/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<your-password>"}'

# Cameras / faces / automations (authenticated)
curl -fsS http://localhost:8200/api/cameras -H "Authorization: Bearer $TOKEN"

# Ecosystem shared-secret (in-app setup, System & Alerts page)
curl -fsS http://localhost:8200/api/ecosystem/secret -H "Authorization: Bearer $TOKEN"
# -> {"configured": true, "source": "env", "path": "~/.config/ecosystem/secret.env", "masked": "…"}
```

OpenEye also exposes ecosystem integration endpoints (`/api/ecosystem/*`): connect,
status, devices, security, and an HMAC-authenticated webhook + WebSocket event feed
for cross-app events (e.g. pushing a security alert to AegisSIEM).

---

## 4. UI walkthrough

Sidebar:

- **Live Dashboard** — camera grid + live status.
- **Events & History** — detected events.
- **Timeline Playback** — recorded footage scrubber.
- **Camera Manager** — add/configure cameras (per-camera motion, recording, image
  quality, zones via the ⚙ button on each card). Includes ARP-prioritized cross-platform
  RTSP/ONVIF discovery (supporting TP-Link Tapo, Hikvision, Dahua/Amcrest, Reolink,
  Axis, UniFi, and Foscam) with inline credential entry and Fernet encryption at rest
  (`enc:v1:...`) in SQLite.
- **AI & Faces** — face library, training, recognition history.
- **Automations** — rules that trigger actions when specific people are detected.
  Notification actions deliver via the providers configured under notification
  settings, optionally scoped per rule to a subset of those providers. A
  per-action notification cooldown suppresses repeat pings in high-traffic
  areas while recordings continue uninterrupted.
- **System & Alerts** — storage paths, display/recording/performance/accessibility
  settings, and the **Ecosystem Setup** card (shared-secret status / paste / generate).
- **Themes** — UI theming.

---

## 5. Ecosystem integration

OpenEye registers with the appEcosystem registry when present (priority 50,
"fallback ecosystem manager") and degrades gracefully when absent. Provision the
shared secret on the System & Alerts → **Ecosystem Setup** card, or via the
`ecosystem secret` CLI / `~/.config/ecosystem/secret.env`. The LLM selection syncs
from the registry's shared AI profile.

### Publishing Detections to the Mesh
OpenEye uses `ecosystem_client` to broadcast real-time computer vision events (motion, face recognition, vehicle detection) so `AegisSIEM` and `cyber-agents` can correlate physical security with network traffic:

```python
from ecosystem_client import EcosystemClient

eco = EcosystemClient(service_name="openeye", service_port=8200)
await eco.start()

# Emit physical security detection
await eco.publish("physical.motion", {
    "camera_id": "driveway_cam",
    "detected_objects": ["person", "vehicle"],
    "confidence": 0.94,
    "zone": "driveway"
})
```



---

## 6. Automations, Forensic Scans & Emergency Freeze

OpenEye's automation engine (`backend/core/automation_engine.py`) supports cross-ecosystem security actions:

### New Action Types
- **`device_scan`**: Dispatches an authorized forensic scan request for a designated target (`self` or specific `device_id`). Requires an active `auto_scan` grant designated during onboarding or via the control plane.
- **`scan_schedule`**: Configures a recurring scan schedule for a designated endpoint.
- **`ecosystem_freeze`**: Broadcasts an emergency freeze event (`ecosystem.freeze`) across the local mesh, stopping new scan/mutation jobs in response to a physical perimeter intrusion.

### Example Automation Rule (YAML / JSON)
```json
{
  "name": "Perimeter Breach -> Emergency Freeze",
  "trigger": { "type": "event", "event": "security.person_detected", "match": { "known": false } },
  "conditions": [
    { "type": "camera_zone", "zone": "restricted_backyard" }
  ],
  "actions": [
    { "type": "ecosystem_freeze", "config": { "reason": "Unrecognized intruder in backyard zone" } }
  ]
}
```
