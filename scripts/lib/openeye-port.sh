#!/usr/bin/env bash
# OpenEye — canonical service port resolution for shell scripts.
#
# Source this, then call openeye_resolve_port.
#
# Why this exists
# ---------------
# kill-server.sh, stop-server.sh and start-local.sh each hardcoded port 8000,
# while the application resolves its port through
# backend/core/config.py::resolve_service_port(), whose default is 8200. On a
# default install the scripts and the app therefore disagreed completely:
#
#   * start-local.sh launched uvicorn on 8000, but everything that registers or
#     advertises the service used 8200.
#   * stop-server.sh and kill-server.sh selected victims with `lsof -ti:8000`,
#     so they never found OpenEye at all — and did find whatever unrelated
#     process happened to hold 8000. On this machine that was another
#     application, which `kill -9` would have taken down.
#
# This mirrors resolve_service_port() exactly, so there is one rule and the
# scripts cannot drift from the application again.
#
# Precedence: ECOSYSTEM_SERVICE_PORT -> OPENEYE_PORT -> PORT -> config.env -> 8200

OPENEYE_DEFAULT_PORT=8200

openeye_resolve_port() {
    local var val config_root config_file

    # 1-3. Process environment, in the same order the application reads it.
    for var in ECOSYSTEM_SERVICE_PORT OPENEYE_PORT PORT; do
        val="$(printenv "$var" 2>/dev/null || true)"
        if [ -n "$val" ] && [ "$val" -eq "$val" ] 2>/dev/null; then
            printf '%s\n' "$val"
            return 0
        fi
    done

    # 4. The data root's config.env — the application loads this at startup, so
    #    a port set only there is still the real port.
    config_root="${OPENEYE_DATA_ROOT:-$HOME/Library/Application Support/OpenEye}"
    config_file="$config_root/config.env"
    if [ ! -f "$config_file" ] && [ -f "$HOME/.local/share/openeye/config.env" ]; then
        config_file="$HOME/.local/share/openeye/config.env"
    fi
    if [ -f "$config_file" ]; then
        for var in ECOSYSTEM_SERVICE_PORT OPENEYE_PORT PORT; do
            val="$(grep -E "^${var}=" "$config_file" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"' \r')"
            if [ -n "$val" ] && [ "$val" -eq "$val" ] 2>/dev/null; then
                printf '%s\n' "$val"
                return 0
            fi
        done
    fi

    # 5. Default.
    printf '%s\n' "$OPENEYE_DEFAULT_PORT"
}

# Print the PIDs on a port that actually belong to OpenEye.
#
# Selecting by port alone is how these scripts came to threaten unrelated
# software: `lsof -ti:<port>` matches every process holding a socket on that
# port, listeners and clients alike. Match the command line too, so a process
# that merely has a connection open is never a target.
openeye_service_pids() {
    local port="$1" pid cmd pids=""
    for pid in $(lsof -ti:"$port" 2>/dev/null || true); do
        cmd="$(ps -o command= -p "$pid" 2>/dev/null || true)"
        case "$cmd" in
            *uvicorn*backend.main:app*|*openeye*|*OpenEye*)
                pids="$pids $pid"
                ;;
        esac
    done
    printf '%s\n' "${pids# }"
}
