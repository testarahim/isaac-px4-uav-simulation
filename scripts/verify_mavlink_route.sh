#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILURES=0
WARNINGS=0

pass() {
    printf 'PASS: %s\n' "$1"
}

warn() {
    WARNINGS=$((WARNINGS + 1))
    printf 'WARN: %s\n' "$1"
}

fail() {
    FAILURES=$((FAILURES + 1))
    printf 'FAIL: %s\n' "$1"
}

check_file() {
    local path="$1"
    local label="$2"

    if [ -f "$path" ]; then
        pass "$label found at $path"
    else
        fail "$label missing at $path"
    fi
}

check_executable() {
    local path="$1"
    local label="$2"

    if [ -x "$path" ]; then
        pass "$label is executable at $path"
    elif [ -e "$path" ]; then
        fail "$label exists but is not executable at $path"
    else
        fail "$label missing at $path"
    fi
}

check_command() {
    local command_name="$1"
    local label="$2"

    if command -v "$command_name" >/dev/null 2>&1; then
        pass "$label available: $(command -v "$command_name")"
    else
        fail "$label command not found in PATH: $command_name"
    fi
}

check_contains() {
    local path="$1"
    local needle="$2"
    local label="$3"

    if grep -Fq -- "$needle" "$path"; then
        pass "$label configured: $needle"
    else
        fail "$label missing from $path: $needle"
    fi
}

printf 'MAVLink route verification\n'
printf 'Repository: %s\n\n' "$ROOT_DIR"

check_executable "$ROOT_DIR/configs/run_mavproxy.sh" "MAVProxy route script"
check_command mavproxy.py "MAVProxy"

ISAACSIM_DIR="${ISAACSIM_PATH:-$HOME/isaacsim}"
PEGASUS_DIR="${PEGASUS_DIR:-$HOME/PegasusSimulator}"
PX4_DIR="${PX4_DIR:-$HOME/PX4-Autopilot}"

check_executable "$ISAACSIM_DIR/isaac-sim.sh" "Isaac Sim launcher"
check_executable "$ISAACSIM_DIR/python.sh" "Isaac Sim Python"
check_file "$PEGASUS_DIR/extensions/pegasus.simulator/config/extension.toml" "Pegasus extension manifest"
check_executable "$PX4_DIR/build/px4_sitl_default/bin/px4" "PX4 SITL binary"

if [ -d "$PX4_DIR/.git" ]; then
    px4_version="$(git -C "$PX4_DIR" describe --tags --always 2>/dev/null || true)"
    if [ "$px4_version" = "v1.16.0" ]; then
        pass "PX4 version pinned to v1.16.0"
    elif [ -n "$px4_version" ]; then
        warn "PX4 version is $px4_version, expected v1.16.0"
    else
        warn "PX4 version could not be determined"
    fi
else
    fail "PX4 git repository missing at $PX4_DIR"
fi

if [ -f "$ROOT_DIR/configs/run_mavproxy.sh" ]; then
    check_contains "$ROOT_DIR/configs/run_mavproxy.sh" "--master=udp:127.0.0.1:14550" "MAVProxy master input"
    check_contains "$ROOT_DIR/configs/run_mavproxy.sh" "--out=udpout:127.0.0.1:14551" "QGroundControl output"
    check_contains "$ROOT_DIR/configs/run_mavproxy.sh" "--out=udpout:127.0.0.1:14542" "MAVSDK/script spare output through MAVProxy"
fi

printf '\nSummary: %s failure(s), %s warning(s)\n' "$FAILURES" "$WARNINGS"

if [ "$FAILURES" -ne 0 ]; then
    exit 1
fi
