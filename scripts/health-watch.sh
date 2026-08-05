#!/usr/bin/env bash
# OpenEye — unattended health watch.
#
# Observes, records, and restarts. It does NOT fix anything: no code is edited,
# no configuration is rewritten, no data is touched. When it finds a problem it
# writes it down and, if the service is genuinely unhealthy, restarts it. Any
# actual repair is a human decision made later from the report.
#
# What it looks for, and why each check exists:
#
#   process     Is the server running at all.
#
#   latency     How long /api/health takes. This is the important one. A hung
#               camera read blocks inside AVFoundation while holding the frame
#               lock; every other frame consumer piles up behind it, the thread
#               pool drains, and unrelated endpoints queue behind a dead camera.
#               Observed in the wild: /api/health taking 24-40 SECONDS while the
#               process sat at 0.2% CPU. Idle and slow at the same time is the
#               signature of that livelock, and it is invisible to a plain
#               "is the port open" check.
#
#   cpu         Paired with latency. Slow + busy is load; slow + idle is blocked.
#
#   camera      Rate of frame-grab failures in the log.
#
#   log growth  Runaway repetition. A websocket error loop once wrote 24 million
#               lines and starved the event loop.
#
# Usage:
#   ./scripts/health-watch.sh              # one pass, restart if unhealthy
#   ./scripts/health-watch.sh --no-restart # observe and report only
#   ./scripts/health-watch.sh --quiet      # only print when something is wrong
#
# Report: $DATA_ROOT/logs/health-watch.log   (append-only, one block per run)
set -uo pipefail

DATA_ROOT="${OPENEYE_DATA_ROOT:-$HOME/.local/share/openeye}"
PORT="${OPENEYE_PORT:-8200}"
APP_LOG="$DATA_ROOT/logs/openeye-app.log"
REPORT="$DATA_ROOT/logs/health-watch.log"
APP_BUNDLE="${OPENEYE_APP_BUNDLE:-$HOME/Applications/OpenEye.app}"
VENV_PY="$DATA_ROOT/venv/bin/python3"

# Thresholds
SLOW_MS="${OPENEYE_SLOW_MS:-5000}"          # health slower than this = degraded
HANG_MS="${OPENEYE_HANG_MS:-15000}"         # slower than this = livelocked
IDLE_CPU="${OPENEYE_IDLE_CPU:-5.0}"         # below this while slow = blocked
GRAB_FAIL_LIMIT="${OPENEYE_GRAB_FAILS:-50}" # failures in the sampled window
RESTART_COOLDOWN_S="${OPENEYE_RESTART_COOLDOWN:-900}"  # never restart more often

NO_RESTART=0
QUIET=0
for a in "$@"; do
    case "$a" in
        --no-restart) NO_RESTART=1 ;;
        --quiet)      QUIET=1 ;;
        --help|-h)    sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
    esac
done

mkdir -p "$(dirname "$REPORT")"
TS="$(date '+%Y-%m-%d %H:%M:%S')"
STATUS="ok"
FINDINGS=()

note() { FINDINGS+=("$1"); }

# ---- process -------------------------------------------------------------
PID="$(pgrep -f "uvicorn backend.main:app" | head -1 || true)"
if [ -z "$PID" ]; then
    STATUS="down"
    note "server process not running"
    CPU="n/a"; MEM="n/a"
else
    read -r CPU MEM <<<"$(ps -o %cpu=,%mem= -p "$PID" 2>/dev/null | awk '{print $1, $2}')"
    CPU="${CPU:-0}"; MEM="${MEM:-0}"
fi

# ---- health latency ------------------------------------------------------
LATENCY_MS="n/a"
if [ -n "$PID" ] && [ -x "$VENV_PY" ]; then
    LATENCY_MS="$("$VENV_PY" - <<PYEOF 2>/dev/null || echo "timeout"
import time, urllib.request
t = time.time()
try:
    urllib.request.urlopen("http://localhost:$PORT/api/health", timeout=45)
    print(int((time.time() - t) * 1000))
except Exception:
    print("timeout")
PYEOF
)"
fi

case "$LATENCY_MS" in
    timeout)
        STATUS="hung"; note "/api/health did not answer within 45s" ;;
    ''|*[!0-9]*)
        [ -n "$PID" ] && { STATUS="unknown"; note "could not measure health latency"; } ;;
    *)
        if [ "$LATENCY_MS" -ge "$HANG_MS" ]; then
            STATUS="hung"
            note "/api/health took ${LATENCY_MS}ms (>= ${HANG_MS}ms)"
            # The distinguishing detail: blocked, not merely loaded.
            if awk -v c="$CPU" -v i="$IDLE_CPU" 'BEGIN{exit !(c < i)}'; then
                note "process is idle (${CPU}% CPU) while unresponsive — consistent with a blocked camera read holding the frame lock, not with load"
            fi
        elif [ "$LATENCY_MS" -ge "$SLOW_MS" ]; then
            [ "$STATUS" = "ok" ] && STATUS="degraded"
            note "/api/health slow: ${LATENCY_MS}ms"
        fi ;;
esac

# ---- camera + log signal -------------------------------------------------
GRAB_FAILS=0
LOG_MB=0
if [ -f "$APP_LOG" ]; then
    LOG_MB="$(du -m "$APP_LOG" 2>/dev/null | cut -f1)"
    GRAB_FAILS="$(tail -c 400000 "$APP_LOG" 2>/dev/null | grep -c "Failed to grab frame" || true)"
    if [ "${GRAB_FAILS:-0}" -ge "$GRAB_FAIL_LIMIT" ]; then
        [ "$STATUS" = "ok" ] && STATUS="degraded"
        note "camera: $GRAB_FAILS frame-grab failures in the recent log window"
    fi
    if [ "${LOG_MB:-0}" -ge 200 ]; then
        note "app log is ${LOG_MB}MB — check for repeating errors"
    fi
fi

# ---- restart decision ----------------------------------------------------
ACTION="none"
if [ "$STATUS" = "down" ] || [ "$STATUS" = "hung" ]; then
    if [ "$NO_RESTART" -eq 1 ]; then
        ACTION="restart suppressed (--no-restart)"
    else
        LAST=0
        [ -f "$REPORT" ] && LAST="$(grep -c "action=restarted" "$REPORT" 2>/dev/null || echo 0)"
        LAST_TS_FILE="$DATA_ROOT/logs/.health-watch-last-restart"
        NOW="$(date +%s)"
        PREV="$(cat "$LAST_TS_FILE" 2>/dev/null || echo 0)"
        if [ $((NOW - PREV)) -lt "$RESTART_COOLDOWN_S" ]; then
            # Restarting in a tight loop hides a problem instead of surfacing it.
            ACTION="restart skipped (cooldown, last was $((NOW - PREV))s ago)"
        else
            if [ -n "$PID" ]; then
                kill -TERM "$PID" 2>/dev/null
                sleep 6
                pgrep -f "uvicorn backend.main:app" >/dev/null 2>&1 && \
                    pkill -9 -f "uvicorn backend.main:app" 2>/dev/null
            fi
            # A camera wedged in AVFoundation needs the device to settle before
            # the next process opens it; restarting immediately reopens a dead
            # handle and the new process is born broken.
            sleep 15
            open -a "$APP_BUNDLE" 2>/dev/null || ACTION="restart FAILED: could not open $APP_BUNDLE"
            sleep 20
            NEWPID="$(pgrep -f "uvicorn backend.main:app" | head -1 || true)"
            if [ -n "$NEWPID" ]; then
                ACTION="restarted (new pid $NEWPID)"
                echo "$NOW" > "$LAST_TS_FILE"
            else
                ACTION="restart FAILED: process did not come back"
            fi
        fi
    fi
fi

# ---- report --------------------------------------------------------------
{
    echo "[$TS] status=$STATUS action=${ACTION} pid=${PID:-none} cpu=${CPU} mem=${MEM} health_ms=${LATENCY_MS} grab_fails=${GRAB_FAILS} log_mb=${LOG_MB}"
    for f in "${FINDINGS[@]:-}"; do [ -n "$f" ] && echo "    - $f"; done
} >> "$REPORT"

if [ "$QUIET" -eq 0 ] || [ "$STATUS" != "ok" ]; then
    echo "[$TS] OpenEye: $STATUS  (health ${LATENCY_MS}ms, cpu ${CPU}%, grab_fails ${GRAB_FAILS})"
    for f in "${FINDINGS[@]:-}"; do [ -n "$f" ] && echo "    - $f"; done
    [ "$ACTION" != "none" ] && echo "    action: $ACTION"
fi

# Exit code carries the state so a scheduler can act on it.
case "$STATUS" in
    ok)       exit 0 ;;
    degraded) exit 1 ;;
    *)        exit 2 ;;
esac
