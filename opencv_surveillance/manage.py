#!/usr/bin/env python3
# Copyright (c) 2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security

"""
OpenEye lifecycle manager — one command surface on Windows, macOS and Linux.

Starts, stops, restarts and inspects the OpenEye server. It resolves the
service port the same way the application does, identifies OpenEye's own
processes before signalling them, stops the server gracefully with a forced
fallback, and reports what it found. It needs only the standard library plus
psutil, which OpenEye already installs.

The shell scripts in the project root (start-local.sh, stop-server.sh and
friends) remain the documented entry points on macOS and Linux, and existing
systemd units and launch agents continue to use them. This module is the
supported way to do the same things on Windows, and can be used directly on
any platform.

Usage
-----
    python manage.py start            # start in the background, record the PID
    python manage.py start -f         # run in the foreground (Ctrl+C to stop)
    python manage.py stop             # graceful stop, escalating if needed
    python manage.py restart
    python manage.py status           # is it up, on which port, since when
    python manage.py logs [-n 200]    # tail the application log
    python manage.py doctor           # check this machine can run OpenEye

Run it from the opencv_surveillance directory, or from anywhere with the full
path — it locates the application relative to itself.

Exit codes: 0 success, 1 failure, 2 nothing was running (for `stop`/`status`).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional

APP_DIR = Path(__file__).resolve().parent
IS_WINDOWS = sys.platform == "win32"

# How long a graceful stop is given before escalating. Matches stop-server.sh so
# behaviour does not change depending on which entry point an operator used.
GRACEFUL_TIMEOUT_SECONDS = 10.0

# Marker every OpenEye server process carries on its command line. This is how
# an OpenEye process is told apart from unrelated software that happens to hold
# the same port, so that only OpenEye is ever signalled.
PROCESS_MARKER = "backend.main:app"


# ---------------------------------------------------------------------------
# Environment resolution
# ---------------------------------------------------------------------------

def _bootstrap_path() -> None:
    """Make `backend.*` importable regardless of the working directory."""
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))


def resolve_port() -> int:
    """
    The canonical service port, resolved exactly as the application resolves it.

    Delegates to backend.core.config rather than reimplementing the precedence
    rules, so this tool and the server always agree on which port is in play.
    Falls back to reading the environment directly if the application package
    cannot be imported, so `status` still works from a broken checkout.
    """
    _bootstrap_path()
    try:
        from backend.core.config import resolve_service_port

        return resolve_service_port()
    except Exception:
        for var in ("ECOSYSTEM_SERVICE_PORT", "OPENEYE_PORT", "PORT"):
            value = os.getenv(var)
            if value and value.isdigit():
                return int(value)
        return 8200


def data_root() -> Path:
    """Where this installation keeps its writable state."""
    _bootstrap_path()
    try:
        from backend.core.paths import DATA_ROOT

        return Path(DATA_ROOT)
    except Exception:
        override = (os.getenv("OPENEYE_DATA_ROOT") or "").strip()
        return Path(override) if override else APP_DIR


def venv_python() -> str:
    """
    The interpreter to launch the server with.

    Prefers this project's virtual environment over whatever happens to be on
    PATH, and handles both layouts: POSIX venvs put the interpreter in `bin/`,
    Windows venvs in `Scripts/`.
    """
    if sys.prefix != sys.base_prefix:
        return sys.executable  # already inside a venv

    subdir = "Scripts" if IS_WINDOWS else "bin"
    name = "python.exe" if IS_WINDOWS else "python3"
    for venv in (APP_DIR / ".venv", APP_DIR / "venv"):
        candidate = venv / subdir / name
        if candidate.exists():
            return str(candidate)
    return sys.executable


def pid_file() -> Path:
    return data_root() / "openeye.pid"


def runtime_file() -> Path:
    return data_root() / "runtime.json"


def read_runtime_state() -> dict:
    """
    What the last launch recorded about itself, if anything.

    `backend/app_entry.py` writes this file when the packaged application
    starts, because a desktop launch moves to the next free port rather than
    refusing to start — so the port in the configuration is not necessarily the
    port in use. Reading it here means `status` and `stop` can find an instance
    this script did not start.
    """
    try:
        return json.loads(runtime_file().read_text())
    except (OSError, ValueError):
        return {}


def log_file() -> Path:
    return data_root() / "logs" / "openeye-app.log"


# ---------------------------------------------------------------------------
# Process discovery
# ---------------------------------------------------------------------------

def _psutil():
    try:
        import psutil

        return psutil
    except ImportError:
        sys.stderr.write(
            "psutil is not installed. It is a declared dependency:\n"
            f"    {venv_python()} -m pip install psutil\n"
        )
        raise SystemExit(1)


def _is_openeye(proc) -> bool:
    """
    True when this process is an OpenEye server rather than something that
    merely holds the port or has a similar name.

    Identity comes from the command line rather than from the port, so this
    never signals unrelated software that happens to be listening, and never
    signals a second OpenEye instance running from a different directory —
    a development checkout beside an installed copy is a supported layout.
    """
    try:
        cmdline = " ".join(proc.cmdline())
    except Exception:
        return False
    if PROCESS_MARKER in cmdline:
        return True
    return "manage.py" in cmdline and " start" in cmdline


def find_server_processes(port: Optional[int] = None) -> List:
    """Every live OpenEye server process, found by PID file, then by scan."""
    psutil = _psutil()
    found = {}

    # The PID file this script writes, and the runtime state a bundle launch
    # writes. Either may be stale; both are verified against the command line
    # before being trusted, so a recycled PID cannot get an unrelated process
    # killed.
    for recorded in (read_pid(), read_runtime_state().get("pid")):
        if not isinstance(recorded, int):
            continue
        try:
            proc = psutil.Process(recorded)
            if _is_openeye(proc):
                found[proc.pid] = proc
        except psutil.Error:
            continue

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.pid not in found and _is_openeye(proc):
                found[proc.pid] = proc
        except psutil.Error:
            continue

    # `port` is accepted for symmetry with the other helpers but deliberately
    # not used to filter: a reloader parent, or a worker that has not yet bound,
    # holds no socket on the port and would be missed — and those are exactly
    # the processes that get orphaned. Identity comes from the command line.
    return list(found.values())


def read_pid() -> Optional[int]:
    try:
        return int(pid_file().read_text().strip())
    except (OSError, ValueError):
        return None


def write_pid(pid: int) -> None:
    path = pid_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def clear_pid() -> None:
    try:
        pid_file().unlink()
    except OSError:
        pass


def port_holder(port: int):
    """
    The process listening on `port`, whether or not it is ours.

    Reported rather than acted on when it is not OpenEye: another application
    holding our port is a conflict worth surfacing, not something to terminate.
    """
    psutil = _psutil()
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == "LISTEN":
                if conn.pid:
                    return psutil.Process(conn.pid)
    except (psutil.AccessDenied, psutil.Error):
        # net_connections needs elevation on macOS and some Windows configs.
        # Absence of an answer is not evidence the port is free, so fall back
        # to a bind probe below.
        return None
    return None


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_start(args) -> int:
    port = args.port or resolve_port()

    running = find_server_processes(port)
    if running:
        print(f"OpenEye is already running (PID {running[0].pid}). "
              "Use `restart` to replace it.")
        return 1

    if not port_is_free(port):
        holder = port_holder(port)
        who = f" (PID {holder.pid}: {holder.name()})" if holder else ""
        print(f"Port {port} is already in use{who}.")
        print("Free it, or choose another port with --port / OPENEYE_PORT.")
        return 1

    env = os.environ.copy()
    # Keep bind and ecosystem registration on the same number. Advertising a
    # port the server is not listening on is silent and near-impossible to
    # diagnose from the peer's side.
    env["OPENEYE_PORT"] = str(port)
    env.setdefault("ECOSYSTEM_SERVICE_PORT", str(port))
    # OpenMP guards, matching what start-local.sh exports. Intel libiomp and
    # LLVM libomp loading together produces threadpoolctl warnings and, on some
    # builds, a hard abort.
    env.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        env.setdefault(var, "1")

    command = [
        venv_python(), "-m", "uvicorn", "backend.main:app",
        "--host", os.getenv("OPENEYE_BIND_HOST", "0.0.0.0"),
        "--port", str(port),
    ]
    # Auto-reload is opt-in and development-only. The reloader runs a
    # supervisor alongside the worker, which roughly doubles resident memory
    # for a process already holding video frame buffers, and its file watcher
    # covers the working directory — which is also where a source checkout
    # keeps its recordings.
    if args.reload:
        command.append("--reload")
        print("Auto-reload enabled — development only. The server will "
              "restart when files in the project directory change.")

    if args.foreground:
        print(f"Starting OpenEye on http://localhost:{port} (Ctrl+C to stop)")
        return subprocess.call(command, cwd=str(APP_DIR), env=env)

    log_path = log_file()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_path, "ab")

    kwargs = {
        "cwd": str(APP_DIR),
        "env": env,
        "stdout": handle,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
    }
    if IS_WINDOWS:
        # A new process group is what makes a graceful stop possible at all on
        # Windows: CTRL_BREAK_EVENT can only be delivered to a group, and
        # uvicorn installs a SIGBREAK handler that runs its shutdown sequence.
        # Without this the only option is TerminateProcess, which gives the
        # application no chance to close cameras or the database.
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(command, **kwargs)
    write_pid(proc.pid)

    if not _wait_for_health(port, timeout=90):
        print(f"Server did not become healthy within 90s. See {log_path}")
        return 1

    print(f"OpenEye started (PID {proc.pid}) on http://localhost:{port}")
    print(f"Logs: {log_path}")
    return 0


def _wait_for_health(port: int, timeout: float) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def _request_graceful_stop(proc) -> None:
    """
    Ask one process to shut down, using whichever mechanism the platform has.

    POSIX has SIGTERM and uvicorn handles it directly. Windows has no SIGTERM
    that a service can act on; the equivalent is a console control event
    delivered to the process group, which is why `start` creates one. If that
    is refused — typically because the target was started from a different
    console — fall back to psutil's terminate(), which on Windows is
    TerminateProcess and is NOT graceful. The caller reports which happened.
    """
    if IS_WINDOWS:
        try:
            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
            return
        except (OSError, AttributeError, ValueError):
            pass
    proc.terminate()


def cmd_stop(args) -> int:
    port = args.port or resolve_port()
    processes = find_server_processes(port)

    if not processes:
        clear_pid()
        holder = port_holder(port)
        if holder:
            print(f"No OpenEye process found, but port {port} is held by "
                  f"PID {holder.pid} ({holder.name()}). Left untouched.")
            return 1
        print("OpenEye is not running.")
        return 2

    psutil = _psutil()
    print(f"Stopping {len(processes)} OpenEye process(es)...")
    for proc in processes:
        try:
            _request_graceful_stop(proc)
            print(f"  requested shutdown of PID {proc.pid}")
        except psutil.Error as exc:
            print(f"  could not signal PID {proc.pid}: {exc}")

    gone, alive = psutil.wait_procs(processes, timeout=GRACEFUL_TIMEOUT_SECONDS)
    for proc in gone:
        print(f"  PID {proc.pid} stopped gracefully")

    for proc in alive:
        print(f"  PID {proc.pid} did not stop in {GRACEFUL_TIMEOUT_SECONDS:.0f}s "
              "— forcing")
        try:
            proc.kill()
        except psutil.Error:
            pass
    if alive:
        psutil.wait_procs(alive, timeout=5)

    clear_pid()

    # The OS releases a listening socket slightly after the process exits.
    for _ in range(10):
        if port_is_free(port):
            break
        time.sleep(0.3)

    print("OpenEye stopped." if not alive else
          "OpenEye stopped (some processes required a forced kill — check the log).")
    return 0


def cmd_restart(args) -> int:
    result = cmd_stop(args)
    if result not in (0, 2):
        return result
    time.sleep(1.0)
    return cmd_start(args)


def cmd_status(args) -> int:
    port = args.port or resolve_port()
    processes = find_server_processes(port)

    print(f"Data root : {data_root()}")
    print(f"Port      : {port}")

    if not processes:
        holder = port_holder(port)
        print("State     : stopped")
        if holder:
            print(f"Note      : port {port} is held by PID {holder.pid} "
                  f"({holder.name()})")
        return 2

    for proc in processes:
        try:
            started = time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(proc.create_time()))
            rss_mb = proc.memory_info().rss / (1024 * 1024)
            print("State     : running")
            print(f"PID       : {proc.pid}")
            print(f"Started   : {started}")
            print(f"Memory    : {rss_mb:.0f} MB")
        except Exception:
            print(f"State     : running (PID {proc.pid}, details unavailable)")

    healthy = _wait_for_health(port, timeout=3)
    print(f"Health    : {'responding' if healthy else 'NOT responding'}")
    print(f"URL       : http://localhost:{port}")
    return 0 if healthy else 1


def cmd_logs(args) -> int:
    path = log_file()
    if not path.exists():
        print(f"No log file at {path}")
        return 1
    # Read the tail without loading a multi-megabyte file into memory.
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        block = min(size, args.lines * 400)
        handle.seek(size - block)
        text = handle.read().decode("utf-8", errors="replace")
    for line in text.splitlines()[-args.lines:]:
        print(line)
    return 0


def cmd_doctor(args) -> int:
    """
    Check that this machine can run OpenEye, and name anything that is missing.

    Optional components degrade quietly by design — OpenEye runs without face
    recognition, object detection or two-way audio — so this reports which of
    them are actually available on this machine, alongside the hard
    prerequisites (interpreter version, ffmpeg, a writable data directory and
    a free port).
    """
    import shutil as _shutil

    problems = 0

    def check(label: str, ok: bool, detail: str = "") -> None:
        nonlocal problems
        mark = "ok  " if ok else "FAIL"
        print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
        if not ok:
            problems += 1

    print(f"Platform  : {sys.platform} ({os.name})")
    print(f"Python    : {sys.version.split()[0]} at {sys.executable}")
    print(f"App dir   : {APP_DIR}")
    print(f"Data root : {data_root()}")
    print("\nRuntime prerequisites:")

    major, minor = sys.version_info[:2]
    check("Python 3.9–3.12", (major, minor) >= (3, 9) and (major, minor) <= (3, 12),
          "numpy<2 and opencv<4.11 do not support 3.13")

    check("virtual environment", sys.prefix != sys.base_prefix or
          (APP_DIR / ".venv").exists(),
          "create one with: python -m venv .venv")

    ffmpeg = _shutil.which("ffmpeg")
    check("ffmpeg on PATH", ffmpeg is not None,
          ffmpeg or "video recording and clip export will fail")

    for module, feature in (
        ("cv2", "camera capture"),
        ("numpy", "everything"),
        ("fastapi", "the API"),
        ("psutil", "hardware detection and this script"),
    ):
        try:
            __import__(module)
            check(f"import {module}", True)
        except ImportError as exc:
            check(f"import {module}", False, f"{feature} unavailable ({exc})")

    print("\nOptional features:")
    for module, feature in (
        ("face_recognition", "face recognition"),
        ("dlib", "face recognition (native)"),
        ("sounddevice", "two-way audio"),
        ("aiortc", "two-way audio (WebRTC)"),
        ("ultralytics", "object detection"),
        ("netifaces", "network camera discovery"),
    ):
        try:
            __import__(module)
            print(f"  [ok  ] {module} — {feature} available")
        except ImportError:
            print(f"  [warn] {module} missing — {feature} disabled")

    port = args.port or resolve_port()
    print("\nNetworking:")
    check(f"port {port} available", port_is_free(port) or bool(find_server_processes(port)),
          "another application holds it")

    root = data_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        check("data root writable", True, str(root))
    except OSError as exc:
        check("data root writable", False, f"{root}: {exc}")

    if IS_WINDOWS:
        print("\nWindows notes:")
        print("  - USB cameras require Settings > Privacy & security > Camera, "
              "with both 'Camera access' and 'Let desktop apps access your "
              "camera' turned on. The second is off by default on many "
              "installations and denies access without an error.")
        print("  - Face recognition needs a C++ toolchain to install: "
              "Visual Studio Build Tools with the 'Desktop development with "
              "C++' workload. OpenEye runs without it.")
        print("  - ffmpeg is not included with Windows. Install it with "
              "'winget install Gyan.FFmpeg' and reopen your terminal, or set "
              "OPENEYE_FFMPEG to its full path.")

    print(f"\n{problems} problem(s) found." if problems else "\nNo problems found.")
    return 1 if problems else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="OpenEye lifecycle manager (Windows, macOS and Linux).",
    )
    parser.add_argument("--port", type=int, default=None,
                        help="override the resolved service port")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="start the server")
    start.add_argument("-f", "--foreground", action="store_true",
                       help="run in this terminal instead of the background")
    start.add_argument("--reload", action="store_true",
                       help="development auto-reload (not for production)")
    start.set_defaults(func=cmd_start)

    stop = sub.add_parser("stop", help="stop the server gracefully")
    stop.set_defaults(func=cmd_stop)

    restart = sub.add_parser("restart", help="stop then start")
    restart.add_argument("-f", "--foreground", action="store_true")
    restart.add_argument("--reload", action="store_true")
    restart.set_defaults(func=cmd_restart)

    status = sub.add_parser("status", help="report whether the server is up")
    status.set_defaults(func=cmd_status)

    logs = sub.add_parser("logs", help="tail the application log")
    logs.add_argument("-n", "--lines", type=int, default=100)
    logs.set_defaults(func=cmd_logs)

    doctor = sub.add_parser("doctor", help="check this machine can run OpenEye")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
