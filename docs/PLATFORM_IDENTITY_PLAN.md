# macOS/Linux Service Identity & Camera Permission — Investigation and Plan

**Prepared for:** Smart Industries LLC
**Date:** 21 July 2026
**Covers:** unmerged work review, USB camera permission mitigation, service naming in
privacy settings

---

## 1. Repository State — Unmerged Work

### Branches

| Ref | Position | Action |
|-----|----------|--------|
| `main` | 5 commits **ahead** of `origin/main` | Push — no conflicts |
| `origin/main` | `73a69f5` | Strict ancestor of local `main` |
| `fix/camera-discovery-and-ws-rce` | 2 commits ahead of `main` | Merge |

No feature branches were abandoned and nothing exists on the remote that `main` lacks.
The divergence is a clean fast-forward: five `fix(install)` commits sitting unpushed
locally.

```
ba6bfb1  fix(install): run from the internal snapshot on Linux too; fix dead rmdir
defa12d  fix(install): run entirely from the internal disk
10abfd1  fix(install): create the launchd agent by default
4b3a3c5  fix(install): portable placeholder substitution in generated start.sh
e9e4c6a  fix(install): build the runtime venv on the internal disk
```

**These five commits are the highest-risk unpushed work in the repository** — they changed
how every install lays itself out, and they exist on exactly one machine, on an external
volume. Push them before anything else.

### Stashes — review before discarding

```
stash@{0}  pre-phaseE WIP: old-scheme ecosystem_auth/client + DOCKER.md
stash@{1}  WIP on main: 8286aa3 feat: set ecosystem priority=50, sync ecosystem_client
```

Both touch `ecosystem_auth`, which is the module whose unguarded import currently prevents
the entire test suite from collecting (audit F-03). Inspect these before fixing that import —
they may contain the intended integration.

### Correction to the audit: F-02 is worse than reported, and confirmed live

The audit stated the weak `SECRET_KEY` fallback was reachable. It is not merely reachable —
**it is active on this machine right now.** `~/Library/Logs/OpenEye/stderr.log` contains
five occurrences of `Using weak SECRET_KEY - DEVELOPMENT ONLY`.

The installer is not at fault; it does the right thing. `install-local.sh:313` generates a
strong random `SECRET_KEY` and a separate `JWT_SECRET_KEY`, writes them to `.env`, and
`start.sh:518` sources that file before launching. The failure is that **the launchd plist
bypasses `start.sh` entirely** and invokes uvicorn directly, so `.env` is never sourced.

`load_dotenv()` cannot compensate, because of an import-ordering bug:

```python
# backend/main.py
39  from dotenv import load_dotenv
44  from backend.api.routes import (users, cameras, ...)   # ← imports auth.py, which
                                                            #   reads SECRET_KEY at
                                                            #   module scope
94  load_dotenv()                                           # ← 50 lines too late
```

`backend/core/auth.py` evaluates `os.getenv("SECRET_KEY")` at import time, which happens at
line 44 — before `load_dotenv()` runs at line 94. The installer's own comment at
`install-local.sh:513` documents this hazard and works around it in `start.sh`; the launchd
path silently reintroduces it.

**Two independent fixes, both wanted:**

1. Move `load_dotenv()` above every `backend.*` import in `main.py` (it must be the first
   statement after the `dotenv` import itself).
2. Add the secrets to the launchd plist / systemd unit via `EnvironmentVariables`, or point
   launchd at `start.sh` rather than at uvicorn.

Also note `.env` is mode `0644` — world-readable on a multi-user machine. It should be `0600`.

---

## 2. USB Camera Permission — Root Cause and Mitigation

### Why the current design cannot work

macOS TCC does not grant permissions to files; it grants them to **code-signing
identities**. The current service resolves like this:

```
plist → ~/.local/share/openeye/venv/bin/python3
      → /Library/Developer/CommandLineTools/.../Python3.framework/.../python3.9
```

That binary is Apple-signed. Its identity, verified with `codesign`:

```
Identifier=com.apple.python3
Authority=Software Signing
```

Three consequences follow, and the third is a security problem rather than an annoyance:

1. **No usage description.** Apple's interpreter carries no `NSCameraUsageDescription`, so
   TCC has no prompt string to display and denies rather than asks.
2. **No prompt is possible under launchd.** A launchd job has no GUI session attachment, so
   even a promptable binary would be denied silently.
3. **The identity is shared system-wide.** Every Python program on the machine presents
   `com.apple.python3`. Granting camera access to "Python" grants it to *every* Python
   script the user ever runs — including ones they did not write. The permission cannot be
   scoped to OpenEye because OpenEye has no distinct identity to scope it to.

Point 3 is why the workaround from the previous session — grant camera access to Terminal —
should be treated as a stopgap, not a solution. It grants camera access to everything
launched from a terminal.

### Verified prototype

Rather than propose an untested approach, the mechanism was validated in a scratch build:

**Confirmed working:**
- A minimal `.app` bundle signed with `--identifier com.smartindustries.openeye` reports
  `Identifier=com.smartindustries.openeye` — a distinct TCC identity, verified via
  `codesign -dv`.
- A small compiled launcher placed at `Contents/MacOS/OpenEye`, signed as part of the
  bundle, successfully starts the existing venv interpreter with the application's
  arguments. No repackaging of the Python runtime is required.

**Confirmed not viable:**
- Copying the interpreter binary into the bundle. It is linked against
  `@executable_path/../Python3` and fails at dyld load once relocated:
  `Library not loaded: @executable_path/../Python3`. Any plan that relocates the
  interpreter must also relocate and re-path the whole framework — avoid this.

**Requires on-device confirmation:**
- Whether TCC attributes the camera request to the signed launcher or to the interpreter
  it starts. The launcher must therefore **spawn and supervise** the interpreter as a child
  rather than `execve` into it — `execve` replaces the process image, discarding the
  bundle's signature along with it. With `posix_spawn` the launcher remains the
  *responsible process*, which is the attribution TCC follows.

### Recommended design

Ship `OpenEye.app` as an install artifact, and have launchd start the bundle rather than
the interpreter. **No functionality is removed**: the same venv, the same uvicorn command,
the same port, the same working directory. Only the process identity changes.

```
OpenEye.app/
  Contents/
    Info.plist          CFBundleIdentifier  = com.smartindustries.openeye
                        CFBundleName        = OpenEye
                        LSBackgroundOnly    = true      (no Dock icon)
                        NSCameraUsageDescription     = "OpenEye needs camera access to
                                                        monitor your USB and built-in
                                                        cameras."
                        NSMicrophoneUsageDescription = "OpenEye needs microphone access
                                                        for two-way audio."
    MacOS/
      OpenEye           compiled launcher; posix_spawn()s $OPENEYE_PYTHON with
                        the uvicorn arguments, forwards SIGTERM/SIGINT to the
                        child, and exits with the child's status
    Resources/
      openeye.icns      icon shown in Privacy & Security
```

The launcher must forward signals, or the graceful-shutdown handlers at `main.py:106-121`
will stop being reached — the one place this change could regress behaviour.

The plist then becomes:

```xml
<key>ProgramArguments</key>
<array><string>/Applications/OpenEye.app/Contents/MacOS/OpenEye</string></array>
<key>EnvironmentVariables</key>
<dict>
  <key>OPENEYE_PYTHON</key><string>~/.local/share/openeye/venv/bin/python3</string>
  <key>ENVIRONMENT</key><string>production</string>
  <!-- plus SECRET_KEY / JWT_SECRET_KEY, closing the gap in section 1 -->
</dict>
```

Signing: ad-hoc (`codesign -s -`) is sufficient for local installs and was what the
prototype used. TCC ties the grant to the identifier plus the binary's content hash, so
**the grant is invalidated whenever the launcher is rebuilt** — keep the launcher tiny and
stable so upgrades to Python or the application code do not reset the user's permission.
For distribution outside the developer's machine, a Developer ID certificate plus
notarization is required.

### Handling first-run permission

`LSBackgroundOnly` avoids a Dock icon but does not by itself make a launchd job able to
prompt. Ship a small **companion action** the user runs once from Finder — a
`Grant Camera Access` entry that launches the bundle in a normal GUI session, calls
`AVCaptureDevice.requestAccess`, and exits. The grant then persists for the identifier, and
the launchd job inherits it on subsequent starts.

Discovery already reports the denial clearly and names the attached devices, so if the user
skips this step the failure is legible rather than silent.

### Fallback

If on-device testing shows TCC still attributing to the interpreter, fall back to `py2app`
or PyInstaller, which produce a bundle with an embedded, correctly-pathed runtime. Cost:
a build step and roughly 50 MB, plus a rebuild on each Python upgrade. Prefer the launcher;
it keeps the venv-based install model the project already depends on.

### Linux

TCC has no Linux equivalent; camera access is filesystem permissions on `/dev/video*`.

- Add the service account to the `video` group at install time, and verify with
  `getent group video`.
- Report the specific cause when a device node exists but is unreadable — discovery already
  distinguishes this case and emits the `video` group hint.
- Under Flatpak or Snap the camera XDG portal would apply, but the project installs as a
  systemd unit, so this is out of scope unless packaging changes.

---

## 3. Service Naming in Privacy Settings and Process Lists

### Current behaviour

`ps -p <pid> -o comm=` on the running service returns:

```
Python
```

Everywhere the operating system surfaces this process — Privacy & Security panes,
Activity Monitor, `ps`, `top`, Console — it appears as a generic Python interpreter,
indistinguishable from any other Python program. When the user is asked to approve camera,
microphone, or Full Disk Access, the request appears to come from "Python".

This is a genuine security-usability defect, not cosmetic. A user who cannot identify which
application is requesting Full Disk Access cannot make an informed decision, and is trained
to approve anonymous requests.

### macOS — resolved by the same bundle

The `.app` bundle from section 2 fixes this as a side effect. Once the responsible process
carries `CFBundleName = OpenEye` and `CFBundleIdentifier = com.smartindustries.openeye`,
every TCC pane lists **OpenEye** with its icon. This is the primary argument for the bundle
even independent of the camera issue: the two problems have one solution.

Add `CFBundleDisplayName = OpenEye Surveillance` for the longer form, and ship
`openeye.icns` so the entry is visually identifiable.

### Both platforms — process title

Add `setproctitle` (not currently a dependency) and set the title during startup, before
the server binds:

```python
# main.py, immediately after load_dotenv()
try:
    import setproctitle
    setproctitle.setproctitle("openeye-server")
except ImportError:
    pass  # cosmetic only; never block startup on it
```

`ps`, `top`, and `htop` then show `openeye-server`. This is the only mechanism that helps on
Linux, where there is no bundle concept.

### Linux — systemd identity

The unit already sets `Description=OpenEye Surveillance System`, which is good. Two
additions:

```ini
SyslogIdentifier=openeye        # journalctl -t openeye
StateDirectory=openeye          # systemd-managed, correctly-permissioned state
```

Without `SyslogIdentifier`, journal entries are attributed to `python3` — the same
identification problem in a different surface.

---

## 4. Sequencing

Ordered by risk retired per unit of effort.

| # | Action | Effort | Why first |
|---|--------|--------|-----------|
| 1 | Push `main`; merge `fix/camera-discovery-and-ws-rce` | 15m | Five install commits exist on one external volume |
| 2 | Move `load_dotenv()` above `backend.*` imports | 15m | Service is running on a published key right now |
| 3 | Inject secrets via plist/unit; `chmod 600 .env` | 1h | Closes the same hole from the other side |
| 4 | Review both stashes before touching `ecosystem_auth` | 1h | May contain the intended integration |
| 5 | Add `setproctitle`; add `SyslogIdentifier` | 1h | Cheapest identity win; no packaging change |
| 6 | Build `OpenEye.app` launcher; repoint launchd | 2d | Fixes camera permission and privacy naming together |
| 7 | Ship the one-time permission-grant action | 4h | Makes first run succeed without terminal instructions |
| 8 | Linux `video` group handling in installer | 2h | Platform parity |

Items 1-3 are the same day's work and retire a live, confirmed vulnerability. Item 6 is the
substantial piece and should not begin until the test suite collects again (audit F-03), or
it cannot be verified.

---

## Appendix — Reproducing the findings

```bash
# Interpreter identity — the root of both problems
codesign -dv --verbose=2 ~/.local/share/openeye/venv/bin/python3   # com.apple.python3

# The service is running on the published development key
grep -c "weak SECRET_KEY" ~/Library/Logs/OpenEye/stderr.log

# The import-ordering bug
grep -n "load_dotenv\|from backend.api.routes" opencv_surveillance/backend/main.py

# How the process presents itself
ps -p "$(pgrep -f 'uvicorn backend.main')" -o comm=                # Python

# Unpushed work
git log --oneline origin/main..main
git stash list
```
